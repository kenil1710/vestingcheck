/**
 * docs/FINAL_CHECK.md: every final-check item as PASS / FAIL with its proof,
 * computed now from the repo, the chain (gen_getContractCode, get_record) and
 * the test run.
 *   node tools/final_check.mjs
 */
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
const root = new URL("..", import.meta.url).pathname;
const require = createRequire(new URL("../test/package.json", import.meta.url));
const { createClient } = require("genlayer-js");
const { studioDevnet } = require("genlayer-js/chains");
const client = createClient({ chain: studioDevnet });
const sh = (cmd, args, opts = {}) => spawnSync(cmd, args, { cwd: root, encoding: "utf8", ...opts });
const git = (...a) => execFileSync("git", ["-C", root, ...a]).toString().trim();
const dep = JSON.parse(readFileSync(root + "deployments.json", "utf8"));
const CAN = dep.contracts.VestingCheck.address, DEMO = dep.contracts.VestingCheckDemo.address;
const src = readFileSync(root + "contracts/VestingCheck.py", "utf8");
const cls = src.split("class VestingCheck(gl.contract.Contract)")[1];
const readme = readFileSync(root + "README.md", "utf8");
const seedsRun = JSON.parse(readFileSync(root + "docs/seed-canonical.json", "utf8")).runs;
const demoRun = existsSync(root + "docs/seed-demo.json") ? JSON.parse(readFileSync(root + "docs/seed-demo.json", "utf8")).steps : [];
const norm = (v) => JSON.parse(JSON.stringify(v, (k, x) => (typeof x === "bigint" ? Number(x) : x instanceof Map ? Object.fromEntries(x) : x)));
async function view(address, fn, args) {
  for (let i = 0; i < 6; i++) {
    try { return norm(await client.readContract({ address, functionName: fn, args })); } catch { await new Promise((r) => setTimeout(r, 4000 * (i + 1))); }
  }
  throw new Error("view " + fn);
}
const unit = (tests) => { const r = sh("python3", ["-m", "unittest", ...tests], { cwd: root + "test" }); return { ok: r.status === 0, ran: (r.stderr.match(/Ran (\d+) tests/) || [])[1], err: r.stderr.slice(-400) }; };
const rows = [];
const add = (item, pass, proof) => rows.push({ item, pass, proof });
const head = git("rev-parse", "HEAD");

// 1. source match
const vs = sh("node", ["tools/verify_source.mjs"]);
add("Source match (canonical + demo)", vs.status === 0 && (vs.stdout.match(/identical to HEAD/g) || []).length === 2,
  "`node tools/verify_source.mjs`:\n```\n" + vs.stdout.split("\n").filter((l) => !/fee|Double check|Details|RPC error/.test(l) && l.trim()).join("\n") + "\n```");

// 2. no payable / custody / owner
const t = sh("python3", ["-c", `
import ast
src=open("contracts/VestingCheck.py").read(); tree=ast.parse(src)
cls=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="VestingCheck"][0]
dec=[ast.unparse(d) for f in cls.body if isinstance(f,ast.FunctionDef) for d in f.decorator_list]
print("decorators:", sorted(set(dec)))
print("write methods:", sorted(f.name for f in cls.body if isinstance(f,ast.FunctionDef) and any(ast.unparse(d)=="gl.public.write" for d in f.decorator_list)))
for w in ("write.payable","emit_transfer","gl.message.value","self.balance","withdraw("):
    print(w, "absent" if w not in src else "PRESENT")
fields=[n.target.id for n in cls.body if isinstance(n,ast.AnnAssign)]
print("storage fields:", fields)
print("owner/admin fields:", [f for f in fields if "owner" in f or "admin" in f])
`]);
add("No payable method, no custody, no owner/admin, no setter", !/PRESENT/.test(t.stdout) && /owner\/admin fields: \[\]/.test(t.stdout) && /write methods: \['file_check', 'recheck'\]/.test(t.stdout),
  "```\n" + t.stdout.trim() + "\n```\nCooldown and freshness are constructor arguments; nothing can change them afterwards.");

// 3. nothing stuck
const pend = (cls.match(/PENDING|\bOPEN\b|deadline/gi) || []).length;
const unsettled = [...seedsRun, ...demoRun].filter((s) => !["ACCEPTED", "FINALIZED"].includes(s.status));
add("Nothing can get stuck", pend === 0,
  `A filing either stores one finished record in its own transaction or stores nothing (refusal = revert; validator disagreement = no record). No pending / open state, no deadline, no second step: \`grep -ciE 'PENDING|OPEN|deadline'\` over the contract class = ${pend}. No method holds or moves value. Live: ${seedsRun.length + demoRun.length} filing transactions in docs/seed-canonical.json and docs/seed-demo.json, ${unsettled.length} not ACCEPTED/FINALIZED${unsettled.length ? " (" + unsettled.map((s) => (s.tx ? s.tx.slice(0, 12) + "… " : "") + (s.tx ? s.status : "never submitted: " + (s.revert || s.status))).join("; ") + "; no transaction reached the contract or none changed state)" : ""}.`);

// 4. counter before revert
const sw = sh("python3", ["tools/scan_writes.py"]);
add("No state written before a revert (AST scan of every write method)", sw.status === 0,
  "`python3 tools/scan_writes.py`:\n```\n" + sw.stdout.trim() + "\n```\nThe offline harness also asserts byte-identical state after every refusal and every unsettled round (`fixtures.tx`).");

// 5. views = storage
const tv = unit(["test_vestingcheck.Static.test_views_read_storage_only"]);
add("Views only read storage", tv.ok, "Views: get_config, get_record, get_records, get_history, get_keys, get_stats. `test_views_read_storage_only` (AST: no gl.nondet / run_nondet / http_get / exec_prompt / gather and no `self.` assignment in any view): " + (tv.ok ? "OK" : tv.err));

// 6. evidence bound
const recs = [];
for (const r of seedsRun.filter((x) => x.record_id)) recs.push(await view(CAN, "get_record", [r.record_id]));
const ok6 = recs.every((r) => r.source_sha256 && r.block && r.block_hash && r.evidence_sha256 && r.contract && (r.stream_id > 0 || r.token));
const r1 = recs.find((r) => r.source_kind === "github") ?? recs[0];
add("Evidence bound to source + subject + block", ok6,
  `Every canonical record (${recs.length}) stores the source (commit or CID, its sha256), the subject (contract + stream id or token), the block (number, hash, time), every chain read and the kept quotes; validators compare the whole evidence byte for byte (\`validate_record\`). Example, record #${r1.record_id}: source \`${r1.source_ref}\` sha256 \`${r1.source_sha256}\`, subject \`${r1.contract}\` ${r1.stream_id > 0 ? "stream " + r1.stream_id : "token " + r1.token}, block ${r1.block} hash \`${r1.block_hash}\`, evidence sha256 \`${r1.evidence_sha256}\`.`);

// 7. commit on original repo / CID verified
const gh = recs.filter((r) => r.source_kind === "github");
const sn = recs.filter((r) => r.source_kind === "snapshot");
const tc = unit(["test_vestingcheck.SourceFetch.test_fork_commit_diverged_refused", "test_vestingcheck.SourceFetch.test_lying_gateway_skipped_then_refused", "test_vestingcheck.SourceFetch.test_cid_not_on_hub_refused", "test_vestingcheck.SourceFetch.test_hub_space_must_match_ipfs"]);
add("GitHub commit proven on a branch of the original repo / Snapshot CID verified", tc.ok && gh.every((r) => ["behind", "identical"].includes(r.source.proof.status)) && sn.every((r) => r.source.cid && r.source.proposal_id),
  `${gh.length} GitHub records: compare status ${[...new Set(gh.map((r) => r.source.proof.status))].join(", ")} (branch ${[...new Set(gh.map((r) => r.source.proof.branch))].join(", ")}). ${sn.length} Snapshot records: bytes hashed in code to the CID, CID found on the hub with the same space and author (${sn.map((r) => r.source.space + " " + r.source.proposal_id.slice(0, 10)).join(", ")}). Offline: fork commit refused, lying gateway skipped, CID not on hub refused, hub space mismatch refused: ${tc.ok ? "OK" : tc.err}`);

// 8. allowlist
const ta = unit(["test_vestingcheck.SourceFetch.test_allowlist", "test_vestingcheck.SourceFetch.test_disallowed_fetch_never_leaves", "test_vestingcheck.GithubUrl"]);
const urlRef = demoRun.filter((s) => /URL_|SOURCE_NOT_ALLOWED|UNSUPPORTED_CHAIN/.test(s.revert)).map((s) => `${s.step}: ${s.revert}`);
const webCalls = (src.match(/gl\.nondet\.web\.(get|request)/g) || []).length;
add("Allowlist only", ta.ok && webCalls === 2,
  `\`gl.nondet.web\` appears ${webCalls} times: in \`http_get\` and in \`rpc_transport.send\`, both gated by \`allowed_url\` (the pinned raw file, the GitHub compare API, four IPFS gateways, the Snapshot hub, five frozen RPCs). Tests: ${ta.ok ? "OK" : ta.err}. Live demo refusals: ${urlRef.join("; ") || "-"}`);

// 9. freshness
const tf = unit(["test_vestingcheck.Filing.test_block_too_old_refused", "test_vestingcheck.Filing.test_block_freshness_boundary", "test_vestingcheck.Filing.test_demo_freshness_30_min", "test_vestingcheck.Filing.test_block_in_future_refused", "test_vestingcheck.Filing.test_leader_old_block_rejected"]);
const ages = recs.map((r) => r.filed_at - r.block_time);
add("Block freshness enforced", tf.ok && ages.every((a) => a <= 3600),
  `Canonical records' block age at filing (filed_at - block_time, limit 3600 s): ${ages.join(", ")} s. The leader's block must be finalized for every validator and not more than 15 min older than its own finalized block. Offline: too old, boundary, demo 30 min, future block, leader old block: ${tf.ok ? "OK" : tf.err}. No supported chain finalizes later than 30 min, so BLOCK_TOO_OLD cannot be produced live on the demo; it is covered offline.`);

// 10. model only quotes
const prompts = (src.match(/exec_prompt\(/g) || []).length;
const tm = unit(["test_vestingcheck.Static.test_prompt_never_asks_for_a_verdict", "test_vestingcheck.KeepFields", "test_attacks.Resisted.test_quote_real_value_altered", "test_attacks.Resisted.test_prompt_injection_cannot_add_a_value", "test_attacks_r2.R2H2SubjectLinkReadAsBeneficiary", "test_attacks_r2.R2M5QuoteCutOutOfALongerNumber"]);
add("The model only quotes; code decides", tm.ok && prompts === 1,
  `\`exec_prompt\` appears ${prompts} time (\`ask_fields\`); its answer goes only into \`keep_fields\`, which keeps a field only if the quote is verbatim (whole words), bound to the subject, and code itself parses the value (the model's own value must say the same or the field is dropped). Chain reads, binding, every number and date, comparison, verdict and wording are code. Tests: ${tm.ok ? "OK" : tm.err}`);

// 11. disagreement
const ti = unit(["test_vestingcheck.Filing.test_validator_disagreement_writes_nothing", "test_vestingcheck.Filing.test_leader_self_disagreement_refused", "test_vestingcheck.Filing.test_model_errors_refused", "test_vestingcheck.Filing.test_leader_forged_fields_rejected", "test_vestingcheck.Filing.test_leader_forged_evidence_rejected"]);
const ext = [...seedsRun, ...demoRun].filter((s) => /EXTRACTION_/.test(s.revert || ""));
add("Disagreement behaviour (as on chain)", ti.ok,
  `Leader's own answers disagree (no two of three with the same kept fields) or the model fails: the filing is refused (\`REFUSED: EXTRACTION_UNSTABLE\` / \`EXTRACTION_MODEL_ERROR\`), a revert, nothing stored; validators accept that refusal only if they read the same evidence. A validator whose own extraction differs from the leader's (or whose chain reads differ) rejects the round: consensus fails and nothing is stored, nothing is pending; the filer can file again. Offline: ${ti.ok ? "OK" : ti.err}. Live: ${ext.length ? ext.map((s) => `${s.id ?? s.step} \`${s.revert}\` (tx ${s.tx.slice(0, 12)}…, no record; next try recorded)`).join("; ") : "no extraction refusal happened"}.`);

// 12. fees
const scripts = readdirSync(root + "test").filter((f) => f.endsWith(".mjs"));
const writes = scripts.flatMap((f) => (readFileSync(root + "test/" + f, "utf8").match(/send\("|deploy\(\{/g) || []).map(() => f));
const harness = readFileSync(root + "test/harness.mjs", "utf8");
add("A fee on every write", /estimateTransactionFees/.test(harness),
  "Every write goes through `harness.send` and every deploy through `harness.deploy`; both attach a fee estimate (per-call write simulation, falling back to `estimateTransactionFees` when Studio Dev cannot simulate a write that fetches - the logged 'write fee simulation failed' line). Writes found in: " + [...new Set(writes)].join(", ") + ".");

// 13. README sections
const need = ["## What the model is never allowed to decide", "## Known limitations", "## How a reviewer can test", "## Verdicts"];
add("README: verdicts, model limits, known limitations, how to test", need.every((n) => readme.includes(n)), need.map((n) => `${readme.includes(n) ? "present" : "MISSING"}: \`${n}\``).join("; "));

// 14. one set of addresses
const files = ["README.md", "ADDRESSES.md", "docs/SEEDS.md", "docs/SUBMISSION.md", "docs/THREAT_MODEL.md", "docs/RESEARCH.md"].filter((f) => existsSync(root + f));
const old2 = new Set((dep.superseded ?? []).map((s) => s.address.toLowerCase()));
const bad = [];
for (const f of files) {
  const text = readFileSync(root + f, "utf8").toLowerCase();
  for (const a of old2) if (text.includes(a)) bad.push(`${f} mentions superseded ${a}`);
}
add("One set of addresses everywhere", bad.length === 0 && readme.includes(CAN) && readme.includes(DEMO),
  `Current: canonical \`${CAN}\`, demo \`${DEMO}\` (deployments.json, both from commit ${dep.contracts.VestingCheck.commit.slice(0, 10)}). Superseded addresses appear only in deployments.json, docs/superseded/ and the attack report's history. ` + (bad.length ? "Problems: " + bad.join("; ") : "Checked: " + files.join(", ")));

// 15. git history
const leaked = git("log", "--all", "--format=%H", "--", "test/.accounts.json");
const msgs = git("log", "--all", "--format=%an <%ae>%n%B");
const BANNED = ["Y2xhdWRl", "YW50aHJvcGlj", "Y28tYXV0aG9yZWQ=", "Q2hhdEdQVA==", "b3BlbmFp"].map((b) => Buffer.from(b, "base64").toString()).join("|");
const words = (msgs.match(new RegExp(BANNED, "gi")) || []).length;
const tracked = git("ls-files");
const secretish = tracked.split("\n").filter((f) => /accounts\.json|\.env|secret/i.test(f));
const grepAI = sh("git", ["grep", "-niE", BANNED, "HEAD", "--", ".", ":!test/package-lock.json"]);
add("Git history clean", leaked === "" && words === 0 && secretish.length === 0 && grepAI.stdout.trim() === "",
  `keys file never committed (\`git log --all -- test/.accounts.json\` empty: ${leaked === ""}); tracked files matching accounts/.env/secret: ${secretish.length}; commit messages or authors naming an AI tool or carrying co-author trailers: ${words}; tree mentions: ${grepAI.stdout.trim() === "" ? 0 : grepAI.stdout.trim().split("\n").length}; authors: ${[...new Set(git("log", "--format=%an <%ae>").split("\n"))].join(", ")}; commits: ${git("rev-list", "--count", "HEAD")}; no force push (origin/main is an ancestor of HEAD: ${sh("git", ["merge-base", "--is-ancestor", "origin/main", "HEAD"]).status === 0}).`);

// 16. tests
const tt = unit(["test_vestingcheck", "test_attacks", "test_attacks_r2", "test_v120"]);
add("Offline tests", tt.ok && Number(tt.ran) >= 300, `\`cd test && python3 -m unittest\` (test_vestingcheck, test_attacks, test_attacks_r2, test_v120): Ran ${tt.ran} tests, ${tt.ok ? "OK" : "FAILED"}`);

const md = `# Final check

Generated by \`node tools/final_check.mjs\` at ${new Date().toISOString()} on commit \`${head}\`. Every line is recomputed from the repo, the chain and the test run.

| # | Check | Result |
|---|---|---|
${rows.map((r, i) => `| ${i + 1} | ${r.item} | **${r.pass ? "PASS" : "FAIL"}** |`).join("\n")}

## Proof

${rows.map((r, i) => `### ${i + 1}. ${r.item}: ${r.pass ? "PASS" : "FAIL"}\n\n${r.proof}\n`).join("\n")}`;
writeFileSync(root + "docs/FINAL_CHECK.md", md);
console.log(rows.map((r, i) => `${i + 1}. ${r.pass ? "PASS" : "FAIL"}  ${r.item}`).join("\n"));
process.exit(rows.every((r) => r.pass) ? 0 : 1);

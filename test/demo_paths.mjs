/**
 * Drives the DEMO deployment (60 s cooldown, 30 min freshness) through every
 * path that can happen live: each verdict, the refusals, the cooldown, the
 * duplicate rule and a recheck after the cooldown. Writes docs/seed-demo.json
 * (resumable). The six disagreeing verdicts use docs/demo/claims.md, this
 * repo's own demo statements about real streams and wallets (see its header);
 * MATCHES and UNVERIFIABLE use real sources.
 *   node demo_paths.mjs [--only=step,step]
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { connect, argOf, sleep, returnedJson } from "./harness.mjs";

const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8"));
const address = dep.contracts.VestingCheckDemo.address;
const outPath = new URL("../docs/seed-demo.json", import.meta.url);
const doc = existsSync(outPath) ? JSON.parse(readFileSync(outPath, "utf8")) : { contract: address, steps: [] };
if (doc.contract !== address) { console.error(`docs file is for ${doc.contract}, not ${address}`); process.exit(1); }
const save = () => writeFileSync(outPath, JSON.stringify(doc, null, 2) + "\n");
const { send, view } = connect({ address, role: argOf("role", "filer") });
const only = argOf("only") ? argOf("only").split(",") : null;

const DEMO_SHA = argOf("demo_sha", "44491d5b8ff593f912fe3ddebd73c5bbfad24366");
const DEMO = `https://raw.githubusercontent.com/kenil1710/vestingcheck/${DEMO_SHA}/docs/demo/claims.md`;
const CLX = "https://raw.githubusercontent.com/clx-trade/crossledger-site/388aa0af887f9cbf9312c31c2f11da0bebbb90d3/lib/site.js";
const NATION3 = "bafkreiax3o7zuvfdu6vn447hu6ypmu4weqmyodikiyav6lkcibn3cfgdh4";
const EXAIP23 = "bafkreigcle3bklsp4o6os6kn6zxyduagdmt22d2dt73dode2cult5ydfye";
const LK3 = "0x93b37bd5b6b278373217333ac30d7e74c85fbdcb";          // Sablier Lockup v4.0, Ethereum
const LT3_BASE = "0xf4937657ed8b3f3cb379eed47b8818ee947beb1e";     // Sablier Lockup Tranched v1.2, Base
const LL_OP = "0xb923abdca17aed90eb5ec5e407bd37164f632bfd";        // Sablier Lockup Linear v1.0, Optimism
const IDOS = "0x68731d6f14b827bbcffbebb62b19daa18de1d79c";
const W_TREASURY = "0x6a553c044a6a113b01be52372e8d7bc94594bbe8";
const W_STAKING = "0x03ed348892a88182e74d8e76e6f7529224032ed8";
const ANT_WALLET = "0x5cb5ba62dc8ced477f20d4692986f1cd42174761";
const ANT = "0xa117000000f279d81a1d3cc75430faa017fa5a2e";

// [name, method, args, expected, github?]
const STEPS = [
  ["unlocks_earlier", "file_check", [DEMO, "", "ethereum", LK3, "1784"], "UNLOCKS_EARLIER", true],
  ["unlocks_later", "file_check", [DEMO, "", "ethereum", LK3, "1783"], "UNLOCKS_LATER", true],
  ["more_than_claimed", "file_check", [DEMO, "", "ethereum", LK3, "1785"], "MORE_THAN_CLAIMED", true],
  ["less_than_claimed", "file_check", [DEMO, "", "arbitrum", W_TREASURY, IDOS], "LESS_THAN_CLAIMED", true],
  ["cancelable_not_disclosed", "file_check", [DEMO, "", "base", LT3_BASE, "1980"], "CANCELABLE_NOT_DISCLOSED", true],
  ["beneficiary_differs", "file_check", [DEMO, "", "arbitrum", W_STAKING, IDOS], "BENEFICIARY_DIFFERS", true],
  ["matches_real_docs", "file_check", [CLX, "", "ethereum", LK3, "1785"], "MATCHES", true],
  ["unverifiable_real_proposal", "file_check", [NATION3, "", "ethereum", ANT_WALLET, ANT], "UNVERIFIABLE", false],
  // refusals before consensus
  ["refuse_not_pinned", "file_check", [DEMO.replace(DEMO_SHA, "main"), "", "ethereum", LK3, "1784"], "URL_NOT_PINNED_TO_COMMIT", false],
  ["refuse_host", "file_check", ["https://docs.example.com/vesting.md", "", "ethereum", LK3, "1784"], "URL_HOST_NOT_ALLOWED", false],
  ["refuse_chain", "file_check", [DEMO, "", "bsc", LK3, "1784"], "UNSUPPORTED_CHAIN", false],
  ["refuse_branch_for_snapshot", "file_check", [NATION3, "main", "ethereum", ANT_WALLET, ANT], "BRANCH_ONLY_FOR_GITHUB", false],
  ["refuse_stream_id_required", "file_check", [DEMO, "", "ethereum", LK3, ""], "STREAM_ID_REQUIRED", false],
  ["refuse_token_required", "file_check", [NATION3, "", "ethereum", ANT_WALLET, ""], "TOKEN_ADDRESS_REQUIRED", false],
  // refusals after the evidence is read
  ["refuse_subject_not_in_source", "file_check", [EXAIP23, "", "optimism", LL_OP, "7157"], "SUBJECT_NOT_IN_SOURCE", false],
  ["refuse_stream_not_found", "file_check", [EXAIP23, "", "optimism", LL_OP, "999999999"], "STREAM_NOT_FOUND", false],
  // cooldown, duplicate, recheck
  ["refuse_cooldown", "file_check", [NATION3, "", "ethereum", ANT_WALLET, ANT], "COOLDOWN_UNTIL", false],
  ["refuse_recheck_cooldown", "recheck", ["@unverifiable_real_proposal"], "COOLDOWN_UNTIL", false],
  ["wait_cooldown", "sleep", [65_000], "", false],
  ["duplicate_same_block", "file_check", [NATION3, "", "ethereum", ANT_WALLET, ANT], "DUPLICATE_OF_RECORD", false],
  ["wait_new_block", "sleep", [480_000], "", false],
  ["recheck_after_cooldown", "recheck", ["@unverifiable_real_proposal"], "(new record linked to the first)", false],
  ["refuse_unknown_record", "recheck", [9999], "NO_SUCH_RECORD", false],
];

const idOf = (name) => doc.steps.find((s) => s.step === name && s.record_id)?.record_id;
let lastGithub = 0;
for (const [name, method, args0, expect, github] of STEPS) {
  if (only && !only.includes(name)) continue;
  if (!only && doc.steps.some((s) => s.step === name && (s.record_id || s.matched))) { console.log(`skip ${name}`); continue; }
  if (method === "sleep") { console.log(`sleep ${args0[0] / 1000}s`); await sleep(args0[0]); continue; }
  if (github) {
    const wait = lastGithub + 330_000 - Date.now();
    if (wait > 0) { console.log(`  GitHub spacing: waiting ${Math.round(wait / 1000)}s`); await sleep(wait); }
    lastGithub = Date.now();
  }
  const args = args0.map((a) => (typeof a === "string" && a.startsWith("@") ? idOf(a.slice(1)) : a));
  console.log(`\n${name}: ${method}(${JSON.stringify(args).slice(0, 170)})  expect ${expect}`);
  const out = await send(method, args);
  const ret = returnedJson(out);
  const step = { step: name, method, args, expect, at: new Date().toISOString(), tx: out.hash, status: out.status, ok: out.ok,
    seconds: out.seconds, revert: out.ok ? "" : String(out.revertReason ?? out.failure ?? "").slice(0, 200) };
  if (out.ok && ret?.record_id) Object.assign(step, { record_id: ret.record_id, prev_id: ret.prev_id, verdict: ret.verdict, basis: ret.basis, block: ret.block, summary: ret.summary });
  step.matched = expect.startsWith("(") ? Boolean(step.record_id) : (step.verdict === expect || step.revert.includes(expect));
  doc.steps.push(step); save();
  console.log(`  ${out.status} ok=${out.ok} ${step.verdict ?? step.revert}  matched=${step.matched}  ${out.seconds}s ${out.hash}`);
  await sleep(8_000);
}
console.log("\nstats", JSON.stringify(await view("get_stats")));

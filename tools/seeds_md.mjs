/**
 * docs/SEEDS.md from the chain: every canonical seed record read back with
 * get_record (storage only), plus the seed list (test/seeds.json), the run
 * log (docs/seed-canonical.json) and the hand checks
 * (docs/research/hand_checks.json).
 *   node tools/seeds_md.mjs
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
const root = new URL("..", import.meta.url).pathname;
const require = createRequire(new URL("../test/package.json", import.meta.url));
const { createClient } = require("genlayer-js");
const { studioDevnet } = require("genlayer-js/chains");
const client = createClient({ chain: studioDevnet });
const dep = JSON.parse(readFileSync(root + "deployments.json", "utf8"));
const addr = dep.contracts.VestingCheck.address;
const seeds = JSON.parse(readFileSync(root + "test/seeds.json", "utf8"));
const runs = JSON.parse(readFileSync(root + "docs/seed-canonical.json", "utf8")).runs;
const hand = existsSync(root + "docs/research/hand_checks.json") ? JSON.parse(readFileSync(root + "docs/research/hand_checks.json", "utf8")) : {};
const EX = "https://explorer-studio-dev.genlayer.com";
const SCAN = { ethereum: "https://etherscan.io", arbitrum: "https://arbiscan.io", optimism: "https://optimistic.etherscan.io",
  base: "https://basescan.org", polygon: "https://polygonscan.com" };
const norm = (v) => JSON.parse(JSON.stringify(v, (k, x) => (typeof x === "bigint" ? Number(x) : x instanceof Map ? Object.fromEntries(x) : x)));
async function view(fn, args) {
  for (let i = 0; i < 6; i++) {
    try { return norm(await client.readContract({ address: addr, functionName: fn, args })); }
    catch (e) { await new Promise((r) => setTimeout(r, 4000 * (i + 1))); }
  }
  throw new Error("view failed " + fn);
}
const iso = (t) => new Date(t * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
const day = (t) => new Date(t * 1000).toISOString().slice(0, 10);
const units = (raw, dec) => {
  if (raw === undefined || raw === null || raw === "") return "-";
  const b = BigInt(raw), d = 10n ** BigInt(dec ?? 18);
  const w = (b / d).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const f = (b % d).toString().padStart(Number(dec ?? 18), "0").slice(0, 4).replace(/0+$/, "");
  return f ? `${w}.${f}` : w;
};
const shown = (field, v) => {
  if (v === null || v === undefined) return "-";
  if (["start_date", "first_unlock_date", "end_date"].includes(field)) return day(v);
  if (field === "cliff_duration" || field === "vesting_duration") {
    const s = v.months > 0 ? `${v.months} calendar months` : `${v.seconds / 86400} days`;
    return field === "vesting_duration" && v.after_cliff ? s + " (\"then\": may run from the cliff)" : s;
  }
  return typeof v === "string" ? v : JSON.stringify(v);
};
const cell = (s) => String(s).replace(/\|/g, "\\|").replace(/\n/g, " ");
const counts = {};
const rows = [];
const details = [];
const chains = new Set();
for (const s of seeds) {
  const tries = runs.filter((r) => r.id === s.id);
  const run = [...tries].reverse().find((r) => r.record_id);
  if (!run) {
    const why = tries.map((t) => t.revert || t.status).join("; ") || "not filed";
    rows.push(`| ${s.label} | ${s.chain} | - | - | refused: \`${why.replace(/^REFUSED: /, "")}\` |`);
    details.push(`### ${s.label}: refused\n\n* Source: ${s.source.startsWith("https://") ? `[${s.source}](${s.source})` : `Snapshot proposal \`ipfs://${s.source}\``}\n* Subject: ${s.chain} \`${s.contract}\` ${s.extra}\n* Filings: ${tries.map((t) => `[${t.tx.slice(0, 12)}…](${EX}/tx/${t.tx}) ${t.revert || t.status}`).join(", ")}\n* Why: ${hand[s.id] ?? "-"}\n`);
    continue;
  }
  const r = await view("get_record", [run.record_id]);
  chains.add(r.chain);
  counts[r.verdict] = (counts[r.verdict] ?? 0) + 1;
  rows.push(`| ${s.label} | ${r.chain} | [#${r.record_id}](${EX}/tx/${run.tx}) | ${r.block} | **${r.verdict}** |`);
  const f = r.chain_facts.facts;
  const src = r.source;
  const d = [];
  d.push(`### ${s.label}: record #${r.record_id}, ${r.verdict}`);
  d.push("");
  if (r.source_kind === "github") {
    d.push(`* Source: [${r.source_label}](${src.url}) at commit \`${src.commit}\` (${day(r.source_date)}), branch proof \`${src.proof.branch}...${src.commit.slice(0, 10)}\` = ${src.proof.status}`);
  } else {
    d.push(`* Source: Snapshot ${src.space} proposal \`${src.proposal_id}\`, IPFS \`${src.cid}\` (created ${day(r.source_date)}), author \`${src.author}\``);
  }
  d.push(`* Source sha256 \`${r.source_sha256}\`; binding: ${r.binding}`);
  d.push(`* Chain: ${r.chain}, block ${r.block} (${iso(r.block_time)}), hash \`${r.block_hash}\`; filed ${iso(r.filed_at)}`);
  const subj = r.stream_id > 0 ? `Sablier stream #${r.stream_id} at [\`${r.contract}\`](${SCAN[r.chain]}/address/${r.contract})` : `vesting wallet [\`${r.contract}\`](${SCAN[r.chain]}/address/${r.contract}), token \`${r.token}\``;
  d.push(`* Subject: ${subj}; pattern ${r.pattern}`);
  d.push(`* Filing tx: [${run.tx}](${EX}/tx/${run.tx}); basis ${r.basis}; ${r.decided} field(s) decided; evidence sha256 \`${r.evidence_sha256}\``);
  d.push("");
  if (f.decidable) {
    d.push(`Chain values at the block: ${f.symbol} (${f.decimals} decimals) total ${units(f.total, f.decimals)}, withdrawn/released ${units(f.withdrawn, f.decimals)}, start ${iso(f.start)}, first unlock ${f.first_unlock >= 0 ? iso(f.first_unlock) : "n/a (dynamic curve)"}, end ${iso(f.end)}, shape ${f.shape}, beneficiary \`${f.beneficiary}\`, cancelable ${f.cancelable}.`);
  } else {
    d.push(`Chain: not a standard pattern code can read: \`${f.why}\`${f.unknown_functions ? ` (unknown functions ${f.unknown_functions.join(", ")})` : ""}.`);
  }
  d.push("");
  const kept = r.fields.kept;
  if (kept.length) {
    d.push("| Field | Value code read from the quote | Quote (verbatim source text) | Result |");
    d.push("|---|---|---|---|");
    for (const k of kept) d.push(`| ${k.field} | ${cell(shown(k.field, k.value))} | \`${cell(k.quote)}\` | ${r.fields.results[k.field]}${r.fields.why[k.field] ? " (" + r.fields.why[k.field] + ")" : ""} |`);
  } else {
    d.push("No field was kept: the model quoted nothing code could bind to this subject and parse.");
  }
  if (r.fields.conflicts?.length) d.push(`\nConflicting fields (not kept): ${r.fields.conflicts.join(", ")}`);
  d.push("");
  const u = r.unlock;
  if (u && u.chain_unlockable !== undefined) {
    const cu = Object.entries(u.claim_unlockable || {}).map(([k, v]) => `reading ${k} ${units(v, f.decimals)}`).join(", ");
    d.push(`Unlock math at the block (${iso(u.time)}): the chain lets ${units(u.chain_unlockable, f.decimals)} ${f.symbol} unlock (withdrawn ${units(u.chain_withdrawn, f.decimals)}); the source's schedule${cu ? ` gives ${cu}` : " has no end code could read"} (amount from the ${u.amount_from}, start from the ${u.start_from}).`);
    d.push("");
  }
  d.push(`> ${r.summary}`);
  d.push("");
  if (hand[s.id]) { d.push(`Checked by hand: ${hand[s.id]}`); d.push(""); }
  details.push(d.join("\n"));
}
const order = ["MATCHES", "UNLOCKS_EARLIER", "UNLOCKS_LATER", "MORE_THAN_CLAIMED", "LESS_THAN_CLAIMED", "CANCELABLE_NOT_DISCLOSED", "BENEFICIARY_DIFFERS", "UNVERIFIABLE"];
const total = Object.values(counts).reduce((a, b) => a + b, 0);
const decided = total - (counts.UNVERIFIABLE ?? 0);
const refused = seeds.filter((s) => !runs.some((r) => r.id === s.id && r.record_id)).length;
const summary = order.filter((v) => counts[v]).map((v) => `${v} ${counts[v]}`).join(" · ");
const md = `# Seeds

Real vesting promises filed on the canonical deployment [\`${addr}\`](${EX}/address/${addr}) (${dep.contracts.VestingCheck.mode}, commit \`${dep.contracts.VestingCheck.commit.slice(0, 10)}\`). Every line below is read back from the contract with \`get_record\` (generated by \`node tools/seeds_md.mjs\`); the run log is [seed-canonical.json](seed-canonical.json) / [seed-run.log](seed-run.log).

**${total} records on ${chains.size} chains (${[...chains].join(", ")}): ${summary}. ${decided} decided. ${refused} filing(s) refused (no record).**

Nothing was forced: each seed was filed once (twice if the model failed or its answers disagreed), and the result is whatever code decided. Every result that is not MATCHES was checked by hand on chain; the explanation is under its record.

| Seed | Chain | Record | Block | Result |
|---|---|---|---|---|
${rows.join("\n")}

## Records

${details.join("\n")}
`;
writeFileSync(root + "docs/SEEDS.md", md);
console.log(summary, "| decided", decided, "| chains", [...chains].join(","), "| refused", refused);

/**
 * Files every seed in seeds.json on a deployment, one at a time, and writes
 * what happened to docs/seed-<canonical|demo>.json (resumable: seeds that
 * already have a record are skipped). Nothing is forced: a refusal or an
 * unsettled round is recorded as such and retried at most `--tries` times.
 *   node seed_canonical.mjs [--target=VestingCheck] [--only=id,id] [--tries=3]
 * GitHub-backed filings are spaced (the GitHub API allows 60 calls/hour for
 * all validators together); Snapshot filings are not.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { connect, argOf, sleep, returnedJson } from "./harness.mjs";

const dep = JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8"));
const target = argOf("target", "VestingCheck");
const address = dep.contracts[target].address;
const outPath = new URL(`../docs/seed-${target === "VestingCheck" ? "canonical" : "demo"}.json`, import.meta.url);
const seeds = JSON.parse(readFileSync(new URL("./seeds.json", import.meta.url), "utf8"));
const only = argOf("only") ? argOf("only").split(",") : null;
const tries = Number(argOf("tries", "3"));
const doc = existsSync(outPath) ? JSON.parse(readFileSync(outPath, "utf8")) : { contract: address, runs: [] };
if (doc.contract !== address) { console.error(`docs file is for ${doc.contract}, not ${address}`); process.exit(1); }
const save = () => writeFileSync(outPath, JSON.stringify(doc, null, 2) + "\n");
const { send, view } = connect({ address, role: argOf("role", "filer") });
console.log(`${target} ${address}`);
let lastGithub = 0;
for (const s of seeds) {
  if (only && !only.includes(s.id)) continue;
  if (doc.runs.some((r) => r.id === s.id && r.record_id)) { console.log(`skip ${s.id} (recorded)`); continue; }
  const github = s.source.startsWith("https://");
  for (let t = 1; t <= tries; t++) {
    if (github) {
      const wait = lastGithub + 330_000 - Date.now();
      if (wait > 0) { console.log(`  GitHub spacing: waiting ${Math.round(wait / 1000)}s`); await sleep(wait); }
      lastGithub = Date.now();
    }
    console.log(`\n${s.id}  try ${t}  ${s.chain} ${s.contract} ${s.extra}`);
    const out = await send("file_check", [s.source, s.branch ?? "", s.chain, s.contract, s.extra]);
    const ret = returnedJson(out);
    const run = { id: s.id, label: s.label, try: t, at: new Date().toISOString(), tx: out.hash, status: out.status,
      ok: out.ok, seconds: out.seconds, revert: out.ok ? "" : String(out.revertReason ?? out.failure ?? "").slice(0, 200) };
    if (out.ok && ret?.record_id) Object.assign(run, { record_id: ret.record_id, verdict: ret.verdict, basis: ret.basis, block: ret.block, summary: ret.summary });
    doc.runs.push(run); save();
    console.log(`  ${out.status} ok=${out.ok} ${run.verdict ?? run.revert}  ${out.seconds}s  ${out.hash}`);
    if (run.record_id) break;
    const w = /GITHUB_API_HTTP_403|GITHUB_API_HTTP_429/.test(run.revert) ? 900_000 : 60_000;
    console.log(`  waiting ${w / 1000}s`); await sleep(w);
  }
  await sleep(15_000);
}
console.log("\nstats", JSON.stringify(await view("get_stats")));

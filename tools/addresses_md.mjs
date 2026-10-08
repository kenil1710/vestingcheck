/** ADDRESSES.md and docs/superseded/README.md from deployments.json.
 *   node tools/addresses_md.mjs */
import { readFileSync, writeFileSync } from "node:fs";
const root = new URL("..", import.meta.url).pathname;
const dep = JSON.parse(readFileSync(root + "deployments.json", "utf8"));
const EX = "https://explorer-studio-dev.genlayer.com";
const c = dep.contracts;
const row = (r) => `| ${r.mode} | [\`${r.address}\`](${EX}/address/${r.address}) | \`${JSON.stringify(r.constructor_args)}\` | [\`${r.commit.slice(0, 10)}\`](https://github.com/kenil1710/vestingcheck/commit/${r.commit}) | [deploy tx](${EX}/tx/${r.deploy_tx}) | \`${r.sha256}\` |`;
writeFileSync(root + "ADDRESSES.md", `# Addresses

Network: GenLayer Studio Dev (chain id ${dep.chain_id}), RPC \`${dep.rpc}\`, explorer ${dep.explorer}

| Deployment | Address | Constructor (mode, cooldown s, freshness s) | Commit | Deploy | contracts/VestingCheck.py sha256 |
|---|---|---|---|---|---|
${row(c.VestingCheck)}
${row(c.VestingCheckDemo)}

Both deployments are the same file from the same commit; only the constructor differs. \`node tools/verify_source.mjs\` reads the code back with \`gen_getContractCode\` and compares it byte for byte with \`contracts/\` at HEAD.

Previous deployments: [docs/superseded/README.md](docs/superseded/README.md).
`);
const sup = dep.superseded ?? [];
writeFileSync(root + "docs/superseded/README.md", `# Superseded deployments

These addresses ran earlier versions of \`contracts/VestingCheck.py\`. They are kept only for history; use [ADDRESSES.md](../../ADDRESSES.md).

| Deployment | Address | Commit | Replaced by | Why |
|---|---|---|---|---|
${sup.map((s) => `| ${s.name} (${s.mode}) | \`${s.address}\` | \`${s.commit.slice(0, 10)}\` | \`${s.superseded_by}\` | ${s.why} |`).join("\n")}

Seed runs on earlier canonical deployments:

* v1.0.0: [seed-canonical-v1.0.0.json](seed-canonical-v1.0.0.json). Stopped when the round-1 attacker pass changed the contract (H1, H2, M1-M4).
* v1.1.0: [seed-canonical-v1.1.0.json](seed-canonical-v1.1.0.json), log [seed-run-v1.1.0.log](seed-run-v1.1.0.log). 7 records (BENEFICIARY_DIFFERS 1, UNVERIFIABLE 6) and 3 refusals. Not used: the docs parser dropped every claim on the three GitHub seeds, and the one decided record (nation3, BENEFICIARY_DIFFERS) was wrong: the model had labelled a link to the vesting contract itself as the beneficiary, and v1.1.0 accepted it. v1.2.0 refuses that (docs/ATTACK_REPORT.md, R2-H2).
* v1.2.0: [seed-canonical-v1.2.0-stopped.json](seed-canonical-v1.2.0-stopped.json), log [seed-run-v1.2.0-stopped.log](seed-run-v1.2.0-stopped.log). Stopped after 3 records (UNVERIFIABLE: nation3, Connext, AKITA) and 1 refusal (EXAIP-23), when the first CrossLedger filing was refused as EXTRACTION_UNSTABLE: the model quoted the date-written schedule in different lengths and v1.2.0 kept some of them. v1.2.1 reads each date by the source words in front of it.
`);
console.log("wrote ADDRESSES.md and docs/superseded/README.md");

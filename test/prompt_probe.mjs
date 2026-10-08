/**
 * Sends VestingCheck's exact prompt for a source to the model twice (via the
 * throwaway probe contract) and saves the raw answers; then runs code's
 * keep rules on them locally (tools/live.py gather ... <answers>).
 *   node prompt_probe.mjs --address=<probe> --source=... --chain=... --contract=... --extra=... [--branch=] --out=<file>
 */
import { writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { connect, argOf } from "./harness.mjs";
const address = argOf("address");
const args = [argOf("source"), argOf("chain"), argOf("contract"), argOf("extra"), argOf("branch", "")];
const prompt = execFileSync("python3", [new URL("../tools/prompt_of.py", import.meta.url).pathname, ...args]).toString();
const { send, view } = connect({ address, role: "probe" });
const out = await send("probe_prompt", [prompt]);
console.log(out.status, out.ok, out.seconds);
const last = JSON.parse(await view("get_last"));
writeFileSync(argOf("out"), JSON.stringify(last, null, 1));
for (const a of last) console.log(a);

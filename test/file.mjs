/**
 * One filing (or recheck) against a deployment, printed and returned as JSON.
 *   node file.mjs --target=VestingCheck|VestingCheckDemo|<address> --source=... --chain=... --contract=... --extra=... [--branch=] [--role=filer]
 *   node file.mjs --target=... --recheck=<record id>
 */
import { readFileSync } from "node:fs";
import { connect, argOf, returnedJson } from "./harness.mjs";

const t = argOf("target", "VestingCheck");
const dep = t.startsWith("0x") ? null : JSON.parse(readFileSync(new URL("../deployments.json", import.meta.url), "utf8"));
const address = t.startsWith("0x") ? t : dep.contracts[t].address;
const { send, view } = connect({ address, role: argOf("role", "filer") });
const out = argOf("recheck")
  ? await send("recheck", [Number(argOf("recheck"))])
  : await send("file_check", [argOf("source"), argOf("branch", ""), argOf("chain"), argOf("contract"), argOf("extra", "")]);
const ret = returnedJson(out);
console.log(JSON.stringify({ status: out.status, ok: out.ok, seconds: out.seconds, hash: out.hash,
  revert: out.ok ? "" : String(out.revertReason ?? out.failure ?? ""), returned: ret, stderr: out.stderr.slice(-1500) }, null, 1));

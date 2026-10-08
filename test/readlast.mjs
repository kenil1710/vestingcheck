/** Reads get_last from a deployed probe and stores it under docs/research/probe_<tag>.json. */
import { writeFileSync } from "node:fs";
import { connect, argOf } from "./harness.mjs";
const address = argOf("address");
const { view } = connect({ address, role: "probe" });
const last = await view("get_last");
const result = (() => { try { return JSON.parse(last); } catch { return last; } })();
writeFileSync(new URL(`../docs/research/probe_${argOf("tag", "1")}.json`, import.meta.url), JSON.stringify({ address, tx: argOf("tx"), result }, null, 2) + "\n");
console.log(JSON.stringify(result, null, 1).slice(0, 12000));

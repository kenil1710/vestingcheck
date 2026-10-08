/** Throwaway deploy of the WORKING TREE contract with the probe key (smoke test only, never listed). */
import { readFileSync } from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { CHAINS, accounts, fundOnStudio, deploy } from "./harness.mjs";
const chain = CHAINS.studiodev;
const account = createAccount(accounts().probe.key);
const wallet = createClient({ chain, account });
const read = createClient({ chain });
await fundOnStudio(chain, account.address, 1000n * 10n ** 18n);
const code = readFileSync(new URL("../contracts/VestingCheck.py", import.meta.url), "utf8");
const res = await deploy({ chain, wallet, read, code, args: ["DEMO", 60, 3600], label: "smoke" });
console.log(res.ok, res.address, res.hash, res.reason ?? "", res.out?.revertReason ?? "", res.out?.stderr?.slice(-2000) ?? "");

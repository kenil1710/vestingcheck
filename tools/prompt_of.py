"""Print the exact prompt VestingCheck sends for a source, subject and nonce
(for probing the model on studio-dev with test/prompt_probe.mjs).
  python3 tools/prompt_of.py <source> <chain> <contract> <stream_or_token> [branch]
"""
import sys
import time
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import live

C = live.load()
source, chain, contract, extra = sys.argv[1:5]
p = live.params(C, source, chain, contract, extra, sys.argv[5] if len(sys.argv) > 5 else "")
tg = p["tg"]
label = ("Sablier Lockup " + tg["release"] + " stream #" + str(tg["stream_id"]) + " at " + tg["contract"]
         if tg["kind"] == C["K_SAB"] else "the vesting wallet " + tg["contract"] + " (token " + tg["token"] + ")")
src = p["src"]
s = C["fetch_github"](src["pin"], p["branch"]) if src["kind"] == "github" else C["fetch_snapshot"](src["cid"])
sys.stdout.write(C["model_prompt"](s["text"], label + " on " + chain, "probe0nonce00000"))

"""Run VestingCheck's own pure + fetch code locally against the REAL network
(GitHub, IPFS gateways, the Snapshot hub, the five RPCs), with a tiny stand-in
for gl.nondet.web. No model: fields are not extracted here unless a JSON file
of model fields is given. Used for research and to verify seeds by hand.

  python3 tools/live.py gather <source> <chain> <contract> <stream_or_token> [branch] [fields.json]
  python3 tools/live.py read <chain> <contract> <stream_or_token> [block|finalized]
"""
import json
import sys
import time
import types
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class _Res:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body
        self.headers = {}


def _request(url, method="GET", body=None, headers=None, **_k):
    req = urllib.request.Request(url, data=body.encode() if isinstance(body, str) else body,
                                 method=method, headers={"User-Agent": "vestingcheck-live", **(headers or {})})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return _Res(r.status, r.read())
        except urllib.error.HTTPError as e:
            return _Res(e.code, e.read())
        except Exception:
            if i == 2:
                raise
            time.sleep(3)


def load():
    mod = types.ModuleType("genlayer")
    web = types.SimpleNamespace(get=lambda url, **k: _request(url), request=_request)
    nondet = types.SimpleNamespace(web=web, exec_prompt=None)
    storage = types.SimpleNamespace(TreeMap=dict, DynArray=list, allow=lambda c: c)
    mod.gl = types.SimpleNamespace(nondet=nondet, storage=storage,
                                   contract=types.SimpleNamespace(Contract=object),
                                   public=types.SimpleNamespace(view=lambda f: f, write=lambda f: f),
                                   vm=types.SimpleNamespace(UserError=Exception, Result=object, Return=object),
                                   message=None)
    mod.Address = str
    for n in ("u8", "u16", "u32", "u64", "u128", "u256", "i64", "bigint"):
        setattr(mod, n, int)
    sys.modules["genlayer"] = mod
    ns = {}
    src = (ROOT / "contracts" / "VestingCheck.py").read_text()
    exec(compile(src, "VestingCheck.py", "exec"), ns)
    return ns


def params(C, source, chain, contract, extra, branch=""):
    src = C["parse_source"](source)
    assert "error" not in src, src
    tg = C["parse_target"](chain, contract, extra)
    assert "error" not in tg, tg
    return {"src": src, "branch": C["clean_branch"](branch) if src["kind"] == "github" else "HEAD",
            "chain": chain, "tg": tg, "key": C["record_key"](chain, tg, src), "subject_label": contract}


if __name__ == "__main__":
    C = load()
    cmd = sys.argv[1]
    if cmd == "read":
        chain, contract, extra = sys.argv[2], sys.argv[3], sys.argv[4]
        tag = sys.argv[5] if len(sys.argv) > 5 else "finalized"
        blk = C["read_block"](chain, tag if not tag.isdigit() else hex(int(tag)))
        print("block", blk)
        tg = C["parse_target"](chain, contract, extra)
        rd = C["Reader"](C["rpc_transport"](chain), hex(blk["number"]))
        print(json.dumps(C["read_subject"](rd, tg, blk["timestamp"]), indent=1))
    elif cmd == "gather":
        source, chain, contract, extra = sys.argv[2:6]
        branch = sys.argv[6] if len(sys.argv) > 6 else ""
        p = params(C, source, chain, contract, extra, branch)
        ev = C["gather"](p, int(time.time()), 3600, -1)
        if "refused" in ev:
            print(json.dumps(ev, indent=1)); sys.exit(0)
        text, refs, my = ev.pop("_text"), ev.pop("_refs"), ev.pop("_my")
        print(json.dumps({k: v for k, v in ev.items() if k != "reads"}, indent=1))
        print("anchors", refs["anchors"][:10], "others", refs["others"][:10], "month/year", my)
        if len(sys.argv) > 7:
            model = json.loads(Path(sys.argv[7]).read_text())
            kf = C["keep_fields"](model, text, refs, my)
            for it in model.get("fields", []):
                print("  item", it.get("field"), "->", C["keep_field"](it, text, refs, my))
            out = C["decide"](kf["kept"], ev["facts"], ev["binding"]["token_in_source"], ev["block"])
            word = "docs" if ev["source"]["meta"]["kind"] == "github" else "proposal"
            print(json.dumps({k: out[k] for k in ("verdict", "basis", "fields", "why", "decided", "unlock")}, indent=1))
            print(C["summary_text"](out, ev["facts"], word, ev["source"]["date"], ev["block"]))

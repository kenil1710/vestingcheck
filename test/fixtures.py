"""Builders for the offline suite: ABI words, Sablier streams and OpenZeppelin
VestingWallets on a MockChain, GitHub docs + compare answers, Snapshot
proposals pinned on a mock IPFS gateway + hub rows, and a loaded contract."""
import copy
import hashlib
import json
from pathlib import Path

import stub

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "VestingCheck.py"

stub._install_stub()
C = stub.load_full(CONTRACT, "vestingcheck")

NOW_ISO = "2026-10-07T12:00:00Z"
NOW = C._epoch_from_iso(NOW_ISO)
FIN = 20_000_000                 # finalized block on every mock chain
FIN_TS = NOW - 900               # 15 minutes before the filing
DAY = 86400
MONTH = 30 * DAY
YEAR = 365 * DAY

OWNER, REPO = "acme", "token-docs"
SHA = "a" * 40
PATH = "docs/vesting.md"
RAW = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (OWNER, REPO, SHA, PATH)
BLOB = "https://github.com/%s/%s/blob/%s/%s" % (OWNER, REPO, SHA, PATH)
COMMIT_DATE = "2025-06-01T10:00:00Z"
COMMIT_TS = C._epoch_from_iso(COMMIT_DATE)


def addr(n):
    return "0x" + ("%040x" % n)


LOCKUP = "0xafb979d9afad1ad27c5eff4e27226e3ab9e5dcc9"     # Sablier Lockup Linear v1.1, Ethereum (LL2)
LOCKUP_D = "0x7cc7e125d83a581ff438608490cc0f7bdff79127"   # Lockup Dynamic v1.1 (LD2)
LOCKUP_T = "0xf86b359035208e4529686a1825f2d5bee38c28a8"   # Lockup Tranched v1.2 (LT3)
LOCKUP_K = "0x7c01aa3783577e15fd7e272443d44b92d5b21056"   # SablierLockup v2.0 (LK)
SID = 42
TOK = addr(0x7001)
TOK2 = addr(0x7002)
RECIP = addr(0x2001)
SENDER = addr(0x2002)
OTHER = addr(0x2003)
WALLET = addr(0x5001)
WALLET2 = addr(0x5002)

START = C._days_from_civil(2025, 1, 1) * DAY              # 2025-01-01
TOTAL = 500_000 * 10 ** 18


def word(n):
    return "0x" + ("%064x" % n)


def aword(a):
    return "0x" + "0" * 24 + a[2:].lower()


def abi_string(s):
    b = s.encode()
    return "0x" + ("%064x" % 32) + ("%064x" % len(b)) + b.hex().ljust(((len(b) + 31) // 32) * 64, "0")


def sid_word(sid):
    return "%064x" % sid


def call(sel, *words):
    return C.call_data(sel, *words)


SEL = C.SEL


def block_ts(mc, blk):
    return mc.blocks.get(blk, (None, FIN_TS))[1]


def linear_v1(dep, start, cliff, end, t):
    if t < cliff or t < start:
        return 0
    if t >= end:
        return dep
    return dep * (t - start) // (end - start)


def token(mc, tok, symbol="VEST", decimals=18, balances=None, bytes32=False):
    mc.code[tok] = "0x6080604052fe"
    if bytes32:
        mc.calls[(tok, SEL["symbol"])] = "0x" + symbol.encode().hex().ljust(64, "0")
    else:
        mc.calls[(tok, SEL["symbol"])] = abi_string(symbol)
    mc.calls[(tok, SEL["decimals"])] = word(decimals)
    for h, v in (balances or {}).items():
        mc.calls[(tok, call(SEL["balanceOf"], h[2:]))] = word(v)


def sablier_stream(mc, lockup=LOCKUP, sid=SID, family="L", recipient=RECIP, sender=SENDER, tok=TOK,
                   start=START, end=START + 3 * YEAR, cliff=None, deposited=TOTAL, withdrawn=0, refunded=0,
                   canceled=False, cancelable=False, model=0, unlock=(0, 0), tranches=None, symbol="VEST",
                   decimals=18, streamed=None, burned=False):
    """A stream as the Sablier Lockup contract answers for it."""
    mc.code[lockup] = "0x6080604052" + "f4" * 0 + "fe"
    s = sid_word(sid)
    c = mc.calls
    c[(lockup, SEL["isStream"] + s)] = word(1)
    c[(lockup, SEL["getRecipient"] + s)] = stub.MockChain.REVERT if burned else aword(recipient)
    c[(lockup, SEL["getSender"] + s)] = aword(sender)
    c[(lockup, SEL["getStartTime"] + s)] = word(start)
    c[(lockup, SEL["getEndTime"] + s)] = word(end)
    c[(lockup, SEL["getDepositedAmount"] + s)] = word(deposited)
    c[(lockup, SEL["getWithdrawnAmount"] + s)] = word(withdrawn)
    c[(lockup, SEL["getRefundedAmount"] + s)] = word(refunded)
    c[(lockup, SEL["wasCanceled"] + s)] = word(1 if canceled else 0)
    c[(lockup, SEL["isCancelable"] + s)] = word(1 if cancelable else 0)
    if family == "K":
        c[(lockup, SEL["getUnderlyingToken"] + s)] = aword(tok)
        c[(lockup, SEL["getLockupModel"] + s)] = word(model)
        c[(lockup, SEL["getUnlockAmounts"] + s)] = word(unlock[0]) + ("%064x" % unlock[1])
    else:
        c[(lockup, SEL["getAsset"] + s)] = aword(tok)
    ct = cliff if cliff is not None else start
    if family in ("L", "K"):
        c[(lockup, SEL["getCliffTime"] + s)] = word(0 if (family == "K" and cliff is None) else ct)
    if tranches is not None:
        body = ("%064x" % 32) + ("%064x" % len(tranches))
        for (amt, ts) in tranches:
            body += ("%064x" % amt) + ("%064x" % ts)
        c[(lockup, SEL["getTranches"] + s)] = "0x" + body

    def streamed_fn(data, blk, _ct=ct):
        if streamed is not None:
            return word(streamed)
        t = block_ts(mc, blk)
        if tranches is not None:
            return word(sum(a for (a, ts) in tranches if ts <= t))
        return word(linear_v1(deposited, start, _ct, end, t))
    mc.fns[(lockup, SEL["streamedAmountOf"])] = lambda data, blk, _sid=s, _f=streamed_fn: \
        _f(data, blk) if data.endswith(_sid) else stub.MockChain.REVERT
    token(mc, tok, symbol, decimals)


VW_V5 = ("8da5cb5b", "715018a6", "f2fde38b", "be9a6555", "0fb5a6b4", "efbe1c1c", "96132521", "9852595c",
         "fbccedae", "a3f8eace", "86d1a69f", "19165587", "0a17b06b", "810ec23b")
VW_V4 = ("38af3eed", "be9a6555", "0fb5a6b4", "96132521", "9852595c", "a3f8eace", "86d1a69f", "19165587",
         "0a17b06b", "810ec23b")


def vw_code(selectors, extra=""):
    """A runtime whose dispatcher compares the calldata selector with each of
    `selectors` (PUSH4 sel EQ PUSH2 dest JUMPI)."""
    body = "6080604052600436106100" + "".join("8063" + s + "14610100" + "57" for s in selectors)
    return "0x" + body + extra + "fe"


def vesting_wallet(mc, wallet=WALLET, tok=TOK, beneficiary=RECIP, start=START, duration=3 * YEAR, cliff=None,
                   balance=TOTAL, released=0, version=5, extra_selectors=(), code=None, curve=None,
                   symbol="VEST", decimals=18, others=None):
    """`others`: {token: (balance, released, symbol)} more tokens in the same wallet."""
    sels = list(VW_V5 if version == 5 else VW_V4)
    if cliff is not None:
        sels.append("13d033c0")
    sels += list(extra_selectors)
    mc.code[wallet] = code if code is not None else vw_code(sels)
    c = mc.calls
    c[(wallet, SEL["start"])] = word(start)
    c[(wallet, SEL["duration"])] = word(duration)
    if cliff is not None:
        c[(wallet, SEL["cliff"])] = word(cliff)
    if version == 5:
        c[(wallet, SEL["owner"])] = aword(beneficiary)
    else:
        c[(wallet, SEL["beneficiary"])] = aword(beneficiary)
    c[(wallet, call(SEL["released"], tok[2:]))] = word(released)
    total = balance + released
    cl = cliff if cliff is not None else 0

    def vested(t):
        if curve is not None:
            return curve(total, t)
        return C.oz_vested(total, start, duration, cl, t)

    books = {tok: (balance, released)}
    for t2, (b2, r2, s2) in (others or {}).items():
        books[t2] = (b2, r2)
        c[(wallet, call(SEL["released"], t2[2:]))] = word(r2)
        token(mc, t2, s2, 18, {wallet: b2})

    def book(data):
        for t2, (b2, r2) in books.items():
            if data[10:74] == "0" * 24 + t2[2:]:
                return b2 + r2, r2
        return 0, 0

    def vested_at(tot, t):
        if curve is not None:
            return curve(tot, t)
        return C.oz_vested(tot, start, duration, cl, t)

    def vested_fn(data, blk):
        tot, _r = book(data)
        return word(vested_at(tot, int(data[74:138], 16)))

    def releasable_fn(data, blk):
        tot, r = book(data)
        return word(vested_at(tot, block_ts(mc, blk)) - r)
    mc.fns[(wallet, SEL["vestedAmount"])] = vested_fn
    mc.fns[(wallet, SEL["releasable"])] = releasable_fn
    token(mc, tok, symbol, decimals, {wallet: balance})


# --- GitHub --------------------------------------------------------------------

def compare_page(sha=SHA, status="behind", date=COMMIT_DATE, merge_base=None):
    return json.dumps({"status": status, "ahead_by": 0 if status != "diverged" else 2, "behind_by": 12,
                       "base_commit": {"sha": "f" * 40},
                       "merge_base_commit": {"sha": merge_base or sha, "commit": {"committer": {"date": date}}},
                       "commits": [], "files": []})


def compare_url(branch="HEAD", sha=SHA, owner=OWNER, repo=REPO):
    return C.GITHUB_API + owner + "/" + repo + "/compare/" + branch + "..." + sha


SAB_LINK = "https://app.sablier.com/vesting/stream/LL2-1-%d" % SID

DOCS = """# Acme token

Some intro text about Acme.

## Team allocation

Team tokens are streamed with Sablier ([stream](%s)).
The team receives 500,000 VEST.
There is a 12-month cliff, then linear vesting over 36 months.
Vesting starts on January 1, 2025.
The stream is non-cancelable.

## Investors

Investor tokens: 250,000 VEST with a 6-month cliff, streamed over 24 months
([stream](https://app.sablier.com/stream/LL2-1-43)).
""" % SAB_LINK

DOCS_VW = """# Acme token

## Team allocation

The team allocation sits in the vesting wallet %s.
The team receives 500,000 VEST, vesting linearly over 3 years.
Vesting starts on 2025-01-01. Beneficiary: %s.

## Treasury

The treasury vesting contract %s holds 1,000,000 VEST over 4 years.
""" % (WALLET, RECIP, WALLET2)


def fields(*items):
    return {"fields": [{"field": f, "value": v, "quote": q} for (f, v, q) in items]}


GOOD = fields(
    ("total_amount", "500,000", "The team receives 500,000 VEST."),
    ("token_symbol", "VEST", "The team receives 500,000 VEST."),
    ("cliff_duration", "12 months", "There is a 12-month cliff"),
    ("vesting_duration", "36 months", "then linear vesting over 36 months"),
    ("start_date", "2025-01-01", "Vesting starts on January 1, 2025."),
    ("irrevocable", True, "The stream is non-cancelable."),
)

GOOD_VW = fields(
    ("total_amount", "500,000", "The team receives 500,000 VEST, vesting linearly over 3 years."),
    ("token_symbol", "VEST", "The team receives 500,000 VEST"),
    ("vesting_duration", "3 years", "vesting linearly over 3 years"),
    ("start_date", "2025-01-01", "Vesting starts on 2025-01-01."),
    ("beneficiary", RECIP, "Beneficiary: " + RECIP),
)


# --- Snapshot -----------------------------------------------------------------

SPACE = "acmedao.eth"
AUTHOR = addr(0xA0A0)
PROP_TS = C._days_from_civil(2024, 12, 10) * DAY


def proposal_bytes(title="AIP-7: Team vesting", body=None, space=SPACE, author=AUTHOR, ts=PROP_TS):
    body = body if body is not None else DOCS.split("## Investors")[0]
    doc = {"address": author[:2] + author[2:].upper(), "sig": "0x" + "ab" * 65, "hash": "0x" + "cd" * 32,
           "data": {"domain": {"name": "snapshot", "version": "0.1.4"},
                    "types": {"Proposal": [{"name": "from", "type": "address"}]},
                    "message": {"from": author, "space": space, "timestamp": ts, "type": "single-choice",
                                "title": title, "body": body, "discussion": "", "choices": ["For", "Against"],
                                "start": ts, "end": ts + 5 * DAY, "snapshot": 1, "plugins": "{}",
                                "app": "snapshot"}}}
    return json.dumps(doc).encode()


def raw_cid(b):
    d = hashlib.sha256(b).digest()
    return "b" + C.b32_encode(bytes([1, 0x55, 0x12, 0x20]) + d)


def cidv0(b):
    d = hashlib.sha256(C.unixfs_node(b)).digest()
    return C.b58_encode(bytes([0x12, 0x20]) + d)


def hub_page(cid, space=SPACE, author=AUTHOR, created=PROP_TS, pid="0x" + "e1" * 32):
    return json.dumps({"data": {"proposals": [{"id": pid, "ipfs": cid, "author": author[:2] + author[2:].upper(),
                                                "created": created, "space": {"id": space}}]}})


def pin_proposal(b, cid=None, gateway=0, hub=True, **hub_kw):
    cid = cid or raw_cid(b)
    stub.WEB.pages[C.IPFS_GATEWAYS[gateway] + cid] = (200, b)
    if hub:
        stub.WEB.pages[C.hub_url(cid)] = (200, hub_page(cid, **hub_kw))
    return cid


# --- world --------------------------------------------------------------------

def fresh_world(docs=DOCS, chain="ethereum"):
    """Reset web, model and message; install docs + compare answer and a mock
    chain per supported chain. Returns the MockChain for `chain`."""
    stub.WEB.reset()
    stub.MODEL.reset()
    stub.FORGE["payload"] = None
    stub.FORGE["mutate"] = None
    stub.MESSAGE.raw = {"datetime": NOW_ISO}
    stub.MESSAGE.sender_address = stub._Addr("0x" + "a" * 40)
    stub.WEB.pages[RAW] = (200, docs)
    stub.WEB.pages[compare_url()] = (200, compare_page())
    mcs = {}
    for name, (cid, url) in C.CHAINS.items():
        mc = stub.MockChain(cid, FIN, FIN_TS)
        stub.WEB.chains[url] = mc
        mcs[name] = mc
    return mcs[chain]


def new_contract(mode="CANONICAL", cooldown=21600, fresh=3600):
    c = C.VestingCheck(mode, cooldown, fresh)
    for name in C.VestingCheck.__annotations__:
        getattr(c, name)
    return c


def snapshot(c):
    return copy.deepcopy(c.__dict__)


class Outcome:
    def __init__(self, ok, value=None, error=None, rolled=False):
        self.ok, self.value, self.error, self.rolled = ok, value, error, rolled

    def __repr__(self):
        return "Outcome(ok=%s, value=%r, error=%r, rolled=%s)" % (self.ok, self.value, self.error, self.rolled)


def tx(c, method, *args, at=None):
    """Run a write like a transaction: on a revert or an unsettled round the
    state must be exactly what it was before (asserted), then restored."""
    if at is not None:
        stub.MESSAGE.raw = {"datetime": at}
    before = snapshot(c)
    try:
        v = getattr(c, method)(*args)
        return Outcome(True, v)
    except stub._UserError as e:
        assert snapshot(c) == before, "state changed before a revert in " + method
        c.__dict__.clear()
        c.__dict__.update(before)
        return Outcome(False, error=e.message)
    except stub._Rolled as e:
        assert snapshot(c) == before, "state changed before an unsettled round in " + method
        c.__dict__.clear()
        c.__dict__.update(before)
        return Outcome(False, error=str(e), rolled=True)


def iso(epoch):
    y, m, d = C._civil_from_days(epoch // 86400)
    s = epoch % 86400
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, s // 3600, (s % 3600) // 60, s % 60)


def file(c, source=RAW, branch="", chain="ethereum", contract=LOCKUP, extra=str(SID), at=None):
    return tx(c, "file_check", source, branch, chain, contract, extra, at=at)


def standard_stream(mc, **kw):
    """Matches DOCS: 500,000 VEST, start 2025-01-01, 12-month cliff, 36 months
    from the start, non-cancelable."""
    args = dict(start=START, cliff=C.add_months(START, 12), end=C.add_months(START, 36), deposited=TOTAL)
    args.update(kw)
    sablier_stream(mc, **args)

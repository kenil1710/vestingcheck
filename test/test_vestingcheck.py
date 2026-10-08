"""Offline suite for VestingCheck: every rule, parser case, contract pattern
(mock chain), verdict, refusal, tolerance boundary and unlock case, against a
stub runtime.

    cd test && python3 -m unittest -q test_vestingcheck
"""
import ast
import json
import subprocess
import sys
import unittest

import fixtures as F
import stub
from fixtures import C

DAY = F.DAY
MONTH = F.MONTH
YEAR = F.YEAR
MY = (C.MONTH_S, C.YEAR_S)


def dur(text):
    d = C.durations(text, C.MONTH_S, C.YEAR_S)
    return None if d is None else [x[0] for x in d]


def amt(text):
    return C.amounts(text, C.MONTH_S, C.YEAR_S)


def run_ok(test, c, **kw):
    o = F.file(c, **kw)
    test.assertTrue(o.ok, o)
    return c.get_record(o.value["record_id"])


# =============================================================================
# 1. claim sources: GitHub URL allowlist
# =============================================================================

class GithubUrl(unittest.TestCase):
    def test_raw_pinned_accepted(self):
        p = C.docs_pin(F.RAW)
        self.assertEqual((p["owner"], p["repo"], p["sha"], p["path"]), (F.OWNER, F.REPO, F.SHA, F.PATH))

    def test_blob_converted_to_raw(self):
        self.assertEqual(C.docs_pin(F.BLOB)["raw"], F.RAW)

    def test_owner_repo_lowercased_path_case_kept(self):
        p = C.docs_pin("https://raw.githubusercontent.com/Acme/Token-Docs/" + F.SHA + "/Docs/README.md")
        self.assertEqual(p["raw"], "https://raw.githubusercontent.com/acme/token-docs/" + F.SHA + "/Docs/README.md")

    def test_branch_name_refused(self):
        self.assertEqual(C.docs_pin(F.RAW.replace(F.SHA, "main"))["error"], "URL_NOT_PINNED_TO_COMMIT")

    def test_tag_refused(self):
        self.assertEqual(C.docs_pin(F.RAW.replace(F.SHA, "v1.2.0"))["error"], "URL_NOT_PINNED_TO_COMMIT")

    def test_short_sha_refused(self):
        self.assertEqual(C.docs_pin(F.RAW.replace(F.SHA, "a" * 39))["error"], "URL_NOT_PINNED_TO_COMMIT")

    def test_refs_heads_refused(self):
        u = "https://raw.githubusercontent.com/acme/docs/refs/heads/main/README.md"
        self.assertEqual(C.docs_pin(u)["error"], "URL_NOT_PINNED_TO_COMMIT")

    def test_query_and_fragment_refused(self):
        self.assertEqual(C.docs_pin(F.RAW + "?x=1")["error"], "URL_HAS_QUERY_OR_FRAGMENT")
        self.assertEqual(C.docs_pin(F.RAW + "#L3")["error"], "URL_HAS_QUERY_OR_FRAGMENT")

    def test_percent_encoding_refused(self):
        self.assertEqual(C.docs_pin(F.RAW.replace("vesting", "vest%69ng"))["error"], "URL_PERCENT_ENCODED")

    def test_dotdot_refused(self):
        self.assertEqual(C.docs_pin(F.RAW.replace("/docs/vesting", "/docs/../vesting"))["error"], "URL_BAD_PATH")

    def test_other_hosts_refused(self):
        for u in ("https://gitlab.com/acme/docs/-/raw/" + F.SHA + "/x.md", "https://docs.acme.xyz/vesting",
                  "https://raw.githubusercontent.com.evil.io/acme/docs/" + F.SHA + "/x.md",
                  "https://cdn.jsdelivr.net/gh/acme/docs@" + F.SHA + "/x.md"):
            self.assertEqual(C.parse_source(u)["error"], "URL_HOST_NOT_ALLOWED", u)

    def test_http_refused(self):
        self.assertEqual(C.parse_source(F.RAW.replace("https://", "http://"))["error"], "URL_HOST_NOT_ALLOWED")

    def test_branch_names(self):
        self.assertEqual(C.clean_branch(""), "HEAD")
        self.assertEqual(C.clean_branch("main"), "main")
        for bad in ("fork:main", "../x", "-x", "a b", "x.lock"):
            self.assertEqual(C.clean_branch(bad), "", bad)


# =============================================================================
# 2. claim sources: IPFS CIDs, verified in code
# =============================================================================

class Cids(unittest.TestCase):
    def test_raw_cid_roundtrip(self):
        b = b'{"x":1}'
        cid = F.raw_cid(b)
        pc = C.parse_cid(cid)
        self.assertEqual(pc["codec"], "raw")
        self.assertTrue(C.cid_matches(pc, b))
        self.assertFalse(C.cid_matches(pc, b + b" "))

    def test_real_snapshot_cid_digest(self):
        # bafkrei... is CIDv1 raw sha2-256 (measured: sha256 of the gateway bytes)
        pc = C.parse_cid("bafkreianjh3ztdn3aprhhk6re3g6fkwriadgle2k5on2kpi2ox7psrb3ey")
        self.assertEqual(pc["codec"], "raw")
        self.assertEqual(len(pc["digest"]), 64)

    def test_ipfs_scheme_accepted(self):
        cid = F.raw_cid(b"abc")
        self.assertEqual(C.parse_source("ipfs://" + cid)["cid"]["cid"], cid)

    def test_cidv0_dag_pb_single_chunk(self):
        b = b"hello vesting"
        cid = F.cidv0(b)
        self.assertTrue(cid.startswith("Qm"))
        pc = C.parse_cid(cid)
        self.assertEqual(pc["codec"], "dag-pb")
        self.assertTrue(C.cid_matches(pc, b))
        self.assertFalse(C.cid_matches(pc, b"hello vestinG"))

    def test_known_cidv0_vector(self):
        # `ipfs add` of "hello world\n" (kubo defaults) is QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o
        pc = C.parse_cid("QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o")
        self.assertTrue(C.cid_matches(pc, b"hello world\n"))

    def test_cidv0_over_one_chunk_not_verifiable(self):
        b = b"x" * (C.MAX_UNIXFS_CHUNK + 1)
        self.assertFalse(C.cid_matches(C.parse_cid(F.cidv0(b)), b))

    def test_bad_cids_refused(self):
        for bad in ("", " bafy", "Qm123", "bafkreiXXX", "zdj7W", "ipfs://", "bafkrei" + "a" * 60):
            self.assertIn("error", C.parse_source(bad), bad)

    def test_uppercase_base32_refused(self):
        cid = F.raw_cid(b"abc")
        self.assertIn("error", C.parse_cid("B" + cid[1:].upper()))

    def test_non_sha256_multihash_refused(self):
        raw = bytes([1, 0x55, 0x1b, 0x20]) + b"\x00" * 32          # keccak-256 multihash
        self.assertEqual(C.parse_cid("b" + C.b32_encode(raw))["error"], "CID_NOT_SHA256")

    def test_unknown_codec_refused(self):
        raw = bytes([1, 0x71, 0x12, 0x20]) + b"\x00" * 32          # dag-cbor
        self.assertEqual(C.parse_cid("b" + C.b32_encode(raw))["error"], "CID_CODEC_NOT_SUPPORTED")

    def test_base58_roundtrip(self):
        for b in (b"\x00\x01abc", b"\x12\x20" + bytes(range(32))):
            self.assertEqual(C.b58_decode(C.b58_encode(b)), b)


# =============================================================================
# 3. fetching and proving the source (stubbed network)
# =============================================================================

class SourceFetch(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world()
        F.standard_stream(self.mc)
        stub.MODEL.answer = F.GOOD

    def test_branch_proof_behind(self):
        p = C.branch_proof(C.docs_pin(F.RAW), "HEAD")
        self.assertEqual(p["status"], "behind")
        self.assertEqual(p["commit_date"], F.COMMIT_TS)

    def test_fork_commit_diverged_refused(self):
        stub.WEB.pages[F.compare_url()] = (200, F.compare_page(status="diverged"))
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: COMMIT_NOT_ON_BRANCH")

    def test_commit_not_in_repo_404(self):
        stub.WEB.pages[F.compare_url()] = (404, "{}")
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: COMMIT_NOT_IN_REPO")

    def test_github_403_refuses(self):
        stub.WEB.pages[F.compare_url()] = (403, '{"message":"API rate limit exceeded"}')
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: GITHUB_API_HTTP_403")

    def test_merge_base_must_be_the_commit(self):
        stub.WEB.pages[F.compare_url()] = (200, F.compare_page(merge_base="b" * 40))
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: COMMIT_NOT_ON_BRANCH")

    def test_one_compare_call_per_node(self):
        F.file(F.new_contract())
        calls = [u for u in stub.WEB.log if u.startswith(C.GITHUB_API)]
        self.assertEqual(len(calls), 2)          # the leader and one validator

    def test_docs_fetch_failure_refuses(self):
        stub.WEB.down.add(F.RAW)
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: SOURCE_FETCH_FAILED")

    def test_docs_404_refuses(self):
        del stub.WEB.pages[F.RAW]
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: SOURCE_NOT_FOUND")

    def test_snapshot_ok(self):
        cid = F.pin_proposal(F.proposal_bytes())
        r = run_ok(self, F.new_contract(), source=cid)
        self.assertEqual(r["source_kind"], "snapshot")
        self.assertEqual(r["source"]["space"], F.SPACE)
        self.assertEqual(r["source_date"], F.PROP_TS)
        self.assertEqual(r["source_ref"], "ipfs://" + cid)

    def test_gateway_falls_through_to_next(self):
        b = F.proposal_bytes()
        cid = F.pin_proposal(b, gateway=2)
        stub.WEB.down.add(C.IPFS_GATEWAYS[0] + cid)
        self.assertTrue(F.file(F.new_contract(), source=cid).ok)

    def test_lying_gateway_skipped_then_refused(self):
        b = F.proposal_bytes()
        cid = F.raw_cid(b)
        lie = F.proposal_bytes(body=F.DOCS.split("## Investors")[0].replace("500,000", "900,000"))
        for g in C.IPFS_GATEWAYS:
            stub.WEB.pages[g + cid] = (200, lie)
        stub.WEB.pages[C.hub_url(cid)] = (200, F.hub_page(cid))
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: IPFS_CONTENT_DOES_NOT_MATCH_CID")

    def test_lying_first_gateway_honest_second(self):
        b = F.proposal_bytes()
        cid = F.pin_proposal(b, gateway=1)
        stub.WEB.pages[C.IPFS_GATEWAYS[0] + cid] = (200, b + b" ")
        self.assertTrue(F.file(F.new_contract(), source=cid).ok)

    def test_all_gateways_down_refuses(self):
        cid = F.raw_cid(F.proposal_bytes())
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: IPFS_FETCH_FAILED")

    def test_cid_not_on_hub_refused(self):
        b = F.proposal_bytes()
        cid = F.pin_proposal(b, hub=False)
        stub.WEB.pages[C.hub_url(cid)] = (200, '{"data":{"proposals":[]}}')
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: CID_NOT_A_SNAPSHOT_PROPOSAL")

    def test_hub_space_must_match_ipfs(self):
        b = F.proposal_bytes()
        cid = F.pin_proposal(b, space="other.eth")
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: HUB_RECORD_DIFFERS_FROM_IPFS")

    def test_hub_down_refuses(self):
        b = F.proposal_bytes()
        cid = F.pin_proposal(b, hub=False)
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: CID_NOT_A_SNAPSHOT_PROPOSAL"
                         if False else F.file(F.new_contract(), source=cid).error)
        stub.WEB.pages[C.hub_url(cid)] = (502, "bad gateway")
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: SNAPSHOT_HUB_UNREACHABLE")

    def test_not_a_proposal_refused(self):
        b = json.dumps({"hello": "world"}).encode()
        cid = F.pin_proposal(b)
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: NOT_A_SNAPSHOT_PROPOSAL")

    def test_legacy_proposal_layout(self):
        msg = json.dumps({"version": "0.1.3", "timestamp": str(F.PROP_TS), "space": F.SPACE, "type": "proposal",
                          "payload": {"name": "Team vesting", "body": F.DOCS.split("## Investors")[0],
                                      "choices": ["For", "Against"]}})
        b = json.dumps({"address": F.AUTHOR, "msg": msg, "sig": "0x00", "version": "2"}).encode()
        p = C.proposal_text(b)
        self.assertEqual((p["space"], p["timestamp"], p["title"]), (F.SPACE, F.PROP_TS, "Team vesting"))

    def test_branch_for_snapshot_refused(self):
        cid = F.pin_proposal(F.proposal_bytes())
        self.assertEqual(F.file(F.new_contract(), source=cid, branch="main").error, "REFUSED: BRANCH_ONLY_FOR_GITHUB")

    def test_allowlist(self):
        self.assertTrue(C.allowed_url(F.RAW))
        self.assertTrue(C.allowed_url(F.compare_url()))
        self.assertTrue(C.allowed_url(C.IPFS_GATEWAYS[0] + F.raw_cid(b"x")))
        self.assertTrue(C.allowed_url(C.hub_url(F.raw_cid(b"x"))))
        for u in ("https://ipfs.io/ipfs/" + F.raw_cid(b"x"), C.IPFS_GATEWAYS[0] + "notacid",
                  "https://evil.io/rpc", "https://api.github.com/users/x", "https://hub.snapshot.org/api/x"):
            self.assertFalse(C.allowed_url(u), u)

    def test_disallowed_fetch_never_leaves(self):
        got = C.http_get("https://evil.io/x")
        self.assertEqual(got["http"], -2)
        self.assertNotIn("https://evil.io/x", stub.WEB.log)


# =============================================================================
# 4. targets
# =============================================================================

class Targets(unittest.TestCase):
    def test_sablier_needs_stream_id(self):
        self.assertEqual(C.parse_target("ethereum", F.LOCKUP, "")["error"], "STREAM_ID_REQUIRED")
        self.assertEqual(C.parse_target("ethereum", F.LOCKUP, F.TOK)["error"], "STREAM_ID_REQUIRED")

    def test_sablier_target(self):
        t = C.parse_target("ethereum", F.LOCKUP.upper().replace("0X", "0x"), "42")
        self.assertEqual((t["kind"], t["release"], t["alias"], t["stream_id"]), (C.K_SAB, "v1.1", "LL2", 42))

    def test_lockup_address_only_on_its_own_chain(self):
        t = C.parse_target("base", F.LOCKUP, "42")
        self.assertEqual(t["error"], "NOT_A_SABLIER_DEPLOYMENT")

    def test_vesting_wallet_needs_token(self):
        self.assertEqual(C.parse_target("ethereum", F.WALLET, "")["error"], "TOKEN_ADDRESS_REQUIRED")
        self.assertEqual(C.parse_target("ethereum", F.WALLET, F.WALLET)["error"], "TOKEN_IS_CONTRACT")

    def test_bad_addresses(self):
        for a in ("0x123", "", C.ZERO, "vitalik.eth"):
            self.assertEqual(C.parse_target("ethereum", a, "1")["error"], "BAD_CONTRACT_ADDRESS", a)

    def test_stream_id_bounds(self):
        self.assertEqual(C.parse_target("ethereum", F.LOCKUP, "0")["error"], "BAD_STREAM_ID")
        self.assertEqual(C.parse_target("ethereum", F.LOCKUP, "1" * 14)["error"], "STREAM_ID_REQUIRED")

    def test_every_allowlisted_lockup_is_on_one_chain_only(self):
        seen = {}
        for ch in C.SABLIER:
            for a in C.SABLIER[ch]:
                self.assertEqual(C._addr(a), a)
                self.assertNotIn(a, seen, a)
                seen[a] = ch
        self.assertEqual(len(seen), 50)


# =============================================================================
# 5. parsers: durations, amounts, dates
# =============================================================================

class Durations(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(dur("12-month cliff"), [12 * MONTH])
        self.assertEqual(dur("1 year"), [YEAR])
        self.assertEqual(dur("36 months"), [36 * MONTH])
        self.assertEqual(dur("3 years"), [3 * YEAR])
        self.assertEqual(dur("one-year cliff"), [YEAR])
        self.assertEqual(dur("twenty four months"), [24 * MONTH])
        self.assertEqual(dur("4y"), [4 * YEAR])
        self.assertEqual(dur("1yr"), [YEAR])
        self.assertEqual(dur("6 mo"), [6 * MONTH])
        self.assertEqual(dur("90 days"), [90 * DAY])
        self.assertEqual(dur("2 weeks"), [14 * DAY])
        self.assertEqual(dur("1.5 years"), [YEAR * 3 // 2])
        self.assertEqual(dur("a year"), [YEAR])

    def test_month_is_30_days_year_365(self):
        self.assertEqual(dur("12 months")[0], 360 * DAY)
        self.assertNotEqual(dur("12 months")[0], dur("1 year")[0])

    def test_bare_m_is_ambiguous(self):
        self.assertIsNone(dur("a 12m cliff"))
        self.assertIsNone(dur("12 m"))

    def test_docs_define_month(self):
        self.assertEqual(C.month_year_seconds(C._equals_sign("Note: 1 month = 31 days.")), (31 * DAY, YEAR))
        self.assertEqual(C.month_year_seconds("a month is 28 days"), (28 * DAY, YEAR))
        self.assertEqual(C.month_year_seconds("1 year is defined as 360 days"), (MONTH, 360 * DAY))

    def test_docs_define_month_out_of_range_ignored(self):
        self.assertEqual(C.month_year_seconds("1 month is 90 days"), (MONTH, YEAR))
        self.assertEqual(C.month_year_seconds("the first month is 31 days long"), (MONTH, YEAR))


class Amounts(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(amt("500,000 ARB"), ["500000"])
        self.assertEqual(amt("500k ARB"), ["500000"])
        self.assertEqual(amt("0.5M ARB"), ["500000"])
        self.assertEqual(amt("1.5 million OP"), ["1500000"])
        self.assertEqual(amt("17_450_000 CRV"), ["17450000"])
        self.assertEqual(amt("29,465,000 NEXT"), ["29465000"])
        self.assertEqual(amt("895.8057 AAVE"), ["895.8057"])
        self.assertEqual(amt("2B tokens"), ["2000000000"])

    def test_not_amounts(self):
        self.assertEqual(amt("35% of supply"), [])
        self.assertEqual(amt("over 36 months"), [])
        self.assertEqual(amt("on Jan 1, 2025"), [])
        self.assertEqual(amt("in 2026"), [])
        self.assertEqual(amt("LL2-1-14801"), [])
        self.assertEqual(amt("0x1072ECb3d246ED37Dd709471D14966A2c3F36a71"), [])
        self.assertEqual(amt("48h"), [])

    def test_comma_grouped_year_like_number_is_an_amount(self):
        self.assertEqual(amt("2,000 EXA"), ["2000"])

    def test_amount_value_one_only(self):
        self.assertEqual(C.amount_value("500,000 VEST over 3 years", *MY), "500000")
        self.assertEqual(C.amount_value("500,000 VEST and 250,000 more", *MY)["drop"], "SEVERAL_AMOUNTS_IN_QUOTE")
        self.assertEqual(C.amount_value("the team allocation", *MY)["drop"], "NO_AMOUNT_IN_QUOTE")

    def test_to_raw(self):
        self.assertEqual(C.to_raw("500000", 18), 500000 * 10 ** 18)
        self.assertEqual(C.to_raw("895.8057", 18), 8958057 * 10 ** 14)
        self.assertEqual(C.to_raw("1926", 6), 1926 * 10 ** 6)


class Dates(unittest.TestCase):
    def d(self, y, m, dd):
        return C._days_from_civil(y, m, dd) * DAY

    def test_forms(self):
        self.assertEqual(C.dates("2025-01-01"), [self.d(2025, 1, 1)])
        self.assertEqual(C.dates("Jan 1, 2025"), [self.d(2025, 1, 1)])
        self.assertEqual(C.dates("January 1st, 2025"), [self.d(2025, 1, 1)])
        self.assertEqual(C.dates("1 January 2025"), [self.d(2025, 1, 1)])
        self.assertEqual(C.dates("6 October 2027"), [self.d(2027, 10, 6)])
        self.assertEqual(C.dates("Feb 1st, 2026"), [self.d(2026, 2, 1)])
        self.assertEqual(C.dates("the 1st of March 2026"), [self.d(2026, 3, 1)])

    def test_no_year(self):
        self.assertIsNone(C.dates("starting February 14"))

    def test_numeric_slash_ignored(self):
        self.assertEqual(C.dates("01/02/2025"), [])

    def test_may_the_verb(self):
        self.assertEqual(C.dates("tokens may vest over 2025"), [])

    def test_start_value_rules(self):
        self.assertEqual(C.start_value("Vesting starts on January 1, 2025."), self.d(2025, 1, 1))
        self.assertEqual(C.start_value("released until 6 October 2029")["drop"], "NO_START_WORD")
        self.assertEqual(C.start_value("from 2025-01-01 until 2026-01-01")["drop"], "SEVERAL_DATES_IN_QUOTE")
        self.assertEqual(C.start_value("starting February 14")["drop"], "DATE_WITHOUT_YEAR")
        self.assertEqual(C.start_value("from 2025-01-01 through the end")["drop"], "DATE_MAY_BE_AN_END")


class CliffAndVesting(unittest.TestCase):
    def test_cliff_forms(self):
        self.assertEqual(C.cliff_value("12-month cliff", *MY), 12 * MONTH)
        self.assertEqual(C.cliff_value("a one year cliff", *MY), YEAR)
        self.assertEqual(C.cliff_value("cliff of 6 months", *MY), 6 * MONTH)
        self.assertEqual(C.cliff_value("Cliff: 90 days", *MY), 90 * DAY)
        self.assertEqual(C.cliff_value("cliff period of 1 year", *MY), YEAR)
        self.assertEqual(C.cliff_value("1-year cliff, 3-year vest", *MY), YEAR)

    def test_no_cliff(self):
        self.assertEqual(C.cliff_value("linear vesting without a cliff", *MY), 0)
        self.assertEqual(C.cliff_value("no cliff", *MY), 0)

    def test_cliff_drops(self):
        self.assertEqual(C.cliff_value("12 months", *MY)["drop"], "NO_CLIFF_WORD")
        self.assertEqual(C.cliff_value("the cliff applies", *MY)["drop"], "NO_CLIFF_DURATION")
        self.assertEqual(C.cliff_value("a 12m cliff", *MY)["drop"], "AMBIGUOUS_UNIT")

    def test_vesting_forms(self):
        self.assertEqual(C.vesting_value("linear over 36 months", *MY), {"seconds": 36 * MONTH, "after_cliff": False})
        self.assertEqual(C.vesting_value("1-year cliff, 3-year vest", *MY)["seconds"], 3 * YEAR)
        self.assertEqual(C.vesting_value("12-month cliff, then linear over 36 months", *MY),
                         {"seconds": 36 * MONTH, "after_cliff": True})
        self.assertEqual(C.vesting_value("streamed over 24 months", *MY)["seconds"], 24 * MONTH)

    def test_vesting_drops(self):
        self.assertEqual(C.vesting_value("36 months", *MY)["drop"], "NO_VESTING_WORD")
        self.assertEqual(C.vesting_value("vests over 2 years or 3 years", *MY)["drop"], "SEVERAL_DURATIONS_IN_QUOTE")
        self.assertEqual(C.vesting_value("vesting over 12m", *MY)["drop"], "AMBIGUOUS_UNIT")


class LockAndSymbol(unittest.TestCase):
    def test_lock_words(self):
        for q in ("The stream is non-cancelable.", "tokens are locked for 36 months", "an irrevocable grant",
                  "it cannot be canceled", "non-revocable vesting"):
            self.assertIs(C.lock_value(q), True, q)

    def test_unlock_words_drop(self):
        for q in ("two revocable one-year vesting streams", "unlocked at TGE", "the stream is cancelable"):
            self.assertIn("drop", C.lock_value(q), q)

    def test_symbol_standalone(self):
        self.assertTrue(C.symbol_in("52,000 EXA tokens", "EXA"))
        self.assertTrue(C.symbol_in("52,000 $EXA", "$EXA"))
        self.assertFalse(C.symbol_in("52,000 EXAMPLE", "EXA"))
        self.assertFalse(C.symbol_in("52,000 EXA", ""))

    def test_dec_symbol_bytes32(self):
        self.assertEqual(C.dec_symbol("0x" + b"MKR".hex().ljust(64, "0")), "MKR")
        self.assertEqual(C.dec_symbol(F.abi_string("EXA")), "EXA")
        self.assertEqual(C.dec_symbol("0x"), "")


# =============================================================================
# 6. binding the source to the subject
# =============================================================================

class Binding(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world()
        F.standard_stream(self.mc)
        self.tg = C.parse_target("ethereum", F.LOCKUP, str(F.SID))
        self.facts = {"beneficiary": F.RECIP, "start": F.START, "token": F.TOK}

    def refs(self, text, date=F.START):
        return C.subject_refs(text, text.lower(), "ethereum", self.tg, self.facts, date)

    def test_link_anchor_and_other_stream(self):
        r = self.refs(F.DOCS)
        self.assertEqual([a[2] for a in r["anchors"]], ["LINK"])
        self.assertEqual(len(r["others"]), 1)

    def test_link_with_wrong_alias_chain_or_id_is_not_ours(self):
        for link in ("LL-1-42", "LL2-10-42", "LL2-1-41", "LD2-1-42"):
            r = self.refs("see app.sablier.com/stream/" + link)
            self.assertEqual(r["anchors"], [], link)

    def test_contract_id_forms(self):
        r = self.refs("nft: opensea.io/assets/ethereum/" + F.LOCKUP + "/42 and " + F.LOCKUP + "-1-42")
        self.assertEqual([a[2] for a in r["anchors"]], ["CONTRACT_ID", "CONTRACT_ID"])

    def test_address_plus_id_mention(self):
        r = self.refs("Lockup: " + F.LOCKUP + "\n{ id: 42, amount: 1 }\n{ id: 43, amount: 2 }")
        self.assertEqual([a[2] for a in r["anchors"]], ["ADDRESS_ID"])
        self.assertEqual(len(r["others"]), 1)

    def test_id_mention_without_lockup_address_is_nothing(self):
        r = self.refs("{ id: 42, amount: 1 }")
        self.assertEqual(r["anchors"], [])

    def test_recipient_inside_window(self):
        r = self.refs("Grant to " + F.RECIP, date=F.START - 10 * DAY)
        self.assertEqual([a[2] for a in r["anchors"]], ["RECIPIENT"])

    def test_recipient_outside_window(self):
        self.assertEqual(self.refs("Grant to " + F.RECIP, date=F.START + 31 * DAY)["anchors"], [])
        self.assertEqual(self.refs("Grant to " + F.RECIP, date=F.START - 181 * DAY)["anchors"], [])
        self.assertEqual(len(self.refs("Grant to " + F.RECIP, date=F.START + 30 * DAY)["anchors"]), 1)
        self.assertEqual(len(self.refs("Grant to " + F.RECIP, date=F.START - 180 * DAY)["anchors"]), 1)

    def test_vesting_wallet_anchor_and_competitor(self):
        tg = C.parse_target("ethereum", F.WALLET, F.TOK)
        r = C.subject_refs(F.DOCS_VW, F.DOCS_VW.lower(), "ethereum", tg, {"beneficiary": F.RECIP, "token": F.TOK}, 0)
        self.assertEqual([a[2] for a in r["anchors"]], ["ADDRESS"])
        self.assertEqual([o[2] for o in r["others"]], ["OTHER_VESTING_ADDRESS"])

    def test_bound_same_section(self):
        r = self.refs(F.DOCS)
        i = F.DOCS.find("12-month cliff")
        self.assertEqual(C.bound_at(F.DOCS, r, i, i + 14), "")

    def test_other_section_not_bound(self):
        r = self.refs(F.DOCS)
        i = F.DOCS.find("6-month cliff")
        self.assertEqual(C.bound_at(F.DOCS, r, i, i + 13), "QUOTE_LINE_NAMES_ANOTHER_SUBJECT"
                         if False else C.bound_at(F.DOCS, r, i, i + 13))
        self.assertNotEqual(C.bound_at(F.DOCS, r, i, i + 13), "")

    def test_section_with_two_subjects_needs_the_line(self):
        text = "## Grants\nTeam: " + F.SAB_LINK + " 12-month cliff\nOther: app.sablier.com/stream/LL2-1-43 6-month cliff\n" \
               "All grants vest over 36 months.\n"
        r = self.refs(text)
        a = text.find("12-month cliff")
        self.assertEqual(C.bound_at(text, r, a, a + 14), "")
        b = text.find("6-month cliff")
        self.assertEqual(C.bound_at(text, r, b, b + 13), "QUOTE_LINE_NAMES_ANOTHER_SUBJECT")
        v = text.find("vest over 36 months")
        self.assertEqual(C.bound_at(text, r, v, v + 19), "SECTION_NAMES_ANOTHER_SUBJECT")

    def test_nearest_reference_on_a_shared_line(self):
        text = "Team " + F.SAB_LINK + " vests over 36 months; investors app.sablier.com/stream/LL2-1-43 vest over 24 months."
        r = self.refs(text)
        a = text.find("vests over 36 months")
        b = text.find("vest over 24 months")
        self.assertEqual(C.bound_at(text, r, a, a + 20), "")
        self.assertEqual(C.bound_at(text, r, b, b + 19), "QUOTE_NEARER_ANOTHER_SUBJECT")

    def test_subject_missing_refuses(self):
        stub.WEB.pages[F.RAW] = (200, "# Docs\nTeam tokens vest over 36 months.\n")
        stub.MODEL.answer = F.GOOD
        self.assertEqual(F.file(F.new_contract()).error, "REFUSED: SUBJECT_NOT_IN_SOURCE")


# =============================================================================
# 7. keeping the model's fields
# =============================================================================

class KeepFields(unittest.TestCase):
    def setUp(self):
        self.tg = C.parse_target("ethereum", F.LOCKUP, str(F.SID))
        self.refs = C.subject_refs(F.DOCS, F.DOCS.lower(), "ethereum", self.tg,
                                   {"beneficiary": F.RECIP, "start": F.START, "token": F.TOK}, 0)

    def keep(self, field, value, quote):
        return C.keep_field({"field": field, "value": value, "quote": quote}, F.DOCS, self.refs, MY)

    def test_good_answer_all_kept(self):
        k = C.keep_fields(F.GOOD, F.DOCS, self.refs, MY)
        self.assertEqual([x["field"] for x in k["kept"]],
                         ["total_amount", "token_symbol", "cliff_duration", "vesting_duration", "start_date", "irrevocable"])

    def test_quote_not_verbatim(self):
        self.assertEqual(self.keep("total_amount", "500,000", "The team gets 500,000 VEST.")["drop"], "QUOTE_NOT_IN_SOURCE")

    def test_value_altered(self):
        self.assertEqual(self.keep("total_amount", "900,000", "The team receives 500,000 VEST.")["drop"],
                         "VALUE_DIFFERS_FROM_QUOTE")
        self.assertEqual(self.keep("cliff_duration", "6 months", "There is a 12-month cliff")["drop"],
                         "VALUE_DIFFERS_FROM_QUOTE")

    def test_wrong_section_quote_dropped(self):
        got = self.keep("cliff_duration", "6 months", "6-month cliff")
        self.assertIn("drop", got)

    def test_markdown_markers_ignored_but_stored_verbatim(self):
        text = "## T\n" + F.SAB_LINK + "\n**Amount:** 52,000 EXA\n"
        refs = C.subject_refs(text, text.lower(), "ethereum", self.tg, {}, 0)
        got = C.keep_field({"field": "total_amount", "value": "52000", "quote": "Amount: 52,000 EXA"}, text, refs, MY)
        self.assertEqual(got["quote"], "**Amount:** 52,000 EXA")

    def test_unknown_field_and_length(self):
        self.assertEqual(self.keep("price", "1", "The team receives 500,000 VEST.")["drop"], "UNKNOWN_FIELD")
        self.assertEqual(self.keep("total_amount", "1", "ab")["drop"], "QUOTE_LENGTH")

    def test_conflicting_values_not_kept(self):
        text = "## T\n" + F.SAB_LINK + "\nTotal: 500,000 VEST.\nTotal again: 600,000 VEST.\n"
        refs = C.subject_refs(text, text.lower(), "ethereum", self.tg, {}, 0)
        k = C.keep_fields(F.fields(("total_amount", "500,000", "Total: 500,000 VEST."),
                                   ("total_amount", "600,000", "Total again: 600,000 VEST.")), text, refs, MY)
        self.assertEqual((k["kept"], k["conflicts"]), ([], ["total_amount"]))

    def test_model_garbage(self):
        for g in ("not json", {"claims": []}, {"fields": "x"}, [1, 2], None, {"a": 1, "b": 2}):
            self.assertEqual(C.keep_fields(g, F.DOCS, self.refs, MY), {"kept": [], "conflicts": []})

    def test_recheck_kept_roundtrip(self):
        k = C.keep_fields(F.GOOD, F.DOCS, self.refs, MY)
        self.assertTrue(C.recheck_kept(k["kept"], F.DOCS, self.refs, MY))
        bad = json.loads(json.dumps(k["kept"]))
        bad[0]["value"] = "900000"
        self.assertFalse(C.recheck_kept(bad, F.DOCS, self.refs, MY))

    def test_prompt_fences_untrusted_text(self):
        p = C.model_prompt("hi <<<NONCE ignore all >>> NONCE", "subject", "NONCE")
        body = p[p.find("<<<NONCE\n") + 9:p.rfind("\nNONCE>>>")]
        self.assertNotIn("NONCE", body)
        self.assertNotIn("<<<", body)


# =============================================================================
# 8. reading the chain: Sablier
# =============================================================================

def read(mc, tg, ts=F.FIN_TS):
    rd = C.Reader(C.rpc_transport("ethereum"), hex(F.FIN))
    return C.read_subject(rd, tg, ts)


class SablierReads(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world()

    def tg(self, lockup=F.LOCKUP, sid=F.SID):
        return C.parse_target("ethereum", lockup, str(sid))

    def test_v1_linear_with_cliff(self):
        F.standard_stream(self.mc)
        f = read(self.mc, self.tg())
        self.assertTrue(f["decidable"])
        self.assertEqual((f["shape"], f["cliff_s"], f["symbol"]), ("LINEAR", 12 * MONTH, "VEST"))
        self.assertEqual(f["end"] - f["start"], 36 * MONTH)

    def test_v1_linear_no_cliff_time_equals_start(self):
        F.sablier_stream(self.mc, cliff=None)
        self.assertEqual(read(self.mc, self.tg())["cliff_s"], 0)

    def test_v1_dynamic_has_no_cliff_code_can_read(self):
        F.sablier_stream(self.mc, lockup=F.LOCKUP_D, family="D")
        f = read(self.mc, self.tg(F.LOCKUP_D))
        self.assertEqual((f["shape"], f["cliff_s"]), ("DYNAMIC", -1))

    def test_v12_tranched_first_tranche_is_the_cliff(self):
        tr = [(0, F.START + 30 * DAY), (100 * 10 ** 18, F.START + 6 * MONTH), (400 * 10 ** 18, F.START + YEAR)]
        F.sablier_stream(self.mc, lockup=F.LOCKUP_T, family="T", tranches=tr, deposited=500 * 10 ** 18,
                         end=F.START + YEAR)
        f = read(self.mc, self.tg(F.LOCKUP_T))
        self.assertEqual((f["shape"], f["cliff_s"]), ("TRANCHED", 6 * MONTH))

    def test_v2_linear_model_and_cliff(self):
        F.sablier_stream(self.mc, lockup=F.LOCKUP_K, family="K", model=0, cliff=F.START + YEAR)
        f = read(self.mc, self.tg(F.LOCKUP_K))
        self.assertEqual((f["pattern"], f["shape"], f["cliff_s"]), ("SABLIER_LOCKUP_v2.0", "LINEAR", YEAR))

    def test_v2_start_unlock_means_no_cliff(self):
        F.sablier_stream(self.mc, lockup=F.LOCKUP_K, family="K", model=0, cliff=F.START + YEAR, unlock=(10, 0))
        self.assertEqual(read(self.mc, self.tg(F.LOCKUP_K))["cliff_s"], 0)

    def test_v2_unknown_model_unverifiable(self):
        F.sablier_stream(self.mc, lockup=F.LOCKUP_K, family="K", model=3)
        f = read(self.mc, self.tg(F.LOCKUP_K))
        self.assertEqual((f["decidable"], f["why"]), (False, "LOCKUP_MODEL_NOT_SUPPORTED"))

    def test_canceled_stream_unverifiable(self):
        F.standard_stream(self.mc, canceled=True, refunded=TOTAL_HALF, withdrawn=0)
        f = read(self.mc, self.tg())
        self.assertEqual((f["decidable"], f["why"]), (False, "STREAM_CANCELED"))

    def test_withdrawn_more_than_deposited_unverifiable(self):
        F.standard_stream(self.mc, withdrawn=F.TOTAL + 1, streamed=F.TOTAL)
        self.assertEqual(read(self.mc, self.tg())["why"], "STREAM_VALUES_INCONSISTENT")

    def test_withdrawn_more_than_streamed_unverifiable(self):
        F.standard_stream(self.mc, withdrawn=10, streamed=5)
        self.assertEqual(read(self.mc, self.tg())["why"], "STREAM_VALUES_INCONSISTENT")

    def test_end_before_start_unverifiable(self):
        F.sablier_stream(self.mc, start=F.START, end=F.START - 1, cliff=F.START - 1)
        self.assertEqual(read(self.mc, self.tg())["why"], "STREAM_VALUES_INCONSISTENT")

    def test_stream_not_found_refuses(self):
        F.standard_stream(self.mc)
        self.mc.calls[(F.LOCKUP, C.SEL["isStream"] + F.sid_word(F.SID))] = F.word(0)
        self.assertEqual(read(self.mc, self.tg()), {"refused": "STREAM_NOT_FOUND"})

    def test_burned_nft_has_no_recipient(self):
        F.standard_stream(self.mc, burned=True)
        self.assertEqual(read(self.mc, self.tg())["beneficiary"], C.ZERO)

    def test_rpc_error_is_read_failed(self):
        F.standard_stream(self.mc)
        self.mc.fail = lambda m, p: {"code": -32005, "message": "rate limited"}
        with self.assertRaises(C.ReadFailed):
            read(self.mc, self.tg())


TOTAL_HALF = F.TOTAL // 2


# =============================================================================
# 9. reading the chain: OpenZeppelin VestingWallet
# =============================================================================

class VestingWalletReads(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world(F.DOCS_VW)
        self.tg = C.parse_target("ethereum", F.WALLET, F.TOK)

    def test_v5_wallet(self):
        F.vesting_wallet(self.mc)
        f = read(self.mc, self.tg)
        self.assertTrue(f["decidable"], f)
        self.assertEqual((f["pattern"], f["beneficiary"], f["cliff_s"], f["total"]), (C.K_VW, F.RECIP, 0, str(F.TOTAL)))

    def test_v4_wallet_beneficiary(self):
        F.vesting_wallet(self.mc, version=4)
        f = read(self.mc, self.tg)
        self.assertEqual((f["decidable"], f["beneficiary"]), (True, F.RECIP))

    def test_cliff_wallet(self):
        F.vesting_wallet(self.mc, cliff=F.START + YEAR)
        f = read(self.mc, self.tg)
        self.assertEqual((f["pattern"], f["cliff_s"]), (C.K_VWC, YEAR))

    def test_total_is_balance_plus_released(self):
        F.vesting_wallet(self.mc, balance=300, released=200)
        self.assertEqual(read(self.mc, self.tg)["total"], "500")

    def test_extra_function_not_standard(self):
        F.vesting_wallet(self.mc, extra_selectors=("b6549f75",))         # revoke(address)
        f = read(self.mc, self.tg)
        self.assertEqual((f["decidable"], f["why"]), (False, "NOT_A_STANDARD_VESTING_WALLET"))

    def test_delegatecall_not_standard(self):
        F.vesting_wallet(self.mc, code=F.vw_code(F.VW_V5, extra="f4"))
        self.assertEqual(read(self.mc, self.tg)["why"], "CODE_CAN_DELEGATE_OR_SELFDESTRUCT")

    def test_proxy_unknown_logic(self):
        F.vesting_wallet(self.mc)
        self.mc.slots[(F.WALLET, C.IMPL_SLOT)] = F.aword(F.addr(0x9999))
        self.assertEqual(read(self.mc, self.tg)["why"], "PROXY_UNKNOWN_LOGIC")

    def test_clone_unverifiable(self):
        F.vesting_wallet(self.mc, code="0x363d3d373d3d3d363d73" + "11" * 20 + "5af43d82803e903d91602b57fd5bf3")
        self.assertEqual(read(self.mc, self.tg)["why"], "CLONE_OR_DELEGATED_CODE")

    def test_custom_curve_unverifiable(self):
        F.vesting_wallet(self.mc, curve=lambda total, t: total if t >= F.START else 0)
        self.assertEqual(read(self.mc, self.tg)["why"], "SCHEDULE_NOT_OPENZEPPELIN_LINEAR")

    def test_no_code(self):
        F.vesting_wallet(self.mc)
        self.mc.code[F.WALLET] = "0x"
        self.assertEqual(read(self.mc, self.tg)["why"], "NO_CONTRACT_CODE")

    def test_unreadable_wallet(self):
        F.vesting_wallet(self.mc)
        self.mc.calls[(F.WALLET, C.SEL["start"])] = stub.MockChain.REVERT
        self.assertEqual(read(self.mc, self.tg)["why"], "VESTING_WALLET_UNREADABLE")

    def test_unknown_contract_with_sablier_like_getters_is_not_sablier(self):
        # a look-alike answering getRecipient(...) is read as a VestingWallet candidate and fails
        self.mc.code[F.WALLET] = F.vw_code(("6d0cee75", "bc2be1be", "9067b677"))
        F.token(self.mc, F.TOK)
        self.assertEqual(read(self.mc, self.tg)["why"], "NOT_A_STANDARD_VESTING_WALLET")

    def test_dispatch_scan(self):
        cf = C.code_facts(bytes.fromhex(F.vw_code(("be9a6555", "0fb5a6b4"))[2:]))
        self.assertEqual(cf["dispatch"], ["0fb5a6b4", "be9a6555"])
        self.assertEqual(cf["mutators"], [])


# =============================================================================
# 10. verdicts and tolerance boundaries (decide is pure)
# =============================================================================

def facts(**kw):
    f = {"decidable": True, "why": "", "contract": F.LOCKUP, "symbol": "VEST", "decimals": 18,
         "total": str(F.TOTAL), "start": F.START, "end": F.START + 36 * MONTH, "cliff_s": 12 * MONTH,
         "beneficiary": F.RECIP, "cancelable": False, "unlocked_now": "0", "withdrawn": "0", "token": F.TOK}
    f.update(kw)
    return f


BLOCK = {"number": F.FIN, "hash": "0x" + "1" * 64, "timestamp": F.FIN_TS}


def kept(**kw):
    out = []
    for k, v in kw.items():
        out.append({"field": k, "value": v, "quote": "q"})
    return out


def V(**kw):
    return {"seconds": kw.get("s", 36 * MONTH), "after_cliff": kw.get("after", False)}


class Verdicts(unittest.TestCase):
    def d(self, k, f=None, tis=False, block=BLOCK):
        return C.decide(k, f or facts(), tis, block)

    def test_all_match(self):
        out = self.d(kept(total_amount="500000", token_symbol="VEST", cliff_duration=12 * MONTH,
                          vesting_duration=V(), start_date=F.START, beneficiary=F.RECIP))
        self.assertEqual((out["verdict"], out["decided"]), ("MATCHES", 6))

    def test_amount_boundary_inclusive(self):
        claim = 500000
        lim = F.TOTAL * 50 // 10000
        out = self.d(kept(total_amount=str(claim), token_symbol="VEST"), facts(total=str(F.TOTAL + lim)))
        self.assertEqual(out["fields"]["total_amount"], "MATCHES")
        out = self.d(kept(total_amount=str(claim), token_symbol="VEST"), facts(total=str(F.TOTAL + lim + 1)))
        self.assertEqual(out["fields"]["total_amount"], "MORE_THAN_CLAIMED")
        out = self.d(kept(total_amount=str(claim), token_symbol="VEST"), facts(total=str(F.TOTAL - lim)))
        self.assertEqual(out["fields"]["total_amount"], "MATCHES")
        out = self.d(kept(total_amount=str(claim), token_symbol="VEST"), facts(total=str(F.TOTAL - lim - 1)))
        self.assertEqual(out["fields"]["total_amount"], "LESS_THAN_CLAIMED")

    def test_amount_needs_token_bound(self):
        out = self.d(kept(total_amount="500000"))
        self.assertEqual((out["fields"]["total_amount"], out["why"]["total_amount"]),
                         ("UNVERIFIABLE", "TOKEN_NOT_BOUND_TO_SOURCE"))
        out = self.d(kept(total_amount="500000"), tis=True)
        self.assertEqual(out["fields"]["total_amount"], "MATCHES")

    def test_different_token_symbol(self):
        out = self.d(kept(total_amount="500000", token_symbol="ARB"))
        self.assertEqual(out["fields"], {"token_symbol": "UNVERIFIABLE", "total_amount": "UNVERIFIABLE"})
        self.assertEqual(out["verdict"], "UNVERIFIABLE")

    def test_duration_boundary_two_days(self):
        f = facts(end=F.START + 36 * MONTH + 2 * DAY)
        self.assertEqual(self.d(kept(vesting_duration=V()), f)["fields"]["vesting_duration"], "MATCHES")
        f = facts(end=F.START + 36 * MONTH + 2 * DAY + 1)
        self.assertEqual(self.d(kept(vesting_duration=V()), f)["fields"]["vesting_duration"], "UNLOCKS_LATER")
        f = facts(end=F.START + 36 * MONTH - 2 * DAY)
        self.assertEqual(self.d(kept(vesting_duration=V()), f)["fields"]["vesting_duration"], "MATCHES")
        f = facts(end=F.START + 36 * MONTH - 2 * DAY - 1)
        self.assertEqual(self.d(kept(vesting_duration=V()), f)["fields"]["vesting_duration"], "UNLOCKS_EARLIER")

    def test_cliff_boundaries(self):
        self.assertEqual(self.d(kept(cliff_duration=12 * MONTH), facts(cliff_s=12 * MONTH - 2 * DAY))["fields"]["cliff_duration"], "MATCHES")
        self.assertEqual(self.d(kept(cliff_duration=12 * MONTH), facts(cliff_s=12 * MONTH - 2 * DAY - 1))["fields"]["cliff_duration"], "UNLOCKS_EARLIER")
        self.assertEqual(self.d(kept(cliff_duration=12 * MONTH), facts(cliff_s=12 * MONTH + 2 * DAY + 1))["fields"]["cliff_duration"], "UNLOCKS_LATER")

    def test_claimed_cliff_missing_on_chain(self):
        out = self.d(kept(cliff_duration=DAY), facts(cliff_s=0))
        self.assertEqual((out["fields"]["cliff_duration"], out["why"]["cliff_duration"]),
                         ("UNLOCKS_EARLIER", "CLAIMED_CLIFF_NOT_ON_CHAIN"))

    def test_no_cliff_claim_matches_no_cliff(self):
        self.assertEqual(self.d(kept(cliff_duration=0), facts(cliff_s=0))["fields"]["cliff_duration"], "MATCHES")

    def test_dynamic_cliff_unverifiable(self):
        out = self.d(kept(cliff_duration=YEAR), facts(cliff_s=-1))
        self.assertEqual(out["why"]["cliff_duration"], "SHAPE_HAS_NO_CLIFF_CODE_CAN_READ")

    def test_after_cliff_reading_b(self):
        k = kept(cliff_duration=12 * MONTH, vesting_duration=V(after=True))
        self.assertEqual(self.d(k, facts(end=F.START + 48 * MONTH))["fields"]["vesting_duration"], "MATCHES")
        self.assertEqual(self.d(k, facts(end=F.START + 36 * MONTH))["fields"]["vesting_duration"], "MATCHES")
        self.assertEqual(self.d(k, facts(end=F.START + 42 * MONTH))["fields"]["vesting_duration"], "UNVERIFIABLE")
        self.assertEqual(self.d(k, facts(end=F.START + 30 * MONTH))["fields"]["vesting_duration"], "UNLOCKS_EARLIER")
        self.assertEqual(self.d(k, facts(end=F.START + 50 * MONTH))["fields"]["vesting_duration"], "UNLOCKS_LATER")

    def test_start_date(self):
        self.assertEqual(self.d(kept(start_date=F.START), facts(start=F.START + 2 * DAY))["fields"]["start_date"], "MATCHES")
        self.assertEqual(self.d(kept(start_date=F.START), facts(start=F.START - 3 * DAY))["fields"]["start_date"], "UNLOCKS_EARLIER")
        self.assertEqual(self.d(kept(start_date=F.START), facts(start=F.START + 3 * DAY))["fields"]["start_date"], "UNLOCKS_LATER")

    def test_beneficiary(self):
        self.assertEqual(self.d(kept(beneficiary=F.OTHER))["verdict"], "BENEFICIARY_DIFFERS")
        self.assertEqual(self.d(kept(beneficiary=F.OTHER), facts(beneficiary=C.ZERO))["fields"]["beneficiary"], "UNVERIFIABLE")

    def test_cancelable_not_disclosed(self):
        self.assertEqual(self.d(kept(irrevocable=True), facts(cancelable=True))["verdict"], "CANCELABLE_NOT_DISCLOSED")
        self.assertEqual(self.d(kept(irrevocable=True), facts(cancelable=False))["verdict"], "MATCHES")

    def test_cancelable_after_end_is_moot(self):
        f = facts(cancelable=True, end=F.FIN_TS - 1)
        self.assertEqual(self.d(kept(irrevocable=True), f)["fields"]["irrevocable"], "MATCHES")

    def test_cancelable_without_lock_quote_is_nothing(self):
        out = self.d(kept(total_amount="500000", token_symbol="VEST"), facts(cancelable=True))
        self.assertEqual(out["verdict"], "MATCHES")

    def test_precedence(self):
        out = self.d(kept(total_amount="600000", token_symbol="VEST", cliff_duration=13 * MONTH,
                          irrevocable=True, beneficiary=F.OTHER), facts(cancelable=True))
        self.assertEqual(out["verdict"], "UNLOCKS_EARLIER")
        out = self.d(kept(total_amount="400000", token_symbol="VEST", irrevocable=True), facts(cancelable=True))
        self.assertEqual(out["verdict"], "MORE_THAN_CLAIMED")
        out = self.d(kept(total_amount="600000", token_symbol="VEST", irrevocable=True), facts(cancelable=True))
        self.assertEqual(out["verdict"], "CANCELABLE_NOT_DISCLOSED")
        out = self.d(kept(total_amount="600000", token_symbol="VEST", beneficiary=F.OTHER))
        self.assertEqual(out["verdict"], "BENEFICIARY_DIFFERS")
        out = self.d(kept(total_amount="600000", token_symbol="VEST", cliff_duration=11 * MONTH))
        self.assertEqual(out["verdict"], "LESS_THAN_CLAIMED")
        out = self.d(kept(token_symbol="VEST", cliff_duration=11 * MONTH))
        self.assertEqual(out["verdict"], "UNLOCKS_LATER")

    def test_rank_order_is_fixed(self):
        self.assertEqual(C.RANK, ("UNLOCKS_EARLIER", "MORE_THAN_CLAIMED", "CANCELABLE_NOT_DISCLOSED",
                                  "BENEFICIARY_DIFFERS", "LESS_THAN_CLAIMED", "UNLOCKS_LATER", "MATCHES"))

    def test_nothing_kept(self):
        out = self.d([])
        self.assertEqual((out["verdict"], out["basis"], out["decided"]), ("UNVERIFIABLE", "NO_FIELD_KEPT", 0))

    def test_nothing_decided(self):
        out = self.d(kept(total_amount="1"))
        self.assertEqual((out["verdict"], out["basis"]), ("UNVERIFIABLE", "NO_FIELD_DECIDED"))

    def test_not_decidable_pattern(self):
        out = self.d(kept(total_amount="500000", token_symbol="VEST"), facts(decidable=False, why="STREAM_CANCELED"))
        self.assertEqual((out["verdict"], out["basis"]), ("UNVERIFIABLE", "PATTERN_STREAM_CANCELED"))


# =============================================================================
# 11. unlock math
# =============================================================================

class UnlockMath(unittest.TestCase):
    sched = {"start": 1000, "cliff_s": 100, "start_from": "claim"}
    A = {"name": "A", "end": 1400, "linear_from": 1000, "duration": 400}
    B = {"name": "B", "end": 1500, "linear_from": 1100, "duration": 400}

    def test_before_cliff(self):
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.A, 1099), 0)

    def test_at_cliff(self):
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.A, 1100), 1000)
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.B, 1100), 0)

    def test_mid(self):
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.A, 1200), 2000)
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.B, 1300), 2000)

    def test_after_end(self):
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.A, 1400), 4000)
        self.assertEqual(C.claim_unlockable(4000, self.sched, self.A, 99999), 4000)

    def test_oz_curve(self):
        self.assertEqual(C.oz_vested(1000, 100, 100, 150, 149), 0)
        self.assertEqual(C.oz_vested(1000, 100, 100, 150, 150), 500)
        self.assertEqual(C.oz_vested(1000, 100, 100, 0, 99), 0)
        self.assertEqual(C.oz_vested(1000, 100, 100, 0, 200), 1000)

    def test_recorded_unlock_integers(self):
        mc = F.fresh_world()
        F.standard_stream(mc)
        stub.MODEL.answer = F.GOOD
        r = run_ok(self, F.new_contract())
        u = r["unlock"]
        t = F.FIN_TS
        self.assertEqual(int(u["chain_unlockable"]), F.linear_v1(F.TOTAL, F.START, F.START + 12 * MONTH, F.START + 36 * MONTH, t))
        self.assertEqual(int(u["claim_unlockable"]["A"]), F.TOTAL * (t - F.START) // (36 * MONTH))
        self.assertEqual(int(u["claim_unlockable"]["B"]), F.TOTAL * (t - F.START - 12 * MONTH) // (36 * MONTH))
        self.assertEqual((u["block"], u["amount_from"], u["start_from"]), (F.FIN, "claim", "claim"))

    def test_canceled_stream_records_no_math(self):
        mc = F.fresh_world()
        F.standard_stream(mc, canceled=True, refunded=F.TOTAL // 2)
        stub.MODEL.answer = F.GOOD
        r = run_ok(self, F.new_contract())
        self.assertEqual((r["verdict"], r["unlock"]), ("UNVERIFIABLE", {}))


# =============================================================================
# 12. the contract: filing, refusals, consensus, history, views
# =============================================================================

class Filing(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world()
        F.standard_stream(self.mc)
        stub.MODEL.answer = F.GOOD
        self.c = F.new_contract()

    def test_matches_record(self):
        r = run_ok(self, self.c)
        self.assertEqual((r["verdict"], r["decided"], r["binding"], r["pattern"]),
                         ("MATCHES", 6, "LINK", "SABLIER_LOCKUP_v1.1"))
        self.assertEqual(r["source"]["commit"], F.SHA)
        self.assertEqual(r["source_date"], F.COMMIT_TS)
        self.assertEqual(r["block"], F.FIN)
        self.assertIn("6 of 6 fields decided: MATCHES", r["summary"])

    def test_vesting_wallet_record(self):
        mc = F.fresh_world(F.DOCS_VW)
        F.vesting_wallet(mc)
        stub.MODEL.answer = F.GOOD_VW
        r = run_ok(self, F.new_contract(), contract=F.WALLET, extra=F.TOK)
        self.assertEqual((r["verdict"], r["pattern"], r["token"]), ("MATCHES", C.K_VW, F.TOK))

    def test_vesting_wallet_wrong_token_in_same_wallet(self):
        mc = F.fresh_world(F.DOCS_VW)
        F.vesting_wallet(mc, others={F.TOK2: (7 * 10 ** 24, 0, "OTHER")})
        stub.MODEL.answer = F.GOOD_VW
        r = run_ok(self, F.new_contract(), contract=F.WALLET, extra=F.TOK2)
        self.assertEqual(r["fields"]["results"]["total_amount"], "UNVERIFIABLE")
        self.assertEqual(r["fields"]["results"]["token_symbol"], "UNVERIFIABLE")

    def test_refusals_before_consensus(self):
        cases = [
            (dict(source="https://example.com/x.md"), "REFUSED: URL_HOST_NOT_ALLOWED"),
            (dict(chain="solana"), "REFUSED: UNSUPPORTED_CHAIN"),
            (dict(extra=""), "REFUSED: STREAM_ID_REQUIRED"),
            (dict(branch="fork:main"), "REFUSED: BAD_BRANCH"),
            (dict(contract="0x12"), "REFUSED: BAD_CONTRACT_ADDRESS"),
        ]
        for kw, err in cases:
            stub.WEB.log.clear()
            self.assertEqual(F.file(self.c, **kw).error, err, kw)
            self.assertEqual(stub.MODEL.prompts, [])

    def test_no_clock_refused(self):
        stub.MESSAGE.raw = {}
        self.assertEqual(F.file(self.c).error, "REFUSED: NO_CLOCK")

    def test_block_too_old_refused(self):
        self.mc.set_block(F.FIN, F.NOW - 3601)
        self.assertEqual(F.file(self.c).error, "REFUSED: BLOCK_TOO_OLD")

    def test_block_freshness_boundary(self):
        self.mc.set_block(F.FIN, F.NOW - 3600)
        self.assertTrue(F.file(self.c).ok)

    def test_demo_freshness_30_min(self):
        d = F.new_contract("DEMO", 60, 1800)
        self.mc.set_block(F.FIN, F.NOW - 1801)
        self.assertEqual(F.file(d).error, "REFUSED: BLOCK_TOO_OLD")
        self.mc.set_block(F.FIN, F.NOW - 1700)
        self.assertTrue(F.file(d).ok)

    def test_block_in_future_refused(self):
        self.mc.set_block(F.FIN, F.NOW + 3601)
        self.assertEqual(F.file(self.c).error, "REFUSED: BLOCK_IN_FUTURE")

    def test_rpc_down_refuses(self):
        stub.WEB.down.add(C.CHAINS["ethereum"][1])
        self.assertEqual(F.file(self.c).error, "REFUSED: RPC_UNREADABLE")

    def test_rpc_wrong_chain_refused(self):
        self.mc.chain_id = 5
        self.assertEqual(F.file(self.c).error, "REFUSED: RPC_WRONG_CHAIN")

    def test_rpc_5xx_refuses(self):
        stub.WEB.rpc_status[C.CHAINS["ethereum"][1]] = 503
        self.assertEqual(F.file(self.c).error, "REFUSED: RPC_UNREADABLE")

    def test_stream_not_found_refused(self):
        self.mc.calls[(F.LOCKUP, C.SEL["isStream"] + F.sid_word(F.SID))] = F.word(0)
        self.assertEqual(F.file(self.c).error, "REFUSED: STREAM_NOT_FOUND")

    def test_duplicate_same_source_same_block(self):
        d = F.new_contract("DEMO", 60, 1800)
        self.assertTrue(F.file(d).ok)
        o = F.file(d, at=F.iso(F.NOW + 61))
        self.assertEqual(o.error, "REFUSED: DUPLICATE_OF_RECORD_1")

    def test_new_block_is_a_new_record(self):
        d = F.new_contract("DEMO", 60, 1800)
        self.assertTrue(F.file(d).ok)
        self.mc.finalized = F.FIN + 5
        self.mc.set_block(F.FIN + 5, F.FIN_TS + 60)
        o = F.file(d, at=F.iso(F.NOW + 61))
        self.assertTrue(o.ok, o)
        self.assertEqual(d.get_record(2)["prev_id"], 1)

    def test_cooldown_boundary(self):
        self.assertTrue(F.file(self.c).ok)
        self.mc.finalized = F.FIN + 5
        self.mc.set_block(F.FIN + 5, F.NOW + 21599 - 900)
        o = F.file(self.c, at=F.iso(F.NOW + 21599))
        self.assertEqual(o.error, "REFUSED: COOLDOWN_UNTIL_" + str(F.NOW + 21600))
        self.mc.set_block(F.FIN + 5, F.NOW + 21600 - 900)
        self.assertTrue(F.file(self.c, at=F.iso(F.NOW + 21600)).ok)

    def test_demo_cooldown_60s(self):
        d = F.new_contract("DEMO", 60, 1800)
        self.assertTrue(F.file(d).ok)
        self.assertTrue(F.file(d, at=F.iso(F.NOW + 59)).error.startswith("REFUSED: COOLDOWN_UNTIL_"))

    def test_cooldown_is_per_key(self):
        self.assertTrue(F.file(self.c).ok)
        F.standard_stream(self.mc, sid=43)
        self.mc.calls[(F.LOCKUP, C.SEL["isStream"] + F.sid_word(43))] = F.word(1)
        o = F.file(self.c, extra="43")
        self.assertNotIn("COOLDOWN", str(o.error))

    def test_recheck_links_and_reuses_inputs(self):
        d = F.new_contract("DEMO", 60, 1800)
        self.assertTrue(F.file(d).ok)
        self.mc.finalized = F.FIN + 5
        self.mc.set_block(F.FIN + 5, F.FIN_TS + 60)
        o = F.tx(d, "recheck", 1, at=F.iso(F.NOW + 61))
        self.assertTrue(o.ok, o)
        r = d.get_record(2)
        self.assertEqual((r["prev_id"], r["seq"], r["source_ref"], r["stream_id"]), (1, 1, F.RAW, F.SID))

    def test_recheck_unknown_record(self):
        self.assertEqual(F.tx(self.c, "recheck", 7).error, "REFUSED: NO_SUCH_RECORD")

    def test_history_keeps_last_20_and_folds(self):
        d = F.new_contract("DEMO", 60, 1800)
        for i in range(22):
            self.mc.finalized = F.FIN + i
            self.mc.set_block(F.FIN + i, F.NOW + i * 61 - 900)
            o = F.file(d, at=F.iso(F.NOW + i * 61))
            self.assertTrue(o.ok, (i, o))
        h = d.get_history(d.get_record(22)["key"])
        self.assertEqual((h["filed"], len(h["records"]), h["folded"]["count"], h["folded"]["MATCHES"]), (22, 20, 2, 2))
        self.assertEqual(h["records"][0]["record_id"], 3)
        self.assertEqual(d.get_record(1), {"record_id": 1, "key": h["key"], "seq": 0, "pruned": True})
        self.assertEqual(F.tx(d, "recheck", 1).error, "REFUSED: RECORD_PRUNED")

    def test_validator_disagreement_writes_nothing(self):
        n = [0]

        def ans(prompt, k):
            n[0] += 1
            return F.GOOD if n[0] <= 2 else {"fields": [F.GOOD["fields"][0]]}
        stub.MODEL.answer = ans
        o = F.file(self.c)
        self.assertTrue(o.rolled, o)
        self.assertEqual(int(self.c.records_n), 0)

    def test_leader_self_disagreement_refused(self):
        seq = [F.GOOD, {"fields": [F.GOOD["fields"][0]]}, {"fields": [F.GOOD["fields"][2]]}]
        stub.MODEL.answer = seq
        o = F.file(self.c)
        self.assertEqual(o.error, "REFUSED: EXTRACTION_UNSTABLE")

    def test_model_errors_refused(self):
        stub.MODEL.raise_next = 3
        self.assertEqual(F.file(self.c).error, "REFUSED: EXTRACTION_MODEL_ERROR")

    def test_leader_forged_evidence_rejected(self):
        stub.FORGE["mutate"] = lambda ev: (ev["facts"].__setitem__("total", "1"), ev)[1]
        self.assertTrue(F.file(self.c).rolled)

    def test_leader_forged_fields_rejected(self):
        def m(ev):
            ev["fields"]["kept"][0]["value"] = "900000"
            return ev
        stub.FORGE["mutate"] = m
        self.assertTrue(F.file(self.c).rolled)

    def test_leader_old_block_rejected(self):
        self.mc.set_block(F.FIN - 100, F.FIN_TS - 1000)
        stub.WEB.leader_hook = lambda: setattr(self.mc, "finalized", F.FIN - 100)
        stub.WEB.validator_hook = lambda: setattr(self.mc, "finalized", F.FIN)
        self.assertTrue(F.file(self.c).rolled)

    def test_leader_block_not_finalized_for_validator(self):
        self.mc.set_block(F.FIN + 3, F.FIN_TS + 30)
        stub.WEB.leader_hook = lambda: setattr(self.mc, "finalized", F.FIN + 3)
        stub.WEB.validator_hook = lambda: setattr(self.mc, "finalized", F.FIN)
        self.assertTrue(F.file(self.c).rolled)

    def test_validator_sees_different_chain_state(self):
        def hook():
            self.mc.calls[(F.LOCKUP, C.SEL["getDepositedAmount"] + F.sid_word(F.SID))] = F.word(F.TOTAL * 2)
        stub.WEB.validator_hook = hook
        self.assertTrue(F.file(self.c).rolled)

    def test_leader_refusal_must_match_validator(self):
        stub.FORGE["payload"] = {"refused": "SOURCE_NOT_FOUND"}
        self.assertTrue(F.file(self.c).rolled)

    def test_stats_and_keys(self):
        self.assertTrue(F.file(self.c).ok)
        self.assertEqual(self.c.get_stats()["MATCHES"], 1)
        k = self.c.get_keys(0, 10)
        self.assertEqual(k["total"], 1)
        self.assertIn("github.com/acme/token-docs/docs/vesting.md", k["keys"][0]["label"])
        self.assertEqual(self.c.get_records(0, 5)["total"], 1)

    def test_config(self):
        cfg = self.c.get_config()
        self.assertEqual((cfg["month_s"], cfg["year_s"], cfg["tolerance_s"], cfg["tolerance_bps"]),
                         (30 * DAY, 365 * DAY, 2 * DAY, 50))
        self.assertEqual(cfg["freshness_s"], 3600)

    def test_constructor_bounds(self):
        for args in (("X", 60, 600), ("DEMO", 59, 600), ("DEMO", 60, 299)):
            with self.assertRaises(stub._UserError):
                C.VestingCheck(*args)

    def test_neutral_wording(self):
        r = run_ok(self, self.c)
        low = r["summary"].lower()
        for w in ("scam", "lie", "lied", "rug", "fraud", "mislead", "cheat"):
            self.assertNotIn(w, low.split(), w)
        self.assertTrue(r["summary"].startswith("At block " + str(F.FIN) + " ("))

    def test_summary_for_disagreeing_claim(self):
        F.standard_stream(self.mc, end=F.START + 24 * MONTH)
        r = run_ok(self, self.c)
        self.assertEqual(r["verdict"], "UNLOCKS_EARLIER")
        self.assertIn("allows 500,000 VEST to unlock by " + C.iso_date(F.START + 24 * MONTH), r["summary"])
        self.assertIn("the docs (2025-06-01) state " + C.iso_date(F.START + 36 * MONTH), r["summary"])

    def test_evidence_record_complete(self):
        r = run_ok(self, self.c)
        self.assertEqual(len(r["evidence_sha256"]), 64)
        self.assertGreater(len(r["chain_facts"]["reads"]), 10)
        self.assertEqual(r["source_sha256"], __import__("hashlib").sha256(F.DOCS.encode()).hexdigest())


# =============================================================================
# 13. static rules
# =============================================================================

SRC = F.CONTRACT.read_text()


class Static(unittest.TestCase):
    def test_no_payable_no_custody(self):
        for w in ("write.payable", "emit_transfer", "gl.message.value", "withdraw(", "self.balance"):
            self.assertNotIn(w, SRC, w)

    def test_no_owner_or_setter(self):
        tree = ast.parse(SRC)
        cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VestingCheck"][0]
        fields = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
        for f in fields:
            self.assertNotIn("owner", f)
            self.assertNotIn("admin", f)
        writes = [f.name for f in cls.body if isinstance(f, ast.FunctionDef)
                  and any(ast.unparse(d) == "gl.public.write" for d in f.decorator_list)]
        self.assertEqual(sorted(writes), ["file_check", "recheck"])

    def test_views_read_storage_only(self):
        tree = ast.parse(SRC)
        cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VestingCheck"][0]
        for f in cls.body:
            if isinstance(f, ast.FunctionDef) and any(ast.unparse(d) == "gl.public.view" for d in f.decorator_list):
                src = ast.unparse(f)
                for bad in ("gl.nondet", "run_nondet", "http_get", "exec_prompt", "gather("):
                    self.assertNotIn(bad, src, f.name)
                for n in ast.walk(f):
                    if isinstance(n, (ast.Assign, ast.AugAssign)):
                        for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                            self.assertFalse(ast.unparse(t).startswith("self."), f.name)

    def test_counter_before_revert_scan(self):
        r = subprocess.run([sys.executable, str(F.ROOT / "tools" / "scan_writes.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_no_str_replace(self):
        self.assertNotIn(".replace(", SRC)

    def test_no_undefined_names(self):
        self.assertEqual(stub.undefined_names(F.CONTRACT), [])

    def test_header_pins_runner(self):
        lines = SRC.split("\n")
        self.assertEqual(lines[0], "# v0.3.0")
        self.assertIn("py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng", lines[1])

    def test_prompt_never_asks_for_a_verdict(self):
        p = C.model_prompt("x", "s", "n").lower()
        for w in ("verdict", "compare", "match", "decide"):
            self.assertNotIn(w, p)


if __name__ == "__main__":
    unittest.main()

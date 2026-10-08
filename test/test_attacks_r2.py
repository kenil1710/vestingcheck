"""Round-2 attacker pass, on the code that is new in v1.2.0 only: date
fields, calendar months, markdown tables (cell headers, whole-row quotes),
TABLE_LABEL binding, and the sender+recipient binding re-check. Written as
an attacker: each finding test failed on the first v1.2.0 draft and passes
after its fix; each "Resisted" test documents an attack the draft already
refused. docs/ATTACK_REPORT.md has the write-up.

    cd test && python3 -m unittest -q test_attacks_r2
"""
import unittest

import fixtures as F
import stub
from fixtures import C

DAY = F.DAY
MONTH = F.MONTH
MY = (C.MONTH_S, C.YEAR_S)
D = lambda y, m, d: C._days_from_civil(y, m, d) * DAY

W1 = F.addr(0x6A55)
W2 = F.addr(0x03ED)


def refs_vw(text, wallet=W1, chain="arbitrum"):
    tg = C.parse_target(chain, wallet, F.TOK)
    return C.subject_refs(text, text.lower(), chain, tg, {"token": F.TOK}, 0)


def keep(text, field, value, quote, wallet=W1):
    return C.keep_field({"field": field, "value": value, "quote": quote}, text, refs_vw(text, wallet), MY)


def keep_all(text, items, wallet=W1):
    return C.keep_fields({"fields": [{"field": f, "value": v, "quote": q} for (f, v, q) in items]},
                         text, refs_vw(text, wallet), MY)


# =============================================================================
# findings
# =============================================================================

class R2H1DecoyStreamWithTreasuryAsSender(unittest.TestCase):
    """Found while re-checking H1 for the Exactly proposals. Sablier's create
    functions take `sender` as a parameter: whoever pays for a stream can
    name ANY address as its sender. v1.1.0 bound a stream to a proposal that
    named its sender and its recipient, so an attacker could open a 1-token
    stream "from" the DAO treasury to a grant recipient and file it:
    LESS_THAN_CLAIMED against the DAO. Binding by a DAO's registered
    treasury (the Snapshot space's treasury list) has the same hole. Fix:
    sender and recipient never bind; the source must name the stream."""

    def test_treasury_named_as_sender_does_not_bind(self):
        body = "## Grant\n- **Amount:** 30,000 VEST\n- **Payment terms:** 12 months linear vesting\n" \
               "- **Treasury:** " + F.SENDER + "\n- **Wallet:** " + F.RECIP + "\n"
        mc = F.fresh_world()
        F.standard_stream(mc, deposited=10 ** 18, start=F.PROP_TS + 5 * DAY, cliff=F.PROP_TS + 5 * DAY,
                          end=F.PROP_TS + 6 * DAY)
        cid = F.pin_proposal(F.proposal_bytes(body=body))
        stub.MODEL.answer = F.fields(("total_amount", "30,000", "30,000 VEST"))
        self.assertEqual(F.file(F.new_contract(), source=cid).error, "REFUSED: SUBJECT_NOT_IN_SOURCE")


STALE = """## Wallets

| Modality | Vesting contract address |
| --- | --- |
| Treasury | %s |

| Modality | Start | Cliff | End |
| --- | --- | --- | --- |
| Treasury | 2026-03-05 | 2026-04-05 | 2031-02-05 |

### Superseded schedule (wrong, kept for history)

| Modality | Start | Cliff | End |
| --- | --- | --- | --- |
| Treasury | 2026-03-05 | 2026-04-05 | 2031-01-05 |
""" % W1


class R2M1TwoLabelRowsThatDisagree(unittest.TestCase):
    """TABLE_LABEL bound every row with the subject's label in the section,
    one per table. A section holding the current table and a superseded one
    (a child heading is inside its parent's section) bound both; a quote from
    the stale row was kept on its own. Fix: a field read from a label row is
    dropped when another label row of the subject, under a header naming the
    same field, gives a different value."""

    def test_stale_row_alone_is_not_kept(self):
        self.assertEqual(keep(STALE, "end_date", "2031-01-05", "2031-01-05")["drop"], "TABLE_ROWS_DISAGREE")

    def test_current_row_alone_is_not_kept_either(self):
        self.assertEqual(keep(STALE, "end_date", "2031-02-05", "2031-02-05")["drop"], "TABLE_ROWS_DISAGREE")

    def test_rows_that_agree_are_kept(self):
        self.assertEqual(keep(STALE, "start_date", "2026-03-05", "2026-03-05")["value"], D(2026, 3, 5))


class R2M2DateThatAnchorsARelativePhrase(unittest.TestCase):
    """"the cliff ends 12 months after TGE on 2025-01-01" and "fully vested
    4 years after the TGE on 2025-01-01": the one date is the TGE, not the
    first unlock or the end, but the words before it say cliff / ends /
    fully. Fix: a duration, "after" or "TGE" before the date drops it."""

    def test_first_unlock(self):
        self.assertIn("drop", C.first_unlock_value("the cliff ends 12 months after TGE on 2025-01-01"))
        self.assertIn("drop", C.first_unlock_value("nothing is released until one year after 2025-01-01"))

    def test_end(self):
        self.assertIn("drop", C.end_value("fully vested 4 years after the TGE on 2025-01-01", False))
        self.assertIn("drop", C.end_value("vesting ends 36 months from TGE (2025-01-01)", False))


class R2M3EndWordFarFromTheDate(unittest.TestCase):
    """"approved by the DAO on 2025-03-01; tokens fully vest over time": "by"
    and "fully" are in the quote, so the vote date was read as the end. Fix:
    the end (or first-unlock) word must be one of the last three words
    before the date."""

    def test_vote_date_is_not_an_end(self):
        self.assertIn("drop", C.end_value("Grant approved by the DAO on 2025-03-01, fully vesting", False))

    def test_vote_date_is_not_a_first_unlock(self):
        self.assertIn("drop", C.first_unlock_value("locked until the vote passed on 2025-03-01"))

    def test_close_words_still_read(self):
        self.assertEqual(C.end_value("fully vested by 2028-01-01", False), D(2028, 1, 1))
        self.assertEqual(C.first_unlock_value("Nothing released until 6 October 2027"), D(2027, 10, 6))


PRICES = """## Round

| Investor | Price | Cliff | Wallet |
| --- | --- | --- | --- |
| Seed fund | 0.05 | 12 months | %s |
""" % W1


class R2M4NumberInANonAmountColumn(unittest.TestCase):
    """A cell under "Price" (or "FDV", "Raise") was read as the token
    amount, because only %, date and duration columns were refused. Fix: in
    a table, an amount is read only from a column whose header names an
    amount (Amount, Tokens, Allocation, Total)."""

    def test_price_cell(self):
        self.assertEqual(keep(PRICES, "total_amount", "0.05", "0.05")["drop"], "NOT_AN_AMOUNT_COLUMN")

    def test_whole_row_without_an_amount_column(self):
        self.assertEqual(keep(PRICES, "total_amount", "0.05", "Seed fund | 0.05 | 12 months")["drop"],
                         "NO_CELL_FOR_FIELD")

    def test_cliff_cell_still_read(self):
        self.assertEqual(keep(PRICES, "cliff_duration", "12 months", "12 months")["value"]["months"], 12)


class R2H2SubjectLinkReadAsBeneficiary(unittest.TestCase):
    """Found while verifying the v1.1.0 seed run by hand (nation3 N3GOV-44,
    recorded as BENEFICIARY_DIFFERS): the proposal only links "[vesting
    contract](etherscan.io/address/<wallet>)"; the model labelled that link
    the beneficiary and code compared the wallet's own address with its
    owner. Fix: a beneficiary is never the subject contract or its token,
    and the quote (or its column header) must use a recipient word."""

    def test_nation3_shape(self):
        body = "### Summary\nThis proposal is to withdraw ANT tokens from the [vesting contract ]" \
               "(https://etherscan.io/address/" + F.WALLET + ") and provide liquidity.\n"
        F.fresh_world()
        mc = stub.WEB.chains[C.CHAINS["ethereum"][1]]
        F.vesting_wallet(mc)
        cid = F.pin_proposal(F.proposal_bytes(body=body))
        stub.MODEL.answer = F.fields(("beneficiary", F.WALLET, "[vesting contract ](https://etherscan.io/address/"
                                      + F.WALLET + ")"))
        o = F.file(F.new_contract(), source=cid, contract=F.WALLET, extra=F.TOK)
        self.assertTrue(o.ok, o)
        self.assertEqual((o.value["verdict"], o.value["basis"]), ("UNVERIFIABLE", "NO_FIELD_KEPT"))

    def test_subject_is_never_its_own_beneficiary(self):
        t = "## Team\nThe beneficiary is the wallet " + W1 + ".\n"
        self.assertEqual(keep(t, "beneficiary", W1, "The beneficiary is the wallet " + W1)["drop"],
                         "BENEFICIARY_IS_THE_SUBJECT")

    def test_address_without_a_recipient_word(self):
        t = "## Team\nWallet " + W1 + " holds the team tokens.\nAdmin: " + W2 + "\n"
        self.assertEqual(keep(t, "beneficiary", W2, "Admin: " + W2)["drop"], "NO_RECIPIENT_WORD")

    def test_recipient_column_header(self):
        t = "| Group | Contract | Beneficiary |\n|-|-|-|\n| Team | " + W1 + " | " + W2 + " |\n"
        self.assertEqual(keep(t, "beneficiary", W2, W2)["value"], W2)
        self.assertEqual(keep(t, "beneficiary", W2, "Team | " + W1 + " | " + W2)["value"], W2)


class R2M5QuoteCutOutOfALongerNumber(unittest.TestCase):
    """Found while writing the table attacks (the matcher dates from v1.0):
    a quote only had to occur somewhere in the source, so "6 months" matched
    inside "36 months" and "00,000 VEST" inside "500,000 VEST" - a truncated
    quote read a different value from a bound line. Fix: a quote may not
    start or end inside a word or a number."""

    def test_cut_spans_are_not_quotes(self):
        t = "## Team\nWallet " + W1 + ": 36 months linear, 500,000 VEST.\n"
        self.assertEqual(keep(t, "vesting_duration", "6 months", "6 months linear")["drop"], "QUOTE_NOT_IN_SOURCE")
        self.assertEqual(keep(t, "total_amount", "0", "00,000 VEST")["drop"], "QUOTE_NOT_IN_SOURCE")
        self.assertEqual(keep(t, "total_amount", "500", "500")["drop"], "QUOTE_NOT_IN_SOURCE")
        self.assertEqual(keep(t, "vesting_duration", "36 months", "36 months linear")["value"]["months"], 36)

    def test_cuts_token(self):
        t = "a 36 months, 5,000,000 x"
        self.assertTrue(C.cuts_token(t, t.find("6 m"), t.find("6 m") + 3))
        self.assertTrue(C.cuts_token(t, t.find("5,000"), t.find("5,000") + 5))
        self.assertFalse(C.cuts_token(t, t.find("36"), t.find("36") + 9))


# =============================================================================
# resisted
# =============================================================================

LABELS = """## Wallets

| Group | Vesting contract |
| --- | --- |
| Team | %s |
| Advisors | %s |

| Group | Cliff | Vesting |
| --- | --- | --- |
| Team | 12 months | 36 months |
| Advisors | 6 months | 24 months |
""" % (W1, W2)


class Resisted(unittest.TestCase):
    def test_other_groups_row(self):
        self.assertEqual(keep(LABELS, "cliff_duration", "6 months", "6 months")["drop"],
                         "SECTION_NAMES_ANOTHER_SUBJECT")
        self.assertEqual(keep(LABELS, "cliff_duration", "12 months", "12 months")["value"]["months"], 12)

    def test_lookalike_label_is_another_label(self):
        t = LABELS.replace("| Team | 12 months", "| Tеam | 12 months")      # Cyrillic e
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_label_in_another_section(self):
        t = LABELS.replace("\n| Group | Cliff", "\n## Elsewhere\n\n| Group | Cliff")
        self.assertEqual(keep(t, "cliff_duration", "12 months", "12 months")["drop"], "QUOTE_NOT_NEXT_TO_SUBJECT")

    def test_voting_table_end_is_not_a_vesting_end(self):
        t = "## Vote\n\n| Item | Start | End |\n| --- | --- | --- |\n| Team | 2025-01-01 | 2025-01-08 |\n\n" \
            "| Item | Contract |\n| --- | --- |\n| Team | " + W1 + " |\n"
        self.assertEqual(keep(t, "end_date", "2025-01-08", "2025-01-08")["drop"], "NO_RELEASE_WORD")

    def test_header_mixing_cliff_and_vesting(self):
        t = "| Group | Linear after cliff | Contract |\n|-|-|-|\n| Team | 24 months | " + W1 + " |\n"
        self.assertEqual(keep(t, "cliff_duration", "24 months", "24 months")["drop"], "HEADER_AMBIGUOUS")

    def test_source_defined_month_is_used_not_calendar(self):
        my = C.month_year_seconds(C._equals_sign("Note: 1 month = 31 days. Vesting over 12 months."))
        v = C.vesting_value("Vesting over 12 months.", *my)
        self.assertEqual((v["months"], v["seconds"]), (0, 372 * DAY))

    def test_leader_cannot_swap_months_for_days(self):
        text = "## Team\nWallet " + W1 + ": a 6-month cliff.\n"
        r = refs_vw(text)
        k = C.keep_fields({"fields": [{"field": "cliff_duration", "value": "6 months", "quote": "a 6-month cliff"}]},
                          text, r, MY)
        bad = [{"field": "cliff_duration", "value": {"seconds": 6 * MONTH, "months": 0}, "quote": "a 6-month cliff"}]
        self.assertTrue(C.recheck_kept(k["kept"], text, r, MY))
        self.assertFalse(C.recheck_kept(bad, text, r, MY))

    def test_one_sentence_with_two_dates_is_split_by_each_dates_own_words(self):
        q = "Nothing released until 6 October 2027, then released continuously until 6 October 2029"
        self.assertEqual(C.first_unlock_value(q), D(2027, 10, 6))
        self.assertEqual(C.end_value(q, False), D(2029, 10, 6))
        # the words of the first clause do not reach the second date
        q2 = "Locked until 2027-01-01 and 2028-01-01"
        self.assertEqual(C.first_unlock_value(q2), D(2027, 1, 1))
        self.assertIn("drop", C.end_value(q2, True))

    def test_id_word_does_not_hide_a_second_amount(self):
        self.assertEqual(C.amount_value("amount 500,000 or 600,000 VEST", *MY)["drop"], "SEVERAL_AMOUNTS_IN_QUOTE")


if __name__ == "__main__":
    unittest.main()

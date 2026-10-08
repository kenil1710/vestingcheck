"""v1.2.0: real-world vesting wording, markdown tables, calendar months,
date-written schedules, label-keyed tables, and the end of sender+recipient
binding. One test per wording the parser now reads (or now refuses).

    cd test && python3 -m unittest -q test_v120
"""
import unittest

import fixtures as F
import stub
from fixtures import C

DAY = F.DAY
MONTH = F.MONTH
YEAR = F.YEAR
MY = (C.MONTH_S, C.YEAR_S)
D = lambda y, m, d: C._days_from_civil(y, m, d) * DAY


# =============================================================================
# calendar months
# =============================================================================

class CalendarMonths(unittest.TestCase):
    def test_add_months(self):
        self.assertEqual(C.add_months(D(2025, 4, 30), 12), D(2026, 4, 30))
        self.assertEqual(C.add_months(D(2025, 1, 31), 1), D(2025, 2, 28))
        self.assertEqual(C.add_months(D(2024, 2, 29), 12), D(2025, 2, 28))
        self.assertEqual(C.add_months(D(2025, 11, 15) + 3600, 3), D(2026, 2, 15) + 3600)

    def test_months_and_years_counted_as_calendar_months(self):
        d = C.durations("12 months", *MY)[0]
        self.assertEqual((d[0], d[5]), (360 * DAY, 12))
        self.assertEqual(C.durations("1 year", *MY)[0][5], 12)
        self.assertEqual(C.durations("4-year", *MY)[0][5], 48)
        self.assertEqual(C.durations("1.5 years", *MY)[0][5], 0)
        self.assertEqual(C.durations("90 days", *MY)[0][5], 0)

    def test_source_defined_month_is_not_calendar(self):
        self.assertEqual(C.durations("12 months", 31 * DAY, YEAR)[0][5], 0)
        self.assertEqual(C.durations("12 months", 31 * DAY, YEAR)[0][0], 372 * DAY)

    def test_twelve_months_matches_a_365_day_stream(self):
        # EXAIP-23 shape: 2025-04-30 -> 2026-04-30 is 365 days; v1.1.0 read
        # "12 months" as 360 days and would have said UNLOCKS_LATER
        start = D(2025, 4, 30)
        f = {"decidable": True, "pattern": "SABLIER_LOCKUP_v1.0", "contract": F.LOCKUP, "symbol": "EXA",
             "decimals": 18, "total": str(30000 * 10 ** 18), "start": start, "end": start + 365 * DAY,
             "cliff_s": 0, "first_unlock": start, "beneficiary": F.RECIP, "cancelable": False,
             "unlocked_now": "0", "withdrawn": "0", "token": F.TOK}
        v = C.vesting_value("12 months linear vesting with Sablier.com", *MY)
        out = C.decide([{"field": "vesting_duration", "value": v, "quote": "q"}], f, False,
                       {"number": 1, "hash": "0x", "timestamp": F.FIN_TS})
        self.assertEqual(out["fields"]["vesting_duration"], "MATCHES")

    def test_model_value_one_year_equals_twelve_months(self):
        v = C.vesting_value("vesting over 1 year", *MY)
        self.assertTrue(C.model_value_ok("vesting_duration", "12 months", v, *MY))
        self.assertFalse(C.model_value_ok("vesting_duration", "360 days", v, *MY))
        c = C.cliff_value("a 6-month cliff", *MY)
        self.assertTrue(C.model_value_ok("cliff_duration", "6 months", c, *MY))
        self.assertFalse(C.model_value_ok("cliff_duration", "180 days", c, *MY))


# =============================================================================
# real-world wording
# =============================================================================

class Wording(unittest.TestCase):
    def test_cliff_then_linear(self):
        self.assertEqual(C.cliff_value("6-month cliff then linear over 18 months", *MY)["months"], 6)
        v = C.vesting_value("6-month cliff then linear over 18 months", *MY)
        self.assertEqual((v["months"], v["after_cliff"]), (18, True))

    def test_monthly_over(self):
        self.assertEqual(C.vesting_value("vests monthly over 24 months", *MY)["months"], 24)

    def test_vesting_with_a_cliff(self):
        self.assertEqual(C.vesting_value("4-year vesting with a 1-year cliff", *MY)["months"], 48)
        self.assertEqual(C.cliff_value("4-year vesting with a 1-year cliff", *MY)["months"], 12)

    def test_labelled_forms(self):
        self.assertEqual(C.cliff_value("Cliff: 12 months", *MY)["months"], 12)
        self.assertEqual(C.vesting_value("Vesting period: 24 months", *MY)["months"], 24)

    def test_tge_percent_is_not_an_amount_or_a_duration(self):
        self.assertEqual(C.amount_value("10% at TGE, then 500,000 tokens", *MY), "500000")
        self.assertEqual(C.vesting_value("10% at TGE, then monthly over 24 months", *MY)["months"], 24)
        self.assertEqual(C.start_value("starting at TGE")["drop"], "NO_DATE_IN_QUOTE")

    def test_stream_id_is_not_an_amount(self):
        q = '{ id: 1784, name: "Founders and team", amount: 150_000_000'
        self.assertEqual(C.amount_value(q, *MY), "150000000")
        self.assertEqual(C.amount_value("Stream 12 holds 500,000 VEST", *MY), "500000")
        self.assertEqual(C.amount_value("tokenId 7: 500,000 VEST", *MY), "500000")
        self.assertEqual(C.amount_value("streamId=7, 500,000 VEST", *MY), "500000")

    def test_stream_colon_amount_is_still_an_amount(self):
        self.assertEqual(C.amount_value("Stream: 500,000 VEST", *MY), "500000")


class FirstUnlockDate(unittest.TestCase):
    def test_forms(self):
        oct6 = D(2027, 10, 6)
        for q in ("Nothing released until 6 October 2027", "locked until 2027-10-06",
                  "the cliff ends on October 6, 2027", "Cliff: 2027-10-06", "first unlock on 6 October 2027",
                  "No tokens unlock before 2027-10-06", "nothing released until 6 October 2027, then released "
                  "continuously"):
            self.assertEqual(C.first_unlock_value(q), oct6, q)

    def test_drops(self):
        self.assertEqual(C.first_unlock_value("then released continuously until 6 October 2029")["drop"],
                         "DATE_MAY_BE_A_LATER_PHASE")
        self.assertEqual(C.first_unlock_value("nothing at first, then released until 2029-10-06")["drop"],
                         "DATE_MAY_BE_A_LATER_PHASE")
        self.assertEqual(C.first_unlock_value("a 1-year cliff from 2025-01-01")["drop"], "DATE_MAY_BE_A_START")
        self.assertEqual(C.first_unlock_value("until 6 October 2027")["drop"], "NO_FIRST_UNLOCK_WORDS")
        self.assertEqual(C.first_unlock_value("locked from 2026-10-06 until 2027-10-06")["drop"],
                         "SEVERAL_DATES_IN_QUOTE")
        self.assertEqual(C.first_unlock_value("nothing released until 6 October")["drop"], "DATE_WITHOUT_YEAR")


class EndDate(unittest.TestCase):
    def test_forms(self):
        for q, d in (("then released continuously until 6 October 2029", D(2029, 10, 6)),
                     ("fully vested by 2028-01-01", D(2028, 1, 1)),
                     ("Timelock: released in full on 6 October 2027", D(2027, 10, 6)),
                     ("vesting ends on January 1st, 2029", D(2029, 1, 1)),
                     ("streamed through 2026-12-31", D(2026, 12, 31))):
            self.assertEqual(C.end_value(q, False), d, q)

    def test_drops(self):
        self.assertEqual(C.end_value("Nothing released until 6 October 2027", False)["drop"],
                         "DATE_MAY_BE_A_FIRST_UNLOCK")
        self.assertEqual(C.end_value("locked until 2027-10-06", False)["drop"], "DATE_MAY_BE_A_FIRST_UNLOCK")
        self.assertEqual(C.end_value("the cliff ends on 2026-04-05", False)["drop"], "DATE_MAY_BE_A_FIRST_UNLOCK")
        self.assertEqual(C.end_value("vesting from 2025-01-01 onward", False)["drop"], "DATE_MAY_BE_A_START")
        self.assertEqual(C.end_value("until 6 October 2029", False)["drop"], "NO_RELEASE_WORD")
        self.assertEqual(C.end_value("until 6 October 2029", True), D(2029, 10, 6))
        self.assertEqual(C.end_value("released on 2029-10-06", False)["drop"], "NO_END_WORD")

    def test_start_still_refuses_an_until_date(self):
        self.assertEqual(C.start_value("Nothing released until 6 October 2027")["drop"], "NO_START_WORD")


# =============================================================================
# markdown tables
# =============================================================================

TABLE = """## Vesting

| Group | Amount | Share | Cliff | Vesting | Months |
|-------|--------|-------|-------|---------|--------|
| Team  | 124,200,000 | 20% | 12 months | 24 months | 36 |
"""

GFM = """## Vesting Schedule
Beneficiary  | Amount |  Distributed at TGE  | Cliff  | Vesting
-|-|-|-|-
Private Sale  |  200,000,000 |  10.0%  |3 months  | 12 months
Team & Advisors | 220,000,000 | - | 12 months | 12 months
"""

UNITS = """| Group | Cliff (months) | Vesting (months) | Linear after cliff |
|---|---|---|---|
| Team | 12 | 36 | 24 months |
"""

DATES = """| Modality | Start | Cliff | End |
| --- | --- | --- | --- |
| Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z |
"""


def cell_value(text, field, quote, nth=0):
    i = -1
    for _ in range(nth + 1):
        i = text.find(quote, i + 1)
    ctx = C.table_context(text, i, i + len(quote))
    return C.claim_value(field, quote, C.MONTH_S, C.YEAR_S, None, ctx)


class Tables(unittest.TestCase):
    def test_cells_read_with_their_header(self):
        self.assertEqual(cell_value(TABLE, "cliff_duration", "12 months")["months"], 12)
        self.assertEqual(cell_value(TABLE, "vesting_duration", "24 months")["months"], 24)
        self.assertEqual(cell_value(TABLE, "total_amount", "124,200,000"), "124200000")

    def test_header_unit_for_bare_numbers(self):
        self.assertEqual(cell_value(UNITS, "cliff_duration", "12")["months"], 12)
        self.assertEqual(cell_value(UNITS, "vesting_duration", "36")["months"], 36)

    def test_header_that_mixes_cliff_and_vesting_is_refused(self):
        self.assertEqual(cell_value(UNITS, "vesting_duration", "24 months")["drop"], "HEADER_AMBIGUOUS")
        self.assertEqual(cell_value(UNITS, "cliff_duration", "24 months")["drop"], "HEADER_AMBIGUOUS")

    def test_percent_and_month_columns_are_not_amounts(self):
        self.assertEqual(cell_value(TABLE, "total_amount", "20%")["drop"], "NOT_AN_AMOUNT_COLUMN")
        self.assertEqual(cell_value(TABLE, "total_amount", "36")["drop"], "NOT_AN_AMOUNT_COLUMN")

    def test_cell_under_the_wrong_header(self):
        self.assertEqual(cell_value(TABLE, "cliff_duration", "24 months")["drop"], "NO_CLIFF_WORD")

    def test_tables_without_outer_pipes(self):
        self.assertEqual(cell_value(GFM, "cliff_duration", "3 months")["months"], 3)
        self.assertEqual(cell_value(GFM, "vesting_duration", "12 months")["months"], 12)
        self.assertEqual(cell_value(GFM, "total_amount", "220,000,000"), "220000000")

    def test_date_columns(self):
        self.assertEqual(cell_value(DATES, "start_date", "2026-03-05T00:00:00Z"), D(2026, 3, 5))
        self.assertEqual(cell_value(DATES, "first_unlock_date", "2026-04-05T00:00:00Z"), D(2026, 4, 5))
        self.assertEqual(cell_value(DATES, "end_date", "2031-02-05T00:00:00Z"), D(2031, 2, 5))

    def test_date_under_another_dates_header(self):
        self.assertEqual(cell_value(DATES, "start_date", "2031-02-05T00:00:00Z")["drop"],
                         "HEADER_NAMES_ANOTHER_DATE")
        self.assertEqual(cell_value(DATES, "end_date", "2026-04-05T00:00:00Z")["drop"],
                         "HEADER_NAMES_ANOTHER_DATE")

    def test_whole_row_quote_takes_the_cell_under_the_fields_header(self):
        row = "Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z"
        self.assertEqual(cell_value(DATES, "start_date", row), D(2026, 3, 5))
        self.assertEqual(cell_value(DATES, "first_unlock_date", row), D(2026, 4, 5))
        self.assertEqual(cell_value(DATES, "end_date", row), D(2031, 2, 5))
        row2 = "Team  | 124,200,000 | 20% | 12 months | 24 months | 36"
        self.assertEqual(cell_value(TABLE, "cliff_duration", row2)["months"], 12)
        self.assertEqual(cell_value(TABLE, "total_amount", row2), "124200000")

    def test_row_with_two_cells_claiming_a_field(self):
        t = "| Name | Start | Start (TGE) |\n|-|-|-|\n| Team | 2025-01-01 | 2025-02-01 |\n"
        self.assertEqual(cell_value(t, "start_date", "Team | 2025-01-01 | 2025-02-01")["drop"],
                         "SEVERAL_CELLS_FOR_FIELD")

    def test_header_and_delimiter_rows_are_not_cells(self):
        self.assertIsNone(C.table_context(DATES, DATES.find("Start"), DATES.find("Start") + 5))
        self.assertIsNone(C.table_at(DATES, DATES.find("---")))

    def test_pipe_text_outside_a_table(self):
        t = "a | b\nno delimiter here\n"
        self.assertIsNone(C.table_at(t, 0))


# =============================================================================
# TABLE_LABEL binding and vesting tables
# =============================================================================

W1 = F.addr(0x6A55)
W2 = F.addr(0x03ED)
BEN = F.addr(0xD525)

LABELS = """# Distribution

## Modalities

| Modality | Start | Cliff | End |
| --- | --- | --- | --- |
| Staking | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2028-02-05T00:00:00Z |
| Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z |

The beneficiary for all of those is %s.

| Modality | Vesting contract address |
| --- | --- |
| Staking | [%s](https://arbiscan.io/address/%s) |
| Treasury | [%s](https://arbiscan.io/address/%s) |

## Older plan

| Modality | Start | Cliff | End |
| --- | --- | --- | --- |
| Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-01-05T00:00:00Z |
""" % (BEN, W2, W2, W1, W1)


def refs_vw(text, wallet=W1):
    tg = C.parse_target("arbitrum", wallet, F.TOK)
    return C.subject_refs(text, text.lower(), "arbitrum", tg, {"beneficiary": BEN, "token": F.TOK}, 0)


def keep(text, field, value, quote, wallet=W1):
    r = refs_vw(text, wallet)
    return C.keep_field({"field": field, "value": value, "quote": quote}, text, r, MY)


class TableLabel(unittest.TestCase):
    def test_label_row_in_the_same_section_is_bound(self):
        r = refs_vw(LABELS)
        kinds = [a[2] for a in r["anchors"]]
        self.assertEqual(kinds.count("TABLE_LABEL"), 1)
        self.assertEqual(kinds.count("ADDRESS"), 2)
        self.assertEqual(keep(LABELS, "end_date", "2031-02-05", "2031-02-05T00:00:00Z")["value"], D(2031, 2, 5))

    def test_other_wallets_row_is_not_bound(self):
        self.assertEqual(keep(LABELS, "end_date", "2028-02-05", "2028-02-05T00:00:00Z")["drop"],
                         "SECTION_NAMES_ANOTHER_SUBJECT")
        self.assertEqual(keep(LABELS, "end_date", "2028-02-05", "2028-02-05T00:00:00Z", wallet=W2)["value"],
                         D(2028, 2, 5))

    def test_same_label_in_another_section_is_not_bound(self):
        self.assertEqual(keep(LABELS, "end_date", "2031-01-05", "2031-01-05T00:00:00Z")["drop"],
                         "QUOTE_NOT_NEXT_TO_SUBJECT")

    def test_addresses_in_a_vesting_table_are_other_subjects(self):
        r = refs_vw(LABELS)
        self.assertIn(W2, [LABELS.lower()[o[0]:o[1]] for o in r["others"]])

    def test_duplicate_label_in_the_address_table_binds_nothing(self):
        t = LABELS.replace("| Staking | [", "| Treasury | [")
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_duplicate_label_in_the_schedule_table_binds_nothing(self):
        t = LABELS.replace("| Staking | 2026", "| Treasury | 2026")
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_label_row_that_names_an_address_binds_nothing(self):
        t = LABELS.replace("| Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z |",
                           "| Treasury | " + F.addr(0x9999) + " | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z |")
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_label_used_by_two_subject_tables_binds_nothing(self):
        t = LABELS.replace("The beneficiary for all of those",
                           "| Modality | Base address |\n| --- | --- |\n| Treasury | " + F.addr(0x7777) +
                           " |\n\nThe beneficiary for all of those")
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_numeric_label_binds_nothing(self):
        t = LABELS.replace("| Treasury |", "| 2 |")
        self.assertNotIn("TABLE_LABEL", [a[2] for a in refs_vw(t)["anchors"]])

    def test_end_to_end_vesting_wallet_with_label_tables(self):
        mc = F.fresh_world(docs=LABELS, chain="arbitrum")
        start = D(2026, 3, 5)
        F.vesting_wallet(mc, wallet=W1, beneficiary=BEN, start=start, duration=D(2031, 2, 5) - start,
                         cliff=D(2026, 4, 5))
        stub.MODEL.answer = F.fields(
            ("start_date", "2026-03-05", "Treasury | 2026-03-05T00:00:00Z | 2026-04-05T00:00:00Z | 2031-02-05T00:00:00Z"),
            ("first_unlock_date", "2026-04-05", "2026-04-05T00:00:00Z"),
            ("end_date", "2031-02-05", "2031-02-05T00:00:00Z"),
            ("beneficiary", BEN, "The beneficiary for all of those is " + BEN))
        o = F.file(F.new_contract(), chain="arbitrum", contract=W1, extra=F.TOK)
        self.assertTrue(o.ok, o)
        self.assertEqual(o.value["verdict"], "MATCHES")
        self.assertIn("3 of 3 fields decided", o.value["summary"])

    def test_end_to_end_end_date_later_on_chain(self):
        mc = F.fresh_world(docs=LABELS, chain="arbitrum")
        start = D(2026, 3, 5)
        F.vesting_wallet(mc, wallet=W1, beneficiary=BEN, start=start, duration=D(2032, 2, 5) - start,
                         cliff=D(2026, 4, 5))
        stub.MODEL.answer = F.fields(("end_date", "2031-02-05", "2031-02-05T00:00:00Z"))
        o = F.file(F.new_contract(), chain="arbitrum", contract=W1, extra=F.TOK)
        self.assertEqual(o.value["verdict"], "UNLOCKS_LATER")


# =============================================================================
# date-written schedules end to end (a Sablier stream named by its id)
# =============================================================================

SITE = """// Sablier Lockup contract holding the vesting streams below.
export const sablierLockup = "%s";
// Public, non-cancelable Sablier vesting streams.
export const LOCKS = [
  { id: 41, name: "Ecosystem", amount: 350_000_000, schedule: "Nothing released until 6 April 2027, then released continuously until 6 October 2029" },
  { id: 42, name: "Founders and team", amount: 150_000_000, schedule: "Nothing released until 6 October 2027, then released continuously until 6 October 2029" },
];
""" % F.LOCKUP


class DateSchedules(unittest.TestCase):
    def setUp(self):
        self.mc = F.fresh_world(docs=SITE)

    def answer(self):
        return F.fields(
            ("total_amount", "150,000,000", '{ id: 42, name: "Founders and team", amount: 150_000_000'),
            ("first_unlock_date", "2027-10-06", "Nothing released until 6 October 2027"),
            ("end_date", "2029-10-06", "then released continuously until 6 October 2029"))

    def test_matches(self):
        F.sablier_stream(self.mc, start=D(2027, 10, 6) - 3600, cliff=None, end=D(2029, 10, 6) - 3600,
                         deposited=150_000_000 * 10 ** 18)
        stub.MODEL.answer = self.answer()
        o = F.file(F.new_contract())
        self.assertTrue(o.ok, o)
        self.assertEqual(o.value["verdict"], "MATCHES")
        self.assertIn("state 2029-10-06", o.value["summary"])

    def test_earlier_first_unlock(self):
        F.sablier_stream(self.mc, start=D(2027, 4, 6), cliff=None, end=D(2029, 10, 6),
                         deposited=150_000_000 * 10 ** 18)
        stub.MODEL.answer = self.answer()
        o = F.file(F.new_contract())
        self.assertEqual(o.value["verdict"], "UNLOCKS_EARLIER")

    def test_the_other_streams_dates_are_not_bound(self):
        F.sablier_stream(self.mc, start=D(2027, 10, 6), cliff=None, end=D(2029, 10, 6),
                         deposited=150_000_000 * 10 ** 18)
        stub.MODEL.answer = F.fields(("first_unlock_date", "2027-04-06", "Nothing released until 6 April 2027"))
        o = F.file(F.new_contract())
        self.assertEqual(o.value["basis"], "NO_FIELD_KEPT")

    def test_comment_line_for_every_stream_is_not_bound(self):
        F.sablier_stream(self.mc, start=D(2027, 10, 6), cliff=None, end=D(2029, 10, 6),
                         deposited=150_000_000 * 10 ** 18)
        stub.MODEL.answer = F.fields(("irrevocable", True, "Public, non-cancelable Sablier vesting streams."))
        o = F.file(F.new_contract())
        self.assertEqual(o.value["basis"], "NO_FIELD_KEPT")


class DecideNewFields(unittest.TestCase):
    def facts(self, **kw):
        f = {"decidable": True, "pattern": "SABLIER_LOCKUP_v1.1", "contract": F.LOCKUP, "symbol": "VEST",
             "decimals": 18, "total": str(F.TOTAL), "start": F.START, "end": C.add_months(F.START, 36),
             "cliff_s": C.add_months(F.START, 12) - F.START, "first_unlock": C.add_months(F.START, 12),
             "beneficiary": F.RECIP, "cancelable": False, "unlocked_now": "0", "withdrawn": "0", "token": F.TOK}
        f.update(kw)
        return f

    def d(self, kept, f=None):
        k = [{"field": a, "value": b, "quote": "q"} for (a, b) in kept]
        return C.decide(k, f or self.facts(), False, {"number": 1, "hash": "0x", "timestamp": F.FIN_TS})

    def test_first_unlock_and_end(self):
        out = self.d([("first_unlock_date", C.add_months(F.START, 12)), ("end_date", C.add_months(F.START, 36))])
        self.assertEqual(out["fields"], {"first_unlock_date": "MATCHES", "end_date": "MATCHES"})
        out = self.d([("first_unlock_date", C.add_months(F.START, 13))])
        self.assertEqual(out["verdict"], "UNLOCKS_EARLIER")
        out = self.d([("end_date", C.add_months(F.START, 30))])
        self.assertEqual(out["verdict"], "UNLOCKS_LATER")

    def test_dynamic_first_unlock_unverifiable(self):
        out = self.d([("first_unlock_date", F.START)], self.facts(first_unlock=-1, cliff_s=-1))
        self.assertEqual(out["why"]["first_unlock_date"], "SHAPE_HAS_NO_CLIFF_CODE_CAN_READ")

    def test_end_date_readings(self):
        fu = C.add_months(F.START, 12)
        end = C.add_months(F.START, 36)
        out = self.d([("first_unlock_date", fu), ("end_date", end)])
        r = {x["name"]: (x["linear_from"], x["end"]) for x in out["schedule"]["readings"]}
        self.assertEqual(r, {"A": (F.START, end), "B": (fu, end)})
        self.assertEqual(out["schedule"]["first"], fu)


class RecheckNewValues(unittest.TestCase):
    def test_leader_kept_values_survive_the_validators_recheck(self):
        text = "## Team\nStream " + F.SAB_LINK + "\n12-month cliff, then linear over 4 years. " \
               "Nothing released until 2026-01-01. Fully vested by 2029-01-01.\n"
        tg = C.parse_target("ethereum", F.LOCKUP, str(F.SID))
        refs = C.subject_refs(text, text.lower(), "ethereum", tg, {}, 0)
        k = C.keep_fields({"fields": [
            {"field": "cliff_duration", "value": "12 months", "quote": "12-month cliff"},
            {"field": "vesting_duration", "value": "4 years", "quote": "then linear over 4 years"},
            {"field": "first_unlock_date", "value": "2026-01-01", "quote": "Nothing released until 2026-01-01"},
            {"field": "end_date", "value": "2029-01-01", "quote": "Fully vested by 2029-01-01"}]}, text, refs, MY)
        self.assertEqual(len(k["kept"]), 4)
        self.assertTrue(C.recheck_kept(k["kept"], text, refs, MY))
        bad = [dict(x) for x in k["kept"]]
        bad[1]["value"] = {"seconds": 4 * YEAR, "months": 0, "after_cliff": True}
        self.assertFalse(C.recheck_kept(bad, text, refs, MY))


if __name__ == "__main__":
    unittest.main()

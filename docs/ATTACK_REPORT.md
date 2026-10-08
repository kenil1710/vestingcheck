# Attack report

Two attacker passes. Each attack is a test; a finding is a test that failed on the code it attacked and passes after the fix. Run them with `cd test && python3 -m unittest test_attacks test_attacks_r2`.

## Round 1: v1.0.0 (whole contract)

34 attack tests against v1.0.0, 9 failing ([raw run](research/attacks_v1.0.0.txt)). Fixed in v1.1.0 (commit `14990d7`).

| # | Severity | Finding | Fix |
|---|---|---|---|
| H1 | High | **Decoy stream by recipient.** A stream was bound to a proposal that named its recipient. Anyone can open a stream to any address, so a 1-token stream to a grant recipient, filed against the DAO's proposal, read LESS_THAN_CLAIMED / UNLOCKS_EARLIER. | The recipient alone no longer binds (v1.1.0 required sender + recipient; round 2 removed that too, see R2-H1). |
| H2 | High | **Same-symbol fake token.** A VestingWallet holds any token sent to it and the filer picks the token; a fake token with the claimed symbol, sent in bulk, read MORE_THAN_CLAIMED. | A wallet's token binds only by its address in the source; a stream's token is the stream's own. |
| M1 | Medium | "a year and a half" was read as one year. | Fraction words make the duration unreadable (dropped). |
| M2 | Medium | Any "id N" anywhere in a source naming the lockup bound stream N ("Proposal id 7"). | An id binds only in a section that names the lockup address and a stream / Sablier. |
| M3 | Medium | A wallet with a `fallback()` that answers any call passed recognition. | An unknown selector must revert. |
| M4 | Medium | The proposal date came from the author-signed timestamp. | The Snapshot hub's `created` is used. |

Resisted in round 1 (18 tests): fork commits, branches / tags instead of a sha, lying IPFS gateways, self-pinned proposals not on the hub, subject not in the source, altered quoted values, unit tricks ("12m"), wrong section, look-alike lockups, canceled streams, inconsistent stream values, an old leader block, duplicate filings in another spelling, the cooldown boundary, history overflow, writes before a revert, accusing wording, prompt injection.

## Round 2: v1.2.x (new code only)

Scope: what v1.2.0 added (calendar months, `first_unlock_date` / `end_date`, markdown table cells read with their headers, whole-row quotes, `TABLE_LABEL` binding, vesting-table "other subjects") and the H1 re-check. 27 tests in [test/test_attacks_r2.py](../test/test_attacks_r2.py).

How it ran: the attacks R2-M1 to R2-M4 were written as tests first and run against the uncommitted v1.2.0 draft: 21 tests, 9 failing ([raw run](research/attacks_r2_first_run.txt)); then fixed. Three findings came from outside that pass and were fixed first, with their test added afterwards: R2-H1 (from the H1 re-check of the Exactly proposals), R2-H2 (from verifying the v1.1.0 seed run by hand) and R2-M5 (exposed by one of the pass's own fixtures; the matcher dates from v1.0).

| # | Severity | Finding | Fix |
|---|---|---|---|
| R2-H1 | High | **Decoy stream "from" the treasury.** Sablier's create functions take `sender` as a parameter, so whoever pays can name the DAO treasury as sender. v1.1.0 bound a stream when the source named its sender and recipient; binding by the Snapshot space's registered treasury (proposed for the Exactly proposals) has the same hole. The funder cannot be checked: its creation transaction is out of reach of the RPCs' `eth_getLogs` limits (docs/RESEARCH.md). | Sender and recipient never bind. A stream must be named by its link or id. |
| R2-H2 | High | **A link to the vesting contract read as its beneficiary.** nation3 N3GOV-44 only links "[vesting contract](…/address/&lt;wallet&gt;)"; the model labelled it the beneficiary and v1.1.0 recorded BENEFICIARY_DIFFERS (wallet address vs its owner). A false finding on the v1.1.0 canonical deployment. | A beneficiary is never the subject or its token, and the quote or its column header must use a recipient word. |
| R2-M1 | Medium | **Stale label row.** `TABLE_LABEL` bound every row with the subject's label in the section; a current table and a superseded one under a child heading were both bound, and a quote from the stale row was kept. | A value from a subject's table row is dropped when another of its rows, under a header naming the same field, says something else. |
| R2-M2 | Medium | **Date that anchors a relative phrase.** "the cliff ends 12 months after TGE on 2025-01-01" read 2025-01-01 as the first unlock. | A duration, "after" or "TGE" before the date drops it. |
| R2-M3 | Medium | **End word far from the date.** "Grant approved by the DAO on 2025-03-01, fully vesting" read the vote date as the end. | The end / first-unlock word must be one of the last three words before the date. |
| R2-M4 | Medium | **Number in a non-amount column.** A "Price" cell, or a whole row with no amount column, was read as the amount. | In a table an amount is read only from a column named Amount / Tokens / Allocation / Total / Quantity. |
| R2-M5 | Medium | **Quote cut out of a longer number.** "6 months" matched inside "36 months" and "00,000 VEST" inside "500,000 VEST". | A quote may not start or end inside a word or a number. |

Resisted in round 2 (9 tests): another group's row in a label-keyed table, a Cyrillic look-alike label, the same label in another section, a voting table's "End" column, a header mixing cliff and vesting, a source-defined month (not calendar), a leader swapping months for days, two dates in one sentence (each is read by its own words), an id word hiding a second amount.

After round 2, live probing showed the model quoting date-written schedules in several lengths ("until 6 October 2029" / "released continuously until 6 October 2029" / the whole sentence with both dates); v1.2.0 kept some and not others, and the first CrossLedger filing on v1.2.0 was refused as `EXTRACTION_UNSTABLE`. v1.2.1 reads each date by the source words in front of it (back to the previous date, ". " or ";"), so every length gives the same value; the rules above are unchanged (test_v120.ClauseBefore, test_attacks_r2.Resisted.test_one_sentence_with_two_dates_is_split_by_each_dates_own_words).

## Status

All findings fixed; `python3 -m unittest` in `test/` runs the attack tests with the rest of the suite (docs/FINAL_CHECK.md, item 16).

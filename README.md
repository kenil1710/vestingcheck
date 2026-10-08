# VestingCheck

**Token projects and DAOs write down how tokens vest: "team: 12-month cliff, then linear over 36 months", "nothing released until 6 October 2027", "non-cancelable". VestingCheck is a GenLayer Intelligent Contract that checks those statements against the vesting contract that actually holds the tokens, and records, with dates, whether the chain matches, unlocks earlier or later, holds more or less, can be canceled, or pays someone else.**

* Contract: [`contracts/VestingCheck.py`](contracts/VestingCheck.py) (one file, GenVM `py-genlayer:5jycge4q...`, v1.2.1)
* Deployed on GenLayer Studio Dev: canonical [`0xD225b3E0D98b2F90a7a7da97C61A920465a3022E`](https://explorer-studio-dev.genlayer.com/address/0xD225b3E0D98b2F90a7a7da97C61A920465a3022E), demo [`0x884De4ce7bb1890A201533747d7C21B3Ee8F308d`](https://explorer-studio-dev.genlayer.com/address/0x884De4ce7bb1890A201533747d7C21B3Ee8F308d) ([ADDRESSES.md](ADDRESSES.md))
* Real seeds: [docs/SEEDS.md](docs/SEEDS.md) · research: [docs/RESEARCH.md](docs/RESEARCH.md) · threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) · attacker passes: [docs/ATTACK_REPORT.md](docs/ATTACK_REPORT.md) · final check: [docs/FINAL_CHECK.md](docs/FINAL_CHECK.md) · submission text: [docs/SUBMISSION.md](docs/SUBMISSION.md)

## The problem

Vesting terms are published as prose: a governance proposal, a tokenomics page, a README table. The tokens sit in a contract (a Sablier stream, an OpenZeppelin VestingWallet) whose real schedule anyone can read, but nobody compares the two. Streams get created with a shorter cliff, a different amount, as cancelable, or to a different wallet, and docs go stale. VestingCheck makes that comparison a public, dated record that validators agree on.

## How it works

A filer calls `file_check(source, branch, chain, contract, stream_or_token)`:

* `source`: a GitHub file **pinned to a commit** (`https://raw.githubusercontent.com/<owner>/<repo>/<40-hex sha>/<path>` or the `github.com/.../blob/<sha>/...` form), or a **Snapshot proposal** by its IPFS CID (`ipfs://<cid>` or the bare CID).
* `branch`: GitHub only, optional (empty = the repo's default branch).
* `chain`: `ethereum`, `arbitrum`, `optimism`, `base` or `polygon`.
* `contract` + `stream_or_token`: a Sablier Lockup deployment and the stream id, or an OpenZeppelin VestingWallet and the token it vests.

Then every validator, on its own:

1. **Proves the source.** GitHub: the GitHub compare API must show the commit on a branch of the repo in the URL (`behind` or `identical`; a fork-only commit answers `diverged`). Snapshot: the proposal bytes are fetched from allowlisted IPFS gateways, hashed **in code** and required to equal the CID; the Snapshot hub must list that CID with the same space and author; the hub's creation time is the proposal date.
2. **Checks the source names the subject.** A Sablier stream is named by a Sablier app link to it (`app.sablier.com/.../stream/LK3-1-1784`), by `<lockup>-<chainId>-<id>` or `<lockup>/<id>`, or by its id next to the lockup address in a section about a stream. A VestingWallet is named by its address. A stream is **never** identified by its sender or recipient: Sablier lets whoever creates a stream write any address as its sender, so a decoy stream "from" a DAO treasury is cheap (round 2, R2-H1). In a markdown table, a row is also bound when its first cell is the same label as the subject's own row in another table of the same section (`TABLE_LABEL`, e.g. a "Treasury" schedule row and a "Treasury" address row). If the subject is not named, the filing is refused.
3. **Reads the vesting contract at one finalized block** the leader names (no older than 1 h canonical / 30 min demo). Standard patterns only:
   * Sablier Lockup v1.0 to v4.0, from an allowlist of official deployments per chain (linear, dynamic, tranched; the shape is read per stream on v2.0+). Recipient, sender, token, deposit, withdrawn, refunded, start, cliff, end, cancelable, canceled, streamed amount, tranches.
   * OpenZeppelin VestingWallet / VestingWalletCliff, recognised only if its whole function table is OpenZeppelin's, it has no DELEGATECALL / SELFDESTRUCT, is not a proxy or clone, answers no unknown function, and `vestedAmount` equals OpenZeppelin's curve at five times.
   * Anything else (custom vesting, a canceled stream, legacy Sablier v1.1) is read but marked not decidable.
4. **Lets the model point at passages, and code reads them.** The model returns `{field, value, quote}` for nine fields: `total_amount`, `token_symbol`, `cliff_duration`, `vesting_duration`, `start_date`, `first_unlock_date`, `end_date`, `beneficiary`, `irrevocable`. Code keeps a field only if:
   * the quote is verbatim source text, made of whole words and numbers (markdown `*` and backticks may be dropped; "6 months" cut out of "36 months" is refused),
   * it is bound to the subject: on a line naming it (and nearest to it), or in a section that names it and no other vesting subject,
   * code itself reads the value out of the quote, and the model's own value says the same thing (otherwise the field is dropped).
5. **Agrees.** Validators accept the leader's record only if every non-model part is byte-identical to their own (source bytes, proof, block, every chain read) and the kept fields pass code's rules again and equal one of their own two extractions. The leader asks up to three times and needs two answers with the same kept fields.

Then **code** compares each kept field with the chain and writes an immutable record.

### What code reads out of a quote

| Field | Accepted wording (examples) | Refused |
|---|---|---|
| amount | "500,000", "17_450_000", "1.5 million", "0.5M", "52,000 EXA"; in a table only from a column named Amount / Tokens / Allocation / Total | two different amounts, a number before `%` or a time unit, a year, a date part, a stream id ("id: 1784", "Stream 12"), a Price or % column |
| cliff | "12-month cliff", "a one year cliff", "cliff of 6 months", "Cliff: 90 days", "no cliff"; a table cell under a "Cliff" header ("Cliff (months)" + "12") | no "cliff" word, two cliffs, "12m" (minutes or months?), "a year and a half", a header mixing cliff and vesting |
| vesting | "linear over 36 months", "4-year vesting", "then linear over 24 months", "vests monthly over 24 months", "Vesting period: 24 months"; a cell under a Vesting / Duration header | no vesting word, two durations, fractions in words |
| start | "starting 2025-01-01", "vesting begins January 1st, 2025", a cell under a "Start" header | "until" / "by" dates, dates without a year |
| first unlock | "Nothing released until 6 October 2027", "locked until 2027-10-06", "the cliff ends on …", "first unlock on …", a cell under a "Cliff" header holding a date | a later phase ("then … until"), a start ("from"), a date counted from something ("12 months after TGE on …"), deciding words not right before the date |
| end | "released continuously until 6 October 2029", "fully vested by 2028-01-01", "released in full on 6 October 2027", a cell under an "End" header of a vesting table | "nothing / locked / cliff … until" (that is a first unlock), a start, "approved by the DAO on …" (end word not right before the date) |
| beneficiary | exactly one address, with a recipient word in the quote or its column header ("Beneficiary:", "Wallet Address:", "to") | the subject contract or its token, two addresses, no recipient word |
| irrevocable | "non-cancelable", "irrevocable", "cannot be canceled", "locked" | the same quote also says cancelable / revocable / unlocked |
| token symbol | the symbol stands alone in the quote ("CLXT", "$EXA") | |

Months and years are **calendar months** counted from the start ("12 months" from 2025-04-30 ends 2026-04-30), unless the source defines its own month or year ("1 month = 30 days"). Every date is 00:00 UTC. A whole table row may be quoted: code takes the one cell whose column header names the field.

## Verdicts

| Verdict | Meaning (per field; the record's verdict is the most important decided one) |
|---|---|
| `UNLOCKS_EARLIER` | the chain unlocks earlier than stated: shorter cliff, earlier first unlock, earlier start, shorter vesting, earlier end, or a stated cliff the chain does not have |
| `MORE_THAN_CLAIMED` | the stream / wallet holds more tokens than stated (more than 0.5 % above) |
| `CANCELABLE_NOT_DISCLOSED` | the source says locked / non-cancelable, the stream can still be canceled and has not ended |
| `BENEFICIARY_DIFFERS` | the chain pays a different address than the one stated |
| `LESS_THAN_CLAIMED` | it holds fewer tokens than stated (more than 0.5 % below) |
| `UNLOCKS_LATER` | the chain unlocks later than stated |
| `MATCHES` | every decided field agrees (dates and durations within 2 days, amounts within 0.5 %) |
| `UNVERIFIABLE` | nothing could be decided: no field was kept, the subject is not a standard pattern, or the stream was canceled |

Ranking: UNLOCKS_EARLIER > MORE_THAN_CLAIMED > CANCELABLE_NOT_DISCLOSED > BENEFICIARY_DIFFERS > LESS_THAN_CLAIMED > UNLOCKS_LATER > MATCHES. An amount only counts when the token is bound: for a stream, its own token's symbol must be stated; for a VestingWallet (which holds whatever anyone sends it), the token's address must be in the source. When a vesting duration is followed by "then / after", code also tries it counted from the end of the cliff and accepts either reading; a chain value between the two readings stays undecided.

Every record carries one sentence built by code, always dated and neutral:

> At block 26147000 (2026-10-08 10:11 UTC) the contract allows 100,000,000 CLXT to unlock by 2027-10-06; the docs (2026-10-06) state 2027-10-06. 2 of 2 fields decided: MATCHES.

It never says a project lied or is unsafe: docs go stale, and the record shows both dates. Every record also stores the unlock math at the block: what the chain lets unlock now and what the stated schedule would allow.

## What code decides

The source allowlist and the commit / CID proof; whether the source names the subject; which block is acceptable (finality, freshness, leader lag); every chain read and its decoding; whether the subject is a standard pattern; every number, date and duration, read from the quote; whether a quote is verbatim, whole-word and bound to the subject; every comparison and tolerance; the unlock math; the verdict; the sentence; cooldowns, duplicates and the history.

## What the model is never allowed to decide

* **Any value.** Amounts, durations, dates and addresses are parsed by code from the verbatim quote. A different model value drops the field.
* **Whether a quote is real.** Code finds it in the fetched source, character for character, whole words only.
* **Which subject a passage is about.** Code requires the passage to be on a line naming the subject or in a section naming it and no other vesting subject (or a label-matched table row); a link to the vesting contract is never a beneficiary.
* **Anything about the chain.** The model never sees chain data.
* **The verdict, the comparison, the tolerance or the wording.**
* **Whether a source, commit, CID, block or subject is acceptable.**

The model's only job is to point at passages and say which of nine fields each is about. The source is fenced with a per-filing nonce; whatever an injected instruction makes the model say, the value still comes from verbatim, bound source text.

## Evidence rules

* Allowlist: the pinned raw GitHub file and the GitHub compare API, four IPFS gateways, the Snapshot hub GraphQL, and one frozen RPC per chain ([docs/RESEARCH.md](docs/RESEARCH.md)). No branches, tags, query strings or `%`-escapes in URLs.
* One finalized block per record, named by the leader, read by all; number, hash and time are stored.
* Strict equality on the whole evidence; any mismatch stores nothing (there is no pending state to get stuck).
* No payable method, no balance, no owner, no setter. Cooldown and freshness are constructor arguments, frozen.
* Records are immutable. `recheck(record_id)` files again with the same inputs and links to the previous record. Cooldown per key: 6 h canonical, 60 s demo. Key = (chain, subject, GitHub repo + file path, or the proposal CID). (The comment above `record_key` in the contract says "Snapshot space"; the code uses the CID.) The same source at the same block cannot be filed twice. The last 20 records per key are kept; older ones fold into counters.
* Nothing is written before the last check that can revert (`tools/scan_writes.py`). Views only read storage. A fetch failure refuses the filing; it never yields a verdict.

## Seeds

15 real sources filed on the canonical deployment: **14 records on 4 chains (Ethereum, Arbitrum, Base, Polygon), 7 decided, all MATCHES; 7 UNVERIFIABLE; 1 refused.**

| Source | Chain | Result |
|---|---|---|
| CrossLedger site: three Sablier LK3 streams (founders 1784, ecosystem 1783, exchange 1785) with amounts and date-written schedules | ethereum | **MATCHES** ×3 (amount, first unlock, end) |
| idOS distribution README: four VestingWalletCliff wallets, Start / Cliff / End table keyed by row label | arbitrum | **MATCHES** ×4 (start, first unlock, end, beneficiary) |
| Nation3 N3GOV-44 (links the ANT VestingWallet, states no schedule) | ethereum | UNVERIFIABLE, nothing stated |
| Connext CGP11 vesting wallet, Gitcoin AKITA (legacy Sablier v1.1), Pegaxy team vesting (custom) | ethereum, polygon | UNVERIFIABLE, not a standard pattern |
| DittoETH founder stream | ethereum | UNVERIFIABLE, stream canceled on chain |
| FU Studios team stream, CULT DAO presets (IDriss, "until 2028") | arbitrum, base | UNVERIFIABLE, no schedule code can read |
| Exactly EXAIP-23 (names the recipient, not the stream) | optimism | refused, `SUBJECT_NOT_IN_SOURCE` |

No real source in the set disagrees with its chain, so the six disagreeing verdicts were produced live on the demo deployment with this repo's own demo statements (below). Every non-MATCHES result was checked by hand on chain.

Full records with quotes, chain values, unlock math and hand checks: [docs/SEEDS.md](docs/SEEDS.md).

## How a reviewer can test

Use the **demo** contract [`0x884De4ce7bb1890A201533747d7C21B3Ee8F308d`](https://explorer-studio-dev.genlayer.com/address/0x884De4ce7bb1890A201533747d7C21B3Ee8F308d) on GenLayer Studio Dev (60 s cooldown, 30 min freshness: every supported chain finalizes within that). One working example (a real promise, MATCHES):

* `source`: `https://raw.githubusercontent.com/clx-trade/crossledger-site/388aa0af887f9cbf9312c31c2f11da0bebbb90d3/lib/site.js`
* `branch`: `""`
* `chain`: `ethereum`
* `contract`: `0x93b37bd5b6b278373217333ac30d7e74c85fbdcb` (Sablier Lockup v4.0)
* `stream_or_token`: `1785`

```js
import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
const client = createClient({ chain: studioDevnet, account: createAccount(PRIVATE_KEY) });
const fees = await client.estimateTransactionFees();            // a fee on every write
const hash = await client.writeContract({
  address: "0x884De4ce7bb1890A201533747d7C21B3Ee8F308d", functionName: "file_check",
  args: ["https://raw.githubusercontent.com/clx-trade/crossledger-site/388aa0af887f9cbf9312c31c2f11da0bebbb90d3/lib/site.js",
         "", "ethereum", "0x93b37bd5b6b278373217333ac30d7e74c85fbdcb", "1785"],
  value: 0n, fees,
});
// then: client.readContract({ address: "0x884D...308d", functionName: "get_record", args: [<record_id>] })
```

Views: `get_record(id)`, `get_records(offset, limit)`, `get_history(key)`, `get_keys(offset, limit)`, `get_stats()`, `get_config()`.

Other paths: [docs/demo/claims.md](docs/demo/claims.md) is this repo's own demo statements file about real streams and wallets; file its sections (A: `ethereum`, `0x93b3…dbcb`, `1784` → UNLOCKS_EARLIER; B: `1783` → UNLOCKS_LATER; C: `1785` → MORE_THAN_CLAIMED; D: `arbitrum`, `0x6a553c044a6a113b01be52372e8d7bc94594bbe8`, token `0x68731d6f14b827bbcffbebb62b19daa18de1d79c` → LESS_THAN_CLAIMED; E: `base`, `0xf4937657ed8b3f3cb379eed47b8818ee947beb1e`, `1980` → CANCELABLE_NOT_DISCLOSED; F: `arbitrum`, `0x03ed348892a88182e74d8e76e6f7529224032ed8`, same token → BENEFICIARY_DIFFERS) at commit `44491d5b8ff593f912fe3ddebd73c5bbfad24366`. Refusals to try: a branch name instead of the commit (`URL_NOT_PINNED_TO_COMMIT`), chain `bsc` (`UNSUPPORTED_CHAIN`), a stream the source does not name (`SUBJECT_NOT_IN_SOURCE`), the same filing twice within 60 s (`COOLDOWN_UNTIL_…`). Every demo path that was run, with its transaction: [docs/seed-demo.json](docs/seed-demo.json) (log: [docs/demo-run.log](docs/demo-run.log)). Live on the demo: UNLOCKS_EARLIER, UNLOCKS_LATER, MORE_THAN_CLAIMED, LESS_THAN_CLAIMED, CANCELABLE_NOT_DISCLOSED, BENEFICIARY_DIFFERS, MATCHES and UNVERIFIABLE records; refusals URL_NOT_PINNED_TO_COMMIT, URL_HOST_NOT_ALLOWED, UNSUPPORTED_CHAIN, BRANCH_ONLY_FOR_GITHUB, STREAM_ID_REQUIRED, TOKEN_ADDRESS_REQUIRED, SUBJECT_NOT_IN_SOURCE, STREAM_NOT_FOUND, COOLDOWN_UNTIL_…, DUPLICATE_OF_RECORD_…, NO_SUCH_RECORD; and a recheck linked to its earlier record. The first filings of sections C and F were recorded UNVERIFIABLE (NO_FIELD_KEPT): the model quoted nothing usable that time; filed again, they gave MORE_THAN_CLAIMED and BENEFICIARY_DIFFERS. BLOCK_TOO_OLD cannot happen on the demo (every chain finalizes within 30 min) and is covered offline. If you get `GITHUB_API_HTTP_403`, the shared GitHub budget is spent; retry within the hour.

## Repository

```
contracts/VestingCheck.py    the contract (the only deployed file)
test/test_vestingcheck.py    offline suite: sources, binding, parsers, patterns, verdicts, filing rules (mock chain)
test/test_v120.py            v1.2.0 wording, tables, labels, calendar months, date fields
test/test_attacks.py         round-1 attacker pass;  test/test_attacks_r2.py  round-2 attacker pass
test/stub.py, fixtures.py    GenVM runtime stub, JSON-RPC mock chain, builders
test/deploy.mjs              deploys canonical + demo from HEAD (refuses a dirty contracts/)
test/seed_canonical.mjs      files test/seeds.json on canonical;  test/demo_paths.mjs  drives the demo
test/file.mjs                one filing or recheck
tools/verify_source.mjs      gen_getContractCode == contracts/ at HEAD, byte for byte
tools/scan_writes.py         no write before a revert (AST)
tools/live.py, prompt_of.py  run the contract's own code against the real sources and chains (hand checks)
tools/seeds_md.mjs, addresses_md.mjs, final_check.mjs   generate SEEDS.md, ADDRESSES.md, FINAL_CHECK.md from the chain
docs/                        research, threat model, seeds, attack report, final check, submission
```

Offline suite: `cd test && python3 -m unittest` (312 tests).

## Known limitations

* **A stream must be named by its id or link.** Proposals that only name the recipient (common in DAO grants, e.g. Exactly EXAIP-21/23/28) are refused with `SUBJECT_NOT_IN_SOURCE`. Binding by sender + recipient was removed in v1.2.0 because Sablier lets a stream's creator name any sender. Checking who actually funded a stream would need the creation transaction, and the allowlisted RPCs cap `eth_getLogs` at 50 blocks (nodies) or 10,000 (Optimism), so it cannot be found on chain from GenVM.
* **Standard patterns only.** Custom vesting contracts (Pegaxy's, Connext's wallets), legacy Sablier v1.1 (`0xcd18…8888`), proxies, clones and anything that delegates are `UNVERIFIABLE`. A canceled stream is `UNVERIFIABLE` (its schedule no longer applies).
* **Dynamic Sablier curves.** Code does not derive a cliff or first unlock from a dynamic (segment) curve; those fields are `UNVERIFIABLE` for such streams. Amount, end, start, beneficiary and cancelability are still decided.
* **Prose that code will not read.** Percent-of-supply allocations ("Team (20%)") are not turned into amounts. Year-only dates ("vesting until 2028"), relative dates ("12 months after TGE"), TGE percentages and a schedule split across sections are dropped, giving `UNVERIFIABLE` rather than a guess.
* **Label-keyed tables.** A schedule table is bound to a subject only through an exact, unique first-cell label in the same markdown section, and only if no other row with that label names a different subject; if two bound rows disagree on a field, the field is dropped.
* **A stated duration with "then".** "12-month cliff, then 24 months linear" is read both ways (24 months from the start or from the cliff); a chain value between the two stays undecided.
* **One RPC per chain, four IPFS gateways, one Snapshot hub.** Validators read the same endpoints. An endpoint that lies identically to everyone would be believed for chain data; IPFS content is hashed in code, so a lying gateway cannot change a proposal. The Snapshot hub supplies the proposal date and space.
* **GitHub API budget.** The compare API is unauthenticated: 60 calls per hour shared by all studio-dev validators (one per node per filing), about ten GitHub filings an hour network-wide. When it is spent a filing is refused with `GITHUB_API_HTTP_403`; retry later.
* **The model can fail or disagree with itself.** Then the filing is refused (`EXTRACTION_MODEL_ERROR` / `EXTRACTION_UNSTABLE`), nothing is stored and the filer can retry; this happened during the live runs and the retry was recorded. A validator whose own extraction differs from the leader's rejects the round: no record is written, nothing is pending.
* **Duplicate refusal** (same source, same block) needs a refiling after the cooldown at the same finalized block; on the demo it happened live (Ethereum's finalized head moves about every 6.4 min).
* **A model that quotes nothing gives UNVERIFIABLE, not a refusal.** If the leader's answers agree on keeping nothing, the record is UNVERIFIABLE (NO_FIELD_KEPT); refiling after the cooldown can give a decided record. This happened twice on the demo.
* **Fee estimation.** Studio Dev cannot simulate a write that makes web requests, so scripts fall back to the node's fee estimate (logged as "write fee simulation failed").
* **Snapshot treasury lists are not used.** A space's registered treasury does not prove who funded a stream (the sender field is free), so it does not bind either.

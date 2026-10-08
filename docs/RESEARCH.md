# Research

What was measured before choosing endpoints, rules and seeds. Dates are 2026-10-08 unless noted.

## Endpoints every validator uses

| Purpose | Endpoint | Why |
|---|---|---|
| Ethereum | `https://eth-pokt.nodies.app` | answers `eth_call` / `eth_getCode` / `eth_getStorageAt` at old blocks, the `finalized` tag and JSON-RPC batches of 10 from inside GenVM |
| Arbitrum | `https://arb-pokt.nodies.app` | same |
| Optimism | `https://mainnet.optimism.io` | same |
| Base | `https://base-pokt.nodies.app` | same |
| Polygon | `https://poly.api.pocket.network` | same |
| IPFS | `snapshot.4everland.link`, `ipfs.snapshot.box`, `ipfs.filebase.io`, `4everland.io` | returned the proposal bytes (HTTP 200) from GenVM; `ipfs.io`, `dweb.link`, `w3s.link` answered 429, `gateway.pinata.cloud` 404, `trustless-gateway.link` 522, `cloudflare-ipfs.com` no answer ([probe_ipfs_gateways.json](research/probe_ipfs_gateways.json)). Content is hashed to the CID in code, so the gateway's honesty does not matter. |
| Snapshot | `https://hub.snapshot.org/graphql` (GET) | the proposal's space, author and creation time by CID |
| GitHub | `raw.githubusercontent.com/<owner>/<repo>/<sha>/<path>` and `api.github.com/repos/<owner>/<repo>/compare/<branch>...<sha>` | the pinned file, and the proof that the commit is on a branch of that repo; unauthenticated: 60 calls per hour shared by all validators |

Finality, measured from the five RPCs (age of the `finalized` block when read): Ethereum 16 min, Arbitrum 18 min, Optimism 17 min, Base 23 min, Polygon under 1 min. Hence the windows: 1 h canonical, 30 min demo (every chain fits).

`eth_getLogs` limits: nodies (Ethereum, Arbitrum, Base) allows at most 50 blocks per request on the public tier; `mainnet.optimism.io` 10,000. Finding a Sablier stream's creation transaction (to learn who funded it) is therefore not possible from GenVM with these endpoints.

## Patterns

* **Sablier Lockup**: the allowlist of official deployments per chain (v1.0 LL/LD, v1.1 LL2/LD2, v1.2 LL3/LD3/LT3, v2.0 LK, v3.0 LK2, v4.0 LK3) is copied from `sablier-labs/sdk` (`src/evm/releases/lockup`). Legacy Sablier v1.1 (`0xcd18…8888`, the AKITA stream) is a different, older protocol and is not read.
* **OpenZeppelin VestingWallet** 4.x / 5.x and **VestingWalletCliff** 5.1+: every external selector of those contracts is listed; a dispatcher with anything else is not standard. The vesting curve is re-computed in code and compared with `vestedAmount` at five times.

## The H1 re-check (Exactly EXAIP-21 / 23 / 28, Optimism)

The three Exactly proposals name the grant recipient's wallet, the amount and "12 months linear vesting with Sablier.com", but not the stream. Read on chain (LL `0xb923…2bfd`):

| Proposal | Stream | Sender | Recipient | Deposit | Start → end |
|---|---|---|---|---|---|
| EXAIP-28 (2026-02-04) | 7460 | `0x8a1c05c4…02f2` | `0x1072ecb3…6a71` (in the proposal) | 52,000 EXA | 2026-03-03 → 2027-03-03 |
| EXAIP-23 (2025-04-01) | 7157 | `0x23fd464e…5019` | `0x52c5c82d…ac3c` (in the proposal) | 30,000 EXA | 2025-04-30 → 2026-04-30 |
| EXAIP-21 | 6516 | `0xc0d6bc5d…86d3` | `0xf76d5dfb…9e8e` (in the proposal) | 500,000 EXA | 2025-03-18 → 2028-03-17 |

The gov.exa.eth Snapshot space registers `0x23fD464e…5019` as its Optimism treasury, so EXAIP-23's stream comes "from" the DAO treasury; the other two senders are in neither the proposal nor the space settings. The Sablier indexer shows one other stream to the EXAIP-23 recipient (`LL-10-2751`, 25,000 EXA, 2024-03-01, from `0xc0d6…86d3`).

Conclusion: the sender of a Sablier stream is a parameter of `createWithDurations` / `createWithTimestamps`, written by whoever pays; it does not prove the DAO funded the stream. A decoy stream naming the treasury as sender and the recipient from the proposal costs a few tokens. Proving the funder needs the creation transaction, which cannot be found within the RPCs' `eth_getLogs` limits. So the safe choice is: no binding by sender, recipient or registered treasury. All three proposals stay refused (`SUBJECT_NOT_IN_SOURCE`), and the round-1 SENDER_AND_RECIPIENT binding was removed (docs/ATTACK_REPORT.md, R2-H1). EXAIP-23 is in the seed list as a recorded refusal.

A side finding: v1.1.0 counted "12 months" as 360 days. EXAIP-23's stream runs 365 days, so had it been bound, v1.1.0 would have said UNLOCKS_LATER for a stream that does exactly what the proposal says. v1.2.0 counts calendar months.

## Why the v1.1.0 GitHub seeds kept nothing

The prompt was re-sent to the studio-dev model through a throwaway probe contract (`tools/prompt_of.py`, `test/prompt_probe.mjs`), and its answers were run through the contract's own keep rules (`tools/live.py`).

* **FU Studios `fumoney.md`** (LT3-1-189, LL2 #17890): the model returned `{"fields": []}` twice for each stream, correctly. The file links the streams from a table whose cells only say "Sablier"; the allocation percentages sit under separate headings and no schedule is stated. UNVERIFIABLE is the right result; v1.2.0 does not turn "35%" of a supply into an amount.
* **CrossLedger `lib/site.js`** (LK3-1-1784): the model quoted `amount: 150_000_000` (kept) or the whole line `{ id: 1784, …, amount: 150_000_000` (dropped: the stream id was read as a second amount), and the schedule as "Nothing released until 6 October 2027, then released continuously until 6 October 2029", which no field could hold (dates, not durations). The two answers disagreed on what was kept. v1.2.0: ids are not amounts, and `first_unlock_date` / `end_date` read date-written schedules.
* **DittoETH `ditto.md`** (LD2-1-10, and LD2-1-11 for the investor): both streams were canceled on chain.

## Finding seeds

* **Snapshot**: every proposal on the hub created between 2023-06-30 and 2026-10-08 was paged through (about 297,000). 2,374 contain vesting / stream wording and a 0x address; 25 mention Sablier; **none links a specific Sablier stream**. Proposals naming a vesting contract by address use custom contracts (Balancer, StakeWise, Shutter, Decentraland) or OpenZeppelin wallets without a schedule (Nation3 N3GOV-44).
* **GitHub code search** (`app.sablier.com/stream`, `sablier.com/vesting/stream`, "vesting wallet" + cliff, block-explorer links + vesting): about 20 real projects; most are planning documents without deployed addresses. Usable: idOS `contracts` (four VestingWalletCliff wallets on Arbitrum, with Start / Cliff / End and address tables), CrossLedger `crossledger-site` (three Sablier LK3 streams with schedules and amounts), CULT DAO `hub` (a Base stream link), Pegaxy `public-contracts` (Polygon; custom vesting contracts), DittoETH and FU Studios docs.
* **Sablier indexer** (`indexer.hyperindex.xyz/53b7e25`): used only during research, to find streams by recipient. The contract never calls it.

Every seed's chain values were read with `tools/live.py read` before filing and checked against the record afterwards (docs/SEEDS.md).

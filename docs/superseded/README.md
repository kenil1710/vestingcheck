# Superseded deployments

These addresses ran earlier versions of `contracts/VestingCheck.py`. They are kept only for history; use [ADDRESSES.md](../../ADDRESSES.md).

| Deployment | Address | Commit | Replaced by | Why |
|---|---|---|---|---|
| VestingCheck (CANONICAL) | `0xa4b5cc3e3a4978b11501896708F49c0Ce40e8E1d` | `ca6163087d` | `0xB22C490cCb3cc628eF8ed8905BDc31CfeFe03664` | v1.1.0: round-1 attack fixes |
| VestingCheckDemo (DEMO) | `0xE93C0D832fEdF9748a9C861d9d0D6494F8545023` | `ca6163087d` | `0xc7814Dbf761F4bd60351a21aC70231019B751c3C` | v1.1.0: round-1 attack fixes |
| VestingCheck (CANONICAL) | `0xB22C490cCb3cc628eF8ed8905BDc31CfeFe03664` | `293e0954e8` | `0xDe1db41f54Eb4994360bBCd566B8F88a25559593` | v1.2.0: parser + seeds |
| VestingCheckDemo (DEMO) | `0xc7814Dbf761F4bd60351a21aC70231019B751c3C` | `293e0954e8` | `0x90e4E6FA4B79915aE6453406C292f798403c925d` | v1.2.0: parser + seeds |
| VestingCheck (CANONICAL) | `0xDe1db41f54Eb4994360bBCd566B8F88a25559593` | `103c46d76f` | `0xD225b3E0D98b2F90a7a7da97C61A920465a3022E` | v1.2.1: dates read by their own clause (v1.2.0 extraction was unstable on date-written schedules) |
| VestingCheckDemo (DEMO) | `0x90e4E6FA4B79915aE6453406C292f798403c925d` | `103c46d76f` | `0x884De4ce7bb1890A201533747d7C21B3Ee8F308d` | v1.2.1: dates read by their own clause (v1.2.0 extraction was unstable on date-written schedules) |

Seed runs on earlier canonical deployments:

* v1.0.0: [seed-canonical-v1.0.0.json](seed-canonical-v1.0.0.json). Stopped when the round-1 attacker pass changed the contract (H1, H2, M1-M4).
* v1.1.0: [seed-canonical-v1.1.0.json](seed-canonical-v1.1.0.json), log [seed-run-v1.1.0.log](seed-run-v1.1.0.log). 7 records (BENEFICIARY_DIFFERS 1, UNVERIFIABLE 6) and 3 refusals. Not used: the docs parser dropped every claim on the three GitHub seeds, and the one decided record (nation3, BENEFICIARY_DIFFERS) was wrong: the model had labelled a link to the vesting contract itself as the beneficiary, and v1.1.0 accepted it. v1.2.0 refuses that (docs/ATTACK_REPORT.md, R2-H2).
* v1.2.0: [seed-canonical-v1.2.0-stopped.json](seed-canonical-v1.2.0-stopped.json), log [seed-run-v1.2.0-stopped.log](seed-run-v1.2.0-stopped.log). Stopped after 3 records (UNVERIFIABLE: nation3, Connext, AKITA) and 1 refusal (EXAIP-23), when the first CrossLedger filing was refused as EXTRACTION_UNSTABLE: the model quoted the date-written schedule in different lengths and v1.2.0 kept some of them. v1.2.1 reads each date by the source words in front of it.

# Submission

## Intelligent Contract description

```
VestingCheck checks a written vesting promise against the contract holding the tokens. A filer gives a GitHub file pinned to a commit or a Snapshot proposal CID, a chain, and a Sablier stream or OpenZeppelin VestingWallet. Validators prove the source (commit on that repo's branch, or bytes hashed to the CID and found on the Snapshot hub), require it to name that stream or wallet, and read the contract at one fresh finalized block. The model only points at passages. Code keeps a quote only if it is verbatim and bound to the subject, reads every amount, duration and date itself, compares, and records with dates: MATCHES, UNLOCKS_EARLIER/LATER, MORE/LESS, CANCELABLE_NOT_DISCLOSED, BENEFICIARY_DIFFERS or UNVERIFIABLE. The model never decides a value, a chain fact, which stream a passage is about, or the verdict. Seeds: 15 real sources, 14 records on 4 chains: 7 MATCHES (CrossLedger, idOS), 7 UNVERIFIABLE, 1 refused.
```

Character count: **925** (limit 1000), Python `len()` of the text above.

Canonical `0xD225b3E0D98b2F90a7a7da97C61A920465a3022E`, demo `0x884De4ce7bb1890A201533747d7C21B3Ee8F308d` (GenLayer Studio Dev), both from commit `3f6ad48`. Seeds: docs/SEEDS.md. Demo paths: docs/seed-demo.json.

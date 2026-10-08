# Threat model

What VestingCheck protects: a record saying "this vesting promise and this vesting contract agree / disagree in this way, at this block" must only exist if every validator independently saw the same source, the same chain state and the same quoted terms, and if the comparison is code's. A wrong record is worse than no record, so every doubt refuses or yields `UNVERIFIABLE`.

## Actors

| Actor | Can | Cannot |
|---|---|---|
| Filer (anyone) | pick the source, the chain, the subject (lockup + stream id, or wallet + token), the branch; file and recheck | upload evidence (validators fetch it), pick the block, change a record, skip the cooldown |
| Source author (a project, a DAO proposer) | write anything in the docs or proposal, including instructions to the model | make code read a value that is not in a verbatim, bound quote; bind a passage to a subject it does not name |
| Stream creator | create a Sablier stream with any sender, recipient, amount and schedule | make a source name that stream's id (unless they wrote the source) |
| Leader validator | name the block, propose a record, lie | get a record accepted that differs from what validators read and extract themselves |
| Model | return any JSON | supply a value, a chain fact, a binding or a verdict |
| Gateway / hub / RPC | return wrong or different data | change a Snapshot proposal (bytes are hashed to the CID in code); get different answers to different validators accepted (strict equality) |

## Threats and what stops them

| # | Threat | Defence | Tests |
|---|---|---|---|
| T1 | Decoy stream: a tiny stream to a grant's recipient, filed against the DAO's proposal | a stream binds only by its id or link in the source; sender and recipient never bind (R2-H1: the sender field is chosen by the creator) | test_attacks.H1*, test_attacks_r2.R2H1* |
| T2 | Fake token in a VestingWallet (it holds whatever anyone sends) | a wallet's token binds only by its address in the source (H2) | test_attacks.H2* |
| T3 | Model invents or alters a value | value parsed by code from a verbatim quote; a different model value drops the field | test_attacks.Resisted.test_quote_real_value_altered |
| T4 | Truncated quote ("6 months" out of "36 months") | quotes must start and end on word / number boundaries (R2-M5) | test_attacks_r2.R2M5* |
| T5 | Quote about another subject (the next table row, another stream in the same file) | line binding with the nearest reference, section binding only if no other vesting subject is named; label-keyed rows only through a unique label (R2-M1) | test_vestingcheck.Binding, test_v120.TableLabel, test_attacks_r2.R2M1* |
| T6 | A link to the vesting contract read as its beneficiary | beneficiary may not be the subject or its token and needs a recipient word (R2-H2) | test_attacks_r2.R2H2* |
| T7 | Ambiguous wording read one way ("12m", "a year and a half", "12 months after TGE on …", "approved by the DAO on …") | refused, never guessed (M1, R2-M2, R2-M3) | test_attacks.M1*, test_attacks_r2.R2M2*, R2M3* |
| T8 | Prompt injection in the source | source fenced with a per-filing nonce; any answer still has to pass T3-T7 | test_attacks.Resisted.test_prompt_injection_cannot_add_a_value |
| T9 | Unpinned or forked GitHub source | commit sha required; GitHub compare must show it on a branch of the repo in the URL | test_vestingcheck.GithubUrl, SourceFetch.test_fork_commit_diverged_refused |
| T10 | Fake Snapshot proposal or lying gateway | bytes hashed to the CID in code; the CID must be on the hub with the same space and author; the hub's date is used (M4) | test_vestingcheck.SourceFetch, test_attacks.M4* |
| T11 | Old or unfinalized block, or a leader choosing a convenient block | finalized for every validator, no older than the freshness window, not more than 15 min older than the validator's own finalized block | test_vestingcheck.Filing.test_block_* |
| T12 | Non-standard vesting contract made to look standard | full function-table check, no DELEGATECALL / SELFDESTRUCT, no proxy / clone, no fallback (M3), curve checked at five times; Sablier only from the official allowlist | test_vestingcheck.VestingWalletReads, test_attacks.M3*, Resisted.test_lookalike_lockup_not_allowlisted |
| T13 | Stray id mention binding a stream | an id binds only in a section naming the lockup and a stream (M2) | test_attacks.M2* |
| T14 | Spam / history flooding | cooldown per key (6 h canonical), duplicate refusal per source and block, last 20 records per key kept | test_vestingcheck.Filing.test_cooldown_*, test_history_* |
| T15 | Partial writes, stuck state, custody | nothing written before the last revert (AST scan); no pending state; no payable, owner or setter | test_vestingcheck.Static, tools/scan_writes.py |
| T16 | Accusatory or undated wording | one code-built sentence, always with the block date and the source date | test_attacks.Resisted.test_accusing_wording_never_produced |

## Residual risks (accepted, documented)

* An RPC that lies identically to every validator would be believed for chain data (one frozen RPC per chain).
* A source author can write a false statement about their own stream; the record then says the chain differs from the statement, which is what it is for.
* A model that keeps quoting the wrong passage of a bound section can make a field undecided (or refused as unstable), not wrong: values still come from verbatim, bound text.
* A stream named by id in an attacker-written source compares the attacker's statement with that stream; the record names the source, so readers see whose statement it is.

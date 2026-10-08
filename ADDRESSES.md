# Addresses

Network: GenLayer Studio Dev (chain id 61997), RPC `https://studio-dev.genlayer.com/api`, explorer https://explorer-studio-dev.genlayer.com/

| Deployment | Address | Constructor (mode, cooldown s, freshness s) | Commit | Deploy | contracts/VestingCheck.py sha256 |
|---|---|---|---|---|---|
| CANONICAL | [`0xD225b3E0D98b2F90a7a7da97C61A920465a3022E`](https://explorer-studio-dev.genlayer.com/address/0xD225b3E0D98b2F90a7a7da97C61A920465a3022E) | `["CANONICAL",21600,3600]` | [`3f6ad48b34`](https://github.com/kenil1710/vestingcheck/commit/3f6ad48b34e6fef0d151a795e2e020704cdc69c4) | [deploy tx](https://explorer-studio-dev.genlayer.com/tx/0xbc8870b6c235fc7f9fe61ce2fd2c5f9fb4ec15290d2ee6276a657dd1d3889146) | `92dad0f09868f42f94ad6e3d8c5ecdd35e9f1abc1ffaf3ad3a3916f9e58b1139` |
| DEMO | [`0x884De4ce7bb1890A201533747d7C21B3Ee8F308d`](https://explorer-studio-dev.genlayer.com/address/0x884De4ce7bb1890A201533747d7C21B3Ee8F308d) | `["DEMO",60,1800]` | [`3f6ad48b34`](https://github.com/kenil1710/vestingcheck/commit/3f6ad48b34e6fef0d151a795e2e020704cdc69c4) | [deploy tx](https://explorer-studio-dev.genlayer.com/tx/0x8ef065118191b89558bd5240f1de784c82fbb6fecb2470e68746eebd4466a119) | `92dad0f09868f42f94ad6e3d8c5ecdd35e9f1abc1ffaf3ad3a3916f9e58b1139` |

Both deployments are the same file from the same commit; only the constructor differs. `node tools/verify_source.mjs` reads the code back with `gen_getContractCode` and compares it byte for byte with `contracts/` at HEAD.

Previous deployments: [docs/superseded/README.md](docs/superseded/README.md).

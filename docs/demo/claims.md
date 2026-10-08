# VestingCheck demo statements

This file is NOT anyone's vesting promise. It was written for this
repository's demo, so that every verdict can be produced live against real
streams and wallets. Each section names one real vesting subject and states
one term that differs from what that subject does on chain, in a known way.
The real promises these subjects come from are filed as seeds (docs/SEEDS.md).

## Demo A: a later first unlock than the stream has

Stream: https://app.sablier.com/vesting/stream/LK3-1-1784

Nothing is released until 6 October 2028.

## Demo B: an earlier end than the stream has

Stream: https://app.sablier.com/vesting/stream/LK3-1-1783

The allocation is fully vested by 6 January 2029.

## Demo C: a smaller amount than the stream holds

Stream: https://app.sablier.com/vesting/stream/LK3-1-1785

This stream holds 90,000,000 CLXT.

## Demo D: a larger amount than the wallet holds

Vesting wallet 0x6a553c044a6a113b01be52372e8d7bc94594bbe8, token 0x68731d6F14B827bBCfFbEBb62b19Daa18de1d79c.

The wallet vests 300,000,000 IDOS.

## Demo E: a cancelable stream described as locked

Stream: https://app.sablier.com/vesting/stream/LT3-8453-1980

The stream is non-cancelable.

## Demo F: a different beneficiary

Vesting wallet 0x03ed348892a88182e74d8e76e6f7529224032ed8.

Beneficiary: 0x1111111111111111111111111111111111111111

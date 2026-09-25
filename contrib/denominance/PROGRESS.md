# Denominance Lab

Run 12 complete.

Added `block_flow.py`, a block-level fee settlement experiment with seven
passing tests. It models subsidy first, then each non-coinbase transaction's
complete fee tail in block transaction order, followed by normal ordered
coinbase output routing.

The main finding is that bare fee sats are consensus-relevant spacing. An
indexer may keep only Denominance-bearing fee ranges, but only if it also keeps
the full fee value and each range's fee-stream offset for every transaction.
Dropping the bare gaps changes where later denomination ranges land in the
coinbase.

The tests cover transaction-order sensitivity, bare spacing between denoms,
multi-transaction OP_RETURN burns, complete and partial coinbase underclaims,
and block-local pending-fee settlement. A partial underclaim slices the last
Denominance interval exactly; reversing transaction order can change which
denomination reaches which miner output.

I also checked the current Ord updater: non-coinbase fee flotsam is offset by
the accumulated block reward and `self.reward` is increased transaction by
transaction, so the lab's block ordering matches Ord's existing inscription
fee-routing structure.

v0.0.5 now records spend-and-declare adoption, routed-state no-recoloring, and
the block-level fee-spacing rule.

Next: make the block fee representation sparse in the same style as
`sparse_index.py`, then round-trip it through coinbase settlement and prove
that sparse and fully inflated block processing are identical.

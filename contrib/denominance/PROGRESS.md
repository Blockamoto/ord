# Denominance Lab

Run 4 complete.

v0.0.3 now has an explicit lifecycle accounting model:

```text
issued = active + pending_fee + burned + lost
```

The new `ledger.py` experiment tests that invariant across input-origin
creation, ordinary OP_RETURN burns, born-burned output origins, fee re-entry,
coinbase burns, underclaimed coinbase loss, and rejected declaration conflicts.

A real edge case was found and fixed in the reference kernel: coinbase routing
previously returned only routed and lost ranges, so a denomination carried in
fees and then paid into a coinbase OP_RETURN was not exposed as burned.
`coinbase()` now reports burned ranges too.

The standard also now says that raw OP_RETURN placement is not live UTXO state.
Only spendable outputs enter the forward outpoint index. Burn detection is
pinned to Ord's existing `script_pubkey.is_op_return()` predicate.

New/modified accounting tests: 13 passing locally (7 flow + 6 ledger).

Next: build a small Rust fixture module against real `bitcoin::Transaction`
and Ord inscription placement, with no persistent tables yet.

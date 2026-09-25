# Denominance Lab v0.0.3

Status: experimental. Metaprotocol tag: `denom`.

Denominance is a thin annotation over Bitcoin's ordered value flow. A valid
declaration creates a checkpoint. From that checkpoint forward, denomination
ranges follow the same FIFO input-to-output ordering used by Ordinal Theory.

v0.0.3 adds deterministic multi-declaration rules and an explicit lifecycle
accounting model. It also tightens burn handling to Ord's exact OP_RETURN
predicate.

## Declaration identity

A declaration is an inscription whose metaprotocol is exactly `denom`. The
canonical denomination identifier is the declaration inscription ID.
Human-readable names are presentation only.

The compact output-origin form remains valid:

```json
{"v":1,"op":"declare","name":"optional display name"}
```

Equivalent explicit form:

```json
{"v":1,"op":"declare","origin":{"kind":"output"}}
```

Rejected declarations do not create a denomination identifier or issued
supply.

## Origin timing

### Output origin: normative

```json
{"v":1,"op":"declare","origin":{"kind":"output"}}
```

The origin is the post-reveal output in which Ord actually places the
declaration inscription. The body does not carry a second `vout` selector.

Ordinary transaction value flow is resolved first. The entire containing
output is then checkpointed as the new denomination with declaration-relative
offsets `[0,value)`.

Transaction fees are outside a new output-origin denomination because the
declaration begins after the reveal transaction has routed its inputs.

### Input origin: experimental candidate

```json
{"v":1,"op":"declare","origin":{"kind":"input","vin":1}}
```

The selected input prevout is checkpointed immediately before the declaration
transaction is routed. The declaration therefore applies to the entire value
of that existing UTXO and follows through the same transaction.

This is the strongest current candidate for intentional colored-coin-style
creation through a spend. The spender must actually consume the target UTXO,
which gives the declaration a natural participation boundary without ancestry
retracing. Any selected value that becomes fee remains part of the
denomination and enters the block fee stream.

Input origin remains experimental until exercised against Ord's real indexer
fixtures.

### Transaction origin: lab-only

A transaction-wide origin checkpoints the complete ordered input stream before
routing. It is deterministic but broad: every input is included and the fee
tail is part of the denomination. The lab keeps this variant for comparison
but does not recommend standardizing it yet.

### Remote live-UTXO checkpoint: lab-only

A declaration can technically checkpoint an old output that is still unspent
without reconstructing its ancestry. Its present value is sufficient to begin
forward tracking.

The unresolved problem is authorization: a remote declaration can otherwise
label somebody else's UTXO without their participation. Until there is a clean
consent rule, remote outpoint declarations are non-normative.

A declaration that claims historical effect before its checkpoint is a
different feature. That requires historical reconstruction and remains
deferred.

## Deterministic batch semantics

All `denom` declarations created in a transaction are evaluated as a set, not
with a first-wins rule.

1. Parse every declaration independently.
2. Group input-origin declarations by `vin`.
3. If more than one declaration claims the same input origin, every declaration
   in that group fails with `conflicting-origin`.
4. Apply valid, disjoint input-origin declarations before FIFO value routing.
5. Resolve ordinary transaction value flow and Ord inscription placement.
6. Group output-origin declarations by their resolved containing `vout`.
7. If more than one output-origin declaration resolves to the same output,
   every declaration in that group fails with `conflicting-origin`.
8. Apply valid, disjoint output-origin declarations after routing.
9. If an output already contains an active Denominance range, a new
   output-origin declaration fails rather than recoloring it.

This makes validity independent of declaration enumeration order.

## Ordered value flow

For a non-coinbase transaction:

1. concatenate inputs in transaction input order;
2. preserve established value order within each input;
3. cut the stream into outputs in transaction output order;
4. the unassigned tail becomes that transaction's fee stream.

A tracked interval is:

```text
{ denom_id, origin_start, length }
```

Splitting is interval slicing. Merging concatenates streams without blending
identities. A swap has no address-level semantic layer: input/output order
alone determines where denomination ranges land.

## Lifecycle accounting

Each accepted declaration has an immutable `issued` value equal to its origin
value at the checkpoint.

At any indexing boundary, denomination value belongs to one of four buckets:

- `active`: value held by spendable outputs;
- `pending_fee`: value currently in transaction fees, before the block
  coinbase routes the fee stream;
- `burned`: value delivered to an OP_RETURN output;
- `lost`: value left unclaimed by coinbase.

The conservation invariant is:

```text
issued = active + pending_fee + burned + lost
```

After the coinbase transaction has been processed for a block,
`pending_fee = 0`.

`issued` is provenance/accounting metadata, not a promise that all issued
value remains spendable.

## Fees and coinbase

A denomination paid as fees is not destroyed. Fee streams are appended after
the block subsidy in transaction order, matching Ordinal Theory's coinbase
routing model.

The coinbase then routes that combined stream through its outputs. A
denomination range can therefore:

- re-enter a spendable miner output;
- land in an OP_RETURN output and become burned;
- remain in an underclaimed tail and become lost.

## Burns

For v0.0.3, burn detection uses the same exact predicate already used by Ord's
inscription updater: `script_pubkey.is_op_return()`.

This is intentionally narrower than an open-ended "provably unspendable"
classification and avoids indexer disagreement.

Raw routing may show a denomination range landing in an OP_RETURN output, but
that output MUST NOT be persisted as an active denomination-bearing UTXO.
Instead, the range is recorded in the burned bucket.

An output-origin declaration whose containing output is OP_RETURN is valid but
is born burned:

```text
issued = output value
active = 0
burned = output value
```

A zero-value OP_RETURN burns no sats.

## Provenance

Each denomination range retains:

```text
declaration inscription ID
origin kind
origin transaction/outpoint
declaration-relative start
length
```

For input-origin declarations, offsets are relative to the selected input
prevout. For output-origin declarations, offsets are relative to the declared
post-reveal output.

Routing never rewrites `origin_start`; splits only slice the original range.

## Conflict and failure rules

A declaration fails if:

- its body is invalid for the supported declaration version;
- its selected origin has zero value;
- an input index is out of range;
- an output-origin inscription does not resolve to a transaction output;
- its selected origin already contains an active Denominance range;
- another declaration in the same transaction claims the same origin.

External rare-sat classes, inscriptions, and unrelated colored-coin protocols
do not count as Denominance overlap.

The no-recoloring rule is intentionally conservative. Transformation,
reissuance, wrapping, and explicit replacement should be designed later rather
than emerge accidentally from declaration order.

## Minimal index

A forward index can remain interval-based:

```text
denom_id -> {
  declaration_inscription,
  origin_kind,
  origin_ref,
  issued
}

outpoint -> ordered [
  { output_offset, denom_id, origin_start, length },
  ...
]

denom_id -> {
  burned,
  lost
}
```

Only spendable outputs belong in the `outpoint` map. Fee intervals may remain
an in-memory block-local stream until coinbase processing. Burned and lost
totals can be stored directly or derived from append-only events.

A spent annotated output only needs its local interval list. The indexer places
those intervals at Bitcoin value offsets, concatenates inputs, cuts outputs,
and carries the fee tail into coinbase handling.

## Reference experiments

`flow.py` tests the forward-flow kernel: split, merge, fees, coinbase
re-entry, coinbase burns, underclaimed reward loss, ordinary burns, and
order-sensitive swaps.

`origins.py` compares declaration timing and the historical/live-checkpoint
boundary.

`engine.py` tests declaration parsing, batch conflict rules, disjoint
multi-origin declarations, recoloring rejection, invalid origins, and
born-burned output declarations.

`ledger.py` tests the lifecycle buckets and conservation invariant. It
specifically guards against the subtle bug of counting OP_RETURN output ranges
as both active and burned.

Run:

```bash
python3 contrib/denominance/flow.py
python3 contrib/denominance/origins.py
python3 contrib/denominance/engine.py
python3 contrib/denominance/ledger.py
```

## Current research boundary

The useful distinction remains:

- checkpointing an old but still-live UTXO today does not require historical
  retracing;
- claiming that a denomination existed before its declaration checkpoint does.

The first can become practical with sound participation/authorization. The
second remains the expensive Output Retracing problem and stays in the back
pocket.

Deferred: historical retroactivity, transformation/reissuance, wallet
construction, reorg policy, proof formats, and persistent Ord indexer tables.

# Denominance Lab v0.0.5

Status: experimental. Metaprotocol tag: `denom`.

Denominance is a thin annotation over Bitcoin's ordered value flow. A valid
declaration creates a checkpoint. From that checkpoint forward, denomination
ranges follow the same FIFO input-to-output ordering used by Ordinal Theory.

v0.0.5 keeps the normative v0 surface output-origin only, adds a practical
spend-and-declare adoption pattern for existing live UTXOs, tightens the
no-recoloring rule to use reveal-transaction routed state, and makes block-level
fee ordering explicit. Input-origin remains a laboratory primitive: the lab
continues to separate deterministic value routing from ownership/consent
authentication.

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

### Input origin: lab-only pending explicit consent

```json
{"v":1,"op":"declare","origin":{"kind":"input","vin":1}}
```

The selected input prevout can be checkpointed immediately before transaction
routing, and the resulting denomination can deterministically follow the same
FIFO value flow through outputs and fees.

However, spending the target UTXO is not itself a Denominance consent rule.
The declaration envelope may be carried by another input, so the target input's
ordinary spend authorization must not be assumed to authenticate arbitrary
declaration bytes elsewhere in the transaction.

For that reason, input-origin is no longer a normative v0 declaration form.
A normative v0 indexer MUST reject it as an unsupported origin rather than
silently treating spend participation as consent.

The current proof-binding experiment proposes that any future input-origin
extension authenticate a domain-separated message containing both the exact
declaration inscription ID and exact target outpoint:

```text
denom:v1:input-origin:<declaration_inscription_id>:<prevout_txid>:<prevout_vout>
```

The proof scheme itself is deliberately not standardized yet. `consent.py`
uses a deterministic HMAC harness only to test the binding properties: changing
either the declaration ID or target outpoint invalidates the proof, while a
proof that omits the outpoint can be retargeted.

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
label somebody else's UTXO without their participation. The same proof-binding
shape explored for input-origin could eventually authorize a remote live-UTXO
checkpoint, because the authenticated message binds both the declaration and
the exact outpoint. That remains experimental until a Bitcoin-native proof
scheme and verification rules are specified.

A declaration that claims historical effect before its checkpoint is a
different feature. That requires historical reconstruction and remains
deferred.

### Spend-and-declare adoption: normative construction pattern

An owner can adopt an existing live UTXO into Denominance without a remote
checkpoint and without historical retracing: spend it into an output that
contains a normal output-origin declaration.

The denomination begins at the new output checkpoint. If transaction ordering
preserves the target UTXO's exact sat set in that output, the indexer MAY expose
that fact as provenance metadata. Exact preservation is not a declaration
validity condition. Funding sats may mix into the declared output and target
sats may be omitted without changing the validity of the output-origin
declaration.

This construction does not turn Denominance metadata into a Bitcoin ownership
primitive. Bitcoin signatures authorize the spend; Denominance deterministically
annotates the resolved output.

## Normative v0 profile

For v0.0.5, a declaration is normative only when `origin` is omitted or when
`origin.kind` is exactly `"output"`.

Input-origin, transaction-origin, and remote-outpoint declarations remain lab
experiments. A conforming v0 indexer MUST NOT assign supply for those forms.
This deliberately keeps the first interoperable profile small: the declaration
inscription itself identifies the denomination, Ord determines its containing
output, and Denominance begins at that output after the reveal transaction has
finished routing value.

## Deterministic batch semantics (lab engine)

The laboratory engine evaluates all `denom` declarations created in a
transaction as a set, not with a first-wins rule. Normative v0 uses only the
output-origin subset of these rules; the input-origin steps remain experiments.

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
9. If any pre-existing Denominance-bearing value was routed into the resolved
   output by the reveal transaction, a new output-origin declaration fails with
   `conflicting-routed-denom`. This check uses routed transaction state, not
   only the persistent active UTXO index.

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
the block subsidy in non-coinbase transaction order, matching Ordinal Theory's
coinbase routing model. Within each transaction fee stream, the exact ordered
tail is preserved.

Bare fee sats are consensus-relevant spacing even though they carry no
Denominance identity. An indexer MUST NOT concatenate only the denominated fee
ranges or otherwise erase bare gaps before coinbase settlement. A sparse
block-local representation is valid only if it retains each transaction's total
fee value and the value offsets of its Denominance ranges.

The coinbase then routes the combined subsidy-plus-fee stream through its outputs. A
denomination range can therefore:

- re-enter a spendable miner output;
- land in an OP_RETURN output and become burned;
- remain in an underclaimed tail and become lost.

## Burns

For normative v0, burn detection uses the same exact predicate already used by
Ord's inscription updater: `script_pubkey.is_op_return()`.

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
- a normative output-origin resolves to an output into which any existing
  Denominance-bearing value was routed by the reveal transaction;
- a lab-only input origin overlaps an existing active Denominance range;
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
an in-memory block-local stream until coinbase processing, but that stream must
retain bare-value spacing. If represented sparsely, store each transaction's
total fee value plus ordered Denominance ranges with fee-stream offsets. Burned
and lost totals can be stored directly or derived from append-only events.

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

`consent.py` tests declaration/outpoint proof binding. Its HMAC signer is only
a test harness: the useful result is that a consent proof must authenticate the
exact declaration ID and exact target outpoint, and that spend participation
alone is not promoted into a protocol consent rule.

`block_flow.py` tests block-level fee ordering, bare fee spacing, coinbase
splits, OP_RETURN burns, partial underclaims, and terminal loss. It guards
against the subtle indexing error of persisting only Denominance-bearing fee
ranges and forgetting the bare sats that determine their eventual coinbase
offsets.

Run:

```bash
python3 contrib/denominance/flow.py
python3 contrib/denominance/origins.py
python3 contrib/denominance/engine.py
python3 contrib/denominance/ledger.py
python3 contrib/denominance/consent.py
python3 contrib/denominance/block_flow.py
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
construction, reorg policy, a Bitcoin-native consent proof format for
non-output origins, and persistent Ord indexer tables.

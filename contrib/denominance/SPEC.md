# Denominance Lab v0.0.1

Status: experimental. Metaprotocol tag: `denom`.

This lab starts with a deliberately narrow rule: a current declaration creates
a checkpoint, and from that checkpoint forward Denominance follows Bitcoin
value using Ordinal Theory's ordered FIFO assignment.

## Declaration

A v0.0.1 declaration is an inscription tagged with metaprotocol `denom` and a
UTF-8 JSON body such as:

```json
{"v":1,"op":"declare","name":"optional display name"}
```

The canonical denom identifier is the declaration inscription ID. `name` is
presentation only.

The origin is the post-reveal output containing the declaration inscription.
Every sat in that output is covered. If the output value is `N`, the denom
contains `N` sats with declaration-relative offsets `[0,N)`. No separate
amount field is needed.

Retrospective declaration of an existing outpoint is useful, but is not
normative yet because it requires historical output retracing.

## Ordered flow

For a non-coinbase transaction:

1. concatenate inputs in transaction input order;
2. preserve the established value order within each input;
3. cut the stream into outputs in transaction output order;
4. the unassigned tail is the transaction fee stream.

A tracked interval is therefore only:

```text
{ denom_id, origin_start, length }
```

Splitting is slicing. Merging concatenates streams but does not blend denom
identities. A swap has no address-level meaning to the indexer: input/output
order alone determines which denom sats reach which output.

## Fees and coinbase

A denom paid as fees is not automatically destroyed. Ordinal Theory models the
coinbase as an implicit subsidy input followed by each transaction's fee stream
in block transaction order. Denom fee ranges may therefore reappear in coinbase
outputs.

If the miner underclaims the available reward, an unassigned tail is lost.
Denom ranges in that tail are lost too.

## Burns

A positive-value provably unspendable output is a terminal Bitcoin sink.
Denominance records the affected ranges as burned/unspendable while preserving
their provenance. A zero-value OP_RETURN burns no sats.

## Provenance

Every range retains the declaration inscription ID, declaration origin
outpoint, declaration-relative start offset, and length. This survives
arbitrary splits and merges without inventing a second serial number per sat.

## Ambiguity rule

For v0.0.1, a new declaration is invalid if its origin output already contains
an active Denominance range. This prevents accidental recoloring inside the
same protocol until an explicit transformation model exists.

Other ordinal properties, rare-sat classifications, inscriptions, and external
colored-coin schemes do not count as Denominance overlap.

## Minimal index

Forward indexing does not require a global sat-to-outpoint index. It can keep:

```text
denom_id -> { origin_outpoint, origin_value }
outpoint -> ordered [
  { output_offset, denom_id, origin_start, length },
  ...
]
```

When an annotated output is spent, the indexer loads only those intervals,
places them at their Bitcoin value offsets, concatenates inputs, cuts by output
values, and carries the fee tail into coinbase processing.

That is the main result of this iteration: once a declaration checkpoint
exists, Denominance is interval bookkeeping rather than full SatLine
reconstruction.

## Reference experiment

`flow.py` implements and tests split, merge, fees, fee re-entry through
coinbase, underclaimed-coinbase loss, burns, and order-sensitive swap routing.

Run:

```bash
python3 contrib/denominance/flow.py
```

Deferred: retrospective outpoint declarations, output-retracing, transaction-
wide origins, transformations/reissuance, wallet construction, reorg policy,
and proof formats.

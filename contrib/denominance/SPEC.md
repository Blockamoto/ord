# Denominance Lab v0.0.2

Status: experimental. Metaprotocol tag: `denom`.

Denominance is a thin annotation over Bitcoin's ordered value flow. A
declaration creates a checkpoint, and from that checkpoint forward the denom
follows Ordinal Theory's FIFO input-to-output assignment.

## Declaration identity

A declaration is an inscription tagged with metaprotocol `denom`. The
canonical denom identifier is the declaration inscription ID. Human-readable
names are presentation only.

The original v0.0.1 form remains valid and means output-origin:

```json
{"v":1,"op":"declare","name":"optional display name"}
```

Equivalent explicit form:

```json
{"v":1,"op":"declare","origin":{"kind":"output"}}
```

## Origin timing

v0.0.2 distinguishes *when* a declaration enters the value stream.

### Output origin: normative

```json
{"v":1,"op":"declare","origin":{"kind":"output"}}
```

The origin is the post-reveal output containing the declaration inscription.
Ordinary transaction value flow is resolved first. The entire target output is
then checkpointed as the new denom with declaration-relative offsets
`[0,value)`.

This is the cleanest mint-like form. Transaction fees are outside the new
denom because the declaration begins after the reveal transaction has routed
its inputs.

### Input origin: experimental candidate

```json
{"v":1,"op":"declare","origin":{"kind":"input","vin":1}}
```

The selected input prevout is checkpointed immediately before the declaration
transaction is routed. The declaration therefore applies to the entire value
of that existing UTXO and then follows through the same transaction.

This gives a useful colored-coin-style operation without ancestry retracing:
the spender takes an existing output and intentionally denominates it while
spending it. If some of that input becomes fee, that fee is part of the denom
and may later reappear through the block coinbase.

This form is not yet normative because inscription/reveal ordering and conflict
handling still need to be integrated with ord's indexer rather than only the
reference model.

### Transaction origin: lab-only

A transaction-wide origin colors the complete ordered input stream immediately
before routing. It is deterministic, but surprisingly broad: it combines every
input into one declaration-relative range and includes the eventual fee tail.
The lab keeps this variant for comparison but does not recommend standardizing
it yet.

### Remote live-UTXO checkpoint: lab-only

An inscription could name an already-existing unspent outpoint and checkpoint
that UTXO from the declaration point forward. Importantly, this does **not**
require tracing its ancestry to coinbase. The output's present value is enough
to create a new forward checkpoint.

The unresolved problem is authorization: a remote declaration can otherwise
label somebody else's UTXO without their participation. Until there is a clean
ownership/consent rule, remote outpoint declarations are non-normative.

A declaration that claims historical effect *before* its checkpoint is a
different feature. That genuinely requires forward/reverse reconstruction and
remains deferred.

## Ordered value flow

For a non-coinbase transaction:

1. concatenate inputs in transaction input order;
2. preserve the established value order within each input;
3. cut the stream into outputs in transaction output order;
4. the unassigned tail is the transaction fee stream.

A tracked interval is:

```text
{ denom_id, origin_start, length }
```

Splitting is slicing. Merging concatenates streams without blending identities.
A swap has no address-level semantic layer: input/output order alone determines
where denom ranges land.

## Fees and coinbase

A denom paid as fees is not automatically destroyed. The coinbase stream is
modeled as subsidy followed by transaction fee streams in block transaction
order. Denom fee ranges can therefore reappear in coinbase outputs.

If the miner underclaims the available reward, ranges in the unassigned tail
are lost.

## Burns

A positive-value provably unspendable output is a terminal sink. Denominance
records the affected ranges as burned/unspendable while preserving provenance.
A zero-value OP_RETURN burns no sats.

## Provenance

Each range retains:

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

## Conflict and failure rules

A declaration fails if:

- its selected origin has zero value;
- an input/output index is out of range;
- the selected origin already contains an active Denominance range;
- two declarations attempt to claim the same origin range in the same indexing
  step, until a deterministic multi-declaration rule is specified.

External rare-sat classes, inscriptions, and other colored-coin protocols do
not count as Denominance overlap.

The no-recoloring rule is intentionally conservative. Transformation,
reissuance, wrapping, and explicit replacement can be designed later instead
of emerging accidentally from declaration order.

## Minimal index

Forward indexing can remain interval-based:

```text
denom_id -> {
  declaration_inscription,
  origin_kind,
  origin_ref,
  origin_value
}

outpoint -> ordered [
  { output_offset, denom_id, origin_start, length },
  ...
]
```

A spent annotated output only needs its local interval list. The indexer places
those intervals at Bitcoin value offsets, concatenates inputs, cuts outputs,
and carries the fee tail into coinbase handling.

## Reference experiments

`flow.py` tests the forward-flow kernel: split, merge, fees, coinbase
re-entry, underclaimed reward loss, burns, and order-sensitive swaps.

`origins.py` compares declaration timing. Its tests show:

- input-origin can denominate an existing UTXO at the moment it is spent;
- input-origin naturally carries a denom into the fee tail;
- output-origin starts after the transaction, so its fee is not part of supply;
- transaction-wide origin is deterministic but broad;
- a live-UTXO checkpoint needs no ancestry reconstruction;
- active Denominance ranges cannot be silently recolored.

Run:

```bash
python3 contrib/denominance/flow.py
python3 contrib/denominance/origins.py
```

## Current research boundary

The useful distinction is now:

- **checkpointing an old but still-live UTXO today** does not require historical
  retracing;
- **claiming that a denom existed before its declaration checkpoint** does.

The first can become practical with a sound authorization rule. The second
remains the expensive Output Retracing problem and stays in the back pocket.

Deferred: historical retroactivity, transformation/reissuance, wallet
construction, reorg policy, proof formats, and indexer integration.

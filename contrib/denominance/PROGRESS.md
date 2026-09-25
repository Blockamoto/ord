# Denominance Lab

Run 9 complete.

Added `sparse_index.py`, a persistent interval-index experiment. It stores
only denomination-bearing ranges, reconstructs bare gaps before ordered routing,
then compresses routed outputs back to sparse ranges.

The test result is that persistent state needs two different offsets:
`output_offset` for current UTXO placement and `origin_start` for immutable
declaration provenance. The indexed output's total value is also required to
reconstruct the gaps.

Seven tests pass locally, including sparse round trips, split/merge routing,
malformed overlap rejection, bounds checks, and a compact layout renderer.

The standard direction for v0.0.5 is to keep output-origin normative and treat
spend-and-declare of an old live UTXO as a wallet construction. Exact source
preservation is provenance metadata, not declaration validity.

Next: reproduce these sparse fixtures in Rust against real transaction and Ord
inscription-placement types before adding persistent database tables.

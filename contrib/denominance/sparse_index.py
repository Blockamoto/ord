#!/usr/bin/env python3
"""Sparse Denominance UTXO index + source-layout visualizer."""

from dataclasses import dataclass
import unittest

from flow import Output, Span, bare, flow


@dataclass(frozen=True)
class IndexedRange:
    output_offset: int
    denom: str
    origin_start: int
    length: int

    @property
    def output_end(self):
        return self.output_offset + self.length


@dataclass(frozen=True)
class IndexedOutput:
    value: int
    ranges: tuple[IndexedRange, ...]

    def __post_init__(self):
        if self.value < 0:
            raise ValueError("negative-output-value")


def validate(indexed: IndexedOutput):
    cursor = 0
    for item in indexed.ranges:
        if not item.denom:
            raise ValueError("empty-denom")
        if item.output_offset < 0 or item.origin_start < 0 or item.length <= 0:
            raise ValueError("invalid-range")
        if item.output_offset < cursor:
            raise ValueError("overlapping-or-unsorted-ranges")
        if item.output_end > indexed.value:
            raise ValueError("range-out-of-bounds")
        cursor = item.output_end
    return indexed


def inflate(indexed: IndexedOutput):
    validate(indexed)
    stream = []
    cursor = 0
    for item in indexed.ranges:
        gap = item.output_offset - cursor
        if gap:
            stream.extend(bare(gap))
        stream.append(Span(item.denom, item.origin_start, item.length))
        cursor = item.output_end
    if cursor < indexed.value:
        stream.extend(bare(indexed.value - cursor))
    return stream


def deflate(spans):
    ranges = []
    offset = 0
    for span in spans:
        if span.denom is not None:
            ranges.append(IndexedRange(offset, span.denom, span.start, span.length))
        offset += span.length
    return IndexedOutput(offset, tuple(ranges))


def render(indexed: IndexedOutput):
    validate(indexed)
    parts = []
    cursor = 0
    for item in indexed.ranges:
        if item.output_offset > cursor:
            parts.append(f"{cursor}:{item.output_offset} bare")
        parts.append(
            f"{item.output_offset}:{item.output_end} "
            f"{item.denom}[{item.origin_start}:{item.origin_start + item.length})"
        )
        cursor = item.output_end
    if cursor < indexed.value:
        parts.append(f"{cursor}:{indexed.value} bare")
    return " | ".join(parts) if parts else f"0:{indexed.value} bare"


class SparseIndexTests(unittest.TestCase):
    def test_round_trip_with_bare_gaps(self):
        full = [Span(None, 0, 5), Span("A", 10, 10), Span(None, 0, 7), Span("B", 0, 3)]
        indexed = deflate(full)
        self.assertEqual(indexed.value, 25)
        self.assertEqual(
            indexed.ranges,
            (IndexedRange(5, "A", 10, 10), IndexedRange(22, "B", 0, 3)),
        )
        self.assertEqual(inflate(indexed), full)

    def test_sparse_state_preserves_flow_order(self):
        source = IndexedOutput(
            100,
            (IndexedRange(20, "A", 0, 30), IndexedRange(70, "B", 10, 20)),
        )
        routed, fee, _ = flow([inflate(source)], [Output(40), Output(50)])
        self.assertEqual(
            deflate(routed[0]),
            IndexedOutput(40, (IndexedRange(20, "A", 0, 20),)),
        )
        self.assertEqual(
            deflate(routed[1]),
            IndexedOutput(
                50,
                (IndexedRange(0, "A", 20, 10), IndexedRange(30, "B", 10, 20)),
            ),
        )
        self.assertEqual(fee, [Span(None, 0, 10)])

    def test_output_offset_and_origin_offset_are_independent(self):
        indexed = IndexedOutput(20, (IndexedRange(5, "D", 100, 10),))
        self.assertEqual(
            render(indexed),
            "0:5 bare | 5:15 D[100:110) | 15:20 bare",
        )

    def test_rejects_overlap(self):
        with self.assertRaisesRegex(ValueError, "overlapping-or-unsorted"):
            inflate(
                IndexedOutput(
                    20,
                    (IndexedRange(2, "A", 0, 10), IndexedRange(5, "B", 0, 3)),
                )
            )

    def test_rejects_out_of_bounds(self):
        with self.assertRaisesRegex(ValueError, "range-out-of-bounds"):
            inflate(IndexedOutput(10, (IndexedRange(8, "A", 0, 3),)))

    def test_empty_sparse_index_is_all_bare(self):
        indexed = IndexedOutput(12, ())
        self.assertEqual(inflate(indexed), bare(12))
        self.assertEqual(render(indexed), "0:12 bare")

    def test_split_merge_roundtrip_through_persistence(self):
        left = IndexedOutput(40, (IndexedRange(0, "A", 0, 40),))
        right = IndexedOutput(60, (IndexedRange(10, "B", 0, 20),))
        routed, fee, _ = flow([inflate(left), inflate(right)], [Output(55), Output(35)])
        persisted = tuple(deflate(x) for x in routed)
        reinflated = [inflate(x) for x in persisted]
        rerouted, refee, _ = flow(reinflated, [Output(90)])
        self.assertEqual(sum(x.value for x in persisted), 90)
        self.assertEqual(refee, [])
        final = deflate(rerouted[0])
        self.assertEqual(final.value, 90)
        self.assertEqual(
            [(r.denom, r.origin_start, r.length) for r in final.ranges],
            [("A", 0, 40), ("B", 0, 20)],
        )
        self.assertEqual(fee, [Span(None, 0, 10)])


if __name__ == "__main__":
    unittest.main()

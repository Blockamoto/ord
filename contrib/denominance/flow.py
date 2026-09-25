#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Iterable, Optional
import unittest

@dataclass(frozen=True)
class Span:
    denom: Optional[str]
    start: int
    length: int

    def __post_init__(self):
        if self.start < 0 or self.length <= 0:
            raise ValueError("invalid span")

    @property
    def end(self):
        return self.start + self.length

@dataclass(frozen=True)
class Output:
    value: int
    unspendable: bool = False

    def __post_init__(self):
        if self.value < 0:
            raise ValueError("negative output")

def declared(denom: str, value: int):
    if not denom or value < 0:
        raise ValueError("invalid declaration")
    return [] if value == 0 else [Span(denom, 0, value)]

def bare(value: int):
    if value < 0:
        raise ValueError("negative value")
    return [] if value == 0 else [Span(None, 0, value)]

def normalize(spans: Iterable[Span]):
    out = []
    for span in spans:
        if out and out[-1].denom is None and span.denom is None:
            out[-1] = Span(None, 0, out[-1].length + span.length)
        elif (
            out
            and span.denom is not None
            and out[-1].denom == span.denom
            and out[-1].end == span.start
        ):
            prev = out[-1]
            out[-1] = Span(prev.denom, prev.start, prev.length + span.length)
        else:
            out.append(span)
    return out

def take(spans, value):
    spans = list(spans)
    total = sum(span.length for span in spans)
    if value < 0 or value > total:
        raise ValueError("invalid prefix")
    got, rest, needed = [], [], value
    for span in spans:
        if needed == 0:
            rest.append(span)
        elif span.length <= needed:
            got.append(span)
            needed -= span.length
        else:
            a = 0 if span.denom is None else span.start
            b = 0 if span.denom is None else span.start + needed
            got.append(Span(span.denom, a, needed))
            rest.append(Span(span.denom, b, span.length - needed))
            needed = 0
    return normalize(got), normalize(rest)

def flow(inputs, outputs):
    stream = [span for inp in inputs for span in inp]
    outputs = list(outputs)
    if sum(o.value for o in outputs) > sum(s.length for s in stream):
        raise ValueError("outputs exceed inputs")
    routed, remaining = [], stream
    for output in outputs:
        part, remaining = take(remaining, output.value)
        routed.append(part)
    burned = normalize(
        span
        for output, spans in zip(outputs, routed)
        if output.unspendable
        for span in spans
    )
    return routed, normalize(remaining), burned

def coinbase(subsidy, fee_streams, outputs):
    routed, lost, burned = flow([bare(subsidy), *fee_streams], outputs)
    return routed, lost, burned

class Tests(unittest.TestCase):
    def test_split(self):
        routed, fee, _ = flow([declared("D", 100)], [Output(30), Output(70)])
        self.assertEqual(routed, [[Span("D", 0, 30)], [Span("D", 30, 70)]])
        self.assertEqual(fee, [])

    def test_merge_and_fee(self):
        routed, fee, _ = flow(
            [declared("D", 100), bare(50), declared("E", 40)],
            [Output(120), Output(60)],
        )
        self.assertEqual(routed[0], [Span("D", 0, 100), Span(None, 0, 20)])
        self.assertEqual(routed[1], [Span(None, 0, 30), Span("E", 0, 30)])
        self.assertEqual(fee, [Span("E", 30, 10)])

    def test_burn(self):
        routed, _, burned = flow(
            [declared("D", 100)],
            [Output(25, True), Output(75)],
        )
        self.assertEqual(burned, [Span("D", 0, 25)])
        self.assertEqual(routed[1], [Span("D", 25, 75)])

    def test_swap_is_order(self):
        routed, _, _ = flow(
            [declared("A", 50), declared("B", 50)],
            [Output(50), Output(50)],
        )
        self.assertEqual(routed, [[Span("A", 0, 50)], [Span("B", 0, 50)]])

    def test_fee_reenters_via_coinbase(self):
        routed, lost, burned = coinbase(
            100,
            [bare(20), [Span("D", 30, 10)]],
            [Output(125), Output(5)],
        )
        self.assertEqual(routed[0], [Span(None, 0, 120), Span("D", 30, 5)])
        self.assertEqual(routed[1], [Span("D", 35, 5)])
        self.assertEqual(lost, [])
        self.assertEqual(burned, [])

    def test_coinbase_can_burn_fee_denom(self):
        routed, lost, burned = coinbase(
            100,
            [[Span("D", 0, 10)]],
            [Output(100), Output(10, True)],
        )
        self.assertEqual(routed[0], bare(100))
        self.assertEqual(routed[1], declared("D", 10))
        self.assertEqual(lost, [])
        self.assertEqual(burned, declared("D", 10))

    def test_underclaimed_coinbase_loses_tail(self):
        routed, lost, burned = coinbase(100, [[Span("D", 0, 10)]], [Output(100)])
        self.assertEqual(routed, [[Span(None, 0, 100)]])
        self.assertEqual(lost, [Span("D", 0, 10)])
        self.assertEqual(burned, [])

if __name__ == "__main__":
    unittest.main()

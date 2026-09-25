#!/usr/bin/env python3
import unittest

from flow import Output, Span, bare, declared, flow


def active(spans):
    return any(span.denom is not None for span in spans)


def value(spans):
    return sum(span.length for span in spans)


def declare_input(inputs, denom, vin):
    """Checkpoint one existing input immediately before transaction flow."""
    inputs = [list(spans) for spans in inputs]
    if vin < 0 or vin >= len(inputs):
        raise ValueError("vin out of range")
    source_value = value(inputs[vin])
    if source_value == 0:
        raise ValueError("cannot denominate zero-value input")
    if active(inputs[vin]):
        raise ValueError("origin overlaps active denom")
    inputs[vin] = declared(denom, source_value)
    return inputs


def declare_transaction(inputs, denom):
    """Experimental: checkpoint the whole ordered input stream as one denom."""
    inputs = [list(spans) for spans in inputs]
    if not inputs or any(active(spans) for spans in inputs):
        raise ValueError("transaction origin overlaps active denom or is empty")
    offset = 0
    colored = []
    for spans in inputs:
        n = value(spans)
        if n == 0:
            colored.append([])
            continue
        colored.append([Span(denom, offset, n)])
        offset += n
    if offset == 0:
        raise ValueError("cannot denominate zero-value transaction")
    return colored


def declare_output(routed, denom, vout):
    """Checkpoint one output immediately after ordinary transaction flow."""
    routed = [list(spans) for spans in routed]
    if vout < 0 or vout >= len(routed):
        raise ValueError("vout out of range")
    target_value = value(routed[vout])
    if target_value == 0:
        raise ValueError("cannot denominate zero-value output")
    if active(routed[vout]):
        raise ValueError("origin overlaps active denom")
    routed[vout] = declared(denom, target_value)
    return routed


def checkpoint_live_utxo(current_spans, denom):
    """
    Experimental remote checkpoint.

    An unspent historical output can be labeled from the declaration point
    forward without reconstructing ancestry. Authorization is intentionally
    left unresolved, so this form is not normative.
    """
    if not current_spans or value(current_spans) == 0:
        raise ValueError("cannot denominate empty UTXO")
    if active(current_spans):
        raise ValueError("origin overlaps active denom")
    return declared(denom, value(current_spans))


class OriginTests(unittest.TestCase):
    def test_input_origin_colors_existing_utxo_at_spend(self):
        inputs = [bare(40), bare(60)]
        inputs = declare_input(inputs, "D", 1)
        routed, fee, _ = flow(inputs, [Output(50), Output(45)])
        self.assertEqual(
            routed,
            [
                [Span(None, 0, 40), Span("D", 0, 10)],
                [Span("D", 10, 45)],
            ],
        )
        self.assertEqual(fee, [Span("D", 55, 5)])

    def test_output_origin_starts_after_spend(self):
        routed, fee, _ = flow([bare(100)], [Output(90), Output(5)])
        routed = declare_output(routed, "D", 0)
        self.assertEqual(routed[0], [Span("D", 0, 90)])
        self.assertEqual(routed[1], [Span(None, 0, 5)])
        self.assertEqual(fee, [Span(None, 0, 5)])

    def test_transaction_origin_is_deterministic_but_broad(self):
        inputs = declare_transaction([bare(40), bare(60)], "D")
        routed, fee, _ = flow(inputs, [Output(90)])
        self.assertEqual(routed[0], [Span("D", 0, 90)])
        self.assertEqual(fee, [Span("D", 90, 10)])

    def test_live_utxo_checkpoint_needs_no_ancestry(self):
        checkpoint = checkpoint_live_utxo(bare(75), "D")
        self.assertEqual(checkpoint, [Span("D", 0, 75)])

    def test_input_origin_rejects_recoloring(self):
        with self.assertRaisesRegex(ValueError, "overlaps active denom"):
            declare_input([declared("A", 50)], "B", 0)

    def test_output_origin_rejects_recoloring(self):
        routed, _, _ = flow([declared("A", 50)], [Output(50)])
        with self.assertRaisesRegex(ValueError, "overlaps active denom"):
            declare_output(routed, "B", 0)

    def test_invalid_origin_indexes_fail(self):
        with self.assertRaisesRegex(ValueError, "vin out of range"):
            declare_input([bare(10)], "D", 1)
        with self.assertRaisesRegex(ValueError, "vout out of range"):
            declare_output([bare(10)], "D", 1)


if __name__ == "__main__":
    unittest.main()

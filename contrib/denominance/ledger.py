#!/usr/bin/env python3
"""Denominance lifecycle accounting and conservation experiments."""

from collections import defaultdict
import unittest

from engine import Declaration, apply_declarations
from flow import Output, Span, bare, coinbase, declared


def denom_totals(spans):
    totals = defaultdict(int)
    for span in spans:
        if span.denom is not None:
            totals[span.denom] += span.length
    return dict(totals)


def nested_totals(groups):
    return denom_totals(span for group in groups for span in group)


def live_outputs(outputs, routed):
    """Only spendable outputs enter the forward UTXO index."""
    return [
        [] if output.unspendable else list(spans)
        for output, spans in zip(outputs, routed)
    ]


def issued_from_decisions(inputs, outputs, declarations, decisions):
    """Return immutable issued value for accepted declarations."""
    issued = {}
    for declaration, decision in zip(declarations, decisions):
        if not decision.valid:
            continue
        if declaration.kind == "input":
            issued[declaration.inscription_id] = sum(
                span.length for span in inputs[declaration.vin]
            )
        elif declaration.kind == "output":
            issued[declaration.inscription_id] = outputs[declaration.vout].value
        else:
            raise AssertionError(f"unsupported declaration kind {declaration.kind}")
    return issued


def add_totals(*buckets):
    out = defaultdict(int)
    for bucket in buckets:
        for denom, value in bucket.items():
            out[denom] += value
    return dict(out)


class LedgerTests(unittest.TestCase):
    def test_input_origin_conserves_across_live_output_and_pending_fee(self):
        inputs = [bare(100)]
        outputs = [Output(90)]
        declarations = [Declaration("D", "input", vin=0)]

        routed, fee, burned, decisions = apply_declarations(
            inputs, outputs, declarations
        )

        issued = issued_from_decisions(inputs, outputs, declarations, decisions)
        active = nested_totals(live_outputs(outputs, routed))
        pending = denom_totals(fee)

        self.assertEqual(issued, {"D": 100})
        self.assertEqual(active, {"D": 90})
        self.assertEqual(pending, {"D": 10})
        self.assertEqual(denom_totals(burned), {})
        self.assertEqual(add_totals(active, pending), issued)

    def test_existing_denom_sent_to_op_return_is_burned_not_live(self):
        inputs = [declared("D", 100)]
        outputs = [Output(25, True), Output(75)]

        routed, fee, burned, _ = apply_declarations(inputs, outputs, [])

        active = nested_totals(live_outputs(outputs, routed))
        self.assertEqual(active, {"D": 75})
        self.assertEqual(denom_totals(burned), {"D": 25})
        self.assertEqual(denom_totals(fee), {})
        self.assertEqual(add_totals(active, denom_totals(burned)), {"D": 100})

    def test_output_origin_can_be_born_burned(self):
        inputs = [bare(50)]
        outputs = [Output(50, True)]
        declarations = [Declaration("D", "output", vout=0)]

        routed, fee, burned, decisions = apply_declarations(
            inputs, outputs, declarations
        )

        issued = issued_from_decisions(inputs, outputs, declarations, decisions)
        active = nested_totals(live_outputs(outputs, routed))

        self.assertEqual(issued, {"D": 50})
        self.assertEqual(active, {})
        self.assertEqual(denom_totals(fee), {})
        self.assertEqual(denom_totals(burned), {"D": 50})

    def test_fee_denom_can_reenter_coinbase_then_burn(self):
        outputs = [Output(100), Output(10, True)]
        routed, lost, burned = coinbase(
            100,
            [[Span("D", 90, 10)]],
            outputs,
        )

        active = nested_totals(live_outputs(outputs, routed))
        self.assertEqual(active, {})
        self.assertEqual(denom_totals(burned), {"D": 10})
        self.assertEqual(denom_totals(lost), {})

    def test_underclaimed_coinbase_moves_pending_fee_to_lost(self):
        outputs = [Output(100)]
        routed, lost, burned = coinbase(
            100,
            [[Span("D", 90, 10)]],
            outputs,
        )

        active = nested_totals(live_outputs(outputs, routed))
        self.assertEqual(active, {})
        self.assertEqual(denom_totals(burned), {})
        self.assertEqual(denom_totals(lost), {"D": 10})

    def test_rejected_conflict_issues_nothing(self):
        inputs = [bare(100)]
        outputs = [Output(100)]
        declarations = [
            Declaration("A", "input", vin=0),
            Declaration("B", "input", vin=0),
        ]

        routed, fee, burned, decisions = apply_declarations(
            inputs, outputs, declarations
        )
        issued = issued_from_decisions(inputs, outputs, declarations, decisions)

        self.assertEqual(issued, {})
        self.assertEqual(nested_totals(live_outputs(outputs, routed)), {})
        self.assertEqual(denom_totals(fee), {})
        self.assertEqual(denom_totals(burned), {})


if __name__ == "__main__":
    unittest.main()

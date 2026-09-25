#!/usr/bin/env python3
"""Block-level Denominance fee ordering experiment."""

from dataclasses import dataclass
from collections import defaultdict
import unittest

from flow import Output, Span, coinbase, declared, normalize


def denom_only(spans):
    """Terminal lifecycle buckets do not need bare Bitcoin value."""
    return normalize(span for span in spans if span.denom is not None)


@dataclass(frozen=True)
class CoinbaseResult:
    outputs: tuple[tuple[Span, ...], ...]
    burned: tuple[Span, ...]
    lost: tuple[Span, ...]


def settle_block(subsidy, transaction_fee_streams, coinbase_outputs):
    """
    Settle Denominance fee value through coinbase in block transaction order.

    Each fee stream is the ordered tail from one non-coinbase transaction.
    Bare spans must be retained in these streams because they affect where later
    Denominance spans land in the coinbase.
    """
    if subsidy < 0:
        raise ValueError("negative-subsidy")

    streams = [list(stream) for stream in transaction_fee_streams]
    outputs = list(coinbase_outputs)

    routed, lost, burned = coinbase(subsidy, streams, outputs)

    return CoinbaseResult(
        outputs=tuple(tuple(spans) for spans in routed),
        burned=tuple(denom_only(burned)),
        lost=tuple(denom_only(lost)),
    )


def totals(spans):
    result = defaultdict(int)
    for span in spans:
        if span.denom is not None:
            result[span.denom] += span.length
    return dict(result)


class BlockFeeOrderingTests(unittest.TestCase):
    def test_transaction_order_controls_coinbase_destinations(self):
        outputs = [Output(105), Output(15)]

        ab = settle_block(100, [declared("A", 10), declared("B", 10)], outputs)
        ba = settle_block(100, [declared("B", 10), declared("A", 10)], outputs)

        self.assertEqual(
            ab.outputs,
            (
                tuple([Span(None, 0, 100), Span("A", 0, 5)]),
                tuple([Span("A", 5, 5), Span("B", 0, 10)]),
            ),
        )
        self.assertEqual(
            ba.outputs,
            (
                tuple([Span(None, 0, 100), Span("B", 0, 5)]),
                tuple([Span("B", 5, 5), Span("A", 0, 10)]),
            ),
        )

    def test_bare_fee_value_between_denoms_is_consensus_relevant_spacing(self):
        result = settle_block(
            100,
            [
                [Span("A", 0, 5), Span(None, 0, 5)],
                [Span("B", 0, 5)],
            ],
            [Output(107), Output(8)],
        )

        self.assertEqual(
            result.outputs[0],
            tuple([Span(None, 0, 100), Span("A", 0, 5), Span(None, 0, 2)]),
        )
        self.assertEqual(
            result.outputs[1],
            tuple([Span(None, 0, 3), Span("B", 0, 5)]),
        )

    def test_op_return_can_burn_fee_denoms_from_multiple_transactions(self):
        result = settle_block(
            100,
            [declared("A", 10), declared("B", 10)],
            [Output(100), Output(20, unspendable=True)],
        )

        self.assertEqual(totals(result.burned), {"A": 10, "B": 10})
        self.assertEqual(result.lost, ())

    def test_underclaimed_coinbase_loses_latest_fee_value_first_by_stream_position(self):
        result = settle_block(
            100,
            [declared("A", 10), declared("B", 10)],
            [Output(110)],
        )

        self.assertEqual(
            result.outputs[0],
            tuple([Span(None, 0, 100), Span("A", 0, 10)]),
        )
        self.assertEqual(totals(result.lost), {"B": 10})

    def test_partial_underclaim_slices_last_denom_interval(self):
        result = settle_block(
            100,
            [declared("A", 10), declared("B", 10)],
            [Output(115)],
        )

        self.assertEqual(
            result.outputs[0],
            tuple([Span(None, 0, 100), Span("A", 0, 10), Span("B", 0, 5)]),
        )
        self.assertEqual(result.lost, (Span("B", 5, 5),))

    def test_all_fees_can_be_lost_if_coinbase_claims_only_subsidy(self):
        result = settle_block(
            100,
            [declared("A", 4), [Span(None, 0, 3)], declared("B", 6)],
            [Output(100)],
        )

        self.assertEqual(totals(result.lost), {"A": 4, "B": 6})

    def test_pending_fee_is_block_local_not_persistent_after_settlement(self):
        fee_streams = [
            [Span("A", 3, 7)],
            [Span(None, 0, 2), Span("B", 10, 3)],
        ]
        result = settle_block(100, fee_streams, [Output(112)])

        self.assertEqual(result.lost, ())
        self.assertEqual(
            totals(span for output in result.outputs for span in output),
            {"A": 7, "B": 3},
        )


if __name__ == "__main__":
    unittest.main()

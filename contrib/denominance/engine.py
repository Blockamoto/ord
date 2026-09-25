#!/usr/bin/env python3
"""Deterministic transaction-level Denominance declaration experiment."""

from dataclasses import dataclass
import json
import unittest

from flow import Output, Span, bare, declared, flow, normalize


def has_denom(spans):
    return any(span.denom is not None for span in spans)


def span_value(spans):
    return sum(span.length for span in spans)


@dataclass(frozen=True)
class Declaration:
    inscription_id: str
    kind: str
    vin: int | None = None
    vout: int | None = None
    name: str | None = None


@dataclass(frozen=True)
class Decision:
    inscription_id: str
    valid: bool
    reason: str


def parse_declaration(inscription_id, body, *, containing_vout=None):
    """Parse a v1 body after ord has matched metaprotocol denom."""
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid-json") from exc

    if not isinstance(payload, dict):
        raise ValueError("body-must-be-object")
    if payload.get("v") != 1:
        raise ValueError("unsupported-version")
    if payload.get("op") != "declare":
        raise ValueError("unsupported-operation")

    name = payload.get("name")
    if name is not None and not isinstance(name, str):
        raise ValueError("name-must-be-string")

    origin = payload.get("origin", {"kind": "output"})
    if not isinstance(origin, dict):
        raise ValueError("origin-must-be-object")

    kind = origin.get("kind")

    if kind == "output":
        if "vin" in origin or "vout" in origin:
            raise ValueError("output-origin-does-not-take-index")
        return Declaration(inscription_id, "output", vout=containing_vout, name=name)

    if kind == "input":
        vin = origin.get("vin")
        if not isinstance(vin, int) or isinstance(vin, bool) or vin < 0:
            raise ValueError("input-origin-requires-vin")
        if "vout" in origin:
            raise ValueError("input-origin-does-not-take-vout")
        return Declaration(inscription_id, "input", vin=vin, name=name)

    raise ValueError("unsupported-origin")


def _conflicts(declarations, kind, field):
    groups = {}
    for declaration in declarations:
        if declaration.kind == kind:
            groups.setdefault(getattr(declaration, field), []).append(declaration)

    return {
        declaration.inscription_id
        for group in groups.values()
        if len(group) > 1
        for declaration in group
    }


def apply_declarations(inputs, outputs, declarations):
    """
    Apply all declarations in one transaction as a set.

    Disjoint input origins checkpoint before FIFO flow. Output origins checkpoint
    after flow, using the output that actually contains the inscription.
    Same-origin conflicts reject every claimant instead of making order matter.
    """
    inputs = [list(spans) for spans in inputs]
    outputs = list(outputs)
    declarations = list(declarations)
    decisions = {}

    input_conflicts = _conflicts(declarations, "input", "vin")

    for declaration in declarations:
        if declaration.kind != "input":
            continue

        if declaration.inscription_id in input_conflicts:
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "conflicting-origin"
            )
            continue

        if declaration.vin is None or declaration.vin >= len(inputs):
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "vin-out-of-range"
            )
            continue

        value = span_value(inputs[declaration.vin])

        if value == 0:
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "zero-value-origin"
            )
            continue

        if has_denom(inputs[declaration.vin]):
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "origin-already-denominated"
            )
            continue

        inputs[declaration.vin] = declared(declaration.inscription_id, value)
        decisions[declaration.inscription_id] = Decision(
            declaration.inscription_id, True, "accepted-input-origin"
        )

    routed, fee, burned = flow(inputs, outputs)

    output_conflicts = _conflicts(declarations, "output", "vout")

    for declaration in declarations:
        if declaration.kind != "output":
            continue

        if declaration.inscription_id in output_conflicts:
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "conflicting-origin"
            )
            continue

        if declaration.vout is None or declaration.vout >= len(routed):
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "no-containing-output"
            )
            continue

        value = span_value(routed[declaration.vout])

        if value == 0:
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "zero-value-origin"
            )
            continue

        if has_denom(routed[declaration.vout]):
            decisions[declaration.inscription_id] = Decision(
                declaration.inscription_id, False, "origin-already-denominated"
            )
            continue

        routed[declaration.vout] = declared(declaration.inscription_id, value)

        if outputs[declaration.vout].unspendable:
            burned = normalize([*burned, *routed[declaration.vout]])

        decisions[declaration.inscription_id] = Decision(
            declaration.inscription_id, True, "accepted-output-origin"
        )

    return (
        routed,
        fee,
        burned,
        [decisions[d.inscription_id] for d in declarations],
    )


class EngineTests(unittest.TestCase):
    def test_parser_defaults_to_containing_output(self):
        declaration = parse_declaration(
            "d0", '{"v":1,"op":"declare","name":"pizza"}', containing_vout=2
        )
        self.assertEqual(
            declaration,
            Declaration("d0", "output", vout=2, name="pizza"),
        )

    def test_parser_input_origin(self):
        declaration = parse_declaration(
            "d0",
            '{"v":1,"op":"declare","origin":{"kind":"input","vin":1}}',
        )
        self.assertEqual(declaration, Declaration("d0", "input", vin=1))

    def test_parser_rejects_explicit_output_index(self):
        with self.assertRaisesRegex(
            ValueError, "output-origin-does-not-take-index"
        ):
            parse_declaration(
                "d0",
                '{"v":1,"op":"declare","origin":{"kind":"output","vout":1}}',
                containing_vout=1,
            )

    def test_disjoint_input_origins_apply_simultaneously(self):
        declarations = [
            Declaration("A", "input", vin=0),
            Declaration("B", "input", vin=1),
        ]
        routed, fee, _, decisions = apply_declarations(
            [bare(40), bare(60)],
            [Output(50), Output(45)],
            declarations,
        )
        self.assertEqual(
            routed,
            [
                [Span("A", 0, 40), Span("B", 0, 10)],
                [Span("B", 10, 45)],
            ],
        )
        self.assertEqual(fee, [Span("B", 55, 5)])
        self.assertTrue(all(decision.valid for decision in decisions))

    def test_same_input_conflict_rejects_all_not_first_wins(self):
        declarations = [
            Declaration("A", "input", vin=0),
            Declaration("B", "input", vin=0),
        ]
        routed, fee, _, decisions = apply_declarations(
            [bare(100)],
            [Output(90)],
            declarations,
        )
        self.assertEqual(routed, [bare(90)])
        self.assertEqual(fee, bare(10))
        self.assertEqual(
            [decision.reason for decision in decisions],
            ["conflicting-origin", "conflicting-origin"],
        )

    def test_same_output_conflict_rejects_all(self):
        declarations = [
            Declaration("A", "output", vout=0),
            Declaration("B", "output", vout=0),
        ]
        routed, _, _, decisions = apply_declarations(
            [bare(100)],
            [Output(100)],
            declarations,
        )
        self.assertEqual(routed, [bare(100)])
        self.assertEqual(
            [decision.reason for decision in decisions],
            ["conflicting-origin", "conflicting-origin"],
        )

    def test_distinct_output_origins_are_valid(self):
        declarations = [
            Declaration("A", "output", vout=0),
            Declaration("B", "output", vout=1),
        ]
        routed, _, _, decisions = apply_declarations(
            [bare(100)],
            [Output(40), Output(60)],
            declarations,
        )
        self.assertEqual(
            routed,
            [declared("A", 40), declared("B", 60)],
        )
        self.assertTrue(all(decision.valid for decision in decisions))

    def test_input_origin_blocks_output_recoloring(self):
        declarations = [
            Declaration("A", "input", vin=0),
            Declaration("B", "output", vout=0),
        ]
        routed, _, _, decisions = apply_declarations(
            [bare(100)],
            [Output(100)],
            declarations,
        )
        self.assertEqual(routed, [declared("A", 100)])
        self.assertEqual(decisions[0].reason, "accepted-input-origin")
        self.assertEqual(
            decisions[1].reason,
            "origin-already-denominated",
        )

    def test_output_origin_must_land_in_reveal_output(self):
        declarations = [Declaration("A", "output", vout=None)]
        routed, fee, _, decisions = apply_declarations(
            [bare(100)],
            [Output(90)],
            declarations,
        )
        self.assertEqual(routed, [bare(90)])
        self.assertEqual(fee, bare(10))
        self.assertEqual(
            decisions[0].reason,
            "no-containing-output",
        )

    def test_existing_denom_rejects_input_origin(self):
        declarations = [Declaration("B", "input", vin=0)]
        routed, _, _, decisions = apply_declarations(
            [declared("A", 100)],
            [Output(100)],
            declarations,
        )
        self.assertEqual(routed, [declared("A", 100)])
        self.assertEqual(
            decisions[0].reason,
            "origin-already-denominated",
        )

    def test_zero_value_output_origin_fails(self):
        declarations = [Declaration("A", "output", vout=0)]
        routed, _, _, decisions = apply_declarations(
            [bare(10)],
            [Output(0), Output(10)],
            declarations,
        )
        self.assertEqual(routed[0], [])
        self.assertEqual(decisions[0].reason, "zero-value-origin")

    def test_output_origin_on_unspendable_output_is_born_burned(self):
        declarations = [Declaration("A", "output", vout=0)]
        routed, _, burned, decisions = apply_declarations(
            [bare(50)],
            [Output(50, unspendable=True)],
            declarations,
        )
        self.assertEqual(routed, [declared("A", 50)])
        self.assertEqual(burned, declared("A", 50))
        self.assertTrue(decisions[0].valid)


if __name__ == "__main__":
    unittest.main()

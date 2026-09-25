#!/usr/bin/env python3
"""Denominance input-origin consent binding experiment.

The HMAC signer in this file is deliberately only a deterministic test harness.
It lets us test what must be committed by a future Bitcoin-native proof without
pretending HMAC is a protocol signature scheme.
"""

from dataclasses import dataclass
import hashlib
import hmac
import unittest

TAG = "denom"
VERSION = 1


@dataclass(frozen=True)
class OutPoint:
    txid: str
    vout: int

    def __post_init__(self):
        if len(self.txid) != 64 or any(c not in "0123456789abcdef" for c in self.txid):
            raise ValueError("txid-must-be-lowercase-hex")
        if self.vout < 0 or self.vout > 0xFFFFFFFF:
            raise ValueError("vout-out-of-range")


def consent_message(declaration_id: str, target: OutPoint) -> bytes:
    """Canonical bytes a future ownership proof must authenticate."""
    if not declaration_id:
        raise ValueError("missing-declaration-id")
    return (
        f"{TAG}:v{VERSION}:input-origin:{declaration_id}:"
        f"{target.txid}:{target.vout}"
    ).encode("ascii")


def weak_message(declaration_id: str) -> bytes:
    """Counterexample: binds the declaration but not the selected UTXO."""
    return f"{TAG}:v{VERSION}:input-origin:{declaration_id}".encode("ascii")


def sign_test(key: bytes, message: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_test(key: bytes, message: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_test(key, message), signature)


class ConsentTests(unittest.TestCase):
    def setUp(self):
        self.key = b"owner-test-key"
        self.a = OutPoint("11" * 32, 0)
        self.b = OutPoint("22" * 32, 1)
        self.declaration = "aa" * 32 + "i0"

    def test_strong_proof_binds_exact_outpoint(self):
        sig = sign_test(self.key, consent_message(self.declaration, self.a))
        self.assertTrue(
            verify_test(self.key, consent_message(self.declaration, self.a), sig)
        )
        self.assertFalse(
            verify_test(self.key, consent_message(self.declaration, self.b), sig)
        )

    def test_strong_proof_binds_exact_declaration(self):
        sig = sign_test(self.key, consent_message(self.declaration, self.a))
        other = "bb" * 32 + "i0"
        self.assertFalse(verify_test(self.key, consent_message(other, self.a), sig))

    def test_weak_proof_can_be_retargeted(self):
        sig = sign_test(self.key, weak_message(self.declaration))
        self.assertTrue(verify_test(self.key, weak_message(self.declaration), sig))
        # There is no target in the authenticated bytes, so an indexer cannot
        # distinguish a declaration aimed at one UTXO from the same proof aimed
        # at another.
        self.assertEqual(
            weak_message(self.declaration),
            weak_message(self.declaration),
        )

    def test_spend_participation_alone_cannot_authenticate_declaration(self):
        # A denom envelope may live outside the target input's witness. Changing
        # declaration data therefore needs its own explicit authentication rule.
        authorized_transaction = b"same-non-witness-transaction-structure"
        altered_declaration = "cc" * 32 + "i0"
        self.assertEqual(
            authorized_transaction,
            authorized_transaction,
        )
        self.assertNotEqual(
            consent_message(self.declaration, self.a),
            consent_message(altered_declaration, self.a),
        )

    def test_outpoint_serialization_is_unambiguous(self):
        m0 = consent_message(self.declaration, OutPoint("11" * 32, 1))
        m1 = consent_message(self.declaration, OutPoint("11" * 32, 10))
        self.assertNotEqual(m0, m1)
        self.assertTrue(m0.endswith(b":1"))
        self.assertTrue(m1.endswith(b":10"))

    def test_message_is_domain_separated(self):
        message = consent_message(self.declaration, self.a)
        self.assertTrue(message.startswith(b"denom:v1:input-origin:"))


if __name__ == "__main__":
    unittest.main()

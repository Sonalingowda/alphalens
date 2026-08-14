"""Regression tests for typed immutable PostgreSQL aggregate decoding."""

import json
from dataclasses import replace
from types import SimpleNamespace
import unittest

from app.opportunity_intelligence.persistence.postgresql import (
    MarketContextPostgreSQLRepository,
    decode_canonical,
)
from tests.test_opportunity_domain_models import _context


class PostgreSQLCanonicalDecodeTests(unittest.TestCase):
    def test_persisted_data_quality_boolean_round_trips_with_its_hash(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                context = _context_with_persisted_input_value(value)
                # JSON serialization models the JSONB representation retained by
                # PostgreSQL without changing canonical payload semantics.
                postgres_payload = json.loads(json.dumps(context.to_dict()))

                restored = decode_canonical(type(context), postgres_payload)

                self.assertIs(restored.data_quality.observations[0].value, value)
                self.assertEqual(restored.canonical_sha256(), context.canonical_sha256())
                repository = MarketContextPostgreSQLRepository(object())
                self.assertEqual(
                    repository._decode(
                        SimpleNamespace(
                            canonical_payload=postgres_payload,
                            canonical_hash=context.canonical_sha256(),
                        )
                    ),
                    context,
                )

    def test_legacy_postgresql_boolean_strings_decode_only_for_boolean_contract(self) -> None:
        for encoded, expected in (("1", True), ("0", False)):
            with self.subTest(encoded=encoded):
                context = _context_with_persisted_input_value(expected)
                payload = context.to_dict()
                payload["data_quality"]["observations"][0]["value"] = encoded

                restored = decode_canonical(type(context), payload)

                self.assertIs(restored.data_quality.observations[0].value, expected)
                self.assertEqual(restored.canonical_sha256(), context.canonical_sha256())


def _context_with_persisted_input_value(value: bool):
    context = _context()
    observation = replace(
        context.data_quality.observations[0],
        semantic_identifier="data_quality.persisted_inputs_verified",
        value=value,
    )
    data_quality = replace(context.data_quality, observations=(observation,))
    return replace(context, data_quality=data_quality)

"""Tests for non-executable AlphaLens v2 labeling infrastructure."""

from dataclasses import replace
import unittest

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.labels.contracts import (
    LABEL_INFRASTRUCTURE_SCHEMA_VERSION,
    LabelClass,
    LabelPolicyDeclaration,
    LabelPolicyMetadataError,
    LabelStrategy,
)
from app.labels.registry import (
    FIRST_TOUCH_STRATEGY_DEFINITION,
    LABEL_STRATEGY_REGISTRY,
    LabelStrategyDefinition,
    LabelStrategyRegistry,
)
from app.market_data.models import CandleTimeframe
from app.persistence.models import (
    V2LabelGenerationRunRecord,
    V2LabelObservationRecord,
    V2LabelPolicyRecord,
    V2LabelRunSourceRecord,
)


class LabelContractTests(unittest.TestCase):
    def test_class_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(label_class.value for label_class in LabelClass),
            ("BUY", "SELL", "WAIT"),
        )

    def test_strategy_registry_is_deterministic_and_non_executable(
        self,
    ) -> None:
        rebuilt = LabelStrategyRegistry(
            definitions=(FIRST_TOUCH_STRATEGY_DEFINITION,)
        )

        self.assertEqual(
            LABEL_STRATEGY_REGISTRY.canonical_bytes(),
            rebuilt.canonical_bytes(),
        )
        self.assertEqual(
            LABEL_STRATEGY_REGISTRY.configuration_hash,
            rebuilt.configuration_hash,
        )
        self.assertEqual(len(rebuilt.configuration_hash), 64)
        self.assertFalse(FIRST_TOUCH_STRATEGY_DEFINITION.executable)
        self.assertEqual(
            rebuilt.canonical_payload()[
                "label_infrastructure_schema_version"
            ],
            LABEL_INFRASTRUCTURE_SCHEMA_VERSION,
        )

    def test_strategy_cannot_be_marked_executable_before_approval(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            LabelPolicyMetadataError,
            "not executable",
        ):
            replace(FIRST_TOUCH_STRATEGY_DEFINITION, executable=True)

    def test_strategy_requires_all_three_classes(self) -> None:
        with self.assertRaisesRegex(
            LabelPolicyMetadataError,
            "BUY/SELL/WAIT",
        ):
            LabelStrategyDefinition(
                identifier=LabelStrategy.FIRST_TOUCH_BARRIER,
                description="Invalid output contract.",
                output_classes=("BUY", "SELL"),
                required_approvals=("policy",),
                executable=False,
            )

    def test_duplicate_strategy_definitions_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            LabelPolicyMetadataError,
            "duplicate",
        ):
            LabelStrategyRegistry(
                definitions=(
                    FIRST_TOUCH_STRATEGY_DEFINITION,
                    FIRST_TOUCH_STRATEGY_DEFINITION,
                )
            )

    def test_approved_policy_declaration_hashes_canonical_content(
        self,
    ) -> None:
        first = _approved_policy(
            {"horizon": {"unit": "unapproved_test", "value": 1}}
        )
        second = _approved_policy(
            {"horizon": {"value": 1, "unit": "unapproved_test"}}
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first.configuration_hash,
            second.configuration_hash,
        )
        self.assertEqual(len(first.configuration_hash), 64)
        self.assertEqual(
            first.canonical_configuration_payload(),
            second.canonical_configuration_payload(),
        )

    def test_policy_configuration_is_defensively_immutable(self) -> None:
        source = {"nested": {"values": [1, 2]}}
        declaration = _approved_policy(source)

        source["nested"]["values"].append(3)  # type: ignore[index,union-attr]
        self.assertEqual(
            declaration.canonical_configuration_payload()[
                "configuration"
            ],
            {"nested": {"values": [1, 2]}},
        )

    def test_policy_declaration_fails_closed(self) -> None:
        valid = _approved_policy({"approved_parameter": "test-only"})
        cases = (
            lambda: replace(valid, identifier="Invalid"),
            lambda: replace(valid, version="1"),
            lambda: replace(valid, asset_identifier="ETH"),
            lambda: replace(valid, quote_currency="EUR"),
            lambda: replace(valid, timeframe=CandleTimeframe.DAY_1),
            lambda: replace(valid, approval_reference=" "),
            lambda: replace(valid, configuration={}),
            lambda: replace(valid, configuration_hash="0" * 64),
        )

        for invalid_factory in cases:
            with self.subTest(invalid_factory=invalid_factory):
                with self.assertRaises(LabelPolicyMetadataError):
                    invalid_factory()

    def test_non_json_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            LabelPolicyMetadataError,
            "canonical JSON",
        ):
            _approved_policy({"invalid": object()})


class LabelPersistenceMetadataTests(unittest.TestCase):
    def test_expected_tables_are_declared(self) -> None:
        self.assertEqual(
            {
                V2LabelPolicyRecord.__tablename__,
                V2LabelGenerationRunRecord.__tablename__,
                V2LabelObservationRecord.__tablename__,
                V2LabelRunSourceRecord.__tablename__,
            },
            {
                "v2_label_policies",
                "v2_label_generation_runs",
                "v2_label_observations",
                "v2_label_run_sources",
            },
        )

    def test_policy_identity_and_observation_identity_are_unique(
        self,
    ) -> None:
        policy_constraints = {
            constraint.name
            for constraint in V2LabelPolicyRecord.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        observation_constraints = {
            constraint.name
            for constraint in V2LabelObservationRecord.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }

        self.assertIn(
            "uq_v2_label_policies_identity",
            policy_constraints,
        )
        self.assertIn(
            "uq_v2_label_observations_run_timestamp",
            observation_constraints,
        )

    def test_fail_closed_database_constraints_are_present(self) -> None:
        expected = {
            "ck_v2_label_policies_strategy",
            "ck_v2_label_policies_timeframe",
            "ck_v2_label_policies_hashes",
            "ck_v2_label_policies_immutable",
            "ck_v2_label_runs_counts",
            "ck_v2_label_runs_range",
            "ck_v2_label_runs_hashes",
            "ck_v2_label_runs_integrity",
            "ck_v2_label_observations_outcome",
            "ck_v2_label_observations_chronology",
            "ck_v2_label_observations_result_hash",
            "ck_v2_label_run_sources_role",
            "ck_v2_label_run_sources_hash",
        }
        actual = {
            constraint.name
            for model in (
                V2LabelPolicyRecord,
                V2LabelGenerationRunRecord,
                V2LabelObservationRecord,
                V2LabelRunSourceRecord,
            )
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }

        self.assertTrue(expected.issubset(actual))


def _approved_policy(
    configuration: dict[str, object],
) -> LabelPolicyDeclaration:
    return LabelPolicyDeclaration.approved(
        identifier="candidate_c_policy",
        version="1.0.0",
        strategy=LabelStrategy.FIRST_TOUCH_BARRIER,
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=CandleTimeframe.MINUTE_5,
        approval_reference="test-only-approval",
        configuration=configuration,
    )


if __name__ == "__main__":
    unittest.main()

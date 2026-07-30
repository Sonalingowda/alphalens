"""Declarative feature-registry and provenance infrastructure tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.features.contracts import (
    CandleField,
    FeatureAvailabilityRule,
    FeatureDefinitionMetadata,
    FeatureHistoryType,
    FeatureMetadataError,
    FeatureOutputMetadata,
    feature_available_at,
)
from app.features.registry import (
    INTRADAY_FEATURE_REGISTRY,
    FeatureRegistry,
)
from app.market_data.models import CandleTimeframe
from app.persistence.models import (
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
    FeaturePipelineRunSourceRecord,
    FeaturePipelineRunValueRecord,
)


class FeatureRegistryTests(unittest.TestCase):
    def test_valid_declarations_produce_deterministic_registry_evidence(
        self,
    ) -> None:
        definitions = (
            _definition("price_state", "price_state_value"),
            _definition(
                "derived_state",
                "derived_state_value",
                dependencies=("price_state",),
            ),
        )

        first = FeatureRegistry(definitions)
        second = FeatureRegistry(definitions)

        self.assertEqual(first, second)
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(
            first.configuration_hash,
            second.configuration_hash,
        )
        self.assertEqual(len(first.configuration_hash), 64)
        self.assertEqual(
            first.output_names,
            ("price_state_value", "derived_state_value"),
        )
        payload = first.canonical_payload()
        self.assertEqual(payload["registry_schema_version"], "1.0.0")
        self.assertEqual(
            payload["availability_contract_version"],
            "1.0.0",
        )
        self.assertEqual(
            payload["definitions"][1]["dependencies"],
            ["price_state"],
        )
        self.assertFalse(hasattr(definitions[0], "compute"))

    def test_production_registry_contains_no_unapproved_features(self) -> None:
        self.assertEqual(INTRADAY_FEATURE_REGISTRY.definitions, ())
        self.assertEqual(INTRADAY_FEATURE_REGISTRY.output_names, ())
        self.assertEqual(len(INTRADAY_FEATURE_REGISTRY.configuration_hash), 64)

    def test_duplicate_definitions_and_outputs_are_rejected(self) -> None:
        first = _definition("price_state", "shared_output")

        with self.assertRaisesRegex(
            FeatureMetadataError,
            "duplicate definition",
        ):
            FeatureRegistry((first, first))

        with self.assertRaisesRegex(
            FeatureMetadataError,
            "declared by both",
        ):
            FeatureRegistry(
                (
                    first,
                    _definition("volume_state", "shared_output"),
                )
            )

    def test_missing_or_forward_dependencies_are_rejected(self) -> None:
        dependent = _definition(
            "derived_state",
            "derived_state_value",
            dependencies=("price_state",),
        )
        source = _definition("price_state", "price_state_value")

        with self.assertRaisesRegex(
            FeatureMetadataError,
            "unregistered or later",
        ):
            FeatureRegistry((dependent, source))

    def test_metadata_validation_is_fail_closed(self) -> None:
        valid = _definition("price_state", "price_state_value")

        invalid_cases = (
            lambda: replace(valid, identifier="PriceState"),
            lambda: replace(valid, description=" "),
            lambda: replace(valid, category=""),
            lambda: replace(valid, definition_version="1"),
            lambda: replace(valid, required_inputs=()),
            lambda: replace(valid, supported_timeframes=()),
            lambda: replace(valid, outputs=()),
            lambda: replace(valid, maximum_lookback_observations=0),
            lambda: replace(valid, requires_continuity=False),
            lambda: replace(valid, decimal_quantum=Decimal("0")),
        )
        for invalid_factory in invalid_cases:
            with self.subTest(invalid_factory=invalid_factory):
                with self.assertRaises(FeatureMetadataError):
                    FeatureRegistry((invalid_factory(),))

    def test_output_warmup_cannot_exceed_bounded_lookback(self) -> None:
        with self.assertRaisesRegex(
            FeatureMetadataError,
            "warm-up cannot exceed",
        ):
            _definition(
                "price_state",
                "price_state_value",
                warmup=3,
                maximum_lookback=2,
            )

    def test_availability_is_exactly_the_candle_close_boundary(self) -> None:
        timestamp = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
        expectations = {
            CandleTimeframe.MINUTE_5: timestamp + timedelta(minutes=5),
            CandleTimeframe.MINUTE_10: timestamp + timedelta(minutes=10),
            CandleTimeframe.MINUTE_15: timestamp + timedelta(minutes=15),
        }

        for timeframe, expected in expectations.items():
            with self.subTest(timeframe=timeframe):
                self.assertEqual(
                    feature_available_at(
                        timestamp,
                        timeframe,
                        FeatureAvailabilityRule.CANDLE_CLOSE,
                    ),
                    expected,
                )

    def test_availability_rejects_noncanonical_timestamps(self) -> None:
        for timestamp in (
            datetime(2026, 7, 30, 10, 0),
            datetime(
                2026,
                7,
                30,
                10,
                0,
                tzinfo=timezone(timedelta(hours=1)),
            ),
            datetime(2026, 7, 30, 10, 3, tzinfo=timezone.utc),
        ):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(FeatureMetadataError):
                    feature_available_at(
                        timestamp,
                        CandleTimeframe.MINUTE_5,
                        FeatureAvailabilityRule.CANDLE_CLOSE,
                    )


class FeatureProvenanceSchemaTests(unittest.TestCase):
    def test_registry_and_availability_columns_exist(self) -> None:
        run_columns = FeaturePipelineRunRecord.__table__.columns
        value_columns = EngineeredFeatureRecord.__table__.columns

        for name in (
            "registry_hash",
            "registry_schema_version",
            "availability_contract_version",
            "registry_snapshot",
        ):
            self.assertIn(name, run_columns)
        self.assertIn("available_at", value_columns)

        run_constraints = {
            constraint.name
            for constraint in FeaturePipelineRunRecord.__table__.constraints
        }
        value_constraints = {
            constraint.name
            for constraint in EngineeredFeatureRecord.__table__.constraints
        }
        self.assertIn(
            "ck_feature_pipeline_runs_registry_metadata",
            run_constraints,
        )
        self.assertIn(
            "ck_engineered_features_availability",
            value_constraints,
        )

    def test_many_batch_provenance_uses_composite_identity(self) -> None:
        table = FeaturePipelineRunSourceRecord.__table__
        self.assertEqual(
            tuple(column.name for column in table.primary_key.columns),
            ("feature_run_id", "ingestion_batch_id"),
        )
        self.assertIn("source_candle_count", table.columns)
        self.assertIn("source_range_start", table.columns)
        self.assertIn("source_range_end", table.columns)
        self.assertIn("source_subset_hash", table.columns)

    def test_run_value_membership_prevents_duplicate_links(self) -> None:
        table = FeaturePipelineRunValueRecord.__table__
        self.assertEqual(
            tuple(column.name for column in table.primary_key.columns),
            ("feature_run_id", "feature_value_id"),
        )


def _definition(
    identifier: str,
    output_name: str,
    *,
    dependencies: tuple[str, ...] = (),
    warmup: int = 2,
    maximum_lookback: int = 2,
) -> FeatureDefinitionMetadata:
    return FeatureDefinitionMetadata(
        identifier=identifier,
        description=f"Declarative test metadata for {identifier}.",
        category="test",
        definition_version="1.0.0",
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=(
            CandleTimeframe.MINUTE_5,
            CandleTimeframe.MINUTE_10,
            CandleTimeframe.MINUTE_15,
        ),
        outputs=(
            FeatureOutputMetadata(
                identifier=output_name,
                description=f"Declarative test output for {identifier}.",
                minimum_observations=warmup,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=maximum_lookback,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        dependencies=dependencies,
    )


if __name__ == "__main__":
    unittest.main()

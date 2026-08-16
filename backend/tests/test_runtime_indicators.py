from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.opportunity_intelligence.domain import (
    AuditMetadata,
    FeatureSnapshot,
    FeatureSnapshotValue,
    IndicatorValue,
    IntegrityReference,
    MarketScope,
    Provenance,
)
from app.opportunity_intelligence.services.projections import (
    IndicatorProjectionService,
)
from app.runtime_indicators import RuntimeIndicatorService


CANDLE_TIME = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
AVAILABLE_AT = datetime(2026, 8, 10, 19, 5, tzinfo=timezone.utc)


def reference(artifact_id: str, artifact_type: str) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest="a" * 64,
        available_at=AVAILABLE_AT,
    )


def audit(feature_record: IntegrityReference, market: IntegrityReference) -> AuditMetadata:
    provenance = Provenance(
        source_references=(market, feature_record),
        policy_references=(),
        code_version="git:runtime-indicators-test",
        configuration_hash="c" * 64,
        lineage_hash="d" * 64,
    )

    return AuditMetadata(
        created_at=AVAILABLE_AT,
        evidence_cutoff=AVAILABLE_AT,
        available_at=AVAILABLE_AT,
        provenance=provenance,
        result_hash="b" * 64,
    )


def make_value(
    output_name: str,
    value: str,
    feature_id: str | None = None,
) -> FeatureSnapshotValue:
    feature_record = reference(
        feature_id or f"feature.{output_name}",
        "feature_definition",
    )

    return FeatureSnapshotValue(
        feature_identifier=feature_id or output_name,
        definition_version="1.0.0",
        output_name=output_name,
        candle_timestamp=CANDLE_TIME,
        available_at=AVAILABLE_AT,
        value=Decimal(value),
        feature_record=feature_record,
    )


def make_snapshot(
    values: tuple[FeatureSnapshotValue, ...],
) -> FeatureSnapshot:
    market = reference("market.snapshot.test", "market_snapshot")

    first_feature_record = (
        values[0].feature_record
        if values
        else reference("feature.empty", "feature_definition")
    )

    return FeatureSnapshot(
        contract_version="1.0.0",
        snapshot_id="feature.snapshot.runtime_indicators.test",
        scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
        market_snapshot=market,
        registry_hash=INTRADAY_FEATURE_REGISTRY.configuration_hash,
        values=values,
        audit=audit(first_feature_record, market),
    )


class RuntimeIndicatorServiceTests(unittest.IsolatedAsyncioTestCase):

    async def test_non_empty_snapshot_projects_matching_indicator_values(self):
        snapshot = make_snapshot(
            (
                make_value(
                    "exponential_moving_average_12",
                    "63911.006645932534305896",
                ),
                make_value(
                    "relative_strength_index",
                    "44.438791102412541989",
                ),
            )
        )

        result = await RuntimeIndicatorService().project(snapshot)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], IndicatorValue)
        self.assertEqual(
            result[0].output_name,
            "exponential_moving_average_12",
        )
        self.assertEqual(
            result[0].value,
            Decimal("63911.006645932534305896"),
        )
        self.assertEqual(result[0].unit, "price")

        self.assertEqual(
            result[1].output_name,
            "relative_strength_index",
        )
        self.assertEqual(
            result[1].value,
            Decimal("44.438791102412541989"),
        )
        self.assertEqual(result[1].unit, "percent")

    async def test_single_value_snapshot_projects_single_indicator(self):
        snapshot = make_snapshot(
            (
                make_value(
                    "relative_strength_index",
                    "44.438791102412541989",
                ),
            )
        )

        result = await RuntimeIndicatorService().project(snapshot)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].output_name,
            "relative_strength_index",
        )

    async def test_canonical_ordering_is_preserved(self):
        values = (
            make_value(
                "exponential_moving_average_12",
                "100.0",
            ),
            make_value(
                "relative_strength_index",
                "50.0",
            ),
        )

        snapshot = make_snapshot(values)

        result = await RuntimeIndicatorService().project(snapshot)

        self.assertEqual(
            tuple(item.output_name for item in result),
            tuple(item.output_name for item in snapshot.values),
        )

    async def test_point_in_time_fields_are_preserved(self):
        snapshot = make_snapshot(
            (
                make_value(
                    "relative_strength_index",
                    "44.438791102412541989",
                ),
            )
        )

        source = snapshot.values[0]
        result = await RuntimeIndicatorService().project(snapshot)
        projected = result[0]

        self.assertEqual(projected.candle_timestamp, source.candle_timestamp)
        self.assertEqual(projected.available_at, source.available_at)

    async def test_feature_record_is_preserved(self):
        snapshot = make_snapshot(
            (
                make_value(
                    "relative_strength_index",
                    "44.438791102412541989",
                ),
            )
        )

        source = snapshot.values[0]
        result = await RuntimeIndicatorService().project(snapshot)

        self.assertIs(result[0].feature_record, source.feature_record)
        self.assertEqual(result[0].feature_record, source.feature_record)

    async def test_concrete_service_satisfies_indicator_projection_protocol(self):
        service = RuntimeIndicatorService()

        self.assertIsInstance(service, IndicatorProjectionService)

        signature = inspect.signature(service.project)
        self.assertIn("feature_snapshot", signature.parameters)

        annotation = signature.return_annotation
        self.assertNotEqual(annotation, inspect.Signature.empty)


if __name__ == "__main__":
    unittest.main()

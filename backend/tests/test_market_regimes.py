"""Deterministic market regime analysis tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.research.dataset import (
    ModelObservation,
    ModelReadyDataset,
)
from app.research.market_regimes import (
    MarketRegimeAnalysisError,
    RegimeModelSource,
    RegimePredictionEvidence,
    ResearchArtifactReference,
    build_market_regime_report,
    classify_market_regimes,
)


class MarketRegimeAnalysisTests(unittest.TestCase):
    def test_assignments_are_point_in_time_and_cover_two_dimensions(
        self,
    ) -> None:
        dataset = _dataset()
        changed_last = replace(
            dataset.development_observations[-1],
            feature_values=_feature_values(29, width=Decimal("0.90")),
        )
        changed_dataset = replace(
            dataset,
            development_observations=(
                *dataset.development_observations[:-1],
                changed_last,
            ),
        )

        original = classify_market_regimes(dataset)
        changed = classify_market_regimes(changed_dataset)

        self.assertEqual(
            [item.assignment_hash for item in original[:-1]],
            [item.assignment_hash for item in changed[:-1]],
        )
        self.assertTrue(
            all(len(item.regimes) == 2 for item in original)
        )
        self.assertEqual(
            {item.trend_regime for item in original},
            {"bull_trend", "bear_trend", "sideways_market"},
        )
        self.assertEqual(
            {item.volatility_regime for item in original},
            {"high_volatility_regime", "low_volatility_regime"},
        )

    def test_report_metrics_and_svg_hashes_are_deterministic(self) -> None:
        dataset = _dataset()
        sources = _sources(dataset)
        statistical, residual, explainability = _references()

        first = build_market_regime_report(
            dataset,
            sources,
            statistical_report=statistical,
            residual_report=residual,
            explainability_artifacts=explainability,
        )
        second = build_market_regime_report(
            dataset,
            tuple(reversed(sources)),
            statistical_report=statistical,
            residual_report=residual,
            explainability_artifacts=tuple(reversed(explainability)),
        )

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(
            [item.plot.content_hash for item in first.plots],
            [item.plot.content_hash for item in second.plots],
        )
        self.assertEqual(len(first.plots), 12)
        self.assertEqual(len(first.assignments), 30)
        self.assertFalse(
            first.payload["verification"]["final_holdout_evaluated"]
        )
        for model in first.payload["model_regime_analysis"].values():
            self.assertEqual(len(model["fold_wise_performance"]), 6)
            self.assertEqual(
                set(model["overall_regime_performance"]),
                {
                    "bull_trend",
                    "bear_trend",
                    "sideways_market",
                    "high_volatility_regime",
                    "low_volatility_regime",
                },
            )

    def test_holdout_evidence_is_rejected(self) -> None:
        dataset = _dataset()
        sources = _sources(dataset)
        statistical, residual, explainability = _references()

        with self.assertRaises(MarketRegimeAnalysisError):
            build_market_regime_report(
                dataset,
                (
                    replace(
                        sources[0],
                        final_holdout_evaluated=True,
                    ),
                    *sources[1:],
                ),
                statistical_report=statistical,
                residual_report=residual,
                explainability_artifacts=explainability,
            )


def _dataset() -> ModelReadyDataset:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observations = tuple(
        ModelObservation(
            prediction_timestamp=start + timedelta(days=index),
            label_available_at=start + timedelta(days=index + 5),
            feature_values=_feature_values(index),
            target_value=Decimal(index - 15) / Decimal("1000"),
        )
        for index in range(30)
    )
    return ModelReadyDataset(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        source_ingestion_batch_id=UUID(int=1),
        source_feature_run_id=UUID(int=2),
        source_target_run_id=UUID(int=3),
        validation_run_id=UUID(int=4),
        source_dataset_hash="a" * 64,
        model_dataset_hash="b" * 64,
        feature_pipeline_version="1.1.0",
        target_name="forward_log_return",
        target_version="1.0.0",
        target_definition_hash="c" * 64,
        validation_split_hash="d" * 64,
        feature_names=(
            "sma_20",
            "sma_50",
            "bollinger_20_2_lower",
            "bollinger_20_2_middle",
            "bollinger_20_2_upper",
        ),
        source_observation_count=30,
        total_eligible_observation_count=30,
        development_eligible_observation_count=30,
        holdout_eligible_observation_count=0,
        excluded_feature_warmup_count=0,
        excluded_missing_target_count=0,
        development_range_start=observations[0].prediction_timestamp,
        development_range_end=observations[-1].prediction_timestamp,
        final_holdout_start=start + timedelta(days=30),
        final_holdout_end=start + timedelta(days=39),
        development_observations=observations,
        validation_splits=(),
        point_in_time_validated=True,
    )


def _feature_values(
    index: int,
    *,
    width: Decimal | None = None,
) -> tuple[Decimal, ...]:
    sma_50 = Decimal("100")
    spread = (
        Decimal("0.02")
        if index % 3 == 0
        else Decimal("-0.02")
        if index % 3 == 1
        else Decimal("0")
    )
    middle = Decimal("100")
    relative_width = width or (
        Decimal(index % 5 + 1) / Decimal("100")
    )
    half_band = middle * relative_width / Decimal(2)
    return (
        sma_50 * (Decimal(1) + spread),
        sma_50,
        middle - half_band,
        middle,
        middle + half_band,
    )


def _sources(
    dataset: ModelReadyDataset,
) -> tuple[RegimeModelSource, ...]:
    families = (
        "linear_regression",
        "ridge_regression",
        "random_forest_regression",
        "xgboost_regression",
    )
    sources: list[RegimeModelSource] = []
    for family_index, family in enumerate(families, start=1):
        predictions: list[RegimePredictionEvidence] = []
        for index, observation in enumerate(
            dataset.development_observations
        ):
            actual = float(observation.target_value)
            predicted = actual * (0.55 + family_index * 0.05) + 0.001
            predictions.append(
                RegimePredictionEvidence(
                    experiment_id=UUID(int=family_index),
                    model_family=family,  # type: ignore[arg-type]
                    split_sequence=index // 5 + 1,
                    prediction_timestamp=(
                        observation.prediction_timestamp
                    ),
                    actual=actual,
                    predicted=predicted,
                    residual=actual - predicted,
                    evidence_hash=(
                        f"{family_index:x}" * 60 + f"{index:04x}"
                    ),
                )
            )
        sources.append(
            RegimeModelSource(
                experiment_id=UUID(int=family_index),
                model_family=family,  # type: ignore[arg-type]
                experiment_configuration_hash=f"{family_index:x}" * 64,
                experiment_result_hash=f"{family_index + 4:x}" * 64,
                model_dataset_hash=dataset.model_dataset_hash,
                feature_pipeline_version=(
                    dataset.feature_pipeline_version
                ),
                target_version=dataset.target_version,
                validation_run_id=dataset.validation_run_id,
                split_hash=dataset.validation_split_hash,
                evaluated_split_count=6,
                evaluated_observation_count=30,
                final_holdout_evaluated=False,
                predictions=tuple(predictions),
            )
        )
    return tuple(sources)


def _references() -> tuple[
    ResearchArtifactReference,
    ResearchArtifactReference,
    tuple[ResearchArtifactReference, ...],
]:
    statistical = ResearchArtifactReference(
        artifact_id=UUID(int=100),
        artifact_type="statistical_validation_report",
        model_family=None,
        configuration_hash="1" * 64,
        result_hash="2" * 64,
    )
    residual = ResearchArtifactReference(
        artifact_id=UUID(int=101),
        artifact_type="residual_diagnostics_report",
        model_family=None,
        configuration_hash="3" * 64,
        result_hash="4" * 64,
    )
    explainability = (
        ResearchArtifactReference(
            artifact_id=UUID(int=102),
            artifact_type="model_explainability_artifact",
            model_family="random_forest_regression",
            configuration_hash="5" * 64,
            result_hash="6" * 64,
        ),
        ResearchArtifactReference(
            artifact_id=UUID(int=103),
            artifact_type="model_explainability_artifact",
            model_family="xgboost_regression",
            configuration_hash="7" * 64,
            result_hash="8" * 64,
        ),
    )
    return statistical, residual, explainability


if __name__ == "__main__":
    unittest.main()

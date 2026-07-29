"""Deterministic statistical validation report tests."""

from dataclasses import replace
from decimal import Decimal
import unittest
from uuid import UUID

from app.research.statistical_validation import (
    ExplainabilityArtifactReference,
    FoldMetricEvidence,
    StatisticalModelSource,
    build_statistical_validation_report,
)


class StatisticalValidationTests(unittest.TestCase):
    def test_report_is_deterministic_and_complete(self) -> None:
        sources = _sources()
        references = _references(sources)

        first = build_statistical_validation_report(sources, references)
        second = build_statistical_validation_report(
            tuple(reversed(sources)),
            tuple(reversed(references)),
        )

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(
            len(first.payload["pairwise_comparisons"]),
            6,
        )
        self.assertEqual(
            first.payload["verification"]["hypothesis_count"],
            18,
        )
        self.assertFalse(
            first.payload["verification"]["model_retraining_performed"]
        )
        self.assertFalse(
            first.payload["verification"]["final_holdout_evaluated"]
        )

    def test_all_wilcoxon_results_receive_holm_adjustment(self) -> None:
        report = build_statistical_validation_report(
            _sources(),
            _references(_sources()),
        )

        tests = [
            comparison["metrics"][metric]["wilcoxon"]
            for comparison in report.payload["pairwise_comparisons"]
            for metric in ("mae", "rmse", "directional_accuracy")
        ]
        self.assertEqual(len(tests), 18)
        self.assertTrue(
            all(test["adjusted_p_value"] is not None for test in tests)
        )
        self.assertTrue(
            all(test["holm_family_size"] == 18 for test in tests)
        )

    def test_holdout_or_boundary_mismatch_is_rejected(self) -> None:
        sources = _sources()
        references = _references(sources)

        with self.assertRaises(ValueError):
            build_statistical_validation_report(
                (
                    replace(sources[0], final_holdout_evaluated=True),
                    *sources[1:],
                ),
                references,
            )
        changed_fold = replace(
            sources[1].folds[0],
            test_end="2099-01-01T00:00:00+00:00",
        )
        with self.assertRaises(ValueError):
            build_statistical_validation_report(
                (
                    sources[0],
                    replace(
                        sources[1],
                        folds=(changed_fold, *sources[1].folds[1:]),
                    ),
                    *sources[2:],
                ),
                references,
            )


def _sources() -> tuple[StatisticalModelSource, ...]:
    families = (
        "linear_regression",
        "ridge_regression",
        "random_forest_regression",
        "xgboost_regression",
    )
    offsets = (
        Decimal("0.004"),
        Decimal("0.001"),
        Decimal("0.003"),
        Decimal("0.005"),
    )
    sources: list[StatisticalModelSource] = []
    for family_index, (family, offset) in enumerate(
        zip(families, offsets, strict=True),
        start=1,
    ):
        folds = tuple(
            FoldMetricEvidence(
                sequence=index,
                test_start=f"2026-01-{index:02d}T00:00:00+00:00",
                test_end=f"2026-01-{index:02d}T00:00:00+00:00",
                mae=(
                    Decimal("0.03")
                    + offset
                    + Decimal(index % 5) / Decimal("1000")
                ),
                rmse=(
                    Decimal("0.04")
                    + offset
                    + Decimal(index % 7) / Decimal("1000")
                ),
                directional_accuracy=(
                    Decimal("0.45")
                    + Decimal(family_index) / Decimal("100")
                    + Decimal(index % 3) / Decimal("100")
                ),
                prediction_hash=f"{family_index:x}" * 64,
            )
            for index in range(1, 21)
        )
        sources.append(
            StatisticalModelSource(
                experiment_id=UUID(int=family_index),
                model_family=family,
                configuration_hash=f"{family_index:x}" * 64,
                result_hash=f"{family_index + 4:x}" * 64,
                model_dataset_hash="a" * 64,
                feature_pipeline_version="1.1.0",
                target_version="1.0.0",
                validation_run_id=UUID(int=100),
                split_hash="b" * 64,
                final_holdout_evaluated=False,
                folds=folds,
            )
        )
    return tuple(sources)


def _references(
    sources: tuple[StatisticalModelSource, ...],
) -> tuple[ExplainabilityArtifactReference, ...]:
    return tuple(
        ExplainabilityArtifactReference(
            artifact_id=UUID(int=200 + index),
            experiment_id=source.experiment_id,
            model_family=source.model_family,
            configuration_hash="c" * 64,
            result_hash="d" * 64,
        )
        for index, source in enumerate(sources[2:], start=1)
    )


if __name__ == "__main__":
    unittest.main()

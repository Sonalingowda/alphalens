"""Deterministic final selection from immutable development evidence."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from app.research.model_selection_scoring import (
    FinalModelSelectionError,
    MODEL_FAMILY_ORDER,
    json_safe as _json_safe,
    market_domain as _market_domain,
    mean as _mean,
    number as _number,
    performance_domain as _performance_domain,
    residual_domain as _residual_domain,
    statistical_domain as _statistical_domain,
)

FINAL_MODEL_SELECTION_REPORT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ImmutableArtifact:
    artifact_id: UUID
    artifact_type: str
    report_version: str
    configuration_hash: str | None
    result_hash: str
    payload: dict[str, Any]
    hash_verified: bool


@dataclass(frozen=True, slots=True)
class PredictionEvidenceSummary:
    model_family: str
    observation_count: int
    prediction_hash_count: int
    evidence_set_hash: str
    hashes_verified: bool


@dataclass(frozen=True, slots=True)
class AutomatedTestEvidence:
    command: str
    tests_run: int
    status: str


@dataclass(frozen=True, slots=True)
class BuiltFinalModelSelectionReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    selected_model_family: str
    selected_experiment_id: UUID


def build_final_model_selection_report(
    *,
    comparison: ImmutableArtifact,
    statistical: ImmutableArtifact,
    residual: ImmutableArtifact,
    market_regime: ImmutableArtifact,
    explainability: tuple[ImmutableArtifact, ...],
    prediction_evidence: tuple[PredictionEvidenceSummary, ...],
    test_evidence: AutomatedTestEvidence,
) -> BuiltFinalModelSelectionReport:
    """Aggregate only immutable development evidence and select by fixed score."""
    artifacts = (comparison, statistical, residual, market_regime)
    _validate_artifacts(
        artifacts,
        explainability,
        prediction_evidence,
        test_evidence,
    )
    models = _comparison_models(comparison.payload)
    provenance = _validated_provenance(
        models,
        statistical.payload,
        residual.payload,
        market_regime.payload,
        explainability,
    )
    prediction_by_family = {
        item.model_family: item for item in prediction_evidence
    }
    explainability_by_family = {
        item.payload["model_family"]: item for item in explainability
    }

    performance = _performance_domain(models)
    statistical_scores = _statistical_domain(statistical.payload)
    residual_scores = _residual_domain(residual.payload)
    market_scores = _market_domain(market_regime.payload)
    explainability_scores = {
        family: Decimal(1) for family in MODEL_FAMILY_ORDER
    }
    engineering_scores = {
        family: Decimal(1) for family in MODEL_FAMILY_ORDER
    }

    domain_scores = {
        family: {
            "performance": performance[family]["score"],
            "statistical_evidence": statistical_scores[family]["score"],
            "residual_quality": residual_scores[family]["score"],
            "market_robustness": market_scores[family]["score"],
            "explainability_integrity": explainability_scores[family],
            "engineering_integrity": engineering_scores[family],
        }
        for family in MODEL_FAMILY_ORDER
    }
    total_scores = {
        family: _mean(tuple(domain_scores[family].values()))
        for family in MODEL_FAMILY_ORDER
    }
    ranking = sorted(
        MODEL_FAMILY_ORDER,
        key=lambda family: (
            -total_scores[family],
            -statistical_scores[family]["score"],
            -performance[family]["score"],
            -residual_scores[family]["score"],
            -market_scores[family]["score"],
            family,
        ),
    )
    rank_lookup = {
        family: rank for rank, family in enumerate(ranking, start=1)
    }

    configuration: dict[str, Any] = {
        "report_version": FINAL_MODEL_SELECTION_REPORT_VERSION,
        "scope": "immutable_development_evidence_only",
        "approved_models": MODEL_FAMILY_ORDER,
        "candidate_eligibility_gates": {
            "common_provenance_required": True,
            "point_in_time_validation_required": True,
            "final_holdout_must_be_untouched": True,
            "experiment_mutation_forbidden": True,
            "prediction_hash_verification_required": True,
            "source_artifact_hash_verification_required": True,
            "automated_tests_must_pass": True,
        },
        "scoring": {
            "domains": (
                "performance",
                "statistical_evidence",
                "residual_quality",
                "market_robustness",
                "explainability_integrity",
                "engineering_integrity",
            ),
            "domain_weighting": "equal_arithmetic_mean_one_sixth_each",
            "within_domain_weighting": "equal_per_declared_criterion",
            "rank_score": (
                "four_model_fraction_of_other_models_ranked_below;"
                "best=1,worst=0,ties=average_occupied_rank_scores"
            ),
            "performance_criteria": {
                "mae": "lower",
                "rmse": "lower",
                "directional_accuracy": "higher",
            },
            "statistical_pair_criterion": {
                "decisive_win": (
                    "holm_adjusted_wilcoxon_significant_at_0.05_and_"
                    "bootstrap_95_percent_confidence_interval_excludes_"
                    "zero_in_the_same_favorable_direction"
                ),
                "decisive_win_points": "1",
                "non_decisive_points_per_model": "0.5",
                "comparisons_per_model": 9,
                "effect_sizes": (
                    "reported_descriptively_without_additional_score_to_"
                    "avoid_double_counting_the_same_pairwise_difference"
                ),
            },
            "residual_criteria": {
                "absolute_mean_residual": "lower",
                "sample_variance": "lower",
                "absolute_median_residual": "lower",
                "absolute_skewness": "lower",
                "absolute_excess_kurtosis": "lower",
                "maximum_absolute_autocorrelation_lags_1_to_20": "lower",
                "heteroscedasticity_non_rejection_count_at_0.05": "higher",
            },
            "market_criteria": {
                "five_regimes_times_mae_rmse_directional_accuracy": 15,
                "regime_metric_spreads": 3,
                "mean_fold_coefficient_of_variation": 1,
                "total": 19,
            },
            "explainability_scoring": (
                "integrity_gate_only;tree_artifacts_required_for_random_"
                "forest_and_xgboost;approved_tree_only_scope_is_not_"
                "applicable_to_linear_or_ridge;no_model_receives_a_"
                "family_availability_advantage"
            ),
            "engineering_scoring": (
                "integrity_gate_only;all_required_checks_must_pass"
            ),
            "tie_breakers": (
                "statistical_evidence_score_descending",
                "performance_score_descending",
                "residual_quality_score_descending",
                "market_robustness_score_descending",
                "model_family_ascending",
            ),
        },
        "source_artifacts": [
            _artifact_reference(item)
            for item in sorted(
                artifacts + explainability,
                key=lambda item: (
                    item.artifact_type,
                    str(item.artifact_id),
                ),
            )
        ],
    }

    evidence_summary: dict[str, Any] = {}
    for family in MODEL_FAMILY_ORDER:
        model = models[family]
        evidence_summary[family] = {
            "experiment_id": model["experiment_id"],
            "performance": _json_safe(performance[family]),
            "statistical_evidence": _json_safe(
                statistical_scores[family]
            ),
            "residual_quality": _json_safe(residual_scores[family]),
            "market_robustness": _json_safe(market_scores[family]),
            "explainability": _explainability_summary(
                family,
                explainability_by_family,
            ),
            "engineering_quality": {
                "registry_duplicate_repeatability": model[
                    "deterministic_repeatability"
                ],
                "deterministic_prediction_replay": {
                    "status": "verified",
                    "source": "residual_diagnostics_report",
                },
                "prediction_evidence": {
                    "observation_count": (
                        prediction_by_family[family].observation_count
                    ),
                    "prediction_hash_count": (
                        prediction_by_family[family].prediction_hash_count
                    ),
                    "evidence_set_hash": (
                        prediction_by_family[family].evidence_set_hash
                    ),
                    "hashes_verified": True,
                },
                "source_artifact_hashes_verified": True,
                "provenance_complete": True,
                "automated_test_status": {
                    "command": test_evidence.command,
                    "tests_run": test_evidence.tests_run,
                    "status": test_evidence.status,
                },
            },
            "domain_scores": {
                name: _number(value)
                for name, value in domain_scores[family].items()
            },
            "total_score": _number(total_scores[family]),
            "rank": rank_lookup[family],
        }

    artifact_hashes = {
        "source_reports": [
            _artifact_reference(item)
            for item in sorted(
                artifacts + explainability,
                key=lambda item: (
                    item.artifact_type,
                    str(item.artifact_id),
                ),
            )
        ],
        "residual_svg_sha256": sorted(
            item["content_hash"]
            for item in residual.payload["plot_manifest"]
        ),
        "market_regime_svg_sha256": sorted(
            item["content_hash"]
            for item in market_regime.payload["plot_manifest"]
        ),
        "prediction_evidence_set_sha256": {
            family: prediction_by_family[family].evidence_set_hash
            for family in MODEL_FAMILY_ORDER
        },
    }
    selected = ranking[0]
    payload: dict[str, Any] = {
        "report_version": FINAL_MODEL_SELECTION_REPORT_VERSION,
        "configuration": configuration,
        "provenance": provenance,
        "evidence_summary": evidence_summary,
        "ranking_table": [
            {
                "rank": rank_lookup[family],
                "model_family": family,
                "experiment_id": models[family]["experiment_id"],
                "total_score": _number(total_scores[family]),
                "domain_scores": {
                    name: _number(value)
                    for name, value in domain_scores[family].items()
                },
            }
            for family in ranking
        ],
        "selected_model": {
            "model_family": selected,
            "experiment_id": models[selected]["experiment_id"],
            "selection_rank": 1,
            "selection_rationale": (
                "highest_total_equal_domain_score_under_the_predeclared_"
                "deterministic_framework"
            ),
            "holdout_status": (
                "selected_for_future_separately_authorized_holdout_"
                "evaluation;not_evaluated_by_this_report"
            ),
        },
        "artifact_hashes": artifact_hashes,
        "verification": {
            "model_count": 4,
            "source_artifact_count": len(artifacts)
            + len(explainability),
            "source_plot_hash_count": len(
                artifact_hashes["residual_svg_sha256"]
            )
            + len(artifact_hashes["market_regime_svg_sha256"]),
            "prediction_evidence_count": sum(
                item.observation_count for item in prediction_evidence
            ),
            "prediction_hashes_verified": sum(
                item.prediction_hash_count for item in prediction_evidence
            ),
            "artifact_hashes_verified": True,
            "deterministic_repeatability_required": True,
            "point_in_time_validated": True,
            "final_holdout_evaluated": False,
            "model_retraining_performed": False,
            "hyperparameter_tuning_performed": False,
            "experiments_modified": False,
            "new_experimental_evidence_created": False,
        },
    }
    selected_experiment_id = UUID(models[selected]["experiment_id"])
    return BuiltFinalModelSelectionReport(
        configuration=configuration,
        configuration_hash=_sha256_json(configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
        selected_model_family=selected,
        selected_experiment_id=selected_experiment_id,
    )


def _explainability_summary(
    family: str,
    by_family: dict[str, ImmutableArtifact],
) -> dict[str, Any]:
    if family in {"linear_regression", "ridge_regression"}:
        return {
            "status": (
                "not_applicable_to_approved_tree_only_explainability_scope"
            ),
            "integrity_gate_passed": True,
            "feature_importance_stability": None,
            "shap_consistency": None,
            "permutation_importance_consistency": None,
        }
    artifact = by_family[family]
    methods = artifact.payload["methods"]
    permutation = methods["permutation_importance"]["ranking"]
    shap = methods["tree_shap"]["ranking"]
    summary: dict[str, Any] = {
        "status": "verified_immutable_tree_explainability_artifact",
        "artifact": _artifact_reference(artifact),
        "integrity_gate_passed": True,
        "shap_consistency": {
            "permutation_rank_spearman": _number(
                _spearman_rank_correlation(permutation, shap)
            ),
            "per_fold_shap_variability_status": (
                "not_recorded_in_source_artifact"
            ),
        },
        "permutation_importance_consistency": _standard_deviation_summary(
            permutation
        ),
    }
    impurity = methods.get("impurity_feature_importance")
    if impurity is None:
        summary["feature_importance_stability"] = {
            "status": "not_applicable_to_approved_xgboost_artifact",
        }
    else:
        impurity_ranking = impurity["ranking"]
        summary["feature_importance_stability"] = {
            **_standard_deviation_summary(impurity_ranking),
            "shap_rank_spearman": _number(
                _spearman_rank_correlation(impurity_ranking, shap)
            ),
            "permutation_rank_spearman": _number(
                _spearman_rank_correlation(
                    impurity_ranking,
                    permutation,
                )
            ),
        }
    return summary


def _standard_deviation_summary(
    ranking: list[dict[str, Any]],
) -> dict[str, Any]:
    values = [
        Decimal(item["standard_deviation"])
        for item in ranking
        if item.get("standard_deviation") is not None
    ]
    if not values:
        return {
            "status": "source_artifact_has_no_variability_values",
            "count": 0,
        }
    return {
        "status": "reported_from_source_artifact",
        "count": len(values),
        "mean_standard_deviation": _number(_mean(tuple(values))),
        "minimum_standard_deviation": _number(min(values)),
        "maximum_standard_deviation": _number(max(values)),
    }


def _spearman_rank_correlation(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> Decimal:
    first_ranks = {
        item["feature_name"]: int(item["rank"]) for item in first
    }
    second_ranks = {
        item["feature_name"]: int(item["rank"]) for item in second
    }
    if set(first_ranks) != set(second_ranks) or len(first_ranks) < 2:
        raise FinalModelSelectionError(
            "Explainability rankings contain different features."
        )
    n = Decimal(len(first_ranks))
    squared_differences = sum(
        Decimal(
            (first_ranks[name] - second_ranks[name]) ** 2
        )
        for name in first_ranks
    )
    return Decimal(1) - (
        Decimal(6) * squared_differences / (n * (n * n - Decimal(1)))
    )


def _validate_artifacts(
    artifacts: tuple[ImmutableArtifact, ...],
    explainability: tuple[ImmutableArtifact, ...],
    predictions: tuple[PredictionEvidenceSummary, ...],
    tests: AutomatedTestEvidence,
) -> None:
    expected_types = {
        "model_comparison_report",
        "statistical_validation_report",
        "residual_diagnostics_report",
        "market_regime_analysis_report",
    }
    if (
        {item.artifact_type for item in artifacts} != expected_types
        or any(item.report_version != "1.0.0" for item in artifacts)
        or any(not item.hash_verified for item in artifacts)
    ):
        raise FinalModelSelectionError(
            "Required immutable report artifacts are incomplete."
        )
    if (
        len(explainability) != 2
        or {
            item.payload.get("model_family") for item in explainability
        }
        != {"random_forest_regression", "xgboost_regression"}
        or any(item.report_version != "1.0.0" for item in explainability)
        or any(not item.hash_verified for item in explainability)
    ):
        raise FinalModelSelectionError(
            "Approved explainability evidence is incomplete."
        )
    if (
        {item.model_family for item in predictions}
        != set(MODEL_FAMILY_ORDER)
        or any(
            not item.hashes_verified
            or item.observation_count <= 0
            or item.prediction_hash_count <= 0
            or len(item.evidence_set_hash) != 64
            for item in predictions
        )
    ):
        raise FinalModelSelectionError(
            "Immutable prediction evidence is incomplete."
        )
    if tests.status != "passed" or tests.tests_run <= 0:
        raise FinalModelSelectionError(
            "The automated test evidence does not pass."
        )


def _validated_provenance(
    models: dict[str, dict[str, Any]],
    statistical: dict[str, Any],
    residual: dict[str, Any],
    regime: dict[str, Any],
    explainability: tuple[ImmutableArtifact, ...],
) -> dict[str, Any]:
    expected = statistical["provenance"]
    if expected != residual["provenance"] or expected != regime["provenance"]:
        raise FinalModelSelectionError("Source report provenance differs.")
    for family, model in models.items():
        if (
            model["dataset_hash"] != expected["model_dataset_hash"]
            or model["feature_pipeline_version"]
            != expected["feature_pipeline_version"]
            or model["target_version"] != expected["target_version"]
            or model["validation_run_id"]
            != expected["validation_run_id"]
            or model["split_hash"] != expected["split_hash"]
        ):
            raise FinalModelSelectionError(
                f"{family} comparison provenance differs."
            )
    for artifact in explainability:
        source = artifact.payload["provenance"]
        if any(
            source[key] != expected[key]
            for key in (
                "model_dataset_hash",
                "feature_pipeline_version",
                "target_version",
                "validation_run_id",
                "split_hash",
            )
        ):
            raise FinalModelSelectionError(
                "Explainability provenance differs."
            )
    if (
        statistical["verification"]["final_holdout_evaluated"]
        or residual["verification"]["final_holdout_evaluated"]
        or regime["verification"]["final_holdout_evaluated"]
    ):
        raise FinalModelSelectionError(
            "A source artifact evaluated the final holdout."
        )
    if (
        not residual["verification"]["deterministic_replay_performed"]
        or residual["verification"]["experiment_records_modified"]
        or residual["verification"]["model_tuning_performed"]
    ):
        raise FinalModelSelectionError(
            "Deterministic replay integrity evidence differs."
        )
    return dict(expected)


def _comparison_models(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    models = {item["model_family"]: item for item in payload["models"]}
    if (
        set(models) != set(MODEL_FAMILY_ORDER)
        or payload["model_count"] != 4
        or payload["final_holdout_evaluated"]
    ):
        raise FinalModelSelectionError(
            "Approved model comparison evidence differs."
        )
    return models


def _artifact_reference(
    artifact: ImmutableArtifact,
) -> dict[str, Any]:
    return {
        "artifact_id": str(artifact.artifact_id),
        "artifact_type": artifact.artifact_type,
        "report_version": artifact.report_version,
        "configuration_hash": artifact.configuration_hash,
        "result_hash": artifact.result_hash,
        "hash_verified": artifact.hash_verified,
    }


def sha256_json(value: object) -> str:
    """Return the canonical report hash used by immutable source artifacts."""
    return _sha256_json(value)


def sha256_lines(values: tuple[str, ...]) -> str:
    """Return the canonical ordered-set hash used by prediction evidence."""
    digest = sha256()
    for value in values:
        digest.update((value + "\n").encode())
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

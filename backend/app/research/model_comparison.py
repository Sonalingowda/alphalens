"""Deterministic comparison of approved regression experiments."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any
from uuid import UUID


MODEL_COMPARISON_REPORT_VERSION = "1.0.0"
APPROVED_EVALUATION_POLICY_VERSION = "1.1.0"
RUNTIME_EVIDENCE_STATUS = "not_recorded_by_source_experiments"


@dataclass(frozen=True, slots=True)
class ComparisonSource:
    experiment_id: UUID
    model_family: str
    model_parameters: dict[str, Any]
    evaluation_policy_version: str
    training_pipeline_version: str
    feature_pipeline_version: str
    target_version: str
    model_dataset_hash: str
    validation_run_id: UUID
    split_hash: str
    evaluated_split_count: int
    skipped_split_count: int
    evaluated_observation_count: int
    mae: Decimal
    rmse: Decimal
    directional_accuracy: Decimal
    configuration_hash: str
    result_hash: str
    exact_matching_experiment_count: int


@dataclass(frozen=True, slots=True)
class BuiltModelComparison:
    payload: dict[str, Any]
    report_hash: str


def build_model_comparison(
    sources: tuple[ComparisonSource, ...],
) -> BuiltModelComparison:
    """Build a deterministic report without interpreting performance."""
    if len(sources) != 4:
        raise ValueError("Exactly four approved baselines are required.")
    families = tuple(source.model_family for source in sources)
    if len(set(families)) != len(families):
        raise ValueError("Approved baseline model families must be unique.")

    rankings = {
        "mae": _rank(sources, "mae", descending=False),
        "rmse": _rank(sources, "rmse", descending=False),
        "directional_accuracy": _rank(
            sources,
            "directional_accuracy",
            descending=True,
        ),
    }
    rank_lookup = {
        metric: {
            item["model_family"]: item["rank"]
            for item in ranking
        }
        for metric, ranking in rankings.items()
    }

    models: list[dict[str, Any]] = []
    for source in sorted(sources, key=lambda item: item.model_family):
        model_ranks = {
            metric: rank_lookup[metric][source.model_family]
            for metric in rankings
        }
        repeatability_verified = (
            source.exact_matching_experiment_count >= 2
        )
        models.append(
            {
                "experiment_id": str(source.experiment_id),
                "model_family": source.model_family,
                "parameter_set": source.model_parameters,
                "evaluation_policy_version": (
                    source.evaluation_policy_version
                ),
                "training_pipeline_version": (
                    source.training_pipeline_version
                ),
                "feature_pipeline_version": (
                    source.feature_pipeline_version
                ),
                "target_version": source.target_version,
                "dataset_hash": source.model_dataset_hash,
                "validation_run_id": str(source.validation_run_id),
                "split_hash": source.split_hash,
                "evaluated_split_count": source.evaluated_split_count,
                "skipped_split_count": source.skipped_split_count,
                "evaluated_observation_count": (
                    source.evaluated_observation_count
                ),
                "metrics": {
                    "mae": format(source.mae, "f"),
                    "rmse": format(source.rmse, "f"),
                    "directional_accuracy": format(
                        source.directional_accuracy,
                        "f",
                    ),
                },
                "runtime": {
                    "seconds": None,
                    "status": RUNTIME_EVIDENCE_STATUS,
                },
                "deterministic_repeatability": {
                    "status": (
                        "verified"
                        if repeatability_verified
                        else "not_verified_from_registry"
                    ),
                    "exact_matching_experiment_count": (
                        source.exact_matching_experiment_count
                    ),
                },
                "configuration_hash": source.configuration_hash,
                "result_hash": source.result_hash,
                "ranks": model_ranks,
                "measured_evidence_summary": _evidence_summary(
                    model_ranks,
                    repeatability_verified,
                ),
            }
        )

    payload: dict[str, Any] = {
        "report_version": MODEL_COMPARISON_REPORT_VERSION,
        "scope": "approved_development_baseline_comparison",
        "model_count": len(models),
        "models": models,
        "rankings": rankings,
        "ranking_rules": {
            "mae": "ascending",
            "rmse": "ascending",
            "directional_accuracy": "descending",
            "tie_breaker": "model_family_ascending",
        },
        "runtime_evidence_status": RUNTIME_EVIDENCE_STATUS,
        "final_holdout_evaluated": False,
        "model_selection_performed": False,
        "statistical_significance_testing_performed": False,
    }
    return BuiltModelComparison(
        payload=payload,
        report_hash=_sha256_json(payload),
    )


def _rank(
    sources: tuple[ComparisonSource, ...],
    metric: str,
    *,
    descending: bool,
) -> list[dict[str, Any]]:
    ordered = sorted(
        sources,
        key=lambda source: (
            -getattr(source, metric)
            if descending
            else getattr(source, metric),
            source.model_family,
        ),
    )
    return [
        {
            "rank": index,
            "experiment_id": str(source.experiment_id),
            "model_family": source.model_family,
            "value": format(getattr(source, metric), "f"),
        }
        for index, source in enumerate(ordered, start=1)
    ]


def _evidence_summary(
    ranks: dict[str, int],
    repeatability_verified: bool,
) -> dict[str, list[str]]:
    strengths = [
        f"{metric} ranked {rank} of 4"
        for metric, rank in ranks.items()
        if rank <= 2
    ]
    if repeatability_verified:
        strengths.append(
            "Exact configuration and result hashes were independently "
            "repeated"
        )
    limitations = [
        f"{metric} ranked {rank} of 4"
        for metric, rank in ranks.items()
        if rank >= 3
    ]
    if not repeatability_verified:
        limitations.append(
            "No second registry record has both the same configuration "
            "and result hash"
        )
    limitations.append("Historical runtime was not recorded")
    return {
        "relative_strengths": strengths,
        "relative_limitations": limitations,
    }


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

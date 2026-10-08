import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.persistence.research_cycle_lineage import (
    EXPLAINABILITY_MODEL_FAMILIES,
    MODEL_FAMILIES,
    current_cycle_explainability,
    current_cycle_experiments,
)


class _ScalarResult:
    def __init__(self, records):
        self.records = records

    def all(self):
        return self.records


class _Session:
    def __init__(self, records):
        self.records = records

    async def scalars(self, _statement):
        return _ScalarResult(self.records)


def _dataset():
    return SimpleNamespace(
        model_dataset_hash="new-cycle-dataset-hash",
        validation_run_id=uuid4(),
        validation_split_hash="new-cycle-split-hash",
    )


def _experiment(family):
    return SimpleNamespace(
        id=uuid4(),
        model_family=family,
        model_dataset_hash="new-cycle-dataset-hash",
        validation_run_id=None,
        split_hash="new-cycle-split-hash",
        point_in_time_validated=True,
        final_holdout_evaluated=False,
    )


def test_experiments_resolve_to_fresh_dataset_cycle_ids():
    dataset = _dataset()
    experiments = tuple(_experiment(family) for family in MODEL_FAMILIES)
    for experiment in experiments:
        experiment.validation_run_id = dataset.validation_run_id

    resolved = asyncio.run(
        current_cycle_experiments(_Session(experiments), dataset)
    )

    assert tuple(item.model_family for item in resolved) == MODEL_FAMILIES
    assert {item.id for item in resolved} == {item.id for item in experiments}


def test_experiment_resolution_rejects_incomplete_or_ambiguous_cycle():
    dataset = _dataset()
    records = tuple(_experiment(family) for family in MODEL_FAMILIES[:-1])

    with pytest.raises(ValueError, match="incomplete or ambiguous"):
        asyncio.run(current_cycle_experiments(_Session(records), dataset))


def test_explainability_resolves_by_current_cycle_experiment_lineage():
    experiments = tuple(_experiment(family) for family in MODEL_FAMILIES)
    artifacts = tuple(
        SimpleNamespace(
            id=uuid4(),
            model_family=family,
            experiment_id=next(
                item.id for item in experiments if item.model_family == family
            ),
            model_dataset_hash="new-cycle-dataset-hash",
            validation_run_id=None,
            split_hash="new-cycle-split-hash",
            final_holdout_evaluated=False,
        )
        for family in EXPLAINABILITY_MODEL_FAMILIES
    )
    for artifact in artifacts:
        artifact.validation_run_id = experiments[0].validation_run_id

    resolved = asyncio.run(
        current_cycle_explainability(_Session(artifacts), experiments)
    )

    assert {item.id for item in resolved} == {item.id for item in artifacts}


def test_explainability_rejects_artifact_from_another_experiment():
    experiments = tuple(_experiment(family) for family in MODEL_FAMILIES)
    artifacts = tuple(
        SimpleNamespace(
            id=uuid4(),
            model_family=family,
            experiment_id=uuid4(),
            model_dataset_hash="new-cycle-dataset-hash",
            validation_run_id=None,
            split_hash="new-cycle-split-hash",
            final_holdout_evaluated=False,
        )
        for family in EXPLAINABILITY_MODEL_FAMILIES
    )

    with pytest.raises(ValueError, match="provenance differs"):
        asyncio.run(
            current_cycle_explainability(_Session(artifacts), experiments)
        )

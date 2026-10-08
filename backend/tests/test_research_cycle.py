from datetime import datetime, timezone
import asyncio
from functools import wraps
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

from app.persistence import research_cycle
from app.persistence.research_cycle_lineage import MODEL_FAMILIES
from app.validation.splits import WalkForwardConfig


def run_async(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def _ids() -> dict[str, object]:
    return {
        "batch": uuid4(),
        "feature": uuid4(),
        "target": uuid4(),
        "validation": uuid4(),
        "experiments": {family: uuid4() for family in MODEL_FAMILIES},
        "explainability": {
            "random_forest_regression": uuid4(),
            "xgboost_regression": uuid4(),
        },
        "statistical": uuid4(),
        "comparison": uuid4(),
        "residual": uuid4(),
        "market": uuid4(),
        "selection": uuid4(),
        "holdout": uuid4(),
        "packaged": uuid4(),
    }


@run_async
async def test_research_cycle_uses_canonical_order_and_summary() -> None:
    ids = _ids()
    session = object()
    batch = SimpleNamespace(id=ids["batch"], source_data_hash="cycle-hash")
    candle_summary = SimpleNamespace(
        row_count=720,
        date_range_start=datetime(2024, 10, 11, tzinfo=timezone.utc),
        date_range_end=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    dataset = object()
    events: list[str] = []

    async def stage(name: str, result: object):
        events.append(name)
        return result

    async def features(*_args):
        return await stage("features", SimpleNamespace(id=ids["feature"]))

    async def targets(*_args):
        return await stage("targets", SimpleNamespace(id=ids["target"]))

    async def validation(*_args):
        return await stage("validation", SimpleNamespace(id=ids["validation"]))

    async def baselines(*_args):
        return await stage(
            "baselines",
            tuple(
                SimpleNamespace(id=value, model_family=family)
                for family, value in ids["experiments"].items()
            ),
        )

    async def explainability(*args):
        family = args[1]
        return await stage(
            f"explainability:{family}",
            SimpleNamespace(artifact_id=ids["explainability"][family]),
        )

    async def statistical(*_args):
        return await stage("statistical", SimpleNamespace(report_id=ids["statistical"]))

    async def comparison(*_args):
        return await stage("comparison", SimpleNamespace(report_id=ids["comparison"]))

    async def residual(*_args):
        return await stage("residual", SimpleNamespace(report_id=ids["residual"]))

    async def market(*_args):
        return await stage("market", SimpleNamespace(report_id=ids["market"]))

    async def selection(*_args, **_kwargs):
        return await stage("selection", SimpleNamespace(report_id=ids["selection"]))

    async def holdout(*_args):
        return await stage("holdout", SimpleNamespace(report_id=ids["holdout"]))

    async def packaging(*_args):
        return await stage("packaging", SimpleNamespace(artifact_id=ids["packaged"]))

    with (
        patch.object(
            research_cycle,
            "_verify_market_candle_input",
            AsyncMock(return_value=(batch, candle_summary)),
        ),
        patch.object(
            research_cycle,
            "_ensure_feature_run",
                AsyncMock(side_effect=features),
        ),
        patch.object(
            research_cycle,
            "_ensure_target_run",
                AsyncMock(side_effect=targets),
        ),
        patch.object(
            research_cycle,
            "_ensure_validation_run",
                AsyncMock(side_effect=validation),
        ),
        patch.object(
            research_cycle,
            "build_model_ready_dataset",
            AsyncMock(return_value=dataset),
        ) as dataset_builder,
        patch.object(
            research_cycle,
            "_ensure_baseline_experiments",
            AsyncMock(side_effect=baselines),
        ) as baseline_runner,
        patch.object(
            research_cycle,
            "create_explainability_artifact",
                AsyncMock(side_effect=explainability),
        ),
        patch.object(
            research_cycle,
            "create_statistical_validation_report",
            AsyncMock(side_effect=statistical),
        ),
        patch.object(
            research_cycle,
            "create_model_comparison_report",
            AsyncMock(side_effect=comparison),
        ),
        patch.object(
            research_cycle,
            "create_residual_diagnostics_report",
            AsyncMock(side_effect=residual),
        ),
        patch.object(
            research_cycle,
            "create_market_regime_report",
            AsyncMock(side_effect=market),
        ),
        patch.object(
            research_cycle,
            "create_final_model_selection_report",
            AsyncMock(side_effect=selection),
        ),
        patch.object(
            research_cycle,
            "create_official_holdout_evaluation_report",
            AsyncMock(side_effect=holdout),
        ),
        patch.object(
            research_cycle,
            "package_selected_ridge_inference_once",
            AsyncMock(side_effect=packaging),
        ),
    ):
        summary = await research_cycle.run_research_cycle(
            session,
            validation_config=WalkForwardConfig(),
            test_evidence=object(),
            stop_after="packaging",
            authorize_holdout=True,
        )

    assert events == [
        "features",
        "targets",
        "validation",
        "baselines",
        "explainability:random_forest_regression",
        "explainability:xgboost_regression",
        "statistical",
        "comparison",
        "residual",
        "market",
        "selection",
        "holdout",
        "packaging",
    ]
    assert summary.status == "succeeded"
    assert summary.final_stage == "ridge_inference_packaging"
    assert summary.research_cycle_id == f"{ids['batch']}:cycle-hash"
    assert summary.experiment_ids == ids["experiments"]
    assert summary.official_holdout_report_id == ids["holdout"]
    assert summary.packaged_artifact_id == ids["packaged"]
    assert summary.as_dict()["packaged_artifact_id"] == str(ids["packaged"])
    dataset_builder.assert_awaited_once_with(session)
    baseline_runner.assert_awaited_once_with(session, dataset)


@run_async
async def test_failure_stops_downstream_stages() -> None:
    batch = SimpleNamespace(id=uuid4(), source_data_hash="hash")
    candles = SimpleNamespace(row_count=720, date_range_start=None, date_range_end=None)
    downstream = AsyncMock()

    with (
        patch.object(research_cycle, "_verify_market_candle_input", AsyncMock(return_value=(batch, candles))),
        patch.object(
            research_cycle,
            "_ensure_feature_run",
            AsyncMock(side_effect=ValueError("feature gate failed")),
        ),
        patch.object(research_cycle, "_ensure_target_run", downstream),
    ):
        summary = await research_cycle.run_research_cycle(
            object(),
            validation_config=WalkForwardConfig(),
            test_evidence=object(),
        )

    assert summary.status == "failed"
    assert summary.failure_stage == "feature_persistence"
    assert summary.failure_reason == "ValueError: feature gate failed"
    downstream.assert_not_awaited()


@run_async
async def test_default_stops_after_final_selection_without_holdout_or_artifact() -> None:
    source = await _success_patches()
    try:
        summary = await research_cycle.run_research_cycle(
            object(),
            validation_config=WalkForwardConfig(),
            test_evidence=object(),
        )
        assert summary.status == "succeeded"
        assert summary.final_stage == "final_model_selection"
        assert summary.final_selection_report_id is not None
        assert summary.official_holdout_report_id is None
        assert summary.packaged_artifact_id is None
        assert source["holdout"].await_count == 0
        assert source["packaging"].await_count == 0
    finally:
        for patcher in source["patchers"]:
            patcher.stop()


@run_async
async def test_holdout_requires_explicit_authorization() -> None:
    summary = await research_cycle.run_research_cycle(
        object(),
        validation_config=WalkForwardConfig(),
        test_evidence=object(),
        stop_after="official_holdout",
    )

    assert summary.status == "failed"
    assert summary.failure_stage == "holdout_authorization"
    assert summary.official_holdout_report_id is None
    assert summary.packaged_artifact_id is None


@run_async
async def test_stop_after_experiments_does_not_run_diagnostics() -> None:
    source = await _success_patches()
    try:
        summary = await research_cycle.run_research_cycle(
            object(),
            validation_config=WalkForwardConfig(),
            test_evidence=object(),
            stop_after="experiments",
        )
        assert summary.status == "succeeded"
        assert summary.final_stage == "baseline_experiments"
        assert source["holdout"].await_count == 0
        assert source["packaging"].await_count == 0
    finally:
        for patcher in source["patchers"]:
            patcher.stop()


@run_async
async def test_existing_feature_target_and_validation_are_reused() -> None:
    batch_id = uuid4()
    feature_id = uuid4()
    target_id = uuid4()
    validation_id = uuid4()
    batch = SimpleNamespace(id=batch_id)
    feature = SimpleNamespace(id=feature_id)
    target = SimpleNamespace(id=target_id)
    config = WalkForwardConfig()
    validation_record = SimpleNamespace(
        id=validation_id,
        minimum_train_size=config.minimum_train_size,
        test_size=config.test_size,
        step_size=config.step_size,
        purge_gap_size=config.purge_gap_size,
        final_holdout_size=config.final_holdout_size,
    )
    session = Mock()

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def one_or_none(self):
            return self.value

    session.scalars = AsyncMock(side_effect=[ScalarResult(target), ScalarResult(validation_record)])
    session.get = AsyncMock(return_value=target)

    with (
        patch.object(research_cycle, "get_active_feature_run", AsyncMock(return_value=feature)),
        patch.object(research_cycle, "compute_and_persist_features", AsyncMock()) as compute,
        patch.object(research_cycle, "generate_and_persist_forward_log_returns", AsyncMock()) as generate,
        patch.object(research_cycle, "get_validation_run", AsyncMock(return_value=SimpleNamespace(id=validation_id))) as load_validation,
        patch.object(research_cycle, "create_validation_run", AsyncMock()) as create_validation,
    ):
        resolved_feature = await research_cycle._ensure_feature_run(session, batch)
        resolved_target = await research_cycle._ensure_target_run(session, batch, feature_id)
        resolved_validation = await research_cycle._ensure_validation_run(
            session, batch, feature_id, config
        )

    assert resolved_feature is feature
    assert resolved_target is target
    assert resolved_validation.id == validation_id
    compute.assert_not_awaited()
    generate.assert_not_awaited()
    create_validation.assert_not_awaited()
    load_validation.assert_awaited_once_with(session, validation_id)


@run_async
async def test_packaging_is_after_holdout_and_invoked_once() -> None:
    source = (await _success_patches())
    try:
        summary = await research_cycle.run_research_cycle(
            object(),
            validation_config=WalkForwardConfig(),
            test_evidence=object(),
            stop_after="packaging",
            authorize_holdout=True,
        )
        assert source["holdout"].await_count == 1
        assert source["packaging"].await_count == 1
        assert source["events"].index("holdout") < source["events"].index("packaging")
        assert summary.packaged_artifact_id is not None
    finally:
        for patcher in source["patchers"]:
            patcher.stop()


async def _success_patches() -> dict[str, object]:
    """Install a compact success path for the packaging gate test."""
    ids = _ids()
    batch = SimpleNamespace(id=ids["batch"], source_data_hash="fresh")
    candles = SimpleNamespace(row_count=720, date_range_start=None, date_range_end=None)
    events: list[str] = []
    patchers = [
        patch.object(research_cycle, "_verify_market_candle_input", AsyncMock(return_value=(batch, candles))),
        patch.object(research_cycle, "_ensure_feature_run", AsyncMock(return_value=SimpleNamespace(id=ids["feature"]))),
        patch.object(research_cycle, "_ensure_target_run", AsyncMock(return_value=SimpleNamespace(id=ids["target"]))),
        patch.object(research_cycle, "_ensure_validation_run", AsyncMock(return_value=SimpleNamespace(id=ids["validation"]))),
        patch.object(research_cycle, "build_model_ready_dataset", AsyncMock(return_value=object())),
        patch.object(research_cycle, "_ensure_baseline_experiments", AsyncMock(return_value=tuple(SimpleNamespace(id=value, model_family=family) for family, value in ids["experiments"].items()))),
    ]
    for name, value in (("create_explainability_artifact", SimpleNamespace(artifact_id=uuid4())),):
        patchers.append(patch.object(research_cycle, name, AsyncMock(return_value=value)))
    for name in (
        "create_statistical_validation_report",
        "create_model_comparison_report",
        "create_residual_diagnostics_report",
        "create_market_regime_report",
        "create_final_model_selection_report",
    ):
        patchers.append(patch.object(research_cycle, name, AsyncMock(return_value=SimpleNamespace(report_id=uuid4()))))
    async def holdout_side_effect(*_args, **_kwargs):
        events.append("holdout")
        return SimpleNamespace(report_id=uuid4())

    async def packaging_side_effect(*_args, **_kwargs):
        events.append("packaging")
        return SimpleNamespace(artifact_id=ids["packaged"])

    holdout_mock = AsyncMock(side_effect=holdout_side_effect)
    packaging_mock = AsyncMock(side_effect=packaging_side_effect)
    holdout = patch.object(research_cycle, "create_official_holdout_evaluation_report", holdout_mock)
    packaging = patch.object(research_cycle, "package_selected_ridge_inference_once", packaging_mock)
    patchers.extend((holdout, packaging))
    for patcher in patchers:
        patcher.start()
    return {
        "patchers": patchers,
        "holdout": holdout_mock,
        "packaging": packaging_mock,
        "events": events,
    }

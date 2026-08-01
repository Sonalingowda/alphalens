"""Structured deterministic audit logging for pipeline outcomes."""

import logging

from app.opportunity_intelligence.orchestration import PipelineRunResult


def log_pipeline_result(
    logger: logging.Logger,
    result: PipelineRunResult,
) -> None:
    """Emit one immutable trace summary without exposing mutable runtime state."""
    logger.info(
        "Opportunity Intelligence pipeline completed.",
        extra={
            "contract_version": "1.0.0",
            "pipeline_run_id": result.run_id,
            "pipeline_outcome": result.outcome.value,
            "pipeline_trace_hash": result.trace_hash,
            "pipeline_stage_count": len(result.stages),
            "pipeline_stages": tuple(stage.stage.value for stage in result.stages),
        },
    )

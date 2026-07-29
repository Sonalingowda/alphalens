"""Deterministic five-observation forward log-return target."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json

from app.market_data.models import Candle


TARGET_NAME = "forward_log_return"
TARGET_VERSION = "1.0.0"
TARGET_HORIZON = 5
TARGET_VALUE_QUANTUM = Decimal("0.000000000000000001")
TARGET_DEFINITION_HASH = sha256(
    json.dumps(
        {
            "formula": "ln(C[t+H]/C[t])",
            "horizon_observations": TARGET_HORIZON,
            "logarithm_base": "e",
            "information_cutoff": "completed_candle_t",
            "label_availability": "completed_candle_t_plus_h",
            "numeric_quantum": format(TARGET_VALUE_QUANTUM, "f"),
            "execution_convention": (
                "strictly_after_prediction_generation_no_same_close"
            ),
            "target_name": TARGET_NAME,
            "target_version": TARGET_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()


class TargetGenerationError(ValueError):
    """Raised when defensible target generation is not possible."""


@dataclass(frozen=True, slots=True)
class ForwardLogReturnLabel:
    prediction_timestamp: datetime
    label_available_at: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class TargetExclusion:
    prediction_timestamp: datetime
    code: str


@dataclass(frozen=True, slots=True)
class ForwardLogReturnResult:
    target_name: str
    target_version: str
    target_definition_hash: str
    horizon: int
    labels: tuple[ForwardLogReturnLabel, ...]
    exclusions: tuple[TargetExclusion, ...]
    point_in_time_validated: bool


@dataclass(frozen=True, slots=True)
class _ClosePoint:
    timestamp: datetime
    close: Decimal


def generate_forward_log_return_targets(
    candles: tuple[Candle, ...],
) -> ForwardLogReturnResult:
    """Generate labels only when the complete forward horizon is available."""
    points = _validated_close_points(candles)
    labels, exclusions = _compute(points)
    _verify_prefix_invariance(points, labels)

    return ForwardLogReturnResult(
        target_name=TARGET_NAME,
        target_version=TARGET_VERSION,
        target_definition_hash=TARGET_DEFINITION_HASH,
        horizon=TARGET_HORIZON,
        labels=labels,
        exclusions=exclusions,
        point_in_time_validated=True,
    )


def _validated_close_points(
    candles: tuple[Candle, ...],
) -> tuple[_ClosePoint, ...]:
    if not candles:
        raise TargetGenerationError("Target generation requires candle input.")

    points: list[_ClosePoint] = []
    previous_timestamp: datetime | None = None
    for candle in candles:
        timestamp = candle.timestamp
        close = candle.close
        if timestamp is None or close is None:
            raise TargetGenerationError(
                "Target input contains a missing timestamp or close."
            )
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise TargetGenerationError(
                "Target input timestamps must be timezone-aware."
            )
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise TargetGenerationError(
                "Target input timestamps must be strictly chronological."
            )
        if not close.is_finite() or close <= 0:
            raise TargetGenerationError(
                f"Target input contains an invalid close at "
                f"{timestamp.isoformat()}."
            )
        points.append(_ClosePoint(timestamp=timestamp, close=close))
        previous_timestamp = timestamp
    return tuple(points)


def _compute(
    points: tuple[_ClosePoint, ...],
) -> tuple[
    tuple[ForwardLogReturnLabel, ...],
    tuple[TargetExclusion, ...],
]:
    labels: list[ForwardLogReturnLabel] = []
    exclusions: list[TargetExclusion] = []
    final_eligible_index = len(points) - TARGET_HORIZON

    for index, point in enumerate(points):
        if index >= final_eligible_index:
            exclusions.append(
                TargetExclusion(
                    prediction_timestamp=point.timestamp,
                    code="insufficient_forward_horizon",
                )
            )
            continue

        future = points[index + TARGET_HORIZON]
        labels.append(
            ForwardLogReturnLabel(
                prediction_timestamp=point.timestamp,
                label_available_at=future.timestamp,
                value=_forward_log_return(point.close, future.close),
            )
        )

    return tuple(labels), tuple(exclusions)


def _forward_log_return(current: Decimal, future: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        value = (future / current).ln()
        if not value.is_finite():
            raise TargetGenerationError(
                "Forward log-return computation produced a non-finite value."
            )
        return value.quantize(
            TARGET_VALUE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _verify_prefix_invariance(
    points: tuple[_ClosePoint, ...],
    full_labels: tuple[ForwardLogReturnLabel, ...],
) -> None:
    """Prove a label never depends on data after its availability timestamp."""
    for prefix_length in range(1, len(points) + 1):
        prefix_labels, _ = _compute(points[:prefix_length])
        prefix_end = points[prefix_length - 1].timestamp
        expected = tuple(
            label
            for label in full_labels
            if label.label_available_at <= prefix_end
        )
        if prefix_labels != expected:
            raise TargetGenerationError(
                "Forward log-return target failed point-in-time prefix "
                f"invariance at input position {prefix_length}."
            )

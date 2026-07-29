"""Deterministic expanding-window validation with purge and holdout controls."""

from dataclasses import dataclass
from datetime import datetime


class ValidationConfigurationError(ValueError):
    """Raised when a chronological validation plan cannot be constructed."""


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    minimum_train_size: int = 20
    test_size: int = 5
    step_size: int = 5
    purge_gap_size: int = 50
    final_holdout_size: int = 10


@dataclass(frozen=True, slots=True)
class TimestampRange:
    start: datetime
    end: datetime
    observation_count: int


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    sequence: int
    train: TimestampRange
    purge_gap: TimestampRange
    test: TimestampRange


@dataclass(frozen=True, slots=True)
class WalkForwardPlan:
    strategy: str
    config: WalkForwardConfig
    source_observation_count: int
    development_range: TimestampRange
    final_holdout_range: TimestampRange
    splits: tuple[ChronologicalSplit, ...]


@dataclass(frozen=True, slots=True)
class LookbackSeparation:
    split_sequence: int
    train_end: datetime
    first_test_timestamp: datetime
    earliest_first_test_feature_input: datetime
    max_feature_window: int
    passed: bool


def generate_development_splits(
    timestamps: tuple[datetime, ...],
    config: WalkForwardConfig,
) -> WalkForwardPlan:
    """Generate expanding splits while excluding the final holdout."""
    _validate_timestamps(timestamps)
    _validate_config(config)

    development_size = len(timestamps) - config.final_holdout_size
    required_size = (
        config.minimum_train_size
        + config.purge_gap_size
        + config.test_size
    )
    if development_size < required_size:
        raise ValidationConfigurationError(
            "Insufficient development observations for one complete "
            "train, purge, and test split."
        )

    splits: list[ChronologicalSplit] = []
    train_end_exclusive = config.minimum_train_size
    sequence = 1
    while True:
        test_start = train_end_exclusive + config.purge_gap_size
        test_end_exclusive = test_start + config.test_size
        if test_end_exclusive > development_size:
            break

        splits.append(
            ChronologicalSplit(
                sequence=sequence,
                train=_range(timestamps, 0, train_end_exclusive),
                purge_gap=_range(
                    timestamps,
                    train_end_exclusive,
                    test_start,
                ),
                test=_range(
                    timestamps,
                    test_start,
                    test_end_exclusive,
                ),
            )
        )
        train_end_exclusive += config.step_size
        sequence += 1

    return WalkForwardPlan(
        strategy="expanding_walk_forward",
        config=config,
        source_observation_count=len(timestamps),
        development_range=_range(timestamps, 0, development_size),
        final_holdout_range=_range(
            timestamps,
            development_size,
            len(timestamps),
        ),
        splits=tuple(splits),
    )


def verify_lookback_separation(
    timestamps: tuple[datetime, ...],
    plan: WalkForwardPlan,
    max_feature_window: int,
) -> tuple[LookbackSeparation, ...]:
    """Verify the first test feature window cannot overlap training data."""
    _validate_timestamps(timestamps)
    if plan.source_observation_count != len(timestamps):
        raise ValidationConfigurationError(
            "Validation plan and timestamp source do not match."
        )
    if max_feature_window <= 0:
        raise ValidationConfigurationError(
            "Maximum feature window must be positive."
        )
    if plan.config.purge_gap_size < max_feature_window:
        raise ValidationConfigurationError(
            "Purge gap must be at least the maximum feature window."
        )

    indexes = {timestamp: index for index, timestamp in enumerate(timestamps)}
    results: list[LookbackSeparation] = []
    for split in plan.splits:
        first_test_index = indexes[split.test.start]
        earliest_input_index = first_test_index - (max_feature_window - 1)
        if earliest_input_index < 0:
            raise ValidationConfigurationError(
                "Test boundary lacks the required feature lookback."
            )
        earliest_input = timestamps[earliest_input_index]
        results.append(
            LookbackSeparation(
                split_sequence=split.sequence,
                train_end=split.train.end,
                first_test_timestamp=split.test.start,
                earliest_first_test_feature_input=earliest_input,
                max_feature_window=max_feature_window,
                passed=(
                    split.train.end < earliest_input <= split.test.start
                ),
            )
        )

    if not all(result.passed for result in results):
        raise ValidationConfigurationError(
            "Feature lookback overlaps a training boundary."
        )
    return tuple(results)


def access_final_holdout(
    timestamps: tuple[datetime, ...],
    config: WalkForwardConfig,
    *,
    acknowledge_final_evaluation: bool = False,
) -> tuple[datetime, ...]:
    """Return holdout timestamps only through an explicit final-evaluation call."""
    _validate_timestamps(timestamps)
    _validate_config(config)
    if config.final_holdout_size >= len(timestamps):
        raise ValidationConfigurationError(
            "Final holdout must leave development observations."
        )
    if not acknowledge_final_evaluation:
        raise PermissionError(
            "Final holdout access requires explicit final-evaluation "
            "acknowledgement."
        )
    return timestamps[-config.final_holdout_size :]


def _validate_config(config: WalkForwardConfig) -> None:
    positive_values = (
        config.minimum_train_size,
        config.test_size,
        config.step_size,
        config.final_holdout_size,
    )
    if any(value <= 0 for value in positive_values):
        raise ValidationConfigurationError(
            "Train, test, step, and holdout sizes must be positive."
        )
    if config.purge_gap_size < 0:
        raise ValidationConfigurationError(
            "Purge gap size cannot be negative."
        )
    if config.step_size < config.test_size:
        raise ValidationConfigurationError(
            "Step size must be at least the test size to avoid overlapping "
            "evaluation windows."
        )


def _validate_timestamps(timestamps: tuple[datetime, ...]) -> None:
    if not timestamps:
        raise ValidationConfigurationError(
            "Chronological validation requires timestamps."
        )
    previous: datetime | None = None
    for timestamp in timestamps:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValidationConfigurationError(
                "Validation timestamps must be timezone-aware."
            )
        if previous is not None and timestamp <= previous:
            raise ValidationConfigurationError(
                "Validation timestamps must be strictly chronological "
                "and unique."
            )
        previous = timestamp


def _range(
    timestamps: tuple[datetime, ...],
    start_index: int,
    end_exclusive: int,
) -> TimestampRange:
    if start_index >= end_exclusive:
        raise ValidationConfigurationError(
            "Validation ranges must contain observations."
        )
    return TimestampRange(
        start=timestamps[start_index],
        end=timestamps[end_exclusive - 1],
        observation_count=end_exclusive - start_index,
    )

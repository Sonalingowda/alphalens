"""Non-mutating validation for normalized candle series."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market_data.models import Candle, CandleTimeframe


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class CandleValidationReport:
    passed: bool
    issues: tuple[ValidationIssue, ...]


_TIMEFRAME_DURATION = {
    CandleTimeframe.MINUTE_5: timedelta(minutes=5),
    CandleTimeframe.MINUTE_10: timedelta(minutes=10),
    CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    CandleTimeframe.DAY_1: timedelta(days=1),
}
_REQUIRED_DECIMAL_FIELDS = ("open", "high", "low", "close", "volume")


def validate_candles(
    candles: tuple[Candle, ...],
    timeframe: CandleTimeframe,
    expected_start: datetime,
    expected_end: datetime,
) -> CandleValidationReport:
    issues: list[ValidationIssue] = []
    seen_timestamps: set[datetime] = set()
    previous_timestamp: datetime | None = None

    for candle in candles:
        timestamp = candle.timestamp
        if timestamp is None:
            issues.append(
                ValidationIssue(
                    code="missing_timestamp",
                    message="Candle timestamp is missing or invalid.",
                    timestamp=None,
                )
            )
        else:
            timestamp_is_aware = (
                timestamp.tzinfo is not None
                and timestamp.utcoffset() is not None
            )
            if not timestamp_is_aware or timestamp.utcoffset() != timedelta(0):
                issues.append(
                    ValidationIssue(
                        code="non_utc_timestamp",
                        message="Candle timestamp is not canonical UTC.",
                        timestamp=timestamp,
                    )
                )
            if timestamp_is_aware and not _is_timeframe_aligned(
                timestamp,
                timeframe,
            ):
                issues.append(
                    ValidationIssue(
                        code="misaligned_timestamp",
                        message=(
                            "Candle timestamp is not aligned to the "
                            f"{timeframe.value} UTC boundary."
                        ),
                        timestamp=timestamp,
                    )
                )
            if (
                timestamp_is_aware
                and timestamp + _TIMEFRAME_DURATION[timeframe] > expected_end
            ):
                issues.append(
                    ValidationIssue(
                        code="incomplete_candle",
                        message="Candle interval extends beyond the completed range.",
                        timestamp=timestamp,
                    )
                )
            if timestamp in seen_timestamps:
                issues.append(
                    ValidationIssue(
                        code="duplicate_timestamp",
                        message="Duplicate candle timestamp.",
                        timestamp=timestamp,
                    )
                )
            if (
                timestamp_is_aware
                and previous_timestamp is not None
                and timestamp <= previous_timestamp
            ):
                issues.append(
                    ValidationIssue(
                        code="non_chronological_timestamp",
                        message="Candle timestamps are not strictly increasing.",
                        timestamp=timestamp,
                    )
                )
            seen_timestamps.add(timestamp)
            if timestamp_is_aware:
                previous_timestamp = timestamp

        missing_fields = [
            field_name
            for field_name in _REQUIRED_DECIMAL_FIELDS
            if getattr(candle, field_name) is None
        ]
        if missing_fields:
            issues.append(
                ValidationIssue(
                    code="missing_required_fields",
                    message=f"Missing or invalid fields: {', '.join(missing_fields)}.",
                    timestamp=timestamp,
                )
            )
            continue

        _validate_candle_values(candle, issues)

    duration = _TIMEFRAME_DURATION[timeframe]
    expected_timestamp = expected_start
    while expected_timestamp < expected_end:
        if expected_timestamp not in seen_timestamps:
            issues.append(
                ValidationIssue(
                    code="missing_candle",
                    message=f"Missing candle for the requested {timeframe.value} interval.",
                    timestamp=expected_timestamp,
                )
            )
        expected_timestamp += duration

    return CandleValidationReport(passed=not issues, issues=tuple(issues))


def _validate_candle_values(
    candle: Candle,
    issues: list[ValidationIssue],
) -> None:
    open_price = _required_decimal(candle.open)
    high = _required_decimal(candle.high)
    low = _required_decimal(candle.low)
    close = _required_decimal(candle.close)
    volume = _required_decimal(candle.volume)

    if low > high:
        issues.append(
            ValidationIssue(
                code="low_above_high",
                message="Low price is greater than high price.",
                timestamp=candle.timestamp,
            )
        )
    if not low <= open_price <= high:
        issues.append(
            ValidationIssue(
                code="open_outside_range",
                message="Open price is outside the low/high range.",
                timestamp=candle.timestamp,
            )
        )
    if not low <= close <= high:
        issues.append(
            ValidationIssue(
                code="close_outside_range",
                message="Close price is outside the low/high range.",
                timestamp=candle.timestamp,
            )
        )
    if min(open_price, high, low, close) <= 0:
        issues.append(
            ValidationIssue(
                code="non_positive_price",
                message="One or more OHLC prices are non-positive.",
                timestamp=candle.timestamp,
            )
        )
    if volume < 0:
        issues.append(
            ValidationIssue(
                code="negative_volume",
                message="Volume is negative.",
                timestamp=candle.timestamp,
            )
        )


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise ValueError("Validated candle field is unexpectedly missing.")
    return value


def timeframe_duration(timeframe: CandleTimeframe) -> timedelta:
    return _TIMEFRAME_DURATION[timeframe]


def floor_timeframe_boundary(
    timestamp: datetime,
    timeframe: CandleTimeframe,
) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Timeframe boundaries require a timezone-aware timestamp.")
    utc_timestamp = timestamp.astimezone(timezone.utc)
    duration_seconds = int(_TIMEFRAME_DURATION[timeframe].total_seconds())
    floored_seconds = int(utc_timestamp.timestamp()) // duration_seconds
    return datetime.fromtimestamp(
        floored_seconds * duration_seconds,
        tz=timezone.utc,
    )


def _is_timeframe_aligned(
    timestamp: datetime,
    timeframe: CandleTimeframe,
) -> bool:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return False
    return timestamp == floor_timeframe_boundary(timestamp, timeframe)

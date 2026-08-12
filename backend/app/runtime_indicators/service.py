"""Runtime indicator projection from persisted feature snapshots."""

from __future__ import annotations

from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.opportunity_intelligence.domain import FeatureSnapshot, IndicatorValue
from app.opportunity_intelligence.domain.market import FeatureSnapshotValue
from app.opportunity_intelligence.services.errors import ServiceContractError
from app.opportunity_intelligence.services.projections import (
    IndicatorProjectionService,
)


_PRICE_UNITS = frozenset(
    {
        "average_true_range",
        "exponential_moving_average",
        "exponential_moving_average_12",
        "exponential_moving_average_26",
        "exponential_moving_average_50",
        "exponential_moving_average_100",
        "exponential_moving_average_200",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "simple_moving_average_20",
        "rolling_standard_deviation_20",
        "bollinger_middle",
        "bollinger_upper",
        "bollinger_lower",
        "positive_directional_movement",
        "negative_directional_movement",
        "true_range",
    }
)

_PERCENT_UNITS = frozenset(
    {
        "relative_strength_index",
        "positive_directional_indicator",
        "negative_directional_indicator",
        "directional_index",
        "average_directional_index",
        "average_directional_movement_rating",
        "bollinger_percent_b",
    }
)

_DIMENSIONLESS_UNITS = frozenset(
    {
        "candle_body_fraction",
        "candle_range_fraction",
        "upper_wick_fraction",
        "lower_wick_fraction",
        "bollinger_band_width",
    }
)

_OUTPUT_UNIT_BY_NAME = {
    **{name: "price" for name in _PRICE_UNITS},
    **{name: "percent" for name in _PERCENT_UNITS},
    **{name: "dimensionless" for name in _DIMENSIONLESS_UNITS},
}


class RuntimeIndicatorService(IndicatorProjectionService):
    """Project persisted feature snapshot values into immutable indicators."""

    async def project(
        self,
        feature_snapshot: FeatureSnapshot,
    ) -> tuple[IndicatorValue, ...]:
        if not isinstance(feature_snapshot, FeatureSnapshot):
            raise ServiceContractError(
                "Runtime indicators require a persisted FeatureSnapshot."
            )
        if feature_snapshot.registry_hash != INTRADAY_FEATURE_REGISTRY.configuration_hash:
            raise ServiceContractError(
                "Runtime indicators require the approved intraday feature registry."
            )
        return tuple(
            _project_value(value)
            for value in feature_snapshot.values
        )


def _project_value(value: FeatureSnapshotValue) -> IndicatorValue:
    unit = _OUTPUT_UNIT_BY_NAME.get(value.output_name)
    if unit is None:
        raise ServiceContractError(
            "Runtime indicators cannot project an unsupported feature output."
        )
    return IndicatorValue(
        feature_identifier=value.feature_identifier,
        definition_version=value.definition_version,
        output_name=value.output_name,
        value=value.value,
        unit=unit,
        candle_timestamp=value.candle_timestamp,
        available_at=value.available_at,
        feature_record=value.feature_record,
    )

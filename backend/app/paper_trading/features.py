"""Point-in-time feature generation for paper predictions."""

from datetime import datetime
from hashlib import sha256
import json

from app.features.pipeline import PIPELINE_VERSION, run_feature_pipeline
from app.market_data.models import Candle
from app.paper_trading.models import PaperFeatureVector


class PaperFeatureGenerationService:
    def generate(
        self,
        *,
        candles: tuple[Candle, ...],
        prediction_timestamps: tuple[datetime, ...],
        ordered_feature_names: tuple[str, ...],
    ) -> tuple[PaperFeatureVector, ...]:
        result = run_feature_pipeline(candles)
        if (
            result.pipeline_version != PIPELINE_VERSION
            or not result.point_in_time_validated
        ):
            raise ValueError("Feature pipeline verification failed.")
        requested = set(prediction_timestamps)
        values: dict[datetime, dict[str, object]] = {}
        for item in result.values:
            if item.timestamp in requested:
                values.setdefault(item.timestamp, {})[
                    item.feature_name
                ] = item.value
        vectors: list[PaperFeatureVector] = []
        for timestamp in prediction_timestamps:
            by_name = values.get(timestamp, {})
            if set(by_name) != set(ordered_feature_names):
                raise ValueError(
                    f"Incomplete paper feature vector at {timestamp.isoformat()}."
                )
            feature_values = tuple(
                by_name[name] for name in ordered_feature_names
            )
            payload = {
                "timestamp": timestamp.isoformat(),
                "pipeline_version": PIPELINE_VERSION,
                "features": [
                    {
                        "name": name,
                        "value": format(value, "f"),
                    }
                    for name, value in zip(
                        ordered_feature_names,
                        feature_values,
                        strict=True,
                    )
                ],
            }
            vectors.append(
                PaperFeatureVector(
                    timestamp=timestamp,
                    feature_names=ordered_feature_names,
                    feature_values=feature_values,
                    pipeline_version=PIPELINE_VERSION,
                    feature_vector_hash=_hash_json(payload),
                )
            )
        return tuple(vectors)


def _hash_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


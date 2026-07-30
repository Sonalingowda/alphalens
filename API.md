# AlphaLens Live Prediction API

## Scope

Live Prediction API v1.0.0 is the single production prediction interface for
AlphaLens. It loads only the verified immutable Ridge inference artifact and
never trains, fits, tunes, or modifies a model.

The API exposes no research, ingestion, configuration-mutation, broker,
trading, authentication, or WebSocket endpoints. Start this dedicated
application with:

```shell
cd backend
.venv/bin/uvicorn app.prediction_api:app --host 127.0.0.1 --port 8000
```

Canonical endpoints use the `/api/v1` prefix. The corresponding root paths are
compatibility aliases and return the same contracts. Every response includes
`X-AlphaLens-API-Version: 1.0.0`, `Cache-Control: no-store`, and, when immutable
audit persistence succeeds, `X-AlphaLens-Audit-ID`.

## Endpoint Reference

### `GET /api/v1/health`

Verifies database access and the complete artifact and state hashes before
reporting health.

```json
{
  "status": "healthy",
  "api_version": "1.0.0",
  "artifact_status": "verified",
  "artifact_identifier": "<artifact UUID>",
  "read_only": true
}
```

### `GET /api/v1/version`

Returns the API and route versions and confirms the read-only inference mode.

```json
{
  "api_name": "AlphaLens Live Prediction API",
  "api_version": "1.0.0",
  "route_version": "v1",
  "inference_mode": "packaged_artifact_only",
  "read_only": true
}
```

### `GET /api/v1/model`

Returns non-sensitive model metadata and the exact request schema. Coefficients,
scaler state, and training interfaces are never exposed.

The returned `schema_hash` and `ordered_feature_names` must be used unchanged
for prediction requests.

```json
{
  "api_version": "1.0.0",
  "artifact_identifier": "<artifact UUID>",
  "model_family": "ridge_regression",
  "artifact_version": "1.0.0",
  "artifact_sha256": "<64 lowercase hexadecimal characters>",
  "configuration_hash": "<64 lowercase hexadecimal characters>",
  "feature_pipeline_version": "1.1.0",
  "target_version": "1.0.0",
  "target_name": "forward_log_return",
  "horizon_observations": 5,
  "schema_hash": "<64 lowercase hexadecimal characters>",
  "feature_count": 12,
  "ordered_feature_names": [
    "bollinger_20_2_lower",
    "bollinger_20_2_middle",
    "bollinger_20_2_upper",
    "ema_20",
    "ema_50",
    "macd_12_26_9_histogram",
    "macd_12_26_9_line",
    "macd_12_26_9_signal",
    "rsi_14",
    "sma_20",
    "sma_50",
    "volume_sma_20"
  ]
}
```

### `GET /api/v1/metrics`

Returns process-local operational counters and timing measurements. These are
service-observability metrics, not model evaluation or trading metrics.

```json
{
  "api_version": "1.0.0",
  "request_count": 3,
  "successful_request_count": 3,
  "error_request_count": 0,
  "prediction_count": 1,
  "average_latency_microseconds": 1250.0,
  "maximum_latency_microseconds": 2400,
  "health": "operational"
}
```

### `GET /api/v1/resources`

Returns process-local uptime and resource measurements for monitoring. Values
describe the running API process and are not research or model metrics.

```json
{
  "api_version": "1.0.0",
  "uptime_seconds": 3600.0,
  "process_cpu_user_seconds": 12.5,
  "process_cpu_system_seconds": 2.1,
  "maximum_resident_set_bytes": 268435456
}
```

### `GET /api/v1/dashboard`

Returns a read-only presentation projection for the AlphaLens dashboard. The
projection is assembled from the verified production artifact and immutable
paper-trading, risk-management, and backtest reports. Every source report's
configuration and result SHA-256 hashes are verified before data is returned.
Unavailable evidence is represented as `null` or an empty collection; the API
does not generate placeholder market, prediction, portfolio, or trading data.

The response includes the latest prediction and signal, paper portfolio
summary and history, simulated orders and trades, risk events, chart-ready
series, backtest summaries, runtime settings, system metadata, and source
report identifiers. The route performs no training, inference, trading,
configuration mutation, or research computation.

### `POST /api/v1/predict`

Validates an exact ordered feature vector and invokes `predict()` on the loaded
artifact. Feature values are decimal strings so JSON binary floating-point
parsing cannot silently change the submitted decimal representation.

The timestamp must identify the completed candle whose feature vector is being
submitted and must include a UTC offset.

```json
{
  "api_version": "1.0.0",
  "schema_hash": "<exact hash returned by GET /api/v1/model>",
  "prediction_timestamp": "2026-07-28T00:00:00+00:00",
  "features": [
    {"name": "bollinger_20_2_lower", "value": "100000.000000000000000000"},
    {"name": "bollinger_20_2_middle", "value": "105000.000000000000000000"},
    {"name": "bollinger_20_2_upper", "value": "110000.000000000000000000"},
    {"name": "ema_20", "value": "105000.000000000000000000"},
    {"name": "ema_50", "value": "104000.000000000000000000"},
    {"name": "macd_12_26_9_histogram", "value": "100.000000000000000000"},
    {"name": "macd_12_26_9_line", "value": "500.000000000000000000"},
    {"name": "macd_12_26_9_signal", "value": "400.000000000000000000"},
    {"name": "rsi_14", "value": "55.000000000000000000"},
    {"name": "sma_20", "value": "105000.000000000000000000"},
    {"name": "sma_50", "value": "104000.000000000000000000"},
    {"name": "volume_sma_20", "value": "1000.000000000000000000"}
  ]
}
```

The values above illustrate request encoding only and are not represented as
market observations or as research evidence.

Successful response:

```json
{
  "api_version": "1.0.0",
  "prediction_timestamp": "2026-07-28T00:00:00Z",
  "inference_timestamp": "<UTC ISO-8601 timestamp>",
  "target_name": "forward_log_return",
  "target_version": "1.0.0",
  "horizon_observations": 5,
  "predicted_forward_log_return": "<deterministic decimal result>",
  "predicted_float_hex": "<exact IEEE-754 hexadecimal value>",
  "prediction_hash": "<64 lowercase hexadecimal characters>",
  "feature_vector_hash": "<64 lowercase hexadecimal characters>",
  "schema_hash": "<validated request schema hash>",
  "artifact_identifier": "<artifact UUID>",
  "artifact_sha256": "<verified artifact hash>",
  "configuration_hash": "<immutable artifact configuration hash>"
}
```

`prediction_hash`, the predicted value, and the feature-vector hash are
identical for identical timestamp, schema, features, and artifact. The
`inference_timestamp` and immutable request-audit identifier describe the
individual API invocation and therefore differ between calls.

## Errors

Every API error uses this structure:

```json
{
  "error": {
    "code": "FEATURE_ORDER_MISMATCH",
    "message": "Feature ordering differs from the model schema.",
    "api_version": "1.0.0",
    "details": []
  }
}
```

| HTTP status | Error code | Meaning |
| --- | --- | --- |
| 413 | `REQUEST_TOO_LARGE` | Body exceeds `ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES`. |
| 422 | `REQUEST_SCHEMA_INVALID` | A required field is missing, an extra field is present, or a field has the wrong JSON type. |
| 422 | `API_VERSION_MISMATCH` | Request version is not `1.0.0`. |
| 422 | `FEATURE_COUNT_MISMATCH` | The vector does not contain exactly twelve features. |
| 422 | `FEATURE_ORDER_MISMATCH` | Correct names were submitted in the wrong order. |
| 422 | `FEATURE_NAME_MISMATCH` | Submitted names differ from the artifact schema. |
| 422 | `SCHEMA_HASH_MISMATCH` | Submitted schema hash differs from `/model`. |
| 422 | `FEATURE_VALUE_INVALID` | A value is not a finite decimal string. |
| 422 | `INVALID_PREDICTION_TIMESTAMP` | Timestamp is missing a UTC offset. |
| 404 | `ROUTE_NOT_FOUND` | No API route exists at the requested path. |
| 405 | `METHOD_NOT_ALLOWED` | The route does not permit the HTTP method. |
| 503 | `ARTIFACT_UNAVAILABLE` | Artifact loading or hash verification failed. |
| 503 | `DASHBOARD_DATA_UNAVAILABLE` | A dashboard source report is unavailable or fails immutable hash verification. |
| 503 | `AUDIT_PERSISTENCE_UNAVAILABLE` | The immutable audit could not be stored; prediction delivery fails closed. |
| 500 | `INTERNAL_ERROR` | An unhandled service failure occurred. |

## Auditing and Observability

Every request records method, path, request size and hash, response status and
hash, latency, outcome, error code, artifact and configuration identity,
schema and prediction hashes when applicable, and UTC start/end timestamps.
The complete audit payload has its own SHA-256 hash and is append-only.

Logs record request metadata, prediction hashes, validation errors, artifact
failures, and audit failures. Request bodies and feature values are not written
to application logs. Production logs are emitted as one JSON object per line
with UTC timestamp, severity, logger, message, and available request context.

Production CORS is an explicit origin allowlist. Wildcards, localhost origins,
credentials, and unconfigured origins are rejected. Request bodies remain
limited by `ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES`.

## Versioning Policy

The path major version changes only for backward-incompatible request or
response changes. Additive compatible fields may be introduced within v1 with
an API minor version update. The request `api_version`, response header, and
response body must agree.

Artifact versions, feature-pipeline versions, target versions, and API versions
are independent provenance fields. A schema change always produces a new
`schema_hash`; clients must retrieve `/model` and submit the exact current
schema rather than assuming compatibility.

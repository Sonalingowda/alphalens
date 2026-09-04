"""Transfer the approved production state between authorized databases.

The production prediction API requires exactly one verified
``ridge_regression`` row in ``model_inference_artifacts`` at startup
(see ``app.startup.verify_readiness``).  This script exports that row
byte-identically from an authorized source database and imports it into a
target database after re-verifying every recorded hash.  No artifact content
is ever generated or modified by this script.

Usage:
    python scripts/transfer_approved_state.py export --url <source-url> --output state.json
    python scripts/transfer_approved_state.py import --url <target-url> --input state.json

Both commands refuse placeholder/dev credentials when targeting an explicit
URL whose environment is not otherwise validated; the URLs are used verbatim
as provided by the operator.
"""

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import json
import sys
from urllib.parse import urlsplit

from sqlalchemy import select

from app.inference.artifact import hash_json
from app.persistence.database import session_factory
from app.persistence.models import ModelInferenceArtifactRecord


_COLUMNS = (
    "id",
    "artifact_version",
    "model_family",
    "artifact_payload",
    "verification_evidence",
    "configuration_hash",
    "artifact_sha256",
    "state_sha256",
    "verification_evidence_hash",
    "selected_experiment_id",
    "holdout_evaluation_report_id",
    "model_dataset_hash",
    "training_dataset_hash",
    "feature_pipeline_version",
    "target_version",
    "validation_run_id",
    "split_hash",
    "final_training_observation_count",
    "purged_observation_count",
    "feature_count",
    "coefficient_count",
    "scaler_mean_count",
    "scaler_scale_count",
    "verification_prediction_count",
    "official_prediction_hash",
    "deterministic_replay",
    "official_prediction_hash_verified",
    "artifact_only_inference_verified",
    "model_tuned",
    "experiment_modified",
    "research_artifacts_modified",
    "created_at",
)

_JSON_COLUMNS = frozenset({"artifact_payload", "verification_evidence"})
_DATETIME_COLUMNS = frozenset({"created_at"})
_UUID_COLUMNS = frozenset(
    {
        "id",
        "selected_experiment_id",
        "holdout_evaluation_report_id",
        "validation_run_id",
    }
)


def _serialize(record: ModelInferenceArtifactRecord) -> dict:
    row = {}
    for column in _COLUMNS:
        value = getattr(record, column)
        if column in _DATETIME_COLUMNS:
            value = value.isoformat()
        elif column in _UUID_COLUMNS and value is not None:
            value = str(value)
        row[column] = value
    return row


def _verify_row(row: dict) -> None:
    payload = row["artifact_payload"]
    if hash_json(payload) != row["artifact_sha256"]:
        raise ValueError(
            f"Artifact {row['id']} failed artifact_sha256 verification."
        )
    if hash_json(payload["core"]) != row["state_sha256"]:
        raise ValueError(
            f"Artifact {row['id']} failed state_sha256 verification."
        )
    if hash_json(row["verification_evidence"]) != row["verification_evidence_hash"]:
        raise ValueError(
            f"Artifact {row['id']} failed verification_evidence_hash check."
        )


async def _export(url: str | None, output_path: str) -> int:
    if url is not None:
        _require_postgres(url)
        from app.persistence.database import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(create_async_engine(url))
    else:
        factory = session_factory
    async with factory() as session:
        records = (
            await session.scalars(select(ModelInferenceArtifactRecord))
        ).all()
    rows = [_serialize(record) for record in records]
    for row in rows:
        _verify_row(row)
    document = {
        "format": "alphalens-approved-state/1",
        "model_inference_artifacts": rows,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": "exported",
                "rows": len(rows),
                "output": output_path,
            },
            sort_keys=True,
        )
    )
    return 0


async def _import(url: str | None, input_path: str) -> int:
    if url is not None:
        _require_postgres(url)
        from app.persistence.database import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(create_async_engine(url))
    else:
        factory = session_factory
    with open(input_path, encoding="utf-8") as handle:
        document = json.load(handle)
    if document.get("format") != "alphalens-approved-state/1":
        raise ValueError("Unrecognized approved-state document format.")
    rows = document["model_inference_artifacts"]
    for row in rows:
        _verify_row(row)
    imported = 0
    skipped = 0
    async with factory() as session:
        for row in rows:
            existing = await session.get(ModelInferenceArtifactRecord, row["id"])
            if existing is not None:
                skipped += 1
                continue
            session.add(
                ModelInferenceArtifactRecord(
                    **{
                        column: (
                            datetime.fromisoformat(row[column])
                            if column in _DATETIME_COLUMNS
                            else row[column]
                        )
                        for column in _COLUMNS
                    }
                )
            )
            imported += 1
        await session.commit()
    print(
        json.dumps(
            {
                "status": "imported",
                "rows_imported": imported,
                "rows_skipped_existing": skipped,
                "hashes_verified": len(rows),
            },
            sort_keys=True,
        )
    )
    return 0


def _require_postgres(url: str) -> None:
    if urlsplit(url).scheme != "postgresql+asyncpg":
        raise ValueError(
            "Approved-state transfer requires a postgresql+asyncpg URL."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "import"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--url", default=None)
        if name == "export":
            subparser.add_argument("--output", required=True)
        else:
            subparser.add_argument("--input", required=True)
    arguments = parser.parse_args()
    if arguments.command == "export":
        return asyncio.run(_export(arguments.url, arguments.output))
    return asyncio.run(_import(arguments.url, arguments.input))


if __name__ == "__main__":
    sys.exit(main())

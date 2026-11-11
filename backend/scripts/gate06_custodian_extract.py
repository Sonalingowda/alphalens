"""Create the bounded Gate 06 development artifact from the retained source."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_SOURCE_SHA256 = (
    "f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc"
)
EXPECTED_CUTOFF = datetime(2026, 9, 12, 10, 5, tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != EXPECTED_SOURCE_SHA256:
        raise SystemExit("source hash mismatch")
    source = json.loads(source_bytes)
    rows = [
        row
        for row in source["klines"]
        if datetime.fromtimestamp(row[0] / 1000, timezone.utc) <= EXPECTED_CUTOFF
    ]
    if not rows or rows[-1][0] != int(EXPECTED_CUTOFF.timestamp() * 1000):
        raise SystemExit("development cutoff is not represented by a completed candle")
    output = {
        "manifest_schema": "alphalens.gate06.development-dataset.v1",
        "lineage_id": "gate06-development-20261111-v2",
        "source_file_sha256": EXPECTED_SOURCE_SHA256,
        "source_custodied_at": datetime.now(timezone.utc).isoformat(),
        "development_cutoff": EXPECTED_CUTOFF.isoformat().replace("+00:00", "Z"),
        "symbol": source["symbol"],
        "timeframe": source["timeframe"],
        "utc_start": datetime.fromtimestamp(rows[0][0] / 1000, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "utc_end": datetime.fromtimestamp(rows[-1][0] / 1000, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "candle_count": len(rows),
        "klines": rows,
    }
    payload = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
    output["development_dataset_sha256"] = hashlib.sha256(payload).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, sort_keys=True, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Small subprocess fixture for Gate 06 checkpoint recovery tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.gate06_offline_experiment import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--folds", type=int, default=8)
    parser.add_argument("--fail-after", type=int)
    args = parser.parse_args()

    if args.folds < 1 or args.fail_after is not None and not 1 <= args.fail_after <= args.folds:
        raise SystemExit("invalid fixture bounds")
    if args.state.exists():
        try:
            state = json.loads(args.state.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"corrupt checkpoint: {error}") from error
        if state.get("identity") != args.identity:
            raise SystemExit("checkpoint identity mismatch")
        rows = state.get("rows")
        if not isinstance(rows, list) or state.get("completed_folds") != len(rows):
            raise SystemExit("checkpoint fold state is invalid")
        if [row.get("fold") for row in rows] != list(range(1, len(rows) + 1)):
            raise SystemExit("checkpoint fold sequence is invalid")
    else:
        rows = []

    for fold in range(len(rows) + 1, args.folds + 1):
        rows.append({"fold": fold, "value": fold * fold})
        atomic_json(
            args.state,
            {
                "schema": "alphalens.gate06.fixture.v1",
                "identity": args.identity,
                "completed_folds": fold,
                "rows": rows,
            },
        )
        if args.fail_after == fold:
            return 17
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

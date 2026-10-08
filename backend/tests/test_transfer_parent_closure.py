"""Focused integrity tests for the approved parent-closure transfer document."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from app.inference.artifact import hash_json
from scripts import transfer_approved_state as transfer


CLOSURE_PATH = Path("/private/tmp/alphalens-approved-closure-a6576881.json")


@unittest.skipUnless(CLOSURE_PATH.exists(), "approved closure export is not present")
class ParentClosureDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        with CLOSURE_PATH.open(encoding="utf-8") as handle:
            self.document = json.load(handle)

    def test_complete_closure_and_relationships_validate(self) -> None:
        artifact, tables = transfer._validate_closure_document(self.document)
        transfer._validate_closure_relationships(tables)
        self.assertEqual(
            artifact["id"], "a6576881-77d2-4947-a8b6-5b3707d8e76a"
        )
        self.assertEqual(
            artifact["artifact_sha256"],
            "88644e3d2316f3c0ef99a40761aecabd1206d63f0c39784a6bb2475b07832bcd",
        )
        self.assertEqual(self.document["closure_record_count"], 13)

    def test_tampered_row_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.document)
        table_name = "regression_experiments"
        tampered["tables"][table_name][0]["values"]["model_family"] = "tampered"
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_closure_document(tampered)

    def test_missing_parent_is_rejected_after_rehash(self) -> None:
        missing = copy.deepcopy(self.document)
        missing["tables"].pop("validation_runs")
        missing["closure_record_count"] = sum(
            len(rows) for rows in missing["tables"].values()
        )
        missing.pop("closure_sha256", None)
        missing["closure_sha256"] = hash_json(missing)
        artifact, tables = transfer._validate_closure_document(missing)
        del artifact
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_closure_relationships(tables)

    def test_closure_hash_is_stable(self) -> None:
        unsigned = dict(self.document)
        unsigned.pop("closure_sha256")
        self.assertEqual(transfer.hash_json(unsigned), self.document["closure_sha256"])

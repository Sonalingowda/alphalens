from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.gate09_local_certification import run, verify_evidence_manifest


class Gate09LocalCertificationTests(unittest.TestCase):
    def test_source_is_unknown_without_explicit_artifact(self):
        report = run(source=None, backend=None)
        source_check = next(
            check for check in report["checks"] if check["name"] == "development_source_hash"
        )
        self.assertEqual(source_check["status"], "UNKNOWN")
        self.assertEqual(report["overall"], "BLOCKED")

    def test_content_addressed_evidence_manifest_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.json"
            artifact.write_text('{"status":"blocked"}', encoding="utf-8")
            payload = {
                "schema": "alphalens.evidence-manifest.v1",
                "entries": [
                    {"name": "artifact", "path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
                ],
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            status, detail = verify_evidence_manifest(manifest)
            self.assertEqual(status, "PASS")
            self.assertIn("1 content-addressed", detail)

    def test_content_addressed_evidence_manifest_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "alphalens.evidence-manifest.v1",
                        "entries": [],
                        "manifest_sha256": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            status, _ = verify_evidence_manifest(manifest)
            self.assertEqual(status, "FAIL")


if __name__ == "__main__":
    unittest.main()

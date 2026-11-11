from __future__ import annotations

import unittest

from scripts.gate09_local_certification import run


class Gate09LocalCertificationTests(unittest.TestCase):
    def test_source_is_unknown_without_explicit_artifact(self):
        report = run(source=None, backend=None)
        source_check = next(
            check for check in report["checks"] if check["name"] == "development_source_hash"
        )
        self.assertEqual(source_check["status"], "UNKNOWN")
        self.assertEqual(report["overall"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anvil_core.harness_runner import run_harness_contract


class HarnessRunnerTests(unittest.TestCase):
    def test_simulated_harness_contract_reaches_done_with_clean_audit(self) -> None:
        try:
            import anvil  # noqa: F401
        except ImportError:
            self.skipTest("anvil-harness is not installed")

        payload = {
            "mission": "Run generated contract",
            "scope_in": ["src"],
            "scope_out": ["prod"],
            "context_budget": {"total": 1000},
            "tasks": [
                {
                    "id": "n1",
                    "title": "Normalize",
                    "risk": "reversible",
                    "deps": [],
                    "tools": [],
                    "paths": ["src/*"],
                    "acceptance": [
                        {
                            "id": "n1_check_1",
                            "description": "Intent is explicit",
                            "kind": "manual",
                            "spec": {},
                            "authored_by": "qa",
                        }
                    ],
                },
                {
                    "id": "n2",
                    "title": "Validate",
                    "risk": "reversible",
                    "deps": ["n1"],
                    "tools": ["anvil.validate_budget"],
                    "paths": ["src/*"],
                    "acceptance": [
                        {
                            "id": "n2_check_1",
                            "description": "Budget respected",
                            "kind": "manual",
                            "spec": {},
                            "authored_by": "qa",
                        }
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            report = run_harness_contract(payload, run_dir=Path(td), mode="simulated")
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["audit_ok"], report)
        self.assertEqual(report["phase"], "done")
        self.assertEqual(report["tasks"]["n1"]["status"], "done")
        self.assertEqual(report["tasks"]["n2"]["status"], "done")


if __name__ == "__main__":
    unittest.main()


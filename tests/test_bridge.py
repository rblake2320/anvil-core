from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from anvil_core.bridge import compiler_plan_to_contract, harness_contract_dict, write_contract


class BridgeTests(unittest.TestCase):
    def test_compiler_plan_maps_to_execution_contract(self) -> None:
        plan = {
            "request_id": "req_test",
            "project_name": "demo",
            "normalized_intent": "Build a small agent plan",
            "cache_key": "cache_test",
            "intent_class": "software_build",
            "metrics": {"plan_hash": "plan_hash"},
            "budget": {"total": 3000},
            "proof_ledger": [{"step_id": "proof_1"}],
            "metadata": {"scope_paths": ["src"], "scope_out": ["prod"], "tool_policy": {"allow_high_risk_tools": True}},
            "loaded_tools": [
                {"name": "anvil.validate_budget", "risk": "none"},
                {"name": "deploy.prod", "risk": "high"},
            ],
            "execution_plan": [
                {
                    "node_id": "n1",
                    "node_type": "normalize_intent",
                    "description": "Normalize",
                    "depends_on": [],
                    "token_budget": 100,
                    "tool_name": None,
                    "acceptance_checks": ["Intent is explicit"],
                },
                {
                    "node_id": "n2",
                    "node_type": "validate",
                    "description": "Validate",
                    "depends_on": ["n1"],
                    "token_budget": 100,
                    "tool_name": "anvil.validate_budget",
                    "acceptance_checks": ["Budget respected"],
                },
                {
                    "node_id": "n3",
                    "node_type": "execute_tool",
                    "description": "Deploy",
                    "depends_on": ["n2"],
                    "token_budget": 100,
                    "tool_name": "deploy.prod",
                    "acceptance_checks": ["Approval recorded"],
                },
            ],
        }
        contract = compiler_plan_to_contract(plan)
        self.assertEqual(contract.request_id, "req_test")
        self.assertEqual(contract.source_plan_hash, "plan_hash")
        self.assertEqual(contract.scope_in, ["src"])
        self.assertEqual(contract.scope_out, ["prod"])
        self.assertEqual(len(contract.tasks), 3)
        self.assertEqual(contract.tasks[1].depends_on, ["n1"])
        self.assertEqual(contract.tasks[1].tool_name, "anvil.validate_budget")
        self.assertEqual(contract.tasks[1].scope_paths, ["src/*"])
        self.assertEqual(contract.tasks[2].risk, "irreversible")
        self.assertIn("deploy.prod", contract.tool_policy["irreversible_tools"])

        harness_contract = harness_contract_dict(contract)
        self.assertEqual(harness_contract["scope_in"], ["src"])
        self.assertEqual(harness_contract["scope_out"], ["prod"])
        self.assertEqual(harness_contract["tasks"][2]["paths"], ["src/*"])
        self.assertEqual(harness_contract["tasks"][2]["risk"], "irreversible")
        self.assertEqual(harness_contract["tasks"][2]["tools"], ["deploy.prod"])

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "contract.json"
            write_contract(contract, out)
            saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["tasks"][0]["acceptance_checks"], ["Intent is explicit"])


if __name__ == "__main__":
    unittest.main()

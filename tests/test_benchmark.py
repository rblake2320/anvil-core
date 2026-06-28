from __future__ import annotations

import unittest

from anvil_core.benchmark import VARIANTS, run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_offline_synthetic_report_covers_required_variants(self) -> None:
        scenario = {
            "name": "unit",
            "request": "Build a minimal feature",
            "context_tokens": 1000,
            "tool_schema_tokens": 300,
            "expected_output_tokens": 200,
            "expected_patch_size_bytes": 1000,
            "tests_total": 3,
        }
        plan = {
            "metrics": {"prompt_package_tokens": 650},
            "loaded_tools": [{"name": "repo.search", "token_estimate": 80}],
            "zones": [{}, {}, {}, {"ledger_refs": ["span_1", "span_2"]}],
            "execution_plan": [],
        }
        report = run_benchmark(scenario, compiled_plan=plan, offline_synthetic=True)
        self.assertEqual([item.variant for item in report.variants], VARIANTS)
        self.assertEqual(report.metadata["mode"], "synthetic_offline")
        anvil = next(item for item in report.variants if item.variant == "anvil_compiler_harness")
        self.assertEqual(anvil.rehydrations, 2)
        self.assertLess(anvil.input_tokens, scenario["context_tokens"] + scenario["tool_schema_tokens"])

    def test_requires_measurements_unless_synthetic_enabled(self) -> None:
        with self.assertRaises(ValueError):
            run_benchmark({"name": "empty", "request": "x"})

    def test_quality_winner_prefers_pass_rate_over_raw_pass_count(self) -> None:
        report = run_benchmark(
            {
                "name": "quality",
                "request": "x",
                "measurements": [
                    {
                        "variant": "baseline_claude_code",
                        "input_tokens": 100,
                        "output_tokens": 100,
                        "tool_schema_tokens": 100,
                        "wall_time_ms": 100,
                        "patch_size_bytes": 100,
                        "tests_passed": 9,
                        "tests_total": 20,
                        "completed": True,
                    },
                    {
                        "variant": "anvil_compiler_harness",
                        "input_tokens": 100,
                        "output_tokens": 100,
                        "tool_schema_tokens": 100,
                        "wall_time_ms": 100,
                        "patch_size_bytes": 120,
                        "tests_passed": 3,
                        "tests_total": 3,
                        "completed": True,
                    },
                ],
            }
        )
        self.assertEqual(report.winner_by_quality, "anvil_compiler_harness")


if __name__ == "__main__":
    unittest.main()

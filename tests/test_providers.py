from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from anvil_core.cli import main as cli_main
from anvil_core.providers import OllamaBenchmarkAdapter, OpenAIChatCompletionAdapter, OpenRouterChatCompletionAdapter


def _live_ollama(testcase: unittest.TestCase) -> tuple[str, str]:
    model = os.getenv("ANVIL_OLLAMA_LIVE_MODEL", "").strip()
    if not model:
        testcase.skipTest("Set ANVIL_OLLAMA_LIVE_MODEL to run live Ollama provider tests")
    base_url = os.getenv("ANVIL_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        with urlopen(f"{base_url}/api/tags", timeout=10) as resp:  # noqa: S310 - explicit live local/provider test
            tags = json.loads(resp.read().decode("utf-8"))
    except (OSError, URLError) as exc:
        testcase.fail(f"ANVIL_OLLAMA_LIVE_MODEL is set but Ollama is unreachable at {base_url}: {exc}")
    models = {item.get("name") for item in tags.get("models", [])}
    if model not in models:
        testcase.fail(f"ANVIL_OLLAMA_LIVE_MODEL={model!r} is not present in Ollama /api/tags")
    return base_url, model


def _live_openai(testcase: unittest.TestCase) -> tuple[str, str, str]:
    model = os.getenv("ANVIL_OPENAI_LIVE_MODEL", "").strip()
    if not model:
        testcase.skipTest("Set ANVIL_OPENAI_LIVE_MODEL to run live OpenAI provider tests")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        testcase.fail("ANVIL_OPENAI_LIVE_MODEL is set but OPENAI_API_KEY is empty")
    base_url = os.getenv("ANVIL_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return base_url, key, model


def _live_openrouter(testcase: unittest.TestCase) -> tuple[str, str, str]:
    model = os.getenv("ANVIL_OPENROUTER_LIVE_MODEL", "").strip()
    if not model:
        testcase.skipTest("Set ANVIL_OPENROUTER_LIVE_MODEL to run live OpenRouter provider tests")
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        testcase.fail("ANVIL_OPENROUTER_LIVE_MODEL is set but OPENROUTER_API_KEY is empty")
    base_url = os.getenv("ANVIL_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    return base_url, key, model


class ProviderTests(unittest.TestCase):
    def test_live_ollama_adapter_records_usage_and_artifacts(self) -> None:
        base_url, model = _live_ollama(self)
        with tempfile.TemporaryDirectory() as td:
            measurement = OllamaBenchmarkAdapter(base_url=base_url, timeout=600).run_variant(
                variant="baseline_claude_code",
                model=model,
                prompt="Return exactly this JSON object and no prose: {\"ok\": true}",
                artifact_dir=td,
                tool_schema_tokens=3,
                tests_passed=1,
                tests_total=1,
                options={"temperature": 0},
            )
            self.assertEqual(measurement.provider, "ollama")
            self.assertEqual(measurement.model, model)
            self.assertGreater(measurement.input_tokens, 0)
            self.assertGreater(measurement.output_tokens, 0)
            self.assertIn("prompt_eval_count", measurement.provider_usage)
            self.assertIn("eval_count", measurement.provider_usage)
            self.assertIn("provider_raw_response.json", measurement.artifacts)
            self.assertTrue(Path(measurement.artifacts["measurement.json"]).exists())

    def test_live_measure_provider_cli_writes_measurement(self) -> None:
        base_url, model = _live_ollama(self)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scenario = root / "scenario.json"
            out = root / "measurement.json"
            artifacts = root / "artifacts"
            scenario.write_text(
                json.dumps({"name": "unit", "request": "Return the word measured.", "tool_schema_tokens": 2}),
                encoding="utf-8",
            )
            code = cli_main(
                [
                    "measure-provider",
                    "--provider",
                    "ollama",
                    "--variant",
                    "baseline_claude_code",
                    "--model",
                    model,
                    "--scenario",
                    str(scenario),
                    "--base-url",
                    base_url,
                    "--artifact-dir",
                    str(artifacts),
                    "--options-json",
                    "{\"temperature\": 0}",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["provider"], "ollama")
            self.assertEqual(saved["model"], model)
            self.assertGreater(saved["input_tokens"], 0)
            self.assertGreater(saved["output_tokens"], 0)
            self.assertTrue((artifacts / "provider_usage.json").exists())

    def test_live_openai_adapter_records_usage_and_artifacts(self) -> None:
        base_url, key, model = _live_openai(self)
        with tempfile.TemporaryDirectory() as td:
            measurement = OpenAIChatCompletionAdapter(api_key=key, base_url=base_url, timeout=600).run_variant(
                variant="baseline_claude_code",
                model=model,
                prompt="Return the word measured.",
                artifact_dir=td,
                tool_schema_tokens=3,
                tests_passed=1,
                tests_total=1,
                options={"max_completion_tokens": 16},
            )
            request = json.loads(Path(measurement.artifacts["provider_request.json"]).read_text(encoding="utf-8"))
            self.assertEqual(measurement.provider, "openai")
            self.assertGreater(measurement.input_tokens, 0)
            self.assertGreater(measurement.output_tokens, 0)
            self.assertIn("prompt_tokens", measurement.provider_usage)
            self.assertEqual(request["headers"]["Authorization"], "Bearer <redacted>")
            self.assertTrue(Path(measurement.artifacts["measurement.json"]).exists())

    def test_live_openai_measure_provider_cli_writes_measurement(self) -> None:
        base_url, _key, model = _live_openai(self)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scenario = root / "scenario.json"
            out = root / "measurement.json"
            artifacts = root / "artifacts"
            scenario.write_text(
                json.dumps({"name": "unit", "request": "Return the word measured.", "tool_schema_tokens": 2}),
                encoding="utf-8",
            )
            code = cli_main(
                [
                    "measure-provider",
                    "--provider",
                    "openai",
                    "--variant",
                    "baseline_claude_code",
                    "--model",
                    model,
                    "--scenario",
                    str(scenario),
                    "--base-url",
                    base_url,
                    "--artifact-dir",
                    str(artifacts),
                    "--options-json",
                    "{\"max_completion_tokens\": 16}",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["provider"], "openai")
            self.assertGreater(saved["input_tokens"], 0)
            self.assertGreater(saved["output_tokens"], 0)
            self.assertTrue((artifacts / "provider_usage.json").exists())

    def test_live_openrouter_adapter_records_usage_and_artifacts(self) -> None:
        base_url, key, model = _live_openrouter(self)
        with tempfile.TemporaryDirectory() as td:
            measurement = OpenRouterChatCompletionAdapter(
                api_key=key,
                base_url=base_url,
                timeout=600,
                app_title="ANVIL Core Tests",
            ).run_variant(
                variant="baseline_claude_code",
                model=model,
                prompt="Return the word measured.",
                artifact_dir=td,
                tool_schema_tokens=3,
                tests_passed=1,
                tests_total=1,
                options={"max_tokens": 16},
            )
            request = json.loads(Path(measurement.artifacts["provider_request.json"]).read_text(encoding="utf-8"))
            self.assertEqual(measurement.provider, "openrouter")
            self.assertGreater(measurement.input_tokens, 0)
            self.assertGreater(measurement.output_tokens, 0)
            self.assertIn("prompt_tokens", measurement.provider_usage)
            self.assertEqual(request["headers"]["Authorization"], "Bearer <redacted>")
            self.assertTrue(Path(measurement.artifacts["measurement.json"]).exists())

if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from anvil_core.cli import main as cli_main
from anvil_core.providers import OllamaBenchmarkAdapter


class _OllamaMockHandler(BaseHTTPRequestHandler):
    seen_payload: dict = {}

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/generate":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.seen_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        body = json.dumps(
            {
                "model": self.__class__.seen_payload["model"],
                "response": "measured output",
                "done": True,
                "total_duration": 50_000_000,
                "load_duration": 1_000_000,
                "prompt_eval_count": 11,
                "prompt_eval_duration": 20_000_000,
                "eval_count": 7,
                "eval_duration": 30_000_000,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class ProviderTests(unittest.TestCase):
    def test_ollama_adapter_records_usage_and_artifacts(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaMockHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                measurement = OllamaBenchmarkAdapter(base_url=f"http://127.0.0.1:{server.server_port}").run_variant(
                    variant="baseline_claude_code",
                    model="unit-model",
                    prompt="hello provider",
                    artifact_dir=td,
                    tool_schema_tokens=3,
                    tests_passed=1,
                    tests_total=1,
                )
                self.assertEqual(_OllamaMockHandler.seen_payload["stream"], False)
                self.assertEqual(measurement.provider, "ollama")
                self.assertEqual(measurement.model, "unit-model")
                self.assertEqual(measurement.input_tokens, 11)
                self.assertEqual(measurement.output_tokens, 7)
                self.assertEqual(measurement.provider_usage["total_duration_ms"], 50)
                self.assertIn("provider_raw_response.json", measurement.artifacts)
                self.assertTrue(Path(measurement.artifacts["measurement.json"]).exists())
        finally:
            server.shutdown()
            server.server_close()

    def test_measure_provider_cli_writes_measurement(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaMockHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                scenario = root / "scenario.json"
                out = root / "measurement.json"
                artifacts = root / "artifacts"
                scenario.write_text(json.dumps({"name": "unit", "request": "hello", "tool_schema_tokens": 2}), encoding="utf-8")
                code = cli_main(
                    [
                        "measure-provider",
                        "--provider",
                        "ollama",
                        "--variant",
                        "baseline_claude_code",
                        "--model",
                        "unit-model",
                        "--scenario",
                        str(scenario),
                        "--base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--artifact-dir",
                        str(artifacts),
                        "--out",
                        str(out),
                    ]
                )
                self.assertEqual(code, 0)
                saved = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(saved["provider"], "ollama")
                self.assertEqual(saved["input_tokens"], 11)
                self.assertTrue((artifacts / "provider_usage.json").exists())
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

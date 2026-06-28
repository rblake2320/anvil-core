from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .models import BenchmarkMeasurement, to_jsonable


def estimate_text_tokens(text: str) -> int:
    return max(1, len(text.split()))


class OllamaBenchmarkAdapter:
    """Measured local provider adapter for Ollama's `/api/generate` endpoint."""

    def __init__(self, *, base_url: str = "http://127.0.0.1:11434", timeout: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def run_variant(
        self,
        *,
        variant: str,
        model: str,
        prompt: str,
        artifact_dir: str | Path,
        tool_schema_tokens: int = 0,
        tests_passed: int = 0,
        tests_total: int = 0,
        patch_size_bytes: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> BenchmarkMeasurement:
        artifacts = ProviderArtifactWriter(artifact_dir)
        request_payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            request_payload["options"] = options

        artifacts.write_text("raw_prompt.txt", prompt)
        artifacts.write_json("provider_request.json", request_payload)

        req = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - user-configured local/provider URL
            raw_response = json.loads(resp.read().decode("utf-8"))
        wall_time_ms = max(1, int((time.perf_counter() - started) * 1000))

        response_text = str(raw_response.get("response", ""))
        artifacts.write_text("provider_output.txt", response_text)
        artifacts.write_json("provider_raw_response.json", raw_response)

        usage = _ollama_usage(raw_response)
        artifacts.write_json("provider_usage.json", usage)

        measurement = BenchmarkMeasurement(
            variant=variant,
            input_tokens=int(usage.get("prompt_eval_count") or estimate_text_tokens(prompt)),
            output_tokens=int(usage.get("eval_count") or estimate_text_tokens(response_text)),
            tool_schema_tokens=max(0, int(tool_schema_tokens)),
            wall_time_ms=wall_time_ms,
            patch_size_bytes=patch_size_bytes if patch_size_bytes is not None else len(response_text.encode("utf-8")),
            tests_passed=max(0, int(tests_passed)),
            tests_total=max(0, int(tests_total)),
            completed=bool(raw_response.get("done", True)),
            mode="measured",
            notes="Measured with Ollama /api/generate using stream=false.",
            provider="ollama",
            model=model,
            provider_usage=usage,
            artifacts={**artifacts.manifest(), "measurement.json": str(artifacts.root / "measurement.json")},
        )
        artifacts.write_json("measurement.json", to_jsonable(measurement))
        return measurement


class ProviderArtifactWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, str] = {}

    def write_text(self, name: str, content: str) -> None:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        self._artifacts[name] = str(path)

    def write_json(self, name: str, payload: Any) -> None:
        path = self.root / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._artifacts[name] = str(path)

    def manifest(self) -> dict[str, str]:
        return dict(self._artifacts)


def _ollama_usage(response: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    ]
    usage = {key: response[key] for key in keys if key in response}
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        if key in usage:
            usage[f"{key}_ms"] = int(int(usage[key]) / 1_000_000)
    return usage

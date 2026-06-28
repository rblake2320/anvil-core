from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
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


class OpenAICompatibleChatAdapter:
    """Measured adapter for OpenAI-compatible `/chat/completions` APIs."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        timeout: int = 600,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(f"{provider} API key is required")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})

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
        request_payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if options:
            request_payload.update(options)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        endpoint = f"{self.base_url}/chat/completions"
        artifacts.write_text("raw_prompt.txt", prompt)
        artifacts.write_json(
            "provider_request.json",
            {
                "endpoint": endpoint,
                "headers": _sanitized_headers(headers),
                "payload": request_payload,
            },
        )

        req = Request(
            endpoint,
            data=json.dumps(request_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        raw_response = _read_json_response(req, timeout=self.timeout)
        wall_time_ms = max(1, int((time.perf_counter() - started) * 1000))

        response_text = _chat_completion_text(raw_response)
        artifacts.write_text("provider_output.txt", response_text)
        artifacts.write_json("provider_raw_response.json", raw_response)

        usage = dict(raw_response.get("usage") or {})
        artifacts.write_json("provider_usage.json", usage)

        finish_reason = _chat_completion_finish_reason(raw_response)
        measurement = BenchmarkMeasurement(
            variant=variant,
            input_tokens=int(usage.get("prompt_tokens") or estimate_text_tokens(prompt)),
            output_tokens=int(usage.get("completion_tokens") or estimate_text_tokens(response_text)),
            tool_schema_tokens=max(0, int(tool_schema_tokens)),
            wall_time_ms=wall_time_ms,
            patch_size_bytes=patch_size_bytes if patch_size_bytes is not None else len(response_text.encode("utf-8")),
            tests_passed=max(0, int(tests_passed)),
            tests_total=max(0, int(tests_total)),
            completed=bool(raw_response.get("choices")) and finish_reason != "error",
            mode="measured",
            notes=f"Measured with {self.provider} /chat/completions using stream=false.",
            provider=self.provider,
            model=str(raw_response.get("model") or model),
            provider_usage=usage,
            artifacts={**artifacts.manifest(), "measurement.json": str(artifacts.root / "measurement.json")},
        )
        artifacts.write_json("measurement.json", to_jsonable(measurement))
        return measurement


class OpenAIChatCompletionAdapter(OpenAICompatibleChatAdapter):
    def __init__(self, *, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 600) -> None:
        super().__init__(provider="openai", base_url=base_url, api_key=api_key, timeout=timeout)


class OpenRouterChatCompletionAdapter(OpenAICompatibleChatAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 600,
        site_url: str | None = None,
        app_title: str | None = None,
    ) -> None:
        headers = {}
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_title:
            headers["X-OpenRouter-Title"] = app_title
        super().__init__(
            provider="openrouter",
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            extra_headers=headers,
        )


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


def _read_json_response(req: Request, *, timeout: int) -> dict[str, Any]:
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-configured provider URL
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"provider request failed with HTTP {exc.code}: {_redact_secret_fragments(body)}") from exc


def _chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _chat_completion_finish_reason(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    return str(first.get("finish_reason") or "")


def _sanitized_headers(headers: dict[str, str]) -> dict[str, str]:
    clean = dict(headers)
    if "Authorization" in clean:
        clean["Authorization"] = "Bearer <redacted>"
    return clean


def _redact_secret_fragments(text: str) -> str:
    redacted = re.sub(r"sk-[^\s\"']+", "sk-<redacted>", text)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", redacted, flags=re.IGNORECASE)
    return redacted[:2000]

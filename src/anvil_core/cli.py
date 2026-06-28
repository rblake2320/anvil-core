from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .benchmark import contract_from_plan_file, load_optional_json, load_scenario, run_benchmark, write_report
from .bridge import compiler_plan_to_contract, harness_contract_dict, load_compiler_plan, write_contract
from .harness_runner import load_harness_contract, run_harness_contract
from .models import to_jsonable
from .providers import OllamaBenchmarkAdapter, OpenAIChatCompletionAdapter, OpenRouterChatCompletionAdapter


def cmd_compile_contract(args: argparse.Namespace) -> int:
    plan = load_compiler_plan(args.plan)
    contract = compiler_plan_to_contract(plan)
    write_contract(contract, args.out)
    if args.harness_out:
        out = Path(args.harness_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(harness_contract_dict(contract), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    if args.measurement_file:
        measurements = list(scenario.get("measurements", []))
        for file in args.measurement_file:
            measurements.append(json.loads(Path(file).read_text(encoding="utf-8")))
        scenario["measurements"] = measurements
    compiled_plan = load_optional_json(args.compiled_plan)
    contract = load_optional_json(args.contract) or contract_from_plan_file(args.compiled_plan)
    report = run_benchmark(
        scenario,
        compiled_plan=compiled_plan,
        contract=contract,
        offline_synthetic=args.offline_synthetic,
    )
    if args.out:
        write_report(report, args.out)
    else:
        print(json.dumps(to_jsonable(report), indent=2, sort_keys=True))
    return 0


def cmd_run_harness_contract(args: argparse.Namespace) -> int:
    payload = load_harness_contract(args.harness_contract)
    run_dir = args.run_dir or ".anvil-core/harness-run"
    report = run_harness_contract(
        payload,
        run_dir=run_dir,
        mode=args.mode,
        approve_irreversible=not args.deny_irreversible,
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def cmd_measure_provider(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        prompt = str(scenario.get("request", ""))
    artifact_dir = args.artifact_dir or f".anvil-core/artifacts/{args.variant}-{args.provider}"
    adapter = _provider_adapter(args)
    measurement = adapter.run_variant(
        variant=args.variant,
        model=args.model,
        prompt=prompt,
        artifact_dir=artifact_dir,
        tool_schema_tokens=_tool_schema_tokens(args, scenario),
        tests_passed=args.tests_passed,
        tests_total=args.tests_total,
        patch_size_bytes=args.patch_size_bytes,
        options=json.loads(args.options_json) if args.options_json else None,
    )
    payload = to_jsonable(measurement)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _provider_adapter(
    args: argparse.Namespace,
) -> OllamaBenchmarkAdapter | OpenAIChatCompletionAdapter | OpenRouterChatCompletionAdapter:
    if args.provider == "ollama":
        return OllamaBenchmarkAdapter(base_url=args.base_url or "http://127.0.0.1:11434", timeout=args.timeout)
    if args.provider == "openai":
        key = os.getenv(args.api_key_env or "OPENAI_API_KEY", "")
        return OpenAIChatCompletionAdapter(
            api_key=key,
            base_url=args.base_url or "https://api.openai.com/v1",
            timeout=args.timeout,
        )
    if args.provider == "openrouter":
        key = os.getenv(args.api_key_env or "OPENROUTER_API_KEY", "")
        return OpenRouterChatCompletionAdapter(
            api_key=key,
            base_url=args.base_url or "https://openrouter.ai/api/v1",
            timeout=args.timeout,
            site_url=args.site_url,
            app_title=args.app_title,
        )
    raise ValueError(f"Unsupported provider: {args.provider}")


def _tool_schema_tokens(args: argparse.Namespace, scenario: dict[str, object]) -> int:
    if args.tool_schema_tokens is not None:
        return int(args.tool_schema_tokens)
    return int(scenario.get("tool_schema_tokens", 0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anvil-core", description="ANVIL integration and benchmark CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile-contract", help="Convert an ANVIL compiler plan into a harness contract artifact")
    c.add_argument("--plan", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--harness-out", help="Also write a JSON artifact shaped like anvil-harness Contract/Task data.")
    c.set_defaults(func=cmd_compile_contract)

    b = sub.add_parser("benchmark", help="Generate a repeatable benchmark report")
    b.add_argument("--scenario", required=True)
    b.add_argument("--compiled-plan")
    b.add_argument("--contract")
    b.add_argument(
        "--measurement-file",
        action="append",
        help="Measured BenchmarkMeasurement JSON to include in the report.",
    )
    b.add_argument("--offline-synthetic", action="store_true")
    b.add_argument("--out")
    b.set_defaults(func=cmd_benchmark)

    r = sub.add_parser("run-harness-contract", help="Execute a harness-shaped contract through anvil-harness Lifecycle")
    r.add_argument("--harness-contract", required=True)
    r.add_argument("--mode", choices=["simulated"], default="simulated")
    r.add_argument("--run-dir", help="Mission run directory. Defaults to .anvil-core/harness-run.")
    r.add_argument("--deny-irreversible", action="store_true", help="Deny irreversible approvals in simulated mode.")
    r.add_argument("--out")
    r.set_defaults(func=cmd_run_harness_contract)

    m = sub.add_parser("measure-provider", help="Run one measured provider variant and save proof artifacts")
    m.add_argument("--provider", choices=["ollama", "openai", "openrouter"], required=True)
    m.add_argument("--variant", required=True)
    m.add_argument("--model", required=True)
    m.add_argument("--scenario", required=True)
    m.add_argument("--prompt-file", help="Prompt to send. Defaults to scenario.request.")
    m.add_argument("--base-url")
    m.add_argument("--api-key-env", help="Environment variable containing the API key for OpenAI-compatible providers.")
    m.add_argument("--site-url", help="Optional OpenRouter HTTP-Referer attribution header.")
    m.add_argument("--app-title", help="Optional OpenRouter X-OpenRouter-Title attribution header.")
    m.add_argument("--timeout", type=int, default=600)
    m.add_argument("--artifact-dir")
    m.add_argument("--tool-schema-tokens", type=int)
    m.add_argument("--tests-passed", type=int, default=0)
    m.add_argument("--tests-total", type=int, default=0)
    m.add_argument("--patch-size-bytes", type=int)
    m.add_argument("--options-json", help="JSON object merged into the provider request payload.")
    m.add_argument("--out")
    m.set_defaults(func=cmd_measure_provider)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    Path(".anvil-core").mkdir(exist_ok=True)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

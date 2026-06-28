from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bridge import compiler_plan_to_contract, load_compiler_plan
from .models import BenchmarkMeasurement, BenchmarkReport, to_jsonable

VARIANTS = [
    "baseline_claude_code",
    "ponytail_style_rules",
    "caveman_style_output",
    "anvil_compiler_only",
    "anvil_harness_only",
    "anvil_compiler_harness",
]


def load_scenario(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_benchmark(
    scenario: dict[str, Any],
    *,
    compiled_plan: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    offline_synthetic: bool = False,
) -> BenchmarkReport:
    measurements = _explicit_measurements(scenario)
    present = {m.variant for m in measurements}
    if offline_synthetic:
        measurements.extend(
            _synthetic_measurement(
                variant,
                scenario=scenario,
                compiled_plan=compiled_plan,
                contract=contract,
            )
            for variant in VARIANTS
            if variant not in present
        )

    if not measurements:
        raise ValueError("No benchmark measurements provided. Add scenario measurements or use --offline-synthetic.")

    measurements = sorted(measurements, key=lambda item: VARIANTS.index(item.variant) if item.variant in VARIANTS else 999)
    return BenchmarkReport(
        scenario_name=str(scenario.get("name", "unnamed")),
        request=str(scenario.get("request", "")),
        variants=measurements,
        winner_by_cost=_winner_by_cost(measurements),
        winner_by_quality=_winner_by_quality(measurements),
        metadata={
            "mode": "synthetic_offline" if any(m.mode == "synthetic_offline" for m in measurements) else "measured",
            "variant_count": len(measurements),
            "comparison_set": VARIANTS,
        },
    )


def write_report(report: BenchmarkReport, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_jsonable(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _explicit_measurements(scenario: dict[str, Any]) -> list[BenchmarkMeasurement]:
    values = []
    for item in scenario.get("measurements", []):
        values.append(
            BenchmarkMeasurement(
                variant=str(item["variant"]),
                input_tokens=int(item["input_tokens"]),
                output_tokens=int(item["output_tokens"]),
                tool_schema_tokens=int(item["tool_schema_tokens"]),
                wall_time_ms=int(item["wall_time_ms"]),
                patch_size_bytes=int(item["patch_size_bytes"]),
                tests_passed=int(item["tests_passed"]),
                tests_total=int(item["tests_total"]),
                rehydrations=int(item.get("rehydrations", 0)),
                unnecessary_files_prevented=int(item.get("unnecessary_files_prevented", 0)),
                unnecessary_deps_prevented=int(item.get("unnecessary_deps_prevented", 0)),
                completed=bool(item.get("completed", True)),
                mode=str(item.get("mode", "measured")),
                notes=str(item.get("notes", "")),
                provider=str(item.get("provider", "")),
                model=str(item.get("model", "")),
                provider_usage=dict(item.get("provider_usage", {})),
                artifacts=dict(item.get("artifacts", {})),
            )
        )
    return values


def _synthetic_measurement(
    variant: str,
    *,
    scenario: dict[str, Any],
    compiled_plan: dict[str, Any] | None,
    contract: dict[str, Any] | None,
) -> BenchmarkMeasurement:
    context_tokens = int(scenario.get("context_tokens", 8000))
    request_tokens = max(1, len(str(scenario.get("request", "")).split()))
    tool_schema_tokens = int(scenario.get("tool_schema_tokens", 2000))
    output_tokens = int(scenario.get("expected_output_tokens", 1200))
    patch_size = int(scenario.get("expected_patch_size_bytes", 4000))
    tests_total = int(scenario.get("tests_total", 1))

    base_input = context_tokens + request_tokens + tool_schema_tokens
    factors = {
        "baseline_claude_code": (1.00, 1.00, 1.00, 1.00, 0, 0),
        "ponytail_style_rules": (0.94, 0.95, 0.92, 0.96, 0, 0),
        "caveman_style_output": (0.86, 0.78, 0.78, 0.90, 0, 0),
        "anvil_compiler_only": (0.58, 0.82, 0.74, 0.88, 0, 0),
        "anvil_harness_only": (1.02, 0.92, 0.84, 1.08, 1, 1),
        "anvil_compiler_harness": (0.54, 0.72, 0.62, 0.94, 1, 1),
    }
    input_factor, output_factor, patch_factor, time_factor, files_prevented, deps_prevented = factors[variant]

    if compiled_plan and variant in {"anvil_compiler_only", "anvil_compiler_harness"}:
        input_tokens = int(compiled_plan.get("metrics", {}).get("prompt_package_tokens", base_input * input_factor))
        tool_schema_tokens = int(
            sum(max(1, int(tool.get("token_estimate", 0))) for tool in compiled_plan.get("loaded_tools", []))
            or tool_schema_tokens * input_factor
        )
        rehydrations = len(compiled_plan.get("zones", [{}])[3].get("ledger_refs", [])) if len(compiled_plan.get("zones", [])) > 3 else 0
    else:
        input_tokens = int(base_input * input_factor)
        rehydrations = 0

    if contract and variant in {"anvil_harness_only", "anvil_compiler_harness"}:
        files_prevented = max(files_prevented, int(contract.get("metadata", {}).get("scope_blocks", 0)))

    return BenchmarkMeasurement(
        variant=variant,
        input_tokens=max(1, input_tokens),
        output_tokens=max(1, int(output_tokens * output_factor)),
        tool_schema_tokens=max(0, int(tool_schema_tokens)),
        wall_time_ms=max(1, int(int(scenario.get("wall_time_ms", 60_000)) * time_factor)),
        patch_size_bytes=max(0, int(patch_size * patch_factor)),
        tests_passed=tests_total,
        tests_total=tests_total,
        rehydrations=rehydrations,
        unnecessary_files_prevented=files_prevented,
        unnecessary_deps_prevented=deps_prevented,
        completed=True,
        mode="synthetic_offline",
        notes="Deterministic smoke estimate; replace with measured provider runs before making benchmark claims.",
    )


def _winner_by_cost(measurements: list[BenchmarkMeasurement]) -> str:
    def cost(item: BenchmarkMeasurement) -> tuple[int, int, int]:
        return (item.input_tokens + item.output_tokens + item.tool_schema_tokens, item.wall_time_ms, item.patch_size_bytes)

    return min(measurements, key=cost).variant


def _winner_by_quality(measurements: list[BenchmarkMeasurement]) -> str:
    def quality(item: BenchmarkMeasurement) -> tuple[int, float, int, int, int, int]:
        pass_rate = item.tests_passed / item.tests_total if item.tests_total else 0.0
        return (
            1 if item.completed else 0,
            pass_rate,
            item.tests_total,
            item.unnecessary_files_prevented + item.unnecessary_deps_prevented,
            -item.patch_size_bytes,
            -item.rehydrations,
        )

    return max(measurements, key=quality).variant


def load_optional_json(path: str | None) -> dict[str, Any] | None:
    return load_compiler_plan(path) if path else None


def contract_from_plan_file(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return to_jsonable(compiler_plan_to_contract(load_compiler_plan(path)))

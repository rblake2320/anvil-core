from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


@dataclass(slots=True)
class ContractTask:
    task_id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    tool_name: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    risk: str = "reversible"
    tool_risk: str = "none"
    token_budget: int = 0
    acceptance_checks: list[str] = field(default_factory=list)
    scope_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionContract:
    contract_version: str
    request_id: str
    project_name: str
    normalized_intent: str
    source_plan_hash: str
    tasks: list[ContractTask]
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    tool_policy: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkMeasurement:
    variant: str
    input_tokens: int
    output_tokens: int
    tool_schema_tokens: int
    wall_time_ms: int
    patch_size_bytes: int
    tests_passed: int
    tests_total: int
    rehydrations: int = 0
    unnecessary_files_prevented: int = 0
    unnecessary_deps_prevented: int = 0
    completed: bool = True
    mode: str = "measured"
    notes: str = ""
    provider: str = ""
    model: str = ""
    provider_usage: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkReport:
    scenario_name: str
    request: str
    variants: list[BenchmarkMeasurement]
    winner_by_cost: str
    winner_by_quality: str
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

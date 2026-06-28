from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hashing import sha256_json
from .models import ContractTask, ExecutionContract, to_jsonable


def load_compiler_plan(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compiler_plan_to_contract(plan: dict[str, Any]) -> ExecutionContract:
    scope_in = _extract_scope_list(plan, "scope_paths", "scope_in", "paths")
    scope_out = _extract_scope_list(plan, "scope_out")
    tool_policy = _tool_policy(plan)
    tasks = []
    for node in plan.get("execution_plan", []):
        tool_name = node.get("tool_name")
        node_scope = _node_scope_paths(node) or _scope_roots_to_task_paths(scope_in)
        tool_risk = _tool_risk(tool_name, tool_policy, node)
        task = ContractTask(
            task_id=str(node["node_id"]),
            description=str(node.get("description", "")),
            depends_on=[str(dep) for dep in node.get("depends_on", [])],
            tool_name=tool_name,
            allowed_tools=[str(tool_name)] if tool_name else [],
            risk=_harness_risk(tool_risk),
            tool_risk=tool_risk,
            token_budget=int(node.get("token_budget", 0)),
            acceptance_checks=[str(check) for check in node.get("acceptance_checks", [])],
            scope_paths=node_scope,
            metadata={
                "node_type": node.get("node_type"),
                "inputs": node.get("inputs", {}),
            },
        )
        tasks.append(task)

    return ExecutionContract(
        contract_version="anvil-core-contract-v1",
        request_id=str(plan.get("request_id", "")),
        project_name=str(plan.get("project_name", "default")),
        normalized_intent=str(plan.get("normalized_intent", "")),
        source_plan_hash=str(plan.get("metrics", {}).get("plan_hash") or sha256_json(plan)),
        tasks=tasks,
        scope_in=scope_in,
        scope_out=scope_out,
        tool_policy=tool_policy,
        metadata={
            "cache_key": plan.get("cache_key"),
            "intent_class": plan.get("intent_class"),
            "budget": plan.get("budget", {}),
            "proof_steps": len(plan.get("proof_ledger", [])),
            "evidence_source_uris": _evidence_source_uris(plan),
        },
    )


def write_contract(contract: ExecutionContract, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_jsonable(contract), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def harness_contract_dict(contract: ExecutionContract) -> dict[str, Any]:
    return {
        "mission": contract.normalized_intent,
        "scope_in": contract.scope_in,
        "scope_out": contract.scope_out,
        "context_budget": contract.metadata.get("budget", {}),
        "tasks": [
            {
                "id": task.task_id,
                "title": task.description,
                "risk": task.risk,
                "deps": task.depends_on,
                "tools": task.allowed_tools,
                "paths": task.scope_paths,
                "acceptance": [
                    {
                        "id": f"{task.task_id}_check_{idx}",
                        "description": check,
                        "kind": "manual",
                        "spec": {},
                        "authored_by": "qa",
                    }
                    for idx, check in enumerate(task.acceptance_checks, start=1)
                ],
            }
            for task in contract.tasks
        ],
    }


def _extract_scope_list(plan: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    candidates: list[Any] = [plan, plan.get("metadata", {})]
    candidates.extend(zone.get("metadata", {}) for zone in plan.get("zones", []) if isinstance(zone, dict))
    for node in plan.get("execution_plan", []):
        if isinstance(node, dict):
            candidates.append(node.get("metadata", {}))
            candidates.append(node.get("inputs", {}))

    for source in candidates:
        if not isinstance(source, dict):
            continue
        for key in keys:
            _extend_unique(values, source.get(key))
    return values


def _evidence_source_uris(plan: dict[str, Any]) -> list[str]:
    values: list[str] = []
    metadata = plan.get("metadata", {})
    if isinstance(metadata, dict):
        _extend_unique(values, metadata.get("evidence_source_uris"))
    for zone in plan.get("zones", []):
        if isinstance(zone, dict) and isinstance(zone.get("metadata"), dict):
            _extend_unique(values, zone["metadata"].get("source_uris"))
    return values


def _node_scope_paths(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in (node.get("metadata", {}), node.get("inputs", {})):
        if isinstance(source, dict):
            _extend_unique(values, source.get("scope_paths"))
            _extend_unique(values, source.get("paths"))
    return values


def _scope_roots_to_task_paths(scope_in: list[str]) -> list[str]:
    paths: list[str] = []
    for scope in scope_in:
        item = scope.strip().replace("\\", "/")
        if not item:
            continue
        if any(ch in item for ch in "*?[]"):
            candidate = item
        elif item.endswith("/"):
            candidate = f"{item}*"
        elif Path(item).suffix:
            candidate = item
        else:
            candidate = f"{item}/*"
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _tool_policy(plan: dict[str, Any]) -> dict[str, Any]:
    metadata = plan.get("metadata", {})
    policy = dict(metadata.get("tool_policy", {})) if isinstance(metadata, dict) and isinstance(metadata.get("tool_policy"), dict) else {}
    loaded_risks = dict(policy.get("loaded_tool_risks", {}))
    deferred_risks = dict(policy.get("deferred_tool_risks", {}))
    for tool in plan.get("loaded_tools", []):
        if isinstance(tool, dict):
            loaded_risks[str(tool.get("name", ""))] = str(tool.get("risk", "low"))
    for tool in plan.get("deferred_tools", []):
        if isinstance(tool, dict):
            deferred_risks[str(tool.get("name", ""))] = str(tool.get("risk", "low"))
    loaded_risks.pop("", None)
    deferred_risks.pop("", None)
    irreversible = sorted(name for name, risk in {**loaded_risks, **deferred_risks}.items() if risk == "high")
    return {
        **policy,
        "loaded_tool_risks": loaded_risks,
        "deferred_tool_risks": deferred_risks,
        "irreversible_tools": irreversible,
    }


def _tool_risk(tool_name: Any, tool_policy: dict[str, Any], node: dict[str, Any]) -> str:
    if isinstance(node.get("risk"), str):
        return str(node["risk"])
    if not tool_name:
        return "none"
    name = str(tool_name)
    for key in ("loaded_tool_risks", "deferred_tool_risks"):
        risks = tool_policy.get(key, {})
        if isinstance(risks, dict) and name in risks:
            return str(risks[name])
    return "low"


def _harness_risk(tool_risk: str) -> str:
    return "irreversible" if tool_risk == "high" else "reversible"


def _extend_unique(target: list[str], raw: Any) -> None:
    if raw is None:
        return
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple, set)):
        items = [str(item) for item in raw]
    else:
        items = [str(raw)]
    for item in items:
        item = item.strip().replace("\\", "/")
        if item and item not in target:
            target.append(item)

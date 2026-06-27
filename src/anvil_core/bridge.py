from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hashing import sha256_json
from .models import ContractTask, ExecutionContract, to_jsonable


def load_compiler_plan(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compiler_plan_to_contract(plan: dict[str, Any]) -> ExecutionContract:
    tasks = []
    for node in plan.get("execution_plan", []):
        task = ContractTask(
            task_id=str(node["node_id"]),
            description=str(node.get("description", "")),
            depends_on=[str(dep) for dep in node.get("depends_on", [])],
            tool_name=node.get("tool_name"),
            token_budget=int(node.get("token_budget", 0)),
            acceptance_checks=[str(check) for check in node.get("acceptance_checks", [])],
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
        metadata={
            "cache_key": plan.get("cache_key"),
            "intent_class": plan.get("intent_class"),
            "budget": plan.get("budget", {}),
            "proof_steps": len(plan.get("proof_ledger", [])),
        },
    )


def write_contract(contract: ExecutionContract, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_jsonable(contract), indent=2, sort_keys=True) + "\n", encoding="utf-8")


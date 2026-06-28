from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def load_harness_contract(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_harness_contract(
    payload: dict[str, Any],
    *,
    run_dir: str | Path | None = None,
    mode: str = "simulated",
    approve_irreversible: bool = True,
) -> dict[str, Any]:
    if mode != "simulated":
        raise ValueError(f"Unsupported harness contract mode: {mode}")

    try:
        from anvil import (  # type: ignore[import-not-found]
            AcceptanceCheck,
            Contract,
            Lifecycle,
            MissionStore,
            Risk,
            SimulatedAgent,
            SimulatedVerifier,
            Task,
            ToolCall,
        )
    except ImportError as exc:  # pragma: no cover - exercised when package is not installed.
        raise RuntimeError("anvil-harness must be installed to run harness contracts") from exc

    task_objects: list[Task] = []
    verdicts: dict[str, bool] = {}
    for task_data in payload.get("tasks", []):
        acceptance = []
        for check_data in task_data.get("acceptance", []):
            check = AcceptanceCheck(
                id=str(check_data["id"]),
                description=str(check_data.get("description", "")),
                kind=str(check_data.get("kind", "manual")),
                spec=dict(check_data.get("spec", {})),
                authored_by=str(check_data.get("authored_by", "qa")),
            )
            acceptance.append(check)
            verdicts[check.id] = True

        task = Task(
            id=str(task_data["id"]),
            title=str(task_data.get("title", task_data["id"])),
            risk=Risk(str(task_data.get("risk", "reversible"))),
            deps=[str(dep) for dep in task_data.get("deps", [])],
            tools=[str(tool) for tool in task_data.get("tools", [])],
            paths=[str(path).replace("\\", "/") for path in task_data.get("paths", [])],
            acceptance=acceptance,
        )
        task_objects.append(task)

    contract = Contract(
        mission=str(payload.get("mission", "")),
        scope_in=[str(item).replace("\\", "/") for item in payload.get("scope_in", [])],
        scope_out=[str(item).replace("\\", "/") for item in payload.get("scope_out", [])],
        context_budget=dict(payload.get("context_budget", {})),
        tasks=task_objects,
    )

    temp_ctx = tempfile.TemporaryDirectory() if run_dir is None else None
    root = Path(run_dir or temp_ctx.name)
    root.mkdir(parents=True, exist_ok=True)

    def calls_for(task: Task) -> list[ToolCall]:
        if not task.tools:
            return []
        return [ToolCall(tool=task.tools[0], paths=list(task.paths[:1]), task_id=task.id, risk=task.risk)]

    lifecycle = Lifecycle(
        MissionStore(root),
        SimulatedAgent(calls_for=calls_for),
        SimulatedVerifier(verdicts),
        approval_fn=lambda _task, _call: approve_irreversible,
    )

    try:
        steps = [
            lifecycle.intake(contract.mission or "ANVIL harness contract run"),
            lifecycle.baseline({"ref": "anvil-core-simulated"}),
            lifecycle.compile(contract),
            lifecycle.review(),
        ]
        if steps[-1].halted:
            return _report(lifecycle, root, steps, ok=False, reason=steps[-1].note)

        execute_result = lifecycle.execute_all()
        steps.append(execute_result)
        if execute_result.halted:
            return _report(lifecycle, root, steps, ok=False, reason=execute_result.note)

        learn_result = lifecycle.learn(["anvil-core simulated harness contract completed"])
        steps.append(learn_result)
        audit_ok, audit_reason = lifecycle.audit()
        ok = audit_ok and not learn_result.halted
        return _report(
            lifecycle,
            root,
            steps,
            ok=ok,
            reason=audit_reason or learn_result.note,
            audit_ok=audit_ok,
        )
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


def _report(lifecycle: Any, root: Path, steps: list[Any], *, ok: bool, reason: str | None, audit_ok: bool | None = None) -> dict[str, Any]:
    audit_result = lifecycle.audit()
    final_audit_ok = audit_ok if audit_ok is not None else audit_result[0]
    return {
        "ok": ok,
        "mode": "simulated",
        "run_dir": str(root),
        "phase": lifecycle.phase.value,
        "audit_ok": final_audit_ok,
        "reason": reason,
        "ledger": str(lifecycle.store.ledger_path),
        "steps": [{"phase": step.phase.value, "note": step.note, "halted": step.halted} for step in steps],
        "tasks": {
            task.id: {
                "status": task.status.value,
                "strikes": task.strikes,
                "evidence_count": len(task.evidence),
            }
            for task in lifecycle.contract.tasks
        }
        if lifecycle.contract
        else {},
    }

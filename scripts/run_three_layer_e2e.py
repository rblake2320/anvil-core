from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ANVIL compiler -> core -> harness artifact smoke.")
    parser.add_argument("--compiler-root", required=True)
    parser.add_argument("--harness-root", required=True)
    parser.add_argument("--core-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--workdir")
    parser.add_argument("--skip-harness-tests", action="store_true")
    args = parser.parse_args(argv)

    compiler_root = Path(args.compiler_root).resolve()
    harness_root = Path(args.harness_root).resolve()
    core_root = Path(args.core_root).resolve()

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(args.workdir).resolve() if args.workdir else Path(td)
        workdir.mkdir(parents=True, exist_ok=True)
        plan_path = workdir / "plan.json"
        prompt_path = workdir / "compiled_prompt.txt"
        ledger_path = workdir / "anvil_ledger.sqlite3"
        contract_path = workdir / "contract.json"
        harness_contract_path = workdir / "harness_contract.json"
        harness_run_path = workdir / "harness_run"
        harness_report_path = workdir / "harness_run_report.json"
        report_path = workdir / "benchmark_report.json"

        for root in (compiler_root, harness_root, core_root):
            _run([sys.executable, "-m", "pip", "install", "-e", str(root)])

        _run(
            [
                sys.executable,
                "-m",
                "anvil_context_compiler.cli",
                "compile",
                "--request",
                "Build the smallest correct agent context plan",
                "--context-file",
                str(compiler_root / "examples" / "sample_context.md"),
                "--tool-file",
                str(compiler_root / "examples" / "tools.json"),
                "--scope-path",
                "src",
                "--scope-out",
                "prod",
                "--ledger",
                str(ledger_path),
                "--out",
                str(plan_path),
                "--prompt-out",
                str(prompt_path),
            ]
        )
        _run([sys.executable, "-m", "anvil_context_compiler.cli", "verify-ledger", "--ledger", str(ledger_path), "--require-anchor"])
        _run(
            [
                sys.executable,
                "-m",
                "anvil_core.cli",
                "compile-contract",
                "--plan",
                str(plan_path),
                "--out",
                str(contract_path),
                "--harness-out",
                str(harness_contract_path),
            ],
            cwd=core_root,
        )
        _run(
            [
                sys.executable,
                "-m",
                "anvil_core.cli",
                "run-harness-contract",
                "--harness-contract",
                str(harness_contract_path),
                "--mode",
                "simulated",
                "--run-dir",
                str(harness_run_path),
                "--out",
                str(harness_report_path),
            ],
            cwd=core_root,
        )
        _run(
            [
                sys.executable,
                "-m",
                "anvil_core.cli",
                "benchmark",
                "--scenario",
                str(core_root / "examples" / "benchmark_scenario.json"),
                "--compiled-plan",
                str(plan_path),
                "--contract",
                str(contract_path),
                "--offline-synthetic",
                "--out",
                str(report_path),
            ],
            cwd=core_root,
        )

        contract = _read_json(contract_path)
        harness_contract = _read_json(harness_contract_path)
        harness_report = _read_json(harness_report_path)
        report = _read_json(report_path)
        assert contract["scope_in"] == ["src"]
        assert contract["scope_out"] == ["prod"]
        assert all(task["scope_paths"] == ["src/*"] for task in contract["tasks"])
        assert harness_contract["scope_in"] == ["src"]
        assert harness_contract["tasks"][0]["paths"] == ["src/*"]
        assert harness_report["ok"] is True
        assert harness_report["audit_ok"] is True
        assert harness_report["phase"] == "done"
        assert len(report["variants"]) == 6

        if not args.skip_harness_tests:
            _run([sys.executable, "-m", "pip", "install", "pytest"])
            _run([sys.executable, "-m", "pytest", "-q"], cwd=harness_root)

        print(json.dumps({"ok": True, "workdir": str(workdir), "variants": len(report["variants"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

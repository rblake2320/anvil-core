from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import contract_from_plan_file, load_optional_json, load_scenario, run_benchmark, write_report
from .bridge import compiler_plan_to_contract, harness_contract_dict, load_compiler_plan, write_contract
from .harness_runner import load_harness_contract, run_harness_contract
from .models import to_jsonable


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    Path(".anvil-core").mkdir(exist_ok=True)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import contract_from_plan_file, load_optional_json, load_scenario, run_benchmark, write_report
from .bridge import compiler_plan_to_contract, load_compiler_plan, write_contract
from .models import to_jsonable


def cmd_compile_contract(args: argparse.Namespace) -> int:
    plan = load_compiler_plan(args.plan)
    contract = compiler_plan_to_contract(plan)
    write_contract(contract, args.out)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anvil-core", description="ANVIL integration and benchmark CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile-contract", help="Convert an ANVIL compiler plan into a harness contract artifact")
    c.add_argument("--plan", required=True)
    c.add_argument("--out", required=True)
    c.set_defaults(func=cmd_compile_contract)

    b = sub.add_parser("benchmark", help="Generate a repeatable benchmark report")
    b.add_argument("--scenario", required=True)
    b.add_argument("--compiled-plan")
    b.add_argument("--contract")
    b.add_argument("--offline-synthetic", action="store_true")
    b.add_argument("--out")
    b.set_defaults(func=cmd_benchmark)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    Path(".anvil-core").mkdir(exist_ok=True)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())


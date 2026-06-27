# ANVIL Core

ANVIL Core is the integration and benchmark layer between:

```text
anvil-context-compiler -> compiled prompt package + execution DAG
anvil-harness          -> governed execution, policy, proof gate, audit ledger
anvil-core             -> bridge artifacts, provider adapters, repeatable benchmarks
```

It is intentionally small and zero-dependency. The first goal is not to claim model wins; it is to make measurements repeatable.

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests
```

## Convert a compiler plan into a harness contract

```powershell
anvil-core compile-contract `
  --plan ..\anvil_context_compiler\.anvil\plan.json `
  --out .\.anvil-core\contract.json
```

The contract is a portable JSON artifact that maps compiler DAG nodes to governed execution tasks: task ID, dependencies, tool name, token budget, and locked acceptance checks.

## Run a benchmark

Use explicit measurements when benchmarking real providers:

```powershell
anvil-core benchmark `
  --scenario .\examples\benchmark_scenario.json `
  --compiled-plan ..\anvil_context_compiler\.anvil\plan.json `
  --contract .\.anvil-core\contract.json `
  --out .\.anvil-core\benchmark_report.json
```

For CI and demos, `--offline-synthetic` fills missing variants with deterministic estimates. Reports label this clearly as synthetic.

```powershell
anvil-core benchmark `
  --scenario .\examples\benchmark_scenario.json `
  --compiled-plan ..\anvil_context_compiler\.anvil\plan.json `
  --offline-synthetic `
  --out .\.anvil-core\benchmark_report.json
```

## Variants

The benchmark schema tracks the product comparison set:

- `baseline_claude_code`
- `ponytail_style_rules`
- `caveman_style_output`
- `anvil_compiler_only`
- `anvil_harness_only`
- `anvil_compiler_harness`

Measured fields:

- input tokens
- output tokens
- tool-schema tokens
- wall time
- patch size
- test pass rate
- rehydration count
- unnecessary files prevented
- unnecessary dependencies prevented

## Current Scope

This package creates the bridge and benchmark harness. Live provider adapters for Claude Code, OpenAI, Ollama, and SelfConnect belong behind the adapter interfaces in `src/anvil_core/adapters.py`.


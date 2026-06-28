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
  --out .\.anvil-core\contract.json `
  --harness-out .\.anvil-core\harness_contract.json
```

The contract is a portable JSON artifact that maps compiler DAG nodes to governed execution tasks: task ID, dependencies, allowed tools, tool risk, harness risk, token budget, scope paths, and locked acceptance checks.

`--harness-out` also writes a JSON artifact shaped like `anvil-harness` contract data:

- `scope_in`
- `scope_out`
- task `paths`
- task `tools`
- task `risk`
- QA-authored acceptance checks

## Execute a Generated Harness Contract

After producing `harness_contract.json`, run it through the real `anvil-harness` lifecycle in deterministic simulated mode:

```powershell
anvil-core run-harness-contract `
  --harness-contract .\.anvil-core\harness_contract.json `
  --mode simulated `
  --run-dir .\.anvil-core\harness-run `
  --out .\.anvil-core\harness_run_report.json
```

This loads the JSON as `anvil.store.Contract`, creates a `MissionStore`, runs `Lifecycle` with `SimulatedAgent` and `SimulatedVerifier`, executes the contract, calls `learn`, and fails if the harness ledger audit fails.

## Run a benchmark

Use explicit measurements when benchmarking real providers:

```powershell
anvil-core benchmark `
  --scenario .\examples\benchmark_scenario.json `
  --compiled-plan ..\anvil_context_compiler\.anvil\plan.json `
  --contract .\.anvil-core\contract.json `
  --out .\.anvil-core\benchmark_report.json
```

## Measure a Provider

Measured provider adapters are available for:

- `ollama`: local `/api/generate`, no API key
- `openai`: OpenAI `/chat/completions`, `OPENAI_API_KEY`
- `openrouter`: OpenRouter `/chat/completions`, `OPENROUTER_API_KEY`

Each adapter records provider-reported token/timing or usage data and saves proof artifacts.

```powershell
anvil-core measure-provider `
  --provider ollama `
  --variant baseline_claude_code `
  --model llama3.2 `
  --scenario .\examples\benchmark_scenario.json `
  --prompt-file .\.anvil-core\raw_prompt.txt `
  --artifact-dir .\.anvil-core\artifacts\baseline_ollama `
  --out .\.anvil-core\measurements\baseline_ollama.json
```

OpenAI API example:

```powershell
anvil-core measure-provider `
  --provider openai `
  --variant baseline_claude_code `
  --model gpt-4o-mini `
  --scenario .\examples\benchmark_scenario.json `
  --artifact-dir .\.anvil-core\artifacts\baseline_openai `
  --out .\.anvil-core\measurements\baseline_openai.json `
  --options-json '{"max_completion_tokens":16}'
```

OpenRouter API example:

```powershell
anvil-core measure-provider `
  --provider openrouter `
  --variant baseline_claude_code `
  --model openrouter/auto `
  --scenario .\examples\benchmark_scenario.json `
  --artifact-dir .\.anvil-core\artifacts\baseline_openrouter `
  --out .\.anvil-core\measurements\baseline_openrouter.json `
  --options-json '{"max_tokens":16}'
```

Artifacts include:

- `raw_prompt.txt`
- `provider_request.json`
- `provider_output.txt`
- `provider_raw_response.json`
- `provider_usage.json`
- `measurement.json`

Then include the measured output in a benchmark report:

```powershell
anvil-core benchmark `
  --scenario .\examples\benchmark_scenario.json `
  --measurement-file .\.anvil-core\measurements\baseline_ollama.json `
  --out .\.anvil-core\benchmark_report.json
```

Run the live provider tests with real provider access:

```powershell
$env:ANVIL_OLLAMA_LIVE_MODEL = "qwen2.5:7b"
$env:ANVIL_OLLAMA_BASE_URL = "http://127.0.0.1:11434"

$env:ANVIL_OPENAI_LIVE_MODEL = "gpt-4o-mini"
$env:OPENAI_API_KEY = "<real key>"

$env:ANVIL_OPENROUTER_LIVE_MODEL = "openrouter/auto"
$env:OPENROUTER_API_KEY = "<real key>"

python -m unittest tests.test_providers -v
```

Provider tests do not use fake servers. If a provider's explicit live model variable is unset, that provider's tests skip instead of fabricating measurements. If the live model variable is set but the API key, local server, or model is unavailable, the test fails.

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

The full 10/10 product target is tracked in `docs/ANVIL_10_OUT_OF_10.md`.

## Three-layer Smoke

From this repo, run the local end-to-end artifact flow:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_three_layer_e2e.py `
  --compiler-root ..\anvil_context_compiler `
  --harness-root ..\anvil-harness `
  --core-root .
```

This installs all three repos into the active Python environment, then runs:

```text
compile -> verify-ledger -> compile-contract -> run-harness-contract -> benchmark
```

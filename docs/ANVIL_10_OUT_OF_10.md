# ANVIL 10/10 Target

ANVIL 10/10 means integrated, executed, measured, defensible, repeatable, and hard to copy.

## Required Capabilities

1. Execute generated contracts through `anvil-harness` Lifecycle.
   - `anvil-core run-harness-contract`
   - compile output -> core harness contract -> Lifecycle intake/baseline/compile/review/execute_all/learn/audit

2. Add real measured provider adapters.
   - Claude Code
   - OpenAI
   - Ollama/local
   - optional SelfConnect

3. Run real six-way benchmarks.
   - `baseline_claude_code`
   - `ponytail_style_rules`
   - `caveman_style_output`
   - `anvil_compiler_only`
   - `anvil_harness_only`
   - `anvil_compiler_harness`

4. Benchmark at least 10 realistic tasks.
   - small bug fix
   - medium feature
   - repo scan
   - RAG-heavy answer
   - tool-heavy task
   - API build
   - PowerShell automation
   - refactor
   - test failure repair
   - multi-step agent workflow

5. Save benchmark proof artifacts.
   - raw prompt
   - compiled prompt
   - tool manifest
   - provider usage
   - patch diff
   - test output
   - ledger audit
   - final report

6. Add token-accurate tokenizer adapters.
   - local heuristic
   - OpenAI/tiktoken optional
   - Anthropic estimate adapter
   - provider-reported usage adapter

7. Add pluggable compression/reranking.
   - lexical
   - BM25-style
   - embedding rerank
   - LLM/extractive compressor
   - policy-preserving compressor
   - no-compression control

8. Harden anchors.
   - HMAC signed anchor
   - external anchor option
   - harness-ledger anchor option
   - append-only anchor history

9. Add release packaging.
   - pipx install
   - Docker image
   - Windows PowerShell installer
   - Makefile or task runner
   - versioned release artifacts
   - checksums

10. Add enterprise/security posture.
    - threat model
    - tenant isolation
    - ledger sensitivity policy
    - secret handling
    - network exposure rules
    - audit export
    - SBOM
    - license clarity

11. Add patent-ready disclosure set.
    - context compiler claims
    - reversible compression ledger claims
    - tool-surface compiler claims
    - budget governor claims
    - YAGNI execution gate claims
    - compiler-to-harness proof chain claims
    - benchmark/proof artifact claims

## Current Status

Done:

- Generated harness contracts execute through `anvil-harness` Lifecycle in simulated mode.
- Three-layer E2E now runs compile, ledger verification, contract generation, harness execution, benchmark generation, and harness tests.
- Local/Ollama measured provider adapter records provider-reported token/timing usage and proof artifacts.
- Synthetic benchmarks are clearly labeled and suitable only for CI/demo smoke.

Next:

- Add OpenAI and Claude Code measured provider adapters.
- Persist benchmark proof artifacts.
- Add signed/external anchor support.

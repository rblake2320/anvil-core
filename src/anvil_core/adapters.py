from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import BenchmarkMeasurement, ExecutionContract


class ContextCompilerAdapter(Protocol):
    def compile_request(self, request: str, context_files: list[Path]) -> Path:
        """Return a path to an ANVIL compiler plan JSON artifact."""


class ExecutionHarnessAdapter(Protocol):
    def execute_contract(self, contract: ExecutionContract) -> BenchmarkMeasurement:
        """Execute a governed contract and return measured run metrics."""


class ProviderBenchmarkAdapter(Protocol):
    def run_variant(self, variant: str, request: str, context_files: list[Path]) -> BenchmarkMeasurement:
        """Run one provider/baseline variant and return measured metrics."""


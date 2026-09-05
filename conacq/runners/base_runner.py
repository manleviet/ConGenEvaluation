"""
Base classes for constraint acquisition runners.

BaseRunResult: Shared result dataclass, common to every runner.
BaseRunner: ABC defining build-once/run-many/cleanup-once lifecycle.
"""

from typing import List, Dict, Any, Optional, Sequence
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .metrics import RunMetrics


@dataclass
class BaseRunResult:
    """Base result shared by ConGen and Interactive runners.

    Attributes:
        kb_constraints: Constraint names in learned KB
        kb_clauses: CNF clauses of the learned KB
        bg_clauses: Background knowledge clauses (root constraint)
        n_bias: Original number of bias constraints
        n_kb: Final KB size
        runtime_ms: Execution time in milliseconds
        consistency_checks: Number of SAT solver calls
        memory_peak_mb: Peak memory usage in MB
        profiler_data: Full profiler snapshot
    """
    # KB result
    kb_constraints: List[str]
    kb_clauses: List[List[int]]
    bg_clauses: Sequence[Sequence[int]]
    n_bias: int
    n_kb: int

    # Core performance metrics
    runtime_ms: float
    consistency_checks: int
    memory_peak_mb: float

    # kw_only defaults: allow child classes to add required positional fields.
    profiler_data: Dict[str, Any] = field(default_factory=dict, kw_only=True)
    # The declarative metric bundle (RunMetrics) this run produced, built via
    # metrics.collect(profiler, <ALGO>_METRICS). The per-run ``performance`` block
    # is derived from it — see _base_to_dict.
    metrics: Optional[RunMetrics] = field(default=None, kw_only=True)

    def _base_to_dict(self) -> dict:
        """Shared serialization for base fields."""
        perf = dict(self.metrics.to_dict()) if self.metrics is not None else {
            'runtime_ms': self.runtime_ms,
            'consistency_checks': self.consistency_checks,
            'memory_peak_mb': self.memory_peak_mb,
        }
        perf['profiler'] = self.profiler_data
        return {
            'kb_constraints': self.kb_constraints,
            'bg_clauses': self.bg_clauses,
            'n_bias': self.n_bias,
            'n_kb': self.n_kb,
            'performance': perf,
        }


class BaseRunner(ABC):
    """ABC for constraint acquisition runners.

    Lifecycle: __init__ (build once) -> run (many) -> cleanup (once).
    Oracle created once in __init__, shared across all runs.
    """

    def __init__(self, bias_path: str, fm_path: str, solver_name: str = 'glucose4',
                 use_incremental: bool = True):
        self.bias_path = bias_path
        self.fm_path = fm_path
        self.solver_name = solver_name
        # Solver mode is the runner's, not the model's — the runner passes it
        # straight to build_checker instead of round-tripping through the model.
        self.use_incremental = use_incremental

        # Create oracle once (reused across runs)
        from conacq.oracle import FMOracle
        self.oracle = FMOracle(
            fm_path, solver_name=solver_name, use_incremental=use_incremental)

    @abstractmethod
    def run(self, positive_examples=None, negative_examples=None,
            shuffle_seed=None) -> BaseRunResult:
        """Run acquisition and return result."""
        ...

    @property
    @abstractmethod
    def feature_ids(self) -> Dict[str, int]:
        """Feature name -> SAT variable ID mapping."""
        ...

    def cleanup(self):
        """Release oracle resources."""
        if hasattr(self, 'oracle') and self.oracle is not None:
            self.oracle.cleanup()

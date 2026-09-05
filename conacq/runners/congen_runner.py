"""
Run ConGen and collect performance metrics.

Runs ConGen directly to:
1. Support cross-validation (each fold needs to train a new KB)
2. Collect performance metrics (#checks, runtime, memory, n_mss, n_kb)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field, replace
import random
import tracemalloc
import logging

from conacq.algorithms.acqmss.congen import ConGen
from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
from explanation.api import build_checker, SolverBackend
from profiling import profiler_session, ProfilerPreset

from .base_runner import BaseRunResult, BaseRunner
from .metrics import CONGEN_METRICS, collect


@dataclass
class ConGenRunResult(BaseRunResult):
    """
    Result of running ConGen with metrics.

    Inherits the shared fields from BaseRunResult (including the declarative
    ``metrics`` RunMetrics bundle). Adds ConGen-specific: redundant_constraints,
    n_mss. The extended profiler metrics are no longer hand-listed here — they
    live in ``metrics`` (built via ``collect(profiler, CONGEN_METRICS)``).
    """
    redundant_constraints: List[str] = field(default_factory=list)
    n_mss: int = 0
    # Memorized ¬e⁻ facts, reported apart from the bias constraints in
    # ``kb_constraints``: |KB| = n_kb + n_ne. They are part of the delivered KB but
    # carry no bias vocabulary, so they stay out of the description/clause/semantic
    # tiers, which score against the bias.
    ne_constraints: List[str] = field(default_factory=list)
    n_ne: int = 0
    # Blocking clauses for the memorized ¬e⁻. Part of the DELIVERED theory
    # (Algorithm 3: KB <- B' u NE), kept as their own list because kb_clauses mirrors
    # kb_constraints, which is bias-only.
    ne_clauses: List[List[int]] = field(default_factory=list)
    # NE that Reduce discarded as entailed. Reported so |KB| accounting closes against
    # the NE prepared for acquisition: prepared = n_ne + len(redundant_ne_constraints).
    redundant_ne_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = self._base_to_dict()
        d['redundant_constraints'] = self.redundant_constraints
        d['n_mss'] = self.n_mss
        d['ne_constraints'] = self.ne_constraints
        d['n_ne'] = self.n_ne
        d['ne_clauses'] = self.ne_clauses
        d['redundant_ne_constraints'] = self.redundant_ne_constraints
        return d


class ConGenRunner(BaseRunner):
    """
    Run ConGen and collect performance metrics.

    Builds model once from file paths, reuses via prepare() per fold.

    Metrics collected (Table 7-8 from paper):
    - runtime_ms: Execution time
    - consistency_checks: Number of SAT solver calls
    - memory_peak_mb: Peak memory usage
    - n_mss: MSS size before REDUCE
    - n_kb: Final KB size
    """

    def __init__(
            self,
            bias_path: str,
            fm_path: str,
            solver_name: str = 'glucose4',
            use_incremental: bool = True
    ):
        """
        Initialize runner with file paths. Builds model once (without examples).

        Args:
            bias_path: Path to bias JSON file
            fm_path: Path to feature model (.uvl) file
            solver_name: SAT solver name
            use_incremental: Use incremental solver mode
        """
        super().__init__(bias_path, fm_path, solver_name, use_incremental=use_incremental)

        # Build model (pure bias KB; solver mode is the runner's, examples per run)
        self.model = (ConGenModelBuilder
                      .from_bias(bias_path)
                      .with_oracle_data(self.oracle.oracle_data)
                      .build())

    @property
    def feature_ids(self) -> Dict[str, int]:
        """Feature name -> SAT variable ID mapping (a plain dict — see ADR-0007)."""
        return self.model.name_to_id

    def run(
            self,
            positive_examples: Optional[List[Dict[str, bool]]] = None,
            negative_examples: Optional[List[Dict[str, bool]]] = None,
            shuffle_seed: Optional[int] = None
    ) -> ConGenRunResult:
        """
        Run ConGen with given examples and collect metrics.

        Args:
            positive_examples: List of E+ (each is {feature: True/False})
            negative_examples: List of E- (each is {feature: True/False})
            shuffle_seed: If provided, shuffle bias keys with this seed

        Returns:
            ConGenRunResult with KB and performance metrics
        """
        logging.debug('>>> ConGenRunner.run(E+=%d, E-=%d)',
                      len(positive_examples), len(negative_examples))

        # Create profiler to collect metrics
        with profiler_session(ProfilerPreset.BENCHMARK) as profiler:
            # Start memory tracking
            tracemalloc.start()
            with profiler.timer("congen_total_time"):
                checker = None
                try:
                    # Prepare this fold's task (pure — runs GenerateNE). The model
                    # keeps no task; the prepared task + describe live here locally.
                    prepared = self.model.prepare_task(
                        ConGenTaskInput.from_examples(
                            self.oracle.oracle_data,
                            positive_examples,
                            negative_examples,
                        ),
                        profiler=profiler,
                    )
                    task = prepared.task
                    describe = prepared.describe

                    # Shuffle bias iteration order if seed provided.
                    # Task is frozen: shuffle a copy and rebind, never mutate in place.
                    if shuffle_seed is not None:
                        shuffled_set_c = list(task.set_c)
                        random.Random(shuffle_seed).shuffle(shuffled_set_c)
                        task = replace(task, set_c=shuffled_set_c)
                        logging.debug('Shuffled set_c with seed=%d', shuffle_seed)

                    # Build the checker from the running task (possibly shuffled).
                    # The un-shuffled order is not retained — a fresh prepare_task
                    # rebuilds it deterministically when needed.
                    checker = build_checker(
                        task,
                        SolverBackend.from_flags(use_incremental=self.use_incremental),
                        self.solver_name, profiler
                    )

                    # Run ConGen
                    congen = ConGen(checker, profiler)
                    result = congen.acquire(
                        set_b=task.set_c,
                        set_bg=task.set_b,
                        set_tc=task.set_tc,
                        set_neg_tv=task.set_neg_tv,
                        negation_map=task.negation_map,
                    )

                finally:
                    # Stop memory tracking
                    current, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()

                    # Cleanup checker
                    if checker is not None:
                        checker.cleanup()

            # Collect metrics declaratively from the profiler + the values that
            # do not live in it (memory from tracemalloc, KB sizes from result).
            memory_peak_mb = peak / (1024 * 1024)
            run_metrics = collect(profiler, CONGEN_METRICS, extra={
                'memory_peak_mb': memory_peak_mb,
                'n_mss': result.n_mss,
                'n_kb': result.n_kb,
            })
            runtime_ms = run_metrics.values['runtime_ms']
            consistency_checks = run_metrics.values['consistency_checks']

            profiler_snapshot = profiler.to_dict()

            # Resolve assumption IDs -> clauses/names via the KB (stateless): the
            # describe provider comes from the prepared task, the root BG clauses
            # from the frozen OracleData snapshot.
            (bg_clauses, kb_clauses, kb_names, ne_clauses, ne_names,
             redundant_names, redundant_ne_names) = \
                self.model.resolve_result(
                    result, describe, self.oracle.oracle_data.get_root_clauses(),
                    set_kb=task.set_kb, negation_map=task.negation_map)

            # ``result.n_kb`` counts the post-Reduce KB as a whole (B′ ∪ NE). Report
            # the two populations apart: ``n_kb`` is bias constraints only, so it
            # is reported separately, and ``n_ne`` carries the
            # memorized ¬e⁻ facts. |KB| = n_kb + n_ne. Both are read off the resolved
            # POST-Reduce ids, never off the prepared task — Reduce runs on B′ ∪ NE and
            # can drop an NE as entailed, which an at-prep count would miss.
            run_result = ConGenRunResult(
                kb_constraints=kb_names,
                ne_constraints=ne_names,
                kb_clauses=kb_clauses,
                ne_clauses=ne_clauses,
                bg_clauses=bg_clauses,
                redundant_constraints=redundant_names,
                redundant_ne_constraints=redundant_ne_names,
                n_bias=result.n_bias,
                n_mss=result.n_mss,
                n_kb=len(kb_names),
                n_ne=len(ne_names),
                runtime_ms=runtime_ms,
                consistency_checks=consistency_checks,
                memory_peak_mb=memory_peak_mb,
                metrics=run_metrics,
                profiler_data=profiler_snapshot
            )

            logging.debug('<<< ConGenRunner: KB=%d, runtime=%.2fms, checks=%d',
                          result.n_kb, runtime_ms, consistency_checks)

        return run_result

"""Progressive evaluation engine for QuAcq->ConGen comparison.

Runs ConGen at multiple query-budget checkpoints and compares each
resulting KB against ground truth C_T.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

from conacq.examples.query_converter import queries_to_assignment_lists
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker, SemanticResult
from conacq.eval.result_loader import ConGenResultData
from conacq.eval.kb_comparator import KBComparator, ComparationStrategy, ComparationResult
from conacq.oracle.ground_truth import GroundTruthData
from conacq.runners.congen_runner import ConGenRunner, ConGenRunResult
from conacq.runners.quacq_runner import QuAcqRunResult


@dataclass
class CheckpointResult:
    """Result at a single query-budget checkpoint.

    Attributes:
        checkpoint_pct: Percentage of total queries used
        n_queries: Absolute number of queries used
        n_positive: Number of positive examples
        n_negative: Number of negative examples
        n_kb: ConGen KB size at this checkpoint
        description_comparison: ComparationResult (description strategy)
        clause_comparison: ComparationResult (clause strategy)
        semantic_result: SemanticResult
        congen_runtime_ms: ConGen execution time
    """
    checkpoint_pct: int
    n_queries: int
    n_positive: int
    n_negative: int
    n_kb: int
    description_comparison: Optional[ComparationResult] = None
    clause_comparison: Optional[ComparationResult] = None
    semantic_result: Optional[SemanticResult] = None
    congen_runtime_ms: float = 0.0

    def to_dict(self) -> dict:
        result = {
            'checkpoint_pct': self.checkpoint_pct,
            'n_queries': self.n_queries,
            'n_positive': self.n_positive,
            'n_negative': self.n_negative,
            'n_kb': self.n_kb,
            'congen_runtime_ms': self.congen_runtime_ms,
            'comparison': {}
        }
        if self.description_comparison:
            result['comparison']['description'] = self.description_comparison.to_dict()
        if self.clause_comparison:
            result['comparison']['clause'] = self.clause_comparison.to_dict()
        if self.semantic_result:
            result['comparison']['semantic'] = self.semantic_result.to_dict()
        return result


@dataclass
class ProgressiveResult:
    """Complete progressive evaluation result.

    Attributes:
        checkpoints: List of CheckpointResult (ConGen at each N%)
        quacq_description: ComparationResult for QuAcq final KB
        quacq_clause: ComparationResult for QuAcq final KB
        quacq_semantic: SemanticResult for QuAcq final KB
        total_queries: Total queries QuAcq asked
        metadata: Additional info (FM name, timestamps, etc.)
    """
    checkpoints: List[CheckpointResult] = field(default_factory=list)
    quacq_description: Optional[ComparationResult] = None
    quacq_clause: Optional[ComparationResult] = None
    quacq_semantic: Optional[SemanticResult] = None
    total_queries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            'total_queries': self.total_queries,
            'metadata': self.metadata,
            'progressive': [cp.to_dict() for cp in self.checkpoints],
            'quacq': {'comparison': {}}
        }
        if self.quacq_description:
            result['quacq']['comparison']['description'] = self.quacq_description.to_dict()
        if self.quacq_clause:
            result['quacq']['comparison']['clause'] = self.quacq_clause.to_dict()
        if self.quacq_semantic:
            result['quacq']['comparison']['semantic'] = self.quacq_semantic.to_dict()
        return result


class ProgressiveEvaluator:
    """Run ConGen at progressive query budgets and compare vs ground truth."""

    def __init__(
        self,
        congen_runner: ConGenRunner,
        comparator: KBComparator,
        groundtruth: GroundTruthData,
        checkpoints_pct: List[int] = None,
    ):
        self.congen_runner = congen_runner
        self.comparator = comparator
        self.groundtruth = groundtruth
        self.checkpoints_pct = checkpoints_pct or [10, 25, 50, 75, 100]

    def evaluate(
        self,
        query_history: List[Tuple[Dict[str, bool], bool, str]],
        quacq_run_result: QuAcqRunResult
    ) -> ProgressiveResult:
        """Run progressive evaluation pipeline.

        Args:
            query_history: Full query history with source tags
            quacq_run_result: QuAcq final result (for KB comparison)

        Returns:
            ProgressiveResult with all checkpoint + QuAcq comparisons
        """
        # Filter to main-loop queries only
        main_queries = [(c, a, s) for c, a, s in query_history if s == 'main']
        total = len(main_queries)

        logging.info('Progressive evaluation: %d main queries, checkpoints=%s',
                     total, self.checkpoints_pct)

        result = ProgressiveResult(total_queries=total)
        checkpoints = []

        for pct in self.checkpoints_pct:
            n = max(1, int(pct / 100 * total)) if total > 0 else 0
            if n == 0:
                continue

            sliced = main_queries[:n]
            pos, neg = queries_to_assignment_lists(sliced, source_filter='main')

            logging.info('Checkpoint %d%%: %d queries (%d+, %d-)',
                         pct, n, len(pos), len(neg))

            start = time.perf_counter()
            congen_result = self.congen_runner.run(pos, neg)
            runtime_ms = (time.perf_counter() - start) * 1000

            # Build ConGenResultData for comparator
            result_data = ConGenResultData(
                kb_constraints=congen_result.kb_constraints,
                n_bias=congen_result.n_bias,
                n_kb=congen_result.n_kb,
                bg_clauses=congen_result.bg_clauses,
            )

            # Run comparisons
            desc_cmp = self.comparator.compare(result_data, ComparationStrategy.DESCRIPTION)
            clause_cmp = self.comparator.compare(result_data, ComparationStrategy.CLAUSE)
            # Delivered theory includes the memorized ¬e⁻ (Algorithm 3: KB <- B' u NE).
            sem_result = self._run_semantic_check(
                list(congen_result.kb_clauses)
                + [list(c) for c in getattr(congen_result, 'ne_clauses', ()) or ()],
                congen_result.bg_clauses)

            cp = CheckpointResult(
                checkpoint_pct=pct,
                n_queries=n,
                n_positive=len(pos),
                n_negative=len(neg),
                n_kb=congen_result.n_kb,
                description_comparison=desc_cmp,
                clause_comparison=clause_cmp,
                semantic_result=sem_result,
                congen_runtime_ms=runtime_ms
            )
            checkpoints.append(cp)

        result.checkpoints = checkpoints

        # Compare QuAcq final KB
        quacq_data = ConGenResultData(
            kb_constraints=quacq_run_result.kb_constraints,
            n_bias=quacq_run_result.n_bias,
            n_kb=quacq_run_result.n_kb,
            bg_clauses=quacq_run_result.bg_clauses,
        )
        result.quacq_description = self.comparator.compare(
            quacq_data, ComparationStrategy.DESCRIPTION)
        result.quacq_clause = self.comparator.compare(
            quacq_data, ComparationStrategy.CLAUSE)
        result.quacq_semantic = self._run_semantic_check(
            quacq_run_result.kb_clauses, quacq_run_result.bg_clauses)

        logging.info('Progressive evaluation complete: %d checkpoints', len(checkpoints))
        return result

    def _run_semantic_check(
        self,
        kb_clauses: List[List[int]],
        bg_clauses: List[List[int]]
    ) -> SemanticResult:
        """Run semantic equivalence check against ground truth."""
        checker = SemanticEquivalenceChecker(
            kb_clauses=kb_clauses,
            ct_clauses=self.groundtruth.clauses,
            bg_clauses=bg_clauses
        )
        return checker.check_equivalence()

"""
Main comparator for ConGen results.

Supports two comparation strategies:
1. Description-based (recommended): Compare constraint descriptions
2. Clause-based: Compare CNF clauses (semantic)
"""

from dataclasses import dataclass
from typing import List, Set, Tuple
from pathlib import Path
from enum import Enum
import logging

from conacq.oracle.ground_truth import GroundTruthData
from conacq.bias import Bias, BiasIO
from .result_loader import ConGenResultData
from .metrics import EvaluationMetrics, compute_metrics


class ComparationStrategy(Enum):
    """Comparation strategy."""
    DESCRIPTION = "description"  # Compare constraint descriptions (recommended)
    CLAUSE = "clause"            # Compare CNF clauses (structural)
    SEMANTIC = "semantic"        # SAT-based semantic equivalence


@dataclass
class ComparationResult:
    """
    Complete comparation result.

    Attributes:
        strategy: Which strategy was used
        metrics: EvaluationMetrics (TP, TN, FP, FN)
        kb_constraints: List of KB constraint IDs
        matched_constraints: TP constraint IDs/descriptions
        missed_constraints: FN - in ground truth but not KB
        extra_constraints: FP - in KB but not ground truth
        kb_reduction_ratio: 1 - (n_kb / n_bias)
    """
    strategy: str
    metrics: EvaluationMetrics
    kb_constraints: List[str]
    matched_constraints: List[str]
    missed_constraints: List[str]
    extra_constraints: List[str]
    kb_reduction_ratio: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'strategy': self.strategy,
            'metrics': self.metrics.to_dict(),
            'kb_constraints': self.kb_constraints,
            'matched_constraints': self.matched_constraints,
            'missed_constraints': self.missed_constraints,
            'extra_constraints': self.extra_constraints,
            'kb_reduction_ratio': self.kb_reduction_ratio,
        }

    def to_enriched_dict(self, bias) -> dict:
        """Produce evaluation dict with id+description for TP/FP/FN.

        Args:
            bias: Bias instance for resolving constraint descriptions
        """
        def _enrich_ids(ids):
            return [{"id": cid,
                     "description": bias.get_description(cid) if bias.has_constraint(cid) else cid}
                    for cid in ids]

        # For description strategy, missed_constraints are descriptions (no IDs)
        if self.strategy == ComparationStrategy.DESCRIPTION.value:
            fn = [{"id": None, "description": d} for d in self.missed_constraints]
        else:
            fn = [{"id": None, "description": str(c)} for c in self.missed_constraints]

        return {
            'metrics': self.metrics.to_dict(),
            'tp': _enrich_ids(self.matched_constraints),
            'fp': _enrich_ids(self.extra_constraints),
            'fn': fn,
        }


class KBComparator:
    """
    Compare ConGen results against ground-truth FM.

    Supports two strategies:
    1. Description-based (recommended): Compare constraint descriptions
    2. Clause-based: Compare CNF clauses (semantic)
    """

    def __init__(self, ground_truth: GroundTruthData, bias: Bias):
        """
        Initialize comparator with ground-truth and bias data.

        Args:
            ground_truth: GroundTruthData extracted from feature model
            bias: Bias loaded from bias JSON
        """
        self.ground_truth = ground_truth
        self.bias = bias
        logging.debug('KBComparator initialized: ground_truth=%d descriptions, bias=%d constraints',
                      len(ground_truth.descriptions), len(bias))

    def compare(
            self,
            result: ConGenResultData,
            strategy: ComparationStrategy = ComparationStrategy.DESCRIPTION
    ) -> ComparationResult:
        """
        Compare ConGen result against ground truth.

        Args:
            result: ConGenResultData with kb_constraints
            strategy: DESCRIPTION (recommended) or CLAUSE

        Returns:
            ComparationResult with metrics and details
        """
        logging.debug('>>> KBComparator.evaluate(kb=%d, strategy=%s)',
                      len(result.kb_constraints), strategy.value)

        if strategy == ComparationStrategy.DESCRIPTION:
            return self._compare_by_description(result)
        elif strategy == ComparationStrategy.CLAUSE:
            return self._compare_by_clause(result)
        elif strategy == ComparationStrategy.SEMANTIC:
            return self._compare_by_semantic(result)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _compare_by_description(self, result: ConGenResultData) -> ComparationResult:
        """
        Compare using description-based strategy.

        1. Get FM descriptions from ground truth
        2. Get KB descriptions from bias
        3. Compare string sets
        """
        # Get ground-truth descriptions
        fm_descriptions = self.ground_truth.descriptions

        # Get acquired KB descriptions
        acquired_descriptions: Set[str] = set()
        kb_to_description: dict = {}
        for cid in result.kb_constraints:
            if self.bias.has_constraint(cid):
                desc = self.bias.get_description(cid)
                acquired_descriptions.add(desc)
                kb_to_description[cid] = desc

        # Compute metrics
        tp = acquired_descriptions & fm_descriptions
        fp = acquired_descriptions - fm_descriptions
        fn = fm_descriptions - acquired_descriptions

        metrics = EvaluationMetrics(
            true_positives=len(tp),
            false_positives=len(fp),
            false_negatives=len(fn),
            true_negatives=0  # Not applicable for description-based
        )

        # Find constraint IDs for matched/extra
        matched = [cid for cid, desc in kb_to_description.items() if desc in tp]
        extra = [cid for cid, desc in kb_to_description.items() if desc in fp]
        missed = list(fn)  # Just descriptions (no IDs in FM)

        # KB reduction ratio
        reduction = 1 - (result.n_kb / result.n_bias) if result.n_bias > 0 else 0

        com_result = ComparationResult(
            strategy=ComparationStrategy.DESCRIPTION.value,
            metrics=metrics,
            kb_constraints=result.kb_constraints,
            matched_constraints=matched,
            missed_constraints=missed,
            extra_constraints=extra,
            kb_reduction_ratio=reduction
        )

        logging.debug('<<< Description: P=%.3f, R=%.3f, F1=%.3f',
                      metrics.precision, metrics.recall, metrics.f1_score)

        return com_result

    def _compare_by_clause(self, result: ConGenResultData) -> ComparationResult:
        """
        Compare using clause-based strategy.

        1. Convert KB constraints to CNF clauses (sorted for normalization)
        2. Compare with ground-truth clause set
        """
        # Convert KB constraint IDs to clause sets (normalized with sorted)
        kb_clauses: Set[Tuple[int, ...]] = set()
        kb_to_clauses: dict = {}
        for cid in result.kb_constraints:
            if self.bias.has_constraint(cid):
                constraint_clauses = []
                for clause in self.bias.get_clauses(cid):
                    normalized = tuple(sorted(clause))
                    kb_clauses.add(normalized)
                    constraint_clauses.append(normalized)
                kb_to_clauses[cid] = constraint_clauses

        # Union background clauses (KB ∪ BG)
        if result.bg_clauses:
            for clause in result.bg_clauses:
                normalized = tuple(sorted(clause))
                kb_clauses.add(normalized)

        # Get bias clause set
        bias_clauses = self.bias.get_all_clause_tuples()

        # Compute metrics
        metrics = compute_metrics(kb_clauses, self.ground_truth.clause_set, bias_clauses)

        # Find matched/missed/extra constraints
        matched = self._find_matched_constraints(kb_clauses, kb_to_clauses)
        missed = self._find_missed_clauses_descriptions(kb_clauses)
        extra = self._find_extra_constraints(result.kb_constraints, kb_clauses, kb_to_clauses)

        # KB reduction ratio
        reduction = 1 - (result.n_kb / result.n_bias) if result.n_bias > 0 else 0

        com_result = ComparationResult(
            strategy=ComparationStrategy.CLAUSE.value,
            metrics=metrics,
            kb_constraints=result.kb_constraints,
            matched_constraints=matched,
            missed_constraints=missed,
            extra_constraints=extra,
            kb_reduction_ratio=reduction
        )

        logging.debug('<<< Clause: P=%.3f, R=%.3f, F1=%.3f',
                      metrics.precision, metrics.recall, metrics.f1_score)

        return com_result

    def _find_matched_constraints(
            self,
            kb_clauses: Set[Tuple[int, ...]],
            kb_to_clauses: dict
    ) -> List[str]:
        """Find constraint IDs that match ground truth (clause-based)."""
        matched = []
        for cid, clauses in kb_to_clauses.items():
            for clause in clauses:
                if clause in self.ground_truth.clause_set:
                    matched.append(cid)
                    break
        return matched

    def _find_missed_clauses_descriptions(
            self,
            kb_clauses: Set[Tuple[int, ...]]
    ) -> List[str]:
        """Find ground-truth clauses not in KB as string descriptions."""
        missed_clauses = self.ground_truth.clause_set - kb_clauses
        return [str(list(c)) for c in list(missed_clauses)[:20]]  # Limit to 20

    def _find_extra_constraints(
            self,
            kb_ids: List[str],
            kb_clauses: Set[Tuple[int, ...]],
            kb_to_clauses: dict
    ) -> List[str]:
        """Find KB constraints not in ground truth (clause-based)."""
        extra = []
        for cid in kb_ids:
            if cid in kb_to_clauses:
                clauses = kb_to_clauses[cid]
                if not any(c in self.ground_truth.clause_set for c in clauses):
                    extra.append(cid)
        return extra

    def _compare_by_semantic(self, result: ConGenResultData) -> ComparationResult:
        """Compare using SAT-based semantic equivalence.

        Uses SemanticEquivalenceChecker for bidirectional entailment.
        Maps semantic results to ComparationResult metrics.
        """
        from .semantic_equivalence import SemanticEquivalenceChecker

        # Bias-only, and deliberately so. The tiers ask "did we recover the right
        # constraints from the bias vocabulary", so a memorized ¬e⁻ (no bias id) and the
        # root axiom are excluded — they were given, not learned. Exact equivalence asks
        # a different question, "does the delivered theory behave correctly", and so
        # INCLUDES both (see run_compare.exact_equivalence). The two disagreeing is the
        # design, not a defect: making them agree would collapse a two-object contract
        # into one and destroy whichever question it was made to match.
        kb_clause_lists = []
        for cid in result.kb_constraints:
            if self.bias.has_constraint(cid):
                for clause in self.bias.get_clauses(cid):
                    kb_clause_lists.append(list(clause))

        ct_clause_lists = [list(c) for c in self.ground_truth.clauses]
        bg_clauses = result.bg_clauses or []

        checker = SemanticEquivalenceChecker(
            kb_clauses=kb_clause_lists,
            ct_clauses=ct_clause_lists,
            bg_clauses=bg_clauses,
        )
        sem_result = checker.check_equivalence()

        # Map to EvaluationMetrics: entailed ct = recall proxy, entailed kb = precision proxy
        n_ct_entailed = sem_result.n_ct_checked - len(sem_result.unentailed_ct)
        n_kb_entailed = sem_result.n_kb_checked - len(sem_result.unentailed_kb)

        metrics = EvaluationMetrics(
            true_positives=n_ct_entailed,
            false_negatives=len(sem_result.unentailed_ct),
            false_positives=len(sem_result.unentailed_kb),
            true_negatives=0
        )

        reduction = 1 - (result.n_kb / result.n_bias) if result.n_bias > 0 else 0

        return ComparationResult(
            strategy=ComparationStrategy.SEMANTIC.value,
            metrics=metrics,
            kb_constraints=result.kb_constraints,
            matched_constraints=[],
            missed_constraints=[str(list(c)) for c in sem_result.unentailed_ct[:20]],
            extra_constraints=[str(list(c)) for c in sem_result.unentailed_kb[:20]],
            kb_reduction_ratio=reduction
        )

    @classmethod
    def from_files(cls, ground_truth_path: Path, bias_path: Path) -> 'KBComparator':
        """
        Create KBComparator from file paths.

        Args:
            ground_truth_path: Path to feature model (.uvl)
            bias_path: Path to bias JSON file

        Returns:
            KBComparator instance
        """
        ground_truth = GroundTruthData.from_uvl(Path(ground_truth_path))
        bias = BiasIO.load_from_json(str(bias_path))
        return cls(ground_truth, bias)

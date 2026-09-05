"""
Accuracy calculator for evaluating KB against test examples.

According to Formula 1 in the paper (page 6):
- TP: positive example ACCEPTED by KB
- TN: negative example REJECTED by KB
- FP: negative example ACCEPTED by KB (error)
- FN: positive example REJECTED by KB (error)

accuracy(KB) = (TP + TN) / (TP + TN + FP + FN)
"""

from typing import List, Dict
from dataclasses import dataclass
import logging

from pysat.solvers import Solver

from .metrics import EvaluationMetrics


@dataclass
class AccuracyResult:
    """
    Result of accuracy calculation.

    Attributes:
        metrics: EvaluationMetrics with TP, TN, FP, FN
        tp_examples: IDs of correctly accepted positive examples
        tn_examples: IDs of correctly rejected negative examples
        fp_examples: IDs of incorrectly accepted negative examples
        fn_examples: IDs of incorrectly rejected positive examples
    """
    metrics: EvaluationMetrics
    tp_examples: List[str]
    tn_examples: List[str]
    fp_examples: List[str]
    fn_examples: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'metrics': self.metrics.to_dict(),
            'tp_examples': self.tp_examples,
            'tn_examples': self.tn_examples,
            'fp_examples': self.fp_examples,
            'fn_examples': self.fn_examples,
        }


class AccuracyCalculator:
    """
    Calculate accuracy of KB against test examples.

    According to Formula 1 in the paper (page 6):
    - TP: positive example ACCEPTED by KB
    - TN: negative example REJECTED by KB
    - FP: negative example ACCEPTED by KB
    - FN: positive example REJECTED by KB
    """

    def __init__(self, kb_clauses: List[List[int]], variables: Dict[str, int],
                 solver_name: str = 'glucose4'):
        """
        Initialize with KB clauses and variable mapping.

        Args:
            kb_clauses: CNF clauses of the learned KB
            variables: Mapping {feature_name: SAT_variable_id}
            solver_name: SAT solver name
        """
        self.variables = variables
        self.solver = Solver(name=solver_name)
        for clause in kb_clauses:
            self.solver.add_clause(clause)
        self._kb_clauses = kb_clauses

    def calculate(
            self,
            positive_examples: List[Dict[str, bool]],
            negative_examples: List[Dict[str, bool]]
    ) -> AccuracyResult:
        """
        Calculate accuracy metrics.

        Args:
            positive_examples: List of E+ (should be ACCEPTED by KB)
            negative_examples: List of E- (should be REJECTED by KB)

        Returns:
            AccuracyResult with metrics and example lists
        """
        logging.debug('>>> AccuracyCalculator.calculate(E+=%d, E-=%d)',
                      len(positive_examples), len(negative_examples))

        tp_examples, fn_examples = [], []
        tn_examples, fp_examples = [], []

        # Test positive examples (should be accepted by correct KB)
        for i, example in enumerate(positive_examples):
            example_id = f"e{i+1}+"
            accepted = self._is_accepted(example)
            if accepted:
                tp_examples.append(example_id)
            else:
                fn_examples.append(example_id)

        # Test negative examples (should be rejected by correct KB)
        for i, example in enumerate(negative_examples):
            example_id = f"e{i+1}-"
            accepted = self._is_accepted(example)
            if accepted:
                fp_examples.append(example_id)  # Error: negative accepted
            else:
                tn_examples.append(example_id)

        metrics = EvaluationMetrics(
            true_positives=len(tp_examples),
            true_negatives=len(tn_examples),
            false_positives=len(fp_examples),
            false_negatives=len(fn_examples)
        )

        logging.debug('<<< AccuracyCalculator: acc=%.4f, TP=%d, TN=%d, FP=%d, FN=%d',
                      metrics.accuracy, len(tp_examples), len(tn_examples),
                      len(fp_examples), len(fn_examples))

        return AccuracyResult(
            metrics=metrics,
            tp_examples=tp_examples,
            tn_examples=tn_examples,
            fp_examples=fp_examples,
            fn_examples=fn_examples
        )

    def _is_accepted(self, example: Dict[str, bool]) -> bool:
        """
        Check if example is accepted (consistent) with KB.

        Args:
            example: Feature assignments {feature_name: True/False}

        Returns:
            True if example is consistent with KB
        """
        assumptions = []
        for name, value in example.items():
            if name in self.variables:
                fid = self.variables[name]
                assumptions.append(fid if value else -fid)
        return self.solver.solve(assumptions=assumptions)

    def cleanup(self):
        """Clean up SAT solver."""
        if self.solver:
            self.solver.delete()
            self.solver = None

    def __del__(self):
        """Destructor to clean up solver."""
        self.cleanup()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False

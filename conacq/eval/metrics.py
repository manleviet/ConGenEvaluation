"""
Evaluation metrics for ConGen.

According to Formula 1 in the paper (page 6), the primary metric is Accuracy:
    accuracy(KB) = (TP + TN) / (TP + TN + FP + FN)

Where:
- TP: True Positive - positive example ACCEPTED by KB
- TN: True Negative - negative example REJECTED by KB
- FP: False Positive - negative example ACCEPTED by KB (error)
- FN: False Negative - positive example REJECTED by KB (error)
"""

from dataclasses import dataclass
from typing import Set, Tuple


@dataclass
class EvaluationMetrics:
    """
    Evaluation metrics based on Formula 1 from the paper.

    Attributes:
        true_positives: E+ examples correctly accepted by KB
        true_negatives: E- examples correctly rejected by KB
        false_positives: E- examples incorrectly accepted by KB
        false_negatives: E+ examples incorrectly rejected by KB
    """
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int

    @property
    def accuracy(self) -> float:
        """
        Accuracy = (TP + TN) / (TP + TN + FP + FN)

        Formula 1 from the paper - PRIMARY METRIC.
        """
        total = (self.true_positives + self.true_negatives +
                 self.false_positives + self.false_negatives)
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total

    @property
    def precision(self) -> float:
        """
        Precision = TP / (TP + FP)

        Proportion of accepted examples that are correct.
        """
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def recall(self) -> float:
        """
        Recall = TP / (TP + FN)

        Proportion of positive examples correctly identified.
        """
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def f1_score(self) -> float:
        """
        F1 = 2 * P * R / (P + R)

        Harmonic mean of precision and recall.
        """
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def specificity(self) -> float:
        """
        Specificity = TN / (TN + FP)

        Proportion of negative examples correctly identified.
        """
        denominator = self.true_negatives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_negatives / denominator

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'specificity': self.specificity,
            'true_positives': self.true_positives,
            'true_negatives': self.true_negatives,
            'false_positives': self.false_positives,
            'false_negatives': self.false_negatives,
        }


def compute_metrics(
        kb_set: Set[Tuple[int, ...]],
        oracle_set: Set[Tuple[int, ...]],
        bias_set: Set[Tuple[int, ...]] = None
) -> EvaluationMetrics:
    """
    Compute metrics by comparing KB clauses with Oracle clauses.

    This is for clause-based evaluation (Strategy 2).

    Args:
        kb_set: Set of KB clauses (normalized as sorted tuples)
        oracle_set: Set of Oracle clauses (normalized as sorted tuples)
        bias_set: Optional set of all bias clauses (for TN calculation)

    Returns:
        EvaluationMetrics
    """
    # True positives: clauses in both KB and Oracle
    tp = len(kb_set & oracle_set)

    # False positives: clauses in KB but not in Oracle
    fp = len(kb_set - oracle_set)

    # False negatives: clauses in Oracle but not in KB
    fn = len(oracle_set - kb_set)

    # True negatives: clauses in bias not in KB and not in Oracle
    # (correctly not selected)
    tn = 0
    if bias_set:
        not_selected = bias_set - kb_set
        tn = len(not_selected - oracle_set)

    return EvaluationMetrics(
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn
    )

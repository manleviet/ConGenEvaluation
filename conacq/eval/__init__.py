"""
Evaluation module for ConGen constraint acquisition.

This module provides tools to evaluate the quality of learned KBs by comparing
with the Oracle (original Feature Model) and calculating accuracy metrics.

Main components:
- KBComparator: Main class for evaluating ConGen results
- AccuracyCalculator: Calculate accuracy of KB against test examples
- n_fold_cross_validation: Cross-validation for generalizability assessment
- ConGenRunner: Run ConGen with performance metrics collection

Evaluation strategies:
1. Description-based (recommended): Compare constraint descriptions
2. Clause-based: Compare CNF clauses (semantic)

Metrics (Formula 1 from paper):
- Accuracy = (TP + TN) / (TP + TN + FP + FN) - PRIMARY METRIC
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 * P * R / (P + R)

Example usage:
    >>> from conacq.eval import KBComparator, ComparationStrategy
    >>> evaluator = KBComparator.from_files('model.uvl', 'bias.json')
    >>> result = evaluator.compare(congen_result, ComparationStrategy.DESCRIPTION)
    >>> print(f"Accuracy: {result.metrics.accuracy:.4f}")
"""

# Metrics
from .metrics import EvaluationMetrics, compute_metrics

# Data loaders
from conacq.bias import Bias, BiasIO
from .result_loader import ConGenResultData
from conacq.oracle.ground_truth import GroundTruthData

# Accuracy calculation
from .accuracy import AccuracyCalculator, AccuracyResult

# Performance metrics moved to conacq/runners/metrics.py (ADR-0006): a runner's
# output, not the evaluation of a run. Import from conacq.runners.metrics.

# Runners (re-exported from conacq.runners for backward compat)
from conacq.runners import BaseRunner, BaseRunResult
from conacq.runners import ConGenRunner, ConGenRunResult
from conacq.runners import QuAcqRunner, QuAcqRunResult

# Cross-validation
from .cross_validation import (
    n_fold_cross_validation,
    n_fold_cross_validation_interactive,
    CrossValidationResult,
    CrossValidationFoldResult
)

# Fold I/O
from .folds import FoldData, generate_folds, save_folds, load_folds, apply_folds

# Semantic equivalence
from .semantic_equivalence import SemanticEquivalenceChecker, SemanticResult

# Progressive evaluation
from .progressive_evaluation import ProgressiveEvaluator, ProgressiveResult, CheckpointResult

# Main evaluator
from .kb_comparator import KBComparator, ComparationStrategy, ComparationResult

# Pipeline config moved to conacq/config.py (ADR-0006): application configuration,
# not evaluation. Import from conacq.config.

# Report generation
from .report import (
    generate_evaluation_report,
    generate_accuracy_report,
    generate_cv_report,
    generate_unified_cv_dict,
    save_kb_result,
)

__all__ = [
    # Metrics
    'EvaluationMetrics',
    'compute_metrics',

    # Data loaders (Bias/BiasIO re-exported from conacq.bias)
    'Bias',
    'BiasIO',
    'ConGenResultData',
    'GroundTruthData',

    # Accuracy
    'AccuracyCalculator',
    'AccuracyResult',

    # Performance

    # Base runner
    'BaseRunner',
    'BaseRunResult',

    # ConGen runner
    'ConGenRunner',
    'ConGenRunResult',

    # QuAcq runner
    'QuAcqRunner', 'QuAcqRunResult',

    # Cross-validation
    'n_fold_cross_validation',
    'n_fold_cross_validation_interactive',
    'CrossValidationResult',
    'CrossValidationFoldResult',

    # Semantic equivalence
    'SemanticEquivalenceChecker',
    'SemanticResult',

    # Progressive evaluation
    'ProgressiveEvaluator',
    'ProgressiveResult',
    'CheckpointResult',

    # KBComparator
    'KBComparator',
    'ComparationStrategy',
    'ComparationResult',

    # Fold I/O
    'FoldData',
    'generate_folds',
    'save_folds',
    'load_folds',
    'apply_folds',


    # Reports
    'generate_evaluation_report',
    'generate_accuracy_report',
    'generate_cv_report',
    'generate_unified_cv_dict',
    'save_kb_result',
]

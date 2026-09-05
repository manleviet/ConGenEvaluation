"""
Report generation for ConGen evaluation.

Generates formatted reports and saves results to JSON.
Includes unified CV output dict builder for single-file export.
"""

from pathlib import Path
from typing import List, Optional
import json

from conacq.bias import Bias
from conacq.atomic_io import write_json_atomic
from .kb_comparator import ComparationResult
from .accuracy import AccuracyResult
from .cross_validation import CrossValidationResult


def generate_evaluation_report(
        result: ComparationResult,
        output_path: Optional[Path] = None
) -> str:
    """
    Generate evaluation report.

    Args:
        result: EvaluationResult from KBComparator
        output_path: Optional path to save JSON report

    Returns:
        Formatted report string
    """
    m = result.metrics
    report = f"""
=== ConGen Evaluation Report ===
Strategy: {result.strategy}

Metrics:
  Accuracy:    {m.accuracy:.4f}
  Precision:   {m.precision:.4f}
  Recall:      {m.recall:.4f}
  F1 Score:    {m.f1_score:.4f}

Counts:
  True Positives:  {m.true_positives}
  True Negatives:  {m.true_negatives}
  False Positives: {m.false_positives}
  False Negatives: {m.false_negatives}

KB Statistics:
  KB Size:           {len(result.kb_constraints)}
  Matched:           {len(result.matched_constraints)}
  Missed:            {len(result.missed_constraints)}
  Extra:             {len(result.extra_constraints)}
  Reduction Ratio:   {result.kb_reduction_ratio:.4f}

Matched Constraints: {_format_list(result.matched_constraints, 10)}
Missed Constraints:  {_format_list(result.missed_constraints, 10)}
Extra Constraints:   {_format_list(result.extra_constraints, 10)}
"""

    if output_path:
        _save_json(result.to_dict(), output_path)

    return report


def generate_accuracy_report(
        result: AccuracyResult,
        output_path: Optional[Path] = None
) -> str:
    """
    Generate accuracy report.

    Args:
        result: AccuracyResult from AccuracyCalculator
        output_path: Optional path to save JSON report

    Returns:
        Formatted report string
    """
    m = result.metrics
    report = f"""
=== KB Accuracy Report ===

Metrics (Formula 1 from paper):
  Accuracy:    {m.accuracy:.4f}
  Precision:   {m.precision:.4f}
  Recall:      {m.recall:.4f}
  F1 Score:    {m.f1_score:.4f}

Counts:
  TP (E+ accepted):  {m.true_positives}
  TN (E- rejected):  {m.true_negatives}
  FP (E- accepted):  {m.false_positives} (errors)
  FN (E+ rejected):  {m.false_negatives} (errors)

Examples:
  TP Examples: {_format_list(result.tp_examples, 10)}
  TN Examples: {_format_list(result.tn_examples, 10)}
  FP Examples: {_format_list(result.fp_examples, 10)}
  FN Examples: {_format_list(result.fn_examples, 10)}
"""

    if output_path:
        _save_json(result.to_dict(), output_path)

    return report


def generate_cv_report(
        result: CrossValidationResult,
        output_path: Optional[Path] = None
) -> str:
    """
    Generate cross-validation report.

    Standard CV report shows mean accuracy ± std across folds.

    Args:
        result: CrossValidationResult from n_fold_cross_validation
        output_path: Optional path to save JSON report

    Returns:
        Formatted report string
    """
    # ``performance`` is the aggregate() dict {group: {stat: value}} (post-T9 metrics
    # refactor) — NOT an attribute object. Read defensively: QuAcq has no kb_size
    # group, and per-algorithm tables differ.
    p = result.performance
    rt = p.get('runtime', {})
    cc = p.get('consistency_checks', {})
    kb = p.get('kb_size', {})
    mem = p.get('memory', {})

    # Format per-fold results
    fold_details = []
    for fr in result.fold_results:
        fold_details.append(
            f"  Fold {fr.fold_index + 1}: accuracy={fr.accuracy:.4f}, "
            f"KB={fr.n_kb}, TP={fr.metrics.true_positives}, TN={fr.metrics.true_negatives}, "
            f"FP={fr.metrics.false_positives}, FN={fr.metrics.false_negatives}"
        )

    report = f"""
=== Cross-Validation Report ===

Folds: {result.n_folds}

Accuracy (Formula 1 from paper):
  Mean:  {result.mean_accuracy:.4f}
  Std:   {result.std_accuracy:.4f}
  Per Fold: {', '.join(f'{a:.4f}' for a in result.fold_accuracies)}

Fold Details:
{chr(10).join(fold_details)}

Intersected KB: {len(result.intersected_kb)} constraints

Performance:
  Total CV Runtime: {result.total_runtime_ms:.2f} ms

  Runtime (per fold):
    Mean:  {rt.get('mean_ms', 0.0):.2f} ms
    Std:   {rt.get('std_ms', 0.0):.2f} ms
    Range: [{rt.get('min_ms', 0.0):.2f}, {rt.get('max_ms', 0.0):.2f}] ms

  Consistency Checks:
    Mean:  {cc.get('mean', 0.0):.1f}
    Range: [{cc.get('min', 0)}, {cc.get('max', 0)}]

  KB Size:
    Mean:  {kb.get('n_kb_mean', 0.0):.1f}

  Memory:
    Max:   {mem.get('max_mb', 0.0):.2f} MB
"""

    if output_path:
        _save_json(result.to_dict(), output_path)

    return report


def save_kb_result(
        kb_constraints: list,
        redundant_constraints: list,
        n_bias: int,
        n_mss: int,
        n_kb: int,
        output_path: Path,
        bg_clauses: Optional[list] = None,
        metadata: Optional[dict] = None,
        ne_constraints: Optional[list] = None,
        n_ne: int = 0
) -> None:
    """
    Save KB result to JSON file.

    This saves the generated knowledge base from ConGen in the same format
    as the original run_congen.py output.

    Args:
        kb_constraints: List of constraint IDs in the learned KB
        redundant_constraints: List of redundant constraint IDs
        n_bias: Original number of bias constraints
        n_mss: Size of MSS before REDUCE
        n_kb: Final KB size — bias constraints ONLY; the memorized ¬e⁻ facts are
            counted in ``n_ne``, |KB| = n_kb + n_ne
        output_path: Path to save JSON file
        bg_clauses: Background knowledge clauses (e.g., [[1]] for root)
        metadata: Optional metadata dict
    """
    data = {
        'kb_constraints': kb_constraints,
        'redundant_constraints': redundant_constraints,
        'bg_clauses': bg_clauses or [],
        'ne_constraints': ne_constraints or [],
        'statistics': {
            'n_bias': n_bias,
            'n_mss': n_mss,
            'n_kb': n_kb,
            'n_ne': n_ne
        }
    }
    if metadata:
        data['metadata'] = metadata

    _save_json(data, output_path)


def _enrich_constraints(constraint_ids: List[str], bias: Bias) -> List[dict]:
    """Convert constraint ID list to [{id, description}]."""
    result = []
    for cid in constraint_ids:
        desc = bias.get_description(cid) if bias.has_constraint(cid) else cid
        result.append({"id": cid, "description": desc})
    return result


def generate_unified_cv_dict(
        cv_result: CrossValidationResult,
        bias: Bias
) -> dict:
    """Build unified CV output dict with descriptions and eval placeholders.

    Args:
        cv_result: CrossValidationResult from CV loop
        bias: Bias for resolving constraint descriptions

    Returns:
        Dict ready for JSON serialization as unified CV output
    """
    folds = []
    for fr in cv_result.fold_results:
        fold_dict = fr.to_dict()
        fold_dict['kb_constraints'] = _enrich_constraints(fr.kb_constraints, bias)
        fold_dict['evaluation'] = None
        folds.append(fold_dict)

    return {
        'n_folds': cv_result.n_folds,
        'fold_accuracies': cv_result.fold_accuracies,
        'mean_accuracy': cv_result.mean_accuracy,
        'std_accuracy': cv_result.std_accuracy,
        'total_runtime_ms': cv_result.total_runtime_ms,
        'intersected_kb': {
            'kb_constraints': _enrich_constraints(cv_result.intersected_kb, bias),
            'bg_clauses': cv_result.bg_clauses,
            'n_kb': len(cv_result.intersected_kb),
            'evaluation': None,
        },
        'folds': folds,
        # performance is already the aggregate() dict {group: {stat: value}} — emit
        # it directly (it has no .to_dict(); it IS the dict).
        'performance': cv_result.performance,
        'summary': None,
    }


def _format_list(items: list, max_items: int = 10) -> str:
    """Format list for display, truncating if necessary."""
    if not items:
        return "(none)"
    if len(items) <= max_items:
        return ', '.join(str(i) for i in items)
    return ', '.join(str(i) for i in items[:max_items]) + f'... (+{len(items) - max_items} more)'


def _save_json(data: dict, path: Path) -> None:
    """Save data to JSON file (atomically — a crash can't truncate a good file)."""
    write_json_atomic(path, data)

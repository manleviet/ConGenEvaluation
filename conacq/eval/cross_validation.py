"""
n-fold cross validation for constraint acquisition.

Standard cross-validation according to the paper (page 6):
1. Split examples into n folds
2. For each fold i: train KB on (n-1) folds, test accuracy on fold i
3. Report mean accuracy +/- std across all folds

Also saves:
- KB for each fold
- Intersected KB (constraints common to all folds)
"""

from typing import List, Dict, Optional, Any, Sequence, Callable, Mapping
from dataclasses import dataclass, field
import random
import logging
import time

from .metrics import EvaluationMetrics
from .accuracy import AccuracyCalculator
from .folds import FoldData, generate_folds, apply_folds
from conacq.runners.base_runner import BaseRunner, BaseRunResult
from conacq.runners.metrics import RunMetrics, aggregate


@dataclass
class CrossValidationFoldResult:
    """Result of a single fold."""
    fold_index: int
    accuracy: float
    metrics: EvaluationMetrics
    performance: RunMetrics
    # KB data
    kb_constraints: List[str]
    bg_clauses: List[List[int]]  # Background knowledge clauses (root constraint)
    redundant_constraints: List[str]
    n_bias: int
    n_kb: int
    # Train/test sizes
    n_train_pos: int
    n_train_neg: int
    n_test_pos: int
    n_test_neg: int
    # Optional fields (after all required for dataclass ordering)
    n_mss: Optional[int] = None
    # Memorized ¬e⁻ facts, counted apart from the bias constraints in n_kb
    # (|KB| = n_kb + n_ne). Optional: only ConGen resolves them today.
    ne_constraints: List[str] = field(default_factory=list)
    n_ne: int = 0
    # The ¬e⁻ blocking clauses and the ¬e⁻ Reduce discarded as entailed. Both are on
    # ConGenRunResult and neither used to reach here: ne_clauses were consumed to build
    # the theory for AccuracyCalculator and dropped, so the delivered theory could not
    # be reconstructed from any saved artefact (which is what backfill_ne_clauses.py
    # exists to work around), and without redundant_ne_constraints the |KB| accounting
    # — prepared = kept + discarded — cannot be closed from a CV file at all.
    ne_clauses: List[List[int]] = field(default_factory=list)
    redundant_ne_constraints: List[str] = field(default_factory=list)
    # Interactive-only budget accounting (Tables 13/14): how many queries the fold
    # consumed and why it stopped. ``None`` on the passive algorithms, which have
    # neither — and a None is omitted from to_dict() rather than serialized, so the
    # The passive algorithms' on-disk schema is unchanged by their presence here.
    n_queries: Optional[int] = None
    convergence_reason: Optional[str] = None
    # Full profiler snapshot (pass-through, not aggregated)
    profiler_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = {
            'fold_index': self.fold_index,
            'accuracy': self.accuracy,
            'metrics': self.metrics.to_dict(),
            'performance': {
                **self.performance.to_dict(),
                'profiler': self.profiler_data,
            },
            'kb_constraints': self.kb_constraints,
            'ne_constraints': self.ne_constraints,
            'ne_clauses': self.ne_clauses,
            'bg_clauses': self.bg_clauses,
            'redundant_constraints': self.redundant_constraints,
            'redundant_ne_constraints': self.redundant_ne_constraints,
            'statistics': {
                'n_bias': self.n_bias,
                'n_mss': self.n_mss,
                'n_kb': self.n_kb,
                'n_ne': self.n_ne,
            },
            'train_size': {'positive': self.n_train_pos, 'negative': self.n_train_neg},
            'test_size': {'positive': self.n_test_pos, 'negative': self.n_test_neg},
        }
        if self.n_queries is not None:
            d['n_queries'] = self.n_queries
        if self.convergence_reason is not None:
            d['convergence_reason'] = self.convergence_reason
        return d

    def to_kb_dict(self) -> dict:
        """Convert to KB file format."""
        return {
            'kb_constraints': self.kb_constraints,
            'ne_constraints': self.ne_constraints,
            'ne_clauses': self.ne_clauses,
            'bg_clauses': self.bg_clauses,
            'redundant_constraints': self.redundant_constraints,
            'redundant_ne_constraints': self.redundant_ne_constraints,
            'statistics': {
                'n_bias': self.n_bias,
                'n_mss': self.n_mss,
                'n_kb': self.n_kb,
                'n_ne': self.n_ne,
            },
            'fold': self.fold_index + 1,
            'accuracy': self.accuracy,
        }


@dataclass
class CrossValidationResult:
    """
    Result of n-fold cross validation.

    Standard CV: each fold trains on (n-1) folds and tests on 1 fold.
    Reports mean accuracy +/- std across all folds.

    Also includes:
    - KB for each fold (in fold_results)
    - Intersected KB (constraints common to all folds)
    - Total CV runtime (entire process)
    """
    n_folds: int
    fold_accuracies: List[float]
    mean_accuracy: float
    std_accuracy: float
    fold_results: List[CrossValidationFoldResult]
    performance: dict  # aggregate() output: {group: {stat: value}}
    # Intersected KB
    intersected_kb: List[str] = field(default_factory=list)
    # Background clauses (root constraint, same across all folds)
    bg_clauses: List[str] = field(default_factory=list)
    # Total CV runtime (ms)
    total_runtime_ms: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'n_folds': self.n_folds,
            'fold_accuracies': self.fold_accuracies,
            'mean_accuracy': self.mean_accuracy,
            'std_accuracy': self.std_accuracy,
            'intersected_kb': self.intersected_kb,
            'bg_clauses': self.bg_clauses,
            'n_intersected': len(self.intersected_kb),
            'total_runtime_ms': self.total_runtime_ms,
            'folds': [fr.to_dict() for fr in self.fold_results],
            'performance': self.performance,
        }


def _compute_fold(
        runner: BaseRunner,
        positive_examples: List[Dict[str, bool]],
        negative_examples: List[Dict[str, bool]],
        fold_data: FoldData,
        fold_idx: int,
        variables: Dict[str, int],
        solver_name: str,
        label: str,
        shuffle_each_fold: bool = True,
        shuffle_bias: bool = False,
) -> CrossValidationFoldResult:
    """Train on the other folds, score on fold ``fold_idx``.

    Reads nothing from any other fold: the split comes from ``fold_data`` and
    ``fold_idx``, and both RNG streams are seeded from
    ``fold_data.shuffle_seeds[fold_idx]``. That independence is what lets a fold
    be computed on its own and merged later — see ``conacq.eval.cv_partials``.
    """
    logging.info('=== %s Fold %d/%d ===', label, fold_idx + 1, fold_data.n_folds)

    train_pos, train_neg, test_pos, test_neg = apply_folds(
        fold_data, positive_examples, negative_examples, fold_idx
    )

    # Shuffle training examples with per-fold deterministic RNG
    if shuffle_each_fold:
        fold_rng = random.Random(fold_data.shuffle_seeds[fold_idx])
        fold_rng.shuffle(train_pos)
        fold_rng.shuffle(train_neg)

    logging.debug('Fold %d: train=(%d+, %d-), test=(%d+, %d-)',
                  fold_idx + 1, len(train_pos), len(train_neg),
                  len(test_pos), len(test_neg))

    # Determine bias shuffle seed for this fold
    fold_shuffle_seed = fold_data.shuffle_seeds[fold_idx] if shuffle_bias else None

    # Train: run acquisition on training set
    run_result = runner.run(train_pos, train_neg,
                            shuffle_seed=fold_shuffle_seed)

    # Test: calculate accuracy on held-out fold (union BG for root constraint).
    # bg_clauses is a frozen tuple (root_clauses) and kb_clauses a list — coerce
    # both so the union is list + list, not list + tuple.
    # Delivered theory = learned bias constraints + memorized ¬e⁻ + root
    # (Algorithm 3: KB <- B' u NE; Definition 6 requires it to reject every e⁻).
    # getattr: only ConGen resolves ne_clauses today.
    with AccuracyCalculator(list(run_result.kb_clauses)
                            + [list(c) for c in getattr(run_result, 'ne_clauses', ()) or ()]
                            + list(run_result.bg_clauses),
                            variables, solver_name) as calculator:
        accuracy_result = calculator.calculate(test_pos, test_neg)

    fold_accuracy = accuracy_result.metrics.accuracy

    # Store fold result (getattr for runner-specific fields only)
    fold_result = CrossValidationFoldResult(
        fold_index=fold_idx,
        accuracy=fold_accuracy,
        metrics=accuracy_result.metrics,
        performance=run_result.metrics,
        kb_constraints=run_result.kb_constraints,
        bg_clauses=run_result.bg_clauses,
        redundant_constraints=getattr(run_result, 'redundant_constraints', []),
        n_bias=run_result.n_bias,
        n_kb=run_result.n_kb,
        ne_constraints=list(getattr(run_result, 'ne_constraints', ()) or ()),
        n_ne=getattr(run_result, 'n_ne', 0),
        ne_clauses=[list(c) for c in getattr(run_result, 'ne_clauses', ()) or ()],
        redundant_ne_constraints=list(
            getattr(run_result, 'redundant_ne_constraints', ()) or ()),
        n_train_pos=len(train_pos),
        n_train_neg=len(train_neg),
        n_test_pos=len(test_pos),
        n_test_neg=len(test_neg),
        n_mss=getattr(run_result, 'n_mss', None),
        n_queries=getattr(run_result, 'n_queries', None),
        convergence_reason=getattr(run_result, 'convergence_reason', None),
        profiler_data=run_result.profiler_data
    )

    n_queries = getattr(run_result, 'n_queries', None)
    logging.info('Fold %d: accuracy=%.4f (TP=%d, TN=%d, FP=%d, FN=%d), KB=%d%s',
                 fold_idx + 1, fold_accuracy,
                 accuracy_result.metrics.true_positives,
                 accuracy_result.metrics.true_negatives,
                 accuracy_result.metrics.false_positives,
                 accuracy_result.metrics.false_negatives,
                 run_result.n_kb,
                 f', queries={n_queries}' if n_queries is not None else '')

    return fold_result


def _assemble_cv_result(
        fold_results: List[CrossValidationFoldResult],
        total_runtime_ms: float,
) -> CrossValidationResult:
    """Fold results -> CrossValidationResult. Pure post-processing.

    Every cross-fold artifact is computed here and only here — the accuracy
    mean/std, the intersected KB, the aggregated performance block. Folds
    computed in one process and folds restored from partials therefore land in
    exactly the same shape; see ``conacq.eval.cv_partials.merge_fold_results``.
    """
    fold_results = sorted(fold_results, key=lambda fr: fr.fold_index)
    fold_accuracies = [fr.accuracy for fr in fold_results]

    # Calculate mean and std of accuracy
    mean_acc = sum(fold_accuracies) / len(fold_accuracies)
    if len(fold_accuracies) > 1:
        variance = sum((x - mean_acc) ** 2 for x in fold_accuracies) / (len(fold_accuracies) - 1)
        std_acc = variance ** 0.5
    else:
        std_acc = 0.0

    # Compute intersected KB
    fold_kbs = [set(fr.kb_constraints) for fr in fold_results]
    if fold_kbs:
        intersected = fold_kbs[0]
        for kb in fold_kbs[1:]:
            intersected = intersected & kb
        intersected_kb = sorted(list(intersected))
    else:
        intersected_kb = []

    logging.info('Intersected KB: %d constraints (from fold sizes: %s)',
                 len(intersected_kb), [len(kb) for kb in fold_kbs])

    # Aggregate performance metrics
    agg_performance = aggregate([fr.performance for fr in fold_results])

    # bg_clauses are identical across folds (from feature model root constraint)
    bg_clauses = fold_results[0].bg_clauses if fold_results else []

    return CrossValidationResult(
        n_folds=len(fold_results),
        fold_accuracies=fold_accuracies,
        mean_accuracy=mean_acc,
        std_accuracy=std_acc,
        fold_results=fold_results,
        performance=agg_performance,
        intersected_kb=intersected_kb,
        bg_clauses=bg_clauses,
        total_runtime_ms=total_runtime_ms
    )


def _run_cv_loop(
        runner: BaseRunner,
        positive_examples: List[Dict[str, bool]],
        negative_examples: List[Dict[str, bool]],
        n_folds: int,
        seed: int,
        solver_name: str,
        label: str,
        shuffle_each_fold: bool = True,
        fold_data: Optional[FoldData] = None,
        shuffle_bias: bool = False,
        fold_indices: Optional[Sequence[int]] = None,
        on_fold: Optional[Callable[[CrossValidationFoldResult], None]] = None,
        done_folds: Optional[Mapping[int, CrossValidationFoldResult]] = None
) -> Optional[CrossValidationResult]:
    """Shared CV loop for both ConGen and Interactive runners.

    Args:
        runner: Runner with run(pos, neg, shuffle_seed) and feature_ids property
        positive_examples: List of E+ ({feature: True/False})
        negative_examples: List of E- ({feature: True/False})
        n_folds: Number of folds
        seed: Random seed for fold generation
        solver_name: SAT solver name
        label: Log label ('ConGen' or 'Interactive')
        shuffle_each_fold: Shuffle training examples before each fold
        fold_data: Optional pre-generated fold assignments
        shuffle_bias: Shuffle bias ordering per fold
        fold_indices: Folds to compute this call. ``None`` means all of them,
            which is the ordinary single-process run.
        on_fold: Called with each fold result the moment it is finished, before
            the next fold starts. The windowed sweep uses it to make the fold
            durable, so a window that ends mid-run loses at most one fold.
        done_folds: Fold results already computed elsewhere (restored from
            partials), keyed by fold index. Merged with the folds computed here.

    Returns:
        The CrossValidationResult, or ``None`` when the folds available (computed
        plus restored) do not yet cover all ``n_folds`` — the caller is
        mid-sweep and there is nothing complete to assemble.
    """
    # Use runner.feature_ids (BaseRunner property)
    variables = runner.feature_ids

    # Generate folds if not pre-provided
    folds_provided = fold_data is not None
    if not folds_provided:
        fold_data = generate_folds(
            n_positive=len(positive_examples),
            n_negative=len(negative_examples),
            n_folds=n_folds,
            seed=seed
        )
    n_folds = fold_data.n_folds

    if fold_indices is None:
        fold_indices = range(n_folds)
    out_of_range = [i for i in fold_indices if not 0 <= i < n_folds]
    if out_of_range:
        raise ValueError(
            f"fold index out of range for a {n_folds}-fold split: {out_of_range}")

    logging.info('>>> %s CV (n=%d, |E+|=%d, |E-|=%d, shared_folds=%s)',
                 label, n_folds, len(positive_examples), len(negative_examples),
                 folds_provided)

    cv_start_time = time.perf_counter()

    collected: Dict[int, CrossValidationFoldResult] = dict(done_folds or {})

    for fold_idx in fold_indices:
        fold_result = _compute_fold(
            runner=runner,
            positive_examples=positive_examples,
            negative_examples=negative_examples,
            fold_data=fold_data,
            fold_idx=fold_idx,
            variables=variables,
            solver_name=solver_name,
            label=label,
            shuffle_each_fold=shuffle_each_fold,
            shuffle_bias=shuffle_bias,
        )
        collected[fold_idx] = fold_result
        # Durability hook fires before the next fold starts, so an interrupted
        # window costs at most the fold that was running.
        if on_fold is not None:
            on_fold(fold_result)

    # Calculate total CV time
    cv_end_time = time.perf_counter()
    total_runtime_ms = (cv_end_time - cv_start_time) * 1000

    missing = [i for i in range(n_folds) if i not in collected]
    if missing:
        logging.info('%s CV: %d/%d folds done, missing %s — nothing to assemble yet',
                     label, len(collected), n_folds, missing)
        return None

    result = _assemble_cv_result(list(collected.values()), total_runtime_ms)

    logging.info('%s CV: accuracy = %.4f +/- %.4f, total_time = %.2f ms',
                 label, result.mean_accuracy, result.std_accuracy, total_runtime_ms)

    return result


def n_fold_cross_validation(
        positive_examples: List[Dict[str, bool]],
        negative_examples: List[Dict[str, bool]],
        n_folds: int,
        bias_path: str,
        fm_path: str,
        seed: int,
        solver_name: str = 'glucose4',
        use_incremental: bool = True,
        shuffle_each_fold: bool = True,
        fold_data: Optional[FoldData] = None,
        shuffle_bias: bool = False,
        fold_indices: Optional[Sequence[int]] = None,
        on_fold: Optional[Callable[[CrossValidationFoldResult], None]] = None,
        done_folds: Optional[Mapping[int, CrossValidationFoldResult]] = None
) -> Optional[CrossValidationResult]:
    """
    Standard n-fold cross validation.

    Process:
    1. Split examples into n folds
    2. For each fold i:
       - Train: run ConGen on (n-1) folds to learn KB
       - Test: calculate accuracy on fold i (held-out)
    3. Report mean accuracy +/- std
    4. Compute intersected KB (constraints common to all folds)

    Args:
        positive_examples: List of E+ ({feature: True/False})
        negative_examples: List of E- ({feature: True/False})
        n_folds: Number of folds (e.g., 5 or 10)
        bias_path: Path to bias JSON file
        fm_path: Path to feature model (.uvl) file
        seed: Random seed for fold generation and training shuffle (required)
        solver_name: SAT solver name
        use_incremental: Use incremental solver mode
        shuffle_each_fold: Shuffle training examples before each fold
        fold_data: Optional pre-generated fold assignments (for shared folds)
        shuffle_bias: Shuffle bias ordering per fold using fold_data.shuffle_seeds
        fold_indices: Folds to compute this call (``None`` = all)
        on_fold: Durability hook, called with each finished fold result
        done_folds: Fold results restored from partials, keyed by fold index

    Returns:
        The CrossValidationResult, or ``None`` when the folds available do not
        yet cover all of them — see ``_run_cv_loop``.
    """
    from conacq.runners import ConGenRunner

    runner = ConGenRunner(
        bias_path=bias_path,
        fm_path=fm_path,
        solver_name=solver_name,
        use_incremental=use_incremental
    )
    try:
        return _run_cv_loop(
            runner=runner,
            positive_examples=positive_examples,
            negative_examples=negative_examples,
            n_folds=n_folds, seed=seed,
            solver_name=solver_name, label='ConGen',
            shuffle_each_fold=shuffle_each_fold,
            fold_data=fold_data, shuffle_bias=shuffle_bias,
            fold_indices=fold_indices, on_fold=on_fold, done_folds=done_folds
        )
    finally:
        runner.cleanup()




def n_fold_cross_validation_interactive(
        positive_examples: List[Dict[str, bool]],
        negative_examples: List[Dict[str, bool]],
        n_folds: int,
        fm_path: str,
        bias_path: str,
        seed: int,
        solver_name: str = 'glucose4',
        max_queries: int = 1000,
        query_mode: str = 'example_only',
        use_incremental: bool = True,
        shuffle_each_fold: bool = True,
        fold_data: Optional[FoldData] = None,
        shuffle_bias: bool = False,
        timeout_s: Optional[float] = None,
        fold_indices: Optional[Sequence[int]] = None,
        on_fold: Optional[Callable[[CrossValidationFoldResult], None]] = None,
        done_folds: Optional[Mapping[int, CrossValidationFoldResult]] = None
) -> Optional[CrossValidationResult]:
    """
    n-fold cross validation using interactive (QuAcq) learning.

    Same CV loop as ConGen CV but using QuAcqRunner.

    Args:
        positive_examples: List of E+ ({feature: True/False})
        negative_examples: List of E- ({feature: True/False})
        n_folds: Number of folds
        fm_path: Path to feature model (.uvl)
        bias_path: Path to bias file (.json)
        seed: Random seed for fold generation and training shuffle (required)
        solver_name: SAT solver name
        max_queries: Maximum queries per fold — the stopping RULE, deterministic and
            machine-independent, and the only bound any reported number may rest on
        query_mode: 'example_only' or 'example_first'
        timeout_s: Optional per-fold wall-clock GUARD (seconds). Operational only: it
            stops a pathological fold from holding a sweep window open, is checked
            between outer iterations, and depends on machine load. It records
            convergence_reason='timeout', which is distinct from 'max_queries' so a
            clock-stopped fold can never be read as a budget-stopped one.
        use_incremental: Use incremental solver mode
        shuffle_each_fold: Shuffle training examples before each fold
        fold_data: Optional pre-generated fold assignments
        shuffle_bias: Shuffle bias ordering per fold using fold_data.shuffle_seeds
        fold_indices: Folds to compute this call (``None`` = all)
        on_fold: Durability hook, called with each finished fold result
        done_folds: Fold results restored from partials, keyed by fold index

    Returns:
        The CrossValidationResult, or ``None`` when the folds available do not
        yet cover all of them — see ``_run_cv_loop``.
    """
    from conacq.runners import QuAcqRunner

    # Refuse to run unseeded. The example pool is shuffled with
    # ``fold_data.shuffle_seeds[i] if shuffle_bias else None``, and QueryProvider
    # passes that straight to ``random.Random(seed)`` (query_provider.py:60), so a
    # False here means the pool order — and therefore which queries are asked, and
    # therefore the learned KB — comes from OS entropy and the fold does not
    # reproduce. Nothing downstream would report that; the numbers would simply
    # differ between runs. ADR-0015 decided to seed by fold index unconditionally
    # and decouple it from this knob; until that lands, refuse rather than run
    # silently unseeded.
    if not shuffle_bias:
        raise ValueError(
            "interactive CV requires shuffle_bias=True: the query pool seed would "
            "be None, seeding the shuffle from OS entropy and making the run "
            "irreproducible. Set shuffle_bias=true in the [evaluation] config "
            "block (ADR-0015 will remove this coupling)."
        )

    runner = QuAcqRunner(
        bias_path=bias_path,
        fm_path=fm_path,
        solver_name=solver_name,
        max_queries=max_queries,
        query_mode=query_mode,
        use_incremental=use_incremental,
        timeout_s=timeout_s
    )
    try:
        return _run_cv_loop(
            runner=runner,
            positive_examples=positive_examples,
            negative_examples=negative_examples,
            n_folds=n_folds, seed=seed,
            solver_name=solver_name, label='Interactive',
            shuffle_each_fold=shuffle_each_fold,
            fold_data=fold_data, shuffle_bias=shuffle_bias,
            fold_indices=fold_indices, on_fold=on_fold, done_folds=done_folds
        )
    finally:
        runner.cleanup()

"""Per-fold persistence for cross-validation, so a sweep survives interruption.

The sweep runs in windows shorter than some of its units. A fold that is still
running when the window closes is a fold that has to be redone from zero, so each
fold is made durable the moment it finishes and a later call assembles the
finished folds into the ordinary CV JSON.

The split is sound because a fold reads only ``fold_data`` and its own index, with
both RNG streams seeded from ``fold_data.shuffle_seeds[fold_idx]``
(``cross_validation._compute_fold``). Everything that crosses folds — accuracy
mean/std, the intersected KB, the aggregated performance block — is computed in
``cross_validation._assemble_cv_result``, which merged folds and single-process
folds go through alike.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from conacq.atomic_io import write_json_atomic
from conacq.runners.metrics import (
    CONGEN_METRICS, QUACQ_METRICS, MetricSpec, RunMetrics,
)

from .cross_validation import CrossValidationFoldResult
from .metrics import EvaluationMetrics

logger = logging.getLogger(__name__)

# Bumped whenever the on-disk partial changes shape. A partial written by an older
# schema is refused rather than half-read: a silently mis-parsed fold would poison
# a merged result that looks perfectly well-formed.
PARTIAL_SCHEMA = 'acqmss.cv.partial/1'

_SPECS: Dict[str, Tuple[MetricSpec, ...]] = {
    'congen': CONGEN_METRICS,
    'interactive': QUACQ_METRICS,
}


def partial_filename(model_name: str, mode_name: str, fold_idx: int,
                     query_mode: Optional[str] = None) -> str:
    """Name of one fold's partial.

    ``query_mode`` is part of the name for the interactive algorithm, mirroring the
    final CV filename: example_only and example_first are separate conditions and
    must not overwrite each other's folds.
    """
    suffix = f"_{query_mode}" if query_mode else ""
    return f"{model_name}_{mode_name}{suffix}_fold{fold_idx}.json"


def write_partial(partial_dir: Path, model_name: str, mode_name: str,
                  algorithm: str, n_folds: int, fold_result: CrossValidationFoldResult,
                  query_mode: Optional[str] = None, commit: Optional[str] = None) -> Path:
    """Persist one finished fold. Atomic: a crash cannot leave a half-written fold
    that a later run would mistake for a completed one."""
    partial_dir.mkdir(parents=True, exist_ok=True)
    path = partial_dir / partial_filename(model_name, mode_name,
                                          fold_result.fold_index, query_mode)
    write_json_atomic(path, {
        'schema': PARTIAL_SCHEMA,
        'model': model_name,
        'algorithm': algorithm,
        'solver_mode': mode_name,
        'query_mode': query_mode,
        'n_folds': n_folds,
        'fold_index': fold_result.fold_index,
        'commit': commit,
        'fold': fold_result.to_dict(),
    })
    logger.info("  Fold %d durable: %s", fold_result.fold_index, path)
    return path


def fold_result_from_dict(fold: Mapping, algorithm: str) -> CrossValidationFoldResult:
    """Rebuild a fold result from its serialized form.

    Inverse of ``CrossValidationFoldResult.to_dict``. ``performance`` is the metric
    spec's own keys plus the profiler snapshot, so the spec is re-attached from the
    algorithm rather than inferred from the keys present.
    """
    perf = dict(fold['performance'])
    profiler_data = perf.pop('profiler', {})
    stats = fold['statistics']
    m = fold['metrics']
    return CrossValidationFoldResult(
        fold_index=fold['fold_index'],
        accuracy=fold['accuracy'],
        metrics=EvaluationMetrics(
            true_positives=m['true_positives'],
            true_negatives=m['true_negatives'],
            false_positives=m['false_positives'],
            false_negatives=m['false_negatives'],
        ),
        performance=RunMetrics(_SPECS[algorithm], perf),
        kb_constraints=fold['kb_constraints'],
        bg_clauses=fold['bg_clauses'],
        redundant_constraints=fold['redundant_constraints'],
        n_bias=stats['n_bias'],
        n_kb=stats['n_kb'],
        n_train_pos=fold['train_size']['positive'],
        n_train_neg=fold['train_size']['negative'],
        n_test_pos=fold['test_size']['positive'],
        n_test_neg=fold['test_size']['negative'],
        n_mss=stats.get('n_mss'),
        ne_constraints=fold.get('ne_constraints', []),
        n_ne=stats.get('n_ne', 0),
        # Round-tripped, or a resumed window would silently deliver folds without the
        # ¬e⁻ clauses while a single-process run kept them — the merge would look fine.
        ne_clauses=[list(c) for c in fold.get('ne_clauses', [])],
        redundant_ne_constraints=fold.get('redundant_ne_constraints', []),
        n_queries=fold.get('n_queries'),
        convergence_reason=fold.get('convergence_reason'),
        profiler_data=profiler_data,
    )


def load_partials(partial_dir: Path, model_name: str, mode_name: str,
                  algorithm: str, n_folds: int,
                  query_mode: Optional[str] = None
                  ) -> Dict[int, CrossValidationFoldResult]:
    """Restore whichever folds are already on disk, keyed by fold index."""
    found: Dict[int, CrossValidationFoldResult] = {}
    if not partial_dir.is_dir():
        return found

    for fold_idx in range(n_folds):
        path = partial_dir / partial_filename(model_name, mode_name, fold_idx, query_mode)
        if not path.exists():
            continue
        with open(path, 'r') as fh:
            payload = json.load(fh)
        if payload.get('schema') != PARTIAL_SCHEMA:
            raise ValueError(
                f"{path}: partial schema {payload.get('schema')!r}, "
                f"expected {PARTIAL_SCHEMA!r}. Delete the stale partials and re-run "
                f"those folds; do not merge across schema versions.")
        if payload.get('algorithm') != algorithm:
            raise ValueError(
                f"{path}: partial was written by algorithm "
                f"{payload.get('algorithm')!r}, not {algorithm!r}.")
        if payload.get('n_folds') != n_folds:
            raise ValueError(
                f"{path}: partial is from a {payload.get('n_folds')}-fold split, "
                f"this run is {n_folds}-fold.")
        found[fold_idx] = fold_result_from_dict(payload['fold'], algorithm)

    if found:
        logger.info("  Restored %d/%d folds from %s", len(found), n_folds, partial_dir)
    return found

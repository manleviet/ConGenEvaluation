#!/usr/bin/env python
"""
Extract evaluation results and generate tables for the paper.

Usage:
    python -m apps.extract_results [--results-dir data/results] [--output-dir paper/tables]

Tables generated:
    - Paper Tables 7, 9, 10, 11 (consistency checks, accuracy by strategy)
    - Fold metrics (Precision/Recall/F1)
    - Performance, KB summary, incremental comparison
"""

import argparse
import json
import logging
import re
import statistics
import sys
import tomllib
from pathlib import Path

from conacq.atomic_io import write_text_atomic
from apps._harness import build_parser, load_config, setup_logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# KB name mapping (paper names).
#
# KEYS MUST MATCH THE RESULT FILENAMES EXACTLY. `_get_result` resolves a label through
# `KB_REVERSE.get(...)`, an exact lookup, so a near-miss produces no error and no data:
# 'arcade' does not match `arcade-game_*`, and busybox was absent altogether. v1.0.0
# shipped `KB3 & - & - & - & - & - & -` and no busybox row because of those two lines.
#
# apps/sosym_r1/check_table_coverage.py asserts this against the filenames on disk, so
# the mapping cannot silently drift from the data again. The labels themselves stay a
# decision of the paper -- which model is called KB1 is not something the code should
# invent -- but the gate proves whatever the paper chose actually resolves.
KB_MAPPING = {
    'REAL-FM-7': 'KB1',
    'fqa': 'KB2',
    'arcade-game': 'KB3',
    'REAL-FM-4': 'KB4',
    'busybox-1.18.0': 'KB5',
}
KB_REVERSE = {v: k for k, v in KB_MAPPING.items()}
# Derived, never a second list to keep in step: the earlier pair could disagree, and a
# model added to one but not the other would vanish from every table without a word.
KB_NAMES = list(KB_MAPPING.values())

# Headers and column specs derived from KB_NAMES for the same reason KB_NAMES is derived
# from KB_MAPPING: adding busybox as KB5 filled the row bodies (which iterate KB_NAMES)
# while the headers stayed at four labels, so `{lcccc}` declared five columns for six
# fields -- LaTeX that does not compile. A header written out by hand is a copy of a
# fact, and every copy of this fact has now been wrong at least once.
KB_HEADER_MD = " | ".join(KB_NAMES)
KB_HEADER_TEX = " & ".join(KB_NAMES)
KB_SEP_MD = "|".join(":---:" for _ in KB_NAMES)
KB_COLS = "c" * len(KB_NAMES)

# Two different absences, told apart because a reader cannot otherwise distinguish
# "we did not run this" from "this scored zero". busybox has 4 of the 6 sampling
# conditions -- rs_2n and rs_3n were never run -- and a bare dash in those cells reads
# as a measurement.
ABSENT = "n/a"          # no result file for this (knowledge base, sampling, mode)
UNSCORED = "-"          # a run exists, but this strategy tier was not scored

# Sampling strategies in order
STRATEGIES = ['rs_1n', 'rs_2n', 'rs_3n', 'rs_m', '2cov', 'ff']
STRATEGY_NAMES = {
    'rs_1n': 'RS(1n)', 'rs_2n': 'RS(2n)', 'rs_3n': 'RS(3n)',
    'rs_m': 'RS(m)', '2cov': '2-COV', 'ff': 'FF',
}


@dataclass
class CVResult:
    """Cross-validation result data."""
    model: str
    strategy: str
    mode: str  # 'incremental' or 'non-incremental'
    n_folds: int
    mean_accuracy: float
    std_accuracy: float
    fold_accuracies: List[float]
    # Performance
    runtime_mean_ms: float
    runtime_std_ms: float
    checks_mean: float
    checks_std: float
    memory_max_mb: float
    # KB size
    n_bias: int
    n_mss_mean: float
    n_kb_mean: float
    n_intersected: int
    total_runtime_ms: float
    # Example counts (from training set)
    n_positive: int = 0
    n_negative: int = 0
    # Fold-level metrics (precision, recall, F1, specificity)
    precision_mean: float = 0.0
    precision_std: float = 0.0
    recall_mean: float = 0.0
    recall_std: float = 0.0
    f1_mean: float = 0.0
    f1_std: float = 0.0
    specificity_mean: float = 0.0
    specificity_std: float = 0.0
    # Strategy evaluation on intersected KB (description strategy)
    desc_accuracy: float = 0.0
    desc_precision: float = 0.0
    desc_recall: float = 0.0
    desc_f1: float = 0.0
    # Strategy evaluation on intersected KB (clause strategy)
    clause_accuracy: float = 0.0
    clause_precision: float = 0.0
    clause_recall: float = 0.0
    clause_f1: float = 0.0
    # Strategy evaluation on intersected KB (semantic strategy). Reported as its own
    # table rather than as three more columns on the three-tier one: adding P and R to
    # that table makes it 27 columns, which does not fit even as ``table*``, and moving
    # Desc/Clause to an appendix to make room would remove the comparison the three-tier
    # question is about.
    sem_accuracy: float = 0.0
    sem_precision: float = 0.0
    sem_recall: float = 0.0
    sem_f1: float = 0.0
    # Absolute counts beside the rates. With recall saturated the practitioner-facing
    # quantity stops being a ratio and becomes a workload: fp is how many delivered
    # constraints are not entailed by the target and must be reviewed away, fn how many
    # must still be authored. |Cτ| = tp + fn, so the target size comes free and the
    # "reached only on the smallest instance" claim becomes checkable from the table.
    sem_tp: int = 0
    sem_fp: int = 0
    sem_fn: int = 0
    # Fold-agreement, NOT a quality score: |intersection of the folds' KBs| over the mean
    # fold KB size. Reported separately and never mixed into the tiers.
    intersect_n_kb: int = 0
    intersect_share: float = 0.0
    # Exact equivalence of the DELIVERED theory (KB u NE u BG) to the target model,
    # as folds attaining / folds scored. An all-zero cell is the result, not a gap:
    # it tells a reader that a high F1 does not mean the model was recovered.
    exact_equiv_attained: int = 0
    exact_equiv_scored: int = 0
    # Per-fold semantic precision/recall/F1, kept alongside the intersected-KB figures.
    # A published F1 cannot be decomposed back into P and R, and the decomposition is
    # what says whether a middling score is a theory that is too weak or one that is too
    # strong. The folds carry it; only the tables dropped it.
    # Per-fold runtimes, kept so the table can show dispersion. A bare mean is not usable
    # here: within one cell the folds span a factor of 2.8 (REAL-FM-4 2cov, 1.65 h to
    # 4.64 h measured on an idle machine), which is an order of magnitude larger than the
    # ~5% that machine contention costs. A reader given only the mean cannot tell those
    # apart, and the larger of the two is the one the tables were silent about.
    fold_runtimes_ms: List[float] = field(default_factory=list)
    fold_semantic: List[Dict] = field(default_factory=list)
    # Positive share of the test split, in BOTH senses, because they differ by 15 points
    # here and an unlabelled one is a trap. ``pos_share_fold_mean`` is the mean over folds
    # of each fold's share: that is what an accept-everything knowledge base scores as a
    # CELL, since the paper's accuracy cell is itself a mean over folds, so it is the
    # trivial baseline the accuracy numbers must be read against. ``pos_share_pooled``
    # merges every test example into one set first — a different quantity, comparable to
    # nothing else in the tables.
    pos_share_fold_mean: float = 0.0
    pos_share_pooled: float = 0.0
    # 'congen', or the QuAcq query mode ('example_only' / 'example_first'). Stored
    # because the three are separate METHODS sharing one (model, strategy, mode) —
    # without it they overwrite each other in the results dict.
    method: str = 'congen'
    has_strategy_eval: bool = False


# =============================================================================
# Data Loading
# =============================================================================

# The trailing group is the QUERY MODE and it is CAPTURED. It used to be discarded, so
# congen, example_only and example_first parsed to one identical key — and results are
# stored by that key, so two of the three were silently overwritten by whichever file
# loaded last. A directory holding all three produced one method's numbers with nothing
# to say the others had been dropped.
_CV_PATTERN = re.compile(r'^(.+)_cv_(incremental|non-incremental)(?:_(.+))?\.json$')

_METHOD_CONGEN = 'congen'


def method_key(mode: str, method: str) -> str:
    """Storage key for one (mode, method).

    ConGen keeps the bare mode, so a ConGen-only results directory — which is every
    pre-existing caller — behaves exactly as before; the QuAcq methods get keys of
    their own instead of colliding with it.
    """
    return mode if method == _METHOD_CONGEN else f'{mode}::{method}'


def parse_filename(filename: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse CV result filename → (model, strategy, mode, method) or None.

      model_cv_incremental.json                 -> method 'congen'
      model_cv_incremental_example_only.json    -> method 'example_only'
      model_cv_incremental_example_first.json   -> method 'example_first'
    """
    m = _CV_PATTERN.match(filename)
    if not m:
        return None

    base, mode, method = m.group(1), m.group(2), m.group(3) or _METHOD_CONGEN

    for strategy in STRATEGIES:
        if base.endswith(f'_{strategy}'):
            model = base[:-len(f'_{strategy}')]
            return (model, strategy, mode, method)
    return None


def load_cv_result(filepath: Path) -> Optional[CVResult]:
    """Load CV result from JSON file."""
    parsed = parse_filename(filepath.name)
    if not parsed:
        return None

    model, strategy, mode, method = parsed

    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Error loading %s: %s", filepath, e)
        return None

    perf = data.get('performance', {})
    runtime = perf.get('runtime', {})
    checks = perf.get('consistency_checks', {})
    memory = perf.get('memory', {})
    kb_size = perf.get('kb_size', {})

    # Extract per-fold data
    n_bias, n_positive, n_negative = 0, 0, 0
    fold_precisions, fold_recalls, fold_f1s, fold_specificities = [], [], [], []
    if data.get('folds'):
        first_fold = data['folds'][0]
        n_bias = first_fold.get('statistics', {}).get('n_bias', 0)
        train_size = first_fold.get('train_size', {})
        n_positive = train_size.get('positive', 0)
        n_negative = train_size.get('negative', 0)
        for fold in data['folds']:
            metrics = fold.get('metrics', {})
            if metrics:
                fold_precisions.append(metrics.get('precision', 0.0))
                fold_recalls.append(metrics.get('recall', 0.0))
                fold_f1s.append(metrics.get('f1_score', 0.0))
                fold_specificities.append(metrics.get('specificity', 0.0))

    def _mean_std(values):
        if not values:
            return 0.0, 0.0
        m = statistics.mean(values)
        s = statistics.pstdev(values) if len(values) > 1 else 0.0
        return m, s

    prec_m, prec_s = _mean_std(fold_precisions)
    rec_m, rec_s = _mean_std(fold_recalls)
    f1_m, f1_s = _mean_std(fold_f1s)
    spec_m, spec_s = _mean_std(fold_specificities)

    # A cell is the MEAN OVER FOLDS, not the intersected KB.
    #
    # Two different objects were being reported under one name. ``intersected_kb`` is the
    # set intersection of the folds' knowledge bases; the per-fold mean is what both
    # papers actually report, and what ``summary.<tier>.f1_score.mean`` holds. They differ
    # substantially — arcade rs_1n scores 0.524859 as a fold mean and 0.443966
    # intersected, and it is the fold mean that is in print. The intersection is a subset
    # of every fold's KB, so its recall can only fall and its value shrinks as the fold
    # count grows: a quantity that moves with k is not a property of the method, and it is
    # kept below as a stability statistic rather than a quality score.
    def _fold_mean(tier: str, key: str) -> float:
        vals = [((f.get('evaluation') or {}).get(tier) or {}).get('metrics', {}).get(key)
                for f in data.get('folds', [])]
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else 0.0

    has_strategy_eval = any((f.get('evaluation') or {}).get('semantic')
                            or (f.get('evaluation') or {}).get('description')
                            for f in data.get('folds', []))
    desc_eval = {k: _fold_mean('description', k) for k in
                 ('accuracy', 'precision', 'recall', 'f1_score')}
    clause_eval = {k: _fold_mean('clause', k) for k in
                   ('accuracy', 'precision', 'recall', 'f1_score')}
    sem_eval = {k: _fold_mean('semantic', k) for k in
                ('accuracy', 'precision', 'recall', 'f1_score',
                 'true_positives', 'false_positives', 'false_negatives')}

    # Retained, relabelled: how much of a delivered KB survives in EVERY fold. It says how
    # much of the result is an artefact of which examples landed in the training split.
    intersected_data = data.get('intersected_kb', {})
    intersected_data = intersected_data if isinstance(intersected_data, dict) else {}
    fold_kb_sizes = [f.get('statistics', {}).get('n_kb', 0) for f in data.get('folds', [])]
    intersect_n = intersected_data.get('n_kb', 0)
    intersect_share = (intersect_n / statistics.mean(fold_kb_sizes)
                       if fold_kb_sizes and statistics.mean(fold_kb_sizes) else 0.0)
    equiv = (data.get('summary') or {}).get('exact_equiv') or {}
    _shares, _P, _N = [], 0, 0
    for fold in data.get('folds', []):
        t = fold.get('test_size') or {}
        pos, neg = t.get('positive', 0), t.get('negative', 0)
        _P += pos
        _N += neg
        if pos + neg:
            _shares.append(pos / (pos + neg))
    pos_share_fold_mean = statistics.mean(_shares) if _shares else 0.0
    pos_share_pooled = _P / (_P + _N) if (_P + _N) else 0.0
    fold_semantic = []
    for fold in data.get('folds', []):
        sm = ((fold.get('evaluation') or {}).get('semantic') or {}).get('metrics')
        if sm:
            fold_semantic.append({
                'fold': fold.get('fold_index'),
                'precision': sm.get('precision', 0.0),
                'recall': sm.get('recall', 0.0),
                'f1_score': sm.get('f1_score', 0.0),
                'tp': sm.get('true_positives', 0),
                'fp': sm.get('false_positives', 0),
                'fn': sm.get('false_negatives', 0),
                'exact_equiv': (fold.get('evaluation') or {}).get('exact_equiv'),
            })

    return CVResult(
        model=model, strategy=strategy, mode=mode, method=method,
        n_folds=data.get('n_folds', 5),
        mean_accuracy=data.get('mean_accuracy', 0),
        std_accuracy=data.get('std_accuracy', 0),
        fold_accuracies=data.get('fold_accuracies', []),
        runtime_mean_ms=runtime.get('mean_ms', 0),
        runtime_std_ms=runtime.get('std_ms', 0),
        fold_runtimes_ms=[(f.get('performance') or {}).get('runtime_ms')
                          for f in data.get('folds', [])
                          if (f.get('performance') or {}).get('runtime_ms') is not None],
        checks_mean=checks.get('mean', 0),
        checks_std=checks.get('std', 0),
        memory_max_mb=memory.get('max_mb', 0),
        n_bias=n_bias,
        n_mss_mean=kb_size.get('n_mss_mean') or 0,
        n_kb_mean=kb_size.get('n_kb_mean', 0),
        n_intersected=(intersected_data.get('n_kb', 0)
                       if isinstance(intersected_data, dict)
                       else data.get('n_intersected', 0)),
        total_runtime_ms=data.get('total_runtime_ms', 0),
        n_positive=n_positive, n_negative=n_negative,
        precision_mean=prec_m, precision_std=prec_s,
        recall_mean=rec_m, recall_std=rec_s,
        f1_mean=f1_m, f1_std=f1_s,
        specificity_mean=spec_m, specificity_std=spec_s,
        desc_accuracy=desc_eval.get('accuracy', 0.0),
        desc_precision=desc_eval.get('precision', 0.0),
        desc_recall=desc_eval.get('recall', 0.0),
        desc_f1=desc_eval.get('f1_score', 0.0),
        clause_accuracy=clause_eval.get('accuracy', 0.0),
        clause_precision=clause_eval.get('precision', 0.0),
        clause_recall=clause_eval.get('recall', 0.0),
        clause_f1=clause_eval.get('f1_score', 0.0),
        sem_accuracy=sem_eval.get('accuracy', 0.0),
        sem_precision=sem_eval.get('precision', 0.0),
        sem_recall=sem_eval.get('recall', 0.0),
        sem_f1=sem_eval.get('f1_score', 0.0),
        sem_tp=round(sem_eval.get('true_positives', 0)),
        sem_fp=round(sem_eval.get('false_positives', 0)),
        sem_fn=round(sem_eval.get('false_negatives', 0)),
        intersect_n_kb=intersect_n,
        intersect_share=intersect_share,
        exact_equiv_attained=equiv.get('attained', 0),
        exact_equiv_scored=equiv.get('scored', 0),
        fold_semantic=fold_semantic,
        pos_share_fold_mean=pos_share_fold_mean,
        pos_share_pooled=pos_share_pooled,
        has_strategy_eval=has_strategy_eval,
    )


def load_eval_result(eval_path: Path) -> Optional[Dict]:
    """Load evaluation metrics from a *_eval.json file (from run_compare.py).

    Returns:
        Dict with 'description' and/or 'clause' strategy metrics, or None
    """
    try:
        with open(eval_path) as f:
            data = json.load(f)
        return data.get('evaluation', {})
    except Exception:
        return None


def _find_matching_eval(results_dir: Path, model: str, strategy: str, mode: str) -> Optional[Dict]:
    """Find *_eval.json matching a CV result by model/strategy/mode.

    Looks for patterns like:
    - {model}_{strategy}_{mode}_intersected_kb_eval.json  (new run_compare output)
    - {model}_{strategy}_intersected_eval_{mode}.json      (old run_congen_eval output)
    """
    # New format: run_compare.py saves {kb_stem}_eval.json
    # KB stem for intersected: {model}_{strategy}_{mode}_intersected_kb
    new_pattern = f"{model}_{strategy}_{mode}_intersected_kb_eval.json"
    new_path = results_dir / new_pattern
    if new_path.exists():
        return load_eval_result(new_path)

    # Old format from run_congen_eval.py
    old_pattern = f"{model}_{strategy}_intersected_eval_{mode}.json"
    old_path = results_dir / old_pattern
    if old_path.exists():
        return load_eval_result(old_path)

    return None


def load_all_results(results_dir: Path) -> Dict[str, Dict[str, Dict[str, CVResult]]]:
    """Load all CV results. Returns: {model: {strategy: {mode: CVResult}}}

    Priority: embedded eval in unified JSON > separate *_eval.json > nothing
    """
    results = {}
    # One level down as well as flat. The sweep writes ``<results>/<algorithm>/*.json``,
    # so a flat glob at the documented ``--results-dir`` matches nothing — and matching
    # nothing is silent: every table renders with '-' in every cell. That is not
    # hypothetical. ``paper/tables/results_tables.tex`` has 0 rows with data in every
    # INCREMENTAL table and full data in every non-incremental one, which is what a run
    # that saw only part of the tree looks like.
    for filepath in sorted(list(results_dir.glob('*_cv_*.json'))
                           + list(results_dir.glob('*/*_cv_*.json'))):
        result = load_cv_result(filepath)
        if result:
            # Only look for external eval if embedded is absent
            if not result.has_strategy_eval:
                ext_eval = _find_matching_eval(results_dir, result.model,
                                               result.strategy, result.mode)
                if ext_eval:
                    desc_eval = ext_eval.get('description', {}).get('metrics', {})
                    clause_eval = ext_eval.get('clause', {}).get('metrics', {})
                    sem_eval = ext_eval.get('semantic', {}).get('metrics', {})
                    result.desc_accuracy = desc_eval.get('accuracy', result.desc_accuracy)
                    result.desc_precision = desc_eval.get('precision', result.desc_precision)
                    result.desc_recall = desc_eval.get('recall', result.desc_recall)
                    result.desc_f1 = desc_eval.get('f1_score', result.desc_f1)
                    result.clause_accuracy = clause_eval.get('accuracy', result.clause_accuracy)
                    result.clause_precision = clause_eval.get('precision', result.clause_precision)
                    result.clause_recall = clause_eval.get('recall', result.clause_recall)
                    result.clause_f1 = clause_eval.get('f1_score', result.clause_f1)
                    result.sem_accuracy = sem_eval.get('accuracy', result.sem_accuracy)
                    result.sem_precision = sem_eval.get('precision', result.sem_precision)
                    result.sem_recall = sem_eval.get('recall', result.sem_recall)
                    result.sem_f1 = sem_eval.get('f1_score', result.sem_f1)
                    result.sem_tp = sem_eval.get('true_positives', result.sem_tp)
                    result.sem_fp = sem_eval.get('false_positives', result.sem_fp)
                    result.sem_fn = sem_eval.get('false_negatives', result.sem_fn)
                    result.has_strategy_eval = True

            key = method_key(result.mode, result.method)
            results.setdefault(result.model, {}).setdefault(result.strategy, {})[key] = result
    return results


# =============================================================================
# Table Helpers — DRY formatting infrastructure
# =============================================================================

def _get_result(results: Dict, kb_name: str, strategy: str, mode: str) -> Optional[CVResult]:
    """Look up a CVResult by KB name, strategy, and mode."""
    model = KB_REVERSE.get(kb_name)
    if model and model in results and strategy in results[model] and mode in results[model][strategy]:
        return results[model][strategy][mode]
    return None


def _compact_grid_md(
    title: str, results: Dict, mode: str,
    cell_fn: Callable[[CVResult], str],
    strategies: List[str] = None, align: str = ':---:'
) -> str:
    """Generate a compact KB-rows × Strategy-columns table in Markdown."""
    strats = strategies or STRATEGIES
    lines = [f"## {title} - {mode.capitalize()} Mode", ""]

    header = "| KB |" + "".join(f" {STRATEGY_NAMES[s]} |" for s in strats)
    sep = "|:---|" + "".join(f"{align}|" for _ in strats)
    lines.extend([header, sep])

    for kb in KB_NAMES:
        row = f"| {kb} |"
        for s in strats:
            r = _get_result(results, kb, s, mode)
            row += f" {cell_fn(r)} |" if r else f" {ABSENT} |"
        lines.append(row)
    return "\n".join(lines)


def _latex_wrap(title: str, label: str, col_spec: str, header: str,
                body_lines: List[str], mode: str = '') -> str:
    """Wrap body lines in LaTeX table boilerplate."""
    caption = f"{title} ({mode.capitalize()})" if mode else title
    full_label = f"{label}_{mode}" if mode else label
    lines = [
        f"% {caption}",
        "\\begin{table}[htbp]", "\\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{tab:{full_label}}}",
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule", header, "\\midrule",
    ]
    lines.extend(body_lines)
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    return "\n".join(lines)


def _compact_grid_latex(
    title: str, label: str, results: Dict, mode: str,
    cell_fn: Callable[[CVResult], str],
    strategies: List[str] = None
) -> str:
    """Generate a compact KB-rows × Strategy-columns table in LaTeX."""
    strats = strategies or STRATEGIES
    col_spec = "l" + "c" * len(strats)
    header = "KB" + "".join(f" & {STRATEGY_NAMES[s]}" for s in strats) + " \\\\"
    body = []
    for kb in KB_NAMES:
        row = kb
        for s in strats:
            r = _get_result(results, kb, s, mode)
            row += f" & {cell_fn(r)}" if r else f" & {ABSENT}"
        row += " \\\\"
        body.append(row)
    return _latex_wrap(title, label, col_spec, header, body, mode)


# =============================================================================
# Table Generators — Compact grid tables (unified MD + LaTeX)
# =============================================================================

def generate_accuracy_table(results: Dict, mode: str, fmt: str) -> str:
    """Accuracy by Sampling Strategy (mean ± std)."""
    title = "Accuracy by Sampling Strategy"
    if fmt == 'md':
        return _compact_grid_md(f"Table: {title}", results, mode,
                                lambda r: f"{r.mean_accuracy:.4f} ± {r.std_accuracy:.4f}")
    return _compact_grid_latex(title, "accuracy", results, mode,
                               lambda r: f"{r.mean_accuracy:.4f} $\\pm$ {r.std_accuracy:.4f}")


def generate_accuracy_compact(results: Dict, mode: str) -> str:
    """Compact accuracy (fewer decimals, MD only)."""
    return _compact_grid_md("Table: Accuracy (Compact)", results, mode,
                            lambda r: f"{r.mean_accuracy:.2f}±{r.std_accuracy:.2f}")


def generate_fold_metrics_table(results: Dict, mode: str, fmt: str) -> str:
    """Fold-level Precision/Recall/F1."""
    title = "Precision / Recall / F1"
    cell = lambda r: f"{r.precision_mean:.2f}/{r.recall_mean:.2f}/{r.f1_mean:.2f}"
    if fmt == 'md':
        return _compact_grid_md(f"Table: Fold Metrics ({title})", results, mode, cell)
    return _compact_grid_latex(title, "fold_metrics", results, mode, cell)


def generate_runtime_compact(results: Dict, mode: str) -> str:
    """Compact runtime table, mean with the fold range beneath it (MD only).

    Never a bare mean. Fold-to-fold spread inside a single cell reaches 2.8x, so a mean
    on its own hides more variation than any effect the tables discuss.
    """
    def fmt(ms):
        return f"{ms/1000:.2f}s" if ms > 1000 else f"{ms:.0f}"

    def cell(r):
        if not r.fold_runtimes_ms:
            return fmt(r.runtime_mean_ms)
        lo, hi = min(r.fold_runtimes_ms), max(r.fold_runtimes_ms)
        return f"{fmt(r.runtime_mean_ms)} [{fmt(lo)}–{fmt(hi)}]"
    return _compact_grid_md("Table: Runtime, mean [min–max over folds]",
                            results, mode, cell, align='---:')


def generate_checks_compact(results: Dict, mode: str) -> str:
    """Compact consistency checks (MD only)."""
    return _compact_grid_md("Table: Consistency Checks", results, mode,
                            lambda r: f"{r.checks_mean:.0f}", align='---:')


def generate_strategy_eval_table(results: Dict, mode: str, fmt: str, eval_strategy: str) -> str:
    """Strategy evaluation on intersected KB (Acc/Prec/Rec/F1)."""
    title = f"Strategy Eval ({eval_strategy.capitalize()}) on Intersected KB — R/P/F1"

    # Recall first. Semantic precision denominators are not comparable across methods:
    # the comparator expands a named constraint into its clauses while a learned rule is
    # one clause, so the expansion factor (1.06-2.03 across the knowledge bases, worst on
    # fqa) inflates one side's denominator and not the other's. Recall is comparable
    # throughout, so it leads here and in every table below.
    _CELL = {
        'description': lambda r: (r.desc_recall, r.desc_precision, r.desc_f1),
        'clause': lambda r: (r.clause_recall, r.clause_precision, r.clause_f1),
        'semantic': lambda r: (r.sem_recall, r.sem_precision, r.sem_f1),
    }[eval_strategy]
    cell = lambda r: (
        "/".join(f"{v:.2f}" for v in _CELL(r)) if r.has_strategy_eval else "-"
    )

    if fmt == 'md':
        return _compact_grid_md(f"Table: {title}", results, mode, cell)
    return _compact_grid_latex(title, f"eval_{eval_strategy}", results, mode, cell)


def generate_three_tier_f1_table(results: Dict, mode: str, fmt: str) -> str:
    """F1 for all three tiers side by side — the comparison the tiers exist to support.

    Kept to F1 alone so the three tiers fit one table. Precision and recall for the
    semantic tier are carried by ``generate_semantic_prf_table``; adding them here
    would take the table to 27 columns, and dropping Desc/Clause to make room would
    remove the very comparison this table is for.
    """
    title = "Three-tier F1 on Intersected KB (Desc / Clause / Sem)"
    cell = lambda r: (
        f"{r.desc_f1:.2f}/{r.clause_f1:.2f}/{r.sem_f1:.2f}"
        if r.has_strategy_eval else "-"
    )
    if fmt == 'md':
        return _compact_grid_md(f"Table: {title}", results, mode, cell)
    return _compact_grid_latex(title, "three_tier_f1", results, mode, cell)


def methods_present(results: Dict, mode: str) -> List[str]:
    """Methods holding data for this solver mode, ConGen first then the QuAcq modes."""
    found = set()
    for strat_modes in results.values():
        for modes in strat_modes.values():
            for key, res in modes.items():
                if key == mode or key.startswith(f'{mode}::'):
                    found.add(res.method)
    order = [_METHOD_CONGEN, 'example_only', 'example_first']
    return [m for m in order if m in found] + sorted(found - set(order))


def select_method(results: Dict, mode: str, method: str) -> Dict:
    """Re-key one method's entries to the bare ``mode``.

    The grid helpers index by mode, so handing them a single method's slice lets the
    per-method tables reuse them unchanged rather than growing a fourth axis into a
    layout that is already KB x sampling.
    """
    key = method_key(mode, method)
    out: Dict = {}
    for model, strats in results.items():
        for strat, modes in strats.items():
            if key in modes:
                out.setdefault(model, {}).setdefault(strat, {})[mode] = modes[key]
    return out


_METHOD_LABEL = {_METHOD_CONGEN: 'ConGen', 'example_only': 'QuAcq (example-only)',
                 'example_first': 'QuAcq (example-first)'}


def generate_semantic_folds_md(results: Dict, mode: str) -> str:
    """Per-fold semantic recall / precision / F1, one row per fold.

    The cell-level tables report the intersected KB, which is one number per cell; this
    is the fold-level decomposition behind it. Recall leads, per the precision-denominator
    caveat. ``eq`` is the fold's exact-equivalence verdict: ``1``/``0`` measured,
    ``--`` not measured.
    """
    lines = [f"## Table: Semantic tier per fold — R/P/F1 ({mode.capitalize()} Mode)", "",
             "| Method | KB | Strategy | Fold | \\|Cτ\\| | tp | fp | fn "
             "| R | P | F1 | eq |",
             "|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|"]
    rows = 0
    for model in sorted(results):
        for strat in sorted(results[model]):
            for key, r in sorted(results[model][strat].items()):
                if not (key == mode or key.startswith(f'{mode}::')):
                    continue
                for fs in r.fold_semantic:
                    eq = fs.get('exact_equiv')
                    lines.append(
                        f"| {_METHOD_LABEL.get(r.method, r.method)} | {model} | {strat} "
                        f"| {fs['fold']} | {fs['tp'] + fs['fn']} | {fs['tp']} "
                        f"| {fs['fp']} | {fs['fn']} "
                        f"| {fs['recall']:.4f} | {fs['precision']:.4f} "
                        f"| {fs['f1_score']:.4f} "
                        f"| {'--' if eq is None else int(bool(eq))} |")
                    rows += 1
    if not rows:
        return ""
    return "\n".join(lines)


def generate_trivial_baseline_md(results: Dict, mode: str) -> str:
    """The accept-everything baseline each accuracy cell has to beat.

    A knowledge base that accepts every configuration scores, on fold i, exactly that
    fold's positive share. The paper's accuracy cell is the mean over folds, so the
    baseline for that cell is the MEAN OF THE FOLD SHARES — not the pooled share, which
    merges the test splits first and is comparable to nothing else in the tables. Over
    the ConGen results the two are 74.62% and 89.41%: fifteen points apart, wider than
    most effects the tables discuss, which is why both are printed and neither is called
    "the positive share".
    """
    lines = [f"## Table: Trivial baseline — accept-everything accuracy ({mode.capitalize()} Mode)",
             "", "`baseline` = mean over folds of the test split's positive share; an "
             "accept-everything KB scores exactly this. `pooled` merges the test splits "
             "first and is shown for reference only — it is not what an accuracy cell is "
             "compared against.", "",
             "| Method | KB | Strategy | baseline (fold mean) | pooled | reported accuracy |",
             "|:---|:---|:---|---:|---:|---:|"]
    rows = 0
    for model in sorted(results):
        for strat in sorted(results[model]):
            for key, r in sorted(results[model][strat].items()):
                if not (key == mode or key.startswith(f'{mode}::')):
                    continue
                lines.append(
                    f"| {_METHOD_LABEL.get(r.method, r.method)} | {model} | {strat} "
                    f"| {r.pos_share_fold_mean:.4f} | {r.pos_share_pooled:.4f} "
                    f"| {r.mean_accuracy:.4f} |")
                rows += 1
    return "\n".join(lines) if rows else ""


def generate_fold_agreement_md(results: Dict, mode: str) -> str:
    """How much of a delivered KB survives in EVERY fold — a reliability statistic.

    NOT a quality score, and it must never be mixed into the tiers. The intersection is a
    subset of every fold's knowledge base, so its recall can only fall, and it shrinks as
    the fold count grows: a quantity that moves with k is a property of the protocol, not
    of the method. What it does say is how much of a result is an artefact of which
    examples happened to land in the training split — 80% agreement and 29% agreement are
    very different claims about the same reported score.
    """
    lines = [f"## Table: Fold agreement ({mode.capitalize()} Mode)", "",
             "Share of the delivered knowledge base present in ALL folds "
             "(|intersection| / mean fold |KB|). A reliability statistic, not a quality "
             "score: the intersection is a subset of every fold's KB, so its recall can "
             "only fall, and it shrinks as the number of folds grows.", "",
             "| Method | KB | Strategy | mean \\|KB\\| | in all folds | agreement |",
             "|:---|:---|:---|---:|---:|---:|"]
    rows = 0
    for model in sorted(results):
        for strat in sorted(results[model]):
            for key, r in sorted(results[model][strat].items()):
                if not (key == mode or key.startswith(f'{mode}::')) or not r.intersect_n_kb:
                    continue
                mean_kb = (r.intersect_n_kb / r.intersect_share) if r.intersect_share else 0
                lines.append(
                    f"| {_METHOD_LABEL.get(r.method, r.method)} | {model} | {strat} "
                    f"| {mean_kb:.1f} | {r.intersect_n_kb} "
                    f"| {r.intersect_share * 100:.0f}% |")
                rows += 1
    return "\n".join(lines) if rows else ""


def generate_semantic_counts_md(results: Dict, mode: str) -> str:
    """Absolute semantic counts per cell, with the target size.

    Rates alone stop being informative once recall saturates: a precision of 0.50 could
    be five surplus constraints or five hundred. ``fp`` is the review workload — delivered
    constraints the target does not entail — and ``fn`` the authoring workload. |Cτ| is
    ``tp + fn``, so the target size needs no oracle here and the claim that exact
    equivalence is reached only on the smallest instance can be checked from the table
    rather than taken on trust.
    """
    lines = [f"## Table: Semantic tier — absolute counts ({mode.capitalize()} Mode)", "",
             "`|Cτ|` = target clauses = tp + fn. `fp` = delivered but not entailed "
             "(review workload). `fn` = entailed by the target but missing (authoring "
             "workload).", "",
             "| Method | KB | Strategy | \\|Cτ\\| | tp | fp | fn | R | P | F1 |",
             "|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|"]
    rows = 0
    for model in sorted(results):
        for strat in sorted(results[model]):
            for key, r in sorted(results[model][strat].items()):
                if not (key == mode or key.startswith(f'{mode}::')) or not r.has_strategy_eval:
                    continue
                lines.append(
                    f"| {_METHOD_LABEL.get(r.method, r.method)} | {model} | {strat} "
                    f"| {r.sem_tp + r.sem_fn} | {r.sem_tp} | {r.sem_fp} | {r.sem_fn} "
                    f"| {r.sem_recall:.4f} | {r.sem_precision:.4f} | {r.sem_f1:.4f} |")
                rows += 1
    return "\n".join(lines) if rows else ""


def generate_exact_equiv_table(results: Dict, mode: str, fmt: str) -> str:
    """Exact-equivalence attainment, folds attaining / folds scored, per KB x strategy.

    Reported even when every cell is zero — especially then. F1 answers "how close",
    and a reader has no way to turn 0.95 into "is this the model?"; this column does,
    and a column of zeros beside high F1 is the honest answer to that question.
    ``--`` marks a cell whose artefacts predate the field, which is not the same as zero.
    """
    title = ("Exact equivalence of the delivered theory (folds attaining / scored); "
             "`--` = not measured, `0/n` = measured and none attained")
    cell = lambda r: (f"{r.exact_equiv_attained}/{r.exact_equiv_scored}"
                      if r.exact_equiv_scored else "--")
    if fmt == 'md':
        return _compact_grid_md(f"Table: {title}", results, mode, cell)
    return _compact_grid_latex(title, "exact_equiv", results, mode, cell)


def generate_semantic_prf_table(results: Dict, mode: str, fmt: str) -> str:
    """Recall / precision / F1 for the semantic tier — the second table of the pair.

    Recall leads. The semantic precision denominator is not comparable between methods
    that deliver named constraints and methods that deliver single clauses, because the
    comparator expands a constraint into its clauses; recall is comparable throughout.
    """
    title = "Semantic tier on Intersected KB — R/P/F1"
    cell = lambda r: (
        f"{r.sem_recall:.2f}/{r.sem_precision:.2f}/{r.sem_f1:.2f}"
        if r.has_strategy_eval else "-"
    )
    if fmt == 'md':
        return _compact_grid_md(f"Table: {title}", results, mode, cell)
    return _compact_grid_latex(title, "semantic_prf", results, mode, cell)


# =============================================================================
# Table Generators — Detail tables (KB × Strategy rows)
# =============================================================================

def generate_performance_table(results: Dict, mode: str, fmt: str) -> str:
    """Performance metrics detail table."""
    if fmt == 'md':
        lines = [f"## Table: Performance Metrics ({mode.capitalize()})", "",
                 "| KB | Strategy | Runtime (ms) | #Checks | Memory (MB) | n_bias | n_mss | n_kb |",
                 "|:---|:---|---:|---:|---:|---:|---:|---:|"]
        for kb in KB_NAMES:
            for s in STRATEGIES:
                r = _get_result(results, kb, s, mode)
                if not r:
                    continue
                lines.append(
                    f"| {kb} | {STRATEGY_NAMES[s]} |"
                    f" {r.runtime_mean_ms:.2f} ± {r.runtime_std_ms:.2f} |"
                    f" {r.checks_mean:.0f} ± {r.checks_std:.0f} |"
                    f" {r.memory_max_mb:.2f} | {r.n_bias} |"
                    f" {r.n_mss_mean:.1f} | {r.n_kb_mean:.1f} |")
        return "\n".join(lines)

    # LaTeX
    body = []
    for kb in KB_NAMES:
        first_row = True
        for s in STRATEGIES:
            r = _get_result(results, kb, s, mode)
            if not r:
                continue
            kb_col = kb if first_row else ""
            body.append(
                f"{kb_col} & {STRATEGY_NAMES[s]} &"
                f" {r.runtime_mean_ms:.2f} $\\pm$ {r.runtime_std_ms:.2f} &"
                f" {r.checks_mean:.0f} $\\pm$ {r.checks_std:.0f} &"
                f" {r.memory_max_mb:.2f} & {r.n_bias} &"
                f" {r.n_mss_mean:.1f} & {r.n_kb_mean:.1f} \\\\")
            first_row = False
        if not first_row:
            body.append("\\midrule")
    if body and body[-1] == "\\midrule":
        body.pop()
    return _latex_wrap("Performance Metrics", "performance", "llrrrrrr",
                       "KB & Strategy & Runtime (ms) & \\#Checks & Memory (MB) & $|B|$ & $|MSS|$ & $|KB|$ \\\\",
                       body, mode)


def generate_kb_summary(results: Dict, mode: str, fmt: str) -> str:
    """KB summary table (bias/kb/intersected/reduction)."""
    def _reduction(r):
        return (1 - r.n_kb_mean / r.n_bias) * 100 if r.n_bias > 0 else 0

    if fmt == 'md':
        lines = [f"## Table: KB Summary ({mode.capitalize()})", "",
                 "| KB | Strategy | n_bias | n_kb (mean) | n_intersected | Reduction |",
                 "|:---|:---|---:|---:|---:|---:|"]
        for kb in KB_NAMES:
            for s in STRATEGIES:
                r = _get_result(results, kb, s, mode)
                if not r:
                    continue
                lines.append(
                    f"| {kb} | {STRATEGY_NAMES[s]} |"
                    f" {r.n_bias} | {r.n_kb_mean:.1f} |"
                    f" {r.n_intersected} | {_reduction(r):.1f}% |")
        return "\n".join(lines)

    # LaTeX
    body = []
    for kb in KB_NAMES:
        first_row = True
        for s in STRATEGIES:
            r = _get_result(results, kb, s, mode)
            if not r:
                continue
            kb_col = kb if first_row else ""
            body.append(
                f"{kb_col} & {STRATEGY_NAMES[s]} &"
                f" {r.n_bias} & {r.n_kb_mean:.1f} &"
                f" {r.n_intersected} & {_reduction(r):.1f}\\% \\\\")
            first_row = False
        if not first_row:
            body.append("\\midrule")
    if body and body[-1] == "\\midrule":
        body.pop()
    return _latex_wrap("KB Summary", "kb_summary", "llrrrr",
                       "KB & Strategy & $|B|$ & $|KB|$ (mean) & $|KB_{\\cap}|$ & Reduction \\\\",
                       body, mode)


def generate_incremental_comparison(results: Dict, fmt: str) -> str:
    """Incremental vs Non-Incremental comparison table."""
    if fmt == 'md':
        lines = ["## Table: Incremental vs Non-Incremental Comparison", "",
                 "| KB | Strategy | Mode | Accuracy | Runtime (ms) | #Checks |",
                 "|:---|:---|:---|---:|---:|---:|"]
        for kb in KB_NAMES:
            for s in STRATEGIES:
                for mode in ['incremental', 'non-incremental']:
                    r = _get_result(results, kb, s, mode)
                    if not r:
                        continue
                    ms = 'Inc' if mode == 'incremental' else 'Non-Inc'
                    lines.append(
                        f"| {kb} | {STRATEGY_NAMES[s]} | {ms} |"
                        f" {r.mean_accuracy:.4f} | {r.runtime_mean_ms:.2f} |"
                        f" {r.checks_mean:.0f} |")
        return "\n".join(lines)

    # LaTeX
    body = []
    for kb in KB_NAMES:
        first_kb = True
        for s in STRATEGIES:
            first_s = True
            for mode in ['incremental', 'non-incremental']:
                r = _get_result(results, kb, s, mode)
                if not r:
                    continue
                kb_col = kb if first_kb else ""
                s_col = STRATEGY_NAMES[s] if first_s else ""
                ms = 'Inc' if mode == 'incremental' else 'Non-Inc'
                body.append(
                    f"{kb_col} & {s_col} & {ms} &"
                    f" {r.mean_accuracy:.4f} & {r.runtime_mean_ms:.2f} &"
                    f" {r.checks_mean:.0f} \\\\")
                first_kb = False
                first_s = False
        body.append("\\midrule")
    if body and body[-1] == "\\midrule":
        body.pop()
    return _latex_wrap("Incremental vs Non-Incremental Comparison", "inc_vs_noninc",
                       "lllrrr",
                       "KB & Strategy & Mode & Accuracy & Runtime (ms) & \\#Checks \\\\",
                       body)


# =============================================================================
# Paper Tables (Tables 7, 9, 10, 11)
# =============================================================================

def generate_table7(results: Dict, mode: str, fmt: str) -> str:
    """Table 7: AcqMSS #consistency checks and runtime (msec)."""
    def _row_data(strategy):
        n_pos, n_neg = '-', '-'
        for kb in KB_NAMES:
            r = _get_result(results, kb, strategy, mode)
            if r and (r.n_positive > 0 or r.n_negative > 0):
                n_pos, n_neg = str(r.n_positive), str(r.n_negative)
                break
        cells = []
        for kb in KB_NAMES:
            r = _get_result(results, kb, strategy, mode)
            cells.append(f"{r.checks_mean:.0f} / {r.runtime_mean_ms:.1f}" if r else ABSENT)
        return n_pos, n_neg, cells

    title = "AcqMSS #consistency checks and runtime (msec)"
    if fmt == 'md':
        lines = [f"## Table 7: {title} - {mode.capitalize()} Mode", "",
                 f"| Strategy | |E+| | |E-| | {KB_HEADER_MD} |",
                 f"|:---|---:|---:|{KB_SEP_MD}|"]
        for s in STRATEGIES:
            np, nn, cells = _row_data(s)
            lines.append(f"| {STRATEGY_NAMES[s]} | {np} | {nn} | " + " | ".join(cells) + " |")
        return "\n".join(lines)

    # LaTeX
    body = []
    for s in STRATEGIES:
        np, nn, cells = _row_data(s)
        body.append(f"{STRATEGY_NAMES[s]} & {np} & {nn} & " + " & ".join(cells) + " \\\\")
    return _latex_wrap(f"AcqMSS \\#consistency checks and runtime (msec) - {mode.capitalize()}",
                       f"table7_{mode}", "lrr" + KB_COLS,
                       f"Strategy & $|E^+|$ & $|E^-|$ & {KB_HEADER_TEX} \\\\",
                       body)


def generate_table9(results: Dict, mode: str, fmt: str) -> str:
    """Table 9: Accuracy with Random Sampling (RS)."""
    rs = ['rs_1n', 'rs_2n', 'rs_3n', 'rs_m']
    title = "Accuracy with Random Sampling (RS)"

    if fmt == 'md':
        lines = [f"## Table 9: {title} - {mode.capitalize()} Mode", "",
                 f"| Strategy | {KB_HEADER_MD} |",
                 f"|:---|{KB_SEP_MD}|"]
        for s in rs:
            row = f"| {STRATEGY_NAMES[s]} |"
            for kb in KB_NAMES:
                r = _get_result(results, kb, s, mode)
                row += f" {r.mean_accuracy:.4f} ± {r.std_accuracy:.4f} |" if r else f" {ABSENT} |"
            lines.append(row)
        return "\n".join(lines)

    # LaTeX
    body = []
    for s in rs:
        row = STRATEGY_NAMES[s]
        for kb in KB_NAMES:
            r = _get_result(results, kb, s, mode)
            row += f" & {r.mean_accuracy:.4f} $\\pm$ {r.std_accuracy:.4f}" if r else f" & {ABSENT}"
        body.append(row + " \\\\")
    return _latex_wrap(f"{title} - {mode.capitalize()}", f"table9_{mode}",
                       "l" + KB_COLS, f"Strategy & {KB_HEADER_TEX} \\\\", body)


def generate_single_strategy_table(
    results: Dict, mode: str, fmt: str, strategy: str, table_num: int, title: str
) -> str:
    """Tables 10/11: single-strategy accuracy table (2-COV or FF)."""
    if fmt == 'md':
        lines = [f"## Table {table_num}: {title} - {mode.capitalize()} Mode", "",
                 "| KB | Accuracy |", "|:---|:---:|"]
        for kb in KB_NAMES:
            r = _get_result(results, kb, strategy, mode)
            if r:
                lines.append(f"| {kb} | {r.mean_accuracy:.4f} ± {r.std_accuracy:.4f} |")
            else:
                lines.append(f"| {kb} | - |")
        return "\n".join(lines)

    # LaTeX
    body = []
    for kb in KB_NAMES:
        r = _get_result(results, kb, strategy, mode)
        if r:
            body.append(f"{kb} & {r.mean_accuracy:.4f} $\\pm$ {r.std_accuracy:.4f} \\\\")
        else:
            body.append(f"{kb} & - \\\\")
    return _latex_wrap(f"{title} - {mode.capitalize()}", f"table{table_num}_{mode}",
                       "lc", "KB & Accuracy \\\\", body)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = build_parser(
        description='Extract evaluation results and generate tables',
        config='optional',
        verbose=False,
        epilog='Usage: PYTHONPATH=. python apps/extract_results.py apps/conf/extract_results_config.toml'
    )
    parser.add_argument('--results-dir', type=str, default=None,
                        help='Directory containing CV result JSON files')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory to save generated tables')
    parser.add_argument('--mode', type=str, choices=['incremental', 'non-incremental', 'both'],
                        default=None, help='Solver mode to include in tables')
    args = parser.parse_args()

    setup_logging()

    # Load defaults from TOML config if provided
    toml_config = {}
    if args.config and Path(args.config).exists():
        toml_config = load_config(args.config)

    general = toml_config.get('general', {})
    results_dir = Path(args.results_dir or general.get('results_dir', 'data/results'))
    output_dir = Path(args.output_dir or general.get('output_dir', 'paper/tables'))
    output_dir.mkdir(parents=True, exist_ok=True)

    mode = args.mode or general.get('mode', 'both')

    logger.info("Loading results from: %s", results_dir)
    results = load_all_results(results_dir)
    # Refuse to render nothing. An empty load prints a full set of tables with '-' in
    # every cell, which is indistinguishable from a genuine table of missing cells and
    # has already shipped once that way. Fail where the cause is visible.
    if not results:
        logger.error(
            "no CV results under %s — nothing to tabulate. The sweep writes "
            "<results>/<algorithm>/*_cv_*.json; this searches that level and the flat "
            "one, so an empty match means the path is wrong or the runs are elsewhere.",
            results_dir)
        return 1

    # Summary
    logger.info("Loaded results:")
    for model in sorted(results.keys()):
        strats = sorted(results[model].keys())
        modes = set()
        for s in strats:
            modes.update(results[model][s].keys())
        logger.info("  %s: %d strategies, modes: %s", model, len(strats), sorted(modes))

    logger.info("Generating tables to: %s", output_dir)
    modes_to_gen = ['incremental', 'non-incremental'] if mode == 'both' else [mode]

    # Rendered from KB_MAPPING, not written out again. This line was a third copy of
    # the same fact and it kept saying KB3=arcade after the mapping was corrected --
    # a header that describes the tables it sits above, and disagrees with them.
    kb_legend = "KB Mapping: " + ", ".join(
        f"{label}={model}" for model, label in KB_MAPPING.items())
    marker_legend = (f"Cell markers: `{ABSENT}` = this (knowledge base, sampling) "
                     f"combination was not run; `{UNSCORED}` = the run exists but this "
                     f"strategy tier was not scored. Neither is a measured zero.")
    md_content = [
        "# Evaluation Results\n",
        f"Generated from: {results_dir}\n",
        f"{kb_legend}\n",
        f"{marker_legend}\n",
    ]
    latex_content = [
        "% Evaluation Results",
        f"% {kb_legend}",
        f"% {marker_legend}",
        "\\usepackage{booktabs}", "",
    ]

    for mode in modes_to_gen:
        # Paper Tables
        md_content.append(f"\n# Paper Tables ({mode.capitalize()})")
        for gen in [
            generate_table7,
            generate_table9,
            lambda r, m, f: generate_single_strategy_table(r, m, f, '2cov', 10, 'Accuracy with 2-COV'),
            lambda r, m, f: generate_single_strategy_table(r, m, f, 'ff', 11, 'Accuracy with FF'),
        ]:
            md_content.append("\n" + gen(results, mode, 'md'))
            latex_content.append("\n" + gen(results, mode, 'latex'))

        # Additional Tables
        md_content.append(f"\n# Additional Tables ({mode.capitalize()})")
        md_content.append("\n" + generate_fold_metrics_table(results, mode, 'md'))
        latex_content.append("\n" + generate_fold_metrics_table(results, mode, 'latex'))
        md_content.append("\n" + generate_accuracy_compact(results, mode))
        md_content.append("\n" + generate_accuracy_table(results, mode, 'md'))
        latex_content.append("\n" + generate_accuracy_table(results, mode, 'latex'))
        md_content.append("\n" + generate_runtime_compact(results, mode))
        md_content.append("\n" + generate_checks_compact(results, mode))
        md_content.append("\n" + generate_performance_table(results, mode, 'md'))
        latex_content.append("\n" + generate_performance_table(results, mode, 'latex'))
        md_content.append("\n" + generate_kb_summary(results, mode, 'md'))
        latex_content.append("\n" + generate_kb_summary(results, mode, 'latex'))

        # Strategy evaluation tables (only if any result has eval data)
        has_eval = any(
            r.has_strategy_eval
            for model_strats in results.values()
            for strat_modes in model_strats.values()
            for r in strat_modes.values()
            if r.mode == mode
        )
        if has_eval:
            md_content.append(f"\n# Strategy Evaluation ({mode.capitalize()})")
            # The pair A5 settled on, per METHOD: ConGen and the two QuAcq query modes
            # are separate conditions, and the ConGen-versus-QuAcq contrast is what makes
            # the equivalence column informative rather than decorative.
            for meth in methods_present(results, mode):
                slice_ = select_method(results, mode, meth)
                label = _METHOD_LABEL.get(meth, meth)
                for gen in (generate_three_tier_f1_table, generate_semantic_prf_table,
                            generate_exact_equiv_table):
                    md_content.append(f"\n### {label}\n"
                                      + gen(slice_, mode, 'md'))
                    latex_content.append("\n" + gen(slice_, mode, 'latex'))
            base_md = generate_trivial_baseline_md(results, mode)
            if base_md:
                md_content.append("\n" + base_md)
            agree_md = generate_fold_agreement_md(results, mode)
            if agree_md:
                md_content.append("\n" + agree_md)
            counts_md = generate_semantic_counts_md(results, mode)
            if counts_md:
                md_content.append("\n" + counts_md)
            folds_md = generate_semantic_folds_md(results, mode)
            if folds_md:
                md_content.append("\n" + folds_md)
            for eval_strat in ['description', 'clause', 'semantic']:
                md_content.append("\n" + generate_strategy_eval_table(results, mode, 'md', eval_strat))
                latex_content.append("\n" + generate_strategy_eval_table(results, mode, 'latex', eval_strat))

    if mode == 'both':
        md_content.append("\n" + generate_incremental_comparison(results, 'md'))
        latex_content.append("\n" + generate_incremental_comparison(results, 'latex'))

    md_file = output_dir / "results_tables.md"
    write_text_atomic(md_file, "\n".join(md_content))
    logger.info("  Markdown tables: %s", md_file)

    latex_file = output_dir / "results_tables.tex"
    write_text_atomic(latex_file, "\n".join(latex_content))
    logger.info("  LaTeX tables: %s", latex_file)

    logger.info("Done!")


if __name__ == '__main__':
    # Propagate the status. main() returns non-zero when it refuses to tabulate an
    # empty load; dropping that made the refusal invisible to any caller that checks
    # an exit code, which is the same silent-success shape as rendering a table of
    # dashes.
    sys.exit(main() or 0)

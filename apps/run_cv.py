#!/usr/bin/env python
"""
Unified n-fold cross-validation for ConGen and Interactive algorithms.

Runs CV, saves fold KBs + intersected KB. No comparison/enrichment
(use run_compare.py for that).

Usage:
    python -m apps.run_cv apps/conf/run_cv_config.toml -v
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from conacq.atomic_io import write_json_atomic
from apps._harness import build_parser, setup_logging

from conacq.eval.cv_partials import load_partials, write_partial
from conacq.eval import (
    n_fold_cross_validation,
    n_fold_cross_validation_interactive,
    generate_cv_report,
    generate_unified_cv_dict,
    load_folds,
)
from conacq.config import load_pipeline_config, parse_models
from conacq.examples import ExampleIO
from conacq.bias import BiasIO

logger = logging.getLogger(__name__)


def get_solver_modes(mode_config: str) -> List[bool]:
    """Get list of solver modes (is_incremental values)."""
    if mode_config == 'all':
        return [True, False]
    elif mode_config == 'incremental':
        return [True]
    elif mode_config == 'non-incremental':
        return [False]
    return [True]


def parse_fold_indices(spec: Optional[str]) -> Optional[List[int]]:
    """'0,2' -> [0, 2]; None -> None (meaning every fold)."""
    if not spec:
        return None
    try:
        return [int(part) for part in spec.split(',') if part.strip() != '']
    except ValueError:
        raise SystemExit(f"--folds expects comma-separated integers, got {spec!r}")


# The committed results, regenerated only deliberately, and read by
# tools/sosym_r1/congen_check_unit_factors.py.
COMMITTED_RESULTS_DIR = Path(__file__).resolve().parent.parent / 'data' / 'results'
ALLOW_DEFAULT_OUTPUT_ENV = 'ACQMSS_ALLOW_DEFAULT_OUTPUT'


def guard_committed_output(base_dir: Path) -> None:
    """Refuse to write into the committed results tree unless it was asked for.

    The config's default output_dir is ``data/results``, so a run that simply omits
    ``-o`` overwrites the committed results. Nothing errors and nothing looks wrong;
    the next analysis quietly reports different numbers. The check is on the
    resolved path rather than on whether ``-o`` was passed, so ``-o data/results``
    is caught too -- it is the destination that matters, not the spelling.

    A deliberate regeneration sets the environment variable once, explicitly.
    """
    if base_dir.resolve() != COMMITTED_RESULTS_DIR.resolve():
        return
    if os.environ.get(ALLOW_DEFAULT_OUTPUT_ENV) == '1':
        logger.warning("writing into the committed results tree at %s (%s=1)",
                       COMMITTED_RESULTS_DIR, ALLOW_DEFAULT_OUTPUT_ENV)
        return
    logger.error(
        "refusing to write into %s: these are the committed results that a "
        "deliberate regeneration owns, and overwriting them is silent -- nothing "
        "fails, the next analysis just reports different numbers. Pass -o <dir> to "
        "write elsewhere, or set %s=1 if overwriting them is the intent.",
        COMMITTED_RESULTS_DIR, ALLOW_DEFAULT_OUTPUT_ENV)
    sys.exit(2)


def current_commit() -> Optional[str]:
    """HEAD sha, recorded into each partial so a merged result names the code that
    produced it. Best-effort: a missing git is not a reason to refuse to run."""
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def main():
    parser = build_parser(
        "Unified n-fold cross-validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python -m apps.run_cv apps/conf/run_cv_config.toml -v
        """
    )
    parser.add_argument('-o', '--output-dir', help='Output directory (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument(
        '--folds',
        help="Comma-separated fold indices to compute this call, e.g. '0,2'. "
             "Default: all. Folds whose partial already exists are skipped either way.")
    parser.add_argument(
        '--merge-only', action='store_true',
        help="Assemble from existing partials without computing any fold.")

    args = parser.parse_args()

    if not Path(args.config).exists():
        logger.error("Config not found: %s", args.config)
        sys.exit(1)

    config = load_pipeline_config(args.config)

    # Parse settings
    general = config.get('general', {})
    # Log level from the -v flag OR the config's `verbose`, now that config is
    # loaded (diagnostics go to stderr; the CV report stays on stdout).
    setup_logging(verbose=args.verbose or general.get('verbose', False), debug=args.debug)
    eval_config = config.get('evaluation', {})
    seed = general.get('seed', 42)
    algorithm = eval_config.get('algorithm', 'congen')
    base_dir = Path(args.output_dir or general.get('output_dir', 'data/results'))
    guard_committed_output(base_dir)
    output_dir = base_dir / algorithm
    n_folds = eval_config.get('n_folds', 5)
    solver_name = eval_config.get('solver_name', 'glucose4')
    solver_modes = get_solver_modes(eval_config.get('solver_mode', 'all'))
    shuffle_bias = eval_config.get('shuffle_bias', False)

    # Interactive-specific settings
    interactive_config = eval_config.get('interactive', {})
    max_queries = interactive_config.get('max_queries', 1000)
    query_mode = interactive_config.get('query_mode', 'example_only')
    # Operational guard, not a stopping rule. 0 or absent disables it. See
    # cross_validation.n_fold_cross_validation_interactive for why the two must not be
    # confused: max_queries is reproducible, this is not.
    timeout_s = interactive_config.get('timeout_s') or None

    models = parse_models(config)
    if not models:
        logger.error("No models specified in configuration")
        sys.exit(1)

    fold_indices = parse_fold_indices(args.folds)
    commit = current_commit()

    # Fail before loading a single example. The library raises the same refusal
    # (cross_validation.n_fold_cross_validation_interactive) — that is the guard
    # that actually holds; this one just makes it immediate and legible.
    if algorithm == 'interactive' and not shuffle_bias:
        logger.error(
            "shuffle_bias=false with algorithm=interactive: the query pool would be "
            "shuffled from OS entropy and the run would not reproduce. "
            "Set shuffle_bias = true in [evaluation].")
        sys.exit(2)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Cross-Validation (%s)", algorithm.upper())
    logger.info("=" * 60)
    logger.info("Config: %s", args.config)
    logger.info("Output: %s", output_dir)
    logger.info("Algorithm: %s", algorithm)
    logger.info("Models: %d", len(models))
    logger.info("Folds: %d", n_folds)
    logger.info("Solver modes: %s", ['inc' if m else 'non-inc' for m in solver_modes])
    logger.info("Solver: %s", solver_name)
    logger.info("Shuffle bias: %s", shuffle_bias)
    if algorithm == 'interactive':
        logger.info("Max queries: %s (stopping rule)", max_queries)
        logger.info("Query mode: %s", query_mode)
        logger.info("Wall-clock guard: %s", f"{timeout_s} s" if timeout_s else "disabled")

    success_count = 0
    deferred_count = 0

    for model_config in models:
        deferred = False
        logger.info("%s", "=" * 60)
        logger.info("Model: %s", model_config.name)
        logger.info("%s", "=" * 60)

        try:
            # Load examples
            if not model_config.examples:
                logger.warning("No examples for %s, skipping", model_config.name)
                continue

            examples = ExampleIO.load_json(model_config.examples)
            pos = [e.assignments for e in examples.positive]
            neg = [e.assignments for e in examples.negative]

            logger.debug("  Oracle: %s", model_config.oracle)
            logger.debug("  Bias: %s", model_config.bias)
            logger.debug("  Examples: %s", model_config.examples)
            logger.debug("  E+: %d, E-: %d", len(pos), len(neg))

            # Load bias once per model (for description resolution and interactive)
            bias = BiasIO.load_from_json(model_config.bias)

            # Load pre-generated folds if available
            fold_data = None
            actual_n_folds = n_folds
            if model_config.folds_path and Path(model_config.folds_path).exists():
                fold_data = load_folds(model_config.folds_path)
                actual_n_folds = fold_data.n_folds
                logger.debug("  Folds: %s (%d folds)", model_config.folds_path, actual_n_folds)
            elif model_config.folds_path:
                logger.warning("folds_path not found: %s", model_config.folds_path)

            for is_incremental in solver_modes:
                mode_name = "incremental" if is_incremental else "non-incremental"
                logger.info("--- Mode: %s ---", mode_name.upper())

                # Resume: folds already on disk are not recomputed. Each fold that
                # finishes here is written before the next one starts, so a window
                # that closes mid-run costs at most the fold that was running.
                partial_dir = output_dir / 'partials'
                qm = query_mode if algorithm == 'interactive' else None
                done_folds = load_partials(partial_dir, model_config.name, mode_name,
                                           algorithm, actual_n_folds, qm)
                requested = (list(range(actual_n_folds)) if fold_indices is None
                             else fold_indices)
                todo = [] if args.merge_only else [i for i in requested
                                                   if i not in done_folds]
                logger.info("  Folds: %d done, computing %s%s",
                            len(done_folds), todo or 'none',
                            ' (--merge-only)' if args.merge_only else '')

                def on_fold(fold_result, _mode=mode_name, _qm=qm,
                            _name=model_config.name, _n=actual_n_folds):
                    write_partial(partial_dir, _name, _mode, algorithm, _n,
                                  fold_result, query_mode=_qm, commit=commit)

                if algorithm == 'congen':
                    cv_result = n_fold_cross_validation(
                        positive_examples=pos,
                        negative_examples=neg,
                        n_folds=actual_n_folds,
                        bias_path=model_config.bias,
                        fm_path=model_config.oracle,
                        seed=seed,
                        solver_name=solver_name,
                        use_incremental=is_incremental,
                        fold_data=fold_data,
                        shuffle_bias=shuffle_bias,
                        fold_indices=todo, on_fold=on_fold, done_folds=done_folds
                    )
                elif algorithm == 'interactive':
                    cv_result = n_fold_cross_validation_interactive(
                        positive_examples=pos,
                        negative_examples=neg,
                        n_folds=actual_n_folds,
                        fm_path=model_config.oracle,
                        bias_path=model_config.bias,
                        seed=seed,
                        solver_name=solver_name,
                        max_queries=max_queries,
                        query_mode=query_mode,
                        timeout_s=timeout_s,
                        use_incremental=is_incremental,
                        fold_data=fold_data,
                        shuffle_bias=shuffle_bias,
                        fold_indices=todo, on_fold=on_fold, done_folds=done_folds
                    )
                else:
                    logger.error("Unknown algorithm: %s", algorithm)
                    continue

                if cv_result is None:
                    # Folds outstanding: this window did what it could and the
                    # partials are on disk. Not an error — the next call resumes.
                    deferred = True
                    logger.info("  Partial: merge deferred until every fold exists")
                    continue

                # The CV report is this command's product — keep it on stdout.
                cv_report = generate_cv_report(cv_result)
                print(cv_report)

                # Save unified CV JSON (with descriptions and eval placeholders)
                unified = generate_unified_cv_dict(cv_result, bias)
                # Include query_mode in filename for interactive to avoid overwrites
                if algorithm == 'interactive':
                    cv_file = output_dir / f"{model_config.name}_cv_{mode_name}_{query_mode}.json"
                else:
                    cv_file = output_dir / f"{model_config.name}_cv_{mode_name}.json"
                write_json_atomic(cv_file, unified)
                logger.info("  Unified CV: %s", cv_file)
                logger.info("  Intersected KB: %d constraints", len(cv_result.intersected_kb))

            if deferred:
                deferred_count += 1
            else:
                success_count += 1

        except Exception:
            logger.exception("Error evaluating %s", model_config.name)

    failed = len(models) - success_count - deferred_count
    logger.info("%s", "=" * 60)
    logger.info("Completed: %d/%d models (deferred: %d, failed: %d)",
                success_count, len(models), deferred_count, failed)
    logger.info("%s", "=" * 60)

    # A deferred model is a window that ran out, not a failure: its folds are on
    # disk and the next call resumes them. Only a real error is a non-zero exit,
    # so a sweep runner can tell "out of time" from "broken".
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()

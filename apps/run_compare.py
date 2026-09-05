#!/usr/bin/env python
"""
Compare learned KB(s) against ground truth feature model.

Config mode reads unified CV JSON files, compares each fold + intersected KB,
writes evaluation and summary back into the same file (idempotent).

CLI mode compares standalone KB files and saves separate eval JSONs.

-o/--output-dir applies to CLI mode ONLY. Config mode ignores it and writes to
the file named by kb_dir, so -o cannot redirect the output away from the input.
The way to score without touching the source tree is to copy the CV files
elsewhere and point kb_dir at the copies -- see make_score_configs.py --cv-dir.
Worth knowing because a run that re-scores in place leaves the old numbers
unreproducible from the tree that produced them, and nothing marks that they
moved.

Usage:
    # Config mode (batch all models — unified CV flow)
    python -m apps.run_compare apps/conf/run_compare_config.toml -v

    # CLI mode (single model — legacy standalone KB files)
    python -m apps.run_compare --kb data/results/model_kb.json --bias path --oracle path
"""

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import List, Optional

from conacq.atomic_io import write_json_atomic
from apps._harness import setup_logging

from conacq.config import (
    find_cv_files, find_kb_files, load_pipeline_config, parse_models,
)
from conacq.eval.kb_comparator import KBComparator, ComparationStrategy
from conacq.eval.result_loader import ConGenResultData
from conacq.oracle.ground_truth import GroundTruthData
from conacq.bias import BiasIO

logger = logging.getLogger(__name__)


def get_strategies(strategy_config: str) -> List[ComparationStrategy]:
    """Parse strategy config string into list of strategies.

    Options: 'all' (all 3), 'description', 'clause', 'semantic'
    """
    if strategy_config == 'all':
        return [
            ComparationStrategy.DESCRIPTION,
            ComparationStrategy.CLAUSE,
            ComparationStrategy.SEMANTIC,
        ]
    elif strategy_config == 'description':
        return [ComparationStrategy.DESCRIPTION]
    elif strategy_config == 'clause':
        return [ComparationStrategy.CLAUSE]
    elif strategy_config == 'semantic':
        return [ComparationStrategy.SEMANTIC]
    return [ComparationStrategy.DESCRIPTION]


# ── Unified CV flow (config mode) ──────────────────────────────


def compare_entry(entry: dict, comparator: KBComparator,
                  bias, strategies: List[ComparationStrategy],
                  label: str = "") -> dict:
    """Compare a fold or intersected KB entry. Returns evaluation dict."""
    result_data = ConGenResultData.from_dict(entry)
    eval_dict = {}
    for strategy in strategies:
        com_result = comparator.compare(result_data, strategy)
        eval_dict[strategy.value] = com_result.to_enriched_dict(bias)
        m = com_result.metrics
        logger.debug("    %s%s: P=%.4f, R=%.4f, F1=%.4f",
                     label, strategy.value, m.precision, m.recall, m.f1_score)
    return eval_dict


def exact_equivalence(fold: dict, comparator: KBComparator, bias) -> Optional[bool]:
    """Is the DELIVERED theory logically equivalent to the target model?

    Delivered means Algorithm 3's KB u NE plus the background axiom — not the bias
    constraints alone, which is what the three tiers score (kb_comparator.py, where the
    same asymmetry is commented from the other side). Two objects by contract: the tiers
    measure what was LEARNED from the bias vocabulary and exclude the memorized ¬e⁻ and
    the root axiom; equivalence measures what was DELIVERED and includes them. The tiers exclude the
    memorized ¬e⁻ deliberately (they measure what was learned), so a theory can score
    below 1 on every tier and still be equivalent, and can score high on all three and
    not be.

    Returns None when the fold predates the ``ne_clauses`` field, so an old artefact
    reports "not measured" rather than silently claiming a theory it cannot reconstruct.
    """
    from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker

    if 'ne_clauses' not in fold:
        return None
    ids = [c['id'] if isinstance(c, dict) else c for c in fold.get('kb_constraints', [])]
    kb = [list(c) for cid in ids if bias.has_constraint(cid)
          for c in bias.get_clauses(cid)]
    kb += [list(c) for c in fold.get('ne_clauses', [])]
    ct = [list(c) for c in comparator.ground_truth.clauses]
    bg = [list(c) for c in fold.get('bg_clauses', [])]
    return bool(SemanticEquivalenceChecker(kb_clauses=kb, ct_clauses=ct,
                                           bg_clauses=bg).check_equivalence().is_equivalent)


def _mean_std(values: list) -> dict:
    """Compute mean and population std."""
    if not values:
        return {'mean': 0.0, 'std': 0.0}
    m = statistics.mean(values)
    s = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {'mean': round(m, 6), 'std': round(s, 6)}


def compute_summary(data: dict, strategies: List[ComparationStrategy]) -> dict:
    """Compute mean/std of P, R, F1 across folds per strategy."""
    summary = {}
    for strategy in strategies:
        key = strategy.value
        precisions, recalls, f1s = [], [], []
        for fold in data.get('folds', []):
            ev = fold.get('evaluation') or {}
            if key in ev:
                m = ev[key].get('metrics', {})
                precisions.append(m.get('precision', 0.0))
                recalls.append(m.get('recall', 0.0))
                f1s.append(m.get('f1_score', 0.0))
        summary[key] = {
            'precision': _mean_std(precisions),
            'recall': _mean_std(recalls),
            'f1_score': _mean_std(f1s),
        }
    # Attainment counts, not a mean: a rate over 3 folds is less readable than "1/3",
    # and an all-zero cell is a result to print rather than a gap to hide.
    verdicts = [f['evaluation'].get('exact_equiv') for f in data.get('folds', [])
                if isinstance(f.get('evaluation'), dict)]
    scored = [v for v in verdicts if v is not None]
    summary['exact_equiv'] = {'attained': sum(1 for v in scored if v),
                              'scored': len(scored)}
    return summary


def reject_foreign_knowledge_bases(model, cv_files) -> None:
    """Refuse to score a CV file against another model's ground truth.

    A block's ``name`` is a label; it selects nothing. ``kb_dir`` is scored in full
    with THIS block's oracle and bias, so pointing it at a directory scores every
    knowledge base in it against one model's ground truth — silently. The files gain
    evaluation blocks, nothing errors, and every number is wrong except the named
    model's. That happened on 2026-08-27 and corrupted 79 committed files; it was
    caught only because a log line said 78 when one knowledge base had been asked for.

    A CV file is named for the model that produced it, and the oracle is named for the
    model it describes, so a mismatch between the two is exactly the widening.
    """
    expected = Path(model.oracle).stem
    foreign = [f.name for f in cv_files if not f.name.startswith(expected + '_')]
    if foreign:
        raise SystemExit(
            f"refusing to score against the wrong ground truth: block '{model.name}' "
            f"has oracle '{expected}' but kb_dir '{model.kb_dir}' resolves to "
            f"{len(cv_files)} file(s) including {foreign[:3]}"
            f"{' and more' if len(foreign) > 3 else ''}. Point kb_dir at a single CV "
            f"file, or at a directory holding only this model's results.")


def compare_model_unified(model, strategies):
    """Compare all unified CV files for a model."""
    if not model.kb_dir:
        logger.warning("No kb_dir configured for %s", model.name)
        return 0
    kb_path = Path(model.kb_dir)
    if not kb_path.exists():
        logger.warning("kb_dir not found: %s", model.kb_dir)
        return 0

    cv_files = find_cv_files(kb_path)
    if not cv_files:
        logger.warning("No CV files found in %s", model.kb_dir)
        return 0

    reject_foreign_knowledge_bases(model, cv_files)

    bias = BiasIO.load_from_json(model.bias)
    oracle = GroundTruthData.from_uvl(Path(model.oracle))
    comparator = KBComparator(oracle, bias)

    count = 0
    for cv_file in cv_files:
        logger.info("%s", cv_file.name)
        with open(cv_file) as f:
            data = json.load(f)

        # Compare each fold
        for fold in data.get('folds', []):
            label = f"Fold {fold.get('fold_index', '?')}: "
            fold['evaluation'] = compare_entry(
                fold, comparator, bias, strategies, label)
            fold['evaluation']['exact_equiv'] = exact_equivalence(fold, comparator, bias)

        # Compare intersected KB
        ik = data.get('intersected_kb', {})
        if ik and ik.get('kb_constraints'):
            ik['evaluation'] = compare_entry(
                ik, comparator, bias, strategies, "Intersected: ")

        # Compute summary
        data['summary'] = compute_summary(data, strategies)
        for key, vals in data['summary'].items():
            # summary carries the per-tier P/R/F1 blocks AND the exact-equivalence
            # counts, which have a different shape. Select by shape, not by name, so a
            # future non-tier entry does not crash the log line.
            if 'precision' not in vals:
                continue
            p, r, f1 = vals['precision'], vals['recall'], vals['f1_score']
            logger.debug("    Summary(%s): "
                         "P=%.4f+/-%.4f, R=%.4f+/-%.4f, F1=%.4f+/-%.4f",
                         key, p['mean'], p['std'], r['mean'], r['std'],
                         f1['mean'], f1['std'])

        # Write back (idempotent)
        write_json_atomic(cv_file, data)
        count += 1

    return count


def run_config_mode(config_path: str, verbose: bool, output_dir_override: str = None):
    """Run in config mode: batch compare unified CV files."""
    config = load_pipeline_config(config_path)
    general = config.get('general', {})
    setup_logging(verbose=verbose or general.get('verbose', False))

    models = parse_models(config)
    if not models:
        logger.error("No models specified in configuration")
        sys.exit(1)

    compare_config = config.get('compare', {})
    strategy_str = compare_config.get('strategy', 'all')
    strategies = get_strategies(strategy_str)

    logger.info("=" * 60)
    logger.info("KB Comparison (unified CV mode)")
    logger.info("=" * 60)
    logger.info("Config: %s", config_path)
    logger.info("Models: %d", len(models))
    logger.info("Strategies: %s", [s.value for s in strategies])

    total = 0
    for model in models:
        logger.info("--- %s ---", model.name)
        total += compare_model_unified(model, strategies)

    logger.info("Done. Compared %d unified CV files across %d models.",
                total, len(models))


# ── CLI mode (legacy standalone KB files) ──────────────────────


def compare_kb(kb_path: Path, comparator: KBComparator,
               strategies: List[ComparationStrategy],
               output_dir: Path) -> dict:
    """Compare a single standalone KB file against ground truth."""
    # REFUSE a cross-validation file rather than scoring it as empty.
    #
    # This path reads the standalone schema, whose constraints are `kb_constraints` at
    # the top level. A CV file keeps them inside `folds[]`, one knowledge base per fold.
    # Handed one, this used to find neither, score an empty knowledge base, and write
    # n_kb 0 with precision and recall 0.0 for every strategy -- exiting 0, logging
    # "Done.", warning about nothing. A reviewer following the artifact's README saw
    # that and would have concluded the method learns nothing.
    #
    # Measured across data/: 214 files carry `kb_constraints` at the root and are scored
    # correctly here; 274 are CV files that reach this only by mistake. A run that
    # produces a correct answer necessarily has the key, so this can only add a failure
    # -- it cannot change any output that was already right.
    #
    # The check belongs HERE and not in ConGenResultData.from_json, which is a loader
    # that several tests require to parse every recorded result without raising
    # (tests/test_t9_metrics_safety_net.py:171, "must not raise"). Refusing at the loader
    # would forbid reading a CV file at all; refusing at this entry point rejects only
    # the combination that cannot work.
    raw = json.loads(kb_path.read_text())
    if isinstance(raw, dict) and 'kb_constraints' not in raw:
        logger.error("%s has no 'kb_constraints' at the top level.", kb_path)
        if 'folds' in raw:
            logger.error(
                "It is a cross-validation file: the learned constraints are inside "
                "folds[], one knowledge base per fold, and --kb reads the standalone "
                "schema. Scoring it here would report n_kb 0 and F1 0.0 for every "
                "strategy -- an artefact of the wrong entry point, not a result.")
            # make_score_configs writes score_<algorithm>.toml and takes the algorithm
            # from the DIRECTORY the CV file sits in, so what can be suggested depends
            # on where the file already is.
            #
            # The precondition is stated first and the commands are written for where
            # the file has to end up -- not for where it is now with a "move it first"
            # appended. That earlier shape failed the one job a message like this has:
            # a reader who did exactly as told still got "no CV files matched", because
            # the printed paths pointed at the old location.
            algorithm = kb_path.parent.name
            if algorithm in ('congen', 'interactive'):
                logger.error(
                    "Use config mode, with kb_dir naming this file:\n"
                    "    python3 tools/sosym_r1/make_score_configs.py "
                    "--cv-dir %s --out scratch\n"
                    "    python3 -m apps.run_compare scratch/score_%s.toml",
                    kb_path.parent, algorithm)
            else:
                dest = kb_path.parent / 'congen'
                logger.error(
                    "make_score_configs selects by directory name, so this file must "
                    "sit in one called 'congen' or 'interactive'. It is in %r. These "
                    "four run as they stand:\n"
                    "    mkdir -p %s\n"
                    "    mv %s %s/\n"
                    "    python3 tools/sosym_r1/make_score_configs.py "
                    "--cv-dir %s --out scratch\n"
                    "    python3 -m apps.run_compare scratch/score_congen.toml",
                    algorithm, dest, kb_path, dest, dest)
        else:
            logger.error(
                "--kb expects a standalone result file. This one carries neither "
                "'kb_constraints' nor 'folds', so there is nothing here to score.")
        sys.exit(1)

    result_data = ConGenResultData.from_json(kb_path)

    eval_result = {}
    for strategy in strategies:
        com_result = comparator.compare(result_data, strategy)
        eval_result[strategy.value] = com_result.to_dict()
        m = com_result.metrics
        logger.debug("  %s: P=%.4f, R=%.4f, F1=%.4f",
                     strategy.value, m.precision, m.recall, m.f1_score)

    eval_file = output_dir / f"{kb_path.stem}_eval.json"
    eval_data = {
        'source_kb': str(kb_path),
        'n_kb': result_data.n_kb,
        'evaluation': eval_result,
    }
    write_json_atomic(eval_file, eval_data)

    return eval_result


def run_cli_mode(args):
    """Run in CLI mode: single model comparison (standalone KB files)."""
    setup_logging(verbose=args.verbose)

    kb_path = Path(args.kb)
    if not kb_path.exists():
        logger.error("KB path not found: %s", args.kb)
        sys.exit(1)

    kb_files = find_kb_files(kb_path)
    if not kb_files:
        logger.error("No KB files found at: %s", args.kb)
        sys.exit(1)

    bias = BiasIO.load_from_json(args.bias)
    oracle = GroundTruthData.from_uvl(Path(args.oracle))
    comparator = KBComparator(oracle, bias)
    strategies = get_strategies(args.strategy)

    output_dir = Path(args.output_dir) if args.output_dir else (
        kb_path if kb_path.is_dir() else kb_path.parent
    )

    logger.info("=" * 60)
    logger.info("KB Comparison (CLI mode)")
    logger.info("=" * 60)
    logger.info("KB files: %d", len(kb_files))
    logger.info("Strategies: %s", [s.value for s in strategies])
    logger.info("Output: %s", output_dir)

    for kb_file in kb_files:
        logger.info("--- %s ---", kb_file.name)
        compare_kb(kb_file, comparator, strategies, output_dir)

    logger.info("Done. Eval files saved to %s", output_dir)


# ── Main ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Compare learned KB(s) against ground truth FM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    # Config mode (unified CV files)
    python -m apps.run_compare apps/conf/run_compare_config.toml -v

    # CLI mode (standalone KB files)
    python -m apps.run_compare --kb data/results/model_kb.json --bias path --oracle path
        """
    )
    parser.add_argument('config', nargs='?', default=None,
                        help='Path to TOML config file (config mode)')
    parser.add_argument('--kb', help='KB file or directory (CLI mode)')
    parser.add_argument('--bias', help='Path to bias JSON file (CLI mode)')
    parser.add_argument('--oracle', help='Path to feature model .uvl (CLI mode)')
    parser.add_argument('--strategy', default='all',
                        choices=['all', 'description', 'clause', 'semantic'],
                        help='Comparison strategy (default: all)')
    parser.add_argument('-o', '--output-dir', help='Output directory override')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.config and args.config.endswith('.toml'):
        if not Path(args.config).exists():
            logger.error("Config not found: %s", args.config)
            sys.exit(1)
        run_config_mode(args.config, args.verbose, args.output_dir)
    elif args.kb:
        if not args.bias or not args.oracle:
            logger.error("CLI mode requires --kb, --bias, and --oracle")
            sys.exit(1)
        run_cli_mode(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

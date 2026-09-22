#!/usr/bin/env python
"""Run the rule-learner baselines (C4) over the same folds as acquisition.

    python -m apps.run_baselines apps/conf/run_baselines_config.toml -o <scratch>

Reports predictive accuracy and semantic F1 per (learner, KB, sampling, fold). The
description tier is deliberately absent — a rule set carries no bias constraint names,
so its description F1 is ~0 by construction and printing it would be a straw man.

Degenerate cells are MARKED, never scored: an empty rule set is CNF ⊤ and accepts
everything, which is an artifact of the fold split rather than a measurement. The
reporting threshold was declared before any number existed (C4 plan).

Needs the ``baselines`` and ``baselines-cn2`` extras. All three learners are run in one
environment on purpose — splitting them across machines would draw the baselines from
two different dependency resolutions (see the committed environment freeze).
"""
import json
import logging
import sys
from pathlib import Path

from conacq.algorithms import ConGenModelBuilder
from conacq.atomic_io import write_json_atomic
from conacq.baselines.evaluation import evaluate_fold, summarise
from conacq.config import load_pipeline_config, parse_models
from conacq.eval.folds import apply_folds, load_folds
from conacq.examples import ExampleIO
from conacq.oracle import FMOracle
from conacq.oracle.ground_truth import GroundTruthData
from apps._harness import build_parser, setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = build_parser("Run rule-learner baselines over the acquisition folds")
    parser.add_argument('-o', '--output-dir', help='Output directory (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    config = load_pipeline_config(args.config)
    general = config.get('general', {})
    setup_logging(verbose=args.verbose or general.get('verbose', False), debug=args.debug)

    ev = config.get('evaluation', {})
    learner_names = ev.get('learners', ['ripper', 'cn2', 'decision_tree'])
    solver_name = ev.get('solver_name', 'glucose4')
    out_dir = Path(args.output_dir or general.get('output_dir', 'data/results')) / 'baselines'
    out_dir.mkdir(parents=True, exist_ok=True)

    from conacq.baselines.learners import LEARNERS

    models = parse_models(config)
    if not models:
        # A malformed config (e.g. a [[models]] header lost in editing) otherwise
        # produces an empty result file that looks like a completed run of nothing.
        logger.error("No models in %s — refusing to write an empty result", args.config)
        sys.exit(1)

    rows, cells = [], []
    for model_cfg in models:
        examples = ExampleIO.load_json(model_cfg.examples)
        pos = [e.assignments for e in examples.positive]
        neg = [e.assignments for e in examples.negative]
        fold_data = load_folds(model_cfg.folds_path)

        oracle = FMOracle(model_cfg.oracle, use_incremental=False)
        try:
            model = (ConGenModelBuilder.from_bias(model_cfg.bias)
                     .with_oracle_data(oracle.oracle_data).build())
            ground_truth = GroundTruthData.from_uvl(Path(model_cfg.oracle))
            bg_clauses = [list(c) for c in oracle.oracle_data.get_root_clauses()]
        finally:
            # Release the oracle's solver now rather than at GC. Every other caller in
            # the repo does this explicitly (base_runner, the CV evaluators); the
            # __del__ fallback exists but its timing is not guaranteed, and this loop
            # builds one oracle per model.
            oracle.cleanup()

        for fold_idx in range(fold_data.n_folds):
            tr_pos, tr_neg, te_pos, te_neg = apply_folds(fold_data, pos, neg, fold_idx)
            for name in learner_names:
                cell = evaluate_fold(
                    name, LEARNERS[name], tr_pos, tr_neg, te_pos, te_neg,
                    model.name_to_id, ground_truth.clauses, bg_clauses, solver_name)
                cell.extra = {'kb': model_cfg.name, 'fold': fold_idx}
                cells.append(cell)
                rows.append(cell.to_row())
                logger.info("%-24s fold%d %-14s %s", model_cfg.name, fold_idx, name,
                            cell.degenerate or
                            f"acc={cell.accuracy:.4f} sem_f1={cell.sem_f1:.4f} "
                            f"rules={cell.n_rules}")

    summary = summarise(cells)
    write_json_atomic(out_dir / 'baselines.json', {'summary': summary, 'rows': rows})
    logger.info("summary: %s", json.dumps(summary))
    logger.info("wrote %s", out_dir / 'baselines.json')


if __name__ == '__main__':
    main()

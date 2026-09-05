#!/usr/bin/env python
"""
Run ConGen constraint acquisition — just for testing

No evaluation, no CV, no enrichment. Use run_cv.py for CV
and run_compare.py for evaluation.

Usage:
    python -m apps.run_congen apps/conf/run_congen_config.toml
    python -m apps.run_congen apps/conf/run_congen_config.toml --non-incremental
"""

import argparse
import logging
import sys
from pathlib import Path

from conacq.runners import ConGenRunner
from conacq.examples import ExampleIO
from conacq.eval.report import save_kb_result
from conacq.config import ModelConfig, load_pipeline_config, parse_models
from apps._harness import build_parser, setup_logging

logger = logging.getLogger(__name__)


def extract_sampling_type(examples_path: str) -> str:
    """Extract sampling type from examples file name.

    Examples:
        REAL-FM-7_rs_1n.json -> rs_1n
        REAL-FM-7_ff.json -> ff

    Args:
        examples_path: Path to examples file

    Returns:
        Sampling type string
    """
    examples_name = Path(examples_path).stem  # e.g., REAL-FM-7_rs_1n
    # Split by underscore and take everything after the first part (model name)
    parts = examples_name.split('_')
    if len(parts) > 1:
        return '_'.join(parts[1:])  # e.g., rs_1n or ff
    return 'unknown'


def process_model(model_config: ModelConfig, output_dir: Path,
                  use_incremental: bool = True,
                  solver_name: str = 'glucose4') -> bool:
    """Process a single model with ConGen via ConGenRunner.

    Args:
        model_config: Model configuration
        output_dir: Directory to save results
        use_incremental: Use incremental solver mode
        solver_name: SAT solver name

    Returns:
        True if successful, False otherwise
    """
    runner = None
    try:
        model_name = model_config.name
        sampling_type = extract_sampling_type(model_config.examples)

        logger.debug("Processing: %s", model_name)
        logger.debug("  FM: %s", model_config.oracle)
        logger.debug("  Bias: %s", model_config.bias)
        logger.debug("  Examples: %s", model_config.examples)
        logger.debug("  Mode: %s",
                     'incremental' if use_incremental else 'non-incremental')

        # Load examples
        examples = ExampleIO.load_json(model_config.examples)
        pos = [e.assignments for e in examples.positive]
        neg = [e.assignments for e in examples.negative]

        # Run ConGen via runner
        runner = ConGenRunner(model_config.bias, model_config.oracle,
                              solver_name, use_incremental)
        result = runner.run(pos, neg)

        logger.debug("  Bias constraints: %d", result.n_bias)
        logger.debug("  E+: %d, E-: %d", len(pos), len(neg))
        logger.debug("  MSS size: %d", result.n_mss)
        logger.debug("  Acquired KB: %d constraints", result.n_kb)
        if result.kb_constraints:
            logger.debug("  Constraints:")
            for c in result.kb_constraints[:10]:
                logger.debug("    - %s", c)
            if len(result.kb_constraints) > 10:
                logger.debug("    ... and %d more", len(result.kb_constraints) - 10)

        # Save result in standard format (compatible with ConGenResultData.from_json)
        output_file = output_dir / f"{model_name}_{sampling_type}_kb.json"
        save_kb_result(
            kb_constraints=result.kb_constraints,
            redundant_constraints=result.redundant_constraints,
            n_bias=result.n_bias,
            n_mss=result.n_mss,
            n_kb=result.n_kb,
            output_path=output_file,
            bg_clauses=result.bg_clauses,
            ne_constraints=result.ne_constraints,
            n_ne=result.n_ne,
        )

        logger.debug("  Saved: %s", output_file)

        return True

    except Exception:
        logger.exception("Error processing %s", model_config.oracle)
        return False

    finally:
        if runner is not None:
            runner.cleanup()


def main():
    parser = build_parser(
        "Run ConGen constraint acquisition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        verbose_help="Verbose output (overrides config)",
        epilog="""
Example:
    python -m apps.run_congen apps/conf/run_congen_config.toml -v
    python -m apps.run_congen apps/conf/run_congen_config.toml -v --non-incremental
        """
    )
    parser.add_argument('-o', '--output-dir', help='Output directory (overrides config)')
    parser.add_argument('--non-incremental', action='store_true',
                        help='Use non-incremental solver mode')
    parser.add_argument('--solver', default='glucose4',
                        help='SAT solver name (default: glucose4)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    if not Path(args.config).exists():
        logger.error("Config not found: %s", args.config)
        sys.exit(1)

    config = load_pipeline_config(args.config)

    # Parse settings
    general = config.get('general', {})
    setup_logging(verbose=args.verbose or general.get('verbose', False),
                  debug=args.debug)
    output_dir = Path(args.output_dir or general.get('output_dir', 'data/results'))

    models = parse_models(config)

    if not models:
        logger.error("No models specified in configuration")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    use_incremental = not args.non_incremental
    mode_str = "incremental" if use_incremental else "non-incremental"

    logger.info("=" * 60)
    logger.info("ConGen Constraint Acquisition")
    logger.info("=" * 60)
    logger.info("Config: %s", args.config)
    logger.info("Output: %s", output_dir)
    logger.info("Models: %d", len(models))
    logger.info("Mode: %s", mode_str)
    logger.info("Solver: %s", args.solver)

    success_count = 0
    for model in models:
        if process_model(model, output_dir,
                         use_incremental=use_incremental, solver_name=args.solver):
            success_count += 1

    logger.info("=" * 60)
    logger.info("Completed: %d/%d models", success_count, len(models))
    logger.info("=" * 60)

    if success_count < len(models):
        sys.exit(1)


if __name__ == '__main__':
    main()

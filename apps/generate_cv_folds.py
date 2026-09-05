#!/usr/bin/env python
"""
Generate shared cross-validation folds for fair ConGen vs QuAcq comparison.

Usage:
    python -m apps.generate_cv_folds apps/conf/generate_cv_folds_config.toml
"""

import argparse
import logging
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from conacq.examples import ExampleIO
from conacq.eval.folds import generate_folds, save_folds
from apps._harness import build_parser, load_config, setup_logging

logger = logging.getLogger(__name__)


def main():
    parser = build_parser("Generate shared CV folds for evaluation", verbose=False)

    args = parser.parse_args()

    if not Path(args.config).exists():
        logger.error("Config not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)
    setup_logging()

    folds_config = config.get('folds', {})
    seed = folds_config.get('seed', 42)
    n_folds = folds_config.get('n_folds', 5)
    output_dir = Path(folds_config.get('output_dir', 'data/folds'))
    output_dir.mkdir(parents=True, exist_ok=True)

    models = config.get('models', [])
    if not models:
        logger.error("No models in config")
        sys.exit(1)

    for model in models:
        name = model.get('name', 'unknown')
        examples_path = model.get('examples')

        if not examples_path:
            logger.warning("Skipping %s: no examples path", name)
            continue

        if not Path(examples_path).exists():
            logger.warning("Skipping %s: examples file not found: %s",
                           name, examples_path)
            continue

        examples = ExampleIO.load_json(examples_path)
        n_pos = len(examples.positive)
        n_neg = len(examples.negative)

        fold_data = generate_folds(n_pos, n_neg, n_folds, seed)

        output_file = output_dir / f"{name}_folds.json"
        save_folds(fold_data, str(output_file))

        logger.info("%s: %d folds (E+=%d, E-=%d) -> %s",
                    name, n_folds, n_pos, n_neg, output_file)

    logger.info("Done.")


if __name__ == '__main__':
    main()

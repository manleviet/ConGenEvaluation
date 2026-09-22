#!/usr/bin/env python
"""
Generate test case examples from feature models.

Sampling methods (from AcqMSS paper):
- Random Sampling (RS): n, 2n, 3n, m examples (n = number of features, m = 2-COV count)
- 2-wise Coverage (2-COV): each pair of features covered
- Feature Frequency (FF): each feature appears True/False in E+/E-

Usage:
    python -m apps.generate_examples apps/conf/generate_examples_config.toml
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from conacq.oracle import FMOracle
from apps._harness import build_parser, setup_logging
from conacq.examples import (
    BalancedRandomSamplingGenerator,
    ControlledRandomSamplingGenerator,
    FeatureFrequencyGenerator,
    TwoCoverageGenerator,
    ExampleIO,
    ExampleSet,
)

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load TOML configuration file."""
    with open(config_path, 'rb') as f:
        return tomllib.load(f)


# Strategy -> example count function(n_features, m_value)
STRATEGY_COUNTS = {
    'rs_1n': lambda n, m: n,
    'rs_2n': lambda n, m: 2 * n,
    'rs_3n': lambda n, m: 3 * n,
    'rs_m': lambda n, m: m,
    '2cov': lambda n, m: None,
    'ff': lambda n, m: 10 * n,
    'balanced': lambda n, m: 2 * n,
}


def get_example_count_for_strategy(strategy: str, n_features: int, m_value: Optional[int] = None) -> Optional[int]:
    """
    Get number of examples based on strategy and feature count.

    Paper strategies: rs_1n=n, rs_2n=2n, rs_3n=3n, rs_m=m (2-COV count),
    2cov=coverage-based (None), ff=10n, balanced=2n.
    """
    if strategy not in STRATEGY_COUNTS:
        raise ValueError(f"Unknown strategy: {strategy}")
    return STRATEGY_COUNTS[strategy](n_features, m_value)


def generate_examples_for_strategy(
        oracle: FMOracle,
        strategy: str,
        n_examples: Optional[int],
        n_features: int,
        seed: int,
        valid_configs: int = None
) -> ExampleSet:
    """
    Generate examples using specified strategy.

    Args:
        oracle: Feature model oracle
        strategy: Strategy name (rs_1n, rs_2n, rs_3n, rs_m, 2cov, ff, balanced)
        n_examples: Pre-computed example count (None for coverage-based)
        n_features: Number of features
        seed: Random seed
        valid_configs: Pre-computed valid configurations count (for E+/E- distribution)

    Returns:
        Generated ExampleSet
    """
    if strategy in ('rs_1n', 'rs_2n', 'rs_3n', 'rs_m'):
        gen = ControlledRandomSamplingGenerator(oracle)
        examples = gen.generate(total=n_examples, valid_configs=valid_configs, seed=seed)
        examples.metadata['target_total'] = n_examples
    elif strategy == '2cov':
        gen = TwoCoverageGenerator(oracle)
        examples = gen.generate(seed=seed)
    elif strategy == 'ff':
        gen = FeatureFrequencyGenerator(oracle)
        examples = gen.generate(max_examples=n_examples, seed=seed)
        examples.metadata['max_examples'] = n_examples
    elif strategy == 'balanced':
        gen = BalancedRandomSamplingGenerator(oracle)
        n_each = n_features
        examples = gen.generate(n_positive=n_each, n_negative=n_each, seed=seed)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    examples.metadata['strategy'] = strategy
    return examples


def process_model(
        model_config: Dict[str, Any],
        default_strategies: List[str],
        output_dir: Path,
        seed: int
) -> bool:
    """
    Process a single feature model.

    Args:
        model_config: Model configuration dict from TOML
        default_strategies: Default strategies to use
        output_dir: Output directory
        seed: Random seed

    Returns:
        True if successful
    """
    fm_path = model_config['path']

    if not Path(fm_path).exists():
        logger.error("Feature model not found: %s", fm_path)
        return False

    model_name = Path(fm_path).stem

    try:
        # Load feature model
        logger.debug("Loading: %s", fm_path)

        oracle = FMOracle(fm_path)
        n_features = len(oracle.get_variables())

        # Use pre-computed values from config if available
        valid_configs = model_config.get('valid_configs')
        m_value = model_config.get('m')

        # Determine strategies
        strategies = model_config.get('strategies') or default_strategies

        logger.debug("  Features: %d", n_features)
        if valid_configs:
            logger.debug("  Valid configs: %s", valid_configs)
        logger.debug("  Strategies: %s", strategies)

        # Compute m value (2-COV count) if rs_m strategy is used and not provided
        if 'rs_m' in strategies and m_value is None:
            gen = TwoCoverageGenerator(oracle)
            two_cov_examples = gen.generate(seed=seed)
            m_value = len(two_cov_examples)
            logger.debug("  m value (2-COV count): %d (computed)", m_value)
        elif m_value is not None:
            logger.debug("  m value (2-COV count): %s (from config)", m_value)

        # Generate examples for each strategy
        for strategy in strategies:
            n_examples = get_example_count_for_strategy(strategy, n_features, m_value)

            if n_examples is not None:
                logger.debug("  %s (total=%s)...", strategy, n_examples)
            else:
                logger.debug("  %s (coverage-based)...", strategy)

            examples = generate_examples_for_strategy(
                oracle=oracle,
                strategy=strategy,
                n_examples=n_examples,
                n_features=n_features,
                seed=seed,
                valid_configs=valid_configs
            )

            # Add model info to metadata
            examples.metadata['model'] = model_name
            examples.metadata['fm_path'] = fm_path
            examples.metadata['n_features'] = n_features

            # Save to file
            output_file = output_dir / f"{model_name}_{strategy}.json"
            ExampleIO.save_json(examples, output_file)

            stats = examples.statistics()
            logger.debug("E+=%d, E-=%d -> %s",
                         stats['n_positive'], stats['n_negative'], output_file.name)

        return True

    except Exception:
        logger.exception("Error processing %s", fm_path)
        return False


def main():
    parser = build_parser(
        description="Generate test case examples from feature models (AcqMSS paper)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        verbose_help="Verbose output (overrides config)",
        epilog="""
Sampling Strategies (from paper):
    rs_1n     - Random Sampling with n examples (n = #features)
    rs_2n     - Random Sampling with 2n examples
    rs_3n     - Random Sampling with 3n examples
    rs_m      - Random Sampling with m examples (m = 2-COV count)
    2cov      - 2-wise Coverage (pairwise, using allpairspy)
    ff        - Feature Frequency (coverage-based)
    balanced  - Balanced RS (equal E+/E-, not in paper)

Example:
    python -m apps.generate_examples apps/conf/generate_examples_config.toml
        """
    )

    parser.add_argument(
        '-o', '--output-dir',
        help='Output directory (overrides config)'
    )

    args = parser.parse_args()

    # Load configuration
    if not Path(args.config).exists():
        logger.error("Configuration file not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)

    # Parse general settings
    general = config.get('general', {})
    setup_logging(verbose=args.verbose or general.get('verbose', False))
    seed = general.get('seed', 42)
    output_dir = Path(args.output_dir or general.get('output_dir', 'data/examples'))
    default_strategies = general.get('strategies', ['rs_1n', 'rs_2n', 'rs_3n', 'ff'])

    # Parse models
    models = config.get('models', [])

    if not models:
        logger.error("No models specified in configuration")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Example Generation (AcqMSS Paper Sampling)")
    logger.info("=" * 60)
    logger.info("Config: %s", args.config)
    logger.info("Output: %s", output_dir)
    logger.info("Seed: %s", seed)
    logger.info("Strategies: %s", default_strategies)
    logger.info("Models: %d", len(models))

    # Process each model
    success_count = 0
    for model in models:
        if process_model(
                model_config=model,
                default_strategies=default_strategies,
                output_dir=output_dir,
                seed=seed
        ):
            success_count += 1

    # Summary
    logger.info("=" * 60)
    logger.info("Completed: %d/%d models", success_count, len(models))
    logger.info("Output directory: %s", output_dir)
    logger.info("=" * 60)

    if success_count < len(models):
        sys.exit(1)


if __name__ == '__main__':
    main()

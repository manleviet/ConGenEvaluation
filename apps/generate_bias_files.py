#!/usr/bin/env python3
"""
Generate bias files from YAML configurations in batch.

This script reads a TOML configuration file containing paths to YAML bias configs,
generates bias constraints for each, and saves them to the specified output directory.

Usage:
    python apps/generate_bias_files.py apps/conf/generate_bias_files_config.toml
    python apps/generate_bias_files.py --config apps/conf/generate_bias_files_config.toml

Example TOML config:
    [settings]
    output_dir = "data/bias"
    output_format = "both"  # "json", "cnf", or "both"
    save_statistics = true
    verbose = true

    [[models]]
    config = "data/bias-config/REAL-FM-7.yaml"
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

import toml

# Set up path for imports
ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent
os.chdir(ROOT_PROJECT_FOLDER)
sys.path.insert(0, str(ROOT_PROJECT_FOLDER))

from conacq.bias import BiasConfigLoader, BiasGenerator, BiasIO
from apps._harness import setup_logging

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    config_path: str
    name: str = None  # Optional override name

    def __post_init__(self):
        if self.name is None:
            # Extract name from config path
            self.name = Path(self.config_path).stem


@dataclass
class BatchConfig:
    """Batch processing configuration from TOML."""
    output_dir: str
    output_format: str  # "json", "cnf", or "both"
    save_statistics: bool
    verbose: bool
    models: List[ModelConfig]


def load_toml_config(config_path: str) -> BatchConfig:
    """
    Load batch configuration from TOML file.

    Args:
        config_path: Path to TOML configuration file

    Returns:
        BatchConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        KeyError: If required fields are missing
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        data = toml.load(f)

    # Parse settings
    settings = data.get('settings', {})
    output_dir = settings.get('output_dir', 'data/bias')
    output_format = settings.get('output_format', 'both')
    save_statistics = settings.get('save_statistics', True)
    verbose = settings.get('verbose', True)

    # Validate output_format
    if output_format not in ['json', 'cnf', 'both']:
        raise ValueError(f"Invalid output_format: {output_format}. Must be 'json', 'cnf', or 'both'")

    # Parse models
    models = []
    for model_data in data.get('models', []):
        if 'config' not in model_data:
            raise KeyError("Each model must have a 'config' field")

        model = ModelConfig(
            config_path=model_data['config'],
            name=model_data.get('name', None)
        )
        models.append(model)

    return BatchConfig(
        output_dir=output_dir,
        output_format=output_format,
        save_statistics=save_statistics,
        verbose=verbose,
        models=models
    )


class BatchBiasGenerator:
    """Generate bias files in batch from YAML configurations."""

    def __init__(self, config: BatchConfig):
        """
        Initialize batch generator.

        Args:
            config: BatchConfig object from TOML
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_single(self, model_config: ModelConfig) -> Dict[str, Any]:
        """
        Process a single YAML config and generate bias.

        Args:
            model_config: ModelConfig for this model

        Returns:
            Dict with processing results:
                {
                    'name': str,
                    'success': bool,
                    'error': str or None,
                    'stats': dict or None,
                    'output_files': list
                }
        """
        result = {
            'name': model_config.name,
            'success': False,
            'error': None,
            'stats': None,
            'output_files': []
        }

        try:
            # 1. Load YAML config
            logger.debug("  Loading config: %s", model_config.config_path)

            yaml_config = BiasConfigLoader.load(model_config.config_path)

            # 2. Validate
            validation = BiasConfigLoader.validate_config(yaml_config)
            if not validation['valid']:
                result['error'] = f"Validation failed: {validation['errors']}"
                return result

            for warning in validation['warnings']:
                logger.warning("%s", warning)

            # 3. Generate bias
            logger.debug("  Generating bias...")

            generator = BiasGenerator(yaml_config)
            bias = generator.generate_bias()

            # 4. Get statistics
            result['stats'] = {
                'num_features': len(bias.features),
                'num_constraints': len(bias.constraints),
                'num_clauses': len(bias.to_cnf())
            }

            # 5. Save to files
            base_name = model_config.name

            if self.config.output_format in ['json', 'both']:
                json_path = self.output_dir / f"{base_name}-bias.json"
                BiasIO.save_to_json(bias, str(json_path))
                result['output_files'].append(str(json_path))
                logger.debug("  Saved: %s", json_path)

            if self.config.output_format in ['cnf', 'both']:
                cnf_path = self.output_dir / f"{base_name}-bias.cnf"
                BiasIO.save_to_cnf(bias, str(cnf_path))
                result['output_files'].append(str(cnf_path))
                logger.debug("  Saved: %s", cnf_path)

            # 6. Save statistics file
            if self.config.save_statistics:
                stats_path = self.output_dir / f"{base_name}-bias-stats.txt"
                BiasIO.save_statistics(bias, str(stats_path))
                result['output_files'].append(str(stats_path))
                logger.debug("  Saved: %s", stats_path)

            result['success'] = True

        except FileNotFoundError as e:
            result['error'] = f"File not found: {e}"
        except Exception as e:
            result['error'] = str(e)

        return result

    def process_batch(self) -> List[Dict[str, Any]]:
        """
        Process all models in batch.

        Returns:
            List of result dicts from process_single()
        """
        results = []

        logger.debug("=" * 60)
        logger.debug("Batch Bias Generation")
        logger.debug("=" * 60)
        logger.debug("Output directory: %s", self.output_dir)
        logger.debug("Output format: %s", self.config.output_format)
        logger.debug("Save statistics: %s", self.config.save_statistics)
        logger.debug("Total models: %d", len(self.config.models))

        for i, model_config in enumerate(self.config.models, 1):
            logger.debug("[%d/%d] Processing: %s",
                         i, len(self.config.models), model_config.name)

            result = self.process_single(model_config)
            results.append(result)

            if result['success']:
                stats = result['stats']
                logger.debug("  Success: %d constraints, %d features",
                             stats['num_constraints'], stats['num_features'])
            else:
                logger.debug("  Failed: %s", result['error'])

        # Log summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: List[Dict[str, Any]]):
        """Log batch processing summary (debug level)."""
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        logger.debug("=" * 60)
        logger.debug("Summary")
        logger.debug("=" * 60)
        logger.debug("Successful: %d/%d", len(successful), len(results))

        if successful:
            logger.debug("Generated files:")
            for result in successful:
                stats = result['stats']
                logger.debug("  %s:", result['name'])
                logger.debug("    Features: %d", stats['num_features'])
                logger.debug("    Constraints: %d", stats['num_constraints'])
                logger.debug("    Clauses: %d", stats['num_clauses'])
                for f in result['output_files']:
                    file_size = Path(f).stat().st_size
                    logger.debug("    -> %s (%s bytes)", f, f"{file_size:,}")

        if failed:
            logger.debug("Failed:")
            for result in failed:
                logger.debug("  %s: %s", result['name'], result['error'])


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate bias files from YAML configurations in batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example TOML config file:
    [settings]
    output_dir = "data/bias"
    output_format = "both"  # "json", "cnf", or "both"
    save_statistics = true
    verbose = true

    [[models]]
    config = "data/bias-config/REAL-FM-7.yaml"

    [[models]]
    config = "data/bias-config/arcade-game.yaml"
    name = "arcade"  # Optional: override output name
        """
    )
    parser.add_argument(
        'config',
        nargs='?',
        help='Path to TOML configuration file'
    )
    parser.add_argument(
        '--config', '-c',
        dest='config_flag',
        help='Path to TOML configuration file (alternative syntax)'
    )

    args = parser.parse_args()

    # Get config path from either positional or flag argument
    config_path = args.config or args.config_flag

    if not config_path:
        parser.error("Configuration file is required. "
                     "Use: python3 -m apps.generate_bias_files <config.toml>")

    return config_path


def main():
    """Main entry point."""
    config_path = parse_arguments()

    try:
        # Load TOML config
        batch_config = load_toml_config(config_path)
        setup_logging(verbose=batch_config.verbose)
        logger.info("Loading configuration: %s", config_path)

        # Create generator and process
        generator = BatchBiasGenerator(batch_config)
        results = generator.process_batch()

        # Exit with error code if any failed
        failed_count = sum(1 for r in results if not r['success'])
        sys.exit(failed_count)

    except FileNotFoundError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()

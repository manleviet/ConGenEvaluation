#!/usr/bin/env python3
"""
Generate YAML bias config from a feature model (.uvl).

This script reads a feature model and generates a YAML bias configuration file
that can be used with the bias generation system.

Usage:
    python generate_bias_config.py <feature_model.uvl> [output.yaml]
    python generate_bias_config.py --config config.toml

Example:
    python generate_bias_config.py data/fms/REAL-FM-7.uvl configs/REAL-FM-7.yaml
    python generate_bias_config.py --config apps/conf/bias_config.toml
"""
import os
import sys
import argparse
import logging
from argparse import Namespace
from pathlib import Path
from typing import List, Dict, Any, Optional

from conacq.atomic_io import write_text_atomic
from apps._harness import load_config as _harness_load_config, setup_logging

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore

from flamapy.metamodels.fm_metamodel.models import FeatureModel

# This is a workaround to set the root project folder as the current working directory
ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent
os.chdir(ROOT_PROJECT_FOLDER)
sys.path.insert(0, os.getcwd())

logger = logging.getLogger(__name__)

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from TOML file.

    Args:
        config_path: Path to TOML config file

    Returns:
        Dictionary with configuration values
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return _harness_load_config(config_path)


def parse_argument() -> Namespace:
    parser = argparse.ArgumentParser(
        description="Generate YAML bias config from a feature model (.uvl)"
    )
    parser.add_argument(
        "fm_path",
        nargs="?",
        help="Path to feature model file (.uvl)"
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output YAML file path (default: <output_dir>/<model_name>.yaml)"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to TOML config file"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="data/bias-config",
        help="Output directory for generated YAML files (default: data/bias-config)"
    )
    parser.add_argument(
        "--cross-tree-mode",
        choices=["all", "leaf", "extracted"],
        default="extracted",
        help="Cross-tree constraint mode: 'all' for all features, 'leaf' for leaf features only, 'extracted' for features from CTCs (default: extracted)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Load config from TOML if provided
    if args.config:
        config = load_config(args.config)

        # Apply global settings first
        if config.get('output_dir'):
            args.output_dir = config['output_dir']
        if config.get('cross_tree_mode'):
            args.cross_tree_mode = config['cross_tree_mode']
        if not args.verbose and config.get('verbose', False):
            args.verbose = True

        # Check for batch mode (list of models)
        if 'models' in config:
            args.models = config['models']
        else:
            args.models = None
            # Single model mode - apply config values (CLI args take precedence)
            if args.fm_path is None and 'fm_path' in config:
                args.fm_path = config['fm_path']
            if args.output is None and 'output' in config:
                args.output = config['output']
    else:
        args.models = None

    # Validate required arguments (only for single model mode)
    if args.models is None and args.fm_path is None:
        parser.error("fm_path is required (either as argument or in config file with 'fm_path' or 'models')")

    return args

def load_feature_model(fm_path: str):
    """
    Load feature model from UVL file.

    Args:
        fm_path: Path to .uvl file

    Returns:
        Feature model object
    """
    from flamapy.metamodels.fm_metamodel.transformations import UVLReader

    if not Path(fm_path).exists():
        raise FileNotFoundError(f"Feature model not found: {fm_path}")

    reader = UVLReader(fm_path)
    return reader.transform()

# def extract_hierarchical_candidates(fm: FeatureModel) -> List[Dict[str, Any]]:
#
#     candidates = []
#
#     def process_feature(feature):
#         relations = feature.get_relations()
#
#         for relation in relations:
#             children = [child.name for child in relation.children]
#
#             if not children:
#                 continue
#
#             # Determine relationship type based on relation properties
#             if relation.is_mandatory() or relation.is_optional():
#                 # Binary relationship: one child at a time
#                 relationship_type = "binary"
#             elif relation.is_or() or relation.is_alternative():
#                 # Group relationship: multiple children
#                 relationship_type = "group"
#             else:
#                 # Default to binary for unknown types
#                 relationship_type = "binary"
#
#             candidate = {
#                 'parent': feature.name,
#                 'children': children,
#                 'relationship_type': relationship_type
#             }
#             candidates.append(candidate)
#
#         # Process children recursively
#         for child in feature.get_children():
#             process_feature(child)
#
#     process_feature(fm.root)
#     return candidates

def extract_hierarchical_candidates(fm: FeatureModel) -> List[Dict[str, Any]]:
    """
        Extract hierarchical relationships from feature model.

        Args:
            fm: Feature model object

        Returns:
            List of hierarchical candidate dictionaries
        """
    candidates = []

    for relationship in fm.get_relations():
        parent = relationship.parent.name
        children = [child.name for child in relationship.children]

        if not children:
            continue

        # Determine relationship type based on relation properties
        if relationship.is_mandatory() or relationship.is_optional():
            # Binary relationship: one child at a time
            relationship_type = "binary"
        elif relationship.is_or() or relationship.is_alternative():
            # Group relationship: multiple children
            relationship_type = "group"
        else:
            # Default to binary for unknown types
            relationship_type = "binary"

        candidate = {
            'parent': parent,
            'children': children,
            'relationship_type': relationship_type
        }
        candidates.append(candidate)
    return candidates

def extract_cross_tree_constraints(fm) -> List[Dict[str, Any]]:
    """
    Extract cross-tree constraints from feature model.

    Args:
        fm: Feature model object

    Returns:
        List of constraint info (for reference in comments)
    """
    constraints = [
        {'text': str(ctc)}
        for ctc in fm.get_constraints()
    ]
    return constraints


def extract_cross_tree_features(fm: FeatureModel) -> List[str]:
    """
    Extract unique features from cross-tree constraints.

    Args:
        fm: Feature model object

    Returns:
        Sorted list of feature names that appear in cross-tree constraints
    """
    ctc_features = set()
    for ctc in fm.get_constraints():
        # Flamapy Constraint.get_features() returns list of feature names (strings)
        for feature_name in ctc.get_features():
            ctc_features.add(feature_name)
    return sorted(ctc_features)


def extract_leaf_features(fm: FeatureModel) -> List[str]:
    """
    Extract leaf features (features with no children).

    Args:
        fm: Feature model object

    Returns:
        List of leaf feature names
    """
    leaf_features = [
        feature.name
        for feature in fm.get_features()
        if feature.is_leaf()
    ]
    return leaf_features

def generate_yaml_content(
        name: str,
        features: List[str],
        leaf_features: List[str],
        hierarchical_candidates: List[Dict[str, Any]],
        cross_tree_constraints: List[Dict[str, Any]],
        cross_tree_mode: str = "extracted",
        cross_tree_features: List[str] = None
) -> str:
    """
    Generate YAML content for bias config.

    Args:
        name: Model name
        features: List of feature names
        leaf_features: List of leaf feature names (features with no children)
        hierarchical_candidates: List of hierarchical relationships
        cross_tree_constraints: List of cross-tree constraints (for comments)
        cross_tree_mode: Mode for cross-tree constraints ('all', 'leaf', or 'extracted')
        cross_tree_features: List of features extracted from CTCs (for 'extracted' mode)

    Returns:
        YAML content as string
    """
    lines = [f"# Bias Config for {name} Feature Model",  # Header
             f"# Auto-generated from feature model",
             "",
             f"name: {name}",  # Model name
             "",
             "# List of all features in the model", "features:"]

    # Features
    for feature in features:
        lines.append(f"  - {feature}")
    lines.append("")

    # Leaf features
    lines.append("# Leaf features (features with no children)")
    lines.append("leaf_features:")
    for feature in leaf_features:
        lines.append(f"  - {feature}")
    lines.append("")

    # Hierarchical candidates
    lines.append("# Hierarchical relationship candidates")
    lines.append("# The generator will create constraints with allowed operators based on relationship_type")
    lines.append("hierarchical_candidates:")

    for candidate in hierarchical_candidates:
        parent = candidate['parent']
        children = candidate['children']
        rel_type = candidate['relationship_type']

        if rel_type == "binary":
            lines.append(f"  # Binary relationships: will generate with mandatory and optional operators")
        else:
            lines.append(f"  # Group relationships: will generate with alternative and or operators")

        lines.append(f"  - parent: {parent}")

        # Format children as inline list
        if len(children) == 1:
            lines.append(f"    children: [{children[0]}]")
        else:
            children_str = ", ".join(children)
            lines.append(f"    children: [{children_str}]")

        lines.append(f"    relationship_type: {rel_type}")
        lines.append("")

    # Cross-tree candidates
    lines.append("# Cross-tree constraint candidates")

    if cross_tree_constraints:
        lines.append("# Original cross-tree constraints from feature model:")
        for ctc in cross_tree_constraints:
            lines.append(f"#   {ctc['text']}")
        lines.append("#")

    lines.append("# cross_tree_mode: 'all' generates requires/excludes for all feature pairs")
    lines.append("#                  'leaf' generates only between leaf features")
    lines.append("#                  'extracted' generates only between features from CTCs")
    lines.append("cross_tree_candidates:")
    lines.append(f"  cross_tree_mode: {cross_tree_mode}")

    # Output cross_tree_features for extracted mode
    if cross_tree_features:
        lines.append("  cross_tree_features:")
        for feature in cross_tree_features:
            lines.append(f"    - {feature}")

    lines.append("")

    return "\n".join(lines)


def process_model(
        fm_path: str,
        output: str = None,
        output_dir: str = "data/bias-config",
        cross_tree_mode: str = "extracted"
) -> bool:
    """
    Process a single feature model and generate bias config.

    Args:
        fm_path: Path to feature model file
        output: Output YAML file path (optional, overrides output_dir)
        output_dir: Output directory for generated YAML files
        cross_tree_mode: Mode for cross-tree constraints ('all', 'leaf', or 'extracted')

    Returns:
        True if successful, False otherwise
    """
    # Load feature model
    logger.debug("Loading feature model: %s", fm_path)

    try:
        fm = load_feature_model(fm_path)
    except FileNotFoundError as e:
        logger.error("%s", e)
        return False
    except Exception as e:
        logger.error("Error loading feature model: %s", e)
        return False

    # Extract model name from file
    model_name = Path(fm_path).stem

    logger.debug("Model name: %s", model_name)
    logger.debug("Root feature: %s", fm.root.name)

    # Extract features
    features = [item.name for item in fm.get_features()]
    logger.debug("Features: %d", len(features))

    # Extract leaf features
    leaf_features = extract_leaf_features(fm)
    logger.debug("Leaf features: %d", len(leaf_features))

    # Extract hierarchical candidates
    hierarchical_candidates = extract_hierarchical_candidates(fm)
    logger.debug("Hierarchical candidates: %d", len(hierarchical_candidates))

    # Extract cross-tree constraints
    cross_tree_constraints = extract_cross_tree_constraints(fm)
    logger.debug("Cross-tree constraints: %d", len(cross_tree_constraints))

    # Extract features from cross-tree constraints (for extracted mode)
    ctc_features = extract_cross_tree_features(fm)
    logger.debug("Features in cross-tree constraints: %d", len(ctc_features))

    # Generate YAML content
    yaml_content = generate_yaml_content(
        name=model_name,
        features=features,
        leaf_features=leaf_features,
        hierarchical_candidates=hierarchical_candidates,
        cross_tree_constraints=cross_tree_constraints,
        cross_tree_mode=cross_tree_mode,
        cross_tree_features=ctc_features if cross_tree_mode == "extracted" else None
    )

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path(output_dir) / f"{model_name}.yaml"

    # Write YAML file atomically (a crash can't truncate an existing config)
    write_text_atomic(output_path, yaml_content)

    logger.info("Generated bias config: %s", output_path)
    logger.info("  Features: %d", len(features))
    logger.info("  Leaf features: %d", len(leaf_features))
    logger.info("  Hierarchical candidates: %d", len(hierarchical_candidates))
    logger.info("  Cross-tree mode: %s", cross_tree_mode)
    if cross_tree_mode == "extracted":
        logger.info("  Cross-tree features (from CTCs): %d", len(ctc_features))

    return True


def main():
    args = parse_argument()

    setup_logging(verbose=args.verbose)

    # Batch mode: process multiple models
    if args.models:
        logger.info("Processing %d models...", len(args.models))

        success_count = 0
        for i, model_config in enumerate(args.models, 1):
            fm_path = model_config.get('fm_path')
            if not fm_path:
                logger.error("[%d] 'fm_path' is required for each model", i)
                continue

            logger.info("[%d/%d] Processing: %s", i, len(args.models), fm_path)

            # Model-specific settings override global settings
            output = model_config.get('output')
            cross_tree_mode = model_config.get('cross_tree_mode', args.cross_tree_mode)

            success = process_model(
                fm_path=fm_path,
                output=output,
                output_dir=args.output_dir,
                cross_tree_mode=cross_tree_mode
            )

            if success:
                success_count += 1

        logger.info("Completed: %d/%d models processed successfully",
                    success_count, len(args.models))

    # Single model mode
    else:
        success = process_model(
            fm_path=args.fm_path,
            output=args.output,
            output_dir=args.output_dir,
            cross_tree_mode=args.cross_tree_mode
        )
        if not success:
            sys.exit(1)

if __name__ == "__main__":
    main()

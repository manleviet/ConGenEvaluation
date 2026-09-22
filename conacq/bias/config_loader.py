"""
Configuration loader for YAML bias configurations.

This module provides functionality to load bias configurations
from YAML files. The format only requires:
- Feature names (no IDs)
- Hierarchical candidates with relationship types
- Cross-tree config (auto-generate or specific pairs)
"""

import yaml
from pathlib import Path
from typing import Dict
from .data_structures import (
    BiasConfig,
    HierarchicalCandidate,
    CrossTreeConfig,
    RelationshipType,
    CrossTreeMode,
)


_MAX_CROSS_TREE_FEATURES_WARNING = 20


class BiasConfigLoader:
    """Load YAML configuration for bias generation"""

    @staticmethod
    def load(config_path: str) -> BiasConfig:
        """
        Load config from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            BiasConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            KeyError: If required fields are missing

        Example YAML format:
            name: Survey
            features:
              - survey
              - payment
              - license
            leaf_features:
              - license
              - nolicense
            hierarchical_candidates:
              - parent: survey
                children: [payment]
                relationship_type: binary
              - parent: payment
                children: [license, nolicense]
                relationship_type: group
            cross_tree_candidates:
              cross_tree_mode: leaf  # 'all', 'leaf', or 'extracted'
              cross_tree_features:   # Optional: features for 'extracted' mode
                - featureA
                - featureB
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Validate required fields
        if 'features' not in data:
            raise KeyError("Required field 'features' missing in config")
        if not isinstance(data['features'], list):
            raise ValueError("Field 'features' must be a list")

        # Parse features (just list of names)
        features = data['features']

        # Parse leaf features (optional, defaults to empty list)
        leaf_features = data.get('leaf_features', [])
        if not isinstance(leaf_features, list):
            raise ValueError("Field 'leaf_features' must be a list")

        hierarchical_candidates = BiasConfigLoader._parse_hierarchical_candidates(data)
        cross_tree_config = BiasConfigLoader._parse_cross_tree_config(data)

        return BiasConfig(
            name=data.get('name', 'Unnamed'),
            features=features,
            leaf_features=leaf_features,
            hierarchical_candidates=hierarchical_candidates,
            cross_tree_config=cross_tree_config
        )

    @staticmethod
    def _parse_hierarchical_candidates(data: dict) -> list:
        """Parse hierarchical candidates from raw YAML data."""
        candidates = []
        for hc in data.get('hierarchical_candidates', []):
            if 'parent' not in hc:
                raise KeyError("'parent' field missing in hierarchical candidate")
            if 'children' not in hc:
                raise KeyError("'children' field missing in hierarchical candidate")
            if 'relationship_type' not in hc:
                raise KeyError("'relationship_type' field missing in hierarchical candidate")

            rel_type_str = hc['relationship_type']
            if rel_type_str not in ['binary', 'group']:
                raise ValueError(f"Invalid relationship_type: {rel_type_str}. Must be 'binary' or 'group'")

            candidates.append(HierarchicalCandidate(
                parent=hc['parent'],
                children=hc['children'] if isinstance(hc['children'], list) else [hc['children']],
                relationship_type=RelationshipType(rel_type_str)
            ))
        return candidates

    @staticmethod
    def _parse_cross_tree_config(data: dict) -> CrossTreeConfig:
        """Parse cross-tree configuration from raw YAML data."""
        ct_data = data.get('cross_tree_candidates', {})

        mode_str = ct_data.get('cross_tree_mode', 'leaf')
        if mode_str not in ['all', 'leaf', 'extracted']:
            raise ValueError(f"Invalid cross_tree_mode: {mode_str}. Must be 'all', 'leaf', or 'extracted'")

        cross_tree_features = ct_data.get('cross_tree_features', [])
        if not isinstance(cross_tree_features, list):
            raise ValueError("Field 'cross_tree_features' must be a list")

        return CrossTreeConfig(
            cross_tree_mode=CrossTreeMode(mode_str),
            specific_pairs=ct_data.get('specific_pairs', []),
            cross_tree_features=cross_tree_features
        )

    @staticmethod
    def validate_config(config: BiasConfig) -> Dict[str, any]:
        """
        Validate that the configuration is consistent.

        Checks:
        - All parent/child references exist in features list
        - No duplicate feature names
        - Feature names are valid strings

        Args:
            config: BiasConfig to validate

        Returns:
            Dictionary with validation results:
                {
                    'valid': bool,
                    'errors': list of error messages,
                    'warnings': list of warning messages
                }
        """
        errors = []
        warnings = []
        feature_set = set(config.features)

        # Check for duplicate features
        if len(feature_set) != len(config.features):
            duplicates = [f for f in config.features if config.features.count(f) > 1]
            errors.append(f"Duplicate features found: {set(duplicates)}")

        # Check that all hierarchical candidate references are valid
        for hc in config.hierarchical_candidates:
            if hc.parent not in feature_set:
                errors.append(f"Parent '{hc.parent}' not in features list")

            for child in hc.children:
                if child not in feature_set:
                    errors.append(f"Child '{child}' not in features list")

        # Check for empty feature names
        for feature in config.features:
            if not feature or not isinstance(feature, str):
                errors.append(f"Invalid feature name: {feature}")

        # Check that all cross_tree_features exist in features list
        for feature in config.cross_tree_config.cross_tree_features:
            if feature not in feature_set:
                errors.append(f"Cross-tree feature '{feature}' not in features list")

        # Warnings
        if not config.hierarchical_candidates:
            warnings.append("No hierarchical candidates defined")

        # Check cross-tree features based on mode
        cross_tree_features = config.get_cross_tree_features()
        if len(cross_tree_features) > _MAX_CROSS_TREE_FEATURES_WARNING:
            n_features = len(cross_tree_features)
            expected_ct = n_features * (n_features - 1) // 2 * 3  # (n choose 2) * 3
            mode = config.cross_tree_config.cross_tree_mode.value
            warnings.append(
                f"Large feature set ({n_features} {mode} features) "
                f"will create ~{expected_ct} cross-tree constraints"
            )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

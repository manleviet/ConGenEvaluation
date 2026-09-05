"""
Bias module for constraint acquisition.

This module provides tools for generating constraint biases from feature models,
including data structures, clause example_generators, and I/O utilities.
"""

from .data_structures import (
    Feature,
    Constraint,
    Bias,
    OperatorType,
    RelationshipType,
    HierarchicalCandidate,
    CrossTreeConfig,
    BiasConfig,
)
from .clause_generator import ConstraintClauseGenerator
from .config_loader import BiasConfigLoader
from .bias_generator import BiasGenerator
from .bias_io import BiasIO

__all__ = [
    # Data structures
    'Feature',
    'Constraint',
    'Bias',
    'OperatorType',
    'RelationshipType',
    'HierarchicalCandidate',
    'CrossTreeConfig',
    'BiasConfig',
    # Generators and utilities
    'ConstraintClauseGenerator',
    'BiasConfigLoader',
    'BiasGenerator',
    'BiasIO',
]

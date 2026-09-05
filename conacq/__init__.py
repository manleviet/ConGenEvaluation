"""
AcqMSS - Constraint Acquisition with Maximum Satisfiable Subsets.

This package provides tools for constraint acquisition from feature models:
- examples: Test case generation and oracle for feature models
- algorithms: ConGen algorithm implementation
- bias: Bias generation for constraint acquisition
"""

from . import examples
from . import algorithms

__all__ = ['examples', 'algorithms']

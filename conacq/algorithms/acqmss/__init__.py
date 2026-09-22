"""
Constraint Acquisition Algorithms.

This package provides implementations of constraint acquisition algorithms:

ConGen (Passive/Batch Learning):
- AcqMSS: Divide-and-conquer algorithm for finding MSS of bias
- REDUCE: Redundancy elimination from acquired KB
- ConGen: Main constraint acquisition algorithm
  (GenerateNE lives behind ConGenTaskPreparation; it is not an algorithm export)

Interactive Learning (QuAcq):
- QuAcq: Interactive constraint acquisition via membership queries
- QueryProvider: Unified query provider (pool + SAT)

Task classes shared across incremental and non-incremental modes.
"""

from .acqmss import AcqMSS
from .reduce import Reduce
from .congen import ConGen, ConGenResult
from .task_preparation import ConGenTask
from .task_preparation import ConGenTaskInput
from .task_preparation import ConGenTaskPreparation
from .congen_model import ConGenModel
from .congen_model_builder import ConGenModelBuilder

# Interactive learning components
from ..quacq import (
    QuAcq,
    QuAcqModel,
    QuAcqModelBuilder,
    QuAcqTask,
    QuAcqResult,
    FMOracle,
    UserPromptOracle,
    CachedOracle,
)

# Re-export explanation module classes for convenience
from explanation.api import Assignment, TestCase, TestSuite
from explanation.api import TaskInput

__all__ = [
    # ConGen (passive learning)
    'AcqMSS',
    'Reduce',
    'ConGen',
    'ConGenResult',
    'ConGenTask',
    'ConGenTaskInput',
    'ConGenTaskPreparation',
    'ConGenModel',
    'ConGenModelBuilder',
    # Interactive learning (QuAcq)
    'QuAcq',
    'QuAcqModel',
    'QuAcqModelBuilder',
    'QuAcqTask',
    'QuAcqResult',
    'FMOracle',
    'UserPromptOracle',
    'CachedOracle',
    # Re-exports from explanation module
    'Assignment',
    'TestCase',
    'TestSuite',
    'TaskInput',
]

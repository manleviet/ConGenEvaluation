"""
Constraint Acquisition Algorithms.

This package provides implementations of constraint acquisition algorithms:

ConGen (Passive/Batch Learning):
- AcqMSS: Divide-and-conquer algorithm for finding MSS of bias
- REDUCE: Redundancy elimination from acquired KB
- ConGen: Main constraint acquisition algorithm
  (GenerateNE is a task-preparation internal, not exported here)

Interactive Learning (QuAcq):
- QuAcq: Interactive constraint acquisition via membership queries
- QueryProvider: Unified query provider (pool + SAT)

Task classes shared across incremental and non-incremental modes.
"""

# Passive learning (ConGen) - expose from acqmss subpackage
from .acqmss import (
    AcqMSS,
    Reduce,
    ConGen,
    ConGenResult,
    ConGenModel,
    ConGenModelBuilder,
    ConGenTaskInput,
)

# Interactive learning (QuAcq)
from .quacq import (
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
    'ConGenModel',
    'ConGenModelBuilder',
    'ConGenTaskInput',
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

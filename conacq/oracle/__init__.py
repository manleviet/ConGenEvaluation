"""
Oracle package for constraint acquisition.

Provides ground truth interfaces for classifying configurations:
- MembershipOracle / GeneratorOracle / … : narrow role protocols (see protocols.py)
- FMOracle: Validates against a feature model (SAT-based)
- UserPromptOracle: Human-in-the-loop oracle
- CachedOracle: Wrapper caching oracle answers
- GroundTruthData: Extracted ground truth for evaluation
"""

from .bg_data import BGData
from .oracle_data import OracleData
from .protocols import (
    MembershipOracle,
    CompletableOracle,
    CatalogProvider,
    BGProvider,
    KBProvider,
    GeneratorOracle,
    PreparationOracle,
)
from .fm.oracle import FMOracle
from .user_prompt import UserPromptOracle
from .cached import CachedOracle
from .ground_truth import GroundTruthData
from .fm.model import FMOracleModel
from .fm.builder import FMOracleModelBuilder
from .constraint_description import extract_constraint_descriptions

__all__ = [
    'BGData',
    'OracleData',
    # Narrow role protocols (contracts consumers depend on)
    'MembershipOracle',
    'CompletableOracle',
    'CatalogProvider',
    'BGProvider',
    'KBProvider',
    'GeneratorOracle',
    'PreparationOracle',
    'FMOracle',
    'UserPromptOracle',
    'CachedOracle',
    'GroundTruthData',
    'FMOracleModel',
    'FMOracleModelBuilder',
    'extract_constraint_descriptions',
]

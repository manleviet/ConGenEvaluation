"""FM-specific oracle implementation, grouped as one package.

The concrete ``FMOracle`` (job ①), its immutable KB ``FMOracleModel`` + external
``FMOracleModelBuilder``, and the pure ``FMOracleTaskPreparation`` (job ②). Kept
apart from the FM-agnostic pieces in ``conacq.oracle`` — the role protocols, the
frozen values (``OracleData``, ``BGData``), and the other oracles (``CachedOracle``,
``UserPromptOracle``).

This ``__init__`` re-exports the classes for convenience; the parent
``conacq.oracle`` and tests import from the specific submodules (``fm.model``,
``fm.oracle``, …) so each symbol keeps one obvious, greppable path.
"""

from conacq.oracle.fm.model import FMOracleModel
from conacq.oracle.fm.builder import FMOracleModelBuilder
from conacq.oracle.fm.task_preparation import FMOracleTaskPreparation
from conacq.oracle.fm.oracle import FMOracle

__all__ = [
    'FMOracleModel',
    'FMOracleModelBuilder',
    'FMOracleTaskPreparation',
    'FMOracle',
]

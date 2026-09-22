"""
FM oracle KB model.

FMOracleModel is an immutable FM knowledge base: it holds the constraint maps, the
name↔id catalog (inherited from KBModel), and the next free assumption ID, and
derives a fresh OracleData snapshot per call via ``prepare`` (pure — no task state
stored on the model). Solver mode (``use_incremental``) is an operation/checker
concern owned by the caller, not the model. Loading an FM file is the builder's job
(FMOracleModelBuilder) — the model does not build itself.
"""

from conacq.kb_model import KBModel
from conacq.oracle.fm.task_preparation import FMOracleTaskPreparation
from conacq.oracle.oracle_data import OracleData


class FMOracleModel(KBModel):
    """Immutable FM knowledge base for oracle validation via ConsistencyChecker.

    Holds only KB data (constraint_map + negated_constraint_map + the name↔id catalog
    + next_available_id, all from KBModel). Preparation is pure: ``prepare`` returns a
    fresh OracleData snapshot and stores nothing on the model. FM clauses go into
    set_kb (always active); feature assignments become assumption-guarded unit clauses:
      [-a_pos_i, fid]  → if a_pos_i active, feature must be true
      [-a_neg_i, -fid] → if a_neg_i active, feature must be false

    The FM's declared root feature name is stored explicitly at build
    (``root_feature``, set by FMOracleModelBuilder). It is the independent witness
    for the "root = first constraint_map key" invariant — see
    ``test_root_constraint_is_the_first_constraint_map_key``. Default "" on a bare
    (unbuilt) model.
    """

    # The FM's declared root name, filled by the builder. Class default keeps a bare
    # FMOracleModel() (synthetic test KBs) attribute-safe.
    root_feature: str = ""

    def prepare(self) -> OracleData:
        """Derive a fresh OracleData provisioning snapshot from this FM KB (pure).

        Unlike the three solve-task models, this facade takes NO ``task_input`` and
        returns OracleData, not a PreparedTask: the oracle's snapshot is fully
        determined by the FM constraints and variables, so there is nothing per-task
        to receive. Each call builds a new snapshot; the model is never mutated.
        """
        return FMOracleTaskPreparation.prepare(self)

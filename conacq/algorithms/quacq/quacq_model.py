"""
Model for QuAcq constraint acquisition.

An immutable KB: bias constraint_map + name↔id catalog (inherited from KBModel).
``prepare_task`` derives a fresh PreparedTask per call (pure); the model stores no
task state and no solver-mode field (that is a caller/checker concern). The
task-computing helpers (get_constraint_vars, get_constraints_with_scope, resolve_kb,
model_to_config) are STATELESS — they take the prepared task / provider as a
parameter, never stored task state.
"""

from __future__ import annotations

from typing import List, Set, Tuple

from conacq.kb_model import KBModel
from explanation.api import (
    DescriptionProvider,
    PreparedTask,
    get_constraint_vars,
    variable_literals_to_config,
)

from .task_preparation import QuAcqTask, QuAcqTaskInput, QuAcqTaskPreparation


class QuAcqModel(KBModel):
    """Immutable QuAcq KB (bias constraints + name↔id catalog).

    Pure data container. prepare_task builds a fresh QuAcqTask; the model holds no
    task, no description provider, no assignment map, no solver mode.

    Usage:
        oracle = FMOracle('data/fms/model.uvl')
        model = (QuAcqModelBuilder
                 .from_bias('data/bias/model.json')
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        prepared = model.prepare_task(QuAcqTaskInput(oracle.oracle_data))
        task = prepared.task  # QuAcqTask with assumption IDs
    """

    def prepare_task(self, task_input: QuAcqTaskInput) -> PreparedTask:
        """Assign assumption IDs and build a fresh QuAcqTask (pure).

        Consumes a QuAcqTaskInput carrying the oracle's frozen provisioning
        snapshot; returns a new PreparedTask (task + describe + assignment_map).
        The signature is unified with the other models; the input TYPE is QuAcq's
        own (not a shared union — ADR-0006).
        """
        return QuAcqTaskPreparation().prepare(self, task_input)

    def get_constraint_vars(self, task: QuAcqTask, assumption_id: int) -> Set[str]:
        """Feature names for a bias constraint (by assumption id). Stateless: the
        constraint clauses come from the given task, the catalog from this KB."""
        clauses = task.constraint_clauses.get(assumption_id, [])
        return get_constraint_vars(clauses, self.id_to_name)

    def get_constraints_with_scope(self, task: QuAcqTask,
                                   scope: set, remaining_bias: dict) -> List[int]:
        """Bias constraint IDs whose variables match scope. Stateless (reads the
        given task's constraint clauses).

        Prefers exact scope match (c_vars == scope). Falls back to subset
        match (c_vars ⊆ scope) if no exact matches found.
        """
        exact = []
        subset = []
        # Collects bias constraints matching scope exactly or subset
        for aid in remaining_bias:
            c_vars = self.get_constraint_vars(task, aid)
            if not c_vars:
                continue
            if c_vars == scope:
                exact.append(aid)
            elif c_vars.issubset(scope):
                subset.append(aid)
        return exact if exact else subset

    def resolve_kb(self, describe: DescriptionProvider,
                   kb_assumption_ids: List[int]) -> Tuple[List[str], List[List[int]]]:
        """Resolve learned assumption IDs to constraint names + raw clauses.

        Stateless: the id→name provider is passed in (from the PreparedTask);
        raw clauses come from this KB's constraint_map.
        """
        names = [describe.get_description(aid) for aid in kb_assumption_ids]
        clauses: List[List[int]] = []
        for aid in kb_assumption_ids:
            name = describe.get_description(aid)
            if name in self.constraint_map:
                clauses.extend(self.constraint_map[name])
        return names, clauses

    def model_to_config(self, model):
        """Convert a SAT model to a configuration dict (uses the KB catalog only)."""
        return variable_literals_to_config(model, self.id_to_name)

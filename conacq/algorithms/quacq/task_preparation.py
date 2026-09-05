"""
QuAcqTask: assumption-ID-based task for QuAcq constraint acquisition.

Parallel to ConGenTask — uses integer assumption IDs instead of string IDs,
inherits DiagnosisTask for set_kb/assumptions/negation_map/set_b fields.
Also contains QuAcqTaskPreparation (co-located: creation logic next to data).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple

from explanation.api import (
    AssignmentAssumptionMap,
    AssumptionIdAllocator,
    DescriptionProvider,
    DiagnosisTask,
    FrozenDict,
    PreparedTask,
    TaskPreparationStrategy,
    prepare_kb,
)
if TYPE_CHECKING:
    from conacq.oracle import OracleData
    from .quacq_model import QuAcqModel


@dataclass(frozen=True)
class QuAcqTaskInput:
    """Per-preparation input for QuAcqModel.prepare_task: the oracle's frozen
    provisioning snapshot. QuAcq's own input type — the prepare_task signature is
    unified across models, the input TYPE is not (a shared union would be the
    fat-container anti-pattern removed at T9, ADR-0006)."""
    oracle_data: "OracleData"


@dataclass(frozen=True)
class QuAcqTask(DiagnosisTask):
    """Immutable task for QuAcq constraint acquisition.

    Inherits from DiagnosisTask:
        set_c:         Bias constraint assumption IDs (same role as ConGenTask)
        set_b:         BG assumption IDs (from BGData root constraint)
        set_kb:        Full KB with assumption guards
        negation_map:  {assumption_id -> negated_assumption_id}
        assumptions:   All assumption IDs

    QuAcq-specific immutable data:
        constraint_clauses:   assumption_id -> raw CNF clauses (no guards)

    Mutable state (remaining_bias, learned_kb, n_queries, query_history)
    lives in the QuAcq algorithm, not here.
    """
    # assumption_id -> raw clauses (WITHOUT assumption guards, for violation checking)
    constraint_clauses: "FrozenDict[int, Tuple[Tuple[int, ...], ...]]" = field(default_factory=dict)

    def __post_init__(self):
        # Freeze the Task guts (super) then deep-freeze constraint_clauses so the
        # frozen=True label is honest (built-then-frozen in QuAcqTaskPreparation).
        super().__post_init__()
        object.__setattr__(self, 'constraint_clauses',
                           FrozenDict({k: tuple(tuple(c) for c in v)
                                       for k, v in self.constraint_clauses.items()}))


class QuAcqTaskPreparation(TaskPreparationStrategy):
    """Prepare QuAcqTask from bias + oracle. No E+/E-.

    Assumption ID layout (QuAcq owns Parts 5-6):
      Parts 1-4: Owned by Oracle (see OracleTaskPreparation)
      Part 5:    Tseitin vars (negated bias constraints)   <- This method
      Part 6:    Bias constraint assumptions (paired)      <- This method
    """

    def prepare(self, model: QuAcqModel,
                task_input: QuAcqTaskInput) -> PreparedTask:
        """Prepare QuAcqTask from model and the frozen OracleData snapshot.

        Build-then-freeze: accumulate into locals, construct frozen QuAcqTask once.

        Args:
            model: QuAcqModel with bias constraint_map
            task_input: QuAcqTaskInput carrying the oracle's frozen snapshot; its
                oracle_data is unpacked here so the signature matches the
                TaskPreparationStrategy contract (model, task_input) — the model
                layer no longer unpacks it before handing it down.

        Returns:
            PreparedTask with QuAcqTask, DescriptionProvider, and the
            feature-assignment map (built here from the BG data, not the builder).
        """
        oracle_data = task_input.oracle_data
        provider = DescriptionProvider()

        # Local accumulation
        set_kb: List[List[int]] = []
        assumptions: List[int] = []
        negation_map: Dict[int, int] = {}

        # Step 0: Copy BG data from Oracle (root constraint pair)
        bg_data = oracle_data.get_bg_data()
        set_kb.extend(bg_data.set_kb)
        assumptions.extend(list(bg_data.assumptions))
        negation_map.update(bg_data.negation_map)
        for aid, desc in bg_data.descriptions.items():
            provider.add_constraint_description(aid, desc)

        # Copy Part 4 data from BGData (feature assignment assumptions)
        set_kb.extend(bg_data.assignment_clauses)
        assumptions.extend(bg_data.assignment_assumptions)

        # The feature-assignment map, built here from the BG data and returned on
        # the PreparedTask. The QuAcq inner loop encodes configs through it
        # (FindC/prune/query generation); it is derived per prepare, not stored.
        assignment_map = AssignmentAssumptionMap(
            dict(bg_data.pos_assignment_to_assumption),
            dict(bg_data.neg_assignment_to_assumption))

        # Step 1: Assign assumption IDs (negated forms from builder). set_c is the
        # bias originals prepare_kb emitted; set_b is the BG root (first assumption).
        alloc = AssumptionIdAllocator(model.next_available_id)
        set_c = prepare_kb(
            set_kb, assumptions, negation_map, provider,
            model.constraint_map, alloc, model.negated_constraint_map)
        set_b = [assumptions[0]]

        # Step 2: Build constraint_clauses mapping
        constraint_clauses: Dict[int, List[List[int]]] = {}
        for aid in set_c:
            name = provider.get_description(aid)
            if name in model.constraint_map:
                constraint_clauses[aid] = model.constraint_map[name]

        task = QuAcqTask(
            set_c=set_c, set_b=set_b, set_kb=set_kb,
            negation_map=negation_map, assumptions=assumptions,
            constraint_clauses=constraint_clauses)
        return PreparedTask(task, provider, assignment_map)

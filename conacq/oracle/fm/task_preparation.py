"""
Task preparation for the FM oracle (job ①/② provisioning).

FMOracleTaskPreparation builds the assumption-guarded task once (pure) and returns
the oracle's frozen provisioning snapshot as a single view: ``prepare`` -> OracleData
(job ②). OracleData already carries the task + assignment_map that every consumer
reads, so no separate PreparedTask view is needed. The oracle *receives* its
OracleData; it does not assemble what it provides (ADR-0009).
"""

from typing import TYPE_CHECKING, Dict, List

from conacq.oracle.bg_data import BGData
from conacq.oracle.oracle_data import OracleData
from explanation.api import (
    AssumptionIdAllocator,
    DiagnosisTask,
    DescriptionProvider,
    AssignmentAssumptionMap,
    prepare_kb,
    prepare_variable_assignments,
)

if TYPE_CHECKING:
    from conacq.oracle.fm.model import FMOracleModel


class FMOracleTaskPreparation:
    """Prepare assumption-guarded clauses + BGData for Oracle FM validation.

    Shared Assumption ID Layout (Oracle owns Parts 1-4):
      Part 1: Feature variable IDs (1..n)               <- FmToDiagPysat
      Part 2: Tseitin vars (negated FM constraints)      <- FmToDiagPysat
      Part 3: FM constraint assumptions (paired)         <- This method
               [root, NOT(root), c2, NOT(c2), ...]
      Part 4: Variable assignment assumptions (paired)   <- This method
               [f1=true, f1=false, f2=true, ...]

    ConGen continues from Part 5 onward (see ConGenTaskPreparation).
    BGData extracts Part 3's first pair (root BG) + end-of-Part-4 ID.

    Pure: builds everything into locals; the model is never mutated. A single public
    view — ``prepare`` (OracleData, job ②). NOT a TaskPreparationStrategy: it is a
    static factory returning OracleData, not the instance ``prepare(model, task_input)
    -> PreparedTask`` contract (the return type keeps it out of the population guard).
    """

    @staticmethod
    def prepare(model: 'FMOracleModel') -> OracleData:
        """Assemble the oracle's frozen provisioning snapshot (job ②, ADR-0009).

        The oracle receives this; it does not build what it provides. One view over
        the preparation — OracleData already carries the ``.task`` + ``.assignment_map``
        consumers read (``describe`` has no readers), so there is no separate
        PreparedTask view and no shared private core.
        """
        provider = DescriptionProvider()

        # Seed the allocator after the Tseitin variables (avoid id conflicts).
        alloc = AssumptionIdAllocator(model.next_available_id)
        negated_constraint_map = model.negated_constraint_map

        # Local accumulation (build-then-freeze)
        set_kb: List[List[int]] = []
        assumptions: List[int] = []
        negation_map: Dict[int, int] = {}

        # Step 1: FM constraints → set_kb with assumptions. set_c is exactly the
        # originals prepare_kb emitted (returned directly, never sliced back out).
        set_c = prepare_kb(
            set_kb, assumptions, negation_map, provider,
            model.constraint_map, alloc, negated_constraint_map)

        # Step 2: Feature assignments → assumption-guarded (paired true/false)
        assignment_kb_start = len(set_kb)
        pos_assignment_to_assumption, neg_assignment_to_assumption = (
            prepare_variable_assignments(
                set_kb, assumptions, provider, model.name_to_id, alloc))

        # The feature-assignment map, returned on the OracleData; membership queries
        # reuse it locally (is_valid appends this query's assumptions to set_c). The
        # model is never mutated.
        assignment_map = AssignmentAssumptionMap(
            pos_assignment_to_assumption, neg_assignment_to_assumption)

        # Extract Part 4 data. assignment_clauses is the set_kb tail; the assumptions
        # are the (pos, neg) pairs the assignment step emitted, in name order — taken
        # from the maps it returned, not sliced back out of the flat list.
        assignment_clauses = set_kb[assignment_kb_start:]
        assignment_assumptions = [
            aid for name in model.name_to_id
            for aid in (pos_assignment_to_assumption[name],
                        neg_assignment_to_assumption[name])]

        # Step 4: Extract root BG data for ConGen consumption (requires negated constraints)
        bg_data = BGData(
            set_kb=set_kb[:2],  # first pair of assumptions for root constraint
            assumptions=(assumptions[0], assumptions[1]),
            negation_map={assumptions[0]: assumptions[1]},
            descriptions=provider.get_descriptions_for(
                [assumptions[0], assumptions[1]]),
            next_available_id=alloc.next_id,
            # Part 4
            assignment_clauses=assignment_clauses,
            assignment_assumptions=assignment_assumptions,
            pos_assignment_to_assumption=dict(pos_assignment_to_assumption),
            neg_assignment_to_assumption=dict(neg_assignment_to_assumption),
        )

        # The root constraint is, by construction, the FIRST entry in constraint_map
        # (FmToDiagPysat traverses the FM tree root-first — the same invariant the
        # bg_data root pair relies on). Its raw clauses are the background clauses
        # ConGen/QuAcq report.
        root_clauses = list(model.constraint_map[next(iter(model.constraint_map))])

        # Build-then-freeze: construct the frozen task once (set_b unused by Oracle).
        task = DiagnosisTask(
            set_c=set_c, set_b=[], set_kb=set_kb,
            negation_map=negation_map, assumptions=assumptions)
        return OracleData(
            task=task,
            bg_data=bg_data,
            root_clauses=root_clauses,
            assignment_map=assignment_map,
            next_available_id=model.next_available_id,
        )

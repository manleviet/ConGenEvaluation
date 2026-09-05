"""
GenerateNE Algorithm for generating negated negative examples.

Uses QuickXPlain to find minimal conflict sets from negative examples,
then negates them to create NE constraints.

Reference: Paper Section "ConGen (Algorithm 1)"
- GENERATENE(E-) activates QUICKXPLAIN once per negative example e- in E-.
- NE is a set of constraints such that: if e-_i in E- then not(e-_i) in NE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Sequence, Tuple

from explanation.api import QuickXPlain
from explanation.api import build_checker, SolverBackend, DiagnosisTask

if TYPE_CHECKING:
    from conacq.oracle import OracleData
    from explanation.api import AssumptionIdAllocator, TestCase, TestSuite


@dataclass
class NEPerTestcase:
    """Result of NE generation for a single testcase."""
    ne_id: int  # assumption ID for this NE
    ne_clause: List[int]  # blocking clause with assumption literal
    desc: str  # description string
    # Full-config assignment-assumption IDs for this e-, captured ONLY when a caller
    # asks via capture_assignments. Empty for ConGen (default) — additive,
    # so the return shape and every existing caller are unchanged.
    assignment_aids: Tuple[int, ...] = ()


class GenerateNE:
    """Generate negated negative examples using QuickXPlain.

    For each negative example e-, finds the minimal conflict set
    and creates a blocking clause. NE clauses are appended to the
    result KB so subsequent testcases see previous NEs.
    """

    def __init__(self, oracle_data: "OracleData") -> None:
        # Frozen provisioning snapshot (ADR-0009), not the live oracle: the KB and
        # background this reads cannot shift under it between test cases.
        self.oracle_data = oracle_data

    def generate(
            self,
            testsuite: TestSuite,
            variables: Dict[str, int],
            result_set_kb: List[List[int]],
            result_assumptions: List[int],
            alloc: "AssumptionIdAllocator",
            capture_assignments: bool = False,
            minimize: bool = True,
            profiler=None
    ) -> List[NEPerTestcase]:
        """Generate NE from negative examples using QuickXPlain.

        ``profiler`` (optional): when given, this PREPROCESSING QuickXplain (paper
        l.299 — reduction outside the acquisition procedure) is counted separately into
        ``shared_preprocessing_quickxplain_checks`` / ``shared_preprocessing_runtime``.
        ConGen omits it (profiler=None) → its behaviour + counters are unchanged.

        Per testcase: merges oracle KB with result KB, creates assignment
        clauses, runs QuickXPlain for minimal conflict, creates blocking clause.

        Args:
            testsuite: Negative test cases
            variables: Feature name -> SAT variable mapping
            result_set_kb: Task KB (mutated: NE clauses appended)
            result_assumptions: Task assumptions (read-only snapshot per iteration)
            alloc: assumption-id allocator (ids for the per-testcase probes + NE)
            capture_assignments: when True, persist each e-'s per-assignment
                guard clause into result_set_kb and return its full-config assignment
                aids on NEPerTestcase (for the cover rejection test). Default False
                keeps ConGen's behaviour and result_set_kb byte-identical.

        Returns:
            per_testcase_results
        """
        if not testsuite.testcases:
            return []

        set_bg = self.oracle_data.get_c()
        results: List[NEPerTestcase] = []

        for testcase in testsuite.testcases:
            results.append(self._process_testcase(
                testcase, variables, result_set_kb, result_assumptions,
                set_bg, alloc, capture_assignments, minimize, profiler))

        logging.debug('<<< GenerateNE: %d NE constraints', len(results))
        return results

    def _process_testcase(
            self,
            testcase: TestCase,
            variables: Dict[str, int],
            result_set_kb: List[List[int]],
            result_assumptions: List[int],
            set_bg: Sequence[int],
            alloc: "AssumptionIdAllocator",
            capture_assignments: bool = False,
            minimize: bool = True,
            profiler=None
    ) -> NEPerTestcase:
        """Process single testcase: merge KBs, QuickXPlain, create NE clause."""
        # Merge oracle KB with current result KB (creates new list)
        set_kb = list(self.oracle_data.get_kb()) + result_set_kb
        assumptions = list(self.oracle_data.get_assumptions()) + result_assumptions

        # Create per-assignment clauses
        set_tv, assumption_to_var, assumption_to_desc = [], {}, {}
        for assignment in testcase.assignments:
            if assignment.feature not in variables:
                raise KeyError(f'Feature {assignment.feature} is not in the model.')

            desc = f'{assignment.feature} = {"true" if assignment.value else "false"}'
            var = variables[assignment.feature] if assignment.value else -variables[assignment.feature]

            aid = alloc.allocate()
            set_tv.append(aid)
            assumptions.append(aid)
            set_kb.append([var, -1 * aid])
            if capture_assignments:
                # Persist the guard clause (aid ⇒ var) into the TASK KB so a
                # checker can activate this e-'s assignment for the rejection test.
                # Vacuous when aid is inactive (¬aid ∨ var), so Stage-1 MSS is unchanged.
                result_set_kb.append([var, -1 * aid])
            assumption_to_var[aid] = var
            assumption_to_desc[aid] = desc

        # Full-config assignment aids, captured BEFORE QuickXplain overwrites set_tv
        # with the minimal conflict — the rejection test needs the whole assignment.
        full_assignment_aids = tuple(assumption_to_var.keys()) if capture_assignments else ()

        # QuickXPlain for minimal conflict. The per-testcase subproblem is itself
        # a Task (set_c = test-value assumptions, set_b = background), so the
        # checker is built through the port like everywhere else.
        task = DiagnosisTask(set_c=set_tv, set_b=set_bg,
                             set_kb=set_kb, assumptions=assumptions)
        # minimize=True (reduced, DEFAULT): QuickXplain reduces e⁻ to a subset-minimal
        # conflict, so ¬e⁻ generalizes. minimize=False (raw): negate the FULL assignment
        # (skip the oracle QuickXplain) — a more specific ¬e⁻. Id allocation is identical
        # either way (QuickXplain allocates nothing), so the golden IDs are unchanged.
        if minimize:
            # One checker per testcase — release its solver before the next iteration.
            # Thread the profiler so this preprocessing QuickXplain is counted apart
            # from acquisition (GAP B): the is_consistent_calls DELTA + runtime go to
            # shared_preprocessing_* (the checker is built WITH the profiler so its
            # solves land there). profiler=None (ConGen) → unchanged behaviour.
            with build_checker(task, SolverBackend.PYSAT_NON_INCREMENTAL,
                               profiler=profiler) as checker:
                quickxplain = QuickXPlain(checker, profiler)
                if profiler is not None:
                    _pp_before = profiler.get_metric("is_consistent_calls", 0)
                    with profiler.timer("shared_preprocessing_runtime"):
                        minimal_conflict = quickxplain.find_conflict(
                            task.set_c, task.set_b)
                    profiler.increment(
                        "shared_preprocessing_quickxplain_checks",
                        profiler.get_metric("is_consistent_calls", 0) - _pp_before)
                else:
                    minimal_conflict = quickxplain.find_conflict(
                        task.set_c, task.set_b)
            if len(minimal_conflict) > 0:
                set_tv = minimal_conflict

        # Filter literals from minimal conflict
        literals, desc_parts = [], []
        for lit in set_tv:
            if lit in assumption_to_var:
                literals.append(assumption_to_var[lit])
                desc_parts.append(assumption_to_desc[lit])

        # Create NE clause: not(e) = (not(l1) or not(l2) or ... or not(ne_id))
        ne_id = alloc.allocate()
        ne_clause = [-lit for lit in literals]
        ne_clause.append(-ne_id)
        result_set_kb.append(ne_clause)  # mutate for subsequent testcases

        return NEPerTestcase(
            ne_id=ne_id, ne_clause=ne_clause,
            desc=f"NOT({' & '.join(desc_parts)})",
            assignment_aids=full_assignment_aids
        )

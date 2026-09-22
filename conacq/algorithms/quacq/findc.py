"""
FindC algorithm from IJCAI13 paper (Algorithm 3).

Given a scope (from FindScope), finds the specific constraint
that is violated by the negative example.

Uses oracle.is_valid() for membership queries, ConsistencyChecker
for SAT-based rejection filtering, and DiscriminatingGenerator
for SAT-based discriminating examples from C_L[Y] (learned KB).

Complexity: O(|Gamma|) queries where Gamma = candidate constraints with scope.
"""

import logging

from explanation.api import ConsistencyChecker, config_to_assignment_assumptions
from conacq.oracle import MembershipOracle
from profiling import measure_time, count_calls


class FindC:
    """Finds constraint with given scope violated by example.

    All collaborators and invariants (oracle, checker, model, record_query,
    root_assumption, generator, task, assignment_map) injected at construction;
    per-call data passed to run(). The model's scope helper is stateless — it reads
    the injected prepared task, not stored state.
    """

    def __init__(self, oracle: MembershipOracle, checker: ConsistencyChecker, model, profiler,
                 record_query, root_assumption: int, generator=None,
                 task=None, assignment_map=None):
        self.oracle = oracle
        self.checker = checker
        self.model = model
        self.profiler = profiler
        self.record_query = record_query
        self.root_assumption = root_assumption
        self.generator = generator
        self.task = task
        self.assignment_map = assignment_map

    @measure_time('findc_runtime')
    @count_calls('findc_calls')
    def run(
            self,
            e: dict,
            scope: set,
            remaining_bias: dict,
            learned_kb: list,
    ):
        """
        Find constraint with given scope violated by e.

        Uses ConsistencyChecker for SAT-based rejection filtering and
        DiscriminatingGenerator to narrow down which constraint
        in the scope is the one in the target (paper Algorithm 3).

        Args:
            e: Negative example
            scope: Variable scope from FindScope (set of feature names)
            remaining_bias: Mutable set of remaining bias assumption IDs
            learned_kb: Currently learned constraint IDs (for DiscriminatingGenerator)

        Returns:
            Constraint ID (int) or None
        """
        # Get candidate constraints: bias constraints whose scope matches
        candidates = self.model.get_constraints_with_scope(self.task, scope, remaining_bias)

        if not candidates:
            logging.debug('FindC: no candidates with scope %s', scope)
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Filter to constraints that actually reject e (SAT-based)
        rejecting = []
        e_assumptions = config_to_assignment_assumptions(e, self.assignment_map)
        base = [self.root_assumption] + e_assumptions

        for c_id in candidates:
            self.profiler.increment("findc_consistency_checks")
            if not self.checker.is_consistent(base + [c_id]):
                rejecting.append(c_id)

        if not rejecting:
            logging.debug('FindC: no rejecting constraint found')
            return None

        if len(rejecting) == 1:
            return rejecting[0]

        # Use DiscriminatingGenerator to narrow down
        remaining = list(rejecting)

        if self.generator is not None:
            result = self._narrow_with_generator(
                remaining, remaining_bias, learned_kb, scope)
            if result is not None:
                return result

        # Conservative (paper-faithful): discrimination could not confirm a SINGLE constraint.
        # Returning an unconfirmed guess (remaining[0]) can learn an OVER-STRONG constraint that
        # rejects e but is not in the target → precision <1.0. Learn nothing here; the caller's
        # band-aid advances progress. Soundness over recall.
        self.profiler.increment('quacq_findc_unconfirmed')  # diagnostic counter (fix-iii decline)
        logging.debug('FindC: %d candidates, none confirmed by discrimination → None', len(remaining))
        return None

    def _narrow_with_generator(
            self,
            candidates: list,
            remaining_bias: dict,
            learned_kb: list,
            scope: set
    ):
        """Try to narrow candidates using DiscriminatingGenerator (C_L[Y])."""
        i = 0
        while i < len(candidates) and len(candidates) > 1:
            c_i = candidates[i]
            j = i + 1
            # Narrows candidates by generating and testing discriminating examples between pairs
            while j < len(candidates):
                c_j = candidates[j]
                disc_e = self.generator.generate(c_i, c_j, learned_kb, scope)
                if disc_e is None:
                    j += 1
                    continue

                self.profiler.increment("paper_consistency_checks")
                is_valid = self.oracle.is_valid(disc_e)
                self.record_query(disc_e, is_valid, 'findc')

                if is_valid:
                    # c_j rejects a valid example -> c_j not in target
                    candidates.remove(c_j)
                    remaining_bias.pop(c_j, None)
                    # don't increment j — next element shifted into position
                else:
                    j += 1

                if len(candidates) == 1:
                    return candidates[0]
            i += 1

        # Only a SINGLE surviving candidate is a confirmed match; >1 means discrimination was
        # inconclusive → return None (unconfirmed), never guess the first (precision guard).
        return candidates[0] if len(candidates) == 1 else None

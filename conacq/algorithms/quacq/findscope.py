"""
FindScope algorithm from IJCAI13 paper (Algorithm 2).

Finds scope of violated constraint using partial membership queries
checked via oracle.is_valid(). Prunes bias via SAT-based consistency
checking with ConsistencyChecker.

Complexity: O(|S| * log|X|) queries where S=scope size, X=total variables.
"""

import logging
from typing import List

from explanation.api import ConsistencyChecker
from conacq.oracle import MembershipOracle
from profiling import measure_time, count_calls
from .sat_utils import prune_rejecting


class FindScope:
    """Finds scope of violated constraint via partial membership queries.

    All collaborators and invariants (oracle, checker, assignment_map, record_query,
    root_assumption) injected at construction; per-call data passed to run(). The
    assignment_map (from the prepared task) is what prune_rejecting needs — the
    model itself is no longer a collaborator here.
    """

    def __init__(self, oracle: MembershipOracle, checker: ConsistencyChecker, assignment_map, profiler,
                 record_query, root_assumption: int):
        self.oracle = oracle
        self.checker = checker
        self.assignment_map = assignment_map
        self.profiler = profiler
        self.record_query = record_query
        self.root_assumption = root_assumption

    @measure_time('findscope_runtime')
    @count_calls('findscope_calls')
    def run(
            self,
            e: dict,
            R: set,
            Y: set,
            ask_query: bool,
            remaining_bias: dict,
    ) -> List[str]:
        """
        Find scope of violated constraint via partial membership queries.

        Args:
            e: Complete negative example (config dict)
            R: Already-determined scope variables (feature names)
            Y: Remaining variables to search
            ask_query: Whether to query oracle with e[R]
            remaining_bias: Mutable set of remaining bias assumption IDs

        Returns:
            Scope variables (feature names) as list
        """
        if ask_query:
            partial = {k: e[k] for k in sorted(R) if k in e}  # canonical order (R is a set)
            self.profiler.increment("paper_consistency_checks")
            is_consistent = self.oracle.is_valid(partial)
            self.record_query(partial, is_consistent, 'findscope')

            if is_consistent:
                if partial:
                    # PARTIAL assignment → paper's fully-assigned-clause rule (include_bg=False):
                    # only condemn a candidate the partial fully assigns and falsifies. Extension-SAT
                    # (with BG) here wrongly pruned FM-entailed candidates whose scope the partial
                    # does not fully assign — the driver of the QuAcq recall loss.
                    pruned = prune_rejecting(self.checker, self.assignment_map, remaining_bias,
                                             partial, self.root_assumption, self.profiler,
                                             include_bg=False)
                    if pruned:
                        logging.debug('FindScope pruned %d constraints from partial query', len(pruned))
            else:
                return []

        if len(Y) <= 1:
            return list(Y)

        # Binary split
        Y_list = sorted(Y)
        mid = len(Y_list) // 2
        Y1 = set(Y_list[:mid])
        Y2 = set(Y_list[mid:])

        S1 = self.run(e, R | Y1, Y2, True, remaining_bias)
        S2 = self.run(e, R | set(S1), Y1, len(S1) > 0, remaining_bias)

        return S1 + S2

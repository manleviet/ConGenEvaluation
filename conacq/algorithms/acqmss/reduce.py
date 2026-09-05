"""
REDUCE Algorithm for redundancy elimination.

Removes redundant constraints from the acquired knowledge base.
Pattern follows WipeOutR_FM.find_redundancies() from the explanation package.

Mode-agnostic: all elements are assumption IDs (int), negation_map is Dict[int, int].
"""

import logging
from typing import List, Dict, Mapping, Sequence, Tuple

from explanation.api import ConsistencyChecker
from profiling import (
    get_global_profiler, measure_time, count_calls, AbstractProfiler
)
from explanation.api import diff


class Reduce:
    """
    REDUCE algorithm for removing redundant constraints.

    A constraint c is redundant if BG ∪ (KB - {c}) |= c
    Equivalently: BG ∪ (KB - {c}) ∪ {¬c} is inconsistent

    Algorithm REDUCE(B', NE, BG)
    1: KB ← B' ∪ NE
    2: for all c ∈ KB do
    3:     if inconsistent(BG ∪ (KB - {c}) ∪ {¬c}) then
    4:         KB ← KB - {c}
    5:     end if
    6: end for
    7: return KB
    """

    def __init__(self, checker: ConsistencyChecker,
                 profiler_instance: AbstractProfiler = None) -> None:
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('reduce_runtime')
    @count_calls('reduce_calls')
    def reduce(self, set_b_prime: List[int], set_neg_tv: List[int],
               set_bg: Sequence[int], negation_map: Mapping[int, int]) -> Tuple[List[int], List[int]]:
        """
        Remove redundant constraints from KB.

        All elements are assumption IDs (int). negation_map is Dict[int, int].

        Args:
            set_b_prime: MSS constraints from AcqMSS (assumption IDs)
            set_neg_tv: Negated negative examples (assumption IDs)
            set_bg: Background knowledge (assumption IDs)
            negation_map: Mapping from assumption ID to its negated form ID

        Returns:
            Tuple of (redundant IDs, non-redundant KB IDs)
        """
        logging.debug('REDUCE [B\'=%s, NE=%s, BG=%s]', set_b_prime, set_neg_tv, set_bg)

        # Normalize set_bg to a list: it is concatenated with lists below, and callers
        # may pass a frozen tuple (QuAcq passes the task's tuple set_b). ConGen
        # already passes a list, so list(list) is a no-op → its numbers stay identical.
        set_bg = list(set_bg)

        # KB ← B' ∪ NE, preserving AcqMSS's gamma1+gamma2 appearance order.
        # NE first, and the reason is over-fitting, not convenience. The test below runs
        # against kb_delta — what is LEFT of the KB at that point — not against the full
        # B'. Assembled last, every learned bias constraint is tested while all the
        # memorized ¬e⁻ are still present, so a fact memorized from ONE training example
        # can make a general constraint look redundant and drop it. Assembled first, the
        # redundant ¬e⁻ go first and those constraints survive: measured over 72 folds,
        # n_kb rises by +9 to +25 per knowledge base, showing up as semantic recall
        # 0.909 -> 1.000 on REAL-FM-7 ff and 0.945 -> 1.000 on REAL-FM-4 rs_3n.
        #
        # It is also what keeps |KB| reportable. With NE assembled last, each ¬e⁻ faces a
        # KB already stripped of the constraints that would entail it, and n_ne climbs to
        # 6 (132 facts retained over 72 folds); assembled first they discharge each other
        # and n_ne stays in {0, 1} (42 retained).
        #
        # dict.fromkeys dedups (first occurrence wins) without going through set(), which
        # would iterate in hash order and make the surviving representative of mutually
        # redundant constraints depend on hashing rather than on the algorithm.
        kb = list(dict.fromkeys(list(set_neg_tv) + list(set_b_prime)))
        kb_delta = kb.copy()
        redundant = []

        for c in kb:
            if c not in kb_delta:
                continue

            kb_without_c = diff(kb_delta, [c])

            # Get ¬c
            if c not in negation_map:
                logging.warning('No negated form for constraint %s, skipping', c)
                continue
            neg_c = negation_map[c]

            # Check inconsistent(BG ∪ (KB - {c}) ∪ {¬c})
            test_set = set_bg + kb_without_c + [neg_c]
            is_consistent = self.checker.is_consistent(test_set)
            self.profiler.increment("redundancy_consistency_checks")
            # self.profiler.increment("paper_consistency_checks")

            logging.debug('Checking c=%s: consistent(BG ∪ KB-{c} ∪ {¬c}) = %s',
                          c, is_consistent)

            if not is_consistent:
                # c is redundant: KB - {cα} |= cα
                kb_delta.remove(c)
                redundant.append(c)
                logging.debug('Constraint %s is redundant', c)

        logging.debug('Redundant: %s', redundant)
        logging.debug('Non-redundant KB: %s', kb_delta)

        return redundant, kb_delta

    @measure_time('reduce_nonredundant_runtime')
    def find_non_redundant(self, set_b_prime: List[int], set_neg_tv: List[int],
                           set_bg: List[int], negation_map: Dict[int, int]) -> List[int]:
        """Find non-redundant constraints in KB."""
        _, non_redundant = self.reduce(set_b_prime, set_neg_tv, set_bg, negation_map)
        return non_redundant

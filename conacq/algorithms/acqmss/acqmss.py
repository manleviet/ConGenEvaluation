"""
AcqMSS Algorithm for constraint acquisition.

Divide-and-conquer algorithm for finding Maximum Satisfiable Subset (MSS)
of bias constraints that are consistent with positive examples.

Pattern follows KBDiag._mssDirect() from the explanation package.
"""

import logging
from typing import List

from explanation.api import ConsistencyChecker
from profiling import (
    get_global_profiler, measure_time, count_calls, AbstractProfiler
)
from explanation.api import split, diff


class AcqMSS:
    """
    AcqMSS divide-and-conquer algorithm for finding MSS.

    Pattern follows KBDiag._mssDirect().

    Algorithm:
        Func AcqMSS(δ, B, NE, E+, BG) : Γ
        E'+ <- E+
        if δ != Φ then
           E'+ <- TestC(B ∪ NE ∪ BG, E+)
           if E'+ = Φ then return B;
        if |B| <= m return Φ;
        B1, B2 = split(B)
        Γ2 = AcqMSS(δ=B1, B1, NE, E'+, BG)
        Γ1 = AcqMSS(δ=B1-Γ2, B2, NE, E'+, BG ∪ Γ2)
        return Γ1 ∪ Γ2

    Args:
        checker: ConsistencyChecker instance for SAT solving
        m: Minimum subset size (default 1)
        profiler_instance: Optional profiler for metrics tracking
    """

    def __init__(self, checker: ConsistencyChecker, m: int = 1,
                 profiler_instance: AbstractProfiler = None) -> None:
        self.checker = checker
        self.m = m
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('acqmss_runtime')
    @count_calls('acqmss_calls')
    def find_mss(self, delta: List, set_b: List, set_neg_tv: List,
                 set_tc: List, set_bg: List) -> List:
        """
        Find maximum satisfiable subset of B.

        Args:
            delta: Previously identified satisfiable constraints (for optimization)
            set_b: Candidate constraints (bias assumption IDs)
            set_neg_tv: Negated negative examples (assumption IDs)
            set_tc: Positive examples (list of assumption IDs)
            set_bg: Background knowledge (assumption IDs)

        Returns:
            MSS subset of B that is consistent with all E+ and NE
        """
        logging.debug('>>> AcqMSS [δ=%s, B=%s, NE=%s, E+=%s, BG=%s]',
                      delta, set_b, set_neg_tv, set_tc, set_bg)

        # E'+ <- E+
        set_tcp = list(set_tc)

        # if δ != Φ then E'+ <- TestC(B ∪ NE ∪ BG, E+)
        if len(delta) != 0:
            # Check which E+ are inconsistent with B ∪ NE ∪ BG
            _solver_before = self.profiler.get_metric("is_consistent_calls", 0)
            set_tcp = self.checker.is_consistent_test_cases(
                set_b + set_neg_tv + set_bg, set_tc, False
            )
            self.profiler.increment("paper_consistency_checks")
            # §9c Stage-1 MSS check at BATCH granularity (+1 per IsConsistent call, to
            # match ConGen's paper_consistency_checks). shared_ prefix — ConGen also
            # runs AcqMSS (ADR-0018); additive, so ConGen's counters stay byte-identical.
            self.profiler.increment("shared_admpool_checks")
            # Same check at ATOMIC granularity: is_consistent_test_cases issues one
            # solver call PER positive when stop_at_first_violation=False, so the batch
            # counter above understates the real work by |E′⁺| per node. Count the
            # is_consistent_calls DELTA, exactly as the cover step does for QuickXplain
            # (GAP A) — never +1, which would just duplicate the batch counter. Additive:
            # a new key, the two counters above are untouched.
            self.profiler.increment(
                "shared_admpool_solver_calls",
                self.profiler.get_metric("is_consistent_calls", 0) - _solver_before)
            # if E'+ = Φ then return B (all E+ are consistent with current B)
            if len(set_tcp) == 0:
                logging.debug('<<< return %s', set_b)
                return set_b

        # if |B| <= m return Φ (base case)
        if len(set_b) <= self.m:
            logging.debug('<<< return Φ')
            return []

        # B1, B2 = split(B)
        set_b1, set_b2 = split(set_b)

        # Γ2 = AcqMSS(δ=B1, B1, NE, E'+, BG)
        gamma2 = self.find_mss(set_b1, set_b1, set_neg_tv, set_tcp, set_bg)

        # Γ1 = AcqMSS(δ=B1-Γ2, B2, NE, E'+, BG ∪ Γ2)
        b1_without_gamma2 = diff(set_b1, gamma2)
        gamma1 = self.find_mss(b1_without_gamma2, set_b2, set_neg_tv,
                               set_tcp, set_bg + gamma2)

        logging.debug('<<< return [Γ1=%s ∪ Γ2=%s]', gamma1, gamma2)

        # return Γ1 ∪ Γ2
        return gamma1 + gamma2

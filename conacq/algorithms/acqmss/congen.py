"""
ConGen Constraint Acquisition Algorithm.

Orchestrates AcqMSS and REDUCE to acquire a knowledge base from
positive examples and pre-computed NE constraints.

NE generation is performed by callers before invoking ConGen.
ConGen receives pre-computed NE via task.set_neg_tv.

Reference: Paper Algorithm 1 (steps 2-9, NE pre-computed)
    ConGen(E+, NE, B, BG) → KB
    2: B′ ← ∅
    3: if IsConsistent(E⁺, NE, BG) then
    4:   B′ ← AcqMSS(∅, B, NE, E⁺, BG)
    5: else
    6:   print "examples inconsistent"
    7:   return (∅)
    8: end if
    9: return (REDUCE(B′, NE, BG))

Mode-agnostic: works identically regardless of checker type.
"""

import logging
from typing import List, Dict, Optional, Sequence
from dataclasses import dataclass, field

from conacq.algorithms.acqmss import AcqMSS
from .reduce import Reduce
from explanation.api import ConsistencyChecker
from profiling import (
    get_global_profiler, measure_time, count_calls, AbstractProfiler
)


@dataclass
class ConGenResult:
    """Result of ConGen constraint acquisition."""
    kb_assumption_ids: List[int]  # Assumption IDs of acquired constraints
    redundant_ids: List[int]  # Assumption IDs of redundant constraints removed
    n_bias: int  # Number of bias constraints
    n_mss: int  # Size of MSS before Reduce
    n_kb: int  # Size of final KB
    metadata: Dict = field(default_factory=dict)



class ConGen:
    """
    ConGen constraint acquisition algorithm.

    Mode-agnostic: all data is assumption-based (List[int]).
    The checker implementation determines solver lifecycle.
    """

    def __init__(self, checker: ConsistencyChecker,
                 profiler_instance: AbstractProfiler = None) -> None:
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()
        self.result: Optional[ConGenResult] = None

    @measure_time('congen_runtime')
    @count_calls('congen_calls')
    def acquire(
            self,
            set_b: Sequence[int],
            set_bg: Sequence[int],
            set_tc: Sequence[int],
            set_neg_tv: Optional[List[int]] = None,
            negation_map: Optional[Dict[int, int]] = None,
    ) -> ConGenResult:
        """Acquire knowledge base from bias constraints.

        Paper Algorithm 1 (steps 2-9, NE pre-computed):
        2. if IsConsistent(E+, NE, BG) then B' <- AcqMSS(...)
        3. return REDUCE(B', NE, BG)

        Args:
            set_b: Bias constraint assumption IDs (B)
            set_bg: Background knowledge assumption IDs (BG)
            set_tc: Positive example assumption IDs (E+)
            set_neg_tv: Negated example assumption IDs (NE)
            negation_map: Mapping assumption ID -> negated ID (for REDUCE)

        Returns:
            CONGENResult with acquired KB
        """
        set_neg_tv = set_neg_tv or []
        negation_map = negation_map or {}
        # Task solve-fields arrive as immutable tuples; work on lists.
        set_b, set_bg, set_tc, set_neg_tv = (
            list(set_b), list(set_bg), list(set_tc), list(set_neg_tv))

        logging.debug('>>> ConGen [B=%d, NE=%d, E+=%d, BG=%d]',
                      len(set_b), len(set_neg_tv), len(set_tc), len(set_bg))

        # Step 3: if IsConsistent(E⁺, NE, BG) then
        inconsistent = self.checker.is_consistent_test_cases(
            set_neg_tv + set_bg,  # NE ∪ BG
            set_tc,  # E+
            stop_at_first_violation=True
        )
        self.profiler.increment("paper_consistency_checks")

        if len(inconsistent) > 0:
            logging.debug('<<< ConGen return Phi (E+ inconsistent with NE ∪ BG)')
            self.result = ConGenResult(
                kb_assumption_ids=[],
                redundant_ids=[],
                n_bias=len(set_b),
                n_mss=0,
                n_kb=0,
                metadata={'error': 'E+ inconsistent with NE ∪ BG'}
            )
            return self.result

        # Step 4: B′ ← AcqMSS(∅, B, NE, E⁺, BG)
        acqmss = AcqMSS(self.checker, m=1, profiler_instance=self.profiler)
        b_prime = acqmss.find_mss(
            delta=[],
            set_b=set_b,
            set_neg_tv=set_neg_tv,
            set_tc=set_tc,
            set_bg=set_bg
        )
        logging.debug('AcqMSS: MSS size = %d', len(b_prime))

        # Step 9: return Reduce(B′, NE, BG)
        reduce = Reduce(self.checker, self.profiler)
        redundant, kb = reduce.reduce(
            set_b_prime=b_prime,
            set_neg_tv=set_neg_tv,
            set_bg=set_bg,
            negation_map=negation_map
        )
        logging.debug('Reduce: %d redundant, %d in final KB', len(redundant), len(kb))

        self.result = ConGenResult(
            kb_assumption_ids=kb,
            redundant_ids=redundant,
            n_bias=len(set_b),
            n_mss=len(b_prime),
            n_kb=len(kb),
            metadata={
                'n_neg_tv': len(set_neg_tv),
                'n_e_pos': len(set_tc),
            }
        )

        logging.debug('<<< ConGen return KB=%d', len(kb))
        return self.result


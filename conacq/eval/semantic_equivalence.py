"""SAT-based semantic equivalence checker for KB vs ground truth.

Checks KB ≡ C_T via bidirectional entailment:
- KB ⊨ C_T: for each c in C_T, (KB + BG + ¬c) is UNSAT
- C_T ⊨ KB: for each c in KB, (C_T + ¬c) is UNSAT
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from pysat.solvers import Solver


@dataclass
class SemanticResult:
    """Result of semantic equivalence check.

    Attributes:
        kb_entails_ct: True if KB entails every clause in C_T
        ct_entails_kb: True if C_T entails every clause in KB
        is_equivalent: True if both directions hold
        unentailed_ct: C_T clauses NOT entailed by KB
        unentailed_kb: KB clauses NOT entailed by C_T
        n_ct_checked: Total C_T clauses checked
        n_kb_checked: Total KB clauses checked
    """
    kb_entails_ct: bool
    ct_entails_kb: bool
    is_equivalent: bool
    unentailed_ct: List[Tuple[int, ...]]
    unentailed_kb: List[Tuple[int, ...]]
    n_ct_checked: int
    n_kb_checked: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'kb_entails_ct': self.kb_entails_ct,
            'ct_entails_kb': self.ct_entails_kb,
            'is_equivalent': self.is_equivalent,
            'unentailed_ct': [list(c) for c in self.unentailed_ct[:20]],
            'unentailed_kb': [list(c) for c in self.unentailed_kb[:20]],
            'n_ct_checked': self.n_ct_checked,
            'n_kb_checked': self.n_kb_checked,
        }


class SemanticEquivalenceChecker:
    """SAT-based semantic equivalence checker.

    Checks KB ≡ C_T via bidirectional entailment.
    Uses pysat Solver directly (lightweight, no checker model overhead).
    """

    def __init__(
        self,
        kb_clauses: Sequence[Sequence[int]],
        ct_clauses: Sequence[Sequence[int]],
        bg_clauses: Optional[Sequence[Sequence[int]]] = None,
        solver_name: str = 'glucose4'
    ):
        # Eval-boundary consumer: inputs may be frozen tuples (root_clauses/set_kb are
        # deep-frozen) or lists (learned KB). Normalise the outer container to a list so
        # the internal ``kb + bg`` / ``source + negated`` concatenations never hit
        # ``list + tuple``. Inner clauses stay as-is — pysat accepts tuple clauses.
        self.kb_clauses = list(kb_clauses)
        self.ct_clauses = list(ct_clauses)
        self.bg_clauses = list(bg_clauses or [])
        self.solver_name = solver_name

    def _check_entails(
        self,
        source_clauses: List[List[int]],
        target_clauses: List[List[int]]
    ) -> Tuple[bool, List[Tuple[int, ...]]]:
        """Check if source entails every clause in target.

        For each clause c in target: negate c as unit clauses,
        check SAT(source + negated). If SAT -> c is NOT entailed.

        Returns:
            (all_entailed, list_of_unentailed_clauses)
        """
        unentailed = []
        for clause in target_clauses:
            negated = [[-lit] for lit in clause]
            formula = source_clauses + negated
            with Solver(name=self.solver_name, bootstrap_with=formula) as solver:
                if solver.solve():  # SAT -> not entailed
                    unentailed.append(tuple(sorted(clause)))
        return len(unentailed) == 0, unentailed

    def check_kb_entails_ct(self) -> Tuple[bool, List[Tuple[int, ...]]]:
        """Does KB (+ BG) entail every clause in C_T?"""
        source = self.kb_clauses + self.bg_clauses
        return self._check_entails(source, self.ct_clauses)

    def check_ct_entails_kb(self) -> Tuple[bool, List[Tuple[int, ...]]]:
        """Does C_T entail every clause in KB? (BG excluded from targets)"""
        return self._check_entails(self.ct_clauses, self.kb_clauses)

    def check_equivalence(self) -> SemanticResult:
        """Full bidirectional equivalence check."""
        kb_ok, unentailed_ct = self.check_kb_entails_ct()
        ct_ok, unentailed_kb = self.check_ct_entails_kb()
        return SemanticResult(
            kb_entails_ct=kb_ok,
            ct_entails_kb=ct_ok,
            is_equivalent=kb_ok and ct_ok,
            unentailed_ct=unentailed_ct,
            unentailed_kb=unentailed_kb,
            n_ct_checked=len(self.ct_clauses),
            n_kb_checked=len(self.kb_clauses),
        )

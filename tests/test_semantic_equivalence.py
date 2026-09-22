"""Tests for SAT-based semantic equivalence checker."""

import pytest
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker, SemanticResult


class TestSemanticEquivalenceChecker:
    """Test SemanticEquivalenceChecker."""

    def test_equivalent_sets(self):
        """KB == C_T -> both directions True."""
        clauses = [[1, 2], [-1, 3]]
        checker = SemanticEquivalenceChecker(
            kb_clauses=clauses, ct_clauses=clauses)
        result = checker.check_equivalence()
        assert result.is_equivalent is True
        assert result.kb_entails_ct is True
        assert result.ct_entails_kb is True
        assert result.unentailed_ct == []
        assert result.unentailed_kb == []

    def test_accepts_frozen_tuple_bg_clauses(self):
        """A real ConGen result has kb_clauses as a list but bg_clauses as a frozen
        tuple-of-tuples (OracleData.root_clauses is deep-frozen). check_kb_entails_ct
        does ``kb_clauses + bg_clauses`` — list + tuple raised TypeError, crashing
        progressive_evaluation / cross-validation (paths no other test drives). The
        checker must normalise both containers at its boundary."""
        kb = [[1, 2], [-1, 3]]        # learned KB — a list
        bg = ((4, -1),)               # frozen root clauses — a tuple of tuples
        ct = [[1, 2], [-1, 3]]
        checker = SemanticEquivalenceChecker(kb_clauses=kb, ct_clauses=ct, bg_clauses=bg)
        result = checker.check_equivalence()   # would TypeError on list + tuple pre-fix
        assert isinstance(result, SemanticResult)
        assert result.n_kb_checked == 2

    def test_kb_superset_of_ct(self):
        """KB has extra clauses -> KB entails C_T, C_T may not entail KB."""
        kb = [[1, 2], [-1, 3], [4]]  # KB has extra [4]
        ct = [[1, 2], [-1, 3]]
        checker = SemanticEquivalenceChecker(kb_clauses=kb, ct_clauses=ct)
        result = checker.check_equivalence()
        assert result.kb_entails_ct is True
        assert result.ct_entails_kb is False
        assert result.is_equivalent is False

    def test_kb_subset_of_ct(self):
        """KB missing clauses -> C_T entails KB, KB may not entail C_T."""
        kb = [[1, 2]]
        ct = [[1, 2], [-1, 3]]
        checker = SemanticEquivalenceChecker(kb_clauses=kb, ct_clauses=ct)
        result = checker.check_equivalence()
        assert result.ct_entails_kb is True
        assert result.kb_entails_ct is False
        assert result.is_equivalent is False

    def test_empty_kb(self):
        """Empty KB entails nothing (except tautologies)."""
        ct = [[1, 2], [-1]]
        checker = SemanticEquivalenceChecker(kb_clauses=[], ct_clauses=ct)
        result = checker.check_equivalence()
        assert result.kb_entails_ct is False
        assert result.ct_entails_kb is True  # C_T entails empty set trivially

    def test_bg_clauses_help_entailment(self):
        """BG clauses contribute to KB entailing C_T."""
        # KB alone: [[1]], BG: [[2]], C_T: [[1], [2]]
        # KB+BG entails both clauses in C_T
        checker = SemanticEquivalenceChecker(
            kb_clauses=[[1]], ct_clauses=[[1], [2]], bg_clauses=[[2]])
        result = checker.check_equivalence()
        assert result.kb_entails_ct is True

    def test_negation_correctness(self):
        """Verify clause [a, b] negated correctly as [[-a], [-b]]."""
        # C_T = [[1, 2]], KB = [[1]] (doesn't entail [1,2] alone)
        # SAT(KB + [-1] + [-2]) = SAT([[1], [-1], [-2]]) = UNSAT? No:
        #   [1] forces 1=T, [-1] forces 1=F -> UNSAT. So [1] entails nothing? Wait.
        # Actually: SAT([[1]] + [[-1], [-2]]) where neg([1,2]) = [[-1], [-2]]
        # [[1], [-1], [-2]] -> clause [1] satisfied by 1=T, but [-1] forces 1=F -> UNSAT
        # So KB=[[1]] entails [1,2]? Yes! Because [[1]] implies literal 1 is true,
        # which satisfies [1,2]. Correct.
        checker = SemanticEquivalenceChecker(
            kb_clauses=[[1]], ct_clauses=[[1, 2]])
        ok, unentailed = checker.check_kb_entails_ct()
        assert ok is True

    def test_to_dict(self):
        """Verify to_dict produces correct structure."""
        result = SemanticResult(
            kb_entails_ct=True,
            ct_entails_kb=False,
            is_equivalent=False,
            unentailed_ct=[],
            unentailed_kb=[(1, 2)],
            n_ct_checked=5,
            n_kb_checked=3
        )
        d = result.to_dict()
        assert d['kb_entails_ct'] is True
        assert d['ct_entails_kb'] is False
        assert d['is_equivalent'] is False
        assert d['n_ct_checked'] == 5
        assert d['unentailed_kb'] == [[1, 2]]

    def test_both_empty(self):
        """Both empty -> trivially equivalent."""
        checker = SemanticEquivalenceChecker(kb_clauses=[], ct_clauses=[])
        result = checker.check_equivalence()
        assert result.is_equivalent is True

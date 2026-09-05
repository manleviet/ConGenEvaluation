"""Converter A — rule set to CNF (C4).

No learner library needed: these drive the converter with hand-built rule sets, so
they run on a clean environment and pin the conversion independently of whatever
RIPPER or CN2 happen to induce.
"""
import pytest

from conacq.baselines import build_feature_table
from conacq.baselines.rule_cnf import Rule, is_degenerate, rules_to_cnf
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker

# Non-alphabetical, non-contiguous ids — see test_baselines_feature_table.
CATALOG = {"a": 2, "b": 5, "c": 1}
POS = [{"a": True, "b": True, "c": True}]
NEG = [{"a": False, "b": False, "c": False}]


# Column order used by MOST fixtures below is deliberately NOT the id-sorted default.
# Sorted-by-id order makes column index and variable id coincide (ids are contiguous
# from 1 on every KB here), so an index-paired converter would agree with almost every
# assertion. Permuting by default makes such a converter fail broadly instead of only
# in the one canary.
PERMUTED = ("a", "b", "c")


def _table(order=PERMUTED):
    return build_feature_table(POS, NEG, CATALOG, feature_order=order)


def _canonical_table():
    """Id-sorted column order — the production default."""
    return build_feature_table(POS, NEG, CATALOG)


def _equivalent(cnf, expected):
    """Semantic equality, not list equality — a different but equivalent clause
    ordering must pass, a genuinely different theory must not."""
    return SemanticEquivalenceChecker(
        [list(c) for c in cnf], [list(c) for c in expected], []
    ).check_equivalence().is_equivalent


def test_hand_built_rule_set_matches_hand_written_cnf():
    """Two rules over three features against a CNF written out by hand.

    rule 1: a ∧ ¬b  ⇒ invalid   ⇒ clause (¬a ∨ b)  = [-2, 5]
    rule 2: c       ⇒ invalid   ⇒ clause (¬c)      = [-1]
    """
    t = _table()
    rules = [Rule.of(("a", True), ("b", False)), Rule.of(("c", True))]
    cnf = rules_to_cnf(rules, t)

    assert cnf == [[-2, 5], [-1]]
    assert _equivalent(cnf, [[-2, 5], [-1]])


def test_single_literal_rule_flips_the_sign():
    """Catches a missing negation, which an all-conjunctions fixture can hide."""
    t = _table()
    assert rules_to_cnf([Rule.of(("a", True))], t) == [[-2]]
    assert rules_to_cnf([Rule.of(("a", False))], t) == [[2]]


def test_empty_rule_set_is_top_and_is_reported_degenerate():
    """No rules ⇒ empty CNF ⇒ accepts everything.

    Pinned deliberately: this is the frequent case when the fold gives the learner too
    few instances of the target class, and the eval layer must MARK it rather than
    score it.
    """
    t = _table()
    assert rules_to_cnf([], t) == []
    assert is_degenerate([]) is True
    assert is_degenerate([Rule.of(("a", True))]) is False


def test_unconditional_rule_is_bottom_not_dropped():
    """A rule with no conditions fires always ⇒ empty clause ⇒ rejects everything.

    Dropping it would turn 'everything is invalid' into 'nothing is constrained' —
    the opposite theory — so the empty clause is emitted on purpose.
    """
    t = _table()
    assert rules_to_cnf([Rule.of()], t) == [[]]


def test_repeated_literal_in_a_rule_is_deduplicated():
    t = _table()
    assert rules_to_cnf([Rule.of(("a", True), ("a", True))], t) == [[-2]]


def test_contradictory_rule_becomes_a_tautological_clause():
    """A rule testing one feature both ways can never fire; its clause holds both
    polarities and is harmless. Pinned so a future 'simplification' that drops such
    clauses has to justify proving the rule unsatisfiable first."""
    t = _table()
    clause = rules_to_cnf([Rule.of(("a", True), ("a", False))], t)[0]
    assert sorted(clause) == [-2, 2]


def test_cnf_is_invariant_under_column_permutation():
    """The CNF-level permutation canary.

    Same rule set, two tables differing only in column ORDER, must give byte-identical
    CNF. A converter pairing column index with variable id fails here; this one maps
    by name. Complements the table-level canary, which only checks literals.
    """
    default = _canonical_table()
    permuted = _table(order=tuple(reversed(default.feature_names)))
    rules = [Rule.of(("a", True), ("b", False)), Rule.of(("c", True))]

    assert rules_to_cnf(rules, default) == rules_to_cnf(rules, permuted)


def test_cnf_rejects_exactly_the_configurations_the_rules_call_invalid():
    """End-to-end semantics over the whole 3-feature space, not a sampled few.

    For all 8 assignments: the CNF is satisfied iff no rule fires. This is the
    property the conversion claims, checked exhaustively rather than by example.
    """
    import itertools

    t = _table()
    rules = [Rule.of(("a", True), ("b", False)), Rule.of(("c", True))]
    cnf = rules_to_cnf(rules, t)

    for combo in itertools.product([False, True], repeat=3):
        assignment = dict(zip(("a", "b", "c"), combo))
        fires = any(r.fires_on(assignment) for r in rules)
        model = {t.literal(f, v) for f, v in assignment.items()}
        satisfied = all(any(lit in model for lit in clause) for clause in cnf)
        assert satisfied == (not fires), f"{assignment}: fires={fires} sat={satisfied}"

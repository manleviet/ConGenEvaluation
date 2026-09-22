"""Learner adapters — RIPPER, CN2, decision tree (C4).

Each test skips when its library is absent, so a clean environment still collects.
The data below is separable by one feature, so all three learners have a known right
answer and the adapters can be compared against it rather than against each other.
"""
import pytest

from conacq.baselines import build_feature_table
from conacq.baselines.rule_cnf import Rule, rules_to_cnf

CATALOG = {"a": 2, "b": 5, "c": 1}
# 'a' alone decides the class: a=True ⇒ valid, a=False ⇒ invalid.
POS = [{"a": True, "b": True, "c": False},
       {"a": True, "b": False, "c": False},
       {"a": True, "b": True, "c": True}]
NEG = [{"a": False, "b": False, "c": False},
       {"a": False, "b": True, "c": True},
       {"a": False, "b": False, "c": True}]

# Determinism needs a TIE-PRONE table: no single feature separates the classes, so the
# learner must break ties. On the separable table above CN2 converges to the same rules
# with or without a seed reset, and a determinism test there passes vacuously — measured,
# not assumed (removing the reset left it green three runs in a row).
TIE_POS = [{"a": True, "b": True, "c": False},
           {"a": False, "b": True, "c": True},
           {"a": True, "b": False, "c": True}]
TIE_NEG = [{"a": False, "b": False, "c": False},
           {"a": True, "b": True, "c": True},
           {"a": False, "b": False, "c": True}]


def _table(order=None):
    return build_feature_table(POS, NEG, CATALOG, feature_order=order)


def _learner(name):
    mod = {"ripper": "wittgenstein", "cn2": "Orange", "decision_tree": "sklearn"}[name]
    pytest.importorskip(mod, reason=f"{name} needs the baselines extra")
    from conacq.baselines.learners import LEARNERS
    return LEARNERS[name]


@pytest.mark.parametrize("name", ["ripper", "cn2", "decision_tree"])
def test_learner_recovers_the_separating_condition(name):
    """On data separable by one feature, every learner must find that feature.

    Compared against the known answer, not against the other learners — three adapters
    agreeing on a wrong rule would otherwise look like corroboration.
    """
    fn = _learner(name)
    table = _table()
    rules = fn(table)

    assert rules, f"{name} learned nothing on separable data"
    assert all(("a", False) in r.conditions for r in rules), \
        f"{name} rules do not test the separating feature: {[r.conditions for r in rules]}"
    assert rules_to_cnf(rules, table) == [[2]] * len(rules)


@pytest.mark.parametrize("name", ["ripper", "cn2", "decision_tree"])
def test_learner_is_deterministic_across_repeated_fits(name):
    """Same table, same seed, repeated fits ⇒ identical rules.

    Pins the property the reported numbers depend on: a baseline that moved between
    runs of the same fold could not be reported at all.

    NON-DISCRIMINATING FOR CN2 ON THIS FIXTURE, measured rather than assumed. Orange's
    full rule list really does vary across fits without a seed reset (2 distinct forms
    over 20 fits), but the subset this adapter keeps is stable at 1 with or without it —
    the variation is confined to the VALID-class rules and the catch-all, which the
    adapter discards. Removing the reset therefore leaves this green HERE; that is one
    sample, and on another fold or KB the variation could reach the kept rules. It still
    guards RIPPER and the tree, and would catch a CN2 whose kept rules start moving.
    """
    fn = _learner(name)
    table = build_feature_table(TIE_POS, TIE_NEG, CATALOG)
    runs = [fn(table) for _ in range(6)]
    assert all(r == runs[0] for r in runs), \
        f"{name} is nondeterministic across fits: {[len(r) for r in runs]}"


@pytest.mark.parametrize("name", ["ripper", "cn2", "decision_tree"])
def test_learner_output_is_independent_of_column_order(name):
    """Permuting the table's columns must not change the learned CNF.

    The adapters name features back through the table they trained on, so a permuted
    table trains a permuted matrix and resolves through the matching order. A wrapper
    that took names from anywhere else would produce a CNF over the wrong variables
    here — the gap the table-level and CNF-level canaries cannot reach, because they
    keep one consistent order throughout.
    """
    fn = _learner(name)
    canonical = _table()
    permuted = _table(order=("a", "b", "c"))

    cnf_canonical = sorted(sorted(c) for c in rules_to_cnf(fn(canonical), canonical))
    cnf_permuted = sorted(sorted(c) for c in rules_to_cnf(fn(permuted), permuted))
    assert cnf_canonical == cnf_permuted


def test_cn2_selectors_are_equality_on_a_binary_domain():
    """The CN2 assumption the plan flagged, checked against Orange rather than trusted.

    Orange emits ``==`` AND ``!=`` against 0/1 — the plan predicted ``==`` only, and the
    adapter's guard caught the difference on real data. Both are exact on a two-valued
    domain. An order operator (``<=``/``>=``) has no boolean reading, so the adapter
    raises on it; this pins the shape the translation relies on.
    """
    pytest.importorskip("Orange", reason="cn2 needs the baselines-cn2 extra")
    import numpy as np
    from Orange.classification.rules import CN2UnorderedLearner
    from Orange.data import DiscreteVariable, Domain, Table

    from conacq.baselines.learners import _seed_global_rngs

    table = _table()
    X = [[1 if c else 0 for c in row] for row in table.rows]
    attrs = [DiscreteVariable(n, values=("0", "1")) for n in table.feature_names]
    cls = DiscreteVariable("__class__", values=("0", "1"))
    data = Table.from_numpy(Domain(attrs, cls), np.array(X, dtype=float),
                            np.array([int(l) for l in table.labels], dtype=float))
    _seed_global_rngs(42)
    classifier = CN2UnorderedLearner()(data)

    seen_ops = {s.op for r in classifier.rule_list for s in r.selectors}
    seen_vals = {float(s.value) for r in classifier.rule_list for s in r.selectors}
    # Measured, not predicted: Orange emits '!=' as well as '==' on a binary domain.
    # The plan assumed '==' only; the adapter's guard caught the difference on real
    # data. Both have an exact boolean reading; an ORDER operator would not.
    assert seen_ops <= {"==", "!="}, f"Orange emitted an order selector: {seen_ops}"
    assert seen_vals <= {0.0, 1.0}, f"Orange emitted non-binary values: {seen_vals}"

    # And the catch-all the adapter drops really is selector-free.
    catch_alls = [r for r in classifier.rule_list if not r.selectors]
    assert len(catch_alls) == 1, \
        f"expected exactly one catch-all rule, got {len(catch_alls)}"


def test_cn2_drops_only_the_selector_free_catch_all():
    """The dropped rule is the fallback, not a learned condition.

    Guards the adapter's one editorial decision: every INVALID rule with selectors is
    kept, and exactly the selector-free one is discarded. Keeping it would make the
    theory reject every configuration.
    """
    pytest.importorskip("Orange", reason="cn2 needs the baselines-cn2 extra")
    import numpy as np
    from Orange.classification.rules import CN2UnorderedLearner
    from Orange.data import DiscreteVariable, Domain, Table

    from conacq.baselines.learners import _seed_global_rngs, learn_cn2

    table = _table()
    X = [[1 if c else 0 for c in row] for row in table.rows]
    attrs = [DiscreteVariable(n, values=("0", "1")) for n in table.feature_names]
    cls = DiscreteVariable("__class__", values=("0", "1"))
    data = Table.from_numpy(Domain(attrs, cls), np.array(X, dtype=float),
                            np.array([int(l) for l in table.labels], dtype=float))
    _seed_global_rngs(42)
    raw = CN2UnorderedLearner()(data)

    kept_by_adapter = learn_cn2(table)
    expected = [r for r in raw.rule_list if int(r.prediction) == 1 and r.selectors]
    assert len(kept_by_adapter) == len(expected)
    # No adapter rule is unconditional — that is the shape that would give ⊥.
    assert all(r.conditions for r in kept_by_adapter)


@pytest.mark.parametrize("name", ["ripper", "cn2", "decision_tree"])
def test_single_class_table_does_not_invent_conditions(name):
    """With no negatives at all, no learner may emit a conditional rule.

    This is the frequent degenerate cell. Whatever each library does internally, the
    adapter must not hand back a rule that looks learned — the caller marks the cell,
    and a fabricated condition would be scored as a finding.
    """
    fn = _learner(name)
    table = build_feature_table(POS, [], CATALOG)
    rules = fn(table)
    assert all(not r.conditions for r in rules), \
        f"{name} invented conditions from a single-class table: {[r.conditions for r in rules]}"


def test_cn2_selector_translation_matches_orange_evaluation():
    """Every translated rule fires on exactly the rows Orange says it fires on.

    The independent oracle is Orange's own ``Rule.evaluate_data`` over the ORIGINAL
    table, so this cannot be satisfied by agreeing with the translation under test.
    (``covered_examples`` is NOT usable here — Orange shrinks its working set while
    learning, so those masks have different lengths than the table.)

    This is the test the '!=' handling needed. Orange emits '!=' as well as '==' on a
    binary domain, and on two values '!=' is the opposite equality — so the adapter
    flips the polarity. Dropping that flip left all other adapter tests green, which is
    exactly the silent-wrong-rule mode the guard exists to prevent.
    """
    pytest.importorskip("Orange", reason="cn2 needs the baselines-cn2 extra")
    import numpy as np
    from Orange.classification.rules import CN2UnorderedLearner
    from Orange.data import DiscreteVariable, Domain, Table

    from conacq.baselines.feature_table import INVALID
    from conacq.baselines.learners import _seed_global_rngs, learn_cn2

    table = build_feature_table(TIE_POS, TIE_NEG, CATALOG)
    X = np.array([[1 if c else 0 for c in row] for row in table.rows], dtype=float)
    attrs = [DiscreteVariable(n, values=("0", "1")) for n in table.feature_names]
    cls = DiscreteVariable("__class__", values=("0", "1"))
    data = Table.from_numpy(
        Domain(attrs, cls), X,
        np.array([int(l) for l in table.labels], dtype=float))

    _seed_global_rngs(42)
    raw = CN2UnorderedLearner()(data)
    orange_rules = [r for r in raw.rule_list
                    if int(r.prediction) == INVALID and r.selectors]
    translated = learn_cn2(table)
    assert len(translated) == len(orange_rules)
    assert any(any(s.op == "!=" for s in r.selectors) for r in orange_rules), \
        "fixture no longer exercises '!=' — the polarity flip would go untested"

    rows = [dict(zip(table.feature_names, row)) for row in table.rows]
    for orange_rule, mine in zip(orange_rules, translated):
        expected = [bool(v) for v in orange_rule.evaluate_data(X)]
        actual = [mine.fires_on(r) for r in rows]
        assert actual == expected, (
            f"translated rule {mine.conditions} fires on {actual} but Orange's "
            f"{[(s.column, s.op, float(s.value)) for s in orange_rule.selectors]} "
            f"fires on {expected}")

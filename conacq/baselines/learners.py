"""Learner adapters — RIPPER, CN2, decision tree → a rule list (C4).

Each adapter takes a ``FeatureTable`` and returns ``List[Rule]`` for converter A. All
three libraries are imported LAZILY inside their adapter, so importing this module on
a machine without the ``baselines`` / ``baselines-cn2`` extras is safe and their tests
skip rather than erroring at collection.

The table is the single source of column order everywhere: each adapter builds its
learner's input FROM the table and names features back through the same table, so a
train-order/convert-order mismatch is unrepresentable rather than merely tested for.

Determinism. Measured 2026-08-23: repeated CN2 fits on identical data produce
GENUINELY DIFFERENT rule lists (not merely reordered) unless the global RNGs are reset
immediately before each fit. sklearn and wittgenstein take an explicit ``random_state``
instead. Every adapter is pinned to a seed — a baseline that changed between runs of
the same fold could not be reported at all.

HOW FAR THAT IS ACTUALLY DEMONSTRATED, so the seed reset is not mistaken for a tested
guarantee. ON ONE TIE-PRONE FIXTURE, over 20 fits: the FULL Orange rule list has 2
distinct forms without the reset and 1 with it, while the subset this adapter keeps
(INVALID rules carrying selectors) is stable at 1 either way — the variation sits in
what the adapter discards, the VALID-class rules and the catch-all. That is ONE SAMPLE,
not a proof: on another fold or KB the variation could reach the kept rules. So the
reset is insurance against a real nondeterminism whose effect happens not to be
observable at this boundary here, and the determinism test cannot fail for CN2 by
removing it. Kept because the nondeterminism is real and the reset costs nothing.
"""
from __future__ import annotations

from typing import List, Tuple

from .feature_table import INVALID, VALID, FeatureTable
from .rule_cnf import Rule

DEFAULT_SEED = 42


def _matrix(table: FeatureTable) -> Tuple[List[List[int]], List[int]]:
    """The table as 0/1 rows plus labels, in the table's own column order."""
    X = [[1 if cell else 0 for cell in row] for row in table.rows]
    y = [int(lab) for lab in table.labels]
    return X, y


def _seed_global_rngs(seed: int) -> None:
    """Reset the RNGs Orange's CN2 draws on. See the module note on determinism."""
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)


def learn_decision_tree(table: FeatureTable, random_state: int = DEFAULT_SEED) -> List[Rule]:
    """Fit a decision tree and reduce it to rules (converter B)."""
    from sklearn.tree import DecisionTreeClassifier

    from .tree_rules import sklearn_tree_to_rules

    # A single-class table fits a single leaf; tree_rules reduces that correctly
    # (one unconditional rule, or none), and the caller marks the cell degenerate.
    X, y = _matrix(table)
    clf = DecisionTreeClassifier(random_state=random_state).fit(X, y)
    return sklearn_tree_to_rules(clf, table)


def learn_ripper(table: FeatureTable, random_state: int = DEFAULT_SEED) -> List[Rule]:
    """Fit RIPPER (wittgenstein) and read off its rule set.

    wittgenstein learns a DNF for the POSITIVE class and predicts negative when no rule
    fires — exactly the semantics converter A assumes, so the rule set transfers
    directly. ``pos_class`` is passed explicitly rather than left to inference: the
    positive class here is INVALID, and inferring it would silently invert the theory
    on a fold where the majority flips.
    """
    import pandas as pd
    import wittgenstein as lw

    X, y = _matrix(table)
    df = pd.DataFrame(X, columns=list(table.feature_names))
    df["__class__"] = y

    clf = lw.RIPPER(random_state=random_state)
    clf.fit(df, class_feat="__class__", pos_class=INVALID)

    rules: List[Rule] = []
    for rule in clf.ruleset_.rules:
        conditions: List[Tuple[str, bool]] = []
        for cond in rule.conds:
            conditions.append((str(cond.feature), _as_bool(cond.val, str(cond.feature))))
        rules.append(Rule(tuple(conditions)))
    return rules


def learn_cn2(table: FeatureTable, random_state: int = DEFAULT_SEED) -> List[Rule]:
    """Fit CN2 (Orange3) and read off the rules predicting INVALID.

    Uses ``CN2UnorderedLearner``, NOT ``CN2Learner``. The ordered learner's semantics
    are first-match-wins, so a VALID rule appearing before an INVALID one suppresses it;
    OR-ing all INVALID rules into a DNF would then over-predict invalid. An unordered
    rule set is per-class and reads as a DNF directly, which is what converter A needs.

    CN2 always appends a catch-all ``IF TRUE`` rule with no selectors — the classifier's
    majority fallback, not a learned condition. It is DROPPED: as a DNF disjunct it
    would mean "everything is invalid", i.e. converter A's empty clause and a theory
    that rejects every configuration. RIPPER has no such rule (it predicts negative when
    nothing fires), so dropping it also makes the two rule-list learners comparable.
    A fold where CN2 learns nothing but the fallback yields an empty rule set, which the
    caller must report as degenerate rather than score.

    The selector shape is CHECKED, not assumed — and the check paid off. The plan
    predicted Orange would emit only ``==`` on a binary domain; it also emits ``!=``.
    On a two-valued domain that is exact, not approximate (``b != 1`` ⟺ ``b == 0``), so
    it is translated by flipping the polarity. An ORDER operator (``<=`` / ``>=``) has no
    such reading and still raises: silently treating it as a boolean test would emit a
    wrong rule over valid variables, which nothing downstream would reject.
    """
    import numpy as np
    from Orange.classification.rules import CN2UnorderedLearner
    from Orange.data import DiscreteVariable, Domain, Table

    X, y = _matrix(table)
    attrs = [DiscreteVariable(n, values=("0", "1")) for n in table.feature_names]
    cls = DiscreteVariable("__class__", values=(str(VALID), str(INVALID)))
    data = Table.from_numpy(
        Domain(attrs, cls), np.array(X, dtype=float), np.array(y, dtype=float))

    _seed_global_rngs(random_state)
    classifier = CN2UnorderedLearner()(data)

    rules: List[Rule] = []
    for rule in classifier.rule_list:
        if int(rule.prediction) != INVALID:
            continue
        if not rule.selectors:          # the catch-all fallback — see docstring
            continue
        conditions: List[Tuple[str, bool]] = []
        for sel in rule.selectors:
            name = table.feature_names[sel.column]
            if sel.op not in ("==", "!="):
                raise ValueError(
                    f"CN2 selector uses operator {sel.op!r} on feature {name!r}; only "
                    f"'==' and '!=' have an exact boolean reading on a binary domain, "
                    f"and treating an order operator as one would emit a wrong rule")
            value = _as_bool(sel.value, name)
            # '!=' on a two-valued domain is the opposite equality, exactly.
            conditions.append((name, value if sel.op == "==" else not value))
        rules.append(Rule(tuple(conditions)))
    return rules


def _as_bool(value, feature: str) -> bool:
    """Coerce a learner's 0/1 selector value to a boolean, refusing anything else.

    Orange hands back a numpy float, wittgenstein a str or int. Accepting a stray value
    (2, 0.5, 'high') as truthy would invert or fabricate a condition, so the accepted
    set is explicit.
    """
    text = str(value).strip()
    if text in ("0", "0.0", "False", "false"):
        return False
    if text in ("1", "1.0", "True", "true"):
        return True
    raise ValueError(
        f"selector value {value!r} on feature {feature!r} is not binary; the table is "
        f"0/1, so a non-binary value means the learner saw a different domain")


LEARNERS = {
    "ripper": learn_ripper,
    "cn2": learn_cn2,
    "decision_tree": learn_decision_tree,
}

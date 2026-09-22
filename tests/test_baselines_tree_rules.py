"""Converter B — decision tree to rule list (C4).

Trees are hand-built from plain lists in sklearn's flat layout, so these run without
sklearn installed and pin the reduction independently of what the learner induces.
One test does use sklearn, to check the hand-built layout still matches the real one.
"""
import pytest

from conacq.baselines import build_feature_table
from conacq.baselines.rule_cnf import Rule, rules_to_cnf
from conacq.baselines.tree_rules import flat_tree_to_rules

CATALOG = {"a": 2, "b": 5, "c": 1}
POS = [{"a": True, "b": True, "c": True}]
NEG = [{"a": False, "b": False, "c": False}]
NAMES = ("a", "b", "c")  # tree feature INDICES address this list

LEAF = -2


def test_two_level_tree_gives_the_path_to_the_invalid_leaf():
    """       split a
             /       \\
        (a=0) leaf    leaf (a=1)
        invalid       valid

    One invalid leaf reached by going left ⇒ rule (a == False).
    """
    rules = flat_tree_to_rules(
        feature=[0, LEAF, LEAF], threshold=[0.5, -2.0, -2.0],
        children_left=[1, -1, -1], children_right=[2, -1, -1],
        leaf_class=[0, 1, 0], feature_names=NAMES)
    assert rules == [Rule.of(("a", False))]


def test_left_is_false_and_right_is_true():
    """Both branches invalid ⇒ both polarities appear, in the right order.

    Pins the branch reading itself: swapping left/right would still produce two rules,
    so a test with a single invalid leaf could not tell the difference.
    """
    rules = flat_tree_to_rules(
        feature=[0, LEAF, LEAF], threshold=[0.5, -2.0, -2.0],
        children_left=[1, -1, -1], children_right=[2, -1, -1],
        leaf_class=[0, 1, 1], feature_names=NAMES)
    assert rules == [Rule.of(("a", False)), Rule.of(("a", True))]


def test_deeper_path_accumulates_conditions_in_order():
    """       split a
             /       \\
       (a=0) split b  leaf valid
            /      \\
      (b=0) valid   invalid (b=1)

    ⇒ rule (a == False ∧ b == True)
    """
    rules = flat_tree_to_rules(
        feature=[0, 1, LEAF, LEAF, LEAF], threshold=[0.5, 0.5, -2.0, -2.0, -2.0],
        children_left=[1, 3, -1, -1, -1], children_right=[4, 2, -1, -1, -1],
        leaf_class=[0, 0, 1, 0, 0], feature_names=NAMES)
    assert rules == [Rule.of(("a", False), ("b", True))]


def test_single_invalid_leaf_is_one_unconditional_rule():
    """A tree with no splits that calls everything invalid ⇒ ⊥ after converter A."""
    rules = flat_tree_to_rules(
        feature=[LEAF], threshold=[-2.0], children_left=[-1], children_right=[-1],
        leaf_class=[1], feature_names=NAMES)
    assert rules == [Rule.of()]
    assert rules_to_cnf(rules, build_feature_table(POS, NEG, CATALOG,
                                           feature_order=("a", "b", "c"))) == [[]]


def test_single_valid_leaf_is_no_rules():
    rules = flat_tree_to_rules(
        feature=[LEAF], threshold=[-2.0], children_left=[-1], children_right=[-1],
        leaf_class=[0], feature_names=NAMES)
    assert rules == []


def test_non_binary_threshold_is_refused():
    """A threshold outside (0,1) means the inputs were not binary, so left=false is
    the wrong reading — raise rather than emit inverted rules."""
    with pytest.raises(ValueError, match="not binary"):
        flat_tree_to_rules(
            feature=[0, LEAF, LEAF], threshold=[3.5, -2.0, -2.0],
            children_left=[1, -1, -1], children_right=[2, -1, -1],
            leaf_class=[0, 1, 0], feature_names=NAMES)


def test_tree_front_end_agrees_with_converter_a_directly():
    """Converter B ∘ A equals A applied to the equivalent hand-written rule.

    This is the composition claim: the tree path is not a separate CNF route, it is
    the same Rule reached another way.
    """
    # Permuted on purpose: id-sorted order would let index-pairing agree.
    table = build_feature_table(POS, NEG, CATALOG, feature_order=("a", "b", "c"))
    via_tree = flat_tree_to_rules(
        feature=[0, LEAF, LEAF], threshold=[0.5, -2.0, -2.0],
        children_left=[1, -1, -1], children_right=[2, -1, -1],
        leaf_class=[0, 1, 0], feature_names=NAMES)
    assert rules_to_cnf(via_tree, table) == rules_to_cnf([Rule.of(("a", False))], table)


def test_real_sklearn_tree_matches_the_hand_built_layout():
    """Guards the premise the hand-built trees rest on.

    Every test above encodes sklearn's flat layout by hand — leaf sentinel -2, left
    child = x <= threshold, threshold 0.5 on binary input. If sklearn changed any of
    that, those tests would keep passing while the production path broke. Fit a real
    tree on data whose answer is known and check the reduction agrees.
    """
    sklearn = pytest.importorskip("sklearn", reason="baselines extra not installed")
    from sklearn.tree import DecisionTreeClassifier

    from conacq.baselines.tree_rules import sklearn_tree_to_rules

    # 'a' alone decides the class: a=0 ⇒ invalid(1), a=1 ⇒ valid(0).
    X = [[0, 0, 0], [0, 1, 1], [1, 0, 1], [1, 1, 0]]
    y = [1, 1, 0, 0]
    clf = DecisionTreeClassifier(random_state=0).fit(X, y)

    # The wrapper takes the TABLE the estimator was fitted on, so the column order and
    # the names cannot come from two sources and disagree.
    table = build_feature_table(POS, NEG, CATALOG, feature_order=NAMES)
    assert sklearn_tree_to_rules(clf, table) == [Rule.of(("a", False))]
    # And the sentinel/threshold conventions the hand-built fixtures assume still hold.
    assert clf.tree_.feature[0] == 0
    assert 0.0 < clf.tree_.threshold[0] < 1.0
    assert int(clf.tree_.feature[clf.tree_.children_left[0]]) == LEAF


def test_estimator_fitted_on_a_different_width_table_is_refused():
    """Belt to the structural braces: a foreign estimator is caught by width.

    Passing the table removes the order-mismatch by construction, but nothing stops a
    caller handing over an estimator fitted on a DIFFERENT table. Width catches the
    common case; a same-width permutation would not be caught, which is exactly why
    the order is derived from the table rather than checked.
    """
    pytest.importorskip("sklearn", reason="baselines extra not installed")
    from sklearn.tree import DecisionTreeClassifier

    from conacq.baselines.tree_rules import sklearn_tree_to_rules

    clf = DecisionTreeClassifier(random_state=0).fit([[0, 0], [1, 1]], [1, 0])
    table = build_feature_table(POS, NEG, CATALOG)   # 3 features, estimator saw 2
    with pytest.raises(ValueError, match="not trained on this table"):
        sklearn_tree_to_rules(clf, table)

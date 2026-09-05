"""Converter B — a fitted decision tree to the rule list converter A consumes (C4).

A decision tree is not a third conversion path: every root→leaf path whose leaf
predicts ``invalid`` IS a conjunction of feature tests, i.e. exactly a ``Rule``. So
this module reduces the tree to a rule list and converter A does the CNF, which keeps
one CNF core behind two front ends.

Works on the FLAT ARRAY layout scikit-learn exposes as ``tree_`` (``feature``,
``threshold``, ``children_left``, ``children_right``) rather than on the estimator,
so it carries no sklearn import and a test can hand-build a tree from plain lists.
The thin unpacking of a fitted estimator lives with the learner adapter.

THE BINARY-SPLIT ASSUMPTION IS CHECKED, NOT ASSUMED. The table is 0/1, so sklearn
splits at ``x <= 0.5``: left is the feature-false branch, right feature-true. If a
threshold ever falls outside (0, 1) the inputs were not binary and that reading is
wrong, so this raises instead of silently emitting inverted rules.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .feature_table import INVALID, FeatureTable
from .rule_cnf import Rule

# sklearn marks a leaf with this sentinel in `tree_.feature`.
_LEAF = -2


def flat_tree_to_rules(
        feature: Sequence[int],
        threshold: Sequence[float],
        children_left: Sequence[int],
        children_right: Sequence[int],
        leaf_class: Sequence[int],
        feature_names: Sequence[str],
) -> List[Rule]:
    """Enumerate root→leaf paths ending in an ``invalid`` leaf.

    ``leaf_class`` is the predicted class per node (only read at leaves). Internal
    nodes are marked by ``feature[node] == -2`` (sklearn's ``TREE_UNDEFINED``).

    A tree that is a single ``invalid`` leaf yields ONE unconditional rule, which
    converter A turns into the empty clause (⊥, rejects everything) — the honest
    reading of "this tree calls everything invalid". A single ``valid`` leaf yields no
    rules (⊤). Both are degenerate and the caller must mark them, not score them.
    """
    if not (len(feature) == len(threshold) == len(children_left)
            == len(children_right) == len(leaf_class)):
        raise ValueError("tree arrays have mismatched lengths")

    rules: List[Rule] = []

    def walk(node: int, path: Tuple[Tuple[str, bool], ...]) -> None:
        if feature[node] == _LEAF:
            if leaf_class[node] == INVALID:
                rules.append(Rule(path))
            return

        thr = threshold[node]
        if not 0.0 < thr < 1.0:
            raise ValueError(
                f"node {node} splits feature {feature[node]} at threshold {thr}, "
                f"outside (0, 1): the table is not binary, so the "
                f"left=false/right=true reading would emit inverted rules")

        name = feature_names[feature[node]]
        # x <= thr  ⇒ feature is 0 (false); the right child is the true branch.
        walk(children_left[node], path + ((name, False),))
        walk(children_right[node], path + ((name, True),))

    walk(0, ())
    return rules


def sklearn_tree_to_rules(estimator, table: FeatureTable) -> List[Rule]:
    """Unpack a fitted ``DecisionTreeClassifier`` into ``flat_tree_to_rules``.

    Takes the TABLE, not a bare name list, on purpose. A tree's ``feature`` array holds
    column INDICES; naming them needs the column order the estimator was trained on. If
    that order and the names arrived as two independent arguments they could disagree,
    and then this emits correct-looking rules over the WRONG features: converter A
    faithfully turns them into a CNF over valid variables, nothing raises, and accuracy
    lands somewhere plausible. Deriving the order from the same table the estimator was
    fitted on leaves nothing to diverge — the misuse becomes unrepresentable rather than
    merely tested for.

    ``classes_`` is consulted rather than assumed: sklearn orders classes by sorted
    label, so the argmax over a leaf's value array is an INDEX, not a class. Reading it
    as the class directly happens to work only while the labels are 0/1 in that order.
    """
    n_in = getattr(estimator, "n_features_in_", None)
    if n_in is not None and n_in != len(table.feature_names):
        raise ValueError(
            f"estimator was fitted on {n_in} features but the table has "
            f"{len(table.feature_names)}; it was not trained on this table")

    t = estimator.tree_
    classes = list(estimator.classes_)
    leaf_class = [classes[int(t.value[n][0].argmax())] for n in range(t.node_count)]
    return flat_tree_to_rules(
        feature=[int(f) for f in t.feature],
        threshold=[float(x) for x in t.threshold],
        children_left=[int(c) for c in t.children_left],
        children_right=[int(c) for c in t.children_right],
        leaf_class=leaf_class,
        feature_names=list(table.feature_names),
    )

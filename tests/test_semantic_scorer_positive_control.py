"""Does the semantic scorer return a perfect score for a perfect answer?

Every structural number in the SoSyM revision rests on this scorer's semantic tier,
and across 234 scored folds not one reaches F1 = 1 — the maximum is 0.9985. So every
observation available is a NEGATIVE one, and a scorer that could never return 1 would
look exactly like the data we have. The A5 invariant
``semantic F1 = 1 <=> exact_equiv = 1`` inherits the same blind spot: with no positive
instances it catches a wrongly-yes but never a wrongly-no, and a stub returning 0
passes it on all 234 folds.

The only way to see the positive half is to construct it: feed the target theory back
as the learned theory and require a perfect score, then perturb it and require an
imperfect one. If the first fails, the scorer is wrong and so is every number derived
from it.
"""

import pytest

from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker
from conacq.oracle.ground_truth import GroundTruthData
from tests.resource_paths import DATA_DIR

ENABLED_TESTS = {
    'identity_scores_perfect': True,
    'weakened_theory_loses_recall': True,
    'foreign_clause_loses_precision': True,
}

# One small and one mid-size model. The scorer is model-independent, so breadth buys
# little; these two differ enough in clause count to catch a size-dependent fault.
MODELS = ['REAL-FM-7', 'arcade-game']


def ground_truth_clauses(name):
    gt = GroundTruthData.from_uvl(DATA_DIR / 'fms' / f'{name}.uvl')
    return [list(c) for c in gt.clauses]


def score(kb_clauses, ct_clauses, bg_clauses=None):
    """Recall and precision exactly as kb_comparator._compare_by_semantic derives them."""
    result = SemanticEquivalenceChecker(
        kb_clauses=kb_clauses, ct_clauses=ct_clauses,
        bg_clauses=bg_clauses or []).check_equivalence()
    tp = result.n_ct_checked - len(result.unentailed_ct)
    fn = len(result.unentailed_ct)
    fp = len(result.unentailed_kb)
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    return recall, precision, result


@pytest.mark.skipif(not ENABLED_TESTS['identity_scores_perfect'], reason="disabled")
@pytest.mark.parametrize('name', MODELS)
def test_the_target_theory_scores_perfectly_against_itself(name):
    """Cτ as the learned theory must score recall = precision = 1 and be equivalent.

    This is the observation the 234 folds cannot supply. A scorer that always returns
    a shortfall — a broken entailment direction, an off-by-one in the clause set, a
    checker that never proves entailment — is indistinguishable from the real data
    without it.
    """
    ct = ground_truth_clauses(name)
    assert ct, f"{name} has no ground-truth clauses"

    recall, precision, result = score(ct, ct)
    assert result.is_equivalent, (
        f"{name}: the target theory is not equivalent to itself; "
        f"{len(result.unentailed_ct)} of {result.n_ct_checked} target clauses "
        f"and {len(result.unentailed_kb)} learned clauses came back unentailed")
    assert recall == 1.0 and precision == 1.0, (
        f"{name}: identity scored recall={recall}, precision={precision}")


@pytest.mark.skipif(not ENABLED_TESTS['weakened_theory_loses_recall'], reason="disabled")
@pytest.mark.parametrize('name', MODELS)
def test_dropping_a_clause_loses_recall(name):
    """A theory missing something the target requires must not score a perfect recall.

    Dropping an arbitrary clause is not enough: the remainder may still entail it, in
    which case the theory is genuinely equivalent and a perfect recall is correct. So
    search for a clause whose removal is actually detectable, and fail only if NO
    clause is — that would mean the scorer cannot see a weakened theory at all.
    """
    ct = ground_truth_clauses(name)
    for i in range(len(ct)):
        weakened = ct[:i] + ct[i + 1:]
        recall, _, result = score(weakened, ct)
        if recall < 1.0:
            assert not result.is_equivalent, (
                f"{name}: recall fell to {recall} but the checker still called it "
                f"equivalent — the two disagree")
            return
    pytest.fail(f"{name}: removing any single clause left recall at 1.0 — the scorer "
                f"cannot distinguish a weakened theory from the target")


@pytest.mark.skipif(not ENABLED_TESTS['foreign_clause_loses_precision'], reason="disabled")
@pytest.mark.parametrize('name', MODELS)
def test_an_unentailed_clause_loses_precision(name):
    """A theory asserting something the target does not must not score a perfect precision.

    Uses a unit clause over a variable the model does not have, so it cannot be
    entailed by any target theory. Precision is the direction the folds exercise least
    — QuAcq scores 1.000 everywhere and ConGen 0.561-0.864 — so a fault here would
    surface as ConGen looking worse than it is.
    """
    ct = ground_truth_clauses(name)
    unseen = max(abs(lit) for clause in ct for lit in clause) + 1
    recall, precision, result = score(ct + [[unseen]], ct)

    assert precision < 1.0, (
        f"{name}: a clause over an unseen variable was counted as entailed; "
        f"precision stayed at {precision}")
    assert recall == 1.0, (
        f"{name}: adding a clause should not cost recall, got {recall}")
    assert not result.is_equivalent

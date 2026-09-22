"""FMOracle.is_valid partial-query semantics (QuAcq paper fix) + complete-path parity.

Complete configs keep the exact prior FM-solution-check behavior (byte-identical); partial
queries now follow the QuAcq paper rule (Bessiere et al., IJCAI 2013): a partial is negative
iff it violates a target constraint whose variables are ALL assigned — NOT extension-SAT.
"""
import random
from pathlib import Path

import pytest

from conacq.oracle import FMOracle

_DATA = Path(__file__).parent.parent / "data"
_KBS = [("REAL-FM-7", _DATA / "fms" / "REAL-FM-7.uvl"),
        ("fqa", _DATA / "fms" / "fqa.uvl")]


def _fully_assigned_clause_check(o: FMOracle, a: dict) -> bool:
    """Independent reference oracle: valid iff no FULLY-ASSIGNED FM clause is violated."""
    id2n = o._oracle_model.id_to_name
    for clause in o._fm_clauses:
        names = [id2n[abs(l)] for l in clause]
        if any(n not in a for n in names):
            continue
        if not any(a[n] if l > 0 else not a[n] for l, n in zip(clause, names)):
            return False
    return True


@pytest.mark.parametrize("kb,path", _KBS)
def test_complete_config_isvalid_byte_identical_to_solution_check(kb, path):
    """A COMPLETE config's is_valid == FM solution check (prior behavior) over 200 configs,
    covering both valid and invalid — proves the complete path is unchanged."""
    if not path.exists():
        pytest.skip(f"missing {path}")
    o = FMOracle(str(path))
    feats = sorted(o.get_variables())
    # explicit VALID complete config (SAT-derived) and explicit INVALID one (all deselected →
    # violates the root clause): both must agree between is_valid and the solution check.
    valid = o.complete_configuration({})
    assert valid is not None and set(valid) == set(feats)
    assert o.is_valid(valid) is True and _fully_assigned_clause_check(o, valid) is True
    all_false = {f: False for f in feats}
    assert o.is_valid(all_false) is False and _fully_assigned_clause_check(o, all_false) is False
    # random parity: is_valid == solution check on every complete config, valid or invalid
    rng = random.Random(7)
    for _ in range(200):
        a = {f: rng.random() < 0.5 for f in feats}
        assert o.is_valid(a) == _fully_assigned_clause_check(o, a)


@pytest.mark.parametrize("kb,path", _KBS)
def test_partial_query_paper_rule(kb, path):
    """Empty partial → valid (no fully-assigned clause); a partial violating a fully-assigned
    binary clause → invalid."""
    if not path.exists():
        pytest.skip(f"missing {path}")
    o = FMOracle(str(path))
    id2n = o._oracle_model.id_to_name
    assert o.is_valid({}) is True
    binclause = next(c for c in o._fm_clauses if len(c) == 2)
    violate = {id2n[abs(l)]: (l < 0) for l in binclause}  # set every literal false
    assert o.is_valid(violate) is False


def test_partial_not_extension_sat_regression():
    """REAL-FM-7: the exact audit case — extension-UNSAT but violates no fully-assigned
    constraint → the paper rule must answer VALID (was False under extension-SAT)."""
    path = _DATA / "fms" / "REAL-FM-7.uvl"
    if not path.exists():
        pytest.skip("missing REAL-FM-7")
    o = FMOracle(str(path))
    # jplug=T, sdi=F, mdi=F is unextendable (jplug→interface→xor(sdi,mdi)) yet no clause fully
    # inside {jplug,sdi,mdi} is violated (interface is unassigned).
    assert o.is_valid({"jplug": True, "sdi": False, "mdi": False}) is True


def test_example_mode_quacq_deterministic():
    """H-2: seeded example-only QuAcq is reproducible run-to-run (was shuffle_seed=None)."""
    from conacq.runners import QuAcqRunner
    from conacq.examples import ExampleIO
    from conacq.eval.folds import load_folds, apply_folds
    fm = _DATA / "fms" / "REAL-FM-7.uvl"
    bias = _DATA / "bias" / "REAL-FM-7-bias.json"
    exp = _DATA / "examples" / "REAL-FM-7_2cov.json"
    folds = _DATA / "folds" / "REAL-FM-7_2cov_folds.json"
    if not all(p.exists() for p in (fm, bias, exp, folds)):
        pytest.skip("missing fixtures")
    ex = ExampleIO.load_json(str(exp))
    pos = [e.assignments for e in ex.positive]
    neg = [e.assignments for e in ex.negative]
    fd = load_folds(str(folds))
    tr_pos, tr_neg, _, _ = apply_folds(fd, pos, neg, 0)

    def once():
        r = QuAcqRunner(str(bias), str(fm), "glucose4", max_queries=3000)
        try:
            res = r.run(tr_pos, tr_neg, shuffle_seed=0)
        finally:
            r.cleanup()
        return res.n_kb, res.n_queries, tuple(sorted(res.kb_constraints))

    assert once() == once()

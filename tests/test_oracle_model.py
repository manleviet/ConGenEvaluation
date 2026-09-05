"""Tests for FMOracleModel — an immutable FM KB with a pure prepare() -> OracleData."""

from pathlib import Path

import pytest

from conacq.oracle import FMOracle
from conacq.oracle.fm.model import FMOracleModel
from explanation.api import config_to_assignment_assumptions
from explanation.checker.backend import build_checker, SolverBackend
from tests.resource_paths import MODELS


def _make_oracle_model(constraint_map, variables, next_available_id):
    """Test helper: create an FMOracleModel from raw KB data. No prep here —
    prepare() is pure and called on demand by each test."""
    model = FMOracleModel()
    model.constraint_map = constraint_map
    model.name_to_id = variables
    model.next_available_id = next_available_id
    return model


def _query_set_c(prepared, config):
    """The set_c a membership query builds (mirrors FMOracle.is_valid): the prepared
    task's FM constraints plus this query's assignment assumptions, via the prepared
    assignment_map. Pure — never touches the prepared task."""
    return list(prepared.task.set_c) + config_to_assignment_assumptions(
        config, prepared.assignment_map)


class TestOracleModel:
    def test_prepare_task_produces_valid_task(self):
        """prepare_task produces a task with the expected set_kb + assumptions."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, next_available_id=2)
        prepared = model.prepare()

        assert len(prepared.task.assumptions) == 5  # 1 FM constraint + 2 features * 2 (pos+neg)
        # set_kb = 1 FM guarded clause + 4 feature assignment clauses
        assert len(prepared.task.set_kb) == 1 + 4

    def test_prepare_task_returns_task_for_checker(self):
        """prepare returns an OracleData snapshot carrying the task the checker consumes."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, 2)
        prepared = model.prepare()
        assert prepared.task.set_kb is not None
        assert prepared.task.assumptions is not None

    def test_constraint_map_and_variables(self):
        """Verify constraint_map + variables stored correctly."""
        constraint_map = {"fm": [[1, 2], [-1, 3]]}
        variables = {"f1": 1, "f2": 2, "f3": 3}
        model = _make_oracle_model(constraint_map, variables, next_available_id=3)

        assert model.constraint_map == constraint_map
        assert model.name_to_id == variables

    def test_prepare_task_is_pure_across_queries(self):
        """A membership query's set_c contains that query's assignment assumptions
        (mapped via the prepared assignment_map) and leaves the prepared task
        untouched — a query cannot leak into the background."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, next_available_id=2)
        prepared = model.prepare()

        before = list(prepared.task.set_c)
        active = _query_set_c(prepared, {"f1": True, "f2": False})

        # The query's assignment assumptions are present in the returned set_c...
        assert prepared.assignment_map.pos_assignment_to_assumption["f1"] in active
        assert prepared.assignment_map.neg_assignment_to_assumption["f2"] in active
        # ...but the prepared task's own set_c is unchanged — no query leaks in.
        assert list(prepared.task.set_c) == before
        assert active != before

    def test_prepare_task_yields_independent_tasks(self):
        """Two prepare_task calls yield equal-but-independent tasks (pure, no shared
        state) — the T3 purity property."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, next_available_id=2)
        p1 = model.prepare()
        p2 = model.prepare()
        assert p1.task.set_c == p2.task.set_c
        assert p1.task is not p2.task

    def test_assumption_ids_start_after_tseitin(self):
        """Assumption IDs don't collide with FM variables."""
        model = _make_oracle_model({"fm": [[1, 2, 3]]}, {"f1": 1, "f2": 2, "f3": 3}, 3)
        prepared = model.prepare()
        # All assumption IDs should be >= next_available_id (3)
        for a in prepared.task.assumptions:
            assert a >= 3

    def test_checker_integration_sat(self):
        """build_checker creates valid checker; SAT case. use_incremental is the
        caller's choice, not the model's."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, next_available_id=2)
        prepared = model.prepare()
        checker = build_checker(prepared.task, SolverBackend.from_flags(use_incremental=True), 'glucose4')

        # f1=True, f2=True → SAT
        assert checker.is_consistent(_query_set_c(prepared, {"f1": True, "f2": True})) is True
        checker.cleanup()

    def test_checker_integration_unsat(self):
        """build_checker creates valid checker; UNSAT case."""
        model = _make_oracle_model({"fm": [[1, 2]]}, {"f1": 1, "f2": 2}, next_available_id=2)
        prepared = model.prepare()
        checker = build_checker(prepared.task, SolverBackend.from_flags(use_incremental=True), 'glucose4')

        # f1=False, f2=False → UNSAT (neither true violates f1 OR f2)
        assert checker.is_consistent(_query_set_c(prepared, {"f1": False, "f2": False})) is False
        checker.cleanup()


@pytest.mark.parametrize("name,fm_path,_bias", MODELS, ids=[m[0] for m in MODELS])
def test_root_constraint_is_the_first_constraint_map_key(name, fm_path, _bias):
    """Preparation derives root_clauses as constraint_map's FIRST key. Pin that it
    IS the FM root: FmToDiagPysat traverses root-first, and both bg_data's root pair
    and root_clauses ride that ordering. If the transformation ever changes
    insertion order, root_clauses would silently become a different constraint
    (wrong background → ConGen learns on wrong ground) — this makes that red
    immediately. (Storing the root name explicitly at build is the T11.4c fix.)"""
    if not Path(fm_path).exists():
        pytest.skip(f"feature model not found: {fm_path}")
    oracle = FMOracle(fm_path)
    model = oracle._oracle_model
    # ``root_feature`` is stored at build from the FM tree's declared root — an
    # independent witness, NOT derived from constraint_map's ordering — so this
    # asserts FmToDiagPysat put the root constraint first. If it ever reorders, the
    # first key diverges from the stored root and this goes red (was oracle
    # .get_root_feature(), deleted in the T11.4c API diet).
    assert next(iter(model.constraint_map)) == model.root_feature

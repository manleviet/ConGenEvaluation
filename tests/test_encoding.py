"""Tests for the encoding free functions + AssignmentAssumptionMap + KB Protocol.

Pins the single-source name↔id / config↔literal translations that replaced the
per-model encoding methods (round-trip, deterministic ordering, guard behavior).
"""
import dataclasses

import pytest

from explanation.models.encoding import (
    config_to_variable_literals,
    variable_literals_to_config,
    config_to_assignment_assumptions,
    get_constraint_vars,
)
from explanation.models.assignment_assumption_map import AssignmentAssumptionMap
from explanation.models.kb_protocol import KBProtocol
from conacq.kb_model import KBModel


def test_config_variable_literals_roundtrip():
    name_to_id = {"a": 1, "b": 2, "c": 3}
    id_to_name = {1: "a", 2: "b", 3: "c"}
    config = {"a": True, "b": False, "c": True}
    lits = config_to_variable_literals(config, name_to_id)
    assert lits == [1, -2, 3]  # sorted by feature name
    assert variable_literals_to_config(lits, id_to_name) == config


def test_config_to_variable_literals_sorted_and_skips_missing():
    name_to_id = {"b": 2, "a": 1}
    lits = config_to_variable_literals({"b": True, "z": True, "a": False}, name_to_id)
    assert lits == [-1, 2]  # 'z' absent → skipped; deterministic name order


def test_variable_literals_to_config_skips_non_features():
    id_to_name = {1: "a", 2: "b"}
    # 99 is a Tseitin/assumption var → skipped
    assert variable_literals_to_config([1, -2, 99], id_to_name) == {"a": True, "b": False}


def test_config_to_assignment_assumptions():
    amap = AssignmentAssumptionMap({"a": 10, "b": 20}, {"a": 11, "b": 21})
    assert config_to_assignment_assumptions({"a": True, "b": False}, amap) == [10, 21]
    assert config_to_assignment_assumptions({"a": True, "z": True}, amap) == [10]  # missing skipped


def test_get_constraint_vars():
    id_to_name = {1: "a", 2: "b", 3: "c"}
    assert get_constraint_vars([[1, -2], [3]], id_to_name) == {"a", "b", "c"}


def test_assignment_assumption_map_frozen():
    amap = AssignmentAssumptionMap({"a": 1}, {"a": 2})
    with pytest.raises(dataclasses.FrozenInstanceError):
        amap.pos_assignment_to_assumption = {}


def test_kbmodel_catalog_and_protocol():
    # The name↔id catalog is exposed as plain dicts (no runtime read-only view —
    # ADR-0007); KBProtocol keeps the read-only guarantee at the type level.
    class _KB(KBModel):
        def __init__(self):
            super().__init__()
            self.name_to_id = {"a": 1}
            self.id_to_name = {1: "a"}
            self.next_available_id = 5

    kb = _KB()
    assert kb.name_to_id == {"a": 1}
    assert kb.id_to_name == {1: "a"}
    assert isinstance(kb, KBProtocol)  # a plain-dict model still satisfies KBProtocol

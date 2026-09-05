"""Coverage for the bias IO / stats surface.

Replaces the two demo scripts (``test_bias_module.py`` / ``_1.py``) that were the
only consumers of ``BiasIO.save_to_json/save_to_cnf/save_statistics`` +
``BiasGenerator.get_statistics`` + ``BiasConfigLoader.validate_config`` — those
demos had 0 assertions, printed to stdout, and wrote into the repo tree.

Literals below are pinned against the committed ``REAL-FM-7.yaml`` fixture. Bias
generation is a pure deterministic function of the YAML (exhaustive
``itertools.combinations``, feature IDs by list order, no ``random``/sampling),
verified by running the whole pipeline twice to byte-equal output — so absolute
counts are safe to assert. All outputs go to ``tmp_path``, never the repo.
"""
import json
from pathlib import Path

import pytest

from conacq.bias import BiasConfigLoader, BiasGenerator, BiasIO
from conacq.bias.data_structures import (
    BiasConfig,
    CrossTreeConfig,
    CrossTreeMode,
    HierarchicalCandidate,
    RelationshipType,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BIAS_CONFIG_PATH = DATA_DIR / "bias-config" / "REAL-FM-7.yaml"

# Pinned expected values for the REAL-FM-7 fixture (see module docstring).
EXPECTED_NUM_FEATURES = 14
EXPECTED_NUM_HIERARCHICAL = 22
EXPECTED_NUM_CROSS_TREE = 273
EXPECTED_TOTAL = 295
EXPECTED_BREAKDOWN = {
    "mandatory": 9,
    "optional": 9,
    "alternative": 2,
    "or": 2,
    "requires": 182,
    "excludes": 91,
}
EXPECTED_NUM_CLAUSES = 314


@pytest.fixture(scope="module")
def config():
    return BiasConfigLoader.load(str(BIAS_CONFIG_PATH))


@pytest.fixture(scope="module")
def bias(config):
    return BiasGenerator(config).generate_bias()


# --- BiasConfigLoader.validate_config -------------------------------------

def test_validate_config_accepts_valid_fixture(config):
    result = BiasConfigLoader.validate_config(config)
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["warnings"] == []


def test_validate_config_rejects_unknown_parent():
    broken = BiasConfig(
        name="broken-parent",
        features=["a", "b"],
        leaf_features=["a", "b"],
        hierarchical_candidates=[
            HierarchicalCandidate(
                parent="ghost",
                children=["a"],
                relationship_type=RelationshipType("binary"),
            )
        ],
        cross_tree_config=CrossTreeConfig(
            cross_tree_mode=CrossTreeMode("leaf"),
            specific_pairs=[],
            cross_tree_features=[],
        ),
    )
    result = BiasConfigLoader.validate_config(broken)
    assert result["valid"] is False
    assert "Parent 'ghost' not in features list" in result["errors"]


def test_validate_config_rejects_duplicate_features():
    broken = BiasConfig(
        name="broken-dup",
        features=["a", "b", "a"],
        leaf_features=[],
        hierarchical_candidates=[],
        cross_tree_config=CrossTreeConfig(
            cross_tree_mode=CrossTreeMode("leaf"),
            specific_pairs=[],
            cross_tree_features=[],
        ),
    )
    result = BiasConfigLoader.validate_config(broken)
    assert result["valid"] is False
    assert any("Duplicate features found" in e for e in result["errors"])


# --- BiasGenerator.get_statistics -----------------------------------------

def test_get_statistics_literals(config):
    stats = BiasGenerator(config).get_statistics()
    assert stats["num_features"] == EXPECTED_NUM_FEATURES
    assert stats["num_hierarchical"] == EXPECTED_NUM_HIERARCHICAL
    assert stats["num_cross_tree"] == EXPECTED_NUM_CROSS_TREE
    assert stats["total"] == EXPECTED_TOTAL
    assert stats["breakdown"] == EXPECTED_BREAKDOWN


# --- BiasIO.save_to_json ---------------------------------------------------

def test_save_to_json_roundtrip(bias, tmp_path):
    out = tmp_path / "bias.json"
    BiasIO.save_to_json(bias, str(out))

    assert out.exists()
    data = json.loads(out.read_text())
    assert set(data.keys()) == {"features", "constraints"}
    assert len(data["features"]) == EXPECTED_NUM_FEATURES
    assert len(data["constraints"]) == EXPECTED_TOTAL

    loaded = BiasIO.load_from_json(str(out))
    # Round-trip preserves counts exactly.
    assert len(loaded.features) == len(bias.features) == EXPECTED_NUM_FEATURES
    assert len(loaded.constraints) == len(bias.constraints) == EXPECTED_TOTAL


# --- BiasIO.save_to_cnf ----------------------------------------------------

def test_save_to_cnf_header_matches_clauses(bias, tmp_path):
    out = tmp_path / "bias.cnf"
    BiasIO.save_to_cnf(bias, str(out))

    lines = out.read_text().splitlines()
    header = [ln for ln in lines if ln.startswith("p cnf")]
    assert header == [f"p cnf {EXPECTED_NUM_FEATURES} {EXPECTED_NUM_CLAUSES}"]

    # Non-comment, non-header lines are the clauses; count must match header.
    clause_lines = [
        ln for ln in lines
        if ln and not ln.startswith("c") and not ln.startswith("p")
    ]
    assert len(clause_lines) == EXPECTED_NUM_CLAUSES


# --- BiasIO.save_statistics ------------------------------------------------

def test_save_statistics_content(bias, tmp_path):
    out = tmp_path / "bias_stats.txt"
    BiasIO.save_statistics(bias, str(out))

    text = out.read_text()
    assert "=== Bias Statistics ===" in text
    assert f"Total features: {EXPECTED_NUM_FEATURES}" in text
    assert f"Total constraints: {EXPECTED_TOTAL}" in text
    assert f"Total clauses: {EXPECTED_NUM_CLAUSES}" in text

"""Feature-table construction for the rule-learner baselines (C4).

No learner library is needed here — the table layer is deliberately plain Python, so
these run on a clean environment without the ``baselines`` extra.
"""
import pytest

from conacq.baselines import INVALID, VALID, build_feature_table

# Ids deliberately NOT in alphabetical order and NOT contiguous: real ids come from
# flamapy's tree traversal, so a test whose ids happen to sort alphabetically would
# let index-pairing pass.
CATALOG = {"root": 3, "gui": 1, "sdi": 7, "mdi": 4}

POS = [{"root": True, "gui": True, "sdi": True, "mdi": False}]
NEG = [{"root": True, "gui": False, "sdi": True, "mdi": True}]


def test_columns_ordered_by_variable_id_not_alphabetically():
    """Default column order follows the id catalog (traversal order), not the name."""
    t = build_feature_table(POS, NEG, CATALOG)
    assert t.feature_names == ("gui", "root", "mdi", "sdi")   # ids 1, 3, 4, 7
    assert t.feature_names != tuple(sorted(CATALOG))          # alphabetical would differ


def test_labels_mark_negatives_as_the_target_class():
    """Positive class is `invalid` — negatives get label 1, positives 0.

    Swapping these silently inverts every learned rule while every downstream call
    still succeeds, so the convention is asserted rather than assumed.
    """
    t = build_feature_table(POS, NEG, CATALOG)
    assert t.labels == (VALID, INVALID)
    assert t.n_invalid == 1 and t.n_valid == 1
    assert INVALID == 1 and VALID == 0


def test_literals_resolve_by_name_with_correct_sign():
    t = build_feature_table(POS, NEG, CATALOG)
    assert t.literal("gui", True) == 1
    assert t.literal("gui", False) == -1
    assert t.literal("sdi", True) == 7
    assert t.literal("sdi", False) == -7


def test_permuting_columns_does_not_change_literals_or_column_contents():
    """The canary for index-pairing, at the table level.

    Build the same data with reversed column order. Every literal and every named
    column must be identical — they are keyed by name. A layer that paired column
    index with variable id would produce different literals here. (The CNF-level
    canary, which compares whole clause sets, lives with the rule→CNF converter.)
    """
    default = build_feature_table(POS, NEG, CATALOG)
    reversed_order = build_feature_table(
        POS, NEG, CATALOG, feature_order=tuple(reversed(default.feature_names)))

    assert reversed_order.feature_names == tuple(reversed(default.feature_names))
    for name in CATALOG:
        assert default.literal(name, True) == reversed_order.literal(name, True)
        assert default.literal(name, False) == reversed_order.literal(name, False)
        assert default.column(name) == reversed_order.column(name)


def test_incomplete_example_is_refused():
    """A missing assignment raises instead of being defaulted.

    Filling a default would fabricate a training row, and the learner would report a
    score computed partly from data nobody supplied.
    """
    with pytest.raises(ValueError, match="complete assignments"):
        build_feature_table([{"root": True, "gui": True}], NEG, CATALOG)


def test_non_bijective_catalog_is_refused():
    """Two features sharing one id would silently merge columns downstream."""
    with pytest.raises(ValueError, match="not bijective"):
        build_feature_table(POS, NEG, {"a": 1, "b": 1})


def test_feature_order_must_cover_the_catalog_exactly():
    with pytest.raises(ValueError, match="does not cover the catalog"):
        build_feature_table(POS, NEG, CATALOG, feature_order=("gui", "root"))


def test_unknown_feature_literal_is_refused():
    t = build_feature_table(POS, NEG, CATALOG)
    with pytest.raises(KeyError, match="no variable id"):
        t.literal("nonexistent", True)


def test_real_catalog_ids_are_not_alphabetical():
    """Guards the premise the canary rests on, against the real FM.

    If flamapy's ids ever became alphabetical, index-pairing and name-pairing would
    agree on these fixtures and the canary would stop discriminating without failing.
    """
    from pathlib import Path

    from conacq.algorithms import ConGenModelBuilder
    from conacq.oracle import FMOracle

    data = Path(__file__).parent.parent / "data"
    fm, bias = data / "fms" / "REAL-FM-7.uvl", data / "bias" / "REAL-FM-7-bias.json"
    if not fm.exists() or not bias.exists():
        pytest.skip("REAL-FM-7 fixtures not found")

    oracle = FMOracle(str(fm), use_incremental=False)
    model = (ConGenModelBuilder.from_bias(str(bias))
             .with_oracle_data(oracle.oracle_data).build())
    by_id = sorted(model.name_to_id, key=lambda n: model.name_to_id[n])
    assert by_id != sorted(by_id), \
        "FM ids now sort alphabetically — the permutation canary no longer discriminates"

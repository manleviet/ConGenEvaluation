"""T9 safety net — written FIRST, green on the OLD code (before the metrics refactor).

Locks the frozen on-disk contract so the runners+metrics refactor (dict-backed
``RunMetrics`` + a generic ``aggregate()`` + disjoint ``CONGEN_METRICS`` /
``QUACQ_METRICS`` tables, moved to ``conacq/runners/metrics.py``) cannot move a
single table cell or silently drop a JSON key.

Order is not negotiable: these are characterization tests, green on the CURRENT
code before a line is refactored. A net woven after the fall catches nothing.

- Test 1 (real acceptance): re-run ``apps.extract_results`` over the recorded
  ``data/results/congen`` and diff the tables against a byte-frozen golden.
- Test 2 (schema pin): the aggregated ``performance`` block schema is pinned as a
  LITERAL (copied from a real file), never re-derived from the code under test.
- Test 3 (from_json sweep): every recorded result JSON still parses.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "data" / "results"
CONGEN_DIR = RESULTS_DIR / "congen"
GOLDEN_DIR = Path(__file__).parent / "resources" / "t9_extraction_golden"

# Relative to the repo root (pytest's cwd) — must match how the golden was
# generated so the "Generated from: ..." provenance line stays byte-identical.
CONGEN_REL = "data/results/congen"


# --------------------------------------------------------------------------- #
# Test 1 — extraction diff (the real acceptance)                              #
# --------------------------------------------------------------------------- #

@pytest.mark.skip(reason="data/results/congen + t9 golden pending B3 REDUCE regen — "
                         "validates stale-vs-stale until ConGen revision; see ADR-0017")
def test_extraction_tables_are_byte_identical(tmp_path, monkeypatch):
    """`python -m apps.extract_results` over the recorded data reproduces the
    frozen paper tables byte-for-byte. No experiment is re-run — only re-extraction.

    SKIPPED until the ConGen revision: B3 (``reduce.py`` MSS-order fix, ADR-0017)
    changed ConGen's learned KB, so ``data/results/congen`` and this frozen golden
    are both stale. Re-extracting stale data still matches the stale golden — a
    green that proves nothing. Kept loud (skip, not pass) so the pending
    multi-hour CV regen is visible. Unskip after regen (see
    `an internal effort log, not shipped`).
    """
    from apps import extract_results

    monkeypatch.setattr(sys, "argv", [
        "extract_results",
        "--results-dir", CONGEN_REL,
        "--output-dir", str(tmp_path),
        "--mode", "both",
    ])
    extract_results.main()

    for name in ("results_tables.md", "results_tables.tex"):
        got = (tmp_path / name).read_text()
        want = (GOLDEN_DIR / name).read_text()
        assert got == want, f"{name} drifted from the frozen golden extraction"


# --------------------------------------------------------------------------- #
# Test 2 — schema pin (LITERAL, not code-derived)                             #
# --------------------------------------------------------------------------- #

# The full aggregated ``performance`` block schema, copied verbatim from a real
# ``data/results/congen/*.json``. The abbreviation-carrying group names
# (``query_gen_runtime``, ``prune_ic_calls``, ``findc_checks`` …) are pinned here
# as a LITERAL — re-deriving the expectation from the reducer under test would be
# a tautology that proves nothing. ``None`` marks a scalar (non-grouped) value.
#
# The ConGen-owned groups are the leading 13 entries (through
# ``redundancy_consistency_checks``); the trailing 16 are QuAcq's. After the
# refactor the disjoint per-algorithm reducers are pinned against slices of THIS
# same literal — the anchor never moves.
AGG_SCHEMA = (
    ("n_runs", None),
    ("runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("consistency_checks", ("mean", "std", "min", "max")),
    ("memory", ("mean_mb", "max_mb")),
    ("kb_size", ("n_mss_mean", "n_kb_mean")),
    ("congen_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("acqmss_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("acqmss_calls", ("mean", "std", "min", "max")),
    ("reduce_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("solver_time", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("is_consistent_calls", ("mean", "std", "min", "max")),
    ("is_consistent_test_cases_calls", ("mean", "std", "min", "max")),
    ("redundancy_consistency_checks", ("mean", "std", "min", "max")),
    ("quacq_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("query_gen_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("findscope_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("findc_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("dis_gen_runtime", ("mean_ms", "std_ms", "min_ms", "max_ms")),
    ("quacq_calls", ("mean", "std", "min", "max")),
    ("query_gen_calls", ("mean", "std", "min", "max")),
    ("query_gen_checks", ("mean", "std", "min", "max")),
    ("prune_calls", ("mean", "std", "min", "max")),
    ("prune_ic_calls", ("mean", "std", "min", "max")),
    ("findscope_calls", ("mean", "std", "min", "max")),
    ("findc_calls", ("mean", "std", "min", "max")),
    ("findc_checks", ("mean", "std", "min", "max")),
    ("dis_gen_calls", ("mean", "std", "min", "max")),
    ("dis_gen_checks", ("mean", "std", "min", "max")),
    ("reduce_calls", ("mean", "std", "min", "max")),
)


AGG_DICT = dict(AGG_SCHEMA)  # group name -> ordered stat-keys (None for scalars)

# ConGen owns the leading entries of the frozen schema, through
# ``redundancy_consistency_checks``; the rest are QuAcq's.
_CONGEN_CUT = AGG_SCHEMA.index(("redundancy_consistency_checks", ("mean", "std", "min", "max"))) + 1
CONGEN_SCHEMA = AGG_SCHEMA[:_CONGEN_CUT]


def _schema_of(block: dict) -> tuple:
    return tuple(
        (g, tuple(v.keys()) if isinstance(v, dict) else None)
        for g, v in block.items()
    )


def _runs(spec, n=2):
    from conacq.runners.metrics import RunMetrics
    return [RunMetrics(spec, {m.key: float(i + 1) for m in spec}) for i in range(n)]


def test_frozen_ondisk_schema_matches_literal():
    """The recorded data still carries exactly the pinned group+stat schema."""
    f = sorted(CONGEN_DIR.glob("*_cv_incremental.json"))[0]
    perf = json.loads(f.read_text())["performance"]
    assert _schema_of(perf) == AGG_SCHEMA


def test_congen_aggregate_reproduces_the_congen_schema():
    """Disjoint ConGen reducer emits exactly the ConGen-owned prefix of the
    frozen schema — pinned against the LITERAL slice, not the reducer.
    """
    from conacq.runners.metrics import CONGEN_METRICS, aggregate
    assert _schema_of(aggregate(_runs(CONGEN_METRICS))) == CONGEN_SCHEMA


def test_quacq_aggregate_uses_the_frozen_group_names():
    """Every group the QuAcq reducer emits carries the frozen on-disk group name
    and stat-keys (pins the abbreviations query_gen_checks / prune_ic_calls /
    findc_checks / dis_gen_checks against real recorded data). QuAcq is disjoint
    from ConGen but for the declared common core (runtime/consistency_checks/memory/…).
    """
    from conacq.runners.metrics import QUACQ_METRICS, aggregate
    for group, stat_keys in _schema_of(aggregate(_runs(QUACQ_METRICS))):
        assert group in AGG_DICT, f"QuAcq emitted an unknown group {group!r}"
        assert stat_keys == AGG_DICT[group], f"group {group!r} stat-keys drifted"


# --------------------------------------------------------------------------- #
# Test 3 — from_json sweep                                                    #
# --------------------------------------------------------------------------- #

def test_every_recorded_result_json_still_parses():
    """Every recorded CV result JSON parses through the loader without raising."""
    from conacq.eval.result_loader import ConGenResultData

    files = sorted(CONGEN_DIR.rglob("*_cv_*.json"))
    assert files, "no recorded CV result JSON found — fixture missing"
    for f in files:
        data = ConGenResultData.from_json(f)  # must not raise
        assert data is not None


# --------------------------------------------------------------------------- #
# Test 4 — metric-map completeness                                            #
# --------------------------------------------------------------------------- #

def test_congen_metric_map_is_complete():
    """Every profiler key a ConGen run emits is either mapped by a MetricSpec or
    explicitly ignored — the old failure mode (metric collected, never exported)
    is now impossible without a red test. Enumerated from a recorded run's own
    profiler snapshot (real data, no re-run).
    """
    from conacq.runners.metrics import CONGEN_METRICS, CONGEN_IGNORED

    f = sorted(CONGEN_DIR.glob("*_cv_incremental.json"))[0]
    emitted = set(json.loads(f.read_text())["folds"][0]["performance"]["profiler"].keys())

    _EXTRA = {"memory_peak_mb", "n_mss", "n_kb"}  # come from `extra`, not the profiler
    profiler_sources = {m.source for m in CONGEN_METRICS} - _EXTRA

    # shared_* counters (e.g. shared_admpool_checks) are cross-algorithm:
    # AcqMSS emits them for ConGen too. They are always-allowed in any algorithm's
    # completeness check — a shared counter is never an "undeclared ConGen metric".
    undeclared = {k for k in (emitted - profiler_sources - CONGEN_IGNORED)
                  if not k.startswith('shared_')}
    assert not undeclared, f"ConGen emits profiler keys neither mapped nor ignored: {sorted(undeclared)}"

    phantom = profiler_sources - emitted
    assert not phantom, f"CONGEN_METRICS points at profiler keys a run never emits: {sorted(phantom)}"


# --------------------------------------------------------------------------- #
# Test 6 — mixed directory (legacy 29-group + new disjoint 13-group)          #
# --------------------------------------------------------------------------- #

def test_extract_handles_mixed_old_and_new_schema(tmp_path, monkeypatch):
    """After T9, ``data/results`` will hold BOTH legacy 29-group files and new
    13-group (disjoint) ConGen files. extract_results must read both without
    crashing, and the four ConGen-owned groups it consumes must extract
    identically from either shape.
    """
    from apps import extract_results
    from apps.extract_results import load_cv_result

    src = sorted(CONGEN_DIR.glob("*_cv_incremental.json"))[0]
    old = json.loads(src.read_text())                       # legacy: 29 groups

    new = json.loads(src.read_text())                       # new: ConGen-owned groups only
    congen_groups = {g for g, _ in CONGEN_SCHEMA}
    new["performance"] = {g: v for g, v in new["performance"].items() if g in congen_groups}
    assert len(new["performance"]) < len(old["performance"]), "QuAcq groups should be dropped"

    d = tmp_path / "mixed"
    d.mkdir()
    old_file = d / "REAL-FM-7_rs_1n_cv_incremental.json"
    new_file = d / "REAL-FM-7_rs_2n_cv_incremental.json"
    old_file.write_text(json.dumps(old))
    new_file.write_text(json.dumps(new))

    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "extract_results", "--results-dir", str(d), "--output-dir", str(out), "--mode", "incremental",
    ])
    extract_results.main()  # must not raise on the mixed directory

    r_old, r_new = load_cv_result(old_file), load_cv_result(new_file)
    for attr in ("runtime_mean_ms", "checks_mean", "memory_max_mb", "n_kb_mean"):
        assert getattr(r_old, attr) == getattr(r_new, attr), f"{attr} differs between old and new shape"

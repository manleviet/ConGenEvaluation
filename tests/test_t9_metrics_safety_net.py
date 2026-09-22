"""T9 safety net — written FIRST, green on the OLD code (before the metrics refactor).

Locks the frozen on-disk contract so the runners+metrics refactor (dict-backed
``RunMetrics`` + a generic ``aggregate()`` + disjoint ``CONGEN_METRICS`` /
``QUACQ_METRICS`` tables, moved to ``conacq/runners/metrics.py``) cannot move a
single table cell or silently drop a JSON key.

Order is not negotiable: these are characterization tests, green on the CURRENT
code before a line is refactored. A net woven after the fall catches nothing.

- Schema pin: the aggregated ``performance`` block schema is pinned as a LITERAL
  (copied from a real file), never re-derived from the code under test.
- from_json sweep: every recorded result JSON still parses.
- Metric-map completeness: every profiler key a run emits is mapped or ignored.

The pins read ``data/results_sosym_r1/congen`` — the acquisition results — so the
literal is anchored against the data that actually ships, not against a description
of it.
"""
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "data" / "results_sosym_r1"
CONGEN_DIR = RESULTS_DIR / "congen"

# --------------------------------------------------------------------------- #
# Test 1 — schema pin (LITERAL, not code-derived)                             #
# --------------------------------------------------------------------------- #

# The full aggregated ``performance`` block schema, copied verbatim from a real
# result file. The abbreviation-carrying group names
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
    """Every recorded result carries exactly the pinned ConGen group+stat schema.

    EVERY file, not the first one. A single-file check passes on a tree whose
    later files drifted, and the drift would surface as a table column that is
    silently absent rather than as a red test.

    The pin is ``CONGEN_SCHEMA`` — the ConGen-owned prefix of the frozen literal.
    These are ConGen runs, so the QuAcq groups are legitimately absent; asserting
    the full ``AGG_SCHEMA`` here would be asserting that a ConGen run emits QuAcq's
    counters.
    """
    files = sorted(CONGEN_DIR.glob("*_cv_incremental.json"))
    assert files, "no recorded CV result JSON found — fixture missing"
    for f in files:
        perf = json.loads(f.read_text())["performance"]
        assert _schema_of(perf) == CONGEN_SCHEMA, f"{f.name} drifted from the frozen schema"


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
# Test 2 — from_json sweep                                                    #
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
# Test 3 — metric-map completeness                                            #
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

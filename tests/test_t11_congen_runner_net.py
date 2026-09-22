"""ConGenRunner.run() golden — the T11 net layer that was never built.

``ConGenRunner.run()`` is the ONLY production path that writes ``data/results/**``,
and 0 tests touched it (Layer 3 drives the model, going around the runner). The
T11.4b3 refactor changed it — shuffle-via-``replace`` instead of in-place mutation,
``resolve_result``'s 3-arg signature, ``prepare_task`` — and it was reviewed by
substitution, never gated by a net. A deferral without a ratchet is a wish (T11b.0).

This replays ``run()`` on a fixed FM+bias+examples for BOTH ``shuffle_seed`` paths
and compares the DETERMINISTIC result fields to a golden recorded from ``main``
(``c7d40a0`` — pre-redesign old code, verified byte-identical to this branch at
record time, so the golden gates the whole arc's runner behaviour, not just 4b3).
A red here means ``run()`` drifted: STOP and report — do NOT regenerate to green.

**Re-baselined once for B3 (ADR-0017, 2026-07-19).** The REDUCE MSS-order fix is an
intentional behaviour change, so this golden was deliberately regenerated: only the
reduce-dependent fields moved (``kb_constraints``/``kb_clauses``/``n_kb``/
``redundant_constraints``); ``n_mss``, ``n_bias``, ``bg_clauses``, ``consistency_checks``
and the pinned counts held. From here it again gates against drift — the
"do NOT regenerate to green" rule stands for any future red.

**Re-baselined again (2026-08-28)** for the memorized-negative fixes: the negated
form now asserts the example instead of switching off its guard, so a memorized
fact can be judged redundant for the first time, and the memorized facts are
reduced before the bias constraints. Only the affected fields moved — ``n_ne`` and
``ne_constraints`` (this fold's fact is now discharged, correctly: its minimal
conflict does not depend on the root axiom), and ``kb_constraints`` /
``kb_clauses`` / ``redundant_constraints`` on the unshuffled path. ``n_bias``,
``n_mss``, ``bg_clauses`` and every pinned count held, which is the check that
made the regeneration admissible. The rule stands for any future red.

Only deterministic fields are pinned. The six timing/memory fields (``runtime_ms``,
``memory_peak_mb``, ``*_runtime_ms``, ``solver_time_ms``) are deliberately NOT in
the golden: pinning a wall-clock value makes a flaky net, and a flaky net gets
ignored — someone sees red, calls it noise, and skips a real regression (T16). They
are only checked to be > 0 (they ran).
"""
import json

import pytest

from tests.resource_paths import DATA_DIR
from tests.t11_oracle_net_helpers import FIXTURES_DIR, load_json

_GOLDEN_PATH = FIXTURES_DIR / "congen_runner.json"

# Execution counts pinned by the golden (they live in the profiler ``performance``
# block, alongside the timing fields we drop).
_PINNED_COUNTS = ("acqmss_calls", "is_consistent_calls",
                  "is_consistent_test_cases_calls", "redundancy_consistency_checks")
# Timing/memory — NOT pinned (flaky); only asserted > 0.
_TIMING = ("runtime_ms", "memory_peak_mb", "congen_runtime_ms",
           "acqmss_runtime_ms", "reduce_runtime_ms", "solver_time_ms")


@pytest.fixture(scope="module")
def golden():
    if not _GOLDEN_PATH.exists():
        pytest.fail(
            "golden fixture missing — the ConGenRunner net is NOT running; "
            "record congen_runner.json from main (see module docstring)")
    return load_json(_GOLDEN_PATH)


def _deterministic_fields(result):
    """The pinned subset of a ConGenRunResult — the same extractor used to record the
    golden from main: behavioural output (learned KB + background) + execution counts,
    no timing."""
    perf = result.to_dict().get("performance", {})
    fields = {
        "kb_constraints": list(result.kb_constraints),
        "ne_constraints": list(result.ne_constraints),
        "kb_clauses": [list(c) for c in result.kb_clauses],
        "bg_clauses": [list(c) for c in result.bg_clauses],
        "redundant_constraints": list(result.redundant_constraints),
        "n_bias": result.n_bias,
        "n_mss": result.n_mss,
        "n_kb": result.n_kb,
        "n_ne": result.n_ne,
        "consistency_checks": result.consistency_checks,
    }
    for k in _PINNED_COUNTS:
        fields[k] = perf.get(k)
    return fields


def _run(shuffle_seed):
    """Run ConGenRunner on the fixed REAL-FM-7 probe inputs (non-incremental)."""
    from conacq.runners import ConGenRunner

    ex = json.loads((DATA_DIR / "examples" / "REAL-FM-7_rs_1n.json").read_text())
    pos = [e["assignments"] for e in ex["positive"]]
    neg = [e["assignments"] for e in ex["negative"]]
    runner = ConGenRunner(
        str(DATA_DIR / "bias" / "REAL-FM-7-bias.json"),
        str(DATA_DIR / "fms" / "REAL-FM-7.uvl"),
        use_incremental=False)
    return runner.run(pos, neg, shuffle_seed=shuffle_seed)


@pytest.mark.parametrize("seed,key", [(None, "seed_none"), (42, "seed_42")])
def test_congen_runner_result_is_pinned(golden, seed, key):
    """run() reproduces the deterministic result recorded from main — the unshuffled
    path AND the shuffle_seed=42 path. set_c order changes the execution counts
    (536 vs 538 consistency_checks) while converging to the same KB, so the shuffle
    path is the one most worth pinning and the only one nothing else covered. Red ⇒
    the runner's behaviour drifted ⇒ STOP + report, do not regenerate."""
    assert _deterministic_fields(_run(seed)) == golden[key]


def test_golden_pins_no_timing_fields():
    """Guard the net against itself: no wall-clock/memory field may enter the golden
    — that would make it flaky, and a flaky net gets ignored (T16)."""
    g = load_json(_GOLDEN_PATH)
    for key in ("seed_none", "seed_42"):
        leaked = [t for t in _TIMING if t in g[key]]
        assert not leaked, f"timing fields leaked into golden[{key}]: {leaked}"


def test_timing_fields_run_but_are_unpinned():
    """The timing fields DO run (assert > 0) — their values are just not pinned."""
    perf = _run(None).to_dict().get("performance", {})
    for t in _TIMING:
        assert perf.get(t, 0) > 0, f"{t} did not run"

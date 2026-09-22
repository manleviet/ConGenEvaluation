"""One-time recorder for the T11 oracle interaction-trace golden (Layer 1).

Run ONCE, on the CURRENT (pre-T11) oracle, to freeze the golden fixtures the
replay test asserts against:

    PYTHONPATH=. uv run --no-sync python scripts/build_t11_oracle_net_fixtures.py

For each feature model it writes two committed JSON files under
``tests/fixtures/t11_oracle_net/``:
  - ``queries_<fm>.json``  — frozen membership + completion inputs (seeded once)
  - ``trace_<fm>.json``    — the oracle's answers + pre-query getter snapshot

The replay test loads these and never regenerates them. Re-run this ONLY to
deliberately re-baseline (e.g. an FM file changed); regenerating casually would
defeat the golden. Pass ``--include-slow`` to also record the large busybox FM.
"""
import sys

from conacq.oracle import FMOracle
from tests.t11_oracle_net_helpers import (
    FIXTURES_DIR,
    FM_SPECS,
    build_frozen_queries,
    canonical_snapshot,
    dump_json,
    queries_path,
    replay_answers,
    trace_path,
)
from tests.t11_e2e_harness import record_layer2_layer3


def record_one(name, path, n_membership, m_completion):
    oracle = FMOracle(str(path))
    # Frozen inputs derived from the feature catalog, then committed to disk.
    queries = build_frozen_queries(oracle, n_membership, m_completion)
    # Snapshot BEFORE any query (get_c must be pre-pollution), then answer.
    snapshot = canonical_snapshot(oracle)
    answers = replay_answers(oracle, queries)

    dump_json(queries_path(name), queries)
    dump_json(trace_path(name), {"snapshot": snapshot, "answers": answers})
    n_valid = sum(answers["membership"])
    print(f"  {name}: {len(queries['membership'])} membership "
          f"({n_valid} valid / {len(queries['membership']) - n_valid} invalid), "
          f"{len(queries['completion'])} completions")


def main():
    include_slow = "--include-slow" in sys.argv
    for name, path, slow, n_membership, m_completion in FM_SPECS:
        if slow and not include_slow:
            print(f"  {name}: SKIPPED (slow; pass --include-slow to record)")
            continue
        record_one(name, path, n_membership, m_completion)

    # Layer 2 (prepared-task ID layout) + Layer 3 (E2E learned KB) golden.
    dump_json(FIXTURES_DIR / "layer23_prepared_and_e2e.json", record_layer2_layer3())
    print("  layer23_prepared_and_e2e.json written")
    print("done")


if __name__ == "__main__":
    main()

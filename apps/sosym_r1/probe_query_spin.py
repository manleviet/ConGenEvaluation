#!/usr/bin/env python
"""Distinguish a saturated QuAcq run from a spinning one.

`quacq.py:255-260` documents a liveness hazard: when FindC cannot isolate a
constraint, `generate_from_sat` can re-propose the identical query indefinitely. The
band-aid that breaks the loop is scoped to oracle mode, and the comment states that
example_first's SAT fallback shares the same spin and is not covered.

That gives "the KB stopped growing" two readings with opposite meanings:

  saturation - extraction ran out of things to find; the extra budget was spent on
               genuinely new queries that happened to teach nothing.
  spin       - the run is re-asking one query; the extra budget bought nothing
               because it bought nothing new.

They separate cleanly on evidence. Under a spin the DISTINCT query count plateaus
while the counter climbs; under saturation distinct keeps rising roughly with total.
This reports the curve so the two cannot be confused, and it reads query_history off
the runner directly because the CV fold dict does not carry it.

    probe_query_spin.py --kb arcade-game --sampling rs_1n --cap 5000 [--folds 0 1 2]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.eval import load_folds, apply_folds          # noqa: E402
from conacq.examples import ExampleIO                    # noqa: E402
from conacq.runners import QuAcqRunner                   # noqa: E402


def query_key(config: dict) -> tuple:
    """Identity of a query, order-independent."""
    return tuple(sorted(config.items()))


def run_fold(runner: QuAcqRunner, pos, neg, fold_data, fold_idx: int) -> dict:
    """Mirror cross_validation._compute_fold's split and seeding exactly."""
    train_pos, train_neg, _, _ = apply_folds(fold_data, pos, neg, fold_idx)
    rng = random.Random(fold_data.shuffle_seeds[fold_idx])
    rng.shuffle(train_pos)
    rng.shuffle(train_neg)

    result = runner.run(train_pos, train_neg,
                        shuffle_seed=fold_data.shuffle_seeds[fold_idx])

    seen, curve, sources = set(), [], {}
    for i, (config, _answer, source) in enumerate(result.query_history, start=1):
        seen.add(query_key(config))
        curve.append(len(seen))
        sources[source] = sources.get(source, 0) + 1

    total = len(result.query_history)
    distinct = len(seen)
    # Where the distinct curve stops moving: the last query index that introduced a
    # query never seen before. A spin pins this far below the total.
    last_new = max((i for i, d in enumerate(curve, start=1)
                    if i == 1 or d > curve[i - 2]), default=0)
    return {
        'fold': fold_idx, 'total_queries': total, 'distinct_queries': distinct,
        'repeat_fraction': round(1 - distinct / total, 4) if total else None,
        'last_new_query_at': last_new,
        'queries_after_last_new': total - last_new,
        'n_kb': len(result.kb_constraints),
        'convergence_reason': result.convergence_reason,
        'sources': sources,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--kb', required=True)
    ap.add_argument('--sampling', default='rs_1n')
    ap.add_argument('--cap', type=int, default=5000)
    ap.add_argument('--mode', default='example_first')
    ap.add_argument('--folds', nargs='+', type=int, default=[0, 1, 2])
    ap.add_argument('--out')
    args = ap.parse_args()

    model = f"{args.kb}_{args.sampling}"
    examples = ExampleIO.load_json(str(REPO / 'data' / 'examples' / f'{model}.json'))
    pos = [e.assignments for e in examples.positive]
    neg = [e.assignments for e in examples.negative]
    fold_data = load_folds(str(REPO / 'data' / 'folds' / f'{model}_folds.json'))

    runner = QuAcqRunner(
        bias_path=str(REPO / 'data' / 'bias' / f'{args.kb}-bias.json'),
        fm_path=str(REPO / 'data' / 'fms' / f'{args.kb}.uvl'),
        solver_name='glucose4', max_queries=args.cap,
        query_mode=args.mode, use_incremental=True, timeout_s=6 * 3600)

    rows = []
    try:
        for fold in args.folds:
            row = run_fold(runner, pos, neg, fold_data, fold)
            rows.append(row)
            # Checkpoint per fold. This tool drives the runner in process rather than
            # through run_cv, so it produces no partials and, before this, wrote nothing
            # until every fold had finished. A busybox fold stopped at 2 h 19 min on
            # 2026-08-26 left nothing at all behind. A fold that completes is a
            # measurement; it should survive whatever happens to the next one.
            if args.out:
                Path(args.out).write_text(json.dumps(rows, indent=2))
            print(f"  fold {fold}: total={row['total_queries']:>5d} "
                  f"distinct={row['distinct_queries']:>5d} "
                  f"repeat={row['repeat_fraction']:>7} "
                  f"last_new_at={row['last_new_query_at']:>5d} "
                  f"after={row['queries_after_last_new']:>5d} "
                  f"n_kb={row['n_kb']} stop={row['convergence_reason']}", flush=True)
    finally:
        runner.cleanup()

    print(f"\n{args.kb} {args.sampling} {args.mode} cap={args.cap}")
    for row in rows:
        # The repeat FRACTION is not the test. A healthy run re-asks plenty: FindScope
        # narrows by re-querying variants and FindC discriminates by re-querying, so a
        # 60-70% repeat rate is ordinary. What distinguishes a spin is WHEN novelty
        # stopped -- a spun run stops discovering queries early and then burns the rest
        # of the budget, so `queries_after_last_new` is most of the total.
        after, total = row['queries_after_last_new'], row['total_queries']
        tail = after / total if total else 0
        verdict = (f"SPIN: novelty stopped at query {row['last_new_query_at']}, "
                   f"{after} of {total} queries ({tail:.0%}) bought nothing"
                   if tail > 0.25 else
                   f"no spin: still finding new queries at {row['last_new_query_at']} "
                   f"of {total}; the run is budget-limited, not stuck")
        print(f"  fold {row['fold']}: {verdict}")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

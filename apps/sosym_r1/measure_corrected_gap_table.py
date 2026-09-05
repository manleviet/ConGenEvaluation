#!/usr/bin/env python
"""The ConGen-minus-iterative gap, per cell, with both trees named.

The gap is what the paper claims, so the gap is what this reports -- not two columns
a reader has to subtract. Every number carries the tree it came from, because the
defect this replaces was not a wrong value but a PAIRING: a corrected ConGen column
set beside an uncorrected iterative one, which matches no tree and cannot be
reproduced from the repo.

    OLD = data/results               -- the tree the published tables were computed from
    NEW = data/results_sosym_r1      -- re-scored ConGen (9162802) + re-scored
                                        interactive, each fold against its own oracle

MODE COLLAPSE. In OLD, many cells carry the identical iterative F1 under example_only
and example_first -- arcade rs_3n is 0.0382 under both. That is the extractor having
lost its method axis (fixed at 2157122), not a finding about the two modes. Those
cells are marked: the published active-vs-passive comparison there was uninformative
rather than merely mis-scored, and the distinction matters when deciding what a
corrected number overturns.

QUERIES AND STOPPING RULE, together. ConGen issues no oracle queries -- it is passive,
and its folds record no n_queries at all. The baseline's count is read per fold and
averaged, and the stopping rule sits beside it because the three rules mean three
different things and an F1 cannot tell them apart:

    max_queries    (66 folds) budget-limited -- a lower bound, could improve with more
    no_query       (18 folds) converged: it asked every question available to it
    pool_exhausted (84 folds) data-limited -- bounded by the example pool, not the budget

A gap at no_query is a stronger result than a gap at max_queries: there, the active
baseline ran out of questions and still lost.

SCOPE. The correction table covers only the 18 cells that exist in OLD -- those are the
published ones, the only rows a correction can supersede. busybox and REAL-FM-4 exist
in NEW alone; they correct nothing and are reported separately as new evidence.

    measure_corrected_gap_table.py                 # every cell in both trees
    measure_corrected_gap_table.py --tree new      # the corrected table alone
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TREES = {'old': REPO / 'data' / 'results', 'new': REPO / 'data' / 'results_sosym_r1'}
STEMS = ['REAL-FM-4', 'REAL-FM-7', 'arcade-game', 'busybox-1.18.0', 'fqa']
SAMPLINGS = ['rs_1n', 'rs_2n', 'rs_3n', 'rs_m', '2cov', 'ff']
MODES = ['example_only', 'example_first']


def semantic(fold: dict) -> dict:
    """evaluation.semantic.metrics -- one level up holds the strategy label, not numbers."""
    return ((fold.get('evaluation') or {}).get('semantic') or {}).get('metrics') or {}


def fold_mean(path: Path, key: str = 'f1_score'):
    """A cell is the mean over folds. Never the intersected KB, never a pooled figure."""
    if not path.exists():
        return None
    folds = json.loads(path.read_text())['folds']
    vals = [semantic(f).get(key) for f in folds if semantic(f)]
    return st.mean(vals) if vals else None


def queries_of(path: Path):
    """Mean oracle queries per fold, and the stopping rules observed."""
    if not path.exists():
        return None, set()
    folds = json.loads(path.read_text())['folds']
    n = [f.get('n_queries') for f in folds if f.get('n_queries') is not None]
    return (st.mean(n) if n else None), {f.get('convergence_reason') for f in folds}


def cell(tree: Path, stem: str, samp: str, mode: str) -> dict | None:
    cg = fold_mean(tree / 'congen' / f'{stem}_{samp}_cv_incremental.json')
    it_path = tree / 'interactive' / f'{stem}_{samp}_cv_incremental_{mode}.json'
    it = fold_mean(it_path)
    if cg is None or it is None:
        return None
    nq, stops = queries_of(it_path)
    return {'congen': cg, 'iterative': it, 'gap': cg - it, 'queries': nq, 'stops': stops}


def collapsed(tree: Path, stem: str, samp: str) -> bool:
    """Identical iterative F1 under both modes: the lost-method-axis signature."""
    a = fold_mean(tree / 'interactive' / f'{stem}_{samp}_cv_incremental_example_only.json')
    b = fold_mean(tree / 'interactive' / f'{stem}_{samp}_cv_incremental_example_first.json')
    return a is not None and b is not None and abs(a - b) < 1e-12


def published(stem: str, samp: str) -> bool:
    """Is the whole cell in OLD? Only those can be superseded.

    BOTH halves must exist: data/results/congen carries REAL-FM-4 files with no
    interactive counterpart, so a congen-only check counts cells whose old gap was
    never computable and puts un-correctable rows in a correction table.
    """
    return _row('old', stem, samp) is not None


def _row(tree_name: str, stem: str, samp: str):
    cs = {m: cell(TREES[tree_name], stem, samp, m) for m in MODES}
    return None if any(v is None for v in cs.values()) else cs


def _fmt(c: dict) -> str:
    q = f"{c['queries']:.0f}" if c['queries'] is not None else '—'
    stop = ','.join(sorted(x for x in c['stops'] if x)) or '—'
    return f"{c['iterative']:7.4f} {c['gap']:+8.4f} {q:>6s} {stop:14s}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--section', choices=['correction', 'new', 'wins', 'all'], default='all')
    args = ap.parse_args()

    cells = [(s, m) for s in STEMS for m in SAMPLINGS if _row('new', s, m)]
    hdr = (f"{'cell':22s} {'mode':6s} {'ConGen':>7s} | {'iter':>7s} {'gap':>8s} "
           f"{'q':>6s} {'stop':14s}")

    if args.section in ('correction', 'all'):
        pub = [(s, m) for s, m in cells if published(s, m)]
        print(f"{'='*92}\nCORRECTION TABLE -- the {len(pub)} published cells\n"
              f"OLD = {TREES['old'].relative_to(REPO)}   "
              f"NEW = {TREES['new'].relative_to(REPO)}\n{'='*92}")
        for stem, samp in pub:
            col = ' [mode-collapsed in OLD]' if collapsed(TREES['old'], stem, samp) else ''
            print(f"\n{stem} {samp}{col}")
            print('  ' + hdr)
            for tree in ('old', 'new'):
                r = _row(tree, stem, samp)
                for mode in MODES:
                    print(f"  {tree.upper():22s} {mode[8:]:6s} "
                          f"{r[mode]['congen']:7.4f} | {_fmt(r[mode])}")

    if args.section in ('new', 'all'):
        new = [(s, m) for s, m in cells if not published(s, m)]
        print(f"\n{'='*92}\nNEW EVIDENCE -- {len(new)} cells absent from OLD, "
              f"superseding nothing\n{'='*92}")
        print(hdr)
        for stem, samp in new:
            r = _row('new', stem, samp)
            for mode in MODES:
                print(f"{stem+' '+samp:22s} {mode[8:]:6s} "
                      f"{r[mode]['congen']:7.4f} | {_fmt(r[mode])}")

    if args.section in ('wins', 'all'):
        both = [(s, m) for s, m in cells
                if all(_row('new', s, m)[x]['gap'] < 0 for x in MODES)]
        first = [(s, m) for s, m in cells
                 if _row('new', s, m)['example_only']['gap'] >= 0
                 and _row('new', s, m)['example_first']['gap'] < 0]
        print(f"\n{'='*92}\nWHERE THE BASELINE WINS, in NEW ({len(cells)} cells)\n{'='*92}")
        print(f"both modes: {len(both)}    example-first only: {len(first)}")
        for stem, samp in first:
            r = _row('new', stem, samp)
            print(f"\n  {stem} {samp} -- the win refutes itself on the query axis:")
            print('  ' + hdr)
            for mode in MODES:
                print(f"  {'':22s} {mode[8:]:6s} {r[mode]['congen']:7.4f} | {_fmt(r[mode])}")
            o, f = r['example_only'], r['example_first']
            print(f"    the cheap configuration LOSES by {o['gap']:+.4f} at "
                  f"{o['queries']:.0f} queries; the winning one needs "
                  f"{f['queries']:.0f} to gain {-f['gap']:.4f}, against ConGen's 0.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

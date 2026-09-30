#!/usr/bin/env python3
"""Negative-example minimization is optional: the numbers the paper and letter quote.

GenerateNE reduces each e- to a subset-minimal conflict with QuickXplain against the
oracle unless ``[evaluation.congen] neg_mode = "raw"``, which negates the full e- and
never consults it. data/results_sosym_r1_rawne/congen/ reruns the committed ConGen sweep
that way -- same folds, seed, solver and bias shuffle -- for 27 of the 28 combinations.
busybox RS(n) was not rerun: its committed folds alone took 12.6 h.

Paper (S6.2.5):
  M1  27 of 28 combinations rerun without minimization; busybox RS(n) not rerun
  M2  the delivered theory is logically equivalent on every rerun fold
  M3  test-fold accuracy is identical on every rerun fold
  M4  on the folds where the reduced run retains a ¬e-, the KB is larger without
      minimization: relative reduction 1 - (|KB|+n_ne)_red / (|KB|+n_ne)_raw,
      median and maximum
  M5  semantic recall is 1.0 without minimization on every rerun combination
Letter:
  L1  |KB| + n_ne summed over the rerun folds, reduced vs raw
  L2  counting the retained ¬e- as learned restores recall 1.000 on every reduced
      combination below 1; busybox RS(n) stays below
  L3  GenerateNE checks saved per fold
  L4  the busybox RS(n) cost not spent, from its committed per-fold runtimes
  L5  the extreme fold of M4

WHAT IS RECOMPUTED AND WHAT IS READ. Everything except M2 and L2 is recomputed here
from the fold files. M2 is a SAT entailment in both directions per fold and L2 a
semantic re-scoring; they are read from the JSON that compare_ne_raw_vs_reduced.py
and score_with_retained_ne.py write, because the mutation harness re-runs this module
once per assertion. That JSON is not trusted blind: its fold set and its per-fold
|KB| and n_ne are checked against the fold files first, so a stale file fails here.

EVERY CELL-LEVEL VALUE IS A MEAN OVER FOLDS, as the tables compute it.

    PYTHONPATH=. python3 apps/sosym_r1/revision_ne_minimization.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

NOT_RERUN = 'busybox-1.18.0_rs_1n'

M = {'rerun': 27, 'combinations': 28, 'folds': 81,
     'equivalent_folds': 81, 'same_accuracy_folds': 81,
     'folds_retaining_ne': 51, 'median_reduction': 0.103, 'max_reduction': 0.994,
     'median_percent': 10, 'max_percent': 99, 'recall_one_combinations': 27}
L = {'size_reduced': 12509, 'size_raw': 18038,
     'below_one': 9, 'restored': 9, 'not_rerun_recall_with_ne': 0.998,
     'saved_min': 0, 'saved_median': 67, 'saved_max': 748,
     'not_rerun_fold_hours': ('4.10', '4.18', '4.34'), 'not_rerun_hours': 12.6,
     'extreme': ('busybox-1.18.0_2cov', 0, 4, 1, 842, 0)}


def _cells(tree: Path) -> dict[str, list[dict]]:
    return {f.name.split('_cv_')[0]: json.loads(f.read_text())['folds']
            for f in sorted(tree.glob('*_cv_incremental.json'))}


def _size(fold: dict) -> int:
    """|KB| + n_ne: the delivered constraints, bias and memorized alike."""
    return len(fold['kb_constraints']) + fold['statistics']['n_ne']


def _genne(fold: dict) -> int:
    """GenerateNE's QuickXplain checks. Absent means the phase never ran, which is a
    measured zero only when the split has no negatives (reduced) or the fold is raw."""
    got = fold['performance']['profiler'].get('shared_preprocessing_quickxplain_checks')
    return 0 if got is None else got


def _recall(folds: list[dict]) -> float:
    return statistics.mean(f['evaluation']['semantic']['metrics']['recall'] for f in folds)


def run(check, repo: Path) -> None:
    red = _cells(repo / 'data' / 'results_sosym_r1' / 'congen')
    raw = _cells(repo / 'data' / 'results_sosym_r1_rawne' / 'congen')
    pairs = [(m, a, b) for m in sorted(raw)
             for a, b in zip(red[m], raw[m], strict=True)]
    for _, a, b in pairs:
        assert a['fold_index'] == b['fold_index']
        if b['train_size']['negative'] and a['train_size']['negative']:
            assert b['performance']['profiler'].get(
                'shared_preprocessing_quickxplain_checks', 0) == 0, 'raw fold ran QuickXplain'

    # M1
    check('M1: combinations rerun without minimization', len(raw), M['rerun'])
    check('M1: combinations in the committed sweep', len(red), M['combinations'])
    check('M1: the one not rerun', sorted(set(red) - set(raw)), [NOT_RERUN])
    check('M1: rerun folds', len(pairs), M['folds'])

    # M2, read from the SAT comparison after checking it describes these folds.
    cmp_ = json.loads((repo / 'data/results_sosym_r1_rawne/raw-vs-reduced.json').read_text())
    by_key = {(r['model'], r['fold']): r for r in cmp_['folds']}
    check('M2: the SAT comparison covers exactly the rerun folds',
          sorted(by_key) == sorted((m, a['fold_index']) for m, a, _ in pairs), True)
    check('M2: ... and agrees with the fold files on |KB| and n_ne',
          all(by_key[(m, a['fold_index'])]['reduced']['kb'] == len(a['kb_constraints'])
              and by_key[(m, a['fold_index'])]['raw']['kb'] == len(b['kb_constraints'])
              and by_key[(m, a['fold_index'])]['reduced']['n_ne'] == a['statistics']['n_ne']
              and by_key[(m, a['fold_index'])]['raw']['n_ne'] == b['statistics']['n_ne']
              for m, a, b in pairs), True)
    check('M2: folds whose delivered theories are logically equivalent',
          sum(r['equivalence']['verdict'] == 'equivalent' for r in cmp_['folds']),
          M['equivalent_folds'])

    # M3
    check('M3: folds with identical test-fold accuracy',
          sum(a['accuracy'] == b['accuracy'] for _, a, b in pairs), M['same_accuracy_folds'])

    # M4, L1, L5
    retaining = [(m, a, b) for m, a, b in pairs if a['statistics']['n_ne'] > 0]
    rel = [1 - _size(a) / _size(b) for _, a, b in retaining]
    check('M4: folds where the reduced run retains a ¬e-', len(retaining),
          M['folds_retaining_ne'])
    check('M4: relative reduction 1-(|KB|+n_ne)_red/(|KB|+n_ne)_raw, median',
          round(statistics.median(rel), 3), M['median_reduction'], tol=1e-9)
    check('M4: ... maximum', round(max(rel), 3), M['max_reduction'], tol=1e-9)
    check('M4: "a median of 10%"', round(100 * statistics.median(rel)), M['median_percent'])
    check('M4: "up to 99%"', int(100 * max(rel)), M['max_percent'])
    check('M4: raw retains no ¬e- on any fold', sum(b['statistics']['n_ne'] for _, _, b in pairs), 0)
    check('L1: |KB|+n_ne summed over the rerun folds, reduced',
          sum(_size(a) for _, a, _ in pairs), L['size_reduced'])
    check('L1: ... raw', sum(_size(b) for _, _, b in pairs), L['size_raw'])
    m, a, b = max(retaining, key=lambda t: 1 - _size(t[1]) / _size(t[2]))
    check('L5: the extreme fold, reduced |KB|, n_ne vs raw |KB|, n_ne',
          (m, a['fold_index'], len(a['kb_constraints']), a['statistics']['n_ne'],
           len(b['kb_constraints']), b['statistics']['n_ne']), L['extreme'])

    # M5, L2
    check('M5: rerun combinations with semantic recall 1.0 without minimization',
          sum(_recall(raw[m]) == 1.0 for m in raw), M['recall_one_combinations'])
    below = [m for m in raw if round(_recall(red[m]), 3) < 1]
    with_ne = json.loads(
        (repo / 'data/results_sosym_r1_rawne/reduced-scored-with-ne.json').read_text())
    check('L2: the re-scoring covers every committed reduced fold, and reproduces its '
          'stored recall when the ¬e- is excluded',
          sorted((r['model'], r['fold']) for r in with_ne)
          == sorted((m, f['fold_index']) for m in red for f in red[m])
          and all(abs(r['excluded']['semantic']['recall'] - next(
              f for f in red[r['model']] if f['fold_index'] == r['fold'])
              ['evaluation']['semantic']['metrics']['recall']) < 1e-12 for r in with_ne), True)

    def recall_with_ne(model):
        return statistics.mean(r['included']['semantic']['recall']
                               for r in with_ne if r['model'] == model)
    check('L2: rerun combinations whose reduced recall prints below 1.000',
          len(below), L['below_one'])
    check('L2: ... restored to 1.000 by counting the retained ¬e- as learned',
          sum(round(recall_with_ne(m), 3) == 1.0 for m in below), L['restored'])
    check('L2: busybox RS(n) (not rerun) with its ¬e- counted, recall',
          round(recall_with_ne(NOT_RERUN), 3), L['not_rerun_recall_with_ne'], tol=1e-9)

    # L3
    saved = [_genne(a) - _genne(b) for _, a, b in pairs]
    check('L3: GenerateNE checks saved per fold, min', min(saved), L['saved_min'])
    check('L3: ... median', statistics.median(saved), L['saved_median'])
    check('L3: ... max', max(saved), L['saved_max'])

    # L4
    hours = [f['performance']['runtime_ms'] / 3.6e6 for f in red[NOT_RERUN]]
    check('L4: busybox RS(n) committed per-fold hours',
          tuple(f'{h:.2f}' for h in hours), L['not_rerun_fold_hours'])
    check('L4: ... cost not spent, hours', round(sum(hours), 1), L['not_rerun_hours'], tol=1e-9)


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    failed: list[str] = []

    def check(name, got, want, tol=None):
        ok = (abs(got - want) <= (5e-3 if tol is None else tol)
              if isinstance(want, float) else got == want)
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}: {got!r}")
        if not ok:
            failed.append(f'{name}: got {got!r}, expected {want!r}')
    run(check, repo)
    for f in failed:
        print('FAIL', f)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

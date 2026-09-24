#!/usr/bin/env python3
"""The figures the abstract, the conclusion and the discussion put their name to.

WHY THESE ARE GATED SEPARATELY FROM THE SECTION THAT PRODUCED THEM
------------------------------------------------------------------
A number in the abstract is a number a reader meets before any method, table or
caveat. It is also the number most likely to be stale, because the abstract is
written first and revised last, and nothing recomputes it. Each figure here is
therefore re-derived from the fold files -- not read back from the section that
introduced it, and not from a table.

THE BIAS REDUCTION IS QUOTED TWICE, WITH TWO ROUNDING ORDERS
-------------------------------------------------------------
"70.4%--99.9% of the candidate constraints" holds exactly, computed from the
unrounded per-cell means of |KB| against |B|.

S6.1.2's KB1 figures do not, and the reason is worth naming rather than smoothing
over: the paper reads KB1's |KB| off Table 13 as 9 and 19 -- which are 8.7 and 18.7
rounded -- and computes the percentages from those. Recomputing from the means gives
93.7%--97.1% against the printed 93.6%--96.9%. Both forms are asserted below, each
labelled with the order it was derived in, so a reader can see that the difference is
a rounding order and not a disagreement about the data.

CONSERVATIVE ERRORS
-------------------
"No invalid configuration is accepted on any fold" is the strongest claim the paper
makes about the shape of the errors, and it is a claim about ALL 84 folds, not a
mean. It is asserted as a total over folds, which is zero, together with the number
of folds that carried a classification at all -- a sum of nothing is also zero.
"""
from __future__ import annotations

import statistics
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from revision_cells import KNOWLEDGE_BASES, SAMPLINGS, folds

BIAS = Path('data') / 'bias'

# Abstract, Conclusion, Discussion (7).
PAPER_RECALL_SATURATED, PAPER_CELLS = 18, 28
PAPER_MAX_PRECISION = 0.994
PAPER_REDUCTION = (70.4, 99.9)
PAPER_REDUCTION_EXTREMES = {'lowest': ('fqa', 'rs_3n'), 'highest': ('busybox-1.18.0', '2cov')}
# S6.1.2, derived from the ROUNDED |KB| the table prints. See the module docstring.
PAPER_KB1_REDUCTION_FROM_ROUNDED = (93.6, 96.9)
PAPER_KB1_KB_ROUNDED = {'2cov': 9, 'rs_2n': 19}

# Discussion (1): scalability, the two ends of it.
PAPER_KB1_SLOWEST_CELL_MS = 623
PAPER_KB5_RS1N_HOURS = 4.2

# Threats to validity, internal.
PAPER_DEGENERATE_MAX_SPREAD = 0.71
PAPER_ALL_FOLD_MEDIAN_SPREAD = 0.005      # printed here, deliberately not gated


def half_up(value: float, places: int) -> float:
    q = Decimal(1).scaleb(-places)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


def _semantic(fold: dict) -> dict:
    return (((fold.get('evaluation') or {}).get('semantic') or {}).get('metrics') or {})


def bias_constraints(repo: Path, stem: str) -> int:
    """|B| for one model, from the committed bias statistics."""
    for line in (repo / BIAS / f'{stem}-bias-stats.txt').read_text().splitlines():
        if line.startswith('Total constraints:'):
            return int(line.split(':')[1].strip())
    raise ValueError(f'{stem}-bias-stats.txt states no total constraint count')


def run(check, repo: Path) -> None:
    print('\n[headline] the semantic figures the abstract and the conclusion quote')
    recall, precision, false_positives, scored = {}, {}, 0, 0
    for sampling in SAMPLINGS:
        for stem, _label in KNOWLEDGE_BASES:
            fs = folds(repo, stem, sampling, 'congen')
            if not fs:
                continue
            cell = (sampling, stem)
            recall[cell] = statistics.mean(_semantic(f).get('recall', 0.0) for f in fs)
            precision[cell] = statistics.mean(_semantic(f).get('precision', 0.0) for f in fs)
            for f in fs:
                metrics = f.get('metrics') or {}
                if metrics:
                    scored += 1
                    false_positives += metrics.get('false_positives', 0)
    check('combinations scored', len(recall), PAPER_CELLS)
    check('combinations at semantic recall 1.000',
          sum(1 for v in recall.values() if abs(v - 1.0) < 1e-9), PAPER_RECALL_SATURATED)
    # The complement of the recall claim: precision never reaches 1, on any of them.
    check('combinations where semantic precision reaches 1',
          [c for c, v in precision.items() if v >= 1.0], [])
    check('   ... the closest any of them gets, as printed',
          half_up(max(precision.values()), 3), PAPER_MAX_PRECISION, tol=1e-9)

    # A positive denominator first: zero false positives over zero folds is not a
    # finding, and that is exactly how this claim would pass while meaning nothing.
    check('folds carrying a classification', scored, 84)
    check('   ... and invalid configurations accepted, over all of them',
          false_positives, 0)

    print('\n[headline] bias reduction, and the two rounding orders it is quoted in')
    reduction = {}
    for sampling in SAMPLINGS:
        for stem, _label in KNOWLEDGE_BASES:
            fs = folds(repo, stem, sampling, 'congen')
            if not fs:
                continue
            kb = statistics.mean(len(f['kb_constraints']) for f in fs)
            reduction[(stem, sampling)] = (1 - kb / bias_constraints(repo, stem)) * 100
    check('combinations with a reduction', len(reduction), PAPER_CELLS)
    lowest = min(reduction, key=reduction.get)
    highest = max(reduction, key=reduction.get)
    check('smallest reduction, as printed', half_up(reduction[lowest], 1),
          PAPER_REDUCTION[0], tol=1e-9)
    check('   ... and the combination it is at', lowest, PAPER_REDUCTION_EXTREMES['lowest'])
    check('largest reduction, as printed', half_up(reduction[highest], 1),
          PAPER_REDUCTION[1], tol=1e-9)
    check('   ... and the combination it is at', highest, PAPER_REDUCTION_EXTREMES['highest'])

    kb1 = {s: statistics.mean(len(f['kb_constraints'])
                              for f in folds(repo, 'REAL-FM-7', s, 'congen'))
           for s in SAMPLINGS}
    b1 = bias_constraints(repo, 'REAL-FM-7')
    for sampling, printed in PAPER_KB1_KB_ROUNDED.items():
        check(f'KB1 {sampling}: |KB| as Table 13 prints it, rounded to a constraint',
              round(kb1[sampling]), printed)
    from_rounded = sorted((1 - printed / b1) * 100
                          for printed in PAPER_KB1_KB_ROUNDED.values())
    check('KB1 reduction from the ROUNDED |KB|, which is what S6.1.2 prints',
          (half_up(from_rounded[0], 1), half_up(from_rounded[1], 1)),
          PAPER_KB1_REDUCTION_FROM_ROUNDED)
    unrounded = sorted((1 - kb1[s] / b1) * 100 for s in ('rs_2n', '2cov'))
    print(f'      ... from the unrounded means it is '
          f'{half_up(unrounded[0], 1)}--{half_up(unrounded[1], 1)}%, '
          f'a rounding order apart and not a different measurement')

    print('\n[headline] Discussion (1): the two ends of the cost')
    kb1_cells = {s: statistics.mean(f['performance']['runtime_ms']
                                    for f in folds(repo, 'REAL-FM-7', s, 'congen'))
                 for s in SAMPLINGS}
    check('KB1: the slowest of its cells, in ms',
          round(max(kb1_cells.values())), PAPER_KB1_SLOWEST_CELL_MS)
    # The sentence says "per fold", and a cell is a mean of three. A mean under a
    # second does not establish that every fold was, so the folds are checked too.
    kb1_folds = [f['performance']['runtime_ms'] for s in SAMPLINGS
                 for f in folds(repo, 'REAL-FM-7', s, 'congen')]
    check('   ... folds behind those cells', len(kb1_folds), 18)
    check('   ... and every one of them under a second',
          [ms for ms in kb1_folds if ms >= 1000], [])
    kb5 = [f['performance']['runtime_ms']
           for f in folds(repo, 'busybox-1.18.0', 'rs_1n', 'congen')]
    check('KB5 RS(n): hours per fold, as printed',
          half_up(statistics.mean(kb5) / 3.6e6, 1), PAPER_KB5_RS1N_HOURS, tol=1e-9)

    print('\n[threats] how far the twelve degenerate folds move, and the median that hides them')
    import json
    from revision_order_and_working_example import DEGENERATE_THRESHOLD, f1_spreads
    data = json.loads((repo / 'data' / 'results_sosym_r1' / 'order_sensitivity'
                       / 'order_sensitivity.json').read_text())
    spreads = [f1_spreads(r)['semantic'] for r in data['folds']]
    check('folds measured across 20 orders', len(spreads), 84)
    degenerate = [s for s in spreads if s > DEGENERATE_THRESHOLD]
    check('the twelve that move most', len(degenerate), 12)
    check('   ... and how far the worst of them moves, as printed',
          half_up(max(degenerate), 2), PAPER_DEGENERATE_MAX_SPREAD, tol=1e-9)
    # Printed, NOT asserted: the paper's 0.004 is the median over the 72 folds the
    # sentence excepts the twelve from, and that is already gated. This is the median
    # the sentence does not quote, kept visible so the two cannot be confused.
    print(f'      the median over all 84 folds is '
          f'{half_up(statistics.median(spreads), 3)}, not the quoted 0.004 -- the '
          f'quoted one excepts the twelve, as the sentence says')

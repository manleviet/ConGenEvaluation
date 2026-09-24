#!/usr/bin/env python3
"""Table 13's ranges and the two paragraphs of S6.2.5 that read it aloud.

WHAT IS NEW HERE, AND WHY A TABLE CHECK IS NOT ENOUGH
-----------------------------------------------------
`check_paper_tables.py` re-derives every CELL of Table 13. That proves each printed
number, and proves nothing about the sentences that summarise them: "on all 23
non-2-COV combinations", "on 27 of 28", "1.6 to 1,952 times". Those are claims about
the SHAPE of the grid, and a grid can be cell-perfect while the sentence about it is
stale -- which is how a summary sentence outlives the table it summarises.

Every count below is therefore recomputed from the fold files, with its denominator
asserted first. A "27 of 28" whose 28 was never checked is a fraction with one
measured half.

THE COMPARISON IS AGAINST THE ACCEPT-EVERYTHING BASELINE, PER FOLD
------------------------------------------------------------------
S6.2.5 compares each method's accuracy with the share of the test fold that is a
valid configuration -- the accuracy of accepting everything. On folds with almost no
positive configuration that share is high, which is the point being made: a method
can look accurate there without having learned anything. The share is computed per
fold and then averaged, like the accuracy it is compared against.
"""
from __future__ import annotations

from pathlib import Path

from revision_cells import (KNOWLEDGE_BASES, METHODS, accuracy, grid, kb_size,
                            positive_share, runtime_ms)

# Table 13, as the manuscript prints it: the extremes of each method's |KB| column,
# and of the example-only accuracy column.
PAPER_KB_RANGE = {'example_only': (0.0, 8.7), 'example_first': (2.0, 40.7),
                  'congen': (6.7, 687.0)}
PAPER_EXAMPLE_ONLY_ACC = (0.667, 1.000)
# The one cell the paragraph names: an empty knowledge base at 0.917 accuracy.
PAPER_EMPTY_KB_CELL = ('rs_m', 'REAL-FM-7', 0.0, 0.917)
# QUOTED IN THE RESPONSE LETTER ONLY. The paper prints the six zeros in
# Table 13 but no longer counts them in prose. The count is asserted because the
# zeros are what the |KB| column was added to show, and a column whose point is
# carried by six cells should not depend on a reader noticing them.
LETTER_EMPTY_KB_CELLS = 6

# S6.2.5, accuracy paragraph.
PAPER_NON_2COV, PAPER_2COV = 23, 5
PAPER_FIRST_ABOVE_SHARE, PAPER_CONGEN_BELOW_SHARE = 27, 20
PAPER_SHARE_TIE = ('rs_m', 'REAL-FM-7')

# S6.2.5, runtime paragraph.
PAPER_FIRST_SLOWEST = 27
PAPER_FIRST_OVER_ONLY = (1.6, 1952.3)
PAPER_FASTEST_COUNTS = {'example_only': 18, 'congen': 10, 'example_first': 0}
# The fastest cell of each knowledge base, over all six strategies and three methods.
PAPER_FASTEST_PER_KB = {'REAL-FM-7': ('congen', '2cov'), 'fqa': ('congen', 'rs_m'),
                        'arcade-game': ('congen', '2cov'),
                        'REAL-FM-4': ('congen', '2cov'),
                        'busybox-1.18.0': ('congen', '2cov')}


def _round(value: float, places: int) -> float:
    """Round for comparison with a printed figure, half away from zero.

    Python rounds halves to even, so ``round(0.665, 2)`` is 0.66 and a printed 0.67
    would read as drift. Every figure here is compared the way it was typeset.
    """
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-places)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


def run(check, repo: Path) -> None:
    print("\n[T13] Table 13's ranges, recomputed from the folds rather than the table")
    acc = {m: grid(repo, m, accuracy) for m in METHODS}
    kb = {m: grid(repo, m, kb_size) for m in METHODS}
    check('cells with a result, per method',
          sorted({len(v) for v in acc.values()} | {len(v) for v in kb.values()}), [28])

    for method, (lo, hi) in PAPER_KB_RANGE.items():
        sizes = kb[method].values()
        check(f'{method}: |KB| smallest cell', _round(min(sizes), 1), lo, tol=1e-9)
        check(f'{method}: |KB| largest cell', _round(max(sizes), 1), hi, tol=1e-9)
    lo, hi = PAPER_EXAMPLE_ONLY_ACC
    check('example-only: accuracy lowest cell',
          _round(min(acc['example_only'].values()), 3), lo, tol=1e-9)
    check('example-only: accuracy highest cell',
          _round(max(acc['example_only'].values()), 3), hi, tol=1e-9)

    samp, stem, want_kb, want_acc = PAPER_EMPTY_KB_CELL
    check('KB1 RS(m) example-only: the knowledge base is empty',
          _round(kb['example_only'][(samp, stem)], 1), want_kb, tol=1e-9)
    check('   ... and accuracy there is still high',
          _round(acc['example_only'][(samp, stem)], 3), want_acc, tol=1e-9)

    empty = sorted(c for c, v in kb['example_only'].items() if v == 0)
    check('example-only combinations that learned nothing at all (letter only)',
          len(empty), LETTER_EMPTY_KB_CELLS)
    # Neither other method has one, which is what makes the six a property of the
    # regime rather than of the folds they were measured on.
    check('   ... and the same for ConGen and example-first',
          [c for m in ('congen', 'example_first') for c, v in kb[m].items() if v == 0], [])

    print('\n[S6.2.5] the accuracy paragraph: who beats whom, and how often')
    cells = sorted(acc['congen'])
    non_2cov = [c for c in cells if c[0] != '2cov']
    two_cov = [c for c in cells if c[0] == '2cov']
    check('non-2-COV combinations', len(non_2cov), PAPER_NON_2COV)
    check('2-COV combinations', len(two_cov), PAPER_2COV)
    # Reported as the cells that BREAK the claim, so a failure names them.
    check('non-2-COV cells where example-first does NOT beat ConGen',
          [c for c in non_2cov if acc['example_first'][c] <= acc['congen'][c]], [])
    check('2-COV cells where ConGen does NOT match or beat example-first',
          [c for c in two_cov if acc['congen'][c] < acc['example_first'][c]], [])

    share = grid(repo, 'congen', positive_share)
    check('cells with a positive share', len(share), 28)
    above = [c for c in cells if acc['example_first'][c] > share[c]]
    ties = [c for c in cells if abs(acc['example_first'][c] - share[c]) < 1e-9]
    check('cells where example-first beats the accept-everything baseline',
          len(above), PAPER_FIRST_ABOVE_SHARE)
    # A tie is not a win and not a loss; the paragraph names this cell, so the check
    # names it too rather than letting "27 of 28" hide which one is missing.
    check('   ... and the one that only ties it', ties, [PAPER_SHARE_TIE])
    check('   ... with none below it',
          [c for c in cells if acc['example_first'][c] < share[c]], [])
    check('cells where ConGen is below that baseline',
          sum(1 for c in cells if acc['congen'][c] < share[c]),
          PAPER_CONGEN_BELOW_SHARE)

    print('\n[S6.2.5] the runtime paragraph: slowest, fastest, and the spread')
    rt = {m: grid(repo, m, runtime_ms) for m in METHODS}
    slowest = [c for c in cells
               if rt['example_first'][c] == max(rt[m][c] for m in METHODS)]
    check('cells where example-first is the slowest method',
          len(slowest), PAPER_FIRST_SLOWEST)
    ratios = [rt['example_first'][c] / rt['example_only'][c] for c in cells]
    lo, hi = PAPER_FIRST_OVER_ONLY
    check('example-first over example-only, smallest ratio',
          _round(min(ratios), 1), lo, tol=1e-9)
    check('   ... and largest', _round(max(ratios), 1), hi, tol=1e-9)

    fastest = {m: 0 for m in METHODS}
    for c in cells:
        fastest[min(METHODS, key=lambda m: rt[m][c])] += 1
    check('which method is fastest, per cell', fastest, PAPER_FASTEST_COUNTS)

    # The fastest CELL of each knowledge base, which is a different statement from
    # the counts above: a method can win most cells of a model and not its best one.
    for stem, _label in KNOWLEDGE_BASES:
        best = min(((m, s) for (s, k) in rt['congen'] if k == stem for m in METHODS),
                   key=lambda ms: rt[ms[0]][(ms[1], stem)])
        check(f'{stem}: the fastest of its cells', best, PAPER_FASTEST_PER_KB[stem])

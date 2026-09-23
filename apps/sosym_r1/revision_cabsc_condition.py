#!/usr/bin/env python3
"""The four figures the CABSC-condition edits put in the paper (S3, S6.2.3, S6.4).

S6.2.3 says the delivered KB and the subset B' it is reduced from "are logically
equivalent given BG and NE" on every fold, and that CABSC "delivers the same theory in
1.4 to 1,659 times as many constraints". S6.4 says their semantic F1 "differs by 0.221
at the median and by up to 0.758". None of those four numbers came from a table, so no
gate could see them: `check_paper_tables.py` re-derives cells, and B' appears in none.

They are asserted here from `data/results_sosym_r1/cabsc_condition/cabsc_condition.json`,
the committed 84-fold measurement, which is produced by
`apps/sosym_r1/measure_mss_as_cabsc_condition.py` from the same result files every table
is computed from. No acquisition is re-run and no number is transcribed.

THE ROUNDING IS ASSERTED, NOT TOLERATED
---------------------------------------
The paper prints 1.4 and 1,659 against measured 1.358407 and 1658.5. A tolerance wide
enough to admit both would be wide enough to admit numbers the paper does not print, so
what is asserted is the RENDERING: the measured value, put through the paper's own
precision, must produce the printed string exactly.

That makes one detail load-bearing. 1658.5 is an exact tie, and Python's ``round`` is
banker's rounding: ``round(1658.5)`` is 1658, so a gate written the obvious way would go
red on a correct paper and send someone to change 1,659. Decimal's ROUND_HALF_UP is
used, which is the rule a reader assumes and the one the paper followed.

THE PREDICATE IS THE PAPER'S, NOT A COUSIN OF IT
------------------------------------------------
"Equivalent given BG and NE" is mutual entailment between (B' u NE u BG) and
(KB u NE u BG) -- whole theories, both directions, BG and NE on both sides. The
measurement records that, and separately records the stronger asymmetric form in which
direction 2 gets no BG. Both hold on 84 of 84 folds; this gate asserts the one the
sentence makes, and reports the other so the difference stays visible.
"""
from __future__ import annotations

import json
import statistics
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

MEASUREMENT = Path('data') / 'results_sosym_r1' / 'cabsc_condition' / 'cabsc_condition.json'

# S6.2.3 and S6.4, exactly as the manuscript prints them.
PAPER_FOLDS = 84
PAPER_SIZE_FACTOR = ('1.4', '1,659')        # "1.4 to 1{,}659 times as many constraints"
PAPER_F1_MEDIAN = '0.221'                   # "differs by 0.221 at the median"
PAPER_F1_MAX = '0.758'                      # "and by up to 0.758"


def half_up(value: float, places: int) -> str:
    """Render as a reader rounds, not as IEEE ties-to-even does. See the module note."""
    quantum = Decimal('1') if places == 0 else Decimal('0.' + '0' * places)
    text = str(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))
    return f'{int(text):,}' if places == 0 else text


def f1(precision: float, recall: float) -> float:
    return 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)


def run(check, repo: Path) -> None:
    path = repo / MEASUREMENT
    if not path.exists():
        raise FileNotFoundError(f'{MEASUREMENT} is missing; run '
                                'apps/sosym_r1/measure_mss_as_cabsc_condition.py')
    data = json.loads(path.read_text())
    rows = data['folds']

    print('\n[cabsc] S6.2.3 and S6.4: B\' as the CABSC condition, beside the delivered KB')
    check('folds measured', len(rows), PAPER_FOLDS)

    # S6.2.3: "on every fold the delivered KB and the subset B' it is reduced from
    # (the |MSS| column) are logically equivalent given BG and NE."
    equivalent = sum(1 for r in rows if r['equivalent_to_kb']['given_bg_and_ne'])
    check('folds where KB and B\' are equivalent given BG and NE', equivalent, PAPER_FOLDS)
    check('   ... and under the stronger form, BG on the left only',
          sum(1 for r in rows if r['equivalent_to_kb']['bg_on_the_left_only']), PAPER_FOLDS)

    # S6.2.3: "in 1.4 to 1,659 times as many constraints". Per fold, since a mean over
    # folds would hide the 6,634-against-4 cell that sets the upper end.
    ratios = [r['n_bprime'] / r['n_kb'] for r in rows]
    check('size factor, smallest, as printed', half_up(min(ratios), 1), PAPER_SIZE_FACTOR[0])
    check('size factor, largest, as printed', half_up(max(ratios), 0), PAPER_SIZE_FACTOR[1])
    # The direction the sentence asserts: B' is never smaller than what it reduces to.
    check('B\' is at least as large as the delivered KB on every fold', min(ratios) >= 1.0, True)

    # S6.4: "their semantic F1 differs by 0.221 at the median and by up to 0.758".
    # DIFFERS BY, so the magnitude: one fold moves the other way (+0.023) and a signed
    # median would report a different quantity than the sentence claims. Both readings
    # give 0.221 here, and the gate pins the one the words mean.
    deltas = [abs(f1(*r['bprime']['semantic']) - f1(*r['kb']['semantic'])) for r in rows]
    check('semantic F1 difference at the median, as printed',
          half_up(statistics.median(deltas), 3), PAPER_F1_MEDIAN)
    check('semantic F1 difference at its largest, as printed',
          half_up(max(deltas), 3), PAPER_F1_MAX)

    # S3's scope, measured: the identification is exact wherever it says anything, and
    # the folds where it does not are the ones with no positive example to be exact about.
    with_positives = [r for r in rows if r['n_train_pos'] > 0]
    check('folds with at least one training positive example', len(with_positives), 73)
    check('   ... on which A is exactly B\', as Proposition 1 now claims',
          sum(1 for r in with_positives if not r['a_minus_bprime']), 73)
    check('folds with none, where S3 says the condition is vacuous',
          sum(1 for r in rows if r['n_train_pos'] == 0), 11)
    check('   ... on which A is the whole bias',
          sum(1 for r in rows if r['n_train_pos'] == 0 and r['n_a'] == r['n_bias']), 11)

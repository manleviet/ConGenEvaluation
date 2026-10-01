#!/usr/bin/env python3
"""The CABSC-condition figures: two still in the paper, two now only in the letter.

The Conclusion (3) says the delivered knowledge base "is logically equivalent to the
subset B' it is reduced from on every fold, while CABSC reaches the same theory in 1.4
to about 950 times as many constraints"; S6.2.3 says the same, citing Table 11, and the
response letter repeats it. Section 6 opens by saying that of the passive
approaches, "only CABSC solves the same problem, and it coincides with the subset B'
that AcqMss computes" -- which is the sentence those two figures exist to support, and
it is quoted here verbatim so a reading of this module shows what is being held.

The other two, "differs by 0.221 at the median and by up to 0.758", are QUOTED IN THE
RESPONSE LETTER ONLY since the 2026-09-24 review; the threats paragraph that
carried them is gone. They stay asserted, without a section reference.

None of the four came from a table, so no gate could see them:
`check_paper_tables.py` re-derives cells, and B' appears in none.

They are asserted here from `data/results_sosym_r1/cabsc_condition/cabsc_condition.json`,
the committed 84-fold measurement, which is produced by
`apps/sosym_r1/measure_mss_as_cabsc_condition.py` from the same result files every table
is computed from. No acquisition is re-run and no number is transcribed.

THE SIZE FACTOR IS A RATIO OF PRINTED MEANS, NOT OF FOLDS
---------------------------------------------------------
S6.2.3 cites Table 11 for it, so it is |B'|/|KB| computed from the fold means Table 11
PRINTS -- each rendered by the generator's own formatter, then divided. The minimum is
KB3 RS(3n), 314/224 = 1.40; the maximum KB5 2-COV, 6,634/7 = 948, which the paper
calls "about 950". The ratio of the UNROUNDED means at that cell is 995.1 (6,634/6.667):
the "about" covers the printed cell, not the unrounded one, and that is stated here so
nobody re-derives it from the JSON and finds a different number. Both printed cells are
also read back out of the committed fragment, so the gate holds the table the sentence
cites and not a recomputation that merely agrees with it.

The per-fold extremes, 1.358 and 1,658.5, were the figure the paper printed before the
2026-10-01 submission. They are no longer printed; they stay below as a STABILITY
statistic of the measurement, labelled as such.

THE ROUNDING IS ASSERTED, NOT TOLERATED
---------------------------------------
The paper prints 1.4 and 948 against computed 1.4018 and 947.71. A tolerance wide
enough to admit both would be wide enough to admit numbers the paper does not print, so
what is asserted is the RENDERING: the measured value, put through the paper's own
precision, must produce the printed string exactly.

One detail was load-bearing for the per-fold form: 1658.5 is an exact tie, and Python's ``round`` is
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

# As the Discussion prints them; the last two are the letter's only.
PAPER_FOLDS = 84
# S6.2.3 / Conclusion (3): "1.4 to about 950 times as many constraints (Table 11)", on
# the printed fold means: KB3 RS(3n) 314/224 and KB5 2-COV 6,634/7.
PAPER_SIZE_FACTOR = ('1.4', '948')
PAPER_SIZE_FACTOR_ABOUT = 950
PAPER_SIZE_FACTOR_CELLS = (('arcade-game', 'rs_3n'), ('busybox-1.18.0', '2cov'))
PAPER_SIZE_FACTOR_PRINTED = ((314, 224), (6634, 7))
PAPER_CELLS = 28
# Not printed since 2026-10-01: the per-fold extremes, kept as a stability statistic.
FOLD_SIZE_FACTOR = ('1.4', '1,659')
TABLE_11 = Path('data') / 'results_sosym_r1' / 'tables' / 'paper' / 'tab_kb_size.tex'
PAPER_F1_MEDIAN = '0.221'                   # "differs by 0.221 at the median"
PAPER_F1_MAX = '0.758'                      # "and by up to 0.758"


def half_up(value: float, places: int) -> str:
    """Render as a reader rounds, not as IEEE ties-to-even does. See the module note."""
    quantum = Decimal('1') if places == 0 else Decimal('0.' + '0' * places)
    text = str(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))
    return f'{int(text):,}' if places == 0 else text


def f1(precision: float, recall: float) -> float:
    return 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)


def table11_printed(repo: Path) -> dict:
    """(stem, sampling) -> (|B'|, |KB|) as Table 11 prints them: the fold means, each
    put through the generator's own count formatter and read back as an integer."""
    import statistics
    from paper_tables import latex as tex
    from revision_cells import KNOWLEDGE_BASES, SAMPLINGS, folds
    out = {}
    for sampling in SAMPLINGS:
        for stem, _label in KNOWLEDGE_BASES:
            fs = folds(repo, stem, sampling, 'congen')
            if fs:
                b = statistics.mean(f['statistics']['n_mss'] for f in fs)
                k = statistics.mean(len(f['kb_constraints']) for f in fs)
                out[(stem, sampling)] = tuple(int(tex.count(v).replace('{,}', ''))
                                              for v in (b, k))
    return out


def table11_fragment_cells(repo: Path) -> dict:
    """The same cells read out of the committed tab_kb_size.tex, by row and column."""
    import re
    from revision_cells import KNOWLEDGE_BASES
    rows = {'RS($n$)': 'rs_1n', 'RS($2n$)': 'rs_2n', 'RS($3n$)': 'rs_3n',
            'RS($m$)': 'rs_m', '2-COV': '2cov', 'FF': 'ff'}
    out = {}
    for line in (repo / TABLE_11).read_text().splitlines():
        cells = [c.strip() for c in line.rstrip('\\ ').split('&')]
        if cells[0] not in rows:
            continue
        values = [c for c in cells[1:]]
        for i, (stem, _label) in enumerate(KNOWLEDGE_BASES):
            pair = values[2 * i:2 * i + 2]
            if len(pair) == 2 and all(re.fullmatch(r'[\d{},]+', v) for v in pair):
                out[(stem, rows[cells[0]])] = tuple(int(v.replace('{,}', '')) for v in pair)
    return out


def run(check, repo: Path) -> None:
    path = repo / MEASUREMENT
    if not path.exists():
        raise FileNotFoundError(f'{MEASUREMENT} is missing; run '
                                'apps/sosym_r1/measure_mss_as_cabsc_condition.py')
    data = json.loads(path.read_text())
    rows = data['folds']

    print('\n[cabsc] B\' as the CABSC condition, beside the delivered KB'
          ' (S6.2.3, Conclusion (3), the response letter; the spread figures are letter-only)')
    check('folds measured', len(rows), PAPER_FOLDS)

    # Discussion (3): "the delivered knowledge base is logically equivalent to the
    # subset B' it is reduced from on every fold". B' is the quantity Table 11 prints
    # as |B'|, and the equivalence is asserted in both directions given BG and NE.
    equivalent = sum(1 for r in rows if r['equivalent_to_kb']['given_bg_and_ne'])
    check('folds where KB and B\' are equivalent given BG and NE', equivalent, PAPER_FOLDS)
    check('   ... and under the stronger form, BG on the left only',
          sum(1 for r in rows if r['equivalent_to_kb']['bg_on_the_left_only']), PAPER_FOLDS)

    # S6.2.3 / Conclusion (3) / the response letter: "1.4 to about 950 times as many
    # constraints (Table 11)" -- the ratio of the fold means Table 11 prints.
    printed = table11_printed(repo)
    check('S6.2.3: Table 11 cells the size factor ranges over', len(printed), PAPER_CELLS)
    ratio = {cell: b / k for cell, (b, k) in printed.items()}
    low, high = min(ratio, key=ratio.get), max(ratio, key=ratio.get)
    check('S6.2.3: size factor on printed means, smallest, as printed',
          half_up(ratio[low], 1), PAPER_SIZE_FACTOR[0])
    check('   ... at the cell the sentence rests on, and from these printed cells',
          (low, printed[low]), (PAPER_SIZE_FACTOR_CELLS[0], PAPER_SIZE_FACTOR_PRINTED[0]))
    check('S6.2.3: size factor on printed means, largest, rounded',
          half_up(ratio[high], 0), PAPER_SIZE_FACTOR[1])
    check('   ... at the cell the sentence rests on, and from these printed cells',
          (high, printed[high]), (PAPER_SIZE_FACTOR_CELLS[1], PAPER_SIZE_FACTOR_PRINTED[1]))
    check('   ... which is "about 950" to the nearest fifty',
          int(50 * round(ratio[high] / 50)), PAPER_SIZE_FACTOR_ABOUT)
    fragment = table11_fragment_cells(repo)
    check('   ... the fragment parser finds every printed cell, so a lookup can fail',
          len(fragment), PAPER_CELLS)
    check('   ... and both cells read the same in the committed Table 11 fragment',
          [fragment[c] for c in PAPER_SIZE_FACTOR_CELLS], list(PAPER_SIZE_FACTOR_PRINTED))

    # Not printed since 2026-10-01. The per-fold extremes, as a stability statistic of
    # the measurement: a mean over folds hides the 6,634-against-4 fold behind them.
    ratios = [r['n_bprime'] / r['n_kb'] for r in rows]
    check('stability (not printed): per-fold size factor, smallest',
          half_up(min(ratios), 1), FOLD_SIZE_FACTOR[0])
    check('stability (not printed): per-fold size factor, largest',
          half_up(max(ratios), 0), FOLD_SIZE_FACTOR[1])
    # The direction the sentence asserts: B' is never smaller than what it reduces to.
    check('B\' is at least as large as the delivered KB on every fold', min(ratios) >= 1.0, True)

    # The letter: "their semantic F1 differs by 0.221 at the median and by up to
    # 0.758". Not printed in the paper since the 2026-09-24 review.
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

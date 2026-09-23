#!/usr/bin/env python3
"""Figures the 2026-09-23 minimal-change review put into the paper's prose.

The review moved numbers out of tables and into sentences, and added claims that were
never quantified anywhere: that 2-COV needs the fewest AcqMss checks on EVERY knowledge
base, that accuracy improves with every step of random sampling, that the semantic tier
dominates the other two on EVERY combination, that no held-out negative configuration is
ever accepted. A claim of the form "on every X" is exactly the kind a table cell cannot
carry, because the reader would have to check twenty-eight cells to believe it.

Everything here is computed from `data/results_sosym_r1/congen/*.json` and
`data/examples/*.json`, the same files the tables are computed from. Cell values that
also appear in a table are asserted here too: the table gate checks the FRAGMENT, and
the manuscript transcribes it, so a sentence quoting a cell is a third copy that
nothing else holds.

ONE CHECK IS NOT A NUMBER. `BG is empty` (S6.1.2) is a statement about what the
implementation passes to the algorithms, so it is asserted by preparing each knowledge
base's task and looking at `set_b`, not by reading a result file. That costs a few
seconds of task preparation and is the only live computation in this file.
"""
from __future__ import annotations

import json
import statistics
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CONGEN = Path('data') / 'results_sosym_r1' / 'congen'
EXAMPLES = Path('data') / 'examples'

# (stem, paper label) in the paper's order, and the sampling order every table uses.
KBS = (('REAL-FM-7', 'KB1'), ('fqa', 'KB2'), ('arcade-game', 'KB3'),
       ('REAL-FM-4', 'KB4'), ('busybox-1.18.0', 'KB5'))
SAMPLINGS = ('rs_1n', 'rs_2n', 'rs_3n', 'rs_m', '2cov', 'ff')
NOT_RUN = {('busybox-1.18.0', 'rs_2n'), ('busybox-1.18.0', 'rs_3n')}

# --- S6.2.1, the performance paragraph --------------------------------------
PAPER_KB3_ACQMSS = (3090, 3290)             # "3,090 to 3,290 on KB3"
PAPER_RUNTIME_FACTOR = {'arcade-game': '3.4', 'REAL-FM-4': '8.3'}
PAPER_2COV_ACQMSS = (10, 10, 1429, 1612, 14)     # fewest on every KB; "only 10" on KB1, KB2
PAPER_2COV_REDUCE_RANGE = (300, 6648)       # "300 to 6,648" on the three KBs with no E+
PAPER_2COV_NO_POSITIVES = ('REAL-FM-7', 'fqa', 'busybox-1.18.0')

# --- S6.2.2, the accuracy paragraph -----------------------------------------
PAPER_ACCURACY_SPAN = {'REAL-FM-7': ('0.194', '1.000'), 'busybox-1.18.0': ('0.089', '1.000')}
PAPER_KB2_RS = ('0.367', '0.966')           # RS(m) to RS(3n)
PAPER_WIDEST, PAPER_SECOND_WIDEST = 'busybox-1.18.0', 'REAL-FM-7'

# --- S6.2.4, the comparison-strategy paragraph ------------------------------
# S6.4: "equivalence holds on 1 of the 84 folds". The UNIT is no longer in the paper --
# the 2026-09-23 review removed the S6.2.4 sentence that named it -- and is quoted by
# the response letter instead.
PAPER_EQUIVALENT_FOLDS = 1
LETTER_EQUIVALENT_UNIT = ('REAL-FM-7', 'rs_3n', 2)
# S6.2.4 and S6.3: "semantic precision stays below 1 on all of them" / "on every
# combination". 28 combinations; the closest to 1 is busybox under 2-COV.
PAPER_COMBINATIONS = 28
PAPER_MAX_PRECISION = '0.994'


def render(value: float, places: int) -> str:
    """The paper's rounding: half up, never ties-to-even. See revision_cabsc_condition."""
    quantum = Decimal('1') if places == 0 else Decimal('0.' + '0' * places)
    return str(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def folds_of(repo: Path, stem: str, sampling: str) -> list:
    path = repo / CONGEN / f'{stem}_{sampling}_cv_incremental.json'
    return json.loads(path.read_text())['folds']


def mean_over_folds(folds: list, pick) -> float:
    return statistics.mean(pick(f) for f in folds)


def acqmss_checks(folds: list) -> float:
    return mean_over_folds(folds, lambda f: f['performance']['profiler']['paper_consistency_checks'])


def reduce_checks(folds: list) -> float:
    return mean_over_folds(folds, lambda f: f['performance']['redundancy_consistency_checks'])


def runtime_ms(folds: list) -> float:
    return mean_over_folds(folds, lambda f: f['performance']['runtime_ms'])


def accuracy(folds: list) -> float:
    return mean_over_folds(folds, lambda f: f['accuracy'])


def semantic_f1(fold: dict) -> float:
    return fold['evaluation']['semantic']['metrics']['f1_score']


def run(check, repo: Path) -> None:
    cells = {(stem, samp): folds_of(repo, stem, samp)
             for stem, _ in KBS for samp in SAMPLINGS if (stem, samp) not in NOT_RUN}

    print('\n[review] S6.2.1: checks per phase, and what the sampling strategy decides')
    check('KB3 AcqMss checks, RS(n)', round(acqmss_checks(cells[('arcade-game', 'rs_1n')])),
          PAPER_KB3_ACQMSS[0])
    check('KB3 AcqMss checks, RS(3n)', round(acqmss_checks(cells[('arcade-game', 'rs_3n')])),
          PAPER_KB3_ACQMSS[1])
    # "the runtime grows by a factor of 3.4 on KB3 and 8.3 on KB4 from RS(n) to RS(3n)"
    for stem, printed in PAPER_RUNTIME_FACTOR.items():
        factor = runtime_ms(cells[(stem, 'rs_3n')]) / runtime_ms(cells[(stem, 'rs_1n')])
        check(f'{stem}: runtime factor RS(n) -> RS(3n), as printed', render(factor, 1), printed)

    # "The 2-COV strategy needs the fewest AcqMss checks on every knowledge base"
    for i, (stem, label) in enumerate(KBS):
        others = [acqmss_checks(cells[(stem, s)]) for s in SAMPLINGS
                  if s != '2cov' and (stem, s) not in NOT_RUN]
        two_cov = acqmss_checks(cells[(stem, '2cov')])
        check(f'{label}: 2-COV needs the fewest AcqMss checks', two_cov < min(others), True)
        check(f'{label}: 2-COV AcqMss checks', round(two_cov), PAPER_2COV_ACQMSS[i])

    # "on the three knowledge bases whose 2-COV example set contains no positive example
    #  (KB1, KB2, and KB5) it needs 300 to 6,648 checks"
    no_positives = tuple(stem for stem, _ in KBS
                         if not json.loads((repo / EXAMPLES / f'{stem}_2cov.json').read_text())['positive'])
    check('KBs whose 2-COV example set has no positive example', no_positives,
          PAPER_2COV_NO_POSITIVES)
    reduce_there = [reduce_checks(cells[(stem, '2cov')]) for stem in no_positives]
    check('   ... their Reduce checks, smallest', round(min(reduce_there)),
          PAPER_2COV_REDUCE_RANGE[0])
    check('   ... their Reduce checks, largest', round(max(reduce_there)),
          PAPER_2COV_REDUCE_RANGE[1])

    print('\n[review] S6.2.2: accuracy, its spread, and the one kind of error')
    # "accuracy improves with more examples on each of the four knowledge bases on which
    #  all three sizes were run"
    for stem, label in KBS:
        if (stem, 'rs_2n') in NOT_RUN:
            continue
        a = [accuracy(cells[(stem, s)]) for s in ('rs_1n', 'rs_2n', 'rs_3n')]
        check(f'{label}: accuracy rises with RS(n) < RS(2n) < RS(3n)',
              a[0] < a[1] < a[2], True)
    check('KB2: RS(m) accuracy, as printed', render(accuracy(cells[('fqa', 'rs_m')]), 3),
          PAPER_KB2_RS[0])
    check('KB2: RS(3n) accuracy, as printed', render(accuracy(cells[('fqa', 'rs_3n')]), 3),
          PAPER_KB2_RS[1])

    # "2-wise coverage yields the highest accuracy on every knowledge base"
    spans = {}
    for stem, label in KBS:
        per_samp = {s: accuracy(cells[(stem, s)]) for s in SAMPLINGS
                    if (stem, s) not in NOT_RUN}
        check(f'{label}: 2-COV is the most accurate strategy',
              per_samp['2cov'] == max(per_samp.values()), True)
        spans[stem] = max(per_samp.values()) - min(per_samp.values())
        if stem in PAPER_ACCURACY_SPAN:
            low, high = PAPER_ACCURACY_SPAN[stem]
            check(f'{label}: lowest accuracy, as printed',
                  render(min(per_samp.values()), 3), low)
            check(f'{label}: highest accuracy, as printed',
                  render(max(per_samp.values()), 3), high)
    order = sorted(spans, key=spans.get, reverse=True)
    check('accuracy varies most on the largest knowledge base', order[0], PAPER_WIDEST)
    check('   ... and next on the smallest', order[1], PAPER_SECOND_WIDEST)

    # "On the held-out folds no negative configuration is accepted, so every error is a
    #  valid configuration that the learned knowledge base rejects."
    confusion = {k: 0 for k in ('true_positives', 'true_negatives',
                                'false_positives', 'false_negatives')}
    worst = 0
    for folds in cells.values():
        for fold in folds:
            for key in confusion:
                confusion[key] += fold['metrics'][key]
            worst = max(worst, fold['metrics']['false_positives'])
    check('folds scored for accuracy', sum(len(f) for f in cells.values()), 84)
    # Per fold, not only in sum: a sum of zero is also what two folds of +1 and -1 would
    # give, and a count cannot go negative only because nothing here makes it.
    check('largest false-positive count on ANY fold', worst, 0)
    check('false positives over all 84 folds', confusion['false_positives'], 0)
    check('   ... beside the other three counts, so the zero is not an empty sum',
          (confusion['true_positives'], confusion['false_negatives'],
           confusion['true_negatives']), (3573, 832, 522))

    print('\n[review] S6.2.4: the tier ordering, and the one equivalent fold')
    # S6.2.4: "The semantic F1-score is at least as high as the clause-based one on
    # every combination, and both exceed the description-based one." Two relations,
    # asserted as two: the sentence makes one non-strict and the other strict, and a
    # single <= chain would hold even if the strict half failed.
    tiers = {k: {tier: statistics.mean(f['evaluation'][tier]['metrics']['f1_score']
                                       for f in v)
                 for tier in ('description', 'clause', 'semantic')}
             for k, v in cells.items()}
    check('combinations scored', len(tiers), PAPER_COMBINATIONS)
    check('combinations where semantic F1 is BELOW clause F1',
          [k for k, v in tiers.items() if v['semantic'] < v['clause']], [])
    check('combinations where clause F1 does not EXCEED description F1',
          [k for k, v in tiers.items() if v['clause'] <= v['description']], [])
    check('combinations where semantic F1 does not EXCEED description F1',
          [k for k, v in tiers.items() if v['semantic'] <= v['description']], [])

    # S6.2.4 and S6.3: "semantic precision stays below 1 on all of them".
    precision = {k: statistics.mean(f['evaluation']['semantic']['metrics']['precision']
                                    for f in v) for k, v in cells.items()}
    check('combinations where semantic precision reaches 1',
          [k for k, v in precision.items() if v >= 1.0], [])
    check('   ... the closest any combination gets, as printed',
          render(max(precision.values()), 3), PAPER_MAX_PRECISION)
    check('   ... and it is busybox under 2-COV',
          max(precision, key=precision.get), ('busybox-1.18.0', '2cov'))

    # PER FOLD the claim does not hold, and that is REPORTED, not gated: the sentence
    # is about combinations, which are means over three folds, and one fold does reach
    # 1.000. Gating the per-fold count would assert something the paper does not claim.
    per_fold_perfect = [(stem, samp, f['fold_index'])
                        for (stem, samp), folds in cells.items() for f in folds
                        if f['evaluation']['semantic']['metrics']['precision'] >= 1.0]
    print(f'      note: {len(per_fold_perfect)} of 84 folds reach semantic precision '
          f'1.000 ({", ".join(f"{a} {b} f{c}" for a, b, c in per_fold_perfect)}); every '
          f'combination mean stays below 1, which is what the paper claims.')

    equivalent = [(stem, samp, f['fold_index'])
                  for (stem, samp), folds in cells.items() for f in folds
                  if f.get('evaluation', {}).get('exact_equiv') in (1, True)]
    check('folds reaching exact equivalence, as S6.4 says', len(equivalent),
          PAPER_EQUIVALENT_FOLDS)
    # The unit left the paper with the S6.2.4 sentence; the response letter quotes it.
    check('   ... the fold it happens on, quoted by the letter', equivalent[0],
          LETTER_EQUIVALENT_UNIT)
    perfect = [(stem, samp, f['fold_index'])
               for (stem, samp), folds in cells.items() for f in folds
               if semantic_f1(f) == 1.0]
    check('folds with semantic F1 exactly 1.000', perfect, equivalent)

    check_background_knowledge_is_empty(check, repo)


def prepared_task(repo: Path, stem: str):
    """One knowledge base's prepared ConGen task, built the way a run builds it."""
    from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
    from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
    from conacq.examples import ExampleIO
    from conacq.oracle import FMOracle

    ex = ExampleIO.load_json(str(repo / EXAMPLES / f'{stem}_rs_m.json'))
    oracle = FMOracle(str(repo / 'data' / 'fms' / f'{stem}.uvl'), use_incremental=False)
    try:
        model = (ConGenModelBuilder
                 .from_bias(str(repo / 'data' / 'bias' / f'{stem}-bias.json'))
                 .with_oracle_data(oracle.oracle_data).build())
        return model.prepare_task(ConGenTaskInput.from_examples(
            oracle.oracle_data,
            [e.assignments for e in ex.positive],
            [e.assignments for e in ex.negative])).task
    finally:
        oracle.cleanup()


def check_background_knowledge_is_empty(check, repo: Path) -> None:
    """S6.1.2: "The background knowledge BG is empty."

    Asserted against the task the algorithms receive, because that is what the
    sentence is about. The root feature constraint is recorded on ``root_axiom`` and
    applied after acquisition -- the paper says so in the next sentence, and the two
    halves are checked together so that neither can drift alone. A gate that only
    checked emptiness would stay green if the root were dropped entirely.

    The smallest example set is used for every knowledge base: the task's BG does not
    depend on the examples, and loading RS(3n) on busybox to look at an empty list
    would cost a minute to learn nothing.
    """
    print('\n[review] S6.1.2: what the algorithms actually receive as BG')
    for stem, label in KBS:
        task = prepared_task(repo, stem)
        check(f'{label}: BG passed to AcqMSS and Reduce is empty', list(task.set_b), [])
        check(f'   ... and the root axiom is recorded, not lost',
              len(task.root_axiom) > 0, True)


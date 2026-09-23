#!/usr/bin/env python3
"""Cost figures the revision quotes in SENTENCES rather than in a table cell.

`check_paper_tables.py` re-derives every cell of every generated fragment. It
cannot see a number a sentence repeats, and the revision added three kinds:

  * The read-aloud row. S6.2.1 no longer reads Table 9 aloud, and gamma and the bound
    evaluated at that row went with the sentence; the response letter quotes them. The
    five CELL values are still printed, in Table 9, and are asserted here as well
    because the manuscript transcribes that table by hand. It used to read: KB1 under
    RS(n) --
    "515 AcqMss checks, 92 Reduce checks, and 6 QuickXplain checks, 613 in total,
    in 194 milliseconds" -- and then does something no cell does: it evaluates the
    complexity bound of S5.1 -- still S5.1 after the renumbering -- at that row, with
    gamma = 203 constraints removed and
    a bound of about 625. gamma and the bound exist nowhere in any table, and the
    row values are a hand transcription of one that does.

  * The justification for the two n/a cells, which S6.1.3 now gives without numbers
    ("their runtime would exceed the compute budget of the study"). The letter quotes
    the figures. KB5's RS(n) fold takes 4.1-4.3 h
    and KB4 grows by 3.6x and 8.3x from RS(n), "which places the two missing
    conditions at roughly two and four days of computation for three folds each".
    That sentence is the entire argument for not running them.

  * S6.1.3's identity between two sampling strategies: "$m$ is the
    size of the 2-COV sample of the same model". If it ever stopped holding, the
    two columns would stop being comparable and the paper would not say so.

EVERY VALUE HERE IS A MEAN OVER THE THREE FOLDS, computed the way the generator
computes it, because that is what the row prints. Quoting fold 0 instead has
already produced three published errors in this project.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

# Table 9 of S6.2.1, and the sentence that used to read it aloud.
READ_ALOUD = {
    'model': 'REAL-FM-7', 'sampling': 'rs_1n',
    'positives': 13, 'negatives': 1, 'bias': 295,
    'acqmss': 515, 'reduce': 92, 'generate_ne': 6, 'total_checks': 613, 'runtime_ms': 194,
    'gamma': 203, 'bound': 625,
}

# S5.4, "the smallest number of valid configurations including each pair of features".
PAPER_M = {'REAL-FM-7': 9, 'fqa': 16, 'arcade-game': 14, 'REAL-FM-4': 18, 'busybox-1.18.0': 21}

# S5.3, the argument for the two n/a cells.
KB5_FOLD_HOURS = (4.1, 4.3)          # "A single RS(n) fold on KB5 already takes 4.1-4.3 hours"
KB4_GROWTH = {'rs_2n': 3.6, 'rs_3n': 8.3}
PROJECTED_DAYS = {'rs_2n': 2, 'rs_3n': 4}   # "roughly two and four days ... for three folds each"


def _folds(results: Path, model: str, sampling: str) -> list[dict]:
    return json.loads((results / f'{model}_{sampling}_cv_incremental.json').read_text())['folds']


def phase_checks(fold: dict) -> dict[str, int]:
    """The three phase counters of one fold, with the one justified zero.

    GenerateNE explains negative examples. A training split with none never calls
    it, so its counter is never created -- and that absence is a measured zero, not
    a gap. The distinction is asserted rather than assumed: a missing counter
    while negatives ARE present raises.
    """
    perf = fold['performance']
    profiler = perf.get('profiler') or {}
    genne = profiler.get('shared_preprocessing_quickxplain_checks')
    if genne is None:
        if fold['train_size']['negative'] > 0:
            raise ValueError('GenerateNE counter missing on a fold WITH negatives')
        genne = 0
    return {
        'acqmss': profiler['paper_consistency_checks'],
        'reduce': perf['redundancy_consistency_checks'],
        'generate_ne': genne,
    }


def acqmss_bound(n: int, gamma: float) -> float:
    """The worst case of S5.1: 2*gamma*log2(n/gamma) + 2*gamma consistency checks."""
    return 2 * gamma * math.log2(n / gamma) + 2 * gamma


def run(check, repo: Path) -> None:
    results = repo / 'data' / 'results_sosym_r1' / 'congen'
    examples = repo / 'data' / 'examples'

    print('\n[cost] Table 9\'s KB1 RS(n) row, and the bound the letter evaluates there')
    r = READ_ALOUD
    folds = _folds(results, r['model'], r['sampling'])
    ex = json.loads((examples / f"{r['model']}_{r['sampling']}.json").read_text())
    check('KB1 RS(n): positive examples', len(ex['positive']), r['positives'])
    check('KB1 RS(n): negative examples', len(ex['negative']), r['negatives'])
    check('KB1 RS(n): candidates in the bias', folds[0]['statistics']['n_bias'], r['bias'])

    per_phase = [phase_checks(f) for f in folds]
    means = {p: statistics.mean(c[p] for c in per_phase) for p in ('acqmss', 'reduce', 'generate_ne')}
    for phase in ('acqmss', 'reduce', 'generate_ne'):
        check(f'KB1 RS(n): {phase} checks, mean over the three folds',
              round(means[phase]), r[phase])
    check('KB1 RS(n): checks in total', round(sum(means.values())), r['total_checks'])
    check('KB1 RS(n): runtime, msec',
          round(statistics.mean(f['performance']['runtime_ms'] for f in folds)), r['runtime_ms'])

    # gamma is what AcqMss removes: the bias minus the maximal satisfiable subset.
    n_mss = statistics.mean(f['statistics']['n_mss'] for f in folds)
    gamma = r['bias'] - n_mss
    check('KB1 RS(n): gamma = |B| - |MSS|, mean over folds', round(gamma), r['gamma'])
    check('KB1 RS(n): the S5.1 bound at that gamma',
          round(acqmss_bound(r['bias'], gamma)), r['bound'])
    check('   ... and the measured count sits below it, as the sentence claims',
          sum(means.values()) < acqmss_bound(r['bias'], gamma), True)

    print('\n[cost] S6.1.3: m is the size of the 2-COV sample of the same model')
    for model, m in PAPER_M.items():
        def size(strategy: str) -> int:
            d = json.loads((examples / f'{model}_{strategy}.json').read_text())
            return len(d['positive']) + len(d['negative'])
        check(f'{model}: |RS(m)| == m', size('rs_m'), m)
        check(f'{model}: |2-COV| == m, which is what makes the two comparable',
              size('2cov'), m)

    print('\n[cost] why RS(2n) and RS(3n) were not run on KB5 (figures now letter-only)')
    kb5 = _folds(results, 'busybox-1.18.0', 'rs_1n')
    hours = sorted(f['performance']['runtime_ms'] / 3.6e6 for f in kb5)
    check('KB5 RS(n): slowest fold, hours', round(hours[-1], 1), KB5_FOLD_HOURS[1], tol=1e-9)
    check('KB5 RS(n): fastest fold, hours', round(hours[0], 1), KB5_FOLD_HOURS[0], tol=1e-9)

    def mean_ms(model: str, sampling: str) -> float:
        return statistics.mean(f['performance']['runtime_ms'] for f in _folds(results, model, sampling))

    base = mean_ms('REAL-FM-4', 'rs_1n')
    for sampling, factor in KB4_GROWTH.items():
        grown = mean_ms('REAL-FM-4', sampling) / base
        check(f'KB4 runtime growth RS(n) -> {sampling}', round(grown, 1), factor, tol=1e-9)
        # The projection the sentence draws from it: KB5's RS(n) fold, grown, x 3 folds.
        days = statistics.mean(f['performance']['runtime_ms'] for f in kb5) * grown * 3 / 8.64e7
        check(f'   ... projects KB5 {sampling} to roughly {PROJECTED_DAYS[sampling]} days',
              round(days), PROJECTED_DAYS[sampling])

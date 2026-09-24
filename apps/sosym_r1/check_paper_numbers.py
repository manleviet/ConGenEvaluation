#!/usr/bin/env python3
"""Reproduce, and ASSERT, every number the paper quotes in its prose.

Why this file exists
--------------------
A number that nobody can recompute cannot be re-checked, only re-asserted. Several of
the figures the paper quotes are load-bearing:

  * |Ctau| = 130 for arcade-game is the hand count that settled the ground-truth
    question, and the disclosure that four of five models had been scored against
    another model's target theory rests on it.
  * 74.62 %, 18/28, 1/84 and the 29-80 % agreement range appear in the paper.

Each is recomputed here from the committed data, so the number moves visibly if the
data moves. When one fails, the finding is that a number changed: update the paper to
the measurement, never the assertion to the number you hoped for.

Table CELLS are not checked here -- they are checked by check_paper_tables.py, which
re-derives each one from the same result files. This file is for the figures that
appear in sentences.
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TREE = REPO / 'data' / 'results_sosym_r1'
R1 = TREE / 'congen'
FMS = REPO / 'data' / 'fms'

STEMS = ['REAL-FM-4', 'REAL-FM-7', 'arcade-game', 'busybox-1.18.0', 'fqa']
SAMPLINGS = ['rs_1n', 'rs_2n', 'rs_3n', 'rs_m', '2cov', 'ff']
MODES = ['example_only', 'example_first']

TOL = 5e-3  # numbers are quoted to 3-4 significant figures in the paper

failures: list[str] = []
checks = 0


def check(name: str, got, want, tol: float | None = None) -> None:
    """Assert one quoted number. Records rather than raises, so one run reports all drift."""
    global checks
    checks += 1
    ok = (abs(got - want) <= (TOL if tol is None else tol)) if isinstance(want, float) else (got == want)
    status = 'ok  ' if ok else 'FAIL'
    print(f'  [{status}] {name}: got {got!r}, paper says {want!r}')
    if not ok:
        failures.append(name)


def semantic(fold: dict) -> dict:
    """The semantic metrics block.

    NOTE the nesting: evaluation.semantic.METRICS.recall. Reading one level
    shallower returns a .get() default of 0 on every fold, which is exactly how
    this was briefly reported, during the authors' own checking, as "the P/R do not
    exist anywhere in the repository". A missing key and a zero value are different
    facts.
    """
    return ((fold.get('evaluation') or {}).get('semantic') or {}).get('metrics') or {}


def folds_of(pattern: str, root: Path):
    for f in sorted(glob.glob(str(root / pattern))):
        if '/partials/' in f:
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for fo in d.get('folds', []) or []:
            yield os.path.basename(f), d, fo


def fold_mean(path: Path, key: str = 'f1_score'):
    """A cell is the mean over folds. Never the intersected KB, never a pooled figure."""
    if not path.exists():
        return None
    folds = json.loads(path.read_text())['folds']
    vals = [semantic(f).get(key) for f in folds if semantic(f)]
    return statistics.mean(vals) if vals else None


def queries_of(path: Path):
    """Mean oracle queries per fold, and the stopping rules observed."""
    if not path.exists():
        return None, set()
    folds = json.loads(path.read_text())['folds']
    n = [f.get('n_queries') for f in folds if f.get('n_queries') is not None]
    return (statistics.mean(n) if n else None), {f.get('convergence_reason') for f in folds}


def cell(stem: str, samp: str, mode: str) -> dict | None:
    """One (KB, sampling, mode) unit: ConGen, the iterative baseline, and the gap.

    Returns None unless BOTH halves exist. A congen-only check would count units
    whose gap was never computable and report them as if they had one.
    """
    cg = fold_mean(TREE / 'congen' / f'{stem}_{samp}_cv_incremental.json')
    it_path = TREE / 'interactive' / f'{stem}_{samp}_cv_incremental_{mode}.json'
    it = fold_mean(it_path)
    if cg is None or it is None:
        return None
    nq, stops = queries_of(it_path)
    return {'congen': cg, 'iterative': it, 'gap': cg - it, 'queries': nq, 'stops': stops}


def collapsed(stem: str, samp: str) -> bool:
    """Identical iterative F1 under both modes: the lost-method-axis signature."""
    a = fold_mean(TREE / 'interactive' / f'{stem}_{samp}_cv_incremental_example_only.json')
    b = fold_mean(TREE / 'interactive' / f'{stem}_{samp}_cv_incremental_example_first.json')
    return a is not None and b is not None and abs(a - b) < 1e-12


# ---------------------------------------------------------------------------
# 1. |Cτ| counted from the feature model alone, never from a result file.
#    This is the hand count that settled which value was correct.
# ---------------------------------------------------------------------------
def count_ctau_from_uvl(path: Path) -> int:
    """Standard FM->CNF clause count.

    root unit                     1
    mandatory child   c <-> p     2 each
    optional  child   c  -> p     1 each
    group     child   c  -> p     1 each
    group             p  -> Vci   1 per or/alternative group
    ALTERNATIVE group !ci v !cj   C(n,2) per group  <-- see below
    cross-tree                    1 each

    The pairwise-exclusion term is the one the first hand count omitted. It
    settled the ground-truth question on arcade-game and was believed general.
    arcade-game and REAL-FM-4 have ZERO alternative groups, so the missing term
    never fired on either model it was tested against; fqa (23 groups) was short
    by 85 clauses and busybox (8 groups) by 23. With the term restored all five
    models reproduce exactly, with no residual.

    The lesson had already been written down and was not applied to this
    check: alternative groups are the encoding path most likely to be wrong,
    and the model used to validate the count could not exercise it.
    """
    lines = path.read_text().split('\n')
    ci = [i for i, l in enumerate(lines) if l.strip() == 'constraints']
    fsec = lines[:ci[0]] if ci else lines
    csec = lines[ci[0] + 1:] if ci else []

    def indent(l: str) -> int:
        return len(l) - len(l.lstrip('\t'))

    edges: list[tuple[str, str | None, str]] = []
    groups: dict[tuple[str | None, str], list[str]] = {}
    cur_parent: list[tuple[int, str]] = []
    pending: list[tuple[int, str, str | None]] = []
    for l in fsec:
        if not l.strip():
            continue
        s, ind = l.strip(), indent(l)
        tok = s.split()[0].rstrip('{')
        if tok in ('namespace', 'features'):
            continue
        while cur_parent and cur_parent[-1][0] >= ind:
            cur_parent.pop()
        while pending and pending[-1][0] >= ind:
            pending.pop()
        if tok in ('mandatory', 'optional', 'or', 'alternative'):
            pending.append((ind, tok, cur_parent[-1][1] if cur_parent else None))
            continue
        if pending:
            gi, kind, par = pending[-1]
            edges.append((tok, par, kind))
            groups.setdefault((par, kind), []).append(tok)
        cur_parent.append((ind, tok))

    n_mand = sum(1 for e in edges if e[2] == 'mandatory')
    n_opt = sum(1 for e in edges if e[2] == 'optional')
    n_grp_child = sum(1 for e in edges if e[2] in ('or', 'alternative'))
    n_groups = sum(1 for k in groups if k[1] in ('or', 'alternative'))
    n_ctc = len([l for l in csec if l.strip()])
    n_pairwise = sum(len(v) * (len(v) - 1) // 2
                     for k, v in groups.items() if k[1] == 'alternative')
    return 1 + 2 * n_mand + n_opt + n_grp_child + n_ctc + n_groups + n_pairwise


EXPECTED_CTAU = {
    'REAL-FM-7': 22,
    'arcade-game': 130,
    'fqa': 342,
    'REAL-FM-4': 428,
    'busybox-1.18.0': 994,
}

print('\n1. |Ctau| hand-counted from data/fms/*.uvl (settles the ground-truth question)')
for model, want in EXPECTED_CTAU.items():
    uvl = FMS / f'{model}.uvl'
    if not uvl.exists():
        print(f'  [skip] {model}: {uvl} absent')
        continue
    check(f'|Ctau| {model} from UVL', count_ctau_from_uvl(uvl), want)

# CLAUSES, not constraints. The paper no longer prints these -- the 2026-09-23 review
# dropped the sentence that listed them -- and it now prints |C_tau| in CONSTRAINTS
# (13, 102, 70, 219, 905) in tab:fm_summary and tab:kb_size's header, which
# revision_target_theory_size asserts. Same symbol, different unit, two to seven times
# apart. These stay asserted because every semantic recall in the paper is measured
# against this clause-level ground truth: the number left the prose, not the evaluation.
# The order is asserted too, because the dict cannot catch a KB relabelling and the
# labels KB1..KB5 are what every table's rows are read through.
KB_ORDER = ['REAL-FM-7', 'fqa', 'arcade-game', 'REAL-FM-4', 'busybox-1.18.0']
check('|Ctau| in the KB1..KB5 order the tables are read through',
      [EXPECTED_CTAU[m] for m in KB_ORDER], [22, 342, 130, 428, 994])

print('\n2. the same |Ctau| appears as tp+fn in the corrected results')
seen: dict[str, set[int]] = {}
for base, _d, fo in folds_of('*.json', R1):
    sm = semantic(fo)
    if not sm:
        continue
    seen.setdefault(base.split('_')[0], set()).add(
        sm.get('true_positives', 0) + sm.get('false_negatives', 0))
for model, want in EXPECTED_CTAU.items():
    if model in seen:
        check(f'|Ctau| {model} == tp+fn, single-valued', sorted(seen[model]), [want])

# ---------------------------------------------------------------------------
# 3. Numbers quoted in A5 / B7 / B20.
# ---------------------------------------------------------------------------
print('\n3. numbers quoted in the paper')

cells: dict[str, list[float]] = {}
eq_hits: list[tuple[str, int]] = []
eq_scored = 0
pos_frac: list[float] = []
pooled_p = pooled_n = 0
acc_mismatch = 0
acc_folds = 0
for base, _d, fo in folds_of('*.json', R1):
    sm = semantic(fo)
    if sm:
        cells.setdefault(base, []).append(sm.get('recall', 0.0))
    ev = fo.get('evaluation') or {}
    if ev.get('exact_equiv') is not None:
        eq_scored += 1
        if ev['exact_equiv'] in (1, True):
            eq_hits.append((base, fo.get('fold_index')))
    ts = fo.get('test_size') or {}
    if ts:
        tot = ts.get('positive', 0) + ts.get('negative', 0)
        if tot:
            pos_frac.append(ts['positive'] / tot)
            pooled_p += ts['positive']
            pooled_n += ts['negative']
    m = fo.get('metrics') or {}
    if m and ts:
        acc_folds += 1
        n = (m.get('true_positives', 0) + m.get('true_negatives', 0)
             + m.get('false_positives', 0) + m.get('false_negatives', 0))
        if n != (ts.get('positive', 0) + ts.get('negative', 0)):
            acc_mismatch += 1

saturated = sum(1 for v in cells.values() if abs(statistics.mean(v) - 1.0) < 1e-9)
check('cells with semantic recall exactly 1.0', saturated, 18)
check('cells scored', len(cells), 28)

check('exact equivalence: folds scored', eq_scored, 84)
check('exact equivalence: attained', len(eq_hits), 1)
if eq_hits:
    check('exact equivalence: on the smallest model', eq_hits[0][0].startswith('REAL-FM-7_rs_3n'), True)
    check('   ... and |Ctau| there is the smallest of the five',
          min(EXPECTED_CTAU.values()), EXPECTED_CTAU['REAL-FM-7'])

# The trivial-baseline reference. Pooled and per-fold-mean differ by ~15 points,
# and only the per-fold mean is comparable with how the paper computes accuracy.
check('accept-everything baseline, PER-FOLD MEAN (the comparable one)',
      statistics.mean(pos_frac) * 100, 74.62, tol=0.05)
check('accept-everything baseline, pooled (reference only, NOT comparable)',
      pooled_p / (pooled_p + pooled_n) * 100, 89.41, tol=0.05)

# Accuracy was written by the CV run, not by the scoring pass that carried the
# ground-truth defect. If these ever stop matching, that premise is broken.
check('accuracy folds internally consistent with their own test split', acc_mismatch, 0)
check('   ... folds checked', acc_folds > 80, True)

# The trivial baseline is a REFERENCE, and the paper states what it references:
# accepting every configuration beats ConGen's accuracy in most cells. That is the
# predicted consequence of maximality -- a maximal satisfiable subset keeps every
# constraint the examples do not rule out, so it rejects configurations a permissive
# model would accept -- and softening it would be hiding the thing the design implies.
below_trivial = 0
for f in sorted(glob.glob(str(R1 / '*_cv_incremental.json'))):
    d = json.load(open(f))
    fs = d.get('folds') or []
    accs = [x['accuracy'] for x in fs if x.get('accuracy') is not None]
    shares = [x['test_size']['positive'] / (x['test_size']['positive'] + x['test_size']['negative'])
              for x in fs if x.get('test_size')
              and (x['test_size']['positive'] + x['test_size']['negative'])]
    if accs and shares and statistics.mean(accs) < statistics.mean(shares):
        below_trivial += 1
check('cells where ConGen is below the accept-everything baseline', below_trivial, 20)

# ---------------------------------------------------------------------------
# 4. Fold agreement, reported as a STABILITY statistic and never as a score.
#
#    QUOTED IN THE RESPONSE LETTER, NOT IN THE PAPER. The 2026-09-24 review
#    dropped the sentence that carried the 29-80% range. The checks stay because
#    the letter still states it and because the range is the evidence behind the
#    threats-to-validity claim that folds disagree; what is removed is the section
#    reference, which would otherwise send a reader to a paragraph that is gone.
# ---------------------------------------------------------------------------
print('\n4. fold-agreement range (letter only; no longer printed in the paper)')
agree: dict[str, float] = {}
for f in sorted(glob.glob(str(R1 / '*.json'))):
    d = json.load(open(f))
    kbs = [set(map(str, fo.get('kb_constraints', []))) for fo in d.get('folds', [])]
    if not kbs or not all(kbs):
        continue
    inter = set.intersection(*kbs)
    mean_size = statistics.mean(len(k) for k in kbs)
    if mean_size:
        agree[os.path.basename(f)] = len(inter) / mean_size * 100
if agree:
    lo_name = min(agree, key=lambda k: agree[k])
    hi_name = max(agree, key=lambda k: agree[k])
    print(f'  lowest  {lo_name}: {agree[lo_name]:.1f}%')
    print(f'  highest {hi_name}: {agree[hi_name]:.1f}%')
    check('arcade rs_1n agreement ~29%', agree.get('arcade-game_rs_1n_cv_incremental.json', -1), 28.9, tol=1.0)
    check('fqa rs_1n agreement ~80%', agree.get('fqa_rs_1n_cv_incremental.json', -1), 79.6, tol=1.0)

# ---------------------------------------------------------------------------
# 5. The aggregation convention: per-fold mean, never the intersected KB.
#    Three separate errors in this project came from the other two aggregations
#    -- the intersected KB, and a pooled figure -- so both are pinned here as
#    numbers that must NOT equal the reported one.
# ---------------------------------------------------------------------------
print('\n5. aggregation convention: per-fold mean is what the paper reports')
p = R1 / 'arcade-game_rs_1n_cv_incremental.json'
if p.exists():
    d = json.load(open(p))
    per = [semantic(fo).get('f1_score') for fo in d['folds'] if semantic(fo)]
    inter = (((d.get('intersected_kb') or {}).get('evaluation') or {})
             .get('semantic') or {}).get('metrics', {}).get('f1_score')
    summ = ((d.get('summary') or {}).get('semantic') or {}).get('f1_score', {}).get('mean')
    check('reported .660 == per-fold mean', round(statistics.mean(per), 6), 0.659711, tol=1e-6)
    check('reported .660 == summary.mean', summ, 0.659711, tol=1e-6)
    check('intersected KB is a DIFFERENT number', round(inter, 6), 0.654709, tol=1e-6)

# ---------------------------------------------------------------------------
# 6. The 2-COV applicability threshold quoted in B20 / A5.
# ---------------------------------------------------------------------------
# QUOTED IN THE RESPONSE LETTER, NOT IN THE PAPER. The two 2-COV paragraphs that
# carried 11 of 15 training folds without a positive example, and the 19-37 usable
# queries, were dropped by the 2026-09-24 review. Both counts stay asserted: they
# are why 2-COV is the one strategy where ConGen matches the iterative methods, a
# claim the paper still makes, and a reader of the letter still meets the numbers.
#
# The two counts are DIFFERENT FACTS and must not be merged: 11 folds train on no
# positive example, 13 have no positive TEST configuration. Merging them has been
# tried once already.
print('\n6. the 2-COV boundary (letter; the paper no longer prints these counts)')
tr_zero = tr_tot = te_zero = 0
max_pos = 0
for base, _d, fo in folds_of('*2cov*.json', R1):
    tr = fo.get('train_size') or {}
    te = fo.get('test_size') or {}
    if not tr:
        continue
    tr_tot += 1
    max_pos = max(max_pos, tr.get('positive', 0))
    if tr.get('positive', 0) == 0:
        tr_zero += 1
    if te.get('positive', 0) == 0:
        te_zero += 1
check('2-COV folds', tr_tot, 15)
check('2-COV folds with |E+| == 0 in training', tr_zero, 11)
check('2-COV max |E+| over all folds', max_pos, 1)
check('2-COV folds with no positive TEST example', te_zero, 13)

# ---------------------------------------------------------------------------
# 7. Cap sensitivity of the iterative baseline. This is the evidence that the
#    baseline was not starved: the budget was raised 20x and the return per
#    query collapsed, with nothing converging at any budget.
#
#    ⚠ EVERY VALUE HERE IS A PER-FOLD MEAN. Quoting fold 0 understated
#    REAL-FM-4 (its least responsive fold, 3->4) and overstated arcade (its most
#    responsive, 10->45) — wrong twice, in opposite directions, which reads as
#    consistent. That is the fifth instance this week of the same hazard:
#    fold-0 vs mean, pooled vs mean, intersected vs mean. Quote the aggregation
#    the paper uses, and say which one it is.
# ---------------------------------------------------------------------------
# QUOTED IN THE RESPONSE LETTER, NOT IN THE PAPER. The cap probe answers the
# question of whether the iterative baseline was starved of budget, and the
# answer lives in the letter. The paper states only that the baselines hit their
# budget, which Table 14's caption carries and the per-fold checks above assert.
print('\n7. cap sensitivity of the iterative baseline (letter only, per-fold means)')
import re as _re

cap_rows: dict[tuple[str, str], dict[int, float]] = {}
stop_reasons: dict[str, int] = {}
for f in sorted(glob.glob(str(REPO / 'data' / 'results_sosym' / 'cap_probe*' / '**' / '*.json'),
                          recursive=True)):
    if '/partials/' in f:
        continue
    m = _re.search(r'/([^/]+?)_(rs_1n|rs_m|2cov|ff)_example_first_cap(\d+)/', f)
    if not m:
        continue
    try:
        d = json.load(open(f))
    except Exception:
        continue
    ks = [fo['statistics']['n_kb'] for fo in d.get('folds', [])
          if fo.get('statistics', {}).get('n_kb') is not None]
    for fo in d.get('folds', []):
        cr = fo.get('convergence_reason') or (fo.get('performance') or {}).get('convergence_reason')
        if cr:
            stop_reasons[cr] = stop_reasons.get(cr, 0) + 1
    if ks:
        cap_rows.setdefault((m.group(1), m.group(2)), {})[int(m.group(3))] = statistics.mean(ks)

for (model, samp), caps in sorted(cap_rows.items()):
    lo, hi = min(caps), max(caps)
    print(f'  {model} {samp}: cap {lo} -> {hi}, mean |KB| {caps[lo]:.2f} -> {caps[hi]:.2f}'
          f'  ({caps[hi] / caps[lo]:.2f}x for {hi // lo}x budget)')

check('REAL-FM-4 rs_1n, mean |KB| at cap 250', cap_rows.get(('REAL-FM-4', 'rs_1n'), {}).get(250, -1), 4.33, tol=0.01)
check('REAL-FM-4 rs_1n, mean |KB| at cap 5000', cap_rows.get(('REAL-FM-4', 'rs_1n'), {}).get(5000, -1), 12.33, tol=0.01)
check('arcade rs_1n, mean |KB| at cap 250', cap_rows.get(('arcade-game', 'rs_1n'), {}).get(250, -1), 11.0, tol=0.01)
check('arcade rs_1n, mean |KB| at cap 5000', cap_rows.get(('arcade-game', 'rs_1n'), {}).get(5000, -1), 32.67, tol=0.01)
check('fqa rs_1n, doubling 10k -> 20k buys under one constraint',
      cap_rows.get(('fqa', 'rs_1n'), {}).get(20000, 0) - cap_rows.get(('fqa', 'rs_1n'), {}).get(10000, 0),
      0.67, tol=0.01)

# The invariant the whole argument rests on: nothing converged, at any budget.
# If a future probe ever stops for another reason, the "lower bound" framing in
# A5 and A7 has to be re-examined rather than repeated.
check('every cap-probe fold stopped on max_queries, none converged',
      sorted(stop_reasons), ['max_queries'])
check('   ... folds observed', stop_reasons.get('max_queries', 0), 42)

# ---------------------------------------------------------------------------
# 8. The passive-vs-active comparison, as INVARIANTS. Per-cell gaps are
#    deliberately NOT asserted: the models do not share a query budget (REAL-FM-7
#    stops on no_query at 953-2,386, busybox ran at 1,000, the rest at 5,000), so
#    a gap is only readable beside its own budget. What is asserted here is what
#    no budget policy can move.
#
#    Every cell is read from ONE tree, and both halves of a cell come from it.
#    The failure mode to catch is a ConGen column set beside an iterative column
#    computed differently: that pairing matches no tree and reproduces from none.
# ---------------------------------------------------------------------------
print('\n8. passive vs active: the invariants, not the per-cell gaps')
cells_ = [(st_, sm) for st_ in STEMS for sm in SAMPLINGS
          if all(cell(st_, sm, m) for m in MODES)]
check('cells with a result in both modes', len(cells_), 28)

gaps = {(st_, sm): {m: cell(st_, sm, m)['gap'] for m in MODES}
        for st_, sm in cells_}
check('cells where the baseline wins in BOTH modes',
      sum(1 for g in gaps.values() if all(v < 0 for v in g.values())), 0)
check('cells where example-only beats ConGen',
      sum(1 for g in gaps.values() if g['example_only'] < 0), 0)
check('cells where example-first beats ConGen',
      sum(1 for g in gaps.values() if g['example_first'] < 0), 1)

# Mode collapse: identical iterative F1 under both modes. That is the signature of
# an extractor that has lost its method axis, and it makes an active-vs-passive
# comparison uninformative rather than merely wrong. Not one cell shows it.
check('mode-collapsed cells', sum(1 for c in cells_ if collapsed(*c)), 0)

# Three stopping rules, three different kinds of fact. no_query is the strong one:
# the active baseline asked every question available to it and still lost.
stops: dict = {}
for _b, _d, fo in folds_of('*_cv_*.json', REPO / 'data' / 'results_sosym_r1' / 'interactive'):
    r = fo.get('convergence_reason')
    stops[r] = stops.get(r, 0) + 1
check('folds stopping on max_queries (budget-limited)', stops.get('max_queries'), 66)
check('folds stopping on no_query (asked everything available)', stops.get('no_query'), 18)
check('folds stopping on pool_exhausted (data-limited)', stops.get('pool_exhausted'), 84)
check('interactive folds total', sum(stops.values()), 168)

# Table 14's caption: "Every example-only run stopped when the example pool was
# exhausted, and every example-first run when the query budget was reached (5,000, and
# 1,000 for KB5), except on KB1, where no further query could be generated."
#
# The counts above are totals; the caption is a statement about WHICH fold stopped how,
# and a total cannot tell "all 18 KB1 folds" from "18 folds scattered anywhere". Both
# halves are checked per fold, and the budget is read from the folds that hit it rather
# than from a constant, so a re-run at another cap moves the check rather than passing.
by_mode: dict = {}
for _b, _d, fo in folds_of('*_cv_*.json', REPO / 'data' / 'results_sosym_r1' / 'interactive'):
    mode = 'example_first' if 'example_first' in _b else 'example_only'
    by_mode.setdefault(mode, []).append((_b.split('_cv_')[0], fo))
check('example-only folds NOT stopping on an exhausted pool',
      [b for b, f in by_mode['example_only'] if f.get('convergence_reason') != 'pool_exhausted'],
      [])
first_no_query = sorted({b for b, f in by_mode['example_first']
                         if f.get('convergence_reason') == 'no_query'})
check('example-first units that ran out of generatable queries',
      sorted({b.split('_rs')[0].split('_2cov')[0].split('_ff')[0] for b in first_no_query}),
      ['REAL-FM-7'])
check('   ... and that is every KB1 fold, all 18',
      len([b for b, f in by_mode['example_first'] if b.startswith('REAL-FM-7')]), 18)
check('example-first folds elsewhere, all stopped by the budget',
      [b for b, f in by_mode['example_first']
       if not b.startswith('REAL-FM-7') and f.get('convergence_reason') != 'max_queries'],
      [])
budgets = sorted({f['n_queries'] for b, f in by_mode['example_first']
                  if f.get('convergence_reason') == 'max_queries'})
check('the budgets the example-first runs reached', budgets, [1000, 5000])
check('   ... and 1,000 is busybox alone',
      sorted({b.split('_')[0] for b, f in by_mode['example_first']
              if f.get('convergence_reason') == 'max_queries' and f['n_queries'] == 1000}),
      ['busybox-1.18.0'])

# busybox at two budgets. The strongest form of "the baseline was not starved":
# not a similar score, the SAME fourteen constraints. One fold, same split and
# seed as the cap-1,000 run, so it compares against that fold and nothing else.
BB5 = (REPO / 'data' / 'results_sosym' / 'cap_probe_busybox'
       / 'busybox-1.18.0_rs_1n_example_first_cap5000' / 'interactive'
       / 'busybox-1.18.0_rs_1n_fold0_example_first_cap5000.json')
# Both sides live under cap_probe_busybox rather than the sweep's partials/, which
# is gitignored: an assertion whose input a fresh clone lacks is one that skips
# silently, and a skipped check reads exactly like a passing one.
BB1 = (REPO / 'data' / 'results_sosym' / 'cap_probe_busybox'
       / 'busybox-1.18.0_rs_1n_example_first_cap1000' / 'interactive'
       / 'busybox-1.18.0_rs_1n_fold0_example_first_cap1000.json')
if not (BB5.exists() and BB1.exists()):
    failures.append('busybox cap-sensitivity inputs missing -- checks skipped')
else:
    def _kb(path):
        fo = json.load(open(path))['fold']
        ids = {c['id'] if isinstance(c, dict) else c for c in fo['kb_constraints']}
        return fo, ids
    f5, k5 = _kb(BB5)
    f1, k1 = _kb(BB1)
    check('busybox cap 5000 stopped on max_queries, not the guard',
          f5['convergence_reason'], 'max_queries')
    check('busybox cap 5000 queries', f5['n_queries'], 5000)
    check('busybox cap 1000 queries', f1['n_queries'], 1000)
    check('busybox |KB| at cap 1000', len(k1), 14)
    check('busybox |KB| at cap 5000', len(k5), 14)
    check('busybox KB is the IDENTICAL SET at both caps', k5 == k1, True)
    check('busybox cap 5000 wall clock, hours',
          f5['performance']['runtime_ms'] / 3.6e6, 15.53, tol=0.02)
    check('busybox cap 1000 wall clock, hours',
          f1['performance']['runtime_ms'] / 3.6e6, 2.12, tol=0.02)

# "Consistently below 0.06" is a claim about BOTH modes, and it does not hold:
# under example-first not one cell of 28 is below 0.06. Under example-only, 12 are.
# The two modes are therefore not interchangeable in any statement about the
# baseline's level, which is why every such statement names its mode.
below = {m: sum(1 for st_, sm in cells_ if cell(st_, sm, m)['iterative'] < 0.06)
         for m in MODES}
check('example-first cells with iterative F1 below 0.06', below['example_first'], 0)
check('example-only cells with iterative F1 below 0.06', below['example_only'], 12)

# The oracle benefit the two modes exist to measure: consulting the oracle first
# is worth something in every cell, never nothing. Measured over all 28 cells --
# the population is the whole tree, not a subset, so the minimum is the weakest
# case anywhere rather than the weakest case in a chosen slice.
benefit = [cell(st_, sm, 'example_first')['iterative']
           - cell(st_, sm, 'example_only')['iterative']
           for st_, sm in cells_]
check('cells showing ZERO oracle benefit', sum(1 for b in benefit if abs(b) < 1e-12), 0)
check('smallest oracle benefit across all cells', min(benefit), 0.0035, tol=1e-3)

# The one number in the comparison no re-score can move.
cg_with_queries = sum(
    1 for _b, _d, fo in folds_of('*_cv_*.json', R1) if fo.get('n_queries') is not None)
check('ConGen folds issuing oracle queries', cg_with_queries, 0)

# ---------------------------------------------------------------------------
# 9b. Two figures the drafts quote about variation. Both are asserted against a
#     COMMITTED measurement, because neither is recoverable from the result files
#     alone -- one needs a probe, the other needs a stated definition.
# ---------------------------------------------------------------------------
print('\n9b. variation: Reduce input-order sensitivity, and runtime spread')

# The spread between folds of the SAME cell, max/min of the fold wall clocks. Named
# here because "runtime spread" has no meaning until the population is stated, and
# the drafts' 2.8x is a different quantity entirely (see the order-sensitivity block
# below): it is the description:semantic spread ratio, not a ratio of runtimes.
spreads = []
for f in sorted(glob.glob(str(R1 / '*_cv_incremental.json'))):
    rts = [(x.get('performance') or {}).get('runtime_ms')
           for x in (json.load(open(f)).get('folds') or [])]
    rts = [r for r in rts if r]
    if len(rts) > 1 and min(rts) > 0:
        spreads.append(max(rts) / min(rts))
check('largest per-cell fold-runtime spread, max/min', max(spreads), 1.5249, tol=1e-4)
check('   ... cells with more than one timed fold', len(spreads), 28)

# Reduce is greedy: the surviving redundant representative depends on the order it
# walks B'. The finding is the RATIO -- order moves the description tier far more
# than the semantic one -- not the absolute spreads, so the ratio is what is pinned.
_os = REPO / 'data' / 'results_sosym_r1' / 'order_sensitivity' / 'order_sensitivity.json'
if not _os.exists():
    failures.append('order-sensitivity measurement missing -- checks skipped')
else:
    _s = json.load(open(_os))['summary']
    check('order sensitivity: folds measured', _s['folds'], 84)
    check('order sensitivity: permutations per fold', _s['permutations_per_fold'], 20)
    check('order sensitivity: folds whose score moved with order', _s['folds_whose_score_moved'], 77)
    check('order sensitivity: largest description spread', _s['max_description_spread'], 0.5182, tol=1e-4)
    check('order sensitivity: largest semantic spread', _s['max_semantic_spread'], 0.8385, tol=1e-4)
    check('order sensitivity: description:semantic ratio, median', _s['desc_over_sem_ratio_median'], 2.7857, tol=1e-4)
    check('   ... folds with a finite ratio', _s['desc_over_sem_ratio_n_finite'], 67)
    check('   ... folds with ZERO semantic spread', _s['folds_with_zero_semantic_spread'], 17)

# ---------------------------------------------------------------------------
# 9. The significance tests. Asserted through significance_tests.compute() so
#     the suite checks THOSE numbers, not a second implementation of them.
#
#     The invariant that matters is the last one. Claim 2 is excluded from the
#     Holm family because at n=5 the exact test's floor p is 0.0625, so no
#     outcome could reach alpha -- it is untestable by design, not a negative
#     result. If the design ever grows enough instances to make it testable,
#     that check fails and forces the question, instead of leaving the claim
#     quietly excluded forever. An absence rendered as a result is the failure
#     mode this whole effort has been about.
# ---------------------------------------------------------------------------
print('\n9. S6.2.6 significance: medians, Holm rejections, and what cannot be tested')
try:
    from significance_tests import compute as _sig_compute, holm as _holm, floor_p, ALPHA
except ImportError as exc:                      # scipy absent, or the tool moved
    failures.append(f'significance tests unavailable ({exc}) -- checks skipped')
else:
    sig = {r['name'].split()[0]: r for r in _sig_compute()}
    for claim, n, med in (('1a', 28, 0.6312), ('1b', 28, 0.3142), ('3', 28, 0.3568),
                          ('5', 28, 0.1461), ('2', 5, 0.0445)):
        check(f'claim {claim}: n', sig[claim]['n'], n)
        check(f'claim {claim}: median difference', sig[claim]['median'], med, tol=5e-5)
    check('claim 1a wins, all 28 (S6.2.6 (i))', sig['1a']['wins'], 28)
    check('claim 1b wins, 27 of 28 (S6.2.6 (ii))', sig['1b']['wins'], 27)
    # S6.2.6 names the exception: "the exception is KB3 under RS(3n)". A count of 27
    # cannot tell that apart from any other cell going the other way, and the
    # sentence makes the stronger statement, so the stronger one is asserted.
    check('   ... and it is KB3 under RS(3n), as the sentence says',
          sig['1b']['losses'], ['arcade-game_rs_3n'])
    check('claim 5 wins, all 28 (S6.2.6 (iii))', sig['5']['wins'], 28)
    # S6.2.6 (iv): "semantic comparison exceeds description-based comparison of
    # ConGen's result on all 28 combinations, with a median difference of 0.357."
    check('claim 3 wins, all 28 combinations (S6.2.6 (iv))', sig['3']['wins'], 28)
    check('   ... with no combination against it', sig['3']['losses'], [])
    # S6.2.6: "All four differences are significant (p < 10^-7)." Asserted on the RAW
    # p, not the Holm-adjusted one: Holm can only raise it, so a raw p below the
    # threshold is the stronger statement and the one the sentence makes.
    for claim in ('1a', '1b', '3', '5'):
        check(f'claim {claim}: p below 1e-7', bool(sig[claim]['p'] < 1e-7), True)

    fam = _holm(_sig_compute())
    check('claims in the Holm family', len(fam), 4)
    check('Holm rejections', sum(1 for r in fam if r['reject']), 4)
    check('Holm adjusted p is non-decreasing (step-down)',
          all(a['holm'] <= b['holm'] + 1e-18 for a, b in zip(fam, fam[1:])), True)

    # The exact test must be the one we chose, not the one the data selected, and
    # it must actually apply. scipy's method='exact' computes the exact
    # distribution even when ties make it invalid, silently -- so the tie count is
    # the check that matters, and the pinned method is what keeps it meaningful.
    for claim in ('1a', '1b', '3', '5', '2'):
        check(f'claim {claim}: method is pinned exact', sig[claim]['method'], 'exact')
        check(f'claim {claim}: tied or zero differences', sig[claim]['ties'], 0)

    # DESIGNED TO FAIL ON SUCCESS. This is the only check in the suite that goes
    # red when the project improves, and that is deliberate -- do not "fix" it by
    # relaxing it. Claim 2 sits outside the Holm family because at n=5 the exact
    # test cannot reach alpha whatever the data says. Add a sixth model and
    # floor_p(6) = 0.03125 < alpha: the claim becomes testable, this check fails,
    # and someone has to decide whether to test it. Without that, the exclusion
    # outlives its own justification and an untested claim reads as a settled one.
    check('claim 2 is excluded from the family', '2' not in {r['name'].split()[0] for r in fam}, True)
    check('claim 2 floor p exceeds alpha (cannot reject at any outcome)',
          floor_p(sig['2']['n']) > ALPHA, True)
    check('claim 2 floor p', floor_p(sig['2']['n']), 0.0625, tol=1e-9)
    # S6.2.6's last sentence: "its median difference of 0.045 is reported
    # descriptively". The median is 0.0445, and 0.045 is that figure rounded HALF UP
    # to three places -- Python's round() gives 0.044, so the comparison is made the
    # way the number was typeset rather than the way the language rounds.
    from decimal import ROUND_HALF_UP as _HALF_UP, Decimal as _D
    check('claim 2 median as the paper prints it',
          float(_D(repr(sig['2']['median'])).quantize(_D('0.001'), rounding=_HALF_UP)),
          0.045, tol=1e-9)

# ---------------------------------------------------------------------------
# 10. The package must work on a machine that is not this one.
#
#     score_interactive.toml shipped with 56 kb_dir values hardcoding one
#     developer's checkout. It was noticed and judged harmless because the run
#     worked HERE -- which answers whether the path resolves on this machine,
#     not whether the package resolves anywhere else. The rule below is what
#     would have caught it without anyone noticing: no tracked config may name
#     an absolute or home-relative path, on any platform.
# ---------------------------------------------------------------------------
print('\n10. portability: no tracked config names a path only this machine has')
_abs = re.compile(r'=\s*"(?:[/~]|[A-Za-z]:[\\/])')
try:
    _tomls = subprocess.run(['git', 'ls-files', '*.toml'], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.split()
except Exception as exc:                        # not a git checkout
    failures.append(f'portability scan unavailable ({exc}) -- check skipped')
else:
    offenders = [t for t in _tomls
                 if any(_abs.search(ln) for ln in (REPO / t).read_text().splitlines())]
    check('tracked .toml files scanned', len(_tomls) > 0, True)
    if offenders:
        print('   machine-specific paths in:')
        for o in offenders[:10]:
            print(f'     {o}')
    check('tracked configs naming an absolute path', len(offenders), 0)

# ---------------------------------------------------------------------------
# The figures the SoSyM revision added. They live in sibling modules because they
# are new claims with their own provenance to explain, not because the sections
# differ in kind: the rule is the same one this file has always applied. Each
# module asserts through the `check` above, so a number that moved is reported
# here with every other. Their section headers carry a TAG rather than a number:
# the artifact drops two sections of this file, and a number would then have to be
# maintained in two trees to stay contiguous in both.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generator_contracts                 # noqa: E402
import revision_bias_composition            # noqa: E402
import revision_cabsc_condition             # noqa: E402
import revision_comparison_prose            # noqa: E402
import revision_ea2468_limit                # noqa: E402
import revision_headline_claims             # noqa: E402
import revision_minimal_review              # noqa: E402
import revision_order_and_working_example   # noqa: E402
import revision_run_cost                    # noqa: E402
import revision_target_theory_size          # noqa: E402

for module in (revision_bias_composition, revision_ea2468_limit,
               revision_run_cost, revision_order_and_working_example,
               revision_cabsc_condition, revision_minimal_review,
               revision_target_theory_size, revision_comparison_prose,
               revision_headline_claims, generator_contracts):
    try:
        module.run(check, REPO)
    except Exception as exc:                # a source that moved or vanished
        failures.append(f'{module.__name__} could not run: {exc!r}')
        print(f'  [FAIL] {module.__name__}: {exc!r}')

# ---------------------------------------------------------------------------
print(f'\n{"=" * 70}')
if failures:
    print(f'FAIL: {len(failures)} of {checks} numbers no longer match the paper:')
    for f in failures:
        print(f'  - {f}')
    print('\nA number that moved is a finding. Update the paper to the measurement,')
    print('never the assertion to the number you hoped for.')
    sys.exit(1)
# A pass is a POSITIVE COUNT, never the absence of a failure. With zero checks this
# script would otherwise print "OK: all 0 numbers" and exit 0 -- and an empty run is
# indistinguishable from a clean one to anything reading the exit code. The same shape
# passed an artifact whose test suite had not run at all, because pytest was absent and
# `grep FAILED` found nothing.
MINIMUM_CHECKS = 400
if checks < MINIMUM_CHECKS:
    print(f'FAIL: only {checks} checks ran; expected at least {MINIMUM_CHECKS}.')
    print('An empty or truncated run is not a pass. Something above exited early or')
    print('skipped a section -- find it rather than lowering this number.')
    sys.exit(1)
print(f'OK: all {checks} numbers quoted in the paper reproduce from the data.')
sys.exit(0)

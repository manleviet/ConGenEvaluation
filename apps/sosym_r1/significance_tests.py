#!/usr/bin/env python3
"""Significance tests across instances, with the two cautions that matter.

The reviewers ask for significance to be *discussed*. The design gives three
folds per cell, which has no power and whose folds share one example pool, so the
unit of analysis is the **(knowledge base x sampling) instance**: one paired
observation per cell, Wilcoxon signed-rank, Holm correction over the family.

TWO THINGS THIS SCRIPT PRINTS THAT A PLAIN p-VALUE TABLE WOULD HIDE
-------------------------------------------------------------------
1. **The exact-test floor.** With n paired observations all differing in the same
   direction, the smallest attainable two-sided p is 2/2**n. At n=28 that is
   7.4506e-09, and three of our tests return exactly it. Printing that to three
   figures implies precision the test does not have; it means "every difference
   went the same way", nothing more. Lead with the median difference.

2. **Tests that cannot reject.** At n=5 the floor is 0.0625, so a five-instance
   comparison can never reach 0.05 whatever the data does. Reporting "not
   significant" for such a test implies the data spoke against the claim when the
   design never let it speak. The script flags these as UNTESTABLE rather than
   letting them read as negative results.

Run: PYTHONPATH=. python3 apps/sosym_r1/significance_tests.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from pathlib import Path

try:
    from scipy.stats import wilcoxon
except ImportError:
    sys.exit("scipy required: pip install scipy")

REPO = Path(__file__).resolve().parents[2]
T = REPO / 'data' / 'results_sosym_r1'
ALPHA = 0.05

# Pinned, not left to 'auto'. scipy's auto picks exact or asymptotic based on
# whether the DIFFERENCES contain ties, so the method would be chosen by the data:
# one re-score producing two equal differences would silently change the method and
# the p-value by 508x, and the paper's "smallest attainable at this sample size"
# would quietly become false. Pin the method and count the ties separately.
METHOD = 'exact'


def cell_mean(path: Path, tier: str = 'semantic', key: str = 'f1_score'):
    """Per-fold mean for one cell. Per-fold, never intersected — see hub 7a."""
    try:
        d = json.loads(path.read_text())
    except Exception:
        return None
    v = [((fo.get('evaluation') or {}).get(tier) or {}).get('metrics', {}).get(key)
         for fo in d.get('folds', [])]
    v = [x for x in v if x is not None]
    return statistics.mean(v) if v else None


def count_ties(diff) -> int:
    """Tied |differences| plus zeros -- the two things that invalidate the exact test.

    This has to be counted here because scipy will NOT tell us. Measured on 1.17.1:
    with one tied pair at n=28, method='auto' returns 3.786883e-06 while
    method='exact' returns 7.450581e-09 and issues no warning at all -- it computes
    the exact distribution as though the tie were not there. So pinning the method
    without this counter would replace a visible 508x change with a silent wrong
    number, which is the opposite of what pinning is for.
    """
    nz = [abs(d) for d in diff if d != 0]
    return (len(diff) - len(nz)) + (len(nz) - len(set(nz)))


def floor_p(n: int) -> float:
    """Smallest two-sided p the exact signed-rank test can produce at this n."""
    return 2.0 / (2 ** n) if n else 1.0


def compute() -> list:
    """The five paired tests, as data. main() prints; check_paper_numbers asserts.

    Returned rather than printed so the suite asserts THESE numbers rather than a
    second implementation of them -- a table computed twice is the pairing defect
    this effort has hit twice already.
    """
    cells = [os.path.basename(f).replace('_cv_incremental.json', '')
             for f in sorted(glob.glob(str(T / 'congen' / '*.json')))]
    D = {}
    for c in cells:
        D[c] = {
            'cg': cell_mean(T / 'congen' / f'{c}_cv_incremental.json'),
            'cg_desc': cell_mean(T / 'congen' / f'{c}_cv_incremental.json', 'description'),
            'eo': cell_mean(T / 'interactive' / f'{c}_cv_incremental_example_only.json'),
            'ef': cell_mean(T / 'interactive' / f'{c}_cv_incremental_example_first.json'),
        }

    results = []

    def paired(name: str, a: str, b: str):
        pairs = [(D[c][a], D[c][b]) for c in cells
                 if D[c].get(a) is not None and D[c].get(b) is not None]
        diff = [x - y for x, y in pairs]
        stat, p = wilcoxon([x for x, _ in pairs], [y for _, y in pairs],
                           method=METHOD)
        results.append({'name': name, 'n': len(pairs), 'median': statistics.median(diff),
                        'wins': sum(1 for d in diff if d > 0), 'p': p, 'W': stat,
                        'method': METHOD, 'ties': count_ties(diff)})

    paired('1a ConGen vs iterative, no oracle', 'cg', 'eo')
    paired('1b ConGen vs iterative, with oracle', 'cg', 'ef')
    paired('3  semantic tier vs description tier', 'cg', 'cg_desc')
    paired('5  oracle access helps the baseline', 'ef', 'eo')

    # Claim 2 pairs each model's 2-COV cell against the mean of its random samplings,
    # which is one observation per MODEL: n=5, below what the test can resolve.
    pairs = []
    for c in cells:
        if not c.endswith('_2cov'):
            continue
        model = c[:-len('_2cov')]
        rnd = [D[f'{model}_{s}']['cg'] for s in ('rs_1n', 'rs_2n', 'rs_3n', 'rs_m')
               if f'{model}_{s}' in D and D[f'{model}_{s}']['cg'] is not None]
        if rnd and D[c]['cg'] is not None:
            pairs.append((D[c]['cg'], statistics.mean(rnd)))
    if pairs:
        diff = [x - y for x, y in pairs]
        stat, p = wilcoxon([x for x, _ in pairs], [y for _, y in pairs], method=METHOD)
        results.append({'name': '2  2-COV vs random sampling', 'n': len(pairs),
                        'median': statistics.median(diff),
                        'wins': sum(1 for d in diff if d > 0), 'p': p, 'W': stat,
                        'method': METHOD, 'ties': count_ties(diff)})

    return results


def holm(results: list) -> list:
    """Holm-adjusted p for the testable members, step-down, monotonic."""
    family = sorted([r for r in results if floor_p(r['n']) <= ALPHA], key=lambda r: r['p'])
    out, running = [], 0.0
    for i, r in enumerate(family):
        running = max(running, min(1.0, r['p'] * (len(family) - i)))
        out.append({**r, 'holm': running, 'reject': running < ALPHA})
    return out


def main() -> int:
    results = compute()
    print(f"{'claim':40}{'n':>4}{'median D':>11}{'wins':>8}{'p':>12}  note")
    for r in results:
        fl = floor_p(r['n'])
        note = ''
        if fl > ALPHA:
            note = f'UNTESTABLE: floor p={fl:.4f} > {ALPHA}'
        elif r['ties']:
            note = (f'INVALID: {r["ties"]} tied/zero difference(s) -- the exact test '
                    f'does not apply and scipy will not say so')
        elif abs(r['p'] - fl) < 1e-15:
            note = f'at the exact-test floor (2/2^{r["n"]}) — report as p < 1e-7'
        print(f"{r['name']:40}{r['n']:>4}{r['median']:>+11.4f}"
              f"{r['wins']:>4}/{r['n']:<3}{r['p']:>12.3e}  {note}")

    # Holm over the family, excluding tests the design cannot resolve: including
    # an untestable comparison in the family costs power on the ones that can.
    family = holm(results)
    excluded = [r for r in results if floor_p(r['n']) > ALPHA]
    print(f"\nHolm correction over {len(family)} testable claims "
          f"({len(excluded)} excluded as untestable by design):")
    for i, r in enumerate(family):
        print(f"  {r['name']:40} p x{len(family) - i} = {r['holm']:.3e}  "
              f"{'REJECT H0' if r['reject'] else 'not significant'}")
    for r in excluded:
        print(f"  {r['name']:40} NOT TESTED — n={r['n']} cannot reach {ALPHA}; "
              f"report the observed {r['median']:+.4f} descriptively")
    return 0


if __name__ == '__main__':
    sys.exit(main())

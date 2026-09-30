#!/usr/bin/env python
"""Render the raw-vs-reduced NE measurement as Markdown tables (stdout).

Inputs are the three JSON files written under data/results_sosym_r1_rawne/ by
compare_ne_raw_vs_reduced.py and score_with_retained_ne.py (reduced tree and raw tree).
Every cell is a MEAN OVER FOLDS rendered with paper_tables/latex.py's formatters, so a
flagged change is a change of the printed string. busybox rs_1n was not rerun without
minimization (deadline decision 2026-09-30); it appears only in the reduced-side
scoring variant and is marked as such everywhere else.

    summarize_ne_raw_vs_reduced.py --dir data/results_sosym_r1_rawne
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apps.sosym_r1.paper_tables import latex as tex  # noqa: E402

NOT_RERUN = 'busybox-1.18.0_rs_1n'


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', required=True)
    d = Path(ap.parse_args().dir)
    cmp_ = json.loads((d / 'raw-vs-reduced.json').read_text())
    red_ne = json.loads((d / 'reduced-scored-with-ne.json').read_text())
    raw_ne = json.loads((d / 'raw-scored-with-ne.json').read_text())
    folds, cells = cmp_['folds'], {c['model']: c for c in cmp_['cells']}
    models = sorted({r['model'] for r in red_ne})

    def by_model(rows, model):
        return [r for r in rows if r['model'] == model]

    q = tex.quality
    print('## Quality per combination (mean over folds)\n')
    print('red = reduced (committed, printed); red+NE = reduced scored WITH retained ¬e⁻; '
          'raw = raw NE. Changed printed cells (raw vs red) marked *.\n')
    print('| combination | sem F1 red | red+NE | raw | sem P red/red+NE/raw | '
          'sem R red/red+NE/raw | clause F1 red/red+NE/raw | desc F1 red/red+NE/raw | '
          'acc red/raw | |KB| red/raw |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for m in models:
        rr, rn = by_model(red_ne, m), by_model(raw_ne, m)

        def t(rows, var, tier, k):
            return mean([r[var][tier][k] for r in rows]) if rows else None

        def trio(tier, k):
            a, b, c = (q(t(rr, 'excluded', tier, k)), q(t(rr, 'included', tier, k)),
                       q(t(rn, 'excluded', tier, k)) if rn else 'not rerun')
            return f"{a}/{b}/{c}{'*' if rn and c != a else ''}"
        sem = [q(t(rr, 'excluded', 'semantic', 'f1_score')),
               q(t(rr, 'included', 'semantic', 'f1_score')),
               q(t(rn, 'excluded', 'semantic', 'f1_score')) if rn else 'not rerun']
        if rn and sem[2] != sem[0]:
            sem[2] += '*'
        c = cells.get(m)
        acc = (f"{c['acc_printed'][1]}/{c['acc_printed'][0]}"
               f"{'*' if c['acc_printed'][0] != c['acc_printed'][1] else ''}"
               if c else 'n/a')
        kb = (f"{c['kb_printed'][1]}/{c['kb_printed'][0]}"
              f"{'*' if c['kb_printed'][0] != c['kb_printed'][1] else ''}" if c else 'n/a')
        print(f"| {m}{' (not rerun without minimization)' if m == NOT_RERUN else ''} | "
              f"{' | '.join(sem)} | {trio('semantic', 'precision')} | "
              f"{trio('semantic', 'recall')} | {trio('clause', 'f1_score')} | "
              f"{trio('description', 'f1_score')} | {acc} | {kb} |")

    print('\n## Cost (Table 9 quantities, mean over folds): reduced -> raw\n')
    print('| combination | GenNE checks | total checks | runtime ms |')
    print('|---|---|---|---|')
    for m in models:
        c = cells.get(m)
        if not c:
            print(f'| {m} | not rerun without minimization | | |')
            continue
        row = [f"{c[k + '_printed'][1]} -> {c[k + '_printed'][0]}"
               for k in ('prep_checks', 'total_checks', 'runtime_ms')]
        print(f"| {m} | {' | '.join(row)} |")

    print('\n## Compactness: |KB| + n_ne per fold\n')
    red_tot = sum(f['reduced']['kb'] + f['reduced']['n_ne'] for f in folds)
    raw_tot = sum(f['raw']['kb'] + f['raw']['n_ne'] for f in folds)
    rel = [1 - (f['reduced']['kb'] + f['reduced']['n_ne']) / (f['raw']['kb'] + f['raw']['n_ne'])
           for f in folds if f['reduced']['n_ne'] == 1]
    smaller = sum(1 for f in folds if f['reduced']['kb'] + f['reduced']['n_ne']
                  < f['raw']['kb'] + f['raw']['n_ne'])
    print(f"total reduced {red_tot} vs raw {raw_tot} over {len(folds)} folds; reduced smaller "
          f"on {smaller}; on the {len(rel)} folds with a retained ¬e⁻ relative reduction "
          f"min {min(rel):.3f} median {st.median(rel):.3f} max {max(rel):.3f}")
    ext = max(folds, key=lambda f: (f['raw']['kb'] + f['raw']['n_ne'])
              - (f['reduced']['kb'] + f['reduced']['n_ne']))
    print(f"largest: {ext['model']} fold {ext['fold']}: reduced "
          f"{ext['reduced']['kb']}+{ext['reduced']['n_ne']} vs raw "
          f"{ext['raw']['kb']}+{ext['raw']['n_ne']}")
    print('\nper combination (sum over folds of |KB|+n_ne, reduced vs raw):')
    for m in sorted({f['model'] for f in folds}):
        fs = [f for f in folds if f['model'] == m]
        a = sum(f['reduced']['kb'] + f['reduced']['n_ne'] for f in fs)
        b = sum(f['raw']['kb'] + f['raw']['n_ne'] for f in fs)
        print(f"  {m}: {a} vs {b} ({1 - a / b:+.3f})")

    whys = [w for f in folds if f['why']
            for w in list(f['why']['only_raw_why'].values())
            + list(f['why']['only_reduced_why'].values())]
    print('\n## Differing folds\n')
    print(f"KB differs on {sum(1 for f in folds if f['why'])} folds; per-constraint reasons: "
          + ', '.join(f'{k} {whys.count(k)}' for k in sorted(set(whys))))
    print(f"only-raw constraints {sum(len(f['why']['only_raw_why']) for f in folds if f['why'])}, "
          f"only-reduced {sum(len(f['why']['only_reduced_why']) for f in folds if f['why'])}")
    ne_red = [n for f in folds for n in f['ne_reduced']]
    root_ne = sum(1 for f in folds if f['why'] and f['why']['ne_is_root_reduced'])
    print(f"retained reduced ¬e⁻: {len(ne_red)} ({len(set(ne_red))} distinct); equal to the root "
          f"axiom on {root_ne} folds; raw n_ne > 0 on "
          f"{sum(1 for f in folds if f['raw']['n_ne'])} folds")
    print('distinct retained reduced ¬e⁻: ' + '; '.join(sorted(set(ne_red))))
    prep = [f['reduced']['prep_checks'] for f in folds]
    print(f"GenerateNE checks saved per fold: min {min(prep)} median {st.median(prep)} "
          f"max {max(prep)} (raw: 0 on every fold)")
    return 0


if __name__ == '__main__':
    sys.exit(main())

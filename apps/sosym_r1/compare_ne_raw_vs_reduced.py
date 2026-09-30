#!/usr/bin/env python
"""Raw vs reduced negative examples in ConGen: per fold, per cell, at printed precision.

Reads the committed (reduced) tree and a raw re-run (run_ne_raw_sweep.py, then scored
by run_compare through make_score_configs.py exactly as Table 14 was) and tests four
predictions derived from the code:

  P1  B' (AcqMss output) is identical per fold. B' is read as the SET
      kb_constraints ∪ redundant_constraints -- Reduce partitions B' into the two, and
      |B'| == n_mss is checked as a control on both sides. AcqMss's own check count
      (profiler.paper_consistency_checks) is compared too: equal counts on an
      identical B' mean the same recursion, not just the same answer.
  P2  on folds whose committed n_ne == 0, the final KB is identical (list equality,
      order included).
  P3  on folds whose committed n_ne == 1, the KB may differ; each difference is listed.
  P4  under raw NE, KB ∪ NE ∪ root rejects every TRAINING e⁻ of the fold. The theory
      is rebuilt from the fold record, and the rebuild is CONTROLLED: it must reproduce
      the fold's recorded test accuracy, or the fold is reported and nothing is claimed.

Cell values are MEANS OVER FOLDS and are rendered with the paper generator's own
formatters (paper_tables/latex.py), so "a printed value changes" means the string in
the table would change. Raw GenerateNE never calls QuickXplain, so its preprocessing
counters are never created; they are read as 0 only after asserting the fold is raw.

    compare_ne_raw_vs_reduced.py --raw data/results_sosym_r1_rawne/congen \\
        --json data/results_sosym_r1_rawne/raw-vs-reduced.json
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apps.sosym_r1.paper_tables import latex as tex                          # noqa: E402
from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder  # noqa: E402
from conacq.oracle import FMOracle                                           # noqa: E402
from apps.sosym_r1.ne_theory_checks import (                                # noqa: E402
    equivalence, explain_difference, ids, rejects_training_negatives)

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']
PREP = 'shared_preprocessing_quickxplain_checks'


def tier(fold, name, key):
    return (((fold.get('evaluation') or {}).get(name) or {}).get('metrics') or {}).get(key)


def fold_values(f: dict, raw: bool) -> dict:
    prof, perf = f['performance']['profiler'], f['performance']
    if raw:
        assert PREP not in prof or prof[PREP] == 0, 'raw fold ran QuickXplain'
    prep = prof.get(PREP, 0) if raw or f['train_size']['negative'] else 0
    if not raw and f['train_size']['negative'] and PREP not in prof:
        raise KeyError(f"reduced fold {f['fold_index']} with negatives lacks {PREP}")
    acq, red = prof['paper_consistency_checks'], perf['redundancy_consistency_checks']
    return {'acc': f['accuracy'], 'kb': len(f['kb_constraints']),
            'n_ne': f['statistics']['n_ne'], 'n_mss': f['statistics']['n_mss'],
            'sem_p': tier(f, 'semantic', 'precision'), 'sem_r': tier(f, 'semantic', 'recall'),
            'sem_f1': tier(f, 'semantic', 'f1_score'),
            'clause_f1': tier(f, 'clause', 'f1_score'),
            'desc_f1': tier(f, 'description', 'f1_score'),
            'acq_checks': acq, 'red_checks': red, 'prep_checks': prep,
            'total_checks': acq + red + prep, 'runtime_ms': perf['runtime_ms']}


# (key, formatter, table) -- the printed column each quantity lands in.
PRINTED = [('acc', tex.quality, 'T13'), ('kb', tex.one_decimal, 'T13'),
           ('sem_p', tex.quality, 'T14'), ('sem_r', tex.quality, 'T14'),
           ('sem_f1', tex.quality, 'T14'), ('clause_f1', tex.quality, 'T12'),
           ('desc_f1', tex.quality, 'T12'), ('n_ne', tex.one_decimal, '-'),
           ('prep_checks', tex.count, 'T9'), ('total_checks', tex.count, 'T9'),
           ('runtime_ms', tex.millis, 'T9')]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--raw', required=True, help='raw congen dir (scored CV files)')
    ap.add_argument('--reduced', default=str(REPO / 'data/results_sosym_r1/congen'))
    ap.add_argument('--json', required=True, help='where to write the full comparison')
    args = ap.parse_args()

    folds_out, cells_out = [], []
    for raw_cv in sorted(Path(args.raw).glob('*_cv_incremental.json')):
        model = raw_cv.name.split('_cv_')[0]
        stem = next(s for s in STEMS if model.startswith(s + '_'))
        raw_doc = json.loads(raw_cv.read_text())
        red_doc = json.loads((Path(args.reduced) / raw_cv.name).read_text())
        oracle = FMOracle(str(REPO / 'data/fms' / f'{stem}.uvl'), use_incremental=False)
        try:
            model_kb = (ConGenModelBuilder.from_bias(str(REPO / 'data/bias' / f'{stem}-bias.json'))
                        .with_oracle_data(oracle.oracle_data).build())
            per = {'raw': [], 'red': []}
            for fr, fd in zip(raw_doc['folds'], red_doc['folds']):
                assert fr['fold_index'] == fd['fold_index']
                vr, vd = fold_values(fr, True), fold_values(fd, False)
                per['raw'].append(vr)
                per['red'].append(vd)
                bp_r = set(ids(fr['kb_constraints'])) | set(fr['redundant_constraints'])
                bp_d = set(ids(fd['kb_constraints'])) | set(fd['redundant_constraints'])
                kb_r, kb_d = ids(fr['kb_constraints']), ids(fd['kb_constraints'])
                desc = {c['id']: c['description'] for c in fr['kb_constraints'] + fd['kb_constraints']
                        if isinstance(c, dict)}
                control, p4, n_tr = rejects_training_negatives(stem, model, fr, model_kb)
                control_d, p4_d, _ = rejects_training_negatives(stem, model, fd, model_kb)
                folds_out.append({
                    'model': model, 'fold': fr['fold_index'],
                    'train_neg': fr['train_size']['negative'],
                    'bprime_control': len(bp_r) == vr['n_mss'] and len(bp_d) == vd['n_mss'],
                    'bprime_equal': bp_r == bp_d,
                    'acq_checks_equal': vr['acq_checks'] == vd['acq_checks'],
                    'kb_equal_ordered': kb_r == kb_d, 'kb_equal_set': set(kb_r) == set(kb_d),
                    'only_raw': [f'{c}: {desc.get(c, "")}' for c in kb_r if c not in kb_d],
                    'only_reduced': [f'{c}: {desc.get(c, "")}' for c in kb_d if c not in kb_r],
                    'ne_raw': fr['ne_constraints'], 'ne_reduced': fd['ne_constraints'],
                    'why': (None if kb_r == kb_d else explain_difference(model_kb, fr, fd)),
                    'equivalence': equivalence(model_kb, fr, fd),
                    'p4_control': control, 'p4_rejects_all': p4, 'p4_n_train_neg': n_tr,
                    'p4_reduced_control': control_d, 'p4_reduced_rejects_all': p4_d,
                    'raw': vr, 'reduced': vd})
        finally:
            oracle.cleanup()

        cell = {'model': model, 'changed': []}
        for key, fmt, table in PRINTED:
            for side in ('raw', 'red'):
                vals = [v[key] for v in per[side] if v[key] is not None]
                cell[f'{key}_{side}'] = st.mean(vals) if vals else None
            a, b = fmt(cell[f'{key}_raw']), fmt(cell[f'{key}_red'])
            cell[f'{key}_printed'] = (a, b)
            if a != b and table != '-':
                cell['changed'].append(f'{table} {key}: {b} -> {a}')
        cells_out.append(cell)

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps({'folds': folds_out, 'cells': cells_out},
                                          indent=1))
    n = len(folds_out)
    count = lambda k: sum(1 for f in folds_out if f[k])  # noqa: E731
    print(f"folds {n}   B' control {count('bprime_control')}/{n}   "
          f"P1 B' equal {count('bprime_equal')}/{n}   "
          f"AcqMss checks equal {count('acq_checks_equal')}/{n}")
    for label, want in (('P2 (reduced n_ne=0)', 0), ('P3 (reduced n_ne=1)', 1)):
        sub = [f for f in folds_out if f['reduced']['n_ne'] == want]
        print(f"{label}: {len(sub)} folds, KB identical (ordered) "
              f"{sum(f['kb_equal_ordered'] for f in sub)}, as set "
              f"{sum(f['kb_equal_set'] for f in sub)}")
    print(f"P4 raw: control {count('p4_control')}/{n}, rejects all training e- "
          f"{count('p4_rejects_all')}/{n}   reduced incl. NE: control "
          f"{count('p4_reduced_control')}/{n}, rejects all {count('p4_reduced_rejects_all')}/{n}")
    verdicts = [f['equivalence']['verdict'] for f in folds_out]
    print('equivalence: ' + ', '.join(f'{v} {verdicts.count(v)}' for v in sorted(set(verdicts))))
    print(f"cells with a printed change: {sum(1 for c in cells_out if c['changed'])}"
          f"/{len(cells_out)}")
    return 0 if all(f['bprime_control'] and f['p4_control'] and f['p4_reduced_control']
                    for f in folds_out) else 1


if __name__ == '__main__':
    sys.exit(main())

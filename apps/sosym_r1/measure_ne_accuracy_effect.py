#!/usr/bin/env python
"""How much does the empty-NE-clause defect move the REPORTED accuracy?

cross_validation.py builds AccuracyCalculator's theory as kb_clauses + ne_clauses +
bg_clauses, citing Definition 6. On a fold with more than one training negative the
combined ¬e⁻ id resolves to a unit clause over an AUXILIARY variable, which constrains
nothing over the feature vocabulary -- so the theory scored was, in effect, the theory
without NE at all. Every accuracy / specificity / TP-TN-FP-FN on such a fold was
computed against it.

The known FP=2 is on TRAINING negatives. The tables report TEST-fold accuracy, so it
says nothing about whether any published figure moves. This measures the right thing:
per fold, test-fold metrics with the NE clauses and without them, on the SAME learned
KB, which isolates the defect from every other change.

  no movement anywhere -> the defect is real and inconsequential to the tables
  movement             -> Table 13 moves, and only upward for ConGen (QuAcq has no NE,
                          so the comparison was biased against ConGen, not for it)

Reconstruction of kb_clauses from kb_constraints is CONTROLLED: the with-NE metrics
must reproduce the accuracy the fold recorded, or the fold is reported as a mismatch
and nothing is claimed from it.

    measure_ne_accuracy_effect.py --cv-dir <scratch>/ne_split
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder  # noqa: E402
from conacq.eval import apply_folds, load_folds                              # noqa: E402
from conacq.eval.accuracy import AccuracyCalculator                          # noqa: E402
from conacq.examples import ExampleIO                                        # noqa: E402
from conacq.oracle import FMOracle                                           # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']


def stem_of(name: str):
    for s in STEMS:
        if name.startswith(s + '_'):
            return s
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dir', required=True,
                    help="directory holding <model>/congen/<model>_cv_incremental.json")
    args = ap.parse_args()

    files = sorted(Path(args.cv_dir).glob('*/congen/*_cv_*.json'))
    if not files:
        print(f"no CV files under {args.cv_dir}", file=sys.stderr)
        return 1

    rows, mismatches = [], []
    by_stem = {}
    for cv in files:
        model = cv.name.split('_cv_')[0]
        by_stem.setdefault(stem_of(model), []).append((model, cv))

    print(f"{'fold':<28}{'E-tr':>5}{'E-te':>6}{'FP no-NE':>10}{'FP +NE':>8}"
          f"{'acc no-NE':>11}{'acc +NE':>10}{'control':>9}")
    for stem, entries in by_stem.items():
        if stem is None:
            continue
        oracle = FMOracle(str(REPO / 'data' / 'fms' / f'{stem}.uvl'),
                          use_incremental=False)
        try:
            model_kb = (ConGenModelBuilder
                        .from_bias(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
                        .with_oracle_data(oracle.oracle_data).build())
            for model, cv in entries:
                ex = ExampleIO.load_json(
                    str(REPO / 'data' / 'examples' / f'{model}.json'))
                pos = [e.assignments for e in ex.positive]
                neg = [e.assignments for e in ex.negative]
                fd = load_folds(str(REPO / 'data' / 'folds' / f'{model}_folds.json'))
                for fold in json.loads(cv.read_text())['folds']:
                    i = fold['fold_index']
                    _, _, test_pos, test_neg = apply_folds(fd, pos, neg, i)
                    # kb_constraints is a list of ids, or of {'id', 'description'}
                    # dicts depending on the writer — accept both.
                    ids = [c['id'] if isinstance(c, dict) else c
                           for c in fold['kb_constraints']]
                    kb = [list(c) for cid in ids
                          for c in model_kb.constraint_map.get(cid, ())]
                    bg = [list(c) for c in fold['bg_clauses']]
                    ne = [list(c) for c in fold.get('ne_clauses', [])]

                    with AccuracyCalculator(kb + bg, model_kb.name_to_id,
                                            'glucose4') as a:
                        m0 = a.calculate(test_pos, test_neg).metrics
                    with AccuracyCalculator(kb + ne + bg, model_kb.name_to_id,
                                            'glucose4') as a:
                        m1 = a.calculate(test_pos, test_neg).metrics

                    ok = abs(m1.accuracy - fold['accuracy']) < 1e-9
                    if not ok:
                        mismatches.append(f"{model} fold{i}: rebuilt {m1.accuracy:.6f} "
                                          f"vs recorded {fold['accuracy']:.6f}")
                    rows.append({'model': model, 'fold': i,
                                 'fp_no_ne': m0.false_positives,
                                 'fp_ne': m1.false_positives,
                                 'acc_no_ne': m0.accuracy, 'acc_ne': m1.accuracy,
                                 'control_ok': ok})
                    print(f"{model + ' f' + str(i):<28}"
                          f"{fold['train_size']['negative']:>5}{len(test_neg):>6}"
                          f"{m0.false_positives:>10}{m1.false_positives:>8}"
                          f"{m0.accuracy:>11.4f}{m1.accuracy:>10.4f}"
                          f"{'ok' if ok else 'MISMATCH':>9}", flush=True)
        finally:
            oracle.cleanup()

    moved = [r for r in rows if r['control_ok'] and r['fp_no_ne'] != r['fp_ne']]
    print(f"\nfolds measured: {len(rows)}   control failures: "
          f"{sum(1 for r in rows if not r['control_ok'])}")
    print(f"folds whose TEST-fold FP moves when the ¬e⁻ clauses are real: {len(moved)}")
    for r in moved:
        print(f"  {r['model']} fold{r['fold']}: FP {r['fp_no_ne']} -> {r['fp_ne']}, "
              f"accuracy {r['acc_no_ne']:.4f} -> {r['acc_ne']:.4f}")
    if mismatches:
        print(f"\nCONTROL FAILED on {len(mismatches)} fold(s) — "
              f"kb_clauses reconstruction does not reproduce the recorded accuracy:")
        for m in mismatches[:10]:
            print(f"  {m}")
        return 1
    Path(args.cv_dir, 'ne-accuracy-effect.json').write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

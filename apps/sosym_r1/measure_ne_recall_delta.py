#!/usr/bin/env python
"""How much do the tiers understate recall by excluding the memorized ¬e⁻?

The three tiers score against the bias vocabulary, and a ¬e⁻ has no bias id, so it is
excluded by the guard in kb_comparator. That is deliberate — the tiers measure what was
LEARNED — but it means reported recall is a lower bound on what the DELIVERED theory
entails, since the theory is B' u NE. The bound has never been quantified, so "lower
bound" reads as a hedge rather than an interval.

This measures the gap: semantic precision and recall over the same folds, scored from
the bias constraints alone (what the tables report) and from the delivered theory
(bias + ¬e⁻ + root). The recall difference is the width of the interval.

    measure_ne_recall_delta.py --cv-dirs <d1> [<d2> ...]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder  # noqa: E402
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker       # noqa: E402
from conacq.oracle import FMOracle                                            # noqa: E402
from conacq.oracle.ground_truth import GroundTruthData                        # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']


def stem_of(n):
    for s in STEMS:
        if n.startswith(s + '_'):
            return s
    return None


def pr(kb, ct, bg):
    r = SemanticEquivalenceChecker(kb_clauses=kb, ct_clauses=ct,
                                   bg_clauses=bg).check_equivalence()
    tp = r.n_ct_checked - len(r.unentailed_ct)
    fn, fp = len(r.unentailed_ct), len(r.unentailed_kb)
    return (tp / (tp + fp) if tp + fp else 0.0,
            tp / (tp + fn) if tp + fn else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dirs', nargs='+', required=True)
    args = ap.parse_args()

    files = []
    for d in args.cv_dirs:
        files += sorted(Path(d).rglob('*_cv_*.json'))
    by_stem = {}
    for cv in files:
        by_stem.setdefault(stem_of(cv.name.split('_cv_')[0]), []).append(cv)

    rows = []
    print(f"{'fold':<28}{'|NE|':>5}{'R bias':>9}{'R +NE':>9}{'dR':>9}"
          f"{'P bias':>9}{'P +NE':>9}{'dP':>9}")
    for stem, cvs in by_stem.items():
        if stem is None:
            continue
        ct = [list(c) for c in
              GroundTruthData.from_uvl(REPO / 'data' / 'fms' / f'{stem}.uvl').clauses]
        oracle = FMOracle(str(REPO / 'data' / 'fms' / f'{stem}.uvl'),
                          use_incremental=False)
        try:
            m = (ConGenModelBuilder
                 .from_bias(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
                 .with_oracle_data(oracle.oracle_data).build())
            for cv in cvs:
                name = cv.name.split('_cv_')[0]
                for fold in json.loads(cv.read_text())['folds']:
                    ids = [c['id'] if isinstance(c, dict) else c
                           for c in fold['kb_constraints']]
                    kb = [list(c) for cid in ids
                          for c in m.constraint_map.get(cid, ())]
                    ne = [list(c) for c in fold.get('ne_clauses', [])]
                    bg = [list(c) for c in fold['bg_clauses']]
                    p0, r0 = pr(kb, ct, bg)
                    p1, r1 = pr(kb + ne, ct, bg)
                    rows.append({'model': name, 'fold': fold['fold_index'],
                                 'n_ne': len(ne), 'p_bias': p0, 'r_bias': r0,
                                 'p_full': p1, 'r_full': r1})
                    print(f"{name + ' f' + str(fold['fold_index']):<28}{len(ne):>5}"
                          f"{r0:>9.4f}{r1:>9.4f}{r1 - r0:>+9.4f}"
                          f"{p0:>9.4f}{p1:>9.4f}{p1 - p0:>+9.4f}", flush=True)
        finally:
            oracle.cleanup()

    with_ne = [x for x in rows if x['n_ne'] > 0]
    dr = [x['r_full'] - x['r_bias'] for x in with_ne]
    dp = [x['p_full'] - x['p_bias'] for x in with_ne]
    print(f"\nfolds: {len(rows)}   of which deliver at least one ¬e⁻: {len(with_ne)}")
    if dr:
        print(f"recall    delta  mean {statistics.mean(dr):+.4f}  "
              f"max {max(dr):+.4f}  min {min(dr):+.4f}  "
              f"folds that move: {sum(1 for x in dr if abs(x) > 1e-12)}")
        print(f"precision delta  mean {statistics.mean(dp):+.4f}  "
              f"max {max(dp):+.4f}  min {min(dp):+.4f}  "
              f"folds that move: {sum(1 for x in dp if abs(x) > 1e-12)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

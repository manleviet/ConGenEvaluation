#!/usr/bin/env python
"""A5: is the delivered theory exactly equivalent to the target feature model?

Algorithm 3 delivers KB <- B' u NE, so the theory under test is the learned bias
constraints PLUS the memorized ¬e⁻ clauses PLUS the root axiom -- not the bias
constraints alone. ne_clauses now reach the CV fold dict, so this reads the delivered
theory straight out of the artefact instead of reconstructing it.

A 0/N result is only meaningful because the scorer is known to be able to return 1:
tests/test_semantic_scorer_positive_control.py feeds Cτ back as the learned theory and
requires a perfect score, then perturbs it and requires an imperfect one. Without that,
a scorer that could never return 1 would produce exactly this table.

    measure_exact_equivalence.py --cv-dir <scratch>/ne_split2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder  # noqa: E402
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker       # noqa: E402
from conacq.oracle import FMOracle                                            # noqa: E402
from conacq.oracle.ground_truth import GroundTruthData                        # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']


def stem_of(name):
    for s in STEMS:
        if name.startswith(s + '_'):
            return s
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dir', required=True)
    args = ap.parse_args()

    files = sorted(Path(args.cv_dir).rglob('*_cv_*.json'))
    by_stem = {}
    for cv in files:
        model = cv.name.split('_cv_')[0]
        by_stem.setdefault(stem_of(model), []).append((model, cv))

    rows = []
    print(f"{'fold':<26}{'|KB|':>6}{'|NE|':>6}{'unent Cτ':>10}{'unent KB':>10}"
          f"{'equivalent':>12}")
    for stem, entries in by_stem.items():
        if stem is None:
            continue
        ct = [list(c) for c in
              GroundTruthData.from_uvl(REPO / 'data' / 'fms' / f'{stem}.uvl').clauses]
        oracle = FMOracle(str(REPO / 'data' / 'fms' / f'{stem}.uvl'),
                          use_incremental=False)
        try:
            model_kb = (ConGenModelBuilder
                        .from_bias(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
                        .with_oracle_data(oracle.oracle_data).build())
            for model, cv in entries:
                for fold in json.loads(cv.read_text())['folds']:
                    ids = [c['id'] if isinstance(c, dict) else c
                           for c in fold['kb_constraints']]
                    kb = [list(c) for cid in ids
                          for c in model_kb.constraint_map.get(cid, ())]
                    ne = [list(c) for c in fold.get('ne_clauses', [])]
                    bg = [list(c) for c in fold['bg_clauses']]
                    res = SemanticEquivalenceChecker(
                        kb_clauses=kb + ne, ct_clauses=ct,
                        bg_clauses=bg).check_equivalence()
                    rows.append({'model': model, 'fold': fold['fold_index'],
                                 'equivalent': bool(res.is_equivalent),
                                 'unentailed_ct': len(res.unentailed_ct),
                                 'unentailed_kb': len(res.unentailed_kb)})
                    print(f"{model + ' f' + str(fold['fold_index']):<26}"
                          f"{len(kb):>6}{len(ne):>6}{len(res.unentailed_ct):>10}"
                          f"{len(res.unentailed_kb):>10}"
                          f"{str(res.is_equivalent):>12}", flush=True)
        finally:
            oracle.cleanup()

    eq = sum(1 for r in rows if r['equivalent'])
    print(f"\nexactly equivalent: {eq} / {len(rows)} folds")
    if eq:
        for r in rows:
            if r['equivalent']:
                print(f"  {r['model']} fold{r['fold']}")
    Path(args.cv_dir, 'exact-equivalence.json').write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python
"""Score ConGen folds WITH their retained ¬e⁻ in the learned theory (report only).

The tables score the bias KB alone (kb_comparator: a ¬e⁻ has no bias id, so every
strategy skips it -- manuscript 6.2.5). Under the reduced encoding that removes a unit
fact such as NOT(jplug = false) AND every bias constraint Reduce dropped because that
fact entails it, so the scored theory is weaker than the delivered one. This scores the
delivered learned theory instead, with the same three strategies and the same target,
and changes no table generator.

  semantic     SemanticEquivalenceChecker, kb = bias clauses + ¬e⁻ clauses, bg = root:
               exactly _compare_by_semantic with the ¬e⁻ appended.
  clause       compute_metrics over bias clause tuples + root + ¬e⁻ tuples: exactly
               _compare_by_clause with the ¬e⁻ appended.
  description  the scorer matches by bias description, and a ¬e⁻ has none, so as the
               scorer stands it is skipped and the score cannot move. Reported twice:
               as scored (= excluded), and FORCED, i.e. its "NOT(f = false)" string added
               to the acquired set -- whether that string ever equals a target
               description is counted, not assumed.

CONTROL: the excluded variant is recomputed by the same code and must equal the fold's
stored evaluation.<tier>.metrics, or the fold is reported and nothing is claimed.

    score_with_retained_ne.py --cv-dir data/results_sosym_r1/congen --json <out>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.bias import BiasIO                                               # noqa: E402
from conacq.eval.metrics import EvaluationMetrics, compute_metrics           # noqa: E402
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker     # noqa: E402
from conacq.oracle.ground_truth import GroundTruthData                       # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']
TIERS = ('semantic', 'clause', 'description')


def prf(m: EvaluationMetrics) -> dict:
    return {'precision': m.precision, 'recall': m.recall, 'f1_score': m.f1_score}


def score(fold: dict, gt: GroundTruthData, bias, with_ne: bool) -> dict:
    kb_ids = [c['id'] if isinstance(c, dict) else c for c in fold['kb_constraints']]
    kb_ids = [c for c in kb_ids if bias.has_constraint(c)]
    ne = [list(c) for c in fold['ne_clauses']] if with_ne else []
    bg = [list(c) for c in fold['bg_clauses']]

    kb_clauses = [list(cl) for c in kb_ids for cl in bias.get_clauses(c)] + ne
    r = SemanticEquivalenceChecker(kb_clauses=kb_clauses, ct_clauses=[list(c) for c in gt.clauses],
                                   bg_clauses=bg).check_equivalence()
    sem = EvaluationMetrics(true_positives=r.n_ct_checked - len(r.unentailed_ct),
                            false_negatives=len(r.unentailed_ct),
                            false_positives=len(r.unentailed_kb), true_negatives=0)

    kb_set = {tuple(sorted(cl)) for cl in kb_clauses} | {tuple(sorted(c)) for c in bg}
    cla = compute_metrics(kb_set, gt.clause_set, bias.get_all_clause_tuples())

    acquired = {bias.get_description(c) for c in kb_ids}
    ne_names = set(fold.get('ne_constraints') or []) if with_ne else set()
    forced = acquired | ne_names
    des = EvaluationMetrics(true_positives=len(acquired & gt.descriptions),
                            false_positives=len(acquired - gt.descriptions),
                            false_negatives=len(gt.descriptions - acquired), true_negatives=0)
    des_forced = EvaluationMetrics(true_positives=len(forced & gt.descriptions),
                                   false_positives=len(forced - gt.descriptions),
                                   false_negatives=len(gt.descriptions - forced),
                                   true_negatives=0)
    return {'semantic': prf(sem), 'clause': prf(cla), 'description': prf(des),
            'description_forced': prf(des_forced),
            'ne_desc_matches_target': sorted(ne_names & gt.descriptions)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dir', required=True)
    ap.add_argument('--json', required=True)
    args = ap.parse_args()

    rows, mismatches = [], []
    cache: dict = {}
    for cv in sorted(Path(args.cv_dir).glob('*_cv_incremental.json')):
        model = cv.name.split('_cv_')[0]
        stem = next(s for s in STEMS if model.startswith(s + '_'))
        if stem not in cache:
            cache[stem] = (GroundTruthData.from_uvl(REPO / 'data/fms' / f'{stem}.uvl'),
                           BiasIO.load_from_json(str(REPO / 'data/bias' / f'{stem}-bias.json')))
        gt, bias = cache[stem]
        for f in json.loads(cv.read_text())['folds']:
            excl, incl = score(f, gt, bias, False), score(f, gt, bias, True)
            for tier in TIERS:
                stored = f['evaluation'][tier]['metrics']
                if any(abs(stored[k] - excl[tier][k]) > 1e-12 for k in excl[tier]):
                    mismatches.append(f'{model} f{f["fold_index"]} {tier}')
            rows.append({'model': model, 'fold': f['fold_index'],
                         'n_ne': f['statistics']['n_ne'], 'excluded': excl, 'included': incl})
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(rows, indent=1))
    matched = sum(1 for r in rows if r['included']['ne_desc_matches_target'])
    print(f'folds {len(rows)}   control mismatches {len(mismatches)}   '
          f'folds where a ¬e⁻ description equals a target description: {matched}')
    for m in mismatches[:10]:
        print('  MISMATCH', m)
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main())

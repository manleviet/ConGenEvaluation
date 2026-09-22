#!/usr/bin/env python
"""How much does Reduce's input order change the SCORE, per tier?

Reduce is greedy: it walks the KB once and drops what the rest entails, so the
surviving set depends on the order it walks. The survivor SIZE is stable; membership is
not. The question that matters for the paper is whether that instability reaches the
reported metrics, and whether it reaches all three tiers equally.

Cheap, because no acquisition is re-run. B' is recoverable from a scored fold as
kb_constraints u redundant_constraints (gated here against n_mss, and verified to hold
on 72/72 folds), and one Reduce pass is ~150 ms. The only real cost is preparing each
fold's task once to get assumption ids and a checker.

  - Permutes B' ONLY. The memorized ¬e⁻ stay first, as the shipped code assembles
    them: permuting those would measure something the shipped code does not do.
  - Scores all three tiers, precision and recall separately.
  - Reports mean +/- sd alongside min-max, and the description:semantic spread ratio
    per cell -- that ratio is the finding, not the absolute spreads.
  - Locates the shipped run inside each spread, so a reader can see whether the
    published number is typical or lucky.

    measure_reduce_order_sensitivity.py --cv-dirs <d1> <d2> --perms 20 --out <file>
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder   # noqa: E402
from conacq.algorithms.acqmss.reduce import Reduce                             # noqa: E402
from conacq.algorithms.acqmss.task_preparation import (                        # noqa: E402
    ConGenTaskInput, ConGenTaskPreparation)
from conacq.bias import BiasIO                                                 # noqa: E402
from conacq.eval import apply_folds, load_folds                                # noqa: E402
from conacq.eval.kb_comparator import ComparationStrategy, KBComparator        # noqa: E402
from conacq.eval.result_loader import ConGenResultData                         # noqa: E402
from conacq.examples import ExampleIO                                          # noqa: E402
from conacq.oracle import FMOracle                                             # noqa: E402
from conacq.oracle.ground_truth import GroundTruthData                         # noqa: E402
from explanation.api import SolverBackend, build_checker                       # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']
TIERS = ('description', 'clause', 'semantic')


def stem_of(name):
    for s in STEMS:
        if name.startswith(s + '_'):
            return s
    return None


def ids_of(entry_list):
    return [c['id'] if isinstance(c, dict) else c for c in entry_list]


def score(names, fold, comparator):
    """P and R per tier for one survivor set, through the same comparator the tables use."""
    data = ConGenResultData.from_dict({
        'kb_constraints': list(names),
        'redundant_constraints': [],
        'statistics': {'n_bias': fold['statistics']['n_bias'],
                       'n_mss': fold['statistics']['n_mss'],
                       'n_kb': len(names)},
        'bg_clauses': fold['bg_clauses'],
    })
    out = {}
    for tier in TIERS:
        m = comparator.compare(data, ComparationStrategy(tier)).metrics
        out[tier] = (m.precision, m.recall)
    return out


def run_cell(cv_path, model_kb, comparator, oracle, n_perms):
    model_name = cv_path.name.split('_cv_')[0]
    ex = ExampleIO.load_json(str(REPO / 'data' / 'examples' / f'{model_name}.json'))
    pos = [e.assignments for e in ex.positive]
    neg = [e.assignments for e in ex.negative]
    fd = load_folds(str(REPO / 'data' / 'folds' / f'{model_name}_folds.json'))
    rows = []

    for fold in json.loads(cv_path.read_text())['folds']:
        idx = fold['fold_index']
        bprime_names = list(dict.fromkeys(
            ids_of(fold['kb_constraints']) + ids_of(fold['redundant_constraints'])))
        if len(bprime_names) != fold['statistics']['n_mss']:
            print(f"  SKIP {model_name} f{idx}: recovered B' is {len(bprime_names)}, "
                  f"n_mss is {fold['statistics']['n_mss']}")
            continue

        train_pos, train_neg, _, _ = apply_folds(fd, pos, neg, idx)
        seed = fd.shuffle_seeds[idx]
        r = random.Random(seed)
        r.shuffle(train_pos)
        r.shuffle(train_neg)
        prepared = ConGenTaskPreparation().prepare(
            model_kb, ConGenTaskInput.from_examples(oracle.oracle_data,
                                                    train_pos, train_neg))
        task, describe = prepared.task, prepared.describe
        sc = list(task.set_c)
        random.Random(seed).shuffle(sc)
        task = replace(task, set_c=sc)

        name_to_aid = {}
        for aid in task.set_c:
            name_to_aid.setdefault(describe.get_description(aid), aid)
        aid_to_name = {v: k for k, v in name_to_aid.items()}
        bprime = [name_to_aid[n] for n in bprime_names if n in name_to_aid]
        if len(bprime) != len(bprime_names):
            print(f"  SKIP {model_name} f{idx}: {len(bprime_names) - len(bprime)} "
                  f"of B' did not map to an assumption id")
            continue

        checker = build_checker(task, SolverBackend.from_flags(use_incremental=True),
                                'glucose4')
        try:
            reducer = Reduce(checker)
            per_perm = []
            for p in range(n_perms):
                order = list(bprime)
                random.Random(1000 * idx + p).shuffle(order)
                _, kb = reducer.reduce(order, list(task.set_neg_tv),
                                       list(task.set_b), task.negation_map)
                names = [aid_to_name[a] for a in kb if a in aid_to_name]
                per_perm.append(score(names, fold, comparator))
            shipped = score(ids_of(fold['kb_constraints']), fold, comparator)
        finally:
            checker.cleanup()

        rows.append({'model': model_name, 'fold': idx, 'n_perms': n_perms,
                     'perms': per_perm, 'shipped': shipped,
                     'n_bprime': len(bprime)})
        print(f"  {model_name} f{idx}: |B'|={len(bprime)}, {n_perms} permutations",
              flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dirs', nargs='+', required=True)
    ap.add_argument('--perms', type=int, default=20)
    ap.add_argument('--cells', nargs='+',
                    help="restrict to these model names, e.g. fqa_rs_2n")
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    files = []
    for d in args.cv_dirs:
        files += sorted(Path(d).rglob('*_cv_*.json'))
    by_stem = {}
    for cv in files:
        model = cv.name.split('_cv_')[0]
        if args.cells and model not in args.cells:
            continue
        by_stem.setdefault(stem_of(model), []).append(cv)

    rows = []
    for stem, cvs in by_stem.items():
        if stem is None:
            continue
        print(f"{stem}: {len(cvs)} cell(s)", flush=True)
        oracle = FMOracle(str(REPO / 'data' / 'fms' / f'{stem}.uvl'),
                          use_incremental=False)
        try:
            model_kb = (ConGenModelBuilder
                        .from_bias(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
                        .with_oracle_data(oracle.oracle_data).build())
            comparator = KBComparator(
                GroundTruthData.from_uvl(REPO / 'data' / 'fms' / f'{stem}.uvl'),
                BiasIO.load_from_json(str(REPO / 'data' / 'bias' / f'{stem}-bias.json')))
            for cv in cvs:
                rows += run_cell(cv, model_kb, comparator, oracle, args.perms)
        finally:
            oracle.cleanup()

    Path(args.out).write_text(json.dumps(rows, indent=2))
    report(rows)
    return 0


def report(rows):
    print(f"\n=== spread of the SCORE over Reduce input order "
          f"({len(rows)} folds, {rows[0]['n_perms'] if rows else 0} permutations each) ===")
    print(f"{'cell':<26}{'tier':<13}{'metric':<4}{'mean':>9}{'sd':>8}"
          f"{'min':>9}{'max':>9}{'range':>8}{'shipped':>9}{'pctile':>8}")
    ratios = []
    for r in rows:
        cell = f"{r['model']} f{r['fold']}"
        spread = {}
        for tier in TIERS:
            for i, met in enumerate(('P', 'R')):
                vals = [p[tier][i] for p in r['perms']]
                lo, hi = min(vals), max(vals)
                ship = r['shipped'][tier][i]
                below = sum(1 for v in vals if v < ship) / len(vals)
                print(f"{cell:<26}{tier:<13}{met:<4}{statistics.mean(vals):>9.4f}"
                      f"{(statistics.pstdev(vals) if len(vals) > 1 else 0.0):>8.4f}"
                      f"{lo:>9.4f}{hi:>9.4f}{hi - lo:>8.4f}{ship:>9.4f}"
                      f"{below:>8.2f}")
                spread.setdefault(tier, []).append(hi - lo)
        d, s = max(spread['description']), max(spread['semantic'])
        ratios.append((cell, d, s, (d / s) if s > 0 else float('inf')))
    print(f"\n=== description : semantic spread ratio (the finding) ===")
    print(f"{'cell':<26}{'desc range':>12}{'sem range':>12}{'ratio':>10}")
    for cell, d, s, ratio in ratios:
        print(f"{cell:<26}{d:>12.4f}{s:>12.4f}"
              f"{('inf' if ratio == float('inf') else f'{ratio:.1f}x'):>10}")
    finite = [x[3] for x in ratios if x[3] != float('inf')]
    inf_n = sum(1 for x in ratios if x[3] == float('inf'))
    if finite:
        print(f"\nfinite ratios: n={len(finite)} median {statistics.median(finite):.1f}x "
              f"range {min(finite):.1f}x-{max(finite):.1f}x"
              f"{f'; {inf_n} cells had ZERO semantic spread' if inf_n else ''}")


if __name__ == '__main__':
    sys.exit(main())

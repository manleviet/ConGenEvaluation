#!/usr/bin/env python
"""Score B' (the MSS before Reduce) as the theory CABSC would return.

    PYTHONPATH=. python3 apps/sosym_r1/measure_mss_as_cabsc_condition.py \
        --cv-dir data/results_sosym_r1/congen --out data/results_sosym_r1/cabsc_condition/cabsc_condition.json

WHY B' IS THE CABSC CONDITION
-----------------------------
CABSC returns, among all models that accept every positive example, the one admitting
the fewest solutions. Proposition 1 of the manuscript proves that under a bias of
unparameterised constraints that combine freely, that objective is met by the
conjunction of EVERY bias constraint consistent with the positive examples -- call it
A -- and the manuscript identifies A with what AcqMss returns for complete positive
examples. AcqMss returns B', the maximal satisfiable subset, before Reduce makes it
irredundant. So scoring B' evaluates CABSC on this benchmark instead of excusing it.

TWO MEASUREMENTS, TWO PREDICTIONS, BOTH WRITTEN TO BE FALSIFIED
---------------------------------------------------------------
1. B' scored beside the delivered KB, per fold, through the SAME comparator the paper's
   tables use.

   Prediction: Reduce drops c exactly when BG u (KB - {c}) |= c, which preserves logical
   equivalence, so KB u NE u BG and B' u NE u BG must accept the same configurations on
   EVERY fold -- and on a fold whose training split has no negative example NE is empty,
   which makes that the plain statement "the delivered theory is equivalent to B'".
   Measured directly below (``equivalent_to_kb``) rather than inferred from a score.

   The score half of that prediction is WRONG, and the measurement says so: semantic
   RECALL is preserved by equivalence and semantic PRECISION is not. Precision counts
   the delivered CLAUSES that the target entails, so a redundant clause the target does
   not entail still counts against it. Equivalence therefore pins recall exactly and
   leaves precision free to move, which is the whole difference between B' and KB.

2. A recomputed from the bias and the training positives, compared with B'.

   A is defined by E+ alone; AcqMss keeps what is consistent with {e+} u NE u BG. That
   gives B' subseteq A, with equality only if no bias constraint was excluded because of
   NE. The manuscript asserts equality. Nothing had measured it.

   A is computed WITHOUT a solver: every example in this evaluation is a COMPLETE
   assignment (asserted below), so "c accepts e+" is the evaluation of c's clauses under
   that assignment, not a satisfiability question. A solver here would add a dependency
   and an approximation where arithmetic is exact.

Both halves of the comparison are bias-derived sets: run_compare.py scores
fold['kb_constraints'] and never the memorized not-e-, and B' is bias constraints only
(`redundant_ne_constraints` is a separate field and is not read here).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.bias import BiasIO                                              # noqa: E402
from conacq.eval import apply_folds, load_folds                             # noqa: E402
from conacq.eval.kb_comparator import ComparationStrategy, KBComparator     # noqa: E402
from conacq.eval.result_loader import ConGenResultData                      # noqa: E402
from conacq.examples import ExampleIO                                       # noqa: E402
from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker     # noqa: E402
from conacq.oracle.ground_truth import GroundTruthData                      # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']
TIERS = ('description', 'clause', 'semantic')


def stem_of(name: str) -> str | None:
    return next((s for s in STEMS if name.startswith(s + '_')), None)


def ids_of(entries) -> list:
    return [c['id'] if isinstance(c, dict) else c for c in entries]


def f1(precision: float, recall: float) -> float:
    return 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)


def score(names, fold, comparator) -> dict:
    """P and R per tier for one constraint set, through the comparator the tables use."""
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


def accepts(clauses, assignment: dict) -> bool:
    """Does a complete assignment satisfy every clause of one constraint?

    ``assignment`` maps a variable id to a bool. Exact because the assignment is
    complete: a clause is satisfied iff one of its literals is.
    """
    return all(any((lit > 0) == assignment[abs(lit)] for lit in clause)
               for clause in clauses)


def admissible_set(bias, var_of: dict, positives: list) -> list:
    """A = {c in B : c accepts every positive example}, the CABSC theory of Prop. 1."""
    # Translate each example once: the inner loop runs |B| x |E+| times, which is
    # 6,635 x 569 on the largest cell.
    assignments = [{var_of[name]: value for name, value in e.items()} for e in positives]
    return [c.id for c in bias.constraints
            if all(accepts(c.clauses, a) for a in assignments)]


def clauses_of(bias, names) -> list:
    return [list(c) for cid in names if bias.has_constraint(cid)
            for c in bias.get_clauses(cid)]


def theories_equivalent(bias, bprime, kb_names, fold) -> dict:
    """Do B' and the delivered KB accept the same configurations, under NE and BG?

    Two forms, because they are not the same predicate and the paper quotes one of them.

    ``given_bg_and_ne`` is Section 5.5.4's sentence, literally: BG and NE sit on BOTH
    sides, so this is mutual entailment between (B' u NE u BG) and (KB u NE u BG). They
    are passed inside the two clause lists rather than through ``bg_clauses`` because
    ``SemanticEquivalenceChecker`` adds ``bg_clauses`` to the source of ONE direction
    only -- symmetric here means putting them in both.

    ``bg_on_the_left_only`` is the asymmetric form that ``bg_clauses`` gives by default:
    direction 2 must entail B' from KB u NE with no BG to help. Fewer premises, so it is
    a STRICTLY STRONGER claim; it is kept because it also held, and because a reader
    comparing this file with the checker's defaults would otherwise wonder which ran.

    Whole-theory, not per-constraint: entailing every clause of a set is entailing its
    conjunction, so each direction is one theory entailing the other.
    """
    ne = [list(c) for c in (fold.get('ne_clauses') or [])]
    bg = [list(c) for c in (fold.get('bg_clauses') or [])]
    left, right = clauses_of(bias, bprime) + ne, clauses_of(bias, kb_names) + ne
    return {
        'given_bg_and_ne': bool(SemanticEquivalenceChecker(
            kb_clauses=left + bg, ct_clauses=right + bg,
            bg_clauses=[]).check_equivalence().is_equivalent),
        'bg_on_the_left_only': bool(SemanticEquivalenceChecker(
            kb_clauses=left, ct_clauses=right,
            bg_clauses=bg).check_equivalence().is_equivalent),
    }


def run_cell(cv_path: Path, bias, comparator) -> list:
    model_name = cv_path.name.split('_cv_')[0]
    ex = ExampleIO.load_json(str(REPO / 'data' / 'examples' / f'{model_name}.json'))
    pos = [e.assignments for e in ex.positive]
    neg = [e.assignments for e in ex.negative]
    folds = load_folds(str(REPO / 'data' / 'folds' / f'{model_name}_folds.json'))
    var_of = {f.name: f.id for f in bias.features}

    # The premise of Proposition 1, asserted rather than assumed: every example is a
    # COMPLETE assignment. Without it "c accepts e+" is a satisfiability question and
    # the clause evaluation below would be the wrong instrument.
    incomplete = [i for i, e in enumerate(pos + neg) if len(e) != len(var_of)]
    if incomplete:
        raise ValueError(f'{model_name}: {len(incomplete)} example(s) are not complete '
                         f'assignments; A cannot be computed by evaluation')

    rows = []
    for fold in json.loads(cv_path.read_text())['folds']:
        idx = fold['fold_index']
        kb_names = ids_of(fold['kb_constraints'])
        bprime = list(dict.fromkeys(kb_names + ids_of(fold['redundant_constraints'])))
        if len(bprime) != fold['statistics']['n_mss']:
            raise ValueError(f"{model_name} f{idx}: recovered B' is {len(bprime)}, "
                             f"n_mss is {fold['statistics']['n_mss']}")

        train_pos, _train_neg, _, _ = apply_folds(folds, pos, neg, idx)
        a_set = admissible_set(bias, var_of, train_pos)
        equivalent = theories_equivalent(bias, bprime, kb_names, fold)

        rows.append({
            'model': model_name, 'fold': idx,
            'n_ne': len(fold.get('ne_constraints') or []),
            'n_train_pos': len(train_pos),
            'n_bias': fold['statistics']['n_bias'],
            'n_kb': len(kb_names), 'n_bprime': len(bprime), 'n_a': len(a_set),
            # Task 2: A superset-equal B' by construction; the question is whether the
            # inclusion is strict, and on which constraints.
            'a_minus_bprime': sorted(set(a_set) - set(bprime)),
            'bprime_minus_a': sorted(set(bprime) - set(a_set)),
            # Task 1's prediction, decided directly: does Reduce preserve the theory?
            'equivalent_to_kb': equivalent,
            'kb': score(kb_names, fold, comparator),
            'bprime': score(bprime, fold, comparator),
        })
        print(f"  {model_name} f{idx}: |KB|={len(kb_names)} |B'|={len(bprime)} "
              f"|A|={len(a_set)} NE={rows[-1]['n_ne']}", flush=True)
    return rows


def summarize(rows: list) -> dict:
    """The two predictions, decided on the rows rather than argued."""
    no_ne = [r for r in rows if r['n_ne'] == 0]
    recall_moved = [r for r in rows if r['kb']['semantic'][1] != r['bprime']['semantic'][1]]
    precision_moved = [r for r in rows if r['kb']['semantic'][0] != r['bprime']['semantic'][0]]
    strict = [r for r in rows if r['a_minus_bprime']]
    reversed_ = [r for r in rows if r['bprime_minus_a']]
    return {
        'folds': len(rows),
        'folds_without_ne': len(no_ne),
        'folds_where_reduce_changed_the_theory':
            sum(1 for r in rows if not r['equivalent_to_kb']['given_bg_and_ne']),
        'folds_where_reduce_changed_the_theory_bg_on_the_left_only':
            sum(1 for r in rows if not r['equivalent_to_kb']['bg_on_the_left_only']),
        'folds_whose_semantic_recall_moved': len(recall_moved),
        'folds_whose_semantic_precision_moved': len(precision_moved),
        'folds_where_A_strictly_contains_Bprime': len(strict),
        'folds_where_Bprime_is_not_contained_in_A': len(reversed_),
        'constraints_in_A_not_in_Bprime': sorted(
            {c for r in strict for c in r['a_minus_bprime']}),
        'semantic_f1_delta_bprime_minus_kb': {
            'median': statistics.median(
                f1(*r['bprime']['semantic']) - f1(*r['kb']['semantic']) for r in rows),
            'max': max(f1(*r['bprime']['semantic']) - f1(*r['kb']['semantic']) for r in rows),
            'min': min(f1(*r['bprime']['semantic']) - f1(*r['kb']['semantic']) for r in rows),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cv-dir', default=str(REPO / 'data' / 'results_sosym_r1' / 'congen'))
    ap.add_argument('--cells', nargs='+', help='restrict to these units, e.g. fqa_rs_2n')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    by_stem: dict = {}
    for cv in sorted(Path(args.cv_dir).rglob('*_cv_*.json')):
        model = cv.name.split('_cv_')[0]
        if args.cells and model not in args.cells:
            continue
        by_stem.setdefault(stem_of(model), []).append(cv)

    rows: list = []
    for stem, cvs in by_stem.items():
        if stem is None:
            continue
        print(f'{stem}: {len(cvs)} cell(s)', flush=True)
        bias = BiasIO.load_from_json(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
        comparator = KBComparator(
            GroundTruthData.from_uvl(REPO / 'data' / 'fms' / f'{stem}.uvl'), bias)
        for cv in cvs:
            rows += run_cell(cv, bias, comparator)

    # A positive count, never the absence of an error: an empty run would otherwise
    # write a tidy summary of nothing and exit 0.
    if not rows:
        print('FAIL: no folds measured', file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        # Provenance in the file, not in a note beside it: a measurement whose inputs
        # are named somewhere else is one nobody can re-run.
        'provenance': {
            'script': 'apps/sosym_r1/measure_mss_as_cabsc_condition.py',
            'source': str(Path(args.cv_dir).relative_to(REPO)),
            'measured': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'cells': sorted({r['model'] for r in rows}),
            'note': "B' = kb_constraints u redundant_constraints; A = bias constraints "
                    "accepting every TRAINING positive; scores through KBComparator, the "
                    "comparator the paper's tables use.",
        },
        'summary': summarize(rows), 'folds': rows}, indent=2))
    print(f'\n{json.dumps(summarize(rows), indent=2)}')
    print(f'\n{len(rows)} folds -> {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

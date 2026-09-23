#!/usr/bin/env python3
"""Two claims the revision added that no cell carries: the order-sensitivity
figures of S6.4, and the arithmetic of the working-example bias in S3.

ORDER SENSITIVITY -- WHY THE EXISTING CHECKS DO NOT COVER THESE
---------------------------------------------------------------
Section 9 of the gate pins the RATIO finding (description spread against semantic
spread) and the two ABSOLUTE MAXIMA over all 84 folds, 0.5182 and 0.8385, as the
measurement script summarises them. The revision quotes three different numbers --
0.004, 0.077 and 0.46 -- because it quotes F1, not precision and recall
separately, and because it excludes a group of folds. Neither the F1 spread nor
the exclusion exists in `order_sensitivity.json`'s summary block, so both are
recomputed here from the per-permutation scores.

THE EXCLUDED GROUP IS DEFINED BY ITS SPREAD, AND ITS MEMBERSHIP IS THE CLAIM
----------------------------------------------------------------------------
Twelve folds move by more than 0.1 semantic F1 across reduction orders. They are
exactly the 2-COV, RS(m) and FF folds of KB1 and KB3 -- the two smallest models
under the three strategies that give them the fewest examples. That membership is
what makes the exclusion principled rather than convenient, so it is asserted
fold by fold, not summarised.

(The draft that fed the revision described these twelve as "the cells with at most
one positive example". They are not, in either direction: seven of the twelve train on
four to seventeen positives, and ten of the fifteen folds that DO train on at most one
move by 0.077 or less -- REAL-FM-4 2-COV fold 0 trains on none and moves by 0.009. The
membership asserted below is the one the data supports.)

THE WORKING EXAMPLE IS ARITHMETIC, NOT DATA
-------------------------------------------
S3 states that the illustrative bias has 3n(n-1) = 18 entries and 2n(n-1) = 12
distinct constraints for n = 3, names the six pairs the commutativity of AND and
NAND makes duplicates, and says the duplicates are what Reduce removes. No code
path in this repository builds that bias: the evaluation generator speaks a
different language (mandatory / optional / alternative / or / requires / excludes)
and cannot express it. What IS checkable without inventing a fixture is the
enumeration itself, re-derived from the rule the table states and compared against
the labels the table prints -- which catches a mis-numbered cell, the failure this
kind of hand-built table actually has. The behavioural half of the claim, that
Reduce drops one member of each pair, is reported as unassertable and is left to
the walkthrough's own figures, whose internal consistency is checked below.
"""
from __future__ import annotations

import itertools
import json
import statistics
from pathlib import Path

# S6.4, the order-sensitivity threat.
DEGENERATE_THRESHOLD = 0.1
PAPER_ORDER_SENSITIVITY = {
    'degenerate_folds': 12,
    'median_semantic_f1_spread': 0.004,
    'max_semantic_f1_spread': 0.077,
    'max_description_f1_spread': 0.46,
}
# ... and the models / strategies those twelve folds belong to.
DEGENERATE_MODELS = {'REAL-FM-7', 'arcade-game'}          # KB1 and KB3
DEGENERATE_STRATEGIES = {'2cov', 'rs_m', 'ff'}

# S6.3 quotes the semantic F1 of 0.660 on KB3 under RS(n); the description-based
# 0.313 beside it is now a Table 12 cell rather than prose. Both are asserted.
PAPER_TIER_EXAMPLE = {'model': 'arcade-game', 'sampling': 'rs_1n',
                      'description': 0.313, 'semantic': 0.660}

# S3: the illustrative vocabulary and language, in the order Table 3 prints them.
WORKING_EXAMPLE_VARIABLES = ('db', 'id', 'ga')
WORKING_EXAMPLE_OPERATORS = ('->', 'and', 'nand')         # commutative: and, nand
# The six duplicate pairs S3 names, and the counts it derives.
PAPER_COMMUTATIVE_PAIRS = ((2, 8), (3, 9), (5, 14), (6, 15), (11, 17), (12, 18))
PAPER_ENTRIES, PAPER_DISTINCT = 18, 12
# fig:mmsgvisualization, the run with background knowledge: AcqMss returns the MSS,
# ConGen returns the theory after Reduce.
PAPER_WALKTHROUGH_MSS = (7, 12, 13, 18)
PAPER_WALKTHROUGH_KB = (7, 12, 13)


ALL_STRATEGIES = ('2cov', 'ff', 'rs_1n', 'rs_2n', 'rs_3n', 'rs_m')


def split_unit(unit: str) -> tuple[str, str]:
    """"arcade-game_rs_m" -> ("arcade-game", "rs_m"). The strategy is a suffix, and
    two of the six contain an underscore, so it cannot be taken off at the last one."""
    for strategy in ALL_STRATEGIES:
        if unit.endswith(f'_{strategy}'):
            return unit[: -len(strategy) - 1], strategy
    raise ValueError(f'no known sampling strategy in {unit!r}')


def f1(precision: float, recall: float) -> float:
    return 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)


def f1_spreads(fold_record: dict) -> dict[str, float]:
    """How far each tier's F1 travels across the 20 reduction orders of one fold."""
    out = {}
    for tier in ('description', 'semantic'):
        scores = [f1(*perm[tier]) for perm in fold_record['perms']]
        out[tier] = max(scores) - min(scores)
    return out


def enumerate_working_example_bias() -> list[tuple[str, str, str]]:
    """Table 3's rule: every ordered pair of distinct variables, every operator.

    Row-major over the ordered pairs, operators in the order the cells print them,
    which is the numbering the walkthrough's figures refer to.
    """
    return [(x, op, y)
            for x, y in itertools.permutations(WORKING_EXAMPLE_VARIABLES, 2)
            for op in WORKING_EXAMPLE_OPERATORS]


def canonical(entry: tuple[str, str, str]) -> tuple:
    """The constraint an entry denotes, with commutativity applied."""
    x, op, y = entry
    return (op, frozenset((x, y))) if op in ('and', 'nand') else (op, x, y)


def run(check, repo: Path) -> None:
    print('\n[order] S6.4: how far the reduction order can move a score (F1, not P and R)')
    data = json.loads((repo / 'data' / 'results_sosym_r1' / 'order_sensitivity'
                       / 'order_sensitivity.json').read_text())
    spreads = [(r['model'], r['fold'], f1_spreads(r)) for r in data['folds']]
    check('folds measured', len(spreads), 84)

    degenerate = [(m, f, s) for m, f, s in spreads if s['semantic'] > DEGENERATE_THRESHOLD]
    check('folds whose semantic F1 moves by more than 0.1',
          len(degenerate), PAPER_ORDER_SENSITIVITY['degenerate_folds'])
    for model, fold, _s in degenerate:
        stem, strategy = split_unit(model)
        check(f'   {model} f{fold} is a 2-COV / RS(m) / FF fold of KB1 or KB3',
              (stem in DEGENERATE_MODELS, strategy in DEGENERATE_STRATEGIES), (True, True))

    rest = [s for _m, _f, s in spreads if s['semantic'] <= DEGENERATE_THRESHOLD]
    check('semantic F1 spread outside those twelve, at the median',
          round(statistics.median(x['semantic'] for x in rest), 3),
          PAPER_ORDER_SENSITIVITY['median_semantic_f1_spread'], tol=1e-9)
    check('semantic F1 spread outside those twelve, at most',
          round(max(x['semantic'] for x in rest), 3),
          PAPER_ORDER_SENSITIVITY['max_semantic_f1_spread'], tol=1e-9)
    check('description F1 spread, at most, over ALL folds',
          round(max(s['description'] for _m, _f, s in spreads), 2),
          PAPER_ORDER_SENSITIVITY['max_description_f1_spread'], tol=1e-9)

    print('\n[order] the tier gap quoted from tab:comparison_strategies')
    folds = json.loads((repo / 'data' / 'results_sosym_r1' / 'congen'
                        / f"{PAPER_TIER_EXAMPLE['model']}_{PAPER_TIER_EXAMPLE['sampling']}"
                          '_cv_incremental.json').read_text())['folds']
    for tier in ('description', 'semantic'):
        mean = statistics.mean(
            fo['evaluation'][tier]['metrics']['f1_score'] for fo in folds)
        check(f'KB3 RS(n): {tier} F1, mean over folds',
              round(mean, 3), PAPER_TIER_EXAMPLE[tier], tol=1e-9)

    print('\n[example] the working-example bias enumerates to 18 entries and 12 constraints')
    entries = enumerate_working_example_bias()
    n = len(WORKING_EXAMPLE_VARIABLES)
    check('entries, and the 3n(n-1) the paper derives', (len(entries), 3 * n * (n - 1)),
          (PAPER_ENTRIES, PAPER_ENTRIES))
    distinct = {canonical(e) for e in entries}
    check('distinct constraints, and the 2n(n-1) the paper derives',
          (len(distinct), 2 * n * (n - 1)), (PAPER_DISTINCT, PAPER_DISTINCT))

    # Which indices collide, derived from the enumeration rather than read off the table.
    by_constraint: dict[tuple, list[int]] = {}
    for i, entry in enumerate(entries, start=1):
        by_constraint.setdefault(canonical(entry), []).append(i)
    derived_pairs = tuple(sorted(tuple(ix) for ix in by_constraint.values() if len(ix) > 1))
    check('the duplicate pairs Table 3 names', derived_pairs,
          tuple(sorted(PAPER_COMMUTATIVE_PAIRS)))

    # The walkthrough: Reduce keeps one member of the one duplicate pair in the MSS.
    mss, kb = set(PAPER_WALKTHROUGH_MSS), set(PAPER_WALKTHROUGH_KB)
    in_mss = [p for p in derived_pairs if set(p) <= mss]
    check('fig:mmsgvisualization: the MSS holds exactly one duplicate pair', len(in_mss), 1)
    check('   ... and the theory after Reduce holds one of its two members',
          [len(set(p) & kb) for p in in_mss], [1])
    check('   ... and what Reduce dropped is exactly the other member',
          sorted(mss - kb), sorted(set(in_mss[0]) - kb) if in_mss else [])
    print('      note: that Reduce is what removes the duplicate is NOT asserted here.')
    print('      No code path builds this bias -- the evaluation generator cannot express')
    print('      its language -- so the claim rests on the walkthrough figures above.')

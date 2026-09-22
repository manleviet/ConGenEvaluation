#!/usr/bin/env python3
"""The bias-composition figures the SoSyM revision added (tab:biasformula, S5.3).

WHAT THE PAPER CLAIMS, AND WHY IT NEEDED A GATE
-----------------------------------------------
The revision introduced a closed form for the size of the evaluation bias,

    |B| = 2 (h_bin + h_grp) + 3 C(k, 2)

and a table of its four inputs for five knowledge bases plus the model the study
could not reach (ea2468). It then states the formula "is exact on all five models".
That sentence is a claim about arithmetic over committed data, and nothing checked
it: the biasformula table is the one table in the paper with no generated fragment
behind it, so `check_paper_tables.py` never sees it.

TWO SOURCES, DELIBERATELY
-------------------------
Every composition figure is derived TWICE, from files that would not move together:

  * `data/bias-config/<model>.yaml`  -- the generator's INPUT. h_bin and h_grp are
    counted from `hierarchical_candidates`, k from the `cross_tree_features` list.
  * `data/bias/<model>-bias-stats.txt` -- the generator's OUTPUT. h_bin is the
    `mandatory` count, h_grp the `alternative` count, and k is recovered from
    `excludes` = C(k,2), one excludes constraint per unordered pair.

A generator defect moves the stats and leaves the config alone, so agreement
between the two is a fact about the pipeline, not a restatement of one file.

THE ea2468 ROW IS NOT A MEASUREMENT OF THIS MACHINE
---------------------------------------------------
Its composition IS committed (`ea2468-bias-stats.txt`, `ea2468.yaml`), and is
asserted here like the others. The 95 s and 46 h feasibility figures beside it are
not: see `revision_ea2468_limit.py`.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import yaml

# tab:biasformula, EXACTLY as the manuscript prints it. Columns:
#   model stem, KB label, n, h_bin, h_grp, k, |B|, reduction as printed.
PAPER_BIAS_TABLE = [
    ('REAL-FM-7',      'KB1',      14,    9,  2,    14,      295, '1.0'),
    # KB2's reduction printed 104 until this gate was written. 104 is what the
    # cross-tree term alone gives (3C(n,2)/|B| = 104.12); the factor the sentence
    # describes, the whole unrestricted bias over the restricted one, is 104.53 and
    # prints as 105. Every other row is identical under both readings, which is why
    # nothing noticed. KB1 is the row that settles which reading is meant: only the
    # whole-bias ratio makes k = n come out at exactly 1.0.
    ('fqa',            'KB2',     179,   57, 36,    14,      459, '105'),
    ('arcade-game',    'KB3',      65,   27,  9,    34,     1755, '3.6'),
    ('REAL-FM-4',      'KB4',     291,  159, 39,    34,     2079, '61'),
    ('busybox-1.18.0', 'KB5',     854,  830,  8,    58,     6635, '165'),
    ('ea2468',         'ea2468', 1408, 1377, 12,  1168,  2047362, '1.5'),
]

# S5.3 prose, "they include both a hierarchy-dominated model (KB5, with 838
# hierarchical and 58 cross-tree candidate features) and a cross-tree-dominated
# one (KB3, with 36 and 34)". Stem -> (hierarchical candidates, k).
PAPER_SELECTION_CRITERIA = {'busybox-1.18.0': (838, 58), 'arcade-game': (36, 34)}


def composition_from_config(path: Path) -> dict:
    """h_bin, h_grp, k and n as the GENERATOR'S INPUT declares them."""
    cfg = yaml.safe_load(path.read_text())
    hier = cfg.get('hierarchical_candidates') or []
    cross = cfg.get('cross_tree_candidates') or {}
    extracted = cross.get('cross_tree_features')
    return {
        'n': len(cfg['features']),
        'h_bin': sum(1 for h in hier if h.get('relationship_type') == 'binary'),
        'h_grp': sum(1 for h in hier if h.get('relationship_type') == 'group'),
        'mode': cross.get('cross_tree_mode'),
        # 'all' admits every feature; 'extracted' admits the listed ones.
        'k': len(extracted) if extracted else len(cfg['features']),
    }


def composition_from_stats(path: Path) -> dict:
    """The same quantities recovered from the BUILT BIAS.

    A binary hierarchical candidate emits one `mandatory` and one `optional`
    constraint, a group candidate one `alternative` and one `or`, and each
    unordered cross-tree pair one `excludes` and two `requires`. Every count is
    therefore a witness for one input of the closed form, and the redundancy
    between the pairs (mandatory vs optional, alternative vs or, excludes vs
    requires) is asserted rather than assumed.
    """
    text = path.read_text()

    def one(pattern: str) -> int:
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            raise ValueError(f'{path.name}: no line matching {pattern!r}')
        return int(m.group(1))

    ops = {op: one(rf'^\s+{op}:\s+(\d+)$')
           for op in ('mandatory', 'optional', 'alternative', 'or', 'excludes', 'requires')}
    # excludes = C(k,2) -> k = (1 + sqrt(1 + 8*excludes)) / 2, exact for a triangular count.
    k = (1 + math.isqrt(1 + 8 * ops['excludes'])) // 2
    return {
        'n': one(r'^Total features:\s+(\d+)$'),
        'bias': one(r'^Total constraints:\s+(\d+)$'),
        'clauses': one(r'^Total clauses:\s+(\d+)$'),
        'h_bin': ops['mandatory'],
        'h_grp': ops['alternative'],
        'k': k,
        'ops': ops,
    }


def closed_form(h_bin: int, h_grp: int, k: int) -> int:
    """|B| = 2 (h_bin + h_grp) + 3 C(k,2), the formula S5.3 states."""
    return 2 * (h_bin + h_grp) + 3 * math.comb(k, 2)


def reduction_against_unrestricted(h_bin: int, h_grp: int, n: int, bias: int) -> float:
    """How much the extracted-pair restriction buys, as the paper defines it.

    The unrestricted language keeps the same hierarchy candidates and pairs every
    two of the n features, so the factor is closed_form(h, h, n) / |B|. The paper
    calls this "about (n/k)^2"; the shorthand drops the hierarchical term and is
    therefore only an approximation of what the column prints (see the report).
    """
    return closed_form(h_bin, h_grp, n) / bias


def render_reduction(value: float) -> str:
    """The manuscript's own precision rule: one decimal below ten, integer above."""
    return f'{value:.1f}' if value < 10 else f'{round(value):d}'


def run(check, repo: Path) -> None:
    cfg_dir, bias_dir = repo / 'data' / 'bias-config', repo / 'data' / 'bias'

    print('\n[bias] the evaluation bias: composition and the closed form (tab:biasformula)')
    for stem, label, n, h_bin, h_grp, k, bias, _red in PAPER_BIAS_TABLE:
        cfg = composition_from_config(cfg_dir / f'{stem}.yaml')
        st = composition_from_stats(bias_dir / f'{stem}-bias-stats.txt')

        check(f'{label} n', st['n'], n)
        check(f'{label} n, config agrees with the built bias', cfg['n'], st['n'])
        check(f'{label} h_bin', st['h_bin'], h_bin)
        check(f'{label} h_bin, config agrees', cfg['h_bin'], h_bin)
        check(f'{label} h_grp', st['h_grp'], h_grp)
        check(f'{label} h_grp, config agrees', cfg['h_grp'], h_grp)
        check(f'{label} k', st['k'], k)
        check(f'{label} k, config agrees', cfg['k'], k)
        check(f'{label} |B|', st['bias'], bias)
        # The claim S5.3 makes in words: "The formula is exact on all five models."
        check(f'{label} |B| == 2(h_bin + h_grp) + 3C(k,2), EXACTLY',
              closed_form(st['h_bin'], st['h_grp'], st['k']), bias)
        # The operator pairs the recovery above relies on.
        check(f'{label} one optional per mandatory', st['ops']['optional'], st['ops']['mandatory'])
        check(f'{label} one or per alternative', st['ops']['or'], st['ops']['alternative'])
        check(f'{label} two requires per excludes',
              st['ops']['requires'], 2 * st['ops']['excludes'])

    print('\n[bias] the one documented exception: KB1 admits every feature to cross-tree pairs')
    k1 = composition_from_config(cfg_dir / 'REAL-FM-7.yaml')
    check('KB1 cross-tree mode is "all", not "extracted"', k1['mode'], 'all')
    check('KB1 k == n, which is what "all" means', k1['k'], k1['n'])
    for stem, label, *_ in PAPER_BIAS_TABLE:
        if stem == 'REAL-FM-7':
            continue
        check(f'{label} cross-tree mode is "extracted"',
              composition_from_config(cfg_dir / f'{stem}.yaml')['mode'], 'extracted')

    print('\n[bias] the selection criteria quoted in S5.3')
    for stem, (hier, k) in PAPER_SELECTION_CRITERIA.items():
        st = composition_from_stats(bias_dir / f'{stem}-bias-stats.txt')
        check(f'{stem}: hierarchical candidates', st['h_bin'] + st['h_grp'], hier)
        check(f'{stem}: cross-tree candidate features', st['k'], k)
    # "34 of its features take part in cross-tree constraints against 14 of KB2's"
    check('KB3 k exceeds KB2 k, which is why |B| does not track model size',
          composition_from_stats(bias_dir / 'arcade-game-bias-stats.txt')['k'] >
          composition_from_stats(bias_dir / 'fqa-bias-stats.txt')['k'], True)
    # "the model with 1,408 features ... keeps 1,168 of them in cross-tree constraints"
    ea = composition_from_stats(bias_dir / 'ea2468-bias-stats.txt')
    check('ea2468 keeps 1,168 of its 1,408 features in cross-tree constraints',
          (ea['k'], ea['n']), (1168, 1408))
    check('ea2468 |B| is above two million, as S5.3 says', ea['bias'] > 2_000_000, True)

    print('\n[bias] the reduction against the unrestricted language (n/k)^2')
    for stem, label, n, _hb, _hg, _k, bias, printed in PAPER_BIAS_TABLE:
        st = composition_from_stats(bias_dir / f'{stem}-bias-stats.txt')
        exact = reduction_against_unrestricted(st['h_bin'], st['h_grp'], st['n'], st['bias'])
        check(f'{label} reduction, as printed', render_reduction(exact), printed)

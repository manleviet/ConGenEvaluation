#!/usr/bin/env python3
"""|C_tau| in CONSTRAINTS -- Table 7's column and Table 11's header (S6.1.1, S6.2.3).

TWO QUANTITIES, ONE SYMBOL, AND THAT IS THE HAZARD
---------------------------------------------------
The paper used to print |C_tau| in CLAUSES (22, 342, 130, 428, 994). The 2026-09-23
review dropped that sentence and introduced |C_tau| in CONSTRAINTS (13, 102, 70, 219,
905) in two places. Same symbol, different unit, a factor of two to seven apart. The
clause counts are still asserted -- every semantic recall is measured against them --
so both live in this gate, and each says its unit in its own label. A reader who meets
a bare "|C_tau|" in either place should be able to tell which one it is.

The constraint unit is the unit of |KB| (``statistics.n_kb``), which is what makes the
comparison in S6.3 legible: 177 constraints delivered against 70 in the target.

THE CONVENTION, AND WHY IT IS COUNTED TWICE
-------------------------------------------
One constraint per child of a mandatory or optional relationship, one per or/alternative
GROUP however many children it has, one per cross-tree constraint line, and the root is
not counted. A multi-literal cross-tree constraint is one constraint.

It is counted twice here, by two different readings of the same file:

  * ``count_by_owner_scan`` walks the lines and asks, for each feature, which group
    keyword owns it, by looking BACK to the nearest line at a smaller indent.
  * ``count_via_shared_parser`` uses ``count_target_clauses.parse``, which walks
    FORWARD carrying a pending map of open groups per indent level.

The two disagree the moment either mis-attributes a feature, which is the failure mode
an indentation format invites. Agreement between them, and with the paper, is what is
asserted -- not one of them against the paper.
"""
from __future__ import annotations

import sys
from pathlib import Path

FMS = Path('data') / 'fms'
GROUP_KEYWORDS = ('mandatory', 'optional', 'or', 'alternative')
PER_CHILD = ('mandatory', 'optional')     # one constraint per child
PER_GROUP = ('or', 'alternative')         # one constraint per group

# Table 7's column and Table 11's header, as the manuscript prints them.
PAPER_TARGET_CONSTRAINTS = {
    'REAL-FM-7': 13, 'fqa': 102, 'arcade-game': 70, 'REAL-FM-4': 219,
    'busybox-1.18.0': 905,
}
# S6.3: "the 177 constraints it delivers, against 70 in the target".
PAPER_KB3_DELIVERED, PAPER_KB3_TARGET = 177, 70


def _sections(path: Path) -> tuple[list[str], list[str]]:
    """The feature block and the constraint block of a UVL file."""
    lines = path.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == 'features') + 1
    end = next((i for i, l in enumerate(lines) if l.strip() == 'constraints'), len(lines))
    return lines[start:end], [l for l in lines[end + 1:] if l.strip()]


def count_by_owner_scan(path: Path) -> dict:
    """Count by asking each feature which group keyword owns it.

    Backwards attribution: a feature's owner is the nearest PRECEDING line with a
    smaller indent, and it counts only if that line is a group keyword. A feature whose
    nearest smaller-indent line is another feature is that feature's child through an
    implicit relationship, which this format does not have -- so it is not counted, and
    the root, which has no smaller-indent line at all, is not counted either.
    """
    features, cross = _sections(path)
    rows = [(len(l) - len(l.lstrip('\t')), l.strip().split('{')[0].strip())
            for l in features if l.strip()]
    per_child = groups = 0
    for i, (indent, name) in enumerate(rows):
        if name in GROUP_KEYWORDS:
            groups += 1 if name in PER_GROUP else 0
            continue
        owner = next((n for d, n in reversed(rows[:i]) if d < indent), None)
        if owner in PER_CHILD:
            per_child += 1
    return {'per_child': per_child, 'groups': groups, 'cross_tree': len(cross),
            'total': per_child + groups + len(cross)}


def count_via_shared_parser(path: Path) -> dict:
    """The same count through the parser the clause counter already uses."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from count_target_clauses import parse

    _root, groups, cross = parse(path)
    per_child = sum(n for kind, n in groups if kind in PER_CHILD)
    n_groups = sum(1 for kind, _n in groups if kind in PER_GROUP)
    return {'per_child': per_child, 'groups': n_groups, 'cross_tree': cross,
            'total': per_child + n_groups + cross}


def run(check, repo: Path) -> None:
    print('\n[target] |C_tau| in CONSTRAINTS: Table 7\'s column and Table 11\'s header')
    for stem, printed in PAPER_TARGET_CONSTRAINTS.items():
        scan = count_by_owner_scan(repo / FMS / f'{stem}.uvl')
        shared = count_via_shared_parser(repo / FMS / f'{stem}.uvl')
        # Printed per rule, so a disagreement names which rule moved rather than only
        # that the total did.
        print(f"      {stem:16s} per-child {scan['per_child']:4d}  groups {scan['groups']:3d}"
              f"  cross-tree {scan['cross_tree']:3d}  = {scan['total']:4d}")
        check(f'{stem}: |C_tau| in constraints', scan['total'], printed)
        check(f'   ... and the two readings of the UVL agree', shared, scan)

    # Table 7 prints the value once and Table 11 repeats it in its header. Asserting
    # the two against EACH OTHER here would compare this file's constants with
    # themselves; the two fragments are re-derived from the UVL, separately, by
    # check_paper_tables.check_fm_summary and check_kb_size, which is where both
    # printings exist to be read.

    # S6.3: "the 177 constraints it delivers, against 70 in the target".
    import json
    import statistics
    folds = json.loads((repo / 'data' / 'results_sosym_r1' / 'congen' /
                        'arcade-game_rs_1n_cv_incremental.json').read_text())['folds']
    delivered = statistics.mean(f['statistics']['n_kb'] for f in folds)
    check('KB3 RS(n): constraints delivered, the Table 11 cell', round(delivered),
          PAPER_KB3_DELIVERED)
    # Counted from the UVL, not read back out of the constant above: the sentence
    # compares a delivered size with a target size, and only one of those two is a
    # measurement if the target comes from this file's own table.
    check('   ... against KB3\'s target theory, counted in the same unit',
          count_by_owner_scan(repo / FMS / 'arcade-game.uvl')['total'], PAPER_KB3_TARGET)

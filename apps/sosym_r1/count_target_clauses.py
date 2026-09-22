#!/usr/bin/env python
"""Count the target theory's clauses straight from the .uvl, independently of the code.

The published semantic recall has the target theory's clause count as its denominator, so
if that count is wrong every recall figure is wrong with it. Checking the extractor against
itself proves nothing; this counts from the MODEL, using the textbook feature-model to CNF
encoding, and the two numbers are then reported side by side.

Encoding, one line per rule so a disagreement can be traced to a rule rather than to the
whole count:

  root                       1 unit clause
  mandatory child            2   (parent -> child, child -> parent)
  optional child             1   (child -> parent)
  or-group of n              1 + n        (parent -> \\/ci, and each ci -> parent)
  alternative group of n     1 + n + n(n-1)/2   (the pairwise exclusions)
  cross-tree constraint      1   (verified: every constraint line in these models is a
                                  pure disjunction — no '&', no '=>', no '<=>')

The alternative group is the case worth the trouble: its exclusions grow quadratically, so
an extraction defect there inflates rather than shifts, which is the shape of a count that
comes out far too large. arcade-game has none, so it cannot exercise that path; busybox,
fqa and REAL-FM-7 do.

THE VALIDATING INSTANCE MUST BE ABLE TO EXERCISE THE RISKY PATH. The ground-truth question
was first settled against arcade-game, which has zero alternative groups — so the one term
that could be wrong, the C(n,2) exclusions, never fired, and a formula missing it entirely
would have agreed anyway. An independent hand count written without that term returned
21 / 257 / 971 for REAL-FM-7 / fqa / busybox against the correct 22 / 342 / 994, and
reproduced arcade-game and REAL-FM-4 exactly, because neither has an alternative group.
Agreement on an instance that cannot reach the defect is not evidence about the defect.

Two implementations now agree on all five models, and they were written separately with
different structure — that is what makes the agreement evidence rather than one blind spot
run twice.

    count_target_clauses.py                    # all five knowledge bases
    count_target_clauses.py --fm arcade-game   # one
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GROUPS = ('mandatory', 'optional', 'or', 'alternative')
KBS = ['REAL-FM-7', 'fqa', 'arcade-game', 'REAL-FM-4', 'busybox-1.18.0']


def parse(path: Path):
    """-> (root_name, [(group_type, n_children)], n_cross_tree). Indentation-based."""
    lines = path.read_text().splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == 'features') + 1
    except StopIteration:
        raise SystemExit(f"{path}: no 'features' section")
    end = next((i for i, l in enumerate(lines) if l.strip() == 'constraints'), len(lines))

    groups, root, pending = [], None, {}          # pending: indent -> [type, count]
    for raw in lines[start:end]:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip('\t'))
        name = raw.strip().split('{')[0].strip()
        if name in GROUPS:
            # Flush anything at or below this level FIRST. A feature can carry several
            # group blocks in sequence (`optional` then `mandatory` under the same
            # parent); assigning straight into pending[indent] overwrote the earlier one
            # and its children vanished from the count silently — which is exactly the
            # kind of quiet loss this tool exists to detect, so it is worth the comment.
            for d in [d for d in pending if d >= indent]:
                groups.append(tuple(pending.pop(d)))
            pending[indent] = [name, 0]
            continue
        if root is None:
            root = name
            continue
        # a feature belongs to the group keyword one indent level above it
        owner = pending.get(indent - 1)
        if owner is not None:
            owner[1] += 1
        for d in [d for d in pending if d >= indent]:
            groups.append(tuple(pending.pop(d)))
    groups += [tuple(v) for v in pending.values()]

    cross = [l for l in lines[end + 1:] if l.strip()]
    bad = [l for l in cross if '&' in l or '=>' in l]
    if bad:
        raise SystemExit(f"{path}: {len(bad)} constraint(s) are not a pure disjunction; "
                         f"the 1-clause-per-line rule does not hold. First: {bad[0]!r}")
    return root, [g for g in groups if g[1] > 0], len(cross)


def count(groups, n_cross):
    total, parts = 1, {'root': 1, 'cross_tree': n_cross}       # root unit clause
    total += n_cross
    for kind, n in groups:
        if kind == 'mandatory':
            c = 2 * n
        elif kind == 'optional':
            c = n
        elif kind == 'or':
            c = 1 + n
        else:                                                   # alternative
            c = 1 + n + n * (n - 1) // 2
        parts[kind] = parts.get(kind, 0) + c
        total += c
    return total, parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fm', nargs='*', default=KBS)
    args = ap.parse_args()

    sys.path.insert(0, str(REPO))
    from conacq.oracle.ground_truth import GroundTruthData

    print(f"{'model':<18}{'by hand':>9}{'extractor':>11}{'agree':>7}   breakdown")
    disagree = []
    for kb in args.fm:
        path = REPO / 'data' / 'fms' / f'{kb}.uvl'
        _, groups, n_cross = parse(path)
        hand, parts = count(groups, n_cross)
        clauses = GroundTruthData.from_uvl(path).clauses
        got = len(clauses)
        ok = hand == got
        if not ok:
            disagree.append((kb, hand, got))
        bd = ' '.join(f"{k}={v}" for k, v in sorted(parts.items()) if v)
        print(f"{kb:<18}{hand:>9}{got:>11}{'yes' if ok else 'NO':>7}   {bd}")
        if len(clauses) != len({tuple(c) for c in clauses}):
            print(f"{'':18}  ^ extractor emitted duplicates: "
                  f"{len(clauses) - len({tuple(c) for c in clauses})}")

    if disagree:
        print("\nDISAGREEMENT — do not adjust the hand count to match; the extractor is "
              "what is under test:", file=sys.stderr)
        for kb, h, g in disagree:
            print(f"  {kb}: by hand {h}, extractor {g}, difference {g - h:+d}",
                  file=sys.stderr)
        return 1
    print("\nevery model agrees: the extracted target theory is the model's own clause set")
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python
"""Measure the ConGen / condition-A ratio from finished ledger units.

Every estimate in the ledger is a condition-A figure -- AcqMss alone, read off
the condition-A reference CSVs. ConGen is AcqMss plus Reduce, so the estimates
are floors and the question is how loose. This reports the observed ratio per cell
and per knowledge base rather than as one number, because a single global ratio
fitted on cells that take milliseconds says nothing about the cells that take
hours, and those are the only ones a window can fail to hold.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / 'sweep-ledger.json'

# Below this, a fold's wall-clock is dominated by interpreter start-up and model
# build, so its ratio measures process overhead rather than Reduce. Those cells
# also cannot cause the failure the budget check exists to prevent.
SUBSTANTIAL_H = 0.01


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else LEDGER
    ledger = json.loads(path.read_text())
    # `is not None` plus an explicit positive-reference test: a 0.0000 h reference is
    # a real measurement that cannot carry a ratio, not a missing one.
    # ConGen-only, condition-A-referenced, positive reference. A nominal placeholder
    # is a scheduling device, not a baseline; a ratio taken against one measures
    # nothing. busybox rs_m reported 0.060x this way before the flag existed.
    done = [u for u in ledger['units']
            if u['status'] == 'done' and u['actual_h'] is not None
            and u['estimate_h'] is not None and u['estimate_h'] > 0
            and u.get('estimate_source', 'condition-A') == 'condition-A'
            and u['algorithm'] == 'congen']
    if not done:
        print("no finished units with both an estimate and an actual")
        return 1

    by_cell = defaultdict(list)
    for u in done:
        by_cell[(u['kb'], u['sampling'])].append(u)

    header = (f"{'kb':11s}{'sampling':9s}{'n':>3s}{'condA h/fold':>14s}"
              f"{'ConGen h/fold':>15s}{'ratio':>9s}")
    print(header)
    by_kb = defaultdict(list)
    for (kb, samp), rows in sorted(by_cell.items()):
        est = rows[0]['estimate_h']
        act = statistics.mean(r['actual_h'] for r in rows)
        ratio = act / est if est else float('inf')
        by_kb[kb].append(ratio)
        print(f"{kb:11s}{samp:9s}{len(rows):>3d}{est:>14.4f}{act:>15.4f}{ratio:>9.2f}x")

    print()
    print("per knowledge base (median of its cells):")
    for kb, ratios in sorted(by_kb.items()):
        finite = [r for r in ratios if r != float('inf')]
        if finite:
            print(f"  {kb:11s} median {statistics.median(finite):6.2f}x   "
                  f"max {max(finite):6.2f}x   over {len(finite)} cells")

    substantial = [u for u in done if u['estimate_h'] >= SUBSTANTIAL_H]
    print()
    if substantial:
        ratios = [u['actual_h'] / u['estimate_h'] for u in substantial]
        print(f"cells with a condition-A reference of >= {SUBSTANTIAL_H} h "
              f"({len(substantial)} folds):")
        print(f"  median {statistics.median(ratios):.2f}x   max {max(ratios):.2f}x")
        print(f"  -> suggested congen_multiplier: {max(1.0, max(ratios)):.2f}")
    else:
        print(f"no finished unit has a condition-A reference of >= {SUBSTANTIAL_H} h yet;")
        print("the ratio is not measurable on any cell a window could fail to hold.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

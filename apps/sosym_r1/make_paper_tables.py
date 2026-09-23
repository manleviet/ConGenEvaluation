#!/usr/bin/env python3
"""Emit one LaTeX fragment per table the paper prints, from the committed JSON.

    python3 apps/sosym_r1/make_paper_tables.py --out data/results_sosym_r1/tables/paper

Every cell the paper prints comes from here. A cell that reaches the paper by any
other route is a defect, including a cell that happens to be correct: the paper's
tables were typed in by hand from a tree that no longer exists, and "correct" was
not something anyone could check.

Each fragment holds exactly ONE ``tabular`` environment and nothing else. The
caption, the ``\\label`` and the ``table*`` wrapper stay in the manuscript, where
the editorial decisions belong. The journal template forbids ``\\input`` of other TeX
files, so the manuscript TRANSCRIBES the fragment instead of including it -- which is
why this file exists: the transcription has a checked source, and a cell typed from
anywhere else has none.

The companion gate, ``check_paper_tables.py``, parses every fragment back and
recomputes each cell from the JSON with code this module does not share.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.sosym_r1.paper_tables import fragments_comparison as cmp_  # noqa: E402
from apps.sosym_r1.paper_tables import fragments_congen as cg  # noqa: E402
from apps.sosym_r1.paper_tables.read_results import ResultTree  # noqa: E402

TREE = REPO / "data" / "results_sosym_r1"
DATA = REPO / "data"
BASELINES = TREE / "baselines" / "baselines.json"


def build_all(out: Path) -> list[tuple[str, int]]:
    """Write every fragment; return (filename, cell count) per fragment."""
    tree = ResultTree(TREE)
    out.mkdir(parents=True, exist_ok=True)

    fragments: dict[str, str] = {
        "tab_fm_summary": cg.fm_summary(tree, DATA),
        "tab_example_sizes": cg.example_sizes_table(tree, DATA),
        "tab_AcqMssruntime": cg.acqmss_runtime(tree, DATA),
        "tab_accuracy_all": cg.accuracy_all(tree, DATA),
        # semantic_pr is gone: the paper folded P and R into tab_comparison_strategies
        # and moved the exact-equivalence rate into prose, where the numbers gate
        # holds it. One table in the paper, one fragment here.
        "tab_comparison_strategies": cg.comparison_strategies(tree, DATA),
        "tab_kb_size": cg.kb_size(tree, DATA),
        "tab_iterative_accuracy": cmp_.iterative_accuracy(tree, DATA),
        "tab_iterative_semantic": cmp_.iterative_semantic(tree, DATA),
        "tab_runtime_comparison": cmp_.runtime_comparison(tree, DATA),
        "tab_rule_learners": cmp_.rule_learners(tree, DATA, BASELINES),
        # ARTIFACT-ONLY, NOT PRINTED. The 2026-09-23 review moved the significance
        # results into S6.2.5's prose and dropped the table. The fragment stays: the
        # Wilcoxon medians, the Holm family and the exclusion of claim 2 are asserted
        # against it, and a reader who wants the per-claim rows has nowhere else to
        # look. It is the one fragment with no table in the paper.
        "tab_significance": _significance(),
    }

    written = []
    for name, body in fragments.items():
        path = out / f"{name}.tex"
        path.write_text(body)
        written.append((f"{name}.tex", _cells(body)))
    return written


def _significance() -> str:
    from significance_tests import ALPHA, compute, floor_p, holm
    return cmp_.significance(compute, holm, floor_p, ALPHA)


def _cells(body: str) -> int:
    """Body cells in a fragment — what the gate will have to re-derive."""
    rows = [ln for ln in body.splitlines()
            if ln.endswith(r"\\") and not ln.startswith(("\\toprule", "\\midrule"))]
    return sum(len(r.split("&")) for r in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(TREE / "tables" / "paper"),
                    help="directory the fragments are written to")
    args = ap.parse_args()

    out = Path(args.out)
    written = build_all(out)
    for name, cells in written:
        print(f"  {name:34s} {cells:4d} cells")
    print(f"{len(written)} fragments -> {out}")
    # A positive count, never the absence of an error: an empty run would otherwise
    # print a tidy summary of nothing and exit 0.
    if len(written) < 11:
        print(f"FAIL: wrote {len(written)} fragments, expected 11.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

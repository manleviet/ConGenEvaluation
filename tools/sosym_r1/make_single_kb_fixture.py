#!/usr/bin/env python3
"""Extract one fold of a cross-validation result as a single-knowledge-base document.

    python3 tools/sosym_r1/make_single_kb_fixture.py \\
        data/results_sosym_r1/congen/REAL-FM-7_rs_1n_cv_incremental.json \\
        --fold 0 --out tests/resources/congen_kb_REAL-FM-7_rs_1n_fold0.json

WHY THIS EXISTS. ``tests/test_evaluation.py`` exercises the comparator and the
accuracy calculator against a real learned knowledge base, and a cross-validation
file cannot stand in for one: it carries its constraints inside ``folds[]``, so
loading it through ``ConGenResultData.from_json`` yields an EMPTY knowledge base and
every assertion downstream passes on nothing. That is the defect ADR-0019 records
from the ``--kb`` entry point, and it would read as a green test rather than a
missing fixture.

So the fixture is DERIVED, mechanically, and this is the derivation. Regenerate it
whenever the results are re-scored, rather than hand-editing the JSON -- a fixture
nobody can reproduce is the same problem one step removed.

Constraint ids are flattened: a fold stores each constraint as an object, and the
loader wants the id. Keeping the objects produces ``TypeError: unhashable type:
'dict'`` deep inside the bias structures, which names nothing useful.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def ids_of(constraints) -> list:
    return [c["id"] if isinstance(c, dict) else c for c in (constraints or [])]


def single_kb(cv_path: Path, fold_index: int) -> dict:
    folds = json.loads(cv_path.read_text())["folds"]
    match = [f for f in folds if f.get("fold_index") == fold_index]
    if not match:
        raise SystemExit(f"{cv_path} has no fold with fold_index {fold_index}; "
                         f"it has {[f.get('fold_index') for f in folds]}")
    fold = match[0]
    return {
        "kb_constraints": ids_of(fold["kb_constraints"]),
        "redundant_constraints": ids_of(fold.get("redundant_constraints")),
        "statistics": {k: fold["statistics"][k] for k in ("n_bias", "n_mss", "n_kb")},
        "fold": fold["fold_index"],
        "accuracy": fold["accuracy"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv_file", type=Path)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    doc = single_kb(args.cv_file, args.fold)
    if not doc["kb_constraints"]:
        raise SystemExit("refusing to write a fixture with an EMPTY knowledge base -- "
                         "that is the failure this fixture exists to make visible")
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"{args.out}: |KB| {len(doc['kb_constraints'])}, "
          f"fold {doc['fold']}, accuracy {doc['accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

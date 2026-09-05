#!/usr/bin/env python3
"""Assert that every model present in the data reaches the generated tables.

    python3 apps/sosym_r1/check_table_coverage.py [--tables DIR] [--results DIR]

THE INVARIANT
-------------
    Every cell in a generated table must be traceable to a source file, and a table
    printing an empty marker for a model that IS present in the data is a failure.

WHY THIS GATE EXISTS, AND WHY THE OTHERS COULD NOT CATCH IT
-----------------------------------------------------------
`results_tables.tex` shipped in v1.0.0 with the row ``KB3 & - & - & - & - & - & -``,
and busybox absent from every table. The cause was a hand-written constant:

    KB_MAPPING = {'REAL-FM-7': 'KB1', 'fqa': 'KB2', 'arcade': 'KB3', 'REAL-FM-4': 'KB4'}

matched against filenames with ``KB_REVERSE.get(kb_name)`` -- an EXACT lookup. The data
is named ``arcade-game`` and ``busybox-1.18.0``, so one key missed and one model was
never listed at all.

Seven rounds of gates were green while that shipped, and the reason is worth stating
plainly, because it is a property of how those gates were built rather than an oversight
in any one of them:

  * the 93 paper-number checks verify figures quoted in the paper, computed from the
    result trees. They never open ``results_tables.tex``.
  * "five tables byte-identical" compares a regenerated table against the COMMITTED
    table. Both were produced by the same defective mapping, so both agreed.

Every gate compared the artifact against itself. Determinism was being measured and
reported as correctness. This gate is the first that asks whether a table contains the
data it claims to contain, and it answers from the FILENAMES ON DISK rather than from a
constant -- because a constant is precisely what failed.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
EMPTY = {'-', '--', 'n/a', 'N/A', ''}


def models_from_data(results_dir: pathlib.Path, fm_dir: pathlib.Path) -> dict[str, int]:
    """Models that actually have results, keyed by name, valued by CV-file count.

    Derived by matching CV filenames against the feature models on disk, so adding a
    model to the sweep adds it here with no edit. The alternative -- a list of names in
    this file -- is the defect being guarded against.
    """
    known = sorted((p.stem for p in fm_dir.glob('*.uvl')), key=len, reverse=True)
    found: dict[str, int] = {}
    for f in sorted(results_dir.glob('*_cv_*.json')):
        for name in known:                      # longest first: busybox-1.18.0 before busybox
            if f.name.startswith(name + '_'):
                found[name] = found.get(name, 0) + 1
                break
    return found


def labels_from_tables(tables_dir: pathlib.Path) -> tuple[dict[str, str], list[pathlib.Path]]:
    """The label->model mapping the tables declare, read from their own header line."""
    mapping: dict[str, str] = {}
    seen: list[pathlib.Path] = []
    for path in sorted(tables_dir.glob('results_tables.*')):
        seen.append(path)
        for line in path.read_text().splitlines():
            if 'KB Mapping:' in line:
                for label, model in re.findall(r'(KB\d+)=([A-Za-z0-9._\-]+)', line):
                    mapping[label] = model
    return mapping, seen


def _row_cells(line: str, label: str) -> list[str] | None:
    """The data cells of a table row whose first column is `label`, else None."""
    cells = [c.strip().rstrip('\\').strip() for c in re.split(r'[&|]', line)]
    cells = [c for c in cells if c != '']
    if len(cells) < 2 or cells[0] != label:
        return None
    return cells[1:]


def orphan_rows(path: pathlib.Path, labels: list[str]) -> list[tuple[int, str]]:
    """Rows empty for one label while a SIBLING label on the same table has data.

    The comparison is against siblings, not against emptiness alone, and that is what
    keeps this gate honest. Whole tables here are legitimately blank -- the sweep ran
    incremental only, so every non-incremental table is empty for every model, and a
    check that simply forbade empty rows would go red on correct output. It would then
    be switched off, which is how a gate stops protecting anything.

    A row that is blank while its neighbours in the same table are populated is a
    different claim: the data exists and this label did not reach it.
    """
    lines = path.read_text().splitlines()
    populated: set[str] = set()
    for line in lines:
        for label in labels:
            cells = _row_cells(line, label)
            if cells and any(c not in EMPTY for c in cells):
                populated.add(label)
    if not populated:
        return []                      # nothing in this file has data; not this gate's call
    orphans = []
    for i, line in enumerate(lines, 1):
        for label in labels:
            if label in populated:
                continue
            cells = _row_cells(line, label)
            if cells and all(c in EMPTY for c in cells):
                orphans.append((i, label))
    return orphans


def malformed_tabulars(path: pathlib.Path) -> list[str]:
    """LaTeX rows whose field count disagrees with the column spec.

    Added because widening the tables introduced exactly this: the row bodies iterate
    KB_NAMES and grew to five models, while the header and `\\begin{tabular}{lcccc}`
    stayed at four. Six fields in a five-column table is LaTeX that does not compile,
    and no gate here would have seen it -- coverage was satisfied, the numbers were
    right, and the file was byte-identical to a regeneration of itself.
    """
    if path.suffix != '.tex':
        return []
    problems: list[str] = []
    spec = None
    label = '?'
    for i, line in enumerate(path.read_text().splitlines(), 1):
        m = re.search(r'\\begin\{tabular\}\{([lcr|@{}.\s]+)\}', line)
        if m:
            spec = sum(1 for ch in m.group(1) if ch in 'lcr')
            continue
        m = re.search(r'\\label\{([^}]+)\}', line)
        if m:
            label = m.group(1)
        if line.strip().startswith(r'\end{tabular}'):
            spec = None
            continue
        if spec is None or '&' not in line:
            continue
        if line.lstrip().startswith('%'):
            continue
        fields = len(line.split('&'))
        if fields != spec:
            problems.append(
                f"{path.name}:{i} ({label}): {fields} fields in a {spec}-column tabular")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--results', default='data/results_sosym_r1/congen')
    ap.add_argument('--tables', default='data/results_sosym_r1/tables')
    ap.add_argument('--fms', default='data/fms')
    args = ap.parse_args()

    results_dir = REPO / args.results
    tables_dir = REPO / args.tables
    fm_dir = REPO / args.fms
    for d in (results_dir, tables_dir, fm_dir):
        if not d.is_dir():
            print(f"FAIL: missing directory {d}", file=sys.stderr)
            return 1

    data_models = models_from_data(results_dir, fm_dir)
    mapping, table_files = labels_from_tables(tables_dir)
    if not table_files:
        print("FAIL: no results_tables.* found -- nothing to check", file=sys.stderr)
        return 1
    if not data_models:
        print(f"FAIL: no CV files under {results_dir}", file=sys.stderr)
        return 1

    print(f"models with results in {args.results}:")
    for name, n in sorted(data_models.items()):
        print(f"  {name:<20} {n:>3} CV file(s)")
    print(f"\nlabels declared by the tables: "
          f"{', '.join(f'{k}={v}' for k, v in sorted(mapping.items())) or '(none)'}")

    failures: list[str] = []

    # 1. every model with data must carry a label
    labelled = set(mapping.values())
    for name in sorted(data_models):
        if name not in labelled:
            failures.append(
                f"{name} has {data_models[name]} CV file(s) but no label in the tables")

    # 2. every declared label must name a model that exists on disk
    for label, model in sorted(mapping.items()):
        if model not in data_models:
            near = [m for m in data_models if m.startswith(model) or model.startswith(m)]
            hint = f" -- did you mean {near[0]!r}?" if near else ""
            failures.append(f"label {label} names {model!r}, which has no results{hint}")

    # 3. no label may be blank while a sibling label on the same table has data
    live = [l for l, m in sorted(mapping.items()) if m in data_models]
    for path in table_files:
        for line_no, label in orphan_rows(path, live):
            model = mapping[label]
            failures.append(
                f"{path.name}:{line_no}: {label} ({model}, {data_models[model]} CV files) "
                f"is empty while other models on the same table have data")

    # 4. a widened table must still be well-formed LaTeX
    for path in table_files:
        failures.extend(malformed_tabulars(path))

    if failures:
        print(f"\n{'=' * 70}")
        print(f"FAIL: {len(failures)} coverage problem(s):")
        for f in failures:
            print(f"  - {f}")
        print("\nA table that prints '-' for a model that has results is not reporting a")
        print("negative result; it is failing to find data that is present.")
        return 1

    print(f"\n{'=' * 70}")
    print(f"OK: all {len(data_models)} model(s) with results are labelled and populated "
          f"across {len(table_files)} table file(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())

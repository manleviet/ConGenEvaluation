"""Properties a cost table must have, whatever expression produced it.

WHY THESE EXIST SEPARATELY FROM THE RE-DERIVATION. The cell gate recomputes each cell
from the JSON, which catches a cell that was mistyped, mis-rounded, or read from the
wrong field. It cannot catch a wrong DEFINITION: if the generator subtracts a phase
that was never part of the minuend, the gate re-implements the same subtraction and
agrees with it. That is not hypothetical -- it printed ``-1{,}723`` as a millisecond
count for KB2 and the gate reported 1,250 cells, 0 mismatched.

A property check does not need to know the expression. A duration is never negative;
phases inside a total never sum past it; a declared total is the sum of its parts.
Those hold for every correct derivation and fail for whole classes of wrong ones.

The containment properties are read from the JSON's own timing scopes rather than
from the table, because the question "may this be subtracted from that?" is a fact
about the profiler, not about the rendering.
"""
from __future__ import annotations

import json
from pathlib import Path


def number(cell: str) -> float | None:
    """Parse a rendered cell back to a number; None for a marker."""
    s = cell.replace("{,}", "").replace(",", "").strip()
    if s in ("n/a", "--", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def durations_non_negative(rows: list[list[str]], ms_columns: dict[int, str]) -> list[str]:
    """P1 -- no printed duration is negative.

    A negative millisecond count is not a small error in a large number; it is a
    statement that time ran backwards, and it means the expression is wrong rather
    than imprecise.
    """
    bad = []
    for row in rows:
        for idx, name in ms_columns.items():
            v = number(row[idx])
            if v is not None and v < 0:
                bad.append(f"{row[0]} {row[1]} {name}: negative duration {row[idx]}")
    return bad


def phases_within_total(rows: list[list[str]], parts: list[int], total: int,
                        label: str, tolerance: float = 0.0) -> tuple[list[str], float]:
    """P2 -- the phases inside a total never sum past it. Returns (failures, max slack).

    Reported as an inequality, not an equality: the slack is real (setup and teardown
    sit outside every phase scope) and naming it is the point. An equality here would
    force the slack into whichever phase happened to be last.
    """
    bad, worst = [], 0.0
    for row in rows:
        vals = [number(row[i]) for i in parts]
        tot = number(row[total])
        if tot is None or any(v is None for v in vals):
            continue
        s = sum(vals)
        if s > tot + tolerance:
            bad.append(f"{row[0]} {row[1]} {label}: phases sum to {s:.0f} > total {tot:.0f}")
        worst = max(worst, tot - s)
    return bad, worst


def parts_sum_to_total(rows: list[list[str]], parts: list[int], total: int,
                       label: str) -> list[str]:
    """P3 -- a declared total IS the sum of its declared parts, exactly."""
    bad = []
    for row in rows:
        vals = [number(row[i]) for i in parts]
        tot = number(row[total])
        if tot is None or any(v is None for v in vals):
            continue
        if abs(sum(vals) - tot) > 1.0:          # 1 unit: each part is rounded once
            bad.append(f"{row[0]} {row[1]} {label}: parts sum to {sum(vals):.0f}, "
                       f"total says {tot:.0f}")
    return bad


def timing_scopes(congen_dir: Path) -> list[str]:
    """P4 -- the containment any derived duration depends on, read from the JSON.

    Checked over every fold, not a sample. These are what make
    ``loop - reduce`` a legitimate expression and ``loop - preprocessing`` an
    illegitimate one, and neither is visible in the rendered table.
    """
    bad = []
    for path in sorted(congen_dir.glob("*_cv_incremental.json")):
        for fold in json.loads(path.read_text()).get("folds", []):
            perf = fold.get("performance") or {}
            prof = perf.get("profiler") or {}

            def total_ms(key: str) -> float:
                block = prof.get(key)
                return (block or {}).get("total", 0.0) * 1000.0 if block else 0.0

            total = perf.get("runtime_ms")
            loop = perf.get("congen_runtime_ms")
            if total is None or loop is None:
                continue
            reduce_ms = perf.get("reduce_runtime_ms") or 0.0
            prep = total_ms("shared_preprocessing_runtime")
            where = f"{path.name} fold {fold.get('fold_index')}"
            if reduce_ms > loop + 1e-6:
                bad.append(f"{where}: reduce_runtime_ms {reduce_ms:.1f} exceeds "
                           f"congen_runtime_ms {loop:.1f} -- Reduce is not inside the loop")
            if loop + prep > total + 1e-6:
                bad.append(f"{where}: congen_runtime_ms + preprocessing "
                           f"{loop + prep:.1f} exceeds runtime_ms {total:.1f}")
            if abs(total_ms("congen_total_time") - total) > 1e-6:
                bad.append(f"{where}: profiler.congen_total_time "
                           f"{total_ms('congen_total_time'):.1f} != runtime_ms {total:.1f}")
    return bad


def fold_counts(congen_dir: Path, declared: int) -> list[str]:
    """P5 -- every unit has exactly the declared number of folds, and every fold
    contributes to every mean.

    The fragment's header declares that each cell is a mean over ``declared`` folds.
    This is what makes that declaration true rather than decorative: if a unit ever
    has a different number of folds, or a fold stops carrying a quantity the mean
    needs, the declaration silently becomes a different statement and every affected
    cell moves without anything going red.

    The GenerateNE/QuickXplain counters are the one case where a fold legitimately
    lacks a key, and it is not an exemption: the phase did not run because the fold's
    training split holds no negative example, so the fold contributes a measured zero
    and still counts. A fold missing the key WITH negatives present is reported here,
    because then the mean really would be over fewer folds than it claims.
    """
    bad = []
    for path in sorted(congen_dir.glob("*_cv_incremental.json")):
        folds = json.loads(path.read_text()).get("folds") or []
        if len(folds) != declared:
            bad.append(f"{path.name}: {len(folds)} folds, the fragment declares {declared}")
        for fold in folds:
            prof = ((fold.get("performance") or {}).get("profiler") or {})
            neg = (fold.get("train_size") or {}).get("negative")
            for key in ("shared_preprocessing_runtime",
                        "shared_preprocessing_quickxplain_checks"):
                if key not in prof and neg != 0:
                    bad.append(f"{path.name} fold {fold.get('fold_index')}: {key} "
                               f"missing but the split holds {neg} negative(s), so the "
                               f"mean would be over fewer folds than declared")
    return bad

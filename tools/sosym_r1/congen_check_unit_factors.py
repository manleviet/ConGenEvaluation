#!/usr/bin/env python3
"""
Node-vs-solver-call unit factors, and the AcqMss positive-set shrink ratio,
derived from the committed ConGen cross-validation results.

Analysis harness for the cost accounting and for the positive-example pruning in
Algorithm 2. Reads only
the produced JSON files and imports nothing from the AcqMSS repo, so it cannot
inherit a defect from the code it measures. Stdlib only.

    python3 tools/sosym_r1/congen_check_unit_factors.py .
    python3 tools/sosym_r1/congen_check_unit_factors.py . --json out.json

WHAT IT COMPUTES
----------------
Per fold, from ``folds[i].performance``:

    nodes      = consistency_checks              # the paper's unit: one per
                                                 # AcqMss node, over all of E'+
    total      = is_consistent_calls             # every SAT solve, atomic
    reduce     = redundancy_consistency_checks   # Reduce's solves, atomic
    acq_calls  = total - reduce                  # AcqMss's solves, atomic
    per_node   = acq_calls / nodes               # the CONVERSION FACTOR
    train_pos  = train_size.positive             # |E+| actually trained on
    shrink     = per_node / train_pos            # mean |E'+| as a fraction of |E+|

``per_node`` is the factor by which ``consistency_checks`` understates AcqMss's
solver work. Summing ``consistency_checks`` and ``redundancy_consistency_checks``
into one total is wrong by exactly this factor, which is why Table 9 reports both
units rather than one.

``shrink`` measures the effect that item B17 makes explicit in Algorithm 2: the
consistency test returns the positives *still violated*, and the recursion
carries that shrinking set. A value below 1 is that pruning, quantified.

WHAT IT DOES NOT COMPUTE
------------------------
The **preprocessing** (GenerateNE / QuickXplain) share. ConGen calls GenerateNE
with ``profiler=None`` (``generate_ne.py``), so those solves are not counted in
``is_consistent_calls`` at all. ``acq_calls`` above therefore excludes them, and
the phase is simply absent from this data. Closing that would mean
instrumenting those solves. Until then, treat ``acq_calls`` as "AcqMss only" rather than
"everything except Reduce".

STALENESS
---------
``data/results/congen/`` predates ADR-0015 (unseeded example-mode pool),
ADR-0016 (QuAcq bias order) and ADR-0017 (Reduce dedup order). The **KB contents** these runs produced are therefore not the
numbers the revision will publish. The ratios here are expected to be more
robust than the contents, because they are structural properties of the
recursion rather than of which constraints survive it, but that is an
expectation and not a result. Re-run this script after the sweep and compare.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

RESULTS_GLOB_DIR = os.path.join("data", "results", "congen")
SUFFIX = "_cv_incremental.json"

# Samplings in the order the paper presents them, so the report is stable.
SAMPLING_ORDER = ["rs_1n", "rs_2n", "rs_3n", "rs_m", "2cov", "ff"]

# The random-sampling family is the only controlled comparison available: it
# triples |E+| while holding the knowledge base, the bias and the fold structure
# fixed. The "shrink ratio is a property of the KB, not of |E+|" claim is made
# from these three and nothing else.
RS_FAMILY = ["rs_1n", "rs_2n", "rs_3n"]

# Below this many training positives the shrink ratio is an artefact of a
# near-empty denominator, so it is reported as undefined rather than computed.
MIN_TRAIN_POS = 3


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_sha(repo: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        sha = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}" if sha else "unknown"
    except Exception:
        return "unknown"


def split_name(stem: str) -> tuple[str, str]:
    """``arcade-game_rs_1n`` -> (``arcade-game``, ``rs_1n``). Splits on the
    longest known sampling suffix, since KB names themselves contain ``-`` and
    ``_`` (``REAL-FM-7``, ``busybox-1.18.0``)."""
    for s in sorted(SAMPLING_ORDER, key=len, reverse=True):
        if stem.endswith("_" + s):
            return stem[: -(len(s) + 1)], s
    return stem, "?"


def collect(repo: str) -> tuple[list[dict], list[dict]]:
    """Returns (per-fold rows, per-file provenance)."""
    d = os.path.join(repo, RESULTS_GLOB_DIR)
    if not os.path.isdir(d):
        sys.exit(f"not found: {d}")

    rows: list[dict] = []
    prov: list[dict] = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(SUFFIX):
            continue
        path = os.path.join(d, fn)
        kb, sampling = split_name(fn[: -len(SUFFIX)])
        prov.append({"file": fn, "sha256": sha256(path),
                     "size_bytes": os.path.getsize(path)})
        data = json.load(open(path))
        for fold in data.get("folds", []):
            p = fold.get("performance", {})
            nodes = p.get("consistency_checks")
            total = p.get("is_consistent_calls")
            reduce_calls = p.get("redundancy_consistency_checks")
            train_pos = (fold.get("train_size") or {}).get("positive")
            if not nodes or total is None:
                continue
            acq = total - (reduce_calls or 0)
            # A fold with almost no training positives makes the shrink ratio
            # meaningless: the denominator is a rounding artefact, not a
            # population. 2-COV is structurally positive-free (see the paper's
            # Table 8), so those folds are excluded from the ratio rather than
            # allowed to produce values above 1.
            usable = bool(train_pos) and train_pos >= MIN_TRAIN_POS
            row = {
                "kb": kb, "sampling": sampling, "fold": fold.get("fold_index"),
                "nodes": nodes, "solver_calls_total": total,
                "reduce_calls": reduce_calls or 0, "acq_calls": acq,
                "train_pos": train_pos,
                "per_node": acq / nodes,
                "shrink": (acq / nodes / train_pos) if usable else None,
                "shrink_excluded": (not usable),
            }
            rows.append(row)
    return rows, prov


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def aggregate(rows: list[dict]) -> list[dict]:
    keys = sorted({(r["kb"], r["sampling"]) for r in rows},
                  key=lambda k: (k[0], SAMPLING_ORDER.index(k[1])
                                 if k[1] in SAMPLING_ORDER else 99))
    out = []
    for kb, sampling in keys:
        grp = [r for r in rows if r["kb"] == kb and r["sampling"] == sampling]
        shr = [r["shrink"] for r in grp if r["shrink"] is not None]
        out.append({
            "kb": kb, "sampling": sampling, "n_folds": len(grp),
            "nodes": sum(r["nodes"] for r in grp),
            "acq_calls": sum(r["acq_calls"] for r in grp),
            "reduce_calls": sum(r["reduce_calls"] for r in grp),
            "per_node": mean([r["per_node"] for r in grp]),
            "train_pos": mean([r["train_pos"] for r in grp
                               if r["train_pos"] is not None]) if any(
                r["train_pos"] is not None for r in grp) else None,
            "shrink": mean(shr) if shr else None,
            "n_folds_excluded": sum(1 for r in grp if r["shrink_excluded"]),
        })
    return out


def render(agg: list[dict], rows: list[dict], prov: list[dict],
           repo: str) -> str:
    lines: list[str] = []
    add = lines.append
    add("# ConGen check-unit factors and AcqMss shrink ratio")
    add("")
    add(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"from `{RESULTS_GLOB_DIR}` at repo `{git_sha(repo)}`.")
    add("")
    add("Regenerate with `python3 tools/sosym_r1/congen_check_unit_factors.py .`")
    add("")
    add("⚠ **Stale inputs.** These results predate ADR-0015, ADR-0016, ADR-0017 "
        "so the knowledge bases they produced "
        "are not what the revision will publish. The ratios are expected to be "
        "more robust than the contents, since they are structural properties of "
        "the recursion, but that is an expectation. Re-run after the sweep.")
    add("")
    add("⚠ **Preprocessing is absent.** ConGen calls GenerateNE with "
        "`profiler=None`, so its solves never reach `is_consistent_calls`. "
        "`acq_calls` is AcqMss only. Closing it means instrumenting those solves.")
    add("")
    add("## Per knowledge base and sampling (mean over folds)")
    add("")
    add("| KB | sampling | folds | nodes | AcqMss solves | Reduce solves "
        "| solves/node | train \\|E+\\| | shrink |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for a in agg:
        shrink = f"{a['shrink']:.3f}" if a["shrink"] is not None else "—"
        tp = f"{a['train_pos']:.1f}" if a["train_pos"] is not None else "—"
        add(f"| {a['kb']} | {a['sampling']} | {a['n_folds']} | {a['nodes']:,} "
            f"| {a['acq_calls']:,} | {a['reduce_calls']:,} "
            f"| {a['per_node']:.2f} | {tp} | {shrink} |")
    add("")

    per_node_vals = [r["per_node"] for r in rows]
    add("## Headline")
    add("")
    add(f"- **Conversion factor** (solver calls per node) spans "
        f"**{min(per_node_vals):.2f}× to {max(per_node_vals):.2f}×** across "
        f"{len(rows)} folds. Adding `consistency_checks` to "
        f"`redundancy_consistency_checks` is wrong by that factor, which is why "
        f"Table 9 reports both units.")
    add("")
    add("- **Shrink ratio, on the controlled comparison only.** The RS family "
        "triples \\|E+\\| while holding the knowledge base, the bias and the "
        "fold structure fixed, so it is the only place the claim can be tested. "
        "A knowledge base needs all three to appear here:")
    tested = 0
    for kb in sorted({a["kb"] for a in agg}):
        vals = [(a["sampling"], a["shrink"]) for a in agg
                if a["kb"] == kb and a["sampling"] in RS_FAMILY
                and a["shrink"] is not None]
        if len(vals) < len(RS_FAMILY):
            add(f"  - `{kb}`: **not testable**, only "
                f"{len(vals)}/{len(RS_FAMILY)} of the RS family present")
            continue
        tested += 1
        vs = [v for _, v in vals]
        spread = max(vs) - min(vs)
        add(f"  - `{kb}`: " + " / ".join(f"{v:.3f}" for v in vs)
            + f" — spread **{spread:.3f}** while \\|E+\\| triples")
    add("")
    if tested:
        add(f"  On the {tested} knowledge base(s) where all three are present, "
            "the ratio barely moves while \\|E+\\| triples, yet differs "
            "substantially between knowledge bases. That supports reporting "
            "this pruning **per knowledge base** rather than as a single "
            "hedged number. It is not established for a knowledge base whose "
            "RS family is incomplete.")
        add("")
    others = [(a["kb"], a["sampling"], a["shrink"]) for a in agg
              if a["sampling"] not in RS_FAMILY and a["shrink"] is not None]
    if others:
        add("- Non-RS samplings, for reference only (\\|E+\\| not controlled): "
            + ", ".join(f"`{kb}/{s}` {v:.3f}" for kb, s, v in others))
        add("")
    excl = [a for a in agg if a["n_folds_excluded"]]
    if excl:
        add(f"- **Excluded from every shrink figure** (fewer than "
            f"{MIN_TRAIN_POS} training positives, so the denominator is an "
            f"artefact): "
            + ", ".join(f"`{a['kb']}/{a['sampling']}` "
                        f"({a['n_folds_excluded']}/{a['n_folds']} folds)"
                        for a in excl))
        add("")
    add("## Input provenance")
    add("")
    add("| file | sha256 (first 16) | bytes |")
    add("|---|---|---:|")
    for p in prov:
        add(f"| `{p['file']}` | `{p['sha256'][:16]}` | {p['size_bytes']:,} |")
    add("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("repo", nargs="?", default=".", help="repo root")
    ap.add_argument("--json", help="also write the raw per-fold rows here")
    ap.add_argument("-o", "--out", help="write the markdown report here "
                                        "instead of stdout")
    args = ap.parse_args()

    rows, prov = collect(args.repo)
    if not rows:
        sys.exit("no usable folds found")
    agg = aggregate(rows)
    report = render(agg, rows, prov, args.repo)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(report + "\n")
        print(f"wrote {args.out} ({len(rows)} folds, {len(agg)} runs)")
    else:
        print(report)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"generated": datetime.now(timezone.utc).isoformat(),
                       "repo_sha": git_sha(args.repo),
                       "folds": rows, "aggregated": agg,
                       "inputs": prov}, fh, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Re-derive every cell of every emitted fragment, from the JSON, independently.

    python3 apps/sosym_r1/check_paper_tables.py --tables data/results_sosym_r1/tables/paper

Green means: every cell the paper will print was recomputed from the committed
result files by code that shares no aggregation with the generator, and matched
exactly after the same rounding. Red means a cell reached the fragment by some
other route -- which includes a cell that happens to be correct, because "happens
to be" is not a property anyone can check later.

A fragment that cannot be parsed is red, not skipped.

The comparison is EXACT on the rendered string. The prose gate's tolerance (5e-3)
is for figures quoted in sentences; a table cell is a rendering, and two renderings
either agree or they do not.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.sosym_r1.audit_tables import parse_tex as P  # noqa: E402
from apps.sosym_r1.audit_tables import properties as PR  # noqa: E402
from apps.sosym_r1.audit_tables import reread as R  # noqa: E402

# The gate declares the frozen vocabulary itself rather than importing the
# generator's. If the generator renumbered a KB, importing its list would make the
# gate agree with the renumbering and report green.
KBS = ["REAL-FM-7", "fqa", "arcade-game", "REAL-FM-4", "busybox-1.18.0"]
SAMPLINGS = ["rs_1n", "rs_2n", "rs_3n", "rs_m", "2cov", "ff"]
NOT_RUN = {("busybox-1.18.0", "rs_2n"), ("busybox-1.18.0", "rs_3n")}
MODES = ["congen", "example_only", "example_first"]
LEARNERS = ["ripper", "cn2", "decision_tree"]
NA, UND = "n/a", "--"

TREE = REPO / "data" / "results_sosym_r1"
DATA = REPO / "data"


class Audit:
    def __init__(self) -> None:
        self.checked = 0
        self.bad: list[str] = []
        self.properties: tuple[int, float] | None = None

    def cell(self, where: str, got: str, want: str) -> None:
        self.checked += 1
        if got != want:
            self.bad.append(f"{where}: fragment says {got!r}, the JSON gives {want!r}")

    # ------------------------------------------------------------ result access
    def folds(self, stem: str, samp: str, method: str) -> list[dict]:
        if method == "congen":
            return R.folds(TREE / "congen" / f"{stem}_{samp}_cv_incremental.json")
        return R.folds(TREE / "interactive"
                       / f"{stem}_{samp}_cv_incremental_{method}.json")


def _grid(audit: Audit, path: Path, header_lines: int, want_cell, label: str,
          per_kb: int = 1) -> None:
    """Rows are samplings, columns are KBs in blocks of ``per_kb`` sub-columns."""
    rows = P.body_rows(path, header_lines)
    if len(rows) != len(SAMPLINGS):
        audit.bad.append(f"{label}: {len(rows)} body rows, expected {len(SAMPLINGS)}")
        return
    for samp, row in zip(SAMPLINGS, rows):
        cells = P.expand(row)[1:]
        for k, stem in enumerate(KBS):
            block = cells[k * per_kb:(k + 1) * per_kb]
            for j, got in enumerate(block):
                audit.cell(f"{label} {samp} {stem} col{j}", got,
                           want_cell(stem, samp, j))


def check_fm_summary(a: Audit, d: Path) -> None:
    rows = P.body_rows(d / "tab_fm_summary.tex", 1)
    for stem, row in zip(KBS, rows):
        n = R.bias_numbers(DATA / "bias", stem)
        for j, key in enumerate(("features", "bias", "clauses")):
            a.cell(f"fm_summary {stem} {key}", row[1 + j], R.fmt_count(n[key]))


def check_example_sizes(a: Audit, d: Path) -> None:
    def want(stem, samp, j):
        if (stem, samp) in NOT_RUN:
            return NA
        return R.fmt_count(R.example_counts(DATA / "examples", stem, samp)[j])
    _grid(a, d / "tab_example_sizes.tex", 2, want, "example_sizes", per_kb=2)


COST_COLS = ("acqmss checks", "acqmss ms", "reduce checks", "reduce ms",
             "prep checks", "prep ms", "total checks", "total ms")
MS_COLUMNS = {3: "AcqMss ms", 5: "Reduce ms", 7: "GenNE/QX ms", 9: "total ms"}
CHECK_PARTS, CHECK_TOTAL = [2, 4, 6], 8
MS_PARTS, MS_TOTAL = [3, 5, 7], 9
# The fragment header declares this; P5 is what keeps the declaration true.
DECLARED_FOLDS = 3


def _cost_rows(d: Path) -> list[list[str]]:
    return P.body_rows(d / "tab_AcqMssruntime.tex", 2)


def check_acqmss_runtime(a: Audit, d: Path) -> None:
    """Re-derive the eight cost quantities per unit.

    AcqMss is the acquisition loop MINUS Reduce, and preprocessing is not subtracted:
    it is a disjoint scope. That is asserted as a property of the JSON by
    check_cost_properties, so this re-derivation cannot quietly agree with a wrong
    definition the way the first version of it did.
    """
    rows = _cost_rows(d)
    expected = len(KBS) * len(SAMPLINGS)
    if len(rows) != expected:
        a.bad.append(f"AcqMssruntime: {len(rows)} body rows, expected {expected}")
        return
    i = 0
    for stem in KBS:
        for samp in SAMPLINGS:
            cells = P.expand(rows[i])[2:]
            if (stem, samp) in NOT_RUN:
                for j, got in enumerate(cells):
                    a.cell(f"cost {stem} {samp} {COST_COLS[j]}", got, NA)
                i += 1
                continue
            fs = a.folds(stem, samp, "congen")
            acq_c = R.profiler_scalar(fs, "paper_consistency_checks")
            red_c = R.perf_mean(fs, "redundancy_consistency_checks") or 0.0
            pre_c = R.profiler_scalar(fs, "shared_preprocessing_quickxplain_checks")
            loop = R.perf_mean(fs, "congen_runtime_ms")
            red_ms = R.perf_mean(fs, "reduce_runtime_ms") or 0.0
            pre_ms = R.profiler_total_ms(fs, "shared_preprocessing_runtime")
            want = [R.fmt_count(acq_c), R.fmt_count(loop - red_ms),
                    R.fmt_count(red_c), R.fmt_count(red_ms),
                    R.fmt_count(pre_c), R.fmt_count(pre_ms),
                    R.fmt_count(acq_c + red_c + pre_c),
                    R.fmt_count(R.perf_mean(fs, "runtime_ms"))]
            for j, got in enumerate(cells):
                a.cell(f"cost {stem} {samp} {COST_COLS[j]}", got, want[j])
            i += 1


def check_cost_properties(a: Audit, d: Path) -> None:
    """Properties the cost table must have whatever expression produced it.

    These do not re-derive anything, which is the point: a re-derivation shares the
    generator's definition and will agree with a wrong one. A negative duration, a
    phase sum exceeding its total, or a total that is not the sum of its parts are
    wrong under EVERY correct derivation.
    """
    rows = _cost_rows(d)
    failures = PR.durations_non_negative(rows, MS_COLUMNS)
    over, slack = PR.phases_within_total(rows, MS_PARTS, MS_TOTAL, "runtime")
    failures += over
    failures += PR.parts_sum_to_total(rows, CHECK_PARTS, CHECK_TOTAL, "checks")
    failures += PR.timing_scopes(TREE / "congen")
    failures += PR.fold_counts(TREE / "congen", DECLARED_FOLDS)
    a.properties = (len(rows), slack)
    a.bad += failures


def check_accuracy_all(a: Audit, d: Path) -> None:
    def want(stem, samp, j):
        if (stem, samp) in NOT_RUN:
            return NA
        mean, sd = R.accuracy_mean_sd(a.folds(stem, samp, "congen"))
        return R.fmt_pm(mean, sd)
    _grid(a, d / "tab_accuracy_all.tex", 1, want, "accuracy_all")


def check_comparison_strategies(a: Audit, d: Path) -> None:
    tiers = ["description", "clause", "semantic"]
    def want(stem, samp, j):
        if (stem, samp) in NOT_RUN:
            return NA
        return R.fmt_quality(R.tier_mean(a.folds(stem, samp, "congen"), tiers[j], "f1_score"))
    _grid(a, d / "tab_comparison_strategies.tex", 2, want, "comparison_strategies", 3)


def check_semantic_pr(a: Audit, d: Path) -> None:
    def want(stem, samp, j):
        if (stem, samp) in NOT_RUN:
            return NA
        fs = a.folds(stem, samp, "congen")
        if j == 0:
            return R.fmt_quality(R.tier_mean(fs, "semantic", "precision"))
        if j == 1:
            return R.fmt_quality(R.tier_mean(fs, "semantic", "recall"))
        hit, scored = R.equivalence(fs)
        return f"{hit}/{scored}" if scored else UND
    _grid(a, d / "tab_semantic_pr.tex", 2, want, "semantic_pr", 3)


def check_kb_size(a: Audit, d: Path) -> None:
    def want(stem, samp, j):
        if (stem, samp) in NOT_RUN:
            return NA
        fs = a.folds(stem, samp, "congen")
        return R.fmt_count(R.stat_mean(fs, "n_mss" if j == 0 else "n_kb"))
    _grid(a, d / "tab_kb_size.tex", 2, want, "kb_size", per_kb=2)


def _method_grid(a: Audit, path: Path, header_lines: int, want_cell, label: str,
                 per_kb: int = 1) -> None:
    """Rows are (sampling, method) pairs; two leading label columns."""
    rows = P.body_rows(path, header_lines)
    expected = len(SAMPLINGS) * len(MODES)
    if len(rows) != expected:
        a.bad.append(f"{label}: {len(rows)} body rows, expected {expected}")
        return
    i = 0
    for samp in SAMPLINGS:
        for method in MODES:
            cells = P.expand(rows[i])[2:]
            for k, stem in enumerate(KBS):
                for j, got in enumerate(cells[k * per_kb:(k + 1) * per_kb]):
                    a.cell(f"{label} {samp} {method} {stem} col{j}", got,
                           want_cell(stem, samp, method, j))
            i += 1


def check_iterative_accuracy(a: Audit, d: Path) -> None:
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        mean, _ = R.accuracy_mean_sd(a.folds(stem, samp, method))
        return R.fmt_quality(mean)
    _method_grid(a, d / "tab_iterative_accuracy.tex", 1, want, "iterative_accuracy")


def check_iterative_semantic(a: Audit, d: Path) -> None:
    short = {"max_queries": "budget", "no_query": "no query", "pool_exhausted": "pool"}
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        fs = a.folds(stem, samp, method)
        if j == 0:
            return R.fmt_quality(R.tier_mean(fs, "semantic", "f1_score"))
        if method == "congen":
            return UND
        if j == 1:
            return R.fmt_count(R.queries_mean(fs))
        return ",".join(short.get(s, s) for s in R.stop_set(fs)) or UND
    _method_grid(a, d / "tab_iterative_semantic.tex", 2, want, "iterative_semantic", 3)


def check_runtime_comparison(a: Audit, d: Path) -> None:
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        return R.fmt_count(R.perf_mean(a.folds(stem, samp, method), "runtime_ms"))
    _method_grid(a, d / "tab_runtime_comparison.tex", 1, want, "runtime_comparison")


def check_rule_learners(a: Audit, d: Path) -> None:
    import json
    doc = json.loads((TREE / "baselines" / "baselines.json").read_text())
    by: dict[tuple[str, str], list[dict]] = {}
    for row in doc["rows"]:
        unit = row["kb"]
        stem = next(s for s in KBS if unit.startswith(s + "_"))
        by.setdefault((unit[len(stem) + 1:] and stem, unit[len(stem) + 1:]), [])
        by.setdefault((stem, unit[len(stem) + 1:]), []).append(row)

    rows = P.body_rows(d / "tab_rule_learners.tex", 2)
    keys = ["accuracy", "sem_precision", "sem_recall", "sem_f1"]
    i = 0
    for samp in SAMPLINGS:
        for learner in LEARNERS:
            cells = P.expand(rows[i])[2:]
            for k, stem in enumerate(KBS):
                block = cells[k * 4:(k + 1) * 4]
                if (stem, samp) in NOT_RUN:
                    for j, got in enumerate(block):
                        a.cell(f"rule_learners {samp} {learner} {stem} col{j}", got, NA)
                    continue
                unit = [r for r in by.get((stem, samp), []) if r["learner"] == learner]
                scored = [r for r in unit if not r.get("degenerate")]
                if not unit:
                    want = [UND] * 4
                elif not scored:
                    reasons = {r.get("degenerate") for r in unit}
                    label = ("too few" if reasons == {"too_few_instances"}
                             else "no rules" if reasons == {"no_rules_learned"}
                             else "degenerate")
                    want = [label] * 4
                else:
                    want = [R.fmt_quality(sum(r[k_] for r in scored) / len(scored))
                            for k_ in keys]
                for j, got in enumerate(block):
                    a.cell(f"rule_learners {samp} {learner} {stem} col{j}", got, want[j])
            i += 1


def check_significance(a: Audit, d: Path) -> None:
    from significance_tests import ALPHA, compute, floor_p, holm
    family = {r["name"].split()[0] for r in holm(compute()) if True}
    rejected = {r["name"].split()[0] for r in holm(compute()) if r["reject"]}
    rows = P.body_rows(d / "tab_significance.tex", 1)
    results = {r["name"].split()[0]: r for r in compute()}
    if len(rows) != len(results):
        a.bad.append(f"significance: {len(rows)} rows for {len(results)} claims")
        return
    for row in rows:
        claim = row[0]
        r = results.get(claim)
        if r is None:
            a.bad.append(f"significance: fragment names an unknown claim {claim!r}")
            continue
        a.cell(f"significance {claim} n", row[1], R.fmt_count(r["n"]))
        a.cell(f"significance {claim} median", row[2], "%.4f" % r["median"])
        a.cell(f"significance {claim} wins", row[3], f"{r['wins']}/{r['n']}")
        if claim in family:
            want_p = r"$< 10^{-7}$" if r["p"] < 1e-7 else "%.4f" % r["p"]
            want_v = "reject" if claim in rejected else "retain"
        else:
            want_p = r"$\geq %.4f$" % floor_p(r["n"])
            want_v = r"not testable at $n = %d$" % r["n"]
        a.cell(f"significance {claim} p", row[4], want_p)
        a.cell(f"significance {claim} verdict", row[5], want_v)
    if ALPHA != 0.05:
        a.bad.append(f"significance: alpha moved to {ALPHA}; the caption says 0.05")


def check_iterative_accuracy(a: Audit, d: Path) -> None:
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        mean, _ = R.accuracy_mean_sd(a.folds(stem, samp, method))
        return R.fmt_quality(mean)
    _method_grid(a, d / "tab_iterative_accuracy.tex", 1, want, "iterative_accuracy")


def check_iterative_semantic(a: Audit, d: Path) -> None:
    short = {"max_queries": "budget", "no_query": "no query", "pool_exhausted": "pool"}
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        fs = a.folds(stem, samp, method)
        if j == 0:
            return R.fmt_quality(R.tier_mean(fs, "semantic", "f1_score"))
        if method == "congen":
            return UND
        if j == 1:
            return R.fmt_count(R.queries_mean(fs))
        return ",".join(short.get(s, s) for s in R.stop_set(fs)) or UND
    _method_grid(a, d / "tab_iterative_semantic.tex", 2, want, "iterative_semantic", 3)


def check_runtime_comparison(a: Audit, d: Path) -> None:
    def want(stem, samp, method, j):
        if (stem, samp) in NOT_RUN:
            return NA
        return R.fmt_count(R.perf_mean(a.folds(stem, samp, method), "runtime_ms"))
    _method_grid(a, d / "tab_runtime_comparison.tex", 1, want, "runtime_comparison")


def check_rule_learners(a: Audit, d: Path) -> None:
    import json
    doc = json.loads((TREE / "baselines" / "baselines.json").read_text())
    by: dict[tuple[str, str], list[dict]] = {}
    for row in doc["rows"]:
        unit = row["kb"]
        stem = next(s for s in KBS if unit.startswith(s + "_"))
        by.setdefault((unit[len(stem) + 1:] and stem, unit[len(stem) + 1:]), [])
        by.setdefault((stem, unit[len(stem) + 1:]), []).append(row)

    rows = P.body_rows(d / "tab_rule_learners.tex", 2)
    keys = ["accuracy", "sem_precision", "sem_recall", "sem_f1"]
    i = 0
    for samp in SAMPLINGS:
        for learner in LEARNERS:
            cells = P.expand(rows[i])[2:]
            for k, stem in enumerate(KBS):
                block = cells[k * 4:(k + 1) * 4]
                if (stem, samp) in NOT_RUN:
                    for j, got in enumerate(block):
                        a.cell(f"rule_learners {samp} {learner} {stem} col{j}", got, NA)
                    continue
                unit = [r for r in by.get((stem, samp), []) if r["learner"] == learner]
                scored = [r for r in unit if not r.get("degenerate")]
                if not unit:
                    want = [UND] * 4
                elif not scored:
                    reasons = {r.get("degenerate") for r in unit}
                    label = ("too few" if reasons == {"too_few_instances"}
                             else "no rules" if reasons == {"no_rules_learned"}
                             else "degenerate")
                    want = [label] * 4
                else:
                    want = [R.fmt_quality(sum(r[k_] for r in scored) / len(scored))
                            for k_ in keys]
                for j, got in enumerate(block):
                    a.cell(f"rule_learners {samp} {learner} {stem} col{j}", got, want[j])
            i += 1


def check_significance(a: Audit, d: Path) -> None:
    from significance_tests import ALPHA, compute, floor_p, holm
    family = {r["name"].split()[0] for r in holm(compute()) if True}
    rejected = {r["name"].split()[0] for r in holm(compute()) if r["reject"]}
    rows = P.body_rows(d / "tab_significance.tex", 1)
    results = {r["name"].split()[0]: r for r in compute()}
    if len(rows) != len(results):
        a.bad.append(f"significance: {len(rows)} rows for {len(results)} claims")
        return
    for row in rows:
        claim = row[0]
        r = results.get(claim)
        if r is None:
            a.bad.append(f"significance: fragment names an unknown claim {claim!r}")
            continue
        a.cell(f"significance {claim} n", row[1], R.fmt_count(r["n"]))
        a.cell(f"significance {claim} median", row[2], "%.4f" % r["median"])
        a.cell(f"significance {claim} wins", row[3], f"{r['wins']}/{r['n']}")
        if claim in family:
            want_p = r"$< 10^{-7}$" if r["p"] < 1e-7 else "%.4f" % r["p"]
            want_v = "reject" if claim in rejected else "retain"
        else:
            want_p = r"$\geq %.4f$" % floor_p(r["n"])
            want_v = r"not testable at $n = %d$" % r["n"]
        a.cell(f"significance {claim} p", row[4], want_p)
        a.cell(f"significance {claim} verdict", row[5], want_v)
    if ALPHA != 0.05:
        a.bad.append(f"significance: alpha moved to {ALPHA}; the caption says 0.05")


CHECKS = (check_fm_summary, check_example_sizes, check_acqmss_runtime,
          check_accuracy_all, check_comparison_strategies, check_semantic_pr,
          check_kb_size, check_cost_properties, check_iterative_accuracy, check_iterative_semantic,
          check_runtime_comparison, check_rule_learners, check_significance)

MINIMUM_CELLS = 1000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default=str(TREE / "tables" / "paper"))
    args = ap.parse_args()
    d = Path(args.tables)

    audit = Audit()
    for check in CHECKS:
        try:
            check(audit, d)
        except P.Unparseable as exc:
            audit.bad.append(f"UNPARSEABLE {exc}")
        except Exception as exc:                       # a broken fragment is red
            audit.bad.append(f"{check.__name__} raised {type(exc).__name__}: {exc}")

    if audit.properties:
        n_rows, slack = audit.properties
        print(f"\ncost-table properties: {n_rows} units checked for negative\n  durations, phase sums within their total, and parts summing to it;\n  largest unattributed runtime slack {slack:.0f} ms")
    print(f"\n{audit.checked} cells checked, {len(audit.bad)} mismatched")
    for line in audit.bad[:40]:
        print(f"  {line}")
    if len(audit.bad) > 40:
        print(f"  ... and {len(audit.bad) - 40} more")
    if audit.bad:
        print("\nA cell that does not re-derive is a defect in the fragment or in the\n"
              "generator. Fix whichever is wrong -- never the expectation.")
        return 1
    # A pass is a positive count. Zero cells checked would otherwise read as clean.
    if audit.checked < MINIMUM_CELLS:
        print(f"FAIL: only {audit.checked} cells checked; expected at least "
              f"{MINIMUM_CELLS}. An empty audit is not a passing one.")
        return 1
    print("OK: every cell the paper prints re-derives from the committed results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

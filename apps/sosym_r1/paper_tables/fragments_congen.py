"""The fragments describing ConGen alone: inputs, cost, and learned-KB quality.

Every builder returns exactly one ``tabular`` environment. Rows are the six
sampling strategies in the paper's order and columns are $KB_1$..$KB_5$, unless
the quantity is per-KB only (``tab:fm_summary``), in which case the KBs are rows.
"""
from __future__ import annotations

from pathlib import Path

from . import latex as tex
from .frozen import (KB_LABELS, KNOWLEDGE_BASES, SAMPLINGS, TIERS, is_not_run)
from .read_results import ResultTree, bias_stats, example_sizes


def _grid(tree: ResultTree, value):
    """rows = sampling, columns = KB; ``value(folds, stem, samp)`` fills a cell."""
    rows = []
    for samp, samp_label in SAMPLINGS:
        cells = [samp_label]
        for stem, *_ in KNOWLEDGE_BASES:
            not_run = is_not_run(stem, samp)
            folds = [] if not_run else tree.require(stem, samp)
            cells.append(value(folds, stem, samp, not_run))
        rows.append(cells)
    return rows


def target_constraints(fm_dir: Path, stem: str) -> int:
    """|C_tau| in CONSTRAINTS for one model, counted from its UVL.

    The convention and the counter live in ``revision_target_theory_size``, which is
    also where the gate asserts them; importing it here keeps ONE definition rather
    than a generator copy that could drift from the checked one.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from revision_target_theory_size import count_by_owner_scan
    return count_by_owner_scan(fm_dir / f"{stem}.uvl")["total"]


def fm_summary(tree: ResultTree, data: Path) -> str:
    """#features, |C_tau|, |B| and the domain, one row per knowledge base.

    Static inputs, not results -- generated anyway so the gate covers them. |B| is read
    from the committed bias statistics rather than recounted here: that file is what the
    bias generator actually produced, and a second count of the same thing would be a
    second chance to be wrong. The clause count B expands to was dropped by the
    2026-09-23 review; it is still recorded in data/bias/<model>-bias-stats.txt.

    |C_tau| is COUNTED FROM THE UVL, and in CONSTRAINTS -- the unit of |KB|, so that
    the two can be compared. The paper prints the same value again in tab:kb_size's
    header; both come from this one function, so they cannot drift apart.
    """
    rows = []
    for stem, label, short, domain in KNOWLEDGE_BASES:
        s = bias_stats(data / "bias", stem)
        rows.append([f"{label} ({short})", tex.count(s["features"]),
                     tex.count(target_constraints(data / "fms", stem)),
                     tex.count(s["bias"]), domain])
    return tex.tabular("lrrrl",
                       [["", r"\#features", r"$|C_\tau|$", r"$|B|$", "domain"]], rows)


def example_sizes_table(tree: ResultTree, data: Path) -> str:
    """|E+| and |E-| per knowledge base and sampling strategy."""
    header = [[""] + [tex.multicolumn(2, lb) for lb in KB_LABELS],
              ["Strategy"] + [c for _ in KB_LABELS for c in (r"$|E^+|$", r"$|E^-|$")]]
    rules = [tex.cmidrules(len(KB_LABELS), 2), ""]
    rows = []
    for samp, samp_label in SAMPLINGS:
        cells = [samp_label]
        for stem, *_ in KNOWLEDGE_BASES:
            if is_not_run(stem, samp):
                # One marker spanning both columns: the unit was not run, so neither
                # |E+| nor |E-| exists, and two separate markers would suggest two
                # separate absences.
                cells.append(tex.multicolumn(2, tex.NA))
                continue
            sizes = example_sizes(data / "examples", stem, samp)
            cells += [tex.count(sizes[0]), tex.count(sizes[1])]
        rows.append(cells)
    return tex.tabular("l" + "rr" * len(KB_LABELS), header, rows, rules)


COST_HEADER = r"""% Cost per (knowledge base, sampling) unit. Every value is the MEAN OVER THE THREE
% FOLDS of the quantity named, computed from data/results_sosym_r1/congen/<unit>.json.
%
% column              unit    source / expression
% ------------------  ------  --------------------------------------------------------
% AcqMss checks       checks  folds[].performance.profiler.paper_consistency_checks
% AcqMss ms           ms      DERIVED: performance.congen_runtime_ms
%                                      - performance.reduce_runtime_ms
% Reduce checks       checks  folds[].performance.redundancy_consistency_checks
% Reduce ms           ms      folds[].performance.reduce_runtime_ms
% GenNE/QX checks     checks  profiler.shared_preprocessing_quickxplain_checks
% GenNE/QX ms         ms      profiler.shared_preprocessing_runtime.total x 1000
% total checks        checks  DERIVED: AcqMss + Reduce + GenNE/QX checks
% total ms            ms      folds[].performance.runtime_ms
%
% SCOPES, measured over all 84 folds rather than assumed -- this is the containment
% the one derived duration depends on, and getting it backwards printed a NEGATIVE
% AcqMss runtime for KB2 before it was checked:
%   reduce_runtime_ms is INSIDE congen_runtime_ms          (0 folds violate)
%   shared_preprocessing_runtime is DISJOINT from it       (0 folds violate)
%   congen_runtime_ms + preprocessing <= runtime_ms        (0 folds violate)
%   profiler.congen_total_time == performance.runtime_ms   (0 folds violate)
% So AcqMss is the acquisition loop minus Reduce, and preprocessing is NOT subtracted
% from the loop: it never was part of it.
%
% EVERY CELL IS A MEAN OVER ALL THREE FOLDS. Five folds carry no GenNE/QX counters
% at all: GenerateNE explains negative examples, and a training split with none never
% runs it, so generate_ne.py returns before the counters are created. Those folds
% contribute a measured ZERO and still count -- the phase ran zero times and cost
% zero, which is a measurement, not a gap. Reading the absence as "no data" and
% averaging over two folds instead would overstate the KB1 RS(m) preprocessing cost
% by half. The correspondence is exact in both directions over all 84 folds: the
% counters are absent in precisely the 5 folds whose training split has 0 negatives.
% A counter missing while negatives ARE present is a different fault, and both the
% generator and the gate raise on it rather than defaulting to zero.
%
% The three phase durations therefore sum to LESS than the total. The remainder is
% setup and teardown outside all three timing scopes (5.8 ms to 11.8 s across the
% folds); it is left unattributed rather than folded into a phase that did not spend it.
%
% profiler.acqmss_runtime is NOT used. It accumulates over thousands of nested
% recursive calls -- 149.9 s against a 15.2 s run on KB3 RS(n) -- so it is not a
% duration, and printing it beside one inflates AcqMss against Reduce, which is the
% one comparison this table exists to support.
"""


def _unit_cost(tree: ResultTree, stem: str, samp: str) -> dict[str, float | None]:
    """The eight cost quantities for one unit, as per-fold means."""
    folds = tree.require(stem, samp)
    checks = tree.phase_checks(folds)
    ms = tree.phases_ms(folds)
    return {"acqmss_checks": checks["acqmss"], "acqmss_ms": ms["acqmss"],
            "reduce_checks": checks["reduce"], "reduce_ms": ms["reduce"],
            "prep_checks": checks["preprocessing"], "prep_ms": ms["preprocessing"],
            "total_checks": checks["total"], "total_ms": ms["total"]}


# The five columns the paper prints, in its order. The per-phase durations that
# ``_unit_cost`` still computes are deliberately absent: see acqmss_runtime.
COST_COLUMNS = ("acqmss_checks", "reduce_checks", "prep_checks",
                "total_checks", "total_ms")


def acqmss_runtime(tree: ResultTree, data: Path) -> str:
    """Cost per unit: checks per phase, checks in total, and the total runtime.

    ONE ROW PER (knowledge base, sampling), blocked by knowledge base with the label
    printed once, which is how the paper reads it. The three PER-PHASE durations are
    no longer printed: the paper reports the phases in checks, which are
    machine-independent, and one total duration. They remain derivable from the JSON
    through ``_unit_cost`` and their scopes are still asserted by the gate, so
    dropping the columns loses a rendering and not a measurement.
    """
    rows = []
    for i, (stem, label, *_) in enumerate(KNOWLEDGE_BASES):
        if i:
            rows.append([tex.MIDRULE])
        for j, (samp, samp_label) in enumerate(SAMPLINGS):
            first = tex.multirow(len(SAMPLINGS), label) if j == 0 else ""
            if is_not_run(stem, samp):
                # One n/a spanning the five value columns, not five of them: the unit
                # was not run, and five separate markers read as five absences.
                rows.append([first, samp_label,
                             tex.multicolumn(len(COST_COLUMNS), tex.NA)])
                continue
            v = _unit_cost(tree, stem, samp)
            rows.append([first, samp_label] + [
                (tex.count(v[c]) if c.endswith("checks") else tex.millis(v[c]))
                for c in COST_COLUMNS])
    header = [["KB", "Strategy", r"\textsc{AcqMss}", r"\textsc{Reduce}",
               r"\textsc{GenerateNE}", "total checks", "total runtime"]]
    return COST_HEADER + tex.tabular("ll" + "r" * len(COST_COLUMNS), header, rows)


def accuracy_all(tree: ResultTree, data: Path) -> str:
    """Predictive accuracy, mean $\\pm$ standard deviation over the three folds."""
    def cell(folds, stem, samp, not_run):
        if not_run:
            return tex.NA
        mean, sd = tree.accuracy(folds)
        return tex.plus_minus(mean, sd)
    # Centred value columns, as the paper sets them: every cell is "mean $\\pm$ sd"
    # of the same width, so right-alignment buys nothing and reads ragged.
    return tex.tabular("l" + "c" * len(KB_LABELS),
                       [["Strategy", *KB_LABELS]], _grid(tree, cell))


def comparison_strategies(tree: ResultTree, data: Path) -> str:
    """F1 under each comparison strategy, and the semantic tier split into P and R.

    ONE TABLE. Precision and recall used to be a second fragment, and the exact
    equivalence rate a third column of it; the paper now prints the five quantities
    together and quotes the equivalence rate in prose instead. Equivalence is still
    asserted -- check_paper_numbers.py holds it at 1 of 84 -- so what was dropped is
    a column, not a claim.

    PER-FOLD MEAN, not the intersected knowledge base. The two are different
    quantities and the submitted table printed the second under a per-fold label.
    """
    header = [["", "", tex.multicolumn(3, "F1 by strategy"),
               tex.multicolumn(2, "semantic")],
              ["KB", "Strategy", "Desc", "Clause", "Sem", "P", "R"]]
    rules = [r"\cmidrule(lr){3-5} \cmidrule(lr){6-7}", ""]
    rows = []
    for i, (stem, label, *_) in enumerate(KNOWLEDGE_BASES):
        if i:
            rows.append([tex.MIDRULE])
        for j, (samp, samp_label) in enumerate(SAMPLINGS):
            # One label per block, as Table 9 sets it. The n/a rows stay INSIDE the
            # group: a knowledge base with two unevaluated samplings still has six
            # rows, and lifting them out would make KB5 look like a different shape.
            first = tex.multirow(len(SAMPLINGS), label) if j == 0 else ""
            if is_not_run(stem, samp):
                rows.append([first, samp_label, tex.multicolumn(5, tex.NA)])
                continue
            folds = tree.require(stem, samp)
            rows.append([first, samp_label]
                        + [tex.quality(tree.tier_f1(folds, t)) for t, _ in TIERS]
                        + [tex.quality(tree.semantic(folds, "precision")),
                           tex.quality(tree.semantic(folds, "recall"))])
    return tex.tabular("ll" + "rrrrr", header, rows, rules)


def kb_size(tree: ResultTree, data: Path) -> str:
    """|MSS| before Reduce and |KB| after it, both per-fold means.

    |KB| is ``statistics.n_kb`` as the corrected scorer defines it: the constraints
    the run finished with, negative-example constraints included where the run
    kept them. That policy is what the accuracy and F1 columns were scored against,
    so a different count here would not describe the same knowledge base.
    """
    # Three header rows: the KB, its target-theory size, then the two columns. |C_tau|
    # rides in the header because it is one number per knowledge base, not per cell,
    # and because |KB| is unreadable without it -- 177 delivered is a different story
    # against a target of 70 than against one of 905. Same counter as tab:fm_summary.
    header = [[""] + [tex.multicolumn(2, lb) for lb in KB_LABELS],
              [""] + [tex.multicolumn(2, rf"($|C_\tau|$={target_constraints(data / 'fms', stem)})")
                      for stem, *_ in KNOWLEDGE_BASES],
              # $|B'|$, not $|MSS|$: S6.2.3 names the unreduced subset B' and the
              # CABSC comparison rests on that name, so the column and the prose use
              # one symbol. The VALUE is unchanged -- statistics.n_mss either way.
              ["Strategy"] + [c for _ in KB_LABELS for c in (r"$|B'|$", r"$|KB|$")]]
    rules = ["", tex.cmidrules(len(KB_LABELS), 2), ""]
    rows = []
    for samp, samp_label in SAMPLINGS:
        cells = [samp_label]
        for stem, *_ in KNOWLEDGE_BASES:
            if is_not_run(stem, samp):
                cells.append(tex.multicolumn(2, tex.NA))
                continue
            folds = tree.require(stem, samp)
            cells += [tex.count(tree.statistic(folds, "n_mss")),
                      tex.count(tree.statistic(folds, "n_kb"))]
        rows.append(cells)
    return tex.tabular("l" + "rr" * len(KB_LABELS), header, rows, rules)

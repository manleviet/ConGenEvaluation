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


def fm_summary(tree: ResultTree, data: Path) -> str:
    """#features, |B|, #clauses and the domain, one row per knowledge base.

    Static inputs, not results -- generated anyway so the gate covers them. |B| and
    #clauses are read from the committed bias statistics rather than recounted
    here: those files are what the bias generator actually produced, and a second
    count of the same thing would be a second chance to be wrong.
    """
    rows = []
    for stem, label, short, domain in KNOWLEDGE_BASES:
        s = bias_stats(data / "bias", stem)
        rows.append([f"{label} ({short})", tex.count(s["features"]),
                     tex.count(s["bias"]), tex.count(s["clauses"]), domain])
    return tex.tabular("lrrrl",
                       [["", r"\#features", r"$|B|$", r"\#clauses", "domain"]], rows)


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


COST_COLUMNS = ("acqmss_checks", "acqmss_ms", "reduce_checks", "reduce_ms",
                "prep_checks", "prep_ms", "total_checks", "total_ms")


def acqmss_runtime(tree: ResultTree, data: Path) -> str:
    """Cost per unit: three phases and a total, in checks and milliseconds.

    One row per (knowledge base, sampling), like every other table, and one column per
    quantity. No aggregation over samplings: a mean across samplers would hide that
    2-COV costs ten consistency checks where RS(3n) costs thousands, and any narrower
    view the paper wants is derivable from this one without recomputing anything.
    """
    rows = []
    for stem, label, *_ in KNOWLEDGE_BASES:
        for samp, samp_label in SAMPLINGS:
            if is_not_run(stem, samp):
                rows.append([label, samp_label] + [tex.NA] * len(COST_COLUMNS))
                continue
            v = _unit_cost(tree, stem, samp)
            rows.append([label, samp_label] + [
                (tex.count(v[c]) if c.endswith("checks") else tex.millis(v[c]))
                for c in COST_COLUMNS])
    header = [["", "", tex.multicolumn(2, "AcqMss"), tex.multicolumn(2, r"\textsc{Reduce}"),
               tex.multicolumn(2, "GenNE / QX"), tex.multicolumn(2, "total")],
              ["KB", "Strategy"] + ["checks", "ms"] * 4]
    rules = [tex.cmidrules(4, 2, first_col=3), ""]
    return COST_HEADER + tex.tabular("ll" + "rr" * 4, header, rows, rules)


def accuracy_all(tree: ResultTree, data: Path) -> str:
    """Predictive accuracy, mean $\\pm$ standard deviation over the three folds."""
    def cell(folds, stem, samp, not_run):
        if not_run:
            return tex.NA
        mean, sd = tree.accuracy(folds)
        return tex.plus_minus(mean, sd)
    return tex.tabular("l" + "r" * len(KB_LABELS),
                       [["Strategy", *KB_LABELS]], _grid(tree, cell))


def comparison_strategies(tree: ResultTree, data: Path) -> str:
    """F1 under each of the three comparison strategies.

    PER-FOLD MEAN, not the intersected knowledge base. The two are different
    quantities and the submitted table printed the second under a per-fold label.
    """
    header = [[""] + [tex.multicolumn(3, lb) for lb in KB_LABELS],
              ["Strategy"] + [short for _ in KB_LABELS for _t, short in TIERS]]
    rules = [tex.cmidrules(len(KB_LABELS), 3), ""]
    rows = []
    for samp, samp_label in SAMPLINGS:
        cells = [samp_label]
        for stem, *_ in KNOWLEDGE_BASES:
            if is_not_run(stem, samp):
                cells.append(tex.multicolumn(3, tex.NA))
                continue
            folds = tree.require(stem, samp)
            cells += [tex.quality(tree.tier_f1(folds, t)) for t, _ in TIERS]
        rows.append(cells)
    return tex.tabular("l" + "rrr" * len(KB_LABELS), header, rows, rules)


def semantic_pr(tree: ResultTree, data: Path) -> str:
    """Semantic precision, recall, and exact equivalence as attained/scored.

    ONE TABLE, not two. Precision and recall are the two halves of the semantic
    tier and are read together; exact equivalence is the same question asked at
    its strictest, and a reader who sees 1.000 recall beside 0/3 equivalence has
    learned something that two separate tables would have kept apart.
    """
    header = [[""] + [tex.multicolumn(3, lb) for lb in KB_LABELS],
              ["Strategy"] + [c for _ in KB_LABELS for c in ("P", "R", "eq.")]]
    rules = [tex.cmidrules(len(KB_LABELS), 3), ""]
    rows = []
    for samp, samp_label in SAMPLINGS:
        cells = [samp_label]
        for stem, *_ in KNOWLEDGE_BASES:
            if is_not_run(stem, samp):
                cells.append(tex.multicolumn(3, tex.NA))
                continue
            folds = tree.require(stem, samp)
            attained, scored = tree.exact_equivalence(folds)
            cells += [tex.quality(tree.semantic(folds, "precision")),
                      tex.quality(tree.semantic(folds, "recall")),
                      (f"{attained}/{scored}" if scored else tex.UNDEFINED)]
        rows.append(cells)
    return tex.tabular("l" + "rrr" * len(KB_LABELS), header, rows, rules)


def kb_size(tree: ResultTree, data: Path) -> str:
    """|MSS| before Reduce and |KB| after it, both per-fold means.

    |KB| is ``statistics.n_kb`` as the corrected scorer defines it: the constraints
    the run finished with, negative-example constraints included where the run
    kept them. That policy is what the accuracy and F1 columns were scored against,
    so a different count here would not describe the same knowledge base.
    """
    header = [[""] + [tex.multicolumn(2, lb) for lb in KB_LABELS],
              ["Strategy"] + [c for _ in KB_LABELS for c in (r"$|MSS|$", r"$|KB|$")]]
    rules = [tex.cmidrules(len(KB_LABELS), 2), ""]
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

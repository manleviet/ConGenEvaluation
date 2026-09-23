"""The fragments comparing ConGen against the iterative and rule-learner baselines.

Rows here are (sampling, method) pairs rather than sampling alone, because a method
is not a property of a cell -- it is a thing being compared, and collapsing it into
a column group makes the six-sampling reading order impossible to keep.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import latex as tex
from .frozen import KB_LABELS, KNOWLEDGE_BASES, LEARNERS, METHODS, SAMPLINGS, is_not_run
from .read_results import ResultTree


def _method_folds(tree: ResultTree, stem: str, samp: str, method: str):
    if method == "congen":
        return tree.require(stem, samp)
    return tree.iterative_folds(stem, samp, method)


def _ruled(rows: list[list[str]]) -> list[list[str]]:
    """A rule between sampling blocks, as the paper sets these tables.

    The blocks are three rows each -- one per method -- and the rule goes BETWEEN
    them, never before the first: that one is the header rule the tabular writes.
    """
    out: list[list[str]] = []
    for i, row in enumerate(rows):
        if i and i % len(METHODS) == 0:
            out.append([tex.MIDRULE])
        out.append(list(row))
    return out


def _method_rows(tree: ResultTree, cell_fn, bold: bool = False):
    """One row per (sampling, method); ``cell_fn(folds) -> (text, value|None)``."""
    rows = []
    for samp, samp_label in SAMPLINGS:
        for i, (method, method_label) in enumerate(METHODS):
            head = [tex.multirow(len(METHODS), samp_label) if i == 0 else "",
                    method_label]
            texts, values = [], []
            for stem, *_ in KNOWLEDGE_BASES:
                if is_not_run(stem, samp):
                    texts.append(tex.NA)
                    values.append(None)
                    continue
                text, value = cell_fn(_method_folds(tree, stem, samp, method))
                texts.append(text)
                values.append(value)
            rows.append((head, texts, values))
    if not bold:
        return _ruled([h + t for h, t, _ in rows])
    # Bold is computed per (sampling, KB) across the three methods, so it has to be
    # decided after all three rows exist. Hand-bolding a winner is how a claim with
    # no derivation behind it survives every regeneration.
    out = [list(h + t) for h, t, _ in rows]
    for block in range(0, len(rows), len(METHODS)):
        group = rows[block:block + len(METHODS)]
        for col in range(len(KB_LABELS)):
            column = [g[2][col] for g in group]
            marked = tex.bold_max([g[1][col] for g in group], column)
            for k, value in enumerate(marked):
                out[block + k][2 + col] = value
    return _ruled(out)


def iterative_accuracy(tree: ResultTree, data: Path) -> str:
    """Predictive accuracy for ConGen and the two iterative modes.

    Six sampling strategies, not four. The submitted paper printed four; nothing
    ever decided to drop the other two, so they are not inherited as dropped.
    """
    def cell(folds):
        mean, _sd = tree.accuracy(folds)
        return tex.quality(mean), mean
    return tex.tabular("ll" + "r" * len(KB_LABELS),
                       [["Strategy", "Method", *KB_LABELS]],
                       _method_rows(tree, cell, bold=True))


def iterative_semantic(tree: ResultTree, data: Path) -> str:
    """Semantic F1 and the oracle queries consumed, for the three methods.

    ONE TABLE. Queries used to be a second table and the stopping rule a third
    column; the paper now prints F1 beside q and states the stopping rules in the
    caption, where a rule that is the same on 84 folds belongs. The rules are still
    asserted, per fold, by the numbers gate -- what moved is a rendering.

    ConGen's q cells are EMPTY, not ``--``. ConGen issues no query, and a dash set
    beside a number column reads as a minus sign.
    """
    header = [["", ""] + [tex.multicolumn(2, lb) for lb in KB_LABELS],
              ["Strategy", "Method"] + [c for _ in KB_LABELS for c in ("F1", "q")]]
    # Two label columns, so the grouped rules start at column 3.
    rules = [tex.cmidrules(len(KB_LABELS), 2, first_col=3), ""]
    rows = []
    for samp, samp_label in SAMPLINGS:
        block = []
        for i, (method, method_label) in enumerate(METHODS):
            cells = [tex.multirow(len(METHODS), samp_label) if i == 0 else "",
                     method_label]
            f1s = []
            for stem, *_ in KNOWLEDGE_BASES:
                if is_not_run(stem, samp):
                    # One n/a across both columns: the unit was not run, and two
                    # markers read as two separate absences.
                    cells.append(tex.multicolumn(2, tex.NA))
                    f1s.append(None)
                    continue
                folds = _method_folds(tree, stem, samp, method)
                f1 = tree.tier_f1(folds, "semantic")
                f1s.append(f1)
                cells += [tex.quality(f1),
                          "" if method == "congen" else tex.count(tree.queries(folds))]
            block.append((cells, f1s))
        # Bold is computed per (sampling, KB) across the three methods, after all
        # three rows exist. The F1 column of KB k sits at 2 + 2k once every earlier
        # KB has contributed its pair -- except where an n/a collapsed the pair into
        # one cell, which is why the index is taken from the row rather than assumed.
        for col in range(len(KB_LABELS)):
            marked = tex.bold_max([_f1_cell(b[0], col) for b in block],
                                  [b[1][col] for b in block])
            for k, value in enumerate(marked):
                _set_f1_cell(block[k][0], col, value)
        rows += [b[0] for b in block]
    # Ruled once, over the whole body: _ruled counts three-row blocks, so calling it
    # per block would never reach a boundary and would emit no rule at all.
    return tex.tabular("ll" + "rr" * len(KB_LABELS), header, _ruled(rows), rules)


def _f1_index(cells: list[str], kb: int) -> int:
    """Where knowledge base ``kb``'s F1 cell sits, counting collapsed n/a pairs."""
    i = 2
    for _ in range(kb):
        i += 1 if cells[i].startswith(r"\multicolumn") else 2
    return i


def _f1_cell(cells: list[str], kb: int) -> str:
    cell = cells[_f1_index(cells, kb)]
    return "" if cell.startswith(r"\multicolumn") else cell


def _set_f1_cell(cells: list[str], kb: int, value: str) -> None:
    i = _f1_index(cells, kb)
    if not cells[i].startswith(r"\multicolumn"):
        cells[i] = value


def runtime_comparison(tree: ResultTree, data: Path) -> str:
    """Total runtime in milliseconds, PER-FOLD MEAN, for the three methods.

    Per-fold mean, not the 3-fold total: every other quantity in this table set is
    a per-fold mean, and one column on a different aggregation is exactly the mix
    the standing rule exists to prevent. The paper's caption has to say so.
    """
    def cell(folds):
        ms = tree.runtime_ms(folds)
        return tex.millis(ms), None      # no argmax: fastest is not "best" here
    return tex.tabular("ll" + "r" * len(KB_LABELS),
                       [["Strategy", "Method", *KB_LABELS]],
                       _method_rows(tree, cell))


def rule_learners(tree: ResultTree, data: Path, baselines: Path) -> str:
    """Accuracy and semantic P/R/F1 per (knowledge base, strategy, learner).

    ONE ROW PER LEARNER, and only the combinations that were scored. A cell is
    scored when both classes carry at least ten training instances -- a threshold
    declared before any number existed -- and that holds on 8 of the 28
    combinations, all of them random sampling. The other 20 are absent rather than
    marked: a grid of twenty "too few" markers is a table about the threshold, not
    about the learners.

    The knowledge base and the strategy are printed on the first row of each block,
    as the paper sets them.
    """
    rows_by_cell: dict[tuple[str, str, str], list[dict]] = {}
    doc = json.loads(baselines.read_text())
    for row in doc["rows"]:
        stem, samp = _split_unit(row["kb"])
        rows_by_cell.setdefault((stem, samp, row["learner"]), []).append(row)

    scored = [(stem, samp) for stem, *_ in KNOWLEDGE_BASES for samp, _ in SAMPLINGS
              if any(not r.get("degenerate")
                     for learner, _ in LEARNERS
                     for r in rows_by_cell.get((stem, samp, learner), []))]

    label_of = {stem: label for stem, label, *_ in KNOWLEDGE_BASES}
    samp_label_of = dict(SAMPLINGS)
    body: list[list[str]] = []
    for block, (stem, samp) in enumerate(scored):
        if block:
            body.append([tex.MIDRULE])
        for i, (learner, learner_label) in enumerate(LEARNERS):
            head = ([label_of[stem], samp_label_of[samp]] if i == 0 else ["", ""])
            body.append(head + [learner_label]
                        + _learner_cells(rows_by_cell.get((stem, samp, learner), [])))
    header = [["KB", "Strategy", "Learner", "acc.", "P", "R", "F1"]]
    return tex.tabular("lll" + "rrrr", header, body)


def _split_unit(unit: str) -> tuple[str, str]:
    """``busybox-1.18.0_rs_1n`` -> (``busybox-1.18.0``, ``rs_1n``)."""
    for stem, *_ in KNOWLEDGE_BASES:
        if unit.startswith(stem + "_"):
            return stem, unit[len(stem) + 1:]
    raise ValueError(f"baselines row names an unknown unit: {unit!r}")


def _learner_cells(rows: list[dict]) -> list[str]:
    scored = [r for r in rows if not r.get("degenerate")]
    if not rows:
        return [tex.UNDEFINED] * 4
    if not scored:
        reasons = {r.get("degenerate") for r in rows}
        label = ("too few" if reasons == {"too_few_instances"}
                 else "no rules" if reasons == {"no_rules_learned"} else "degenerate")
        return [tex.multicolumn(4, label)]
    mean = lambda k: (sum(r[k] for r in scored) / len(scored))  # noqa: E731
    return [tex.quality(mean("accuracy")), tex.quality(mean("sem_precision")),
            tex.quality(mean("sem_recall")), tex.quality(mean("sem_f1"))]


def significance(compute, holm, floor_p, alpha: float) -> str:
    """Claim, n, median difference, wins, p, and the Holm verdict.

    Computed by calling the significance module, never by re-deriving the tests
    here: a second implementation of a statistic is a second statistic.

    Claim 2 prints as NOT TESTABLE rather than "not significant". At n = 5 the
    exact test's smallest attainable p is 0.0625, above alpha, so no outcome could
    reject -- that is a property of the design, and rendering it as a negative
    result would report an absence as a finding.
    """
    family = {r["name"].split()[0]: r for r in holm(compute())}
    rows = []
    for r in compute():
        claim = r["name"].split()[0]
        n, p = r["n"], r["p"]
        in_family = claim in family
        if not in_family:
            verdict = rf"not testable at $n = {n}$"
            p_text = rf"$\geq {floor_p(n):.4f}$"
        else:
            verdict = "reject" if family[claim]["reject"] else "retain"
            p_text = (r"$< 10^{-7}$" if p < 1e-7 else f"{p:.4f}")
        rows.append([claim, tex.count(n), f"{r['median']:.4f}",
                     f"{r['wins']}/{n}", p_text, verdict])
    return tex.tabular("lrrrrl",
                       [["Claim", "$n$", "median $\\Delta$", "wins", "$p$",
                         rf"Holm ($\alpha = {alpha}$)"]], rows)

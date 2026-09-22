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


def _method_rows(tree: ResultTree, cell_fn, bold: bool = False):
    """One row per (sampling, method); ``cell_fn(folds) -> (text, value|None)``."""
    rows = []
    for samp, samp_label in SAMPLINGS:
        for i, (method, method_label) in enumerate(METHODS):
            head = [samp_label if i == 0 else "", method_label]
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
        return [h + t for h, t, _ in rows]
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
    return out


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
    """Semantic F1 for the three methods, with queries consumed and stopping rule.

    The two extra quantities are IN THE TABLE, not in a footnote. An F1 cannot tell
    the three stopping rules apart, and the three mean different things: a gap at
    ``no_query`` is the active baseline having asked every question available to it
    and still losing, which is a stronger result than a gap at ``max_queries``.
    ConGen issues no queries at all -- it is passive -- so its two cells are ``--``,
    an absence by definition rather than a measurement of zero.
    """
    stop_short = {"max_queries": "budget", "no_query": "no query",
                  "pool_exhausted": "pool"}
    header = [[""] + [tex.multicolumn(3, lb) for lb in KB_LABELS],
              ["Strategy", "Method"] + [c for _ in KB_LABELS
                                        for c in ("F1", "q", "stop")]]
    # Column 1 and 2 are the two label columns, so the grouped rules start at 3.
    rules = [tex.cmidrules(len(KB_LABELS), 3, first_col=3), ""]
    header[0] = ["", ""] + header[0][1:]

    rows = []
    for samp, samp_label in SAMPLINGS:
        block = []
        for i, (method, method_label) in enumerate(METHODS):
            cells = [samp_label if i == 0 else "", method_label]
            f1s = []
            for stem, *_ in KNOWLEDGE_BASES:
                if is_not_run(stem, samp):
                    cells += [tex.NA, tex.NA, tex.NA]
                    f1s.append(None)
                    continue
                folds = _method_folds(tree, stem, samp, method)
                f1 = tree.tier_f1(folds, "semantic")
                f1s.append(f1)
                if method == "congen":
                    cells += [tex.quality(f1), tex.UNDEFINED, tex.UNDEFINED]
                else:
                    stops = tree.stop_reasons(folds)
                    cells += [tex.quality(f1), tex.count(tree.queries(folds)),
                              ",".join(stop_short.get(s, s) for s in stops) or tex.UNDEFINED]
            block.append((cells, f1s))
        for col in range(len(KB_LABELS)):
            marked = tex.bold_max([b[0][2 + col * 3] for b in block],
                                  [b[1][col] for b in block])
            for k, value in enumerate(marked):
                block[k][0][2 + col * 3] = value
        rows += [b[0] for b in block]
    return tex.tabular("ll" + "rrl" * len(KB_LABELS), header, rows, rules)


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
    """Accuracy and semantic P/R/F1 for RIPPER, CN2 and a decision tree.

    Degenerate cells are MARKED, never scored. ``too few`` means a fold had fewer
    than ten training instances of one class, so the learner was never asked; it is
    not a score of zero, and printing 0.000 there would be a measurement the run
    never made. The threshold was declared before any number existed.
    """
    rows_by_cell: dict[tuple[str, str, str], list[dict]] = {}
    doc = json.loads(baselines.read_text())
    for row in doc["rows"]:
        kb = row["kb"]
        stem, samp = _split_unit(kb)
        rows_by_cell.setdefault((stem, samp, row["learner"]), []).append(row)

    header = [[""] + [tex.multicolumn(4, lb) for lb in KB_LABELS],
              ["Strategy", "Learner"] + [c for _ in KB_LABELS
                                         for c in ("acc.", "P", "R", "F1")]]
    header[0] = ["", ""] + header[0][1:]
    rules = [tex.cmidrules(len(KB_LABELS), 4, first_col=3), ""]
    body = []
    for samp, samp_label in SAMPLINGS:
        for i, (learner, learner_label) in enumerate(LEARNERS):
            cells = [samp_label if i == 0 else "", learner_label]
            for stem, *_ in KNOWLEDGE_BASES:
                if is_not_run(stem, samp):
                    cells.append(tex.multicolumn(4, tex.NA))
                    continue
                cells += _learner_cells(rows_by_cell.get((stem, samp, learner), []))
            body.append(cells)
    return tex.tabular("ll" + "rrrr" * len(KB_LABELS), header, body, rules)


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

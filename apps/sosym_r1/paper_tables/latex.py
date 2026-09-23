"""Number formatting and tabular assembly — one rule, applied everywhere.

The formatting rules were measured from the manuscript's majority and then applied
without exception, because the alternative is a reader inferring meaning from a
difference that is only typographic. Three decimals with a leading zero for every
quality metric; ``{,}`` thousands separators for counts and milliseconds; ``$\\pm$``
for a standard deviation the paper prints.

Bold is COMPUTED (:func:`bold_max`), never hand-applied. A hand-bolded cell is a
claim with no derivation behind it, and it survives every regeneration.
"""
from __future__ import annotations

from .frozen import NA, UNDEFINED

# A body row holding only this is emitted as a rule, not as a row of cells.
MIDRULE = r"\midrule"


def quality(value: float | None, not_run: bool = False) -> str:
    """A metric in [0, 1]: three decimals, leading zero kept.

    ``None`` is an absence, and the two kinds of absence are different facts: the
    unit was never run (``n/a``) or it ran and this quantity has no meaning there
    (``--``). Neither is ever rendered as 0.000.
    """
    if value is None:
        return NA if not_run else UNDEFINED
    return f"{value:.3f}"


def count(value: float | None, not_run: bool = False) -> str:
    """An integer count, rounded, with LaTeX-safe thousands separators."""
    if value is None:
        return NA if not_run else UNDEFINED
    return _thousands(int(round(value)))


def millis(value: float | None, not_run: bool = False) -> str:
    """A duration in milliseconds, rounded to whole ms."""
    return count(value, not_run)


def plus_minus(mean: float | None, sd: float | None, not_run: bool = False) -> str:
    """``mean $\\pm$ sd``, both to three decimals."""
    if mean is None:
        return NA if not_run else UNDEFINED
    if sd is None:
        return quality(mean)
    return f"{mean:.3f} $\\pm$ {sd:.3f}"


def _thousands(n: int) -> str:
    """``1755`` -> ``1{,}755``.

    ``{,}`` rather than a bare comma: in maths mode a bare comma is a punctuation
    atom and TeX sets a thin space after it, so ``1,755`` renders as ``1, 755``.
    The paper already uses this spelling; it is reproduced rather than reinvented.
    """
    s = f"{abs(n):,}".replace(",", "{,}")
    return f"-{s}" if n < 0 else s


def bold_max(cells: list[str], values: list[float | None]) -> list[str]:
    """Bold the cell holding the largest value; leave the rest alone.

    Ties are all bolded, because picking one of equal values would be an editorial
    choice dressed as a measurement. Absences never win: ``None`` is not a value.
    """
    present = [v for v in values if v is not None]
    if not present:
        return cells
    top = max(present)
    return [rf"\textbf{{{c}}}" if v is not None and v == top else c
            for c, v in zip(cells, values)]


def tabular(colspec: str, header_rows: list[list[str]], body_rows: list[list[str]],
            rules: list[str] | None = None) -> str:
    """One ``tabular`` environment, booktabs-ruled, and nothing around it.

    The caption, ``\\label`` and ``table*`` wrapper stay in the manuscript: those are
    editorial and belong where the prose is. What is generated is only what is
    derived from data.
    """
    out = [rf"\begin{{tabular}}{{{colspec}}}", r"\toprule"]
    for i, row in enumerate(header_rows):
        out.append(" & ".join(row) + r" \\")
        if rules and i < len(rules) and rules[i]:
            out.append(rules[i])
    out.append(r"\midrule")
    for row in body_rows:
        # A one-cell row holding a rule is a SEPARATOR, emitted verbatim. The paper
        # rules between knowledge-base blocks, and parse_tex skips rule lines, so the
        # gate reads the same rows either way.
        if len(row) == 1 and row[0] in (r"\midrule", r"\addlinespace"):
            out.append(row[0])
            continue
        out.append(" & ".join(row) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


def cmidrules(n_groups: int, width: int, first_col: int = 2) -> str:
    """``\\cmidrule(lr){2-4} \\cmidrule(lr){5-7} ...`` for grouped column headers."""
    parts = []
    c = first_col
    for _ in range(n_groups):
        parts.append(rf"\cmidrule(lr){{{c}-{c + width - 1}}}")
        c += width
    return " ".join(parts)


def multicolumn(span: int, text: str, align: str = "c") -> str:
    return rf"\multicolumn{{{span}}}{{{align}}}{{{text}}}"


def multirow(span: int, text: str) -> str:
    """``\multirow{6}{*}{$KB_1$}`` -- one label for a block of rows.

    The manuscript prints the knowledge base once per block rather than once per row.
    It needs the ``multirow`` package, which the manuscript already loads; the
    fragment carries no preamble, so this is the one place the dependency is named.
    """
    return rf"\multirow{{{span}}}{{*}}{{{text}}}"

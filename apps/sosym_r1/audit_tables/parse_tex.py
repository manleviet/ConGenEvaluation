"""Parse an emitted fragment back into rows of cells.

A fragment that cannot be parsed is RED, never skipped. An unparseable table and a
table full of wrong numbers look the same to a gate that shrugs at the first and
reports nothing -- and "nothing to check" has already read as "everything checks
out" twice in this project.
"""
from __future__ import annotations

import re
from pathlib import Path

RULE_LINES = (r"\toprule", r"\midrule", r"\bottomrule")


class Unparseable(Exception):
    """The fragment is not one tabular of rows and cells."""


def rows_of(path: Path) -> list[list[str]]:
    """Every ``a & b & c \\\\`` line, split into stripped cells."""
    if not path.exists():
        raise Unparseable(f"{path} does not exist")
    text = path.read_text()
    if text.count(r"\begin{tabular}") != 1 or text.count(r"\end{tabular}") != 1:
        raise Unparseable(f"{path.name} must hold exactly one tabular environment")

    out: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        # A leading %-comment block carries each column's JSON path, unit and, for a
        # derived column, its expression. It is documentation of the derivation and
        # lives with the numbers rather than in a report nobody will have open.
        if not s or s.startswith("%") or s.startswith(RULE_LINES) or s.startswith(r"\cmidrule"):
            continue
        if s.startswith((r"\begin{tabular}", r"\end{tabular}")):
            continue
        if not s.endswith(r"\\"):
            raise Unparseable(f"{path.name}: line is neither a rule nor a row: {s!r}")
        out.append([c.strip() for c in s[:-2].split("&")])
    if not out:
        raise Unparseable(f"{path.name}: tabular holds no rows")
    return out


def body_rows(path: Path, header_lines: int) -> list[list[str]]:
    rows = rows_of(path)
    if len(rows) <= header_lines:
        raise Unparseable(f"{path.name}: {len(rows)} rows, expected more than "
                          f"{header_lines} header row(s)")
    return rows[header_lines:]


_MULTICOL = re.compile(r"^\\multicolumn\{(\d+)\}\{[^}]*\}\{(.*)\}$")
_BOLD = re.compile(r"^\\textbf\{(.*)\}$")


def unwrap(cell: str) -> tuple[str, int]:
    """Strip ``\\multicolumn`` and ``\\textbf``; return (text, column span).

    Bold is stripped before comparison on purpose. Whether a cell is bold is a
    separate assertion -- it is an argmax over the compared methods -- and folding
    it into the value comparison would let a wrongly bolded cell fail as if its
    number were wrong.
    """
    span = 1
    m = _MULTICOL.match(cell)
    if m:
        span, cell = int(m.group(1)), m.group(2).strip()
    b = _BOLD.match(cell)
    if b:
        cell = b.group(1).strip()
    return cell, span


def expand(row: list[str]) -> list[str]:
    """Row with each ``\\multicolumn{n}`` repeated n times, so columns line up."""
    out: list[str] = []
    for cell in row:
        text, span = unwrap(cell)
        out += [text] * span
    return out


def bolded(cell: str) -> bool:
    text, _ = (_MULTICOL.match(cell).group(2).strip(), 0) if _MULTICOL.match(cell) else (cell, 0)
    return bool(_BOLD.match(text.strip()))

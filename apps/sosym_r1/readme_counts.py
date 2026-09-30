"""The README states each gate's final count; the gate holds it to that.

The README tells a reader what count to expect from each gate ("412 checks -- the count
it prints"), so the reader can compare one line with their own run. A count written by
hand and checked by nobody drifts the first time a check is added -- and that already
happened once: a README went out stating counts its own gates no longer printed. Each
gate therefore compares the number it just printed with the README's sentence.

A tree whose README states no such count (the development repository) is reported as a
skip, by name, never silently passed.
"""
from __future__ import annotations

import re
from pathlib import Path


def stated(repo: Path, pattern: str) -> int | None:
    """The count the README states for `pattern` (one capture group), or None."""
    readme = repo / 'README.md'
    if not readme.exists():
        return None
    found = re.findall(pattern, readme.read_text())
    if len(found) > 1:
        raise ValueError(f'README.md states {pattern!r} {len(found)} times; expected once')
    return int(found[0].replace(',', '')) if found else None


def mismatch(repo: Path, pattern: str, got: int, what: str) -> str | None:
    """A failure message if the README states a different count; prints a skip if none."""
    want = stated(repo, pattern)
    if want is None:
        print(f'  [skip] README.md states no {what} count here')
        return None
    if want != got:
        return f'README.md states {want:,} {what}, this run printed {got:,}'
    print(f'  [ok  ] README.md states {want:,} {what}, as printed')
    return None

"""Atomic file writes — never truncate a good file on a mid-write crash.

Every result/table/data writer routes through here. A plain ``open(path, 'w')``
truncates the target the instant it opens: a crash between then and the final
write — a SAT4J timeout that now *raises* (it used to be swallowed), a killed
three-hour eval, a Ctrl-C — would leave a zero-length or half-written file where
a good one was. These helpers write to a temp file in the **same directory**,
``fsync`` it, then ``os.replace`` (an atomic rename on POSIX), so the target is
either fully replaced or left completely intact — the previous good file is never
at risk.

``atomic_write`` is the primitive (a context manager yielding a writable handle);
``write_text_atomic`` / ``write_json_atomic`` are thin wrappers. Line-by-line
writers just swap ``open(path, 'w')`` for ``atomic_write(path)`` — their body is
unchanged.

Scope of the guarantee: the file content is fsynced, but the parent directory is
not fsynced after ``os.replace``. That makes it robust against a **process** dying
mid-write (our threat model — ``SolverTimeoutError``, Ctrl-C, OOM), not against a
sudden power loss (the rename may not yet be durable on disk). That trade-off is
deliberate for a research repo; do not read it as full crash-consistency.

Lives at the ``conacq`` root, not under ``apps/`` or ``eval/``: app scripts,
``conacq/eval``, ``conacq/bias`` and ``conacq/examples`` all write files, and
putting it in ``apps`` would force those packages to import ``apps`` (a backwards
layer dependency). It imports only stdlib, so nothing imports back into it.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Union


@contextmanager
def atomic_write(path: Union[str, Path], encoding: str = "utf-8"):
    """Yield a writable text handle whose contents land at *path* atomically.

    Writes to a temp file in the target's own directory (``os.replace`` is only
    atomic within a single filesystem — a system temp dir may be a different
    mount), flushes + fsyncs on success, then atomically renames over the target.
    If the body raises (exception, ``KeyboardInterrupt``), the original file is
    untouched and the temp is removed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            yield f
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # The original at `path` was never opened for writing; drop the temp.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path: Union[str, Path], text: str, encoding: str = "utf-8") -> None:
    """Write *text* to *path* atomically."""
    with atomic_write(path, encoding) as f:
        f.write(text)


def write_json_atomic(path: Union[str, Path], data: Any, indent: int = 2) -> None:
    """Serialize *data* to JSON (``indent=2`` by default) and write it atomically.

    Uses the same ``json.dump(..., indent=2)`` as the plain writes it replaces, so
    the frozen on-disk export is byte-for-byte unchanged.
    """
    with atomic_write(path) as f:
        json.dump(data, f, indent=indent)


def read_json(path: Union[str, Path]) -> Any:
    """Read and parse a JSON file (utf-8) — the read side symmetric to
    ``write_json_atomic``, so both IO classes share one ``open + json.load``
    instead of duplicating it. Raises ``FileNotFoundError`` / ``json.JSONDecodeError``
    exactly as the plain reads it replaces (behaviour-inert)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

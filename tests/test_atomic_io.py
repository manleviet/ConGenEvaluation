"""Atomic-write safety net — a mid-write crash must never destroy a good file.

The whole point of `conacq.atomic_io` is that the previous good result file
survives a crash between "start writing" and "done". These tests prove it by
forcing the failure and checking the original is byte-for-byte intact.
"""
import io
import json
import os

import pytest

from conacq.atomic_io import atomic_write, write_json_atomic, write_text_atomic


def test_original_intact_when_rename_crashes(tmp_path, monkeypatch):
    """A crash at the final os.replace leaves the previous file untouched."""
    target = tmp_path / "result.json"
    target.write_text(json.dumps({"good": "original"}, indent=2))
    before = target.read_bytes()

    def boom(*_a, **_k):
        raise RuntimeError("crash mid-write")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError):
        write_json_atomic(target, {"new": "half-written", "big": list(range(1000))})

    assert target.read_bytes() == before                     # original untouched
    assert list(tmp_path.glob(".result.json.*")) == []       # no temp litter left


def test_original_intact_when_serialization_fails(tmp_path):
    """Non-serializable data raises before any file op — original survives."""
    target = tmp_path / "result.json"
    target.write_text("ORIGINAL")

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        write_json_atomic(target, {"bad": Unserializable()})

    assert target.read_text() == "ORIGINAL"


def test_successful_write_creates_parent_and_replaces(tmp_path):
    """Happy path: parent dir auto-created; content written; overwrite works."""
    target = tmp_path / "sub" / "dir" / "result.json"
    write_json_atomic(target, {"a": 1})
    assert json.loads(target.read_text()) == {"a": 1}
    write_json_atomic(target, {"a": 2})                       # overwrite
    assert json.loads(target.read_text()) == {"a": 2}


def test_json_output_byte_identical_to_json_dump(tmp_path):
    """The atomic path must reproduce json.dump(indent=2) exactly (frozen export)."""
    data = {"z": 1, "a": [1, 2, {"k": "v"}], "n": None, "s": "x"}
    target = tmp_path / "a.json"
    write_json_atomic(target, data)

    buf = io.StringIO()
    json.dump(data, buf, indent=2)
    assert target.read_text() == buf.getvalue()


def test_text_write_is_exact_no_trailing_newline(tmp_path):
    """write_text_atomic writes the string verbatim (paper tables are byte-frozen)."""
    target = tmp_path / "results_tables.md"
    content = "## Table\n\n| KB | x |\n|:---|---:|\n| KB1 | 1 |"
    write_text_atomic(target, content)
    assert target.read_text() == content


def test_atomic_write_cm_body_crash_leaves_original(tmp_path):
    """The line-by-line path (bias_io writers): a crash mid-body leaves the
    previous file intact and drops the temp — the whole point for a DIMACS/stats
    file written one f.write at a time.
    """
    target = tmp_path / "bias.cnf"
    target.write_text("c ORIGINAL BIAS\np cnf 2 1\n1 2 0\n")
    before = target.read_bytes()

    with pytest.raises(RuntimeError):
        with atomic_write(target) as f:
            f.write("c half-written header\n")
            raise RuntimeError("crash between lines")

    assert target.read_bytes() == before
    assert list(tmp_path.glob(".bias.cnf.*")) == []

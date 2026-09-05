"""Frozen provisioning snapshot derived from the oracle model at build time.

An oracle does two unrelated jobs (ADR-0009): it *answers* questions about the
target (``is_valid``/``complete_configuration``), and it *provisions* the
algorithm's SAT inputs (``kb``/``assumptions``/``c``/``bg_data``/``root_clauses``).
The second job has no business living on a live actor whose state a query can
shift — that entanglement was the A6 bug.

``OracleData`` is job ② extracted into an immutable value: built once, eagerly, and
handed to the consumers (``GenerateNE``, the model builders, both task-preparation
strategies). Being frozen, nothing a membership query does can reach it, so "a
query corrupts the background" is not expressible. It satisfies ``BGProvider`` +
``KBProvider`` so the consumers depend on the same narrow contracts as before —
they simply receive a snapshot instead of the live oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from conacq.oracle.bg_data import BGData
    from explanation.api import AssignmentAssumptionMap, DiagnosisTask


@dataclass(frozen=True)
class OracleData:
    """Immutable snapshot of the oracle's provisioning surface (job ②).

    Holds the prepared ``task`` as the SINGLE source of the KB/assumptions/set_c —
    ``get_kb``/``get_assumptions``/``get_c`` derive from it, so there is no second
    copy to drift (and the oracle builds its checker from the same real task, not a
    fabricated one). The task carries the real ``set_c`` a future delta/optimising
    checker may read; a stripped copy would break it silently.

    Fields:
        task: The prepared oracle task — the one source for kb/assumptions/c.
        bg_data: Root BG constraint pair + Part-4 assignment data for ConGen/QuAcq.
        root_clauses: Raw root-constraint CNF clauses (without assumption guards).
        assignment_map: Feature-assignment → assumption-id map (for query encoding).
        next_available_id: First free assumption id after the oracle's Parts 1-4.
    """

    task: "DiagnosisTask"
    bg_data: "BGData"
    root_clauses: Tuple[Tuple[int, ...], ...]
    assignment_map: "AssignmentAssumptionMap"
    next_available_id: int

    def __post_init__(self):
        # Deep-freeze root_clauses (the only own mutable gut) so ``frozen=True`` is
        # honest end-to-end: task/bg_data/assignment_map are already deeply frozen.
        object.__setattr__(self, 'root_clauses', tuple(tuple(c) for c in self.root_clauses))

    # --- KBProvider surface (derived from the task — one source of truth) ---
    # Return types are the task's frozen tuples (not List): callers concatenate them
    # (`set_b + set_c`), and typing.Sequence has no __add__ — so Tuple, honestly.
    def get_kb(self) -> Tuple[Tuple[int, ...], ...]:
        """Get the full knowledge base with assumptions."""
        return self.task.set_kb

    def get_assumptions(self) -> Tuple[int, ...]:
        """Get the list of assumption literals."""
        return self.task.assumptions

    def get_c(self) -> Tuple[int, ...]:
        """Get the FM constraint assumptions (background knowledge)."""
        return self.task.set_c

    # --- BGProvider surface ---
    def get_bg_data(self) -> "BGData":
        """Return root BG assumption data for ConGen/QuAcq."""
        return self.bg_data

    def get_root_clauses(self) -> Tuple[Tuple[int, ...], ...]:
        """Get raw background-knowledge clauses (root constraint)."""
        return self.root_clauses

"""Background knowledge data extracted from Oracle for ConGen consumption.

BGData captures the root BG constraint pair (first entry in Part 3 of the
shared assumption ID layout) plus the next available ID after Oracle's
Parts 3+4, allowing ConGen to start its own ID allocation cleanly.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from explanation.api import FrozenDict


@dataclass(frozen=True)
class BGData:
    """Root BG constraint data extracted post-preparation from Oracle.

    Fields (Part 3 -- root constraint):
        set_kb: Assumption-guarded clauses for root constraint + negated form
        assumptions: (root_assumption_id, negated_root_assumption_id)
        negation_map: {root_id: negated_root_id}
        descriptions: {root_id: "desc", neg_id: "NOT(desc)"}
        next_available_id: First free ID after Oracle Parts 3+4

    Fields (Part 4 -- feature assignments):
        assignment_clauses: Assumption-guarded unit clauses ([-a_pos, fid], [-a_neg, -fid])
        assignment_assumptions: All Part 4 assumption IDs
        pos_assignment_to_assumption: {feature_name: pos_assumption_id}
        neg_assignment_to_assumption: {feature_name: neg_assumption_id}
    """
    set_kb: Tuple[Tuple[int, ...], ...]
    assumptions: Tuple[int, int]
    negation_map: "FrozenDict[int, int]"
    descriptions: "FrozenDict[int, str]"
    next_available_id: int

    # Part 4: Feature assignment assumptions (for QuAcq pruning)
    assignment_clauses: Tuple[Tuple[int, ...], ...] = field(default_factory=tuple)
    assignment_assumptions: Tuple[int, ...] = field(default_factory=tuple)
    pos_assignment_to_assumption: "FrozenDict[str, int]" = field(default_factory=dict)
    neg_assignment_to_assumption: "FrozenDict[str, int]" = field(default_factory=dict)

    def __post_init__(self):
        # Deep-freeze every gut so ``frozen=True`` is honest (built-then-frozen:
        # the preparer accumulates locals and constructs BGData once).
        object.__setattr__(self, 'set_kb', tuple(tuple(c) for c in self.set_kb))
        object.__setattr__(self, 'negation_map', FrozenDict(self.negation_map))
        object.__setattr__(self, 'descriptions', FrozenDict(self.descriptions))
        object.__setattr__(self, 'assignment_clauses', tuple(tuple(c) for c in self.assignment_clauses))
        object.__setattr__(self, 'assignment_assumptions', tuple(self.assignment_assumptions))
        object.__setattr__(self, 'pos_assignment_to_assumption', FrozenDict(self.pos_assignment_to_assumption))
        object.__setattr__(self, 'neg_assignment_to_assumption', FrozenDict(self.neg_assignment_to_assumption))

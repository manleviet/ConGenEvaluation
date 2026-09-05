"""
ConGen result loader for evaluation.

Loads result JSON files produced by ConGen algorithm.
"""

from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path
import json


@dataclass
class ConGenResultData:
    """
    ConGen result loaded from JSON.

    Attributes:
        kb_constraints: List of constraint IDs in learned KB
        redundant_constraints: List of redundant constraint IDs
        n_bias: Original number of bias constraints
        n_mss: Size of MSS before REDUCE
        n_kb: Final KB size
        bg_clauses: Background knowledge clauses (e.g., [[1]] for root)
        metadata: Additional metadata
    """
    kb_constraints: List[str] = field(default_factory=list)
    redundant_constraints: List[str] = field(default_factory=list)
    n_bias: int = 0
    n_mss: int = 0
    n_kb: int = 0
    bg_clauses: List[List[int]] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> 'ConGenResultData':
        """Construct from in-memory dict (fold data from unified JSON).

        Handles both enriched [{"id", "description"}] and legacy ["c1"] formats.
        """
        kb_raw = data.get('kb_constraints', [])
        if kb_raw and isinstance(kb_raw[0], dict):
            kb_ids = [c['id'] for c in kb_raw]
        else:
            kb_ids = kb_raw

        stats = data.get('statistics', {})
        return cls(
            kb_constraints=kb_ids,
            redundant_constraints=data.get('redundant_constraints', []),
            n_bias=stats.get('n_bias', 0),
            n_mss=stats.get('n_mss', 0),
            n_kb=stats.get('n_kb', len(kb_ids)),
            bg_clauses=data.get('bg_clauses', []),
            metadata=data.get('metadata', {})
        )

    @classmethod
    def from_json(cls, json_path: Path) -> 'ConGenResultData':
        """
        Load result from JSON file.

        Args:
            json_path: Path to result JSON file

        Returns:
            ConGenResultData instance
        """
        json_path = Path(json_path)
        with open(json_path, 'r') as f:
            data = json.load(f)

        stats = data.get('statistics', {})

        return cls(
            kb_constraints=data.get('kb_constraints', []),
            redundant_constraints=data.get('redundant_constraints', []),
            n_bias=stats.get('n_bias', 0),
            n_mss=stats.get('n_mss', 0),
            n_kb=stats.get('n_kb', 0),
            bg_clauses=data.get('bg_clauses', []),
            metadata=data.get('metadata', {})
        )

    @property
    def kb_reduction_ratio(self) -> float:
        """
        Calculate KB reduction ratio.

        reduction = 1 - (n_kb / n_bias)
        """
        if self.n_bias == 0:
            return 0.0
        return 1 - (self.n_kb / self.n_bias)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'kb_constraints': self.kb_constraints,
            'redundant_constraints': self.redundant_constraints,
            'statistics': {
                'n_bias': self.n_bias,
                'n_mss': self.n_mss,
                'n_kb': self.n_kb,
            },
            'bg_clauses': self.bg_clauses,
            'metadata': self.metadata
        }

    def __repr__(self) -> str:
        return f"ConGenResultData(kb={self.n_kb}, redundant={len(self.redundant_constraints)})"

"""
Ground truth data extractor for evaluation.

Extracts constraint descriptions and CNF clauses from feature models
directly (without instantiating a full oracle).
"""

from dataclasses import dataclass, field
from typing import List, Set, Tuple, Dict
from pathlib import Path


@dataclass
class GroundTruthData:
    """Ground truth data extracted from feature model.

    Attributes:
        descriptions: Set of constraint descriptions (for Strategy 1)
        clauses: All CNF clauses as lists (for Strategy 2)
        clause_set: Normalized clause set with sorted tuples
        feature_map: Mapping {feature_name: variable_id}
        root_feature: Name of root feature
    """
    descriptions: Set[str] = field(default_factory=set)
    clauses: List[List[int]] = field(default_factory=list)
    clause_set: Set[Tuple[int, ...]] = field(default_factory=set)
    feature_map: Dict[str, int] = field(default_factory=dict)
    root_feature: str = ""

    @classmethod
    def from_uvl(cls, uvl_path: Path) -> 'GroundTruthData':
        """Load ground truth data directly from UVL file.

        Reads FM, converts to CNF, extracts descriptions — no solver needed.

        Args:
            uvl_path: Path to feature model (.uvl format)

        Returns:
            GroundTruthData instance
        """
        from flamapy.metamodels.fm_metamodel.transformations import UVLReader
        from explanation.api import FmToDiagPysat
        from conacq.oracle.constraint_description import extract_constraint_descriptions

        uvl_path = Path(uvl_path)
        fm = UVLReader(str(uvl_path)).transform()
        fm_model = FmToDiagPysat(fm, create_negation=False).transform()

        descriptions = extract_constraint_descriptions(fm)
        clauses = [clause for clauses in fm_model.constraint_map.values()
                   for clause in clauses]
        clause_set = {tuple(sorted(c)) for c in clauses}
        feature_map = dict(fm_model.variables)
        root_feature = fm.root.name

        return cls(
            descriptions=descriptions,
            clauses=clauses,
            clause_set=clause_set,
            feature_map=feature_map,
            root_feature=root_feature
        )

    def __len__(self) -> int:
        """Number of descriptions/constraints."""
        return len(self.descriptions)

    def __repr__(self) -> str:
        return (f"GroundTruthData(descriptions={len(self.descriptions)}, "
                f"clauses={len(self.clauses)}, features={len(self.feature_map)})")

"""
Data structures for constraint bias generation.

This module defines the core data structures used in constraint acquisition:
- Feature: Represents a binary feature in a feature model
- Constraint: Represents a constraint with operator and CNF clauses
- Bias: Collection of constraints forming the constraint bias B
- Configuration classes for simplified YAML input
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum


class OperatorType(Enum):
    """Types of operators in feature models"""
    MANDATORY = "mandatory"
    OPTIONAL = "optional"
    ALTERNATIVE = "alternative"
    OR = "or"
    REQUIRES = "requires"
    EXCLUDES = "excludes"


class RelationshipType(Enum):
    """Type of hierarchical relationship"""
    BINARY = "binary"  # mandatory/optional
    GROUP = "group"  # alternative/or


@dataclass
class Feature:
    """Represents a binary feature in a feature model"""
    name: str
    id: int  # SAT variable ID (positive integer)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Feature) and self.id == other.id

    def __repr__(self):
        return f"Feature({self.name}, id={self.id})"


@dataclass
class Constraint:
    """Represents a constraint in bias B"""
    id: str  # e.g., "c1", "c2"
    operator: Optional[OperatorType]
    parent: Optional[Feature] = None
    children: List[Feature] = field(default_factory=list)
    clauses: List[List[int]] = field(default_factory=list)  # CNF clauses
    description: str = ""

    def to_cnf(self) -> List[List[int]]:
        """Convert constraint to CNF clauses"""
        return self.clauses

    def __str__(self):
        if self.operator in [OperatorType.MANDATORY, OperatorType.OPTIONAL]:
            return f"{self.id}: {self.parent.name} --{self.operator.value}--> {self.children[0].name}"
        elif self.operator in [OperatorType.ALTERNATIVE, OperatorType.OR]:
            child_names = [c.name for c in self.children]
            return f"{self.id}: {self.parent.name} --{self.operator.value}--> {child_names}"
        elif self.operator == OperatorType.REQUIRES:
            return f"{self.id}: {self.parent.name} requires {self.children[0].name}"
        elif self.operator == OperatorType.EXCLUDES:
            return f"{self.id}: {self.parent.name} excludes {self.children[0].name}"
        else:
            return f"{self.id}: {self.description}"


@dataclass
class Bias:
    """Constraint bias B - collection of candidate constraints"""
    constraints: List[Constraint]
    features: List[Feature]

    def get_constraint_by_id(self, cid: str) -> Optional[Constraint]:
        """Get constraint by ID (O(1) via cached dict)."""
        return self._constraint_dict.get(cid)

    @property
    def _constraint_dict(self) -> Dict[str, 'Constraint']:
        """Lazy cached constraint lookup dict."""
        if not hasattr(self, '_cached_constraint_dict'):
            self._cached_constraint_dict = {c.id: c for c in self.constraints}
        return self._cached_constraint_dict

    def has_constraint(self, cid: str) -> bool:
        """Check if constraint ID exists."""
        return cid in self._constraint_dict

    def get_description(self, cid: str) -> str:
        """Get description for a constraint ID."""
        c = self._constraint_dict.get(cid)
        return c.description if c else ""

    def get_clauses(self, cid: str) -> List[List[int]]:
        """Get CNF clauses for a constraint ID."""
        c = self._constraint_dict.get(cid)
        return c.clauses if c else []

    def get_all_clause_tuples(self) -> Set[Tuple[int, ...]]:
        """Get all clauses as normalized sorted tuples."""
        result: Set[Tuple[int, ...]] = set()
        for c in self.constraints:
            for clause in c.clauses:
                result.add(tuple(sorted(clause)))
        return result

    def get_all_descriptions(self) -> Set[str]:
        """Get all constraint descriptions."""
        return {c.description for c in self.constraints}

    def get_constraint_ids_by_description(self, description: str) -> List[str]:
        """Find constraint IDs matching a description."""
        return [c.id for c in self.constraints if c.description == description]

    def to_cnf(self) -> List[List[int]]:
        """Get all CNF clauses from all constraints"""
        clauses = []
        for c in self.constraints:
            clauses.extend(c.clauses)
        return clauses

    @property
    def feature_ids(self) -> Dict[str, int]:
        """Feature name to SAT variable ID mapping."""
        return {f.name: f.id for f in self.features}

    @property
    def id_to_feature(self) -> Dict[int, str]:
        """SAT variable ID to feature name mapping."""
        return {f.id: f.name for f in self.features}

    def to_constraint_map(self) -> Dict[str, List[List[int]]]:
        """Convert bias constraints to {constraint_id: clauses} mapping."""
        return {c.id: c.clauses for c in self.constraints}

    @property
    def max_variable_id(self) -> int:
        """Max absolute literal value across all constraint clauses and feature IDs."""
        max_var = max((f.id for f in self.features), default=0)
        for c in self.constraints:
            for clause in c.clauses:
                for lit in clause:
                    max_var = max(max_var, abs(lit))
        return max_var

    def to_constraint_maps_with_negation(self) -> Tuple[Dict[str, List[List[int]]], Dict[str, List[List[int]]], int]:
        """Convert bias to constraint map and negated constraint map.

        Returns:
            Tuple of (constraint_map, negated_constraint_map, next_tseitin_var)
        """
        from explanation.api import negate_cnf_tseitin

        constraint_map = {}
        negated_constraint_map = {}
        next_tseitin_var = self.max_variable_id + 1

        for c in self.constraints:
            constraint_map[c.id] = c.clauses
            neg_clauses, next_tseitin_var = negate_cnf_tseitin(c.clauses, next_tseitin_var)

            negated_key = f"NOT({c.id})"
            negated_constraint_map[negated_key] = neg_clauses

        return constraint_map, negated_constraint_map, next_tseitin_var

    def __len__(self):
        return len(self.constraints)

    def __repr__(self):
        return f"Bias({len(self.constraints)} constraints, {len(self.features)} features)"


@dataclass
class HierarchicalCandidate:
    """Hierarchical candidate specification for config file"""
    parent: str
    children: List[str]
    relationship_type: RelationshipType

    def get_allowed_operators(self) -> List[str]:
        """Get allowed operators based on relationship type"""
        if self.relationship_type == RelationshipType.BINARY:
            return ['mandatory', 'optional']
        else:  # GROUP
            return ['alternative', 'or']


class CrossTreeMode(Enum):
    """Mode for cross-tree constraint generation"""
    ALL = "all"  # Generate constraints between all features
    LEAF = "leaf"  # Generate constraints only between leaf features
    EXTRACTED = "extracted"  # Generate constraints only between features extracted from CTCs


@dataclass
class CrossTreeConfig:
    """Cross-tree configuration"""
    cross_tree_mode: CrossTreeMode = CrossTreeMode.LEAF
    specific_pairs: List[tuple] = field(default_factory=list)
    cross_tree_features: List[str] = field(default_factory=list)  # Features for extracted mode

    def get_allowed_operators(self) -> List[str]:
        """Always generate both requires and excludes"""
        return ['requires', 'excludes']


@dataclass
class BiasConfig:
    """Bias configuration loaded from YAML"""
    name: str
    features: List[str]  # All feature names
    leaf_features: List[str]  # Leaf feature names (features with no children)
    hierarchical_candidates: List[HierarchicalCandidate]
    cross_tree_config: CrossTreeConfig

    def get_feature_ids(self) -> Dict[str, int]:
        """Auto-assign IDs to features (starting from 1)"""
        feature_ids = {}
        for i, feature_name in enumerate(self.features, start=1):
            feature_ids[feature_name] = i
        return feature_ids

    def get_cross_tree_features(self) -> List[str]:
        """Get features to use for cross-tree constraint generation based on mode"""
        if self.cross_tree_config.cross_tree_mode == CrossTreeMode.LEAF:
            return self.leaf_features
        elif self.cross_tree_config.cross_tree_mode == CrossTreeMode.EXTRACTED:
            return self.cross_tree_config.cross_tree_features if self.cross_tree_config.cross_tree_features else []
        else:  # ALL
            return self.features

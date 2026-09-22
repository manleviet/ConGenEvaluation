"""
Data structures for test cases in constraint acquisition.

Provides Example and ExampleSet classes for representing configurations
and their classifications (positive/negative).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set
from enum import Enum

from explanation.api import config_to_variable_literals


class ExampleType(Enum):
    """Classification of an example (test case)"""
    POSITIVE = "positive"  # Valid configuration (e⁺)
    NEGATIVE = "negative"  # Invalid configuration (e⁻)
    UNKNOWN = "unknown"    # Not yet classified


@dataclass
class Example:
    """
    A test case (example) for constraint acquisition.

    Represents a (partial or complete) configuration of features.

    Attributes:
        id: Unique identifier (e.g., "e1+", "rs_42")
        assignments: Feature assignments {feature_name: True/False}
        example_type: Classification (positive, negative, unknown)

    Example:
        >>> e = Example("e1", {"f1": True, "f2": False})
        >>> e.to_literals({"f1": 1, "f2": 2})
        [1, -2]
    """
    id: str
    assignments: Dict[str, bool]
    example_type: ExampleType = ExampleType.UNKNOWN

    def is_complete(self, all_features: Set[str]) -> bool:
        """
        Check if all features are assigned.

        Args:
            all_features: Set of all feature names

        Returns:
            True if this example assigns all features
        """
        return set(self.assignments.keys()) == all_features

    def is_partial(self, all_features: Set[str]) -> bool:
        """
        Check if this is a partial assignment.

        Args:
            all_features: Set of all feature names

        Returns:
            True if some features are not assigned
        """
        return len(self.assignments) < len(all_features)

    def get_assigned_features(self) -> Set[str]:
        """Get set of assigned feature names"""
        return set(self.assignments.keys())

    def get_missing_features(self, all_features: Set[str]) -> Set[str]:
        """
        Get features not assigned in this example.

        Args:
            all_features: Set of all feature names

        Returns:
            Set of unassigned feature names
        """
        return all_features - set(self.assignments.keys())

    def to_literals(self, feature_ids: Dict[str, int]) -> List[int]:
        """
        Convert to SAT literals for solver.

        Args:
            feature_ids: Mapping {feature_name: SAT_variable_id}

        Returns:
            List of literals where positive = True, negative = False
            Example: [1, -2, 3] means f1=True, f2=False, f3=True
        """
        return config_to_variable_literals(self.assignments, feature_ids)

    def to_clause(self, feature_ids: Dict[str, int]) -> List[int]:
        """
        Convert to CNF clause (disjunction of negated literals).

        Used for adding negative examples as constraints.
        If example is {f1: True, f2: False}, the clause is [-1, 2]
        meaning "NOT this exact configuration".

        Args:
            feature_ids: Mapping {feature_name: SAT_variable_id}

        Returns:
            Clause that blocks this configuration
        """
        literals = self.to_literals(feature_ids)
        return [-lit for lit in literals]

    def copy(self) -> 'Example':
        """Create a copy of this example"""
        return Example(
            id=self.id,
            assignments=dict(self.assignments),
            example_type=self.example_type
        )

    def __str__(self):
        parts = [f"{name}" if val else f"¬{name}"
                 for name, val in sorted(self.assignments.items())]
        type_str = self.example_type.value[0]  # p/n/u
        return f"{self.id}({type_str}): {' ∧ '.join(parts)}"

    def __repr__(self):
        return f"Example(id='{self.id}', type={self.example_type.value}, " \
               f"n_assigned={len(self.assignments)})"

    def __hash__(self):
        return hash((self.id, tuple(sorted(self.assignments.items()))))

    def __eq__(self, other):
        if not isinstance(other, Example):
            return False
        return self.id == other.id and self.assignments == other.assignments


@dataclass
class ExampleSet:
    """
    Collection of positive and negative examples.

    Attributes:
        positive: List of positive examples (E⁺)
        negative: List of negative examples (E⁻)
        metadata: Additional information (sampling method, etc.)

    Example:
        >>> es = ExampleSet()
        >>> es.add(Example("e1", {"f1": True}, ExampleType.POSITIVE))
        >>> print(es)
        ExampleSet(E⁺=1, E⁻=0)
    """
    positive: List[Example] = field(default_factory=list)  # E⁺
    negative: List[Example] = field(default_factory=list)  # E⁻
    metadata: Dict = field(default_factory=dict)

    def add(self, example: Example):
        """
        Add example to appropriate list based on its type.

        Args:
            example: Example to add (must have type POSITIVE or NEGATIVE)
        """
        if example.example_type == ExampleType.POSITIVE:
            self.positive.append(example)
        elif example.example_type == ExampleType.NEGATIVE:
            self.negative.append(example)
        else:
            raise ValueError(f"Cannot add example with type {example.example_type}")

    def add_positive(self, example: Example):
        """Add as positive example"""
        example.example_type = ExampleType.POSITIVE
        self.positive.append(example)

    def add_negative(self, example: Example):
        """Add as negative example"""
        example.example_type = ExampleType.NEGATIVE
        self.negative.append(example)

    def get_all(self) -> List[Example]:
        """Get all examples (positive + negative)"""
        return self.positive + self.negative

    def statistics(self) -> Dict:
        """
        Get statistics about the example set.

        Returns:
            Dictionary with counts and ratios
        """
        total = len(self)
        n_pos = len(self.positive)
        n_neg = len(self.negative)

        return {
            'total': total,
            'n_positive': n_pos,
            'n_negative': n_neg,
            'pos_ratio': n_pos / total if total > 0 else 0,
            'neg_ratio': n_neg / total if total > 0 else 0,
        }

    def __len__(self):
        return len(self.positive) + len(self.negative)

    def __repr__(self):
        return f"ExampleSet(E⁺={len(self.positive)}, E⁻={len(self.negative)})"

    def __str__(self):
        return self.__repr__()

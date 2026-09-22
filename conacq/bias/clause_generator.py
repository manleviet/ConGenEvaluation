"""
Constraint clause generator for feature model operators.

This module implements CNF clause generation for different feature model
relationship types: mandatory, optional, alternative, or, requires, excludes.

Based on the formulation from the plan_bias.md document.
"""

from typing import List
from .data_structures import Feature


class ConstraintClauseGenerator:
    """Generate CNF clauses for different operator types in feature models"""

    @staticmethod
    def mandatory(parent: Feature, child: Feature) -> List[List[int]]:
        """
        Mandatory: child ↔ parent (bidirectional implication)

        CNF: (¬parent ∨ child) ∧ (¬child ∨ parent)

        Args:
            parent: Parent feature
            child: Child feature

        Returns:
            List of CNF clauses

        Example:
            If parent=Feature("survey", 1) and child=Feature("payment", 2):
            Returns: [[-1, 2], [-2, 1]]
        """
        return [
            [-parent.id, child.id],   # parent → child
            [-child.id, parent.id]    # child → parent
        ]

    @staticmethod
    def optional(parent: Feature, child: Feature) -> List[List[int]]:
        """
        Optional: child → parent (child requires parent)

        CNF: ¬child ∨ parent

        Args:
            parent: Parent feature
            child: Child feature

        Returns:
            List of CNF clauses

        Example:
            If parent=Feature("survey", 1) and child=Feature("abtesting", 3):
            Returns: [[-3, 1]]
        """
        return [
            [-child.id, parent.id]
        ]

    @staticmethod
    def alternative(parent: Feature, children: List[Feature]) -> List[List[int]]:
        """
        Alternative (XOR): exactly one child if parent selected

        Three rules:
        1. At least one child if parent: ¬parent ∨ child1 ∨ child2 ∨ ... ∨ childN
        2. At most one child (pairwise mutex): ¬childi ∨ ¬childj for all i < j
        3. Each child requires parent: ¬child ∨ parent for all children

        Args:
            parent: Parent feature
            children: List of child features

        Returns:
            List of CNF clauses

        Example:
            If parent=Feature("payment", 2) and children=[Feature("license", 3), Feature("nolicense", 4)]:
            Returns:
                [[-2, 3, 4],      # At least one child
                 [-3, -4],        # Mutex: not both
                 [-3, 2],         # license requires payment
                 [-4, 2]]         # nolicense requires payment
        """
        clauses = []

        # Rule 1: At least one child OR no parent
        # ¬parent ∨ child1 ∨ child2 ∨ ... ∨ childN
        alt_clause = [-parent.id]
        for child in children:
            alt_clause.append(child.id)
        clauses.append(alt_clause)

        # Rule 2: At most one child (pairwise mutex)
        for i in range(len(children)):
            for j in range(i + 1, len(children)):
                # ¬childi ∨ ¬childj
                clauses.append([
                    -children[i].id,
                    -children[j].id
                ])

        # Rule 3: Each child implies parent
        for child in children:
            # ¬child ∨ parent
            clauses.append([
                -child.id,
                parent.id
            ])

        return clauses

    @staticmethod
    def or_relation(parent: Feature, children: List[Feature]) -> List[List[int]]:
        """
        Or: at least one child if parent selected

        Two rules:
        1. At least one child if parent: ¬parent ∨ child1 ∨ child2 ∨ ... ∨ childN
        2. Each child requires parent: ¬child ∨ parent for all children

        Args:
            parent: Parent feature
            children: List of child features

        Returns:
            List of CNF clauses

        Example:
            If parent=Feature("qa", 7) and children=[Feature("multiple", 8), Feature("multimedia", 9)]:
            Returns:
                [[-7, 8, 9],     # At least one child
                 [-8, 7],        # multiple requires qa
                 [-9, 7]]        # multimedia requires qa
        """
        clauses = []

        # Rule 1: At least one child OR no parent
        # ¬parent ∨ child1 ∨ child2 ∨ ... ∨ childN
        or_clause = [-parent.id]
        for child in children:
            or_clause.append(child.id)
        clauses.append(or_clause)

        # Rule 2: Each child implies parent
        for child in children:
            # ¬child ∨ parent
            clauses.append([
                -child.id,
                parent.id
            ])

        return clauses

    @staticmethod
    def requires(feature_a: Feature, feature_b: Feature) -> List[List[int]]:
        """
        Requires: a → b (if a then b)

        CNF: ¬a ∨ b

        Args:
            feature_a: Source feature
            feature_b: Target feature

        Returns:
            List of CNF clauses

        Example:
            If feature_a=Feature("abtesting", 5) and feature_b=Feature("statistics", 6):
            Returns: [[-5, 6]]
        """
        return [
            [-feature_a.id, feature_b.id]
        ]

    @staticmethod
    def excludes(feature_a: Feature, feature_b: Feature) -> List[List[int]]:
        """
        Excludes: ¬(a ∧ b) (cannot both be selected)

        CNF: ¬a ∨ ¬b

        Args:
            feature_a: First feature
            feature_b: Second feature

        Returns:
            List of CNF clauses

        Example:
            If feature_a=Feature("nolicense", 4) and feature_b=Feature("abtesting", 5):
            Returns: [[-4, -5]]
        """
        return [
            [-feature_a.id, -feature_b.id]
        ]

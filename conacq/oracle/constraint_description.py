"""
Constraint description extraction from feature models.

Parses FM hierarchical relations and cross-tree constraints (CTCs)
into human-readable description strings matching bias format.
"""

from typing import Optional, Set

from flamapy.core.models.ast import ASTOperation


def extract_constraint_descriptions(fm) -> Set[str]:
    """Extract constraint descriptions from a feature model.

    Returns descriptions in format matching bias:
    - "parent --mandatory--> child"
    - "parent --optional--> child"
    - "parent --alternative--> [child1, child2, ...]"
    - "parent --or--> [child1, child2, ...]"
    - "feature1 requires feature2"
    - "feature1 excludes feature2"

    Args:
        fm: Feature model object (flamapy FeatureModel)

    Returns:
        Set of constraint description strings
    """
    descriptions = set()

    # Hierarchical constraints from feature relationships
    for feature in fm.get_features():
        for relation in feature.get_relations():
            if relation.is_mandatory():
                for child in relation.children:
                    descriptions.add(f"{feature.name} --mandatory--> {child.name}")
            elif relation.is_optional():
                for child in relation.children:
                    descriptions.add(f"{feature.name} --optional--> {child.name}")
            elif relation.is_alternative():
                children_names = [c.name for c in relation.children]
                descriptions.add(f"{feature.name} --alternative--> {children_names}")
            elif relation.is_or():
                children_names = [c.name for c in relation.children]
                descriptions.add(f"{feature.name} --or--> {children_names}")

    # Cross-tree constraints
    for ctc in fm.get_constraints():
        desc = _parse_ctc_to_description(ctc)
        if desc:
            descriptions.add(desc)

    return descriptions


def _parse_ctc_to_description(ctc) -> Optional[str]:
    """Parse cross-tree constraint to description format.

    Supports requires (A => B) and excludes (!(A & B)) patterns.
    Falls back to string representation for unrecognized patterns.
    """
    ast = ctc.ast
    if ast is None:
        return None

    root = ast.root

    # Handle requires: A => B (same as !A | B)
    if root.data == ASTOperation.IMPLIES:
        left, right = root.left, root.right
        if left and right:
            left_name = _get_feature_name(left)
            right_name = _get_feature_name(right)
            if left_name and right_name:
                return f"{left_name} requires {right_name}"

    # Handle excludes: !(A & B)
    if root.data == ASTOperation.NOT:
        inner = root.left
        if inner and inner.data == ASTOperation.AND:
            left, right = inner.left, inner.right
            if left and right:
                left_name = _get_feature_name(left)
                right_name = _get_feature_name(right)
                if left_name and right_name:
                    names = sorted([left_name, right_name])
                    return f"{names[0]} excludes {names[1]}"

    # Handle excludes: A => !B
    if root.data == ASTOperation.IMPLIES:
        left, right = root.left, root.right
        if right and right.data == ASTOperation.NOT:
            left_name = _get_feature_name(left)
            right_name = _get_feature_name(right.left)
            if left_name and right_name:
                names = sorted([left_name, right_name])
                return f"{names[0]} excludes {names[1]}"

    # Handle OR patterns (flamapy UVL representation)
    if root.data == ASTOperation.OR:
        left, right = root.left, root.right
        if left and right:
            # OR(NOT(A), NOT(B)) == !(A & B) == A excludes B
            if left.data == ASTOperation.NOT and right.data == ASTOperation.NOT:
                left_name = _get_feature_name(left.left)
                right_name = _get_feature_name(right.left)
                if left_name and right_name:
                    names = sorted([left_name, right_name])
                    return f"{names[0]} excludes {names[1]}"

            # OR(NOT(A), B) == !A | B == A => B == A requires B
            if left.data == ASTOperation.NOT:
                left_name = _get_feature_name(left.left)
                right_name = _get_feature_name(right)
                if left_name and right_name:
                    return f"{left_name} requires {right_name}"

    # Fallback: use constraint string representation
    return str(ctc)


def _get_feature_name(node) -> Optional[str]:
    """Extract feature name from AST node."""
    if node is None:
        return None
    if node.data is None or not isinstance(node.data, ASTOperation):
        return str(node.data) if node.data else None
    return None

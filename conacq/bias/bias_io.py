"""
Bias I/O utilities for saving and loading bias files.

This module provides functionality to save and load constraint biases
in different formats: JSON (structured) and DIMACS CNF (standard SAT format).
"""

from pathlib import Path
from typing import Dict

from conacq.atomic_io import atomic_write, write_json_atomic, read_json
from .data_structures import Feature, Constraint, Bias, OperatorType


class BiasIO:
    """Save and load bias to/from files"""

    @staticmethod
    def save_to_cnf(bias: Bias, filepath: str):
        """
        Save bias to DIMACS CNF format with metadata in comments.

        Format:
            c <metadata in comments>
            c Constraint c1: survey --mandatory--> payment
            c Constraint c2: payment --optional--> license
            p cnf <num_vars> <num_clauses>
            <clauses>

        Args:
            bias: Bias object to save
            filepath: Output file path

        Example output:
            c Constraint Bias B
            c Generated for constraint acquisition
            c Number of features: 9
            c Number of constraints: 92
            c
            c Feature mapping:
            c   1: survey
            c   2: payment
            c
            c Constraint descriptions:
            c   c1: survey --mandatory--> payment
            c   c2: survey --optional--> payment
            c
            p cnf 9 184
            -1 2 0
            -2 1 0
            -2 1 0
            ...
        """
        with atomic_write(filepath) as f:
            # Header comments
            f.write("c Constraint Bias B\n")
            f.write("c Generated for constraint acquisition\n")
            f.write(f"c Number of features: {len(bias.features)}\n")
            f.write(f"c Number of constraints: {len(bias.constraints)}\n")
            f.write("c\n")

            # Feature mapping
            f.write("c Feature mapping:\n")
            for feature in sorted(bias.features, key=lambda f: f.id):
                f.write(f"c   {feature.id}: {feature.name}\n")
            f.write("c\n")

            # Constraint descriptions
            f.write("c Constraint descriptions:\n")
            for constraint in bias.constraints:
                f.write(f"c   {constraint.id}: {constraint.description}\n")
            f.write("c\n")

            # CNF header
            all_clauses = bias.to_cnf()
            num_vars = max(f.id for f in bias.features)
            num_clauses = len(all_clauses)
            f.write(f"p cnf {num_vars} {num_clauses}\n")

            # Clauses (one per line, terminated with 0)
            for clause in all_clauses:
                f.write(' '.join(map(str, clause)) + ' 0\n')

    @staticmethod
    def save_to_json(bias: Bias, filepath: str):
        """
        Save bias to JSON format (more structured, easier to load).

        Args:
            bias: Bias object to save
            filepath: Output file path

        Example output:
            {
              "features": [
                {"name": "survey", "id": 1},
                {"name": "payment", "id": 2}
              ],
              "constraints": [
                {
                  "id": "c1",
                  "operator": "mandatory",
                  "parent": "survey",
                  "children": ["payment"],
                  "clauses": [[-1, 2], [-2, 1]],
                  "description": "survey --mandatory--> payment"
                }
              ]
            }
        """
        data = {
            'features': [
                {'name': f.name, 'id': f.id}
                for f in sorted(bias.features, key=lambda f: f.id)
            ],
            'constraints': [
                BiasIO._constraint_to_dict(c) for c in bias.constraints
            ]
        }

        write_json_atomic(filepath, data)

    @staticmethod
    def load_from_json(filepath: str) -> Bias:
        """
        Load bias from JSON file.

        Args:
            filepath: Input JSON file path

        Returns:
            Bias object

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON parsing fails
        """
        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"Bias file not found: {filepath}")

        data = read_json(filepath)

        # Reconstruct features
        features = [
            Feature(name=f['name'], id=f['id'])
            for f in data['features']
        ]
        feature_map = {f.name: f for f in features}

        # Reconstruct constraints
        constraints = [
            BiasIO._constraint_from_dict(c_data, feature_map)
            for c_data in data['constraints']
        ]

        return Bias(constraints=constraints, features=features)

    @staticmethod
    def _constraint_to_dict(constraint: Constraint) -> dict:
        """Serialize a Constraint to a JSON-compatible dict."""
        return {
            'id': constraint.id,
            'operator': constraint.operator.value if constraint.operator else None,
            'parent': constraint.parent.name if constraint.parent else None,
            'children': [ch.name for ch in constraint.children],
            'clauses': constraint.clauses,
            'description': constraint.description
        }

    @staticmethod
    def _constraint_from_dict(c_data: dict, feature_map: dict) -> Constraint:
        """Deserialize a Constraint from a JSON dict and feature lookup map."""
        parent_name = c_data.get('parent', '')
        parent = feature_map.get(parent_name) if parent_name else None
        children = [feature_map[name] for name in c_data.get('children', []) if name in feature_map]
        operator_str = c_data.get('operator', '')
        return Constraint(
            id=c_data['id'],
            operator=OperatorType(operator_str) if operator_str else None,
            parent=parent,
            children=children,
            clauses=c_data.get('clauses', []),
            description=c_data.get('description', '')
        )

    @staticmethod
    def save_statistics(bias: Bias, filepath: str):
        """
        Save bias statistics to a text file.

        Args:
            bias: Bias object
            filepath: Output file path

        Output format:
            ===  Bias Statistics ===
            Total features: 9
            Total constraints: 92
            Total clauses: 184

            Constraints by operator:
              mandatory: 4
              optional: 4
              alternative: 2
              or: 2
              requires: 72
              excludes: 36
        """
        from collections import Counter

        with atomic_write(filepath) as f:
            f.write("=== Bias Statistics ===\n")
            f.write(f"Total features: {len(bias.features)}\n")
            f.write(f"Total constraints: {len(bias.constraints)}\n")
            f.write(f"Total clauses: {len(bias.to_cnf())}\n")
            f.write("\n")

            # Count by operator
            op_counts = Counter(c.operator.value if c.operator else 'unknown'
                                for c in bias.constraints)
            f.write("Constraints by operator:\n")
            for op, count in sorted(op_counts.items()):
                f.write(f"  {op}: {count}\n")

            f.write("\n")

            # Feature list
            f.write("Features:\n")
            for feature in sorted(bias.features, key=lambda f: f.id):
                f.write(f"  {feature.id}: {feature.name}\n")

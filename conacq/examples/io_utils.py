"""
I/O utilities for saving and loading examples.

Supports JSON format for ExampleSet serialization.
"""

from pathlib import Path
from typing import Union

from conacq.atomic_io import write_json_atomic, read_json
from .data_structures import Example, ExampleSet, ExampleType


class ExampleIO:
    """
    Save and load examples to/from files.

    Supports JSON format with full metadata preservation.

    Example:
        >>> ExampleIO.save_json(example_set, 'examples.json')
        >>> loaded = ExampleIO.load_json('examples.json')
    """

    @staticmethod
    def save_json(example_set: ExampleSet, filepath: Union[str, Path]):
        """
        Save ExampleSet to JSON file.

        Args:
            example_set: ExampleSet to save
            filepath: Output file path

        JSON structure:
            {
                "metadata": {...},
                "positive": [{"id": "e1+", "assignments": {...}}, ...],
                "negative": [{"id": "e1-", "assignments": {...}}, ...]
            }
        """
        data = {
            'metadata': example_set.metadata,
            'statistics': example_set.statistics(),
            'positive': [
                {
                    'id': e.id,
                    'assignments': e.assignments
                }
                for e in example_set.positive
            ],
            'negative': [
                {
                    'id': e.id,
                    'assignments': e.assignments
                }
                for e in example_set.negative
            ]
        }

        write_json_atomic(filepath, data)

    @staticmethod
    def load_json(filepath: Union[str, Path]) -> ExampleSet:
        """
        Load ExampleSet from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Loaded ExampleSet
        """
        data = read_json(filepath)

        example_set = ExampleSet(metadata=data.get('metadata', {}))

        # Load positive examples
        for e_data in data.get('positive', []):
            example = Example(
                id=e_data['id'],
                assignments=e_data['assignments'],
                example_type=ExampleType.POSITIVE
            )
            example_set.positive.append(example)

        # Load negative examples
        for e_data in data.get('negative', []):
            example = Example(
                id=e_data['id'],
                assignments=e_data['assignments'],
                example_type=ExampleType.NEGATIVE
            )
            example_set.negative.append(example)

        return example_set

    @staticmethod
    def to_dict(example_set: ExampleSet) -> dict:
        """
        Convert ExampleSet to dictionary (for programmatic use).

        Args:
            example_set: ExampleSet to convert

        Returns:
            Dictionary representation
        """
        return {
            'metadata': example_set.metadata,
            'statistics': example_set.statistics(),
            'positive': [
                {'id': e.id, 'assignments': e.assignments}
                for e in example_set.positive
            ],
            'negative': [
                {'id': e.id, 'assignments': e.assignments}
                for e in example_set.negative
            ]
        }

    @staticmethod
    def from_dict(data: dict) -> ExampleSet:
        """
        Create ExampleSet from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            ExampleSet instance
        """
        example_set = ExampleSet(metadata=data.get('metadata', {}))

        for e_data in data.get('positive', []):
            example = Example(
                id=e_data['id'],
                assignments=e_data['assignments'],
                example_type=ExampleType.POSITIVE
            )
            example_set.positive.append(example)

        for e_data in data.get('negative', []):
            example = Example(
                id=e_data['id'],
                assignments=e_data['assignments'],
                example_type=ExampleType.NEGATIVE
            )
            example_set.negative.append(example)

        return example_set

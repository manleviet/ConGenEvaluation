"""Convert QuAcqRunner query history to example formats for ConGen."""

from typing import List, Tuple, Dict, Optional

from .data_structures import Example, ExampleSet, ExampleType


def queries_to_examples(
    query_history: List[Tuple[Dict[str, bool], bool, str]],
    source_filter: str = 'main',
    metadata: Optional[Dict] = None
) -> ExampleSet:
    """Convert query history from QuAcq into ExampleSet for ConGen.

    Each (config, answer, source) triple becomes one Example if source matches:
    - answer=True  -> ExampleType.POSITIVE
    - answer=False -> ExampleType.NEGATIVE

    Args:
        query_history: List of (config_dict, oracle_answer, source) tuples
        source_filter: Only include queries with this source tag
        metadata: Optional metadata dict for the ExampleSet

    Returns:
        ExampleSet with positive and negative examples
    """
    es = ExampleSet(metadata=metadata or {})
    idx = 0
    for config, answer, source in query_history:
        if source != source_filter:
            continue
        example_type = ExampleType.POSITIVE if answer else ExampleType.NEGATIVE
        suffix = "+" if answer else "-"
        example = Example(
            id=f"q{idx}{suffix}",
            assignments=config,
            example_type=example_type
        )
        es.add(example)
        idx += 1
    return es


def queries_to_assignment_lists(
    query_history: List[Tuple[Dict[str, bool], bool, str]],
    source_filter: str = 'main'
) -> Tuple[List[Dict[str, bool]], List[Dict[str, bool]]]:
    """Split query history into positive/negative assignment lists.

    Returns format directly usable by ConGenRunner.run(pos, neg).

    Args:
        query_history: List of (config_dict, oracle_answer, source) tuples
        source_filter: Only include queries with this source tag

    Returns:
        (positive_assignments, negative_assignments) tuple
    """
    positive = [config for config, answer, source in query_history
                if answer and source == source_filter]
    negative = [config for config, answer, source in query_history
                if not answer and source == source_filter]
    return positive, negative

"""Tests for query_converter: converting QuAcq query history to ConGen examples."""

import pytest
from conacq.examples.query_converter import queries_to_examples, queries_to_assignment_lists
from conacq.examples.data_structures import ExampleType


class TestQueriesToExamples:
    """Test queries_to_examples()."""

    def test_empty_history(self):
        es = queries_to_examples([])
        assert len(es.positive) == 0
        assert len(es.negative) == 0

    def test_mixed_positive_negative(self):
        history = [
            ({'f1': True, 'f2': False}, True, 'main'),
            ({'f1': False, 'f2': True}, False, 'main'),
            ({'f1': True, 'f2': True}, True, 'main'),
        ]
        es = queries_to_examples(history)
        assert len(es.positive) == 2
        assert len(es.negative) == 1

    def test_all_positive(self):
        history = [
            ({'f1': True}, True, 'main'),
            ({'f1': False}, True, 'main'),
        ]
        es = queries_to_examples(history)
        assert len(es.positive) == 2
        assert len(es.negative) == 0

    def test_all_negative(self):
        history = [
            ({'f1': True}, False, 'main'),
            ({'f1': False}, False, 'main'),
        ]
        es = queries_to_examples(history)
        assert len(es.positive) == 0
        assert len(es.negative) == 2

    def test_id_pattern(self):
        history = [
            ({'f1': True}, True, 'main'),
            ({'f1': False}, False, 'main'),
        ]
        es = queries_to_examples(history)
        ids = [e.id for e in es.positive + es.negative]
        assert 'q0+' in ids
        assert 'q1-' in ids

    def test_source_filter(self):
        history = [
            ({'f1': True}, True, 'main'),
            ({'f1': False}, False, 'findc'),
            ({'f1': True}, False, 'main'),
        ]
        es = queries_to_examples(history, source_filter='main')
        # Only 2 main queries, skip findc
        assert len(es.positive) + len(es.negative) == 2

    def test_metadata_propagated(self):
        history = [({'f1': True}, True, 'main')]
        es = queries_to_examples(history, metadata={'source': 'test'})
        assert es.metadata == {'source': 'test'}


class TestQueriesToAssignmentLists:
    """Test queries_to_assignment_lists()."""

    def test_empty_history(self):
        pos, neg = queries_to_assignment_lists([])
        assert pos == []
        assert neg == []

    def test_correct_split(self):
        history = [
            ({'f1': True}, True, 'main'),
            ({'f1': False}, False, 'main'),
            ({'f1': True, 'f2': True}, True, 'main'),
        ]
        pos, neg = queries_to_assignment_lists(history)
        assert len(pos) == 2
        assert len(neg) == 1

    def test_source_filter(self):
        history = [
            ({'f1': True}, True, 'main'),
            ({'f1': False}, False, 'findc'),
            ({'f1': True}, False, 'main'),
        ]
        pos, neg = queries_to_assignment_lists(history, source_filter='main')
        assert len(pos) == 1
        assert len(neg) == 1

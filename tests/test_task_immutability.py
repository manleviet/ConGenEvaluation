"""Characterization tests pinning the T1 Task-family invariants.

Tasks are immutable pure-data units-of-work: frozen dataclasses with only
intrinsic solve fields, no methods (derived quantities are free functions),
and TaskInput validates mutually-exclusive input combinations.
"""
import dataclasses

import pytest
from flamapy.metamodels.configuration_metamodel.models import Configuration

from explanation.models.task_preparation import (
    Task,
    DiagnosisTask,
    TaskInput,
    cf,
)
# Aliased with leading underscore so pytest does not try to collect these
# "Test*"-named data classes as test cases.
from explanation.models.task_preparation import TestCaseTask as _TestCaseTask
from explanation.models.testsuite import TestSuite as _TestSuite
from conacq.algorithms.acqmss.task_preparation import ConGenTask
from conacq.algorithms.quacq.task_preparation import QuAcqTask


# --- Deep-frozen contract: rebinding a field raises, and the list-valued fields
#     are tuples so mutating their contents raises too (the deep-immutability
#     mechanism is pinned by test_t11_purity_guards::test_task_is_deeply_frozen). ---

@pytest.mark.parametrize("task_cls", [DiagnosisTask, _TestCaseTask, ConGenTask, QuAcqTask])
def test_task_rebind_raises(task_cls):
    task = task_cls()
    with pytest.raises(dataclasses.FrozenInstanceError):
        task.set_c = [1, 2, 3]


def test_task_input_is_frozen():
    ti = TaskInput()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ti.for_redundancy = True


# --- Hierarchy: every task is a Task; test-case tasks are TestCaseTask ---

def test_hierarchy():
    assert issubclass(DiagnosisTask, Task)
    assert issubclass(_TestCaseTask, Task)
    assert issubclass(ConGenTask, _TestCaseTask)
    assert issubclass(QuAcqTask, DiagnosisTask)
    # ConGen tasks are test-case tasks; QuAcq tasks are not.
    assert isinstance(ConGenTask(), _TestCaseTask)
    assert not isinstance(QuAcqTask(), _TestCaseTask)


# --- Pure data: no residual get_cf method; cf() is a free function ---

def test_no_get_cf_method_on_task():
    assert not hasattr(DiagnosisTask(), "get_cf")


def test_cf_free_function():
    task = DiagnosisTask(set_c=[3, 4], set_b=[1, 2])
    assert cf(task) == (1, 2, 3, 4)  # set_b + set_c (frozen tuples -> tuple)


# --- QuAcq-specific field survives frozen construction ---

def test_quacq_constraint_clauses_field():
    task = QuAcqTask(constraint_clauses={10: [[1, -2], [3]]})
    assert task.constraint_clauses == {10: ((1, -2), (3,))}  # deep-frozen: nested tuples
    assert task.set_c == ()  # default (deep-frozen: fields are tuples)


# --- TaskInput factories map to the documented use cases ---

def test_taskinput_factories():
    assert TaskInput.fm_diagnosis() == TaskInput()
    assert TaskInput.redundancy_fm().for_redundancy is True

    cfg = Configuration({})
    assert TaskInput.config(cfg).configuration is cfg
    assert TaskInput.config_with_cf(cfg).with_cf_in_c is True
    assert TaskInput.error(cfg).test_case is cfg

    pos = _TestSuite([])
    ti = TaskInput.testcases(pos)
    assert ti.positive_test_cases is pos and ti.is_testcase_task()
    assert TaskInput.redundancy_t(pos).for_redundancy is True


# --- TaskInput validates mutually-exclusive inputs ---

def test_taskinput_rejects_config_with_testcases():
    with pytest.raises(ValueError):
        TaskInput(configuration=Configuration({}), positive_test_cases=_TestSuite([]))


def test_taskinput_rejects_testcase_with_error():
    with pytest.raises(ValueError):
        TaskInput(test_case=Configuration({}), positive_test_cases=_TestSuite([]))

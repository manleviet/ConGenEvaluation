"""Shared harness for the T11 prepared-task-ID (Layer 2) and E2E (Layer 3) nets.

Not a test module. Imported by both the fixture recorder
(``scripts/build_t11_oracle_net_fixtures.py``) and the replay tests. The builders
below are deterministic on the committed REAL-FM-7 fixtures, so the recorder
freezes their output as a golden JSON and the replay tests re-run them against
the (possibly refactored) code and compare to that frozen golden.
"""
from tests.resource_paths import (
    FM_PATH,
    BIAS_PATH,
    EXAMPLES_RS_1N_PATH,
    EXAMPLES_FF_PATH,
)
from tests.t11_oracle_net_helpers import _canon, load_json, queries_path, trace_path

# Two real REAL-FM-7 feature names, used to give config/error factories non-empty
# Part-4 assignment assumptions so their ID layout is actually exercised.
_CONFIG = {"java": True, "qt": False}

# QuAcq learns an empty KB even at 500 queries on this FM/bias (see report), so
# the E2E golden pins the query TRAJECTORY (deterministic, SAT-driven) — a
# regression that changes what QuAcq asks is caught even with an empty KB.
_QUACQ_MAX_QUERIES = 15


def _frozen_negative_testsuite():
    """A TestSuite of known-invalid REAL-FM-7 configs (reuses Layer-1 fixtures).

    The membership queries whose recorded answer is False are guaranteed-invalid
    and already frozen on disk, so QuickXPlain finds a real conflict for each and
    the inputs never regenerate at test time.
    """
    from explanation.models.testsuite import TestSuite, TestCase, Assignment

    queries = load_json(queries_path("REAL-FM-7"))["membership"]
    answers = load_json(trace_path("REAL-FM-7"))["answers"]["membership"]
    invalid = [cfg for cfg, ans in zip(queries, answers) if ans is False][:3]
    return TestSuite(testcases=[
        TestCase([Assignment(name, value) for name, value in cfg.items()])
        for cfg in invalid
    ])


def diagnosis_model():
    """The DiagnosisModel (flamapy) for REAL-FM-7, negation enabled."""
    from flamapy.metamodels.fm_metamodel.transformations import UVLReader
    from explanation.api import FmToDiagPysat

    fm = UVLReader(str(FM_PATH)).transform()
    return FmToDiagPysat(fm, create_negation=True).transform()


def _task_input_cases():
    """All 7 TaskInput factories (name -> TaskInput)."""
    from explanation.api import TaskInput
    from flamapy.metamodels.configuration_metamodel.models import Configuration

    cfg = Configuration(dict(_CONFIG))
    testsuite = _frozen_negative_testsuite()
    return {
        "fm_diagnosis": TaskInput.fm_diagnosis(),
        "redundancy_fm": TaskInput.redundancy_fm(),
        "config": TaskInput.config(cfg),
        "config_with_cf": TaskInput.config_with_cf(cfg),
        "error": TaskInput.error(Configuration(dict(_CONFIG))),
        "testcases": TaskInput.testcases(testsuite),
        "redundancy_t": TaskInput.redundancy_t(testsuite),
    }


def generate_ne_subproblem():
    """Layer 2 (③): the GenerateNE per-testcase sub-problem ID layout.

    Pins each NE-clause id + clause literals + the set_kb growth for a fixed
    negative TestSuite and start id. GenerateNE reads oracle_data.get_c() as
    QuickXPlain background (the once-A6-affected getter, now a frozen snapshot) and
    is relocated by the model-purity work, so this is exactly the seam where NE ids
    could drift while the learned bias KB (Layer 3) stays identical.
    """
    from conacq.algorithms.acqmss.generate_ne import GenerateNE
    from conacq.oracle import FMOracle
    from explanation.api import AssumptionIdAllocator

    oracle = FMOracle(str(FM_PATH))
    testsuite = _frozen_negative_testsuite()
    result_set_kb, result_assumptions = [], []
    # The frozen snapshot's next_available_id (model.next_available_id) seeds the
    # allocator; next_id is read back off it after generation.
    alloc = AssumptionIdAllocator(oracle.oracle_data.next_available_id)
    results = GenerateNE(oracle.oracle_data).generate(
        testsuite,
        oracle.get_variable_ids(),
        result_set_kb,
        result_assumptions,
        alloc,
    )
    next_id = alloc.next_id
    return {
        "per_testcase": [
            {"ne_id": r.ne_id, "ne_clause": _canon(r.ne_clause), "desc": r.desc}
            for r in results
        ],
        "result_set_kb_growth": _canon(result_set_kb),
        "next_id": next_id,
    }


def _task_id_fields(task):
    """The assumption-ID layout of a prepared task (Layer 2 golden shape)."""
    fields = {
        "set_c": _canon(task.set_c),
        "set_b": _canon(task.set_b),
        "assumptions": _canon(task.assumptions),
        "negation_map": _canon(task.negation_map),
    }
    for extra in ("set_tc", "set_tv", "set_neg_tv"):
        if hasattr(task, extra):
            fields[extra] = _canon(getattr(task, extra))
    return fields


def diagnosis_factory_ids():
    """Layer 2: DiagnosisModel.prepare_task ID layout per TaskInput factory."""
    model = diagnosis_model()
    return {
        name: _task_id_fields(model.prepare_task(task_input).task)
        for name, task_input in _task_input_cases().items()
    }


def _congen_setup(examples_path):
    """Build the ConGen checker + prepared task (mirrors tests/test_congen.py).

    The model is a pure KB: examples are loaded here and passed through
    ``prepare_task`` (was the builder's auto-prepare + ``model.task``). Same model,
    oracle snapshot, and examples as before, so the prepared task is unchanged.
    """
    from conacq.algorithms import ConGenModelBuilder
    from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
    from conacq.examples import ExampleIO
    from conacq.oracle import FMOracle
    from explanation.checker.backend import build_checker, SolverBackend
    from profiling import get_global_profiler

    profiler = get_global_profiler()
    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    model = (ConGenModelBuilder
             .from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data)
             .build())
    examples = ExampleIO.load_json(str(examples_path))
    pos = [e.assignments for e in examples.positive]
    neg = [e.assignments for e in examples.negative]
    prepared = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg))
    task = prepared.task
    checker = build_checker(
        task, SolverBackend.from_flags(use_incremental=True), "glucose4", profiler)
    return checker, task, profiler


def congen_prep_ids(examples_path):
    """Layer 2: the ConGen prepared-task ID layout (no acquisition run)."""
    checker, task, _ = _congen_setup(examples_path)
    try:
        return _task_id_fields(task)
    finally:
        checker.cleanup()


def run_congen(examples_path):
    """Layer 3: ConGen end-to-end learned KB."""
    from conacq.algorithms import ConGen

    checker, task, profiler = _congen_setup(examples_path)
    try:
        result = ConGen(checker, profiler).acquire(
            set_b=task.set_c,
            set_bg=task.set_b,
            set_tc=task.set_tc,
            set_neg_tv=task.set_neg_tv,
            negation_map=task.negation_map,
        )
        return {
            "kb_assumption_ids": _canon(result.kb_assumption_ids),
            "n_bias": result.n_bias,
            "n_mss": result.n_mss,
            "n_kb": result.n_kb,
        }
    finally:
        checker.cleanup()


def _quacq_setup():
    """Build the QuAcq model + prepared task + checker (mirrors test_quacq fixtures)."""
    from conacq.oracle import FMOracle
    from conacq.algorithms.quacq.quacq_model_builder import QuAcqModelBuilder
    from conacq.algorithms.quacq.task_preparation import QuAcqTaskInput
    from explanation.checker.backend import build_checker, SolverBackend

    oracle = FMOracle(str(FM_PATH))
    model = QuAcqModelBuilder.from_bias(str(BIAS_PATH)).with_oracle_data(oracle.oracle_data).build()
    prepared = model.prepare_task(QuAcqTaskInput(oracle.oracle_data))
    checker = build_checker(
        prepared.task, SolverBackend.from_flags(use_incremental=True))
    return oracle, model, prepared, checker


def quacq_prep_ids():
    """Layer 2: the QuAcq prepared-task ID layout (no learning run)."""
    _oracle, _model, prepared, checker = _quacq_setup()
    try:
        return _task_id_fields(prepared.task)
    finally:
        checker.cleanup()


def run_quacq():
    """Layer 3: QuAcq end-to-end learned KB + convergence."""
    from conacq.algorithms.quacq import QuAcq, DiscriminatingGenerator
    from conacq.example_generators import QueryProvider
    from profiling import get_global_profiler

    oracle, model, prepared, checker = _quacq_setup()
    task = prepared.task
    try:
        query_provider = QueryProvider(checker=checker, model=model,
                                       assignment_map=prepared.assignment_map)
        discrim_gen = DiscriminatingGenerator(
            checker=checker, model=model,
            profiler=get_global_profiler(), root_assumption=task.set_b[0], task=task)
        quacq = QuAcq.for_oracle(checker, oracle, query_provider, discrim_gen, model=model,
                                 task=task, assignment_map=prepared.assignment_map)
        result = quacq.learn(
            set_c=task.set_c, set_b=task.set_b, negation_map=task.negation_map,
            mode="oracle", max_queries=_QUACQ_MAX_QUERIES)
        return {
            "kb_assumption_ids": _canon(result.kb_assumption_ids),
            "n_kb": len(result.kb_assumption_ids),
            "n_queries": result.n_queries,
            "convergence_reason": result.convergence_reason,
            # The exact query trajectory (config asked, answer, source) — the
            # non-trivial deterministic signal that catches a QuAcq regression.
            "query_history": _canon(result.query_history),
        }
    finally:
        checker.cleanup()


def record_layer2_layer3():
    """Produce the full Layer 2 + Layer 3 golden (recorder entry point)."""
    return {
        "layer2": {
            "diagnosis_factory_ids": diagnosis_factory_ids(),
            "congen_rs_prep": congen_prep_ids(EXAMPLES_RS_1N_PATH),
            "congen_ff_prep": congen_prep_ids(EXAMPLES_FF_PATH),
            "quacq_prep": quacq_prep_ids(),
            "generate_ne_subproblem": generate_ne_subproblem(),
        },
        "layer3": {
            "congen_rs": run_congen(EXAMPLES_RS_1N_PATH),
            "congen_ff": run_congen(EXAMPLES_FF_PATH),
            "quacq": run_quacq(),
        },
    }

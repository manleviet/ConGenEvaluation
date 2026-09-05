"""Layer 4 + A6 of the T11 oracle safety net — purity/structure guards.

Each guard pins a STATED goal of the oracle arc so it cannot be quietly dropped.
A guard is written as ``xfail(strict=True)`` while its property does not yet hold;
``strict=True`` means the day it flips green (an xpass) the suite fails loudly, so
the flip is never missed. When a sub-change lands, its guard is turned into a
plain assertion — a permanent regression guard. Job ② leaving the oracle facade
(``test_oracle_does_not_provision``), the frozen ``OracleData`` snapshot, and the
two guards that came with the A6 symptom fix — no post-build mutator, no cached
base-set_c bridge — have landed and are permanent. The behavioural A6 guard is
NOT retired: it is moved onto the new surface
(``test_oracle_background_is_invariant_across_queries`` reads ``oracle_data.get_c()``
= the task's set_c), because ``frozen=True`` blocks rebinding that field, not
mutating its contents in place — so the invariant still needs a live guard (the A5
lesson).

``test_oracle_holds_no_provisioning_object`` (the arrangement guard, stronger than
the facade one) landed once ``FMOracleModel`` became a pure KB and stopped being a
KBProvider. ``test_prepare_task_is_unified_across_models`` and
``test_no_call_prepare_first_runtime_error_in_source`` landed once all three conacq
models (FMOracle · QuAcq · ConGen) carry the pure ``prepare_task`` and shed the
call-ordering RuntimeError — now permanent regression guards. GenerateNE's
relocation flipped its guard too. No xfails remain: the last one was DELETED rather
than flipped, because its target — completion reusing one persistent solver — is a
behaviour change (a persistent solver returns different completion witnesses → a
different dataset), not a refactor (ADR-0011).

Reasons describe the invariant that flips the guard, not a plan label (plan
headers get renumbered; the behavioural target is stable).
"""
import inspect
from pathlib import Path
import random

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONACQ_DIR = REPO_ROOT / "conacq"
EXPLANATION_DIR = REPO_ROOT / "explanation"


def _grep_source(needle, roots=(CONACQ_DIR, EXPLANATION_DIR)):
    """Every `path:line` under roots (excluding bytecode) whose line contains needle."""
    hits = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if needle in line:
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    return hits


# ---------------------------------------------------------------------------
# A6 — the class-level cure: the oracle answers, it does not provision
# ---------------------------------------------------------------------------
def test_oracle_does_not_provision(oracle):
    """The oracle FACADE answers questions; it does not provision the algorithm.

    Job ② (kb/assumptions/c/bg_data/root_clauses) lives on the frozen
    ``OracleData`` snapshot, never on the oracle's own surface — so consumers that
    depend on a provisioning protocol cannot bind to the live oracle. The day the
    oracle satisfies either provisioning protocol again, job ② has leaked back
    onto the actor and the door to the next A6 is open (ADR-0009).

    This checks the facade only. That the oracle does not *hold* a live
    provisioning object is a stronger property, guarded separately by
    ``test_oracle_holds_no_provisioning_object`` (flips at T11.4b)."""
    from conacq.oracle import BGProvider, KBProvider
    assert not isinstance(oracle, KBProvider)
    assert not isinstance(oracle, BGProvider)


def test_oracle_holds_no_provisioning_object(oracle):
    """The arrangement, not just the facade: the oracle holds NO live object that
    can provision. A clean facade with ``oracle._oracle_model`` still a KBProvider
    would leave job ② one attribute-access away — exactly the arrangement ADR-0009
    removes. Now enforced: the T3 recipe stripped the model's provisioning getters,
    so the held ``_oracle_model`` is no longer a KBProvider. ``oracle_data`` is the
    frozen snapshot and is meant to be held, so it is exempt. Permanent guard."""
    from conacq.oracle import BGProvider, KBProvider
    for name, val in vars(oracle).items():
        if name == "oracle_data":  # the frozen provisioning snapshot — by design
            continue
        assert not isinstance(val, (KBProvider, BGProvider)), (
            f"oracle holds a live provisioning object at .{name}"
        )


def test_oracle_background_is_invariant_across_queries(oracle):
    """The background the checker sees (``oracle_data.get_c()`` = the task's set_c)
    must not shift across membership queries — a query must never leak into the
    facts the acquisition algorithm treats as true. The task's set_c is now a frozen
    tuple, so a stray ``set_c.extend(...)`` would raise instead of poisoning the
    background silently (the A6 class); this behavioural guard still checks the
    invariant end-to-end across 50 queries. Permanent guard, moved onto the new
    surface, not retired."""
    before = list(oracle.oracle_data.get_c())
    feats = sorted(oracle.get_variables())
    rng = random.Random(1)
    for _ in range(50):
        oracle.is_valid({f: rng.choice([True, False]) for f in feats})
    assert list(oracle.oracle_data.get_c()) == before


# ---------------------------------------------------------------------------
# Layer 4 — purity & structure
# ---------------------------------------------------------------------------
def test_oracle_model_has_no_configuration_mutator():
    """The oracle model exposes no post-build mutator: nothing rebinds its task,
    so no query can shift the state a later reader sees. Permanent guard against
    reopening that seam."""
    from conacq.oracle.fm.model import FMOracleModel
    assert not hasattr(FMOracleModel, "with_configuration")


def test_no_fat_oracle_abc():
    """T11.1's own target: the fat ``Oracle`` ABC is gone. It promised a minimal
    membership interface yet carried an ``ask`` alias and two None-returning stubs
    (``get_variables``/``complete_configuration``) — a base class that hands out
    methods it fakes to None. The oracle world is now typed on the narrow
    ``@runtime_checkable`` protocols (MembershipOracle/CompletableOracle/
    CatalogProvider/GeneratorOracle), so a consumer binds to the 1-3 methods it
    actually needs, not to a class that lies about its surface. Permanent guard
    against a fourth recurrence of the add-new-keep-old shape (after the
    ``with_negation`` no-op and the hardcoded GenerateNE adapter)."""
    import conacq.oracle as oracle_pkg
    from conacq.algorithms import quacq as quacq_pkg
    assert not hasattr(oracle_pkg, "Oracle"), "fat Oracle ABC still exported from conacq.oracle"
    assert "Oracle" not in getattr(oracle_pkg, "__all__", [])
    assert not hasattr(quacq_pkg, "Oracle"), "fat Oracle ABC still re-exported from conacq.algorithms.quacq"


def test_fm_oracle_model_does_not_build_itself():
    """T6's goal: all four models have an external builder and none builds itself.
    FMOracleModel was the last self-builder — ``from_fm``/``build`` lived on the model
    — and those move to ``FMOracleModelBuilder`` (inheriting AbstractModelBuilder like
    the other three). The model is a pure KB: it holds data, it does not know how to
    load an FM. Permanent guard against the self-build smell returning."""
    from conacq.oracle import FMOracleModel
    assert not hasattr(FMOracleModel, "from_fm"), "FMOracleModel still self-builds (from_fm)"
    assert not hasattr(FMOracleModel, "build"), "FMOracleModel still self-builds (build)"


def test_fm_oracle_has_no_dead_metadata_getters():
    """The API diet (T11.4c): FMOracle's five zero-consumer metadata getters are gone.
    ``get_fm_data`` was the dead root; it alone called ``get_root_feature`` /
    ``get_num_constraints`` / ``get_next_available_id``, and ``get_cnf_clauses`` had
    only the net helper. Their sole reader was the T11 net itself — which was keeping
    a dead API alive — so the five golden keys are dropped WITH the methods (the one
    sanctioned golden-key drop; the drop IS this commit's purpose). Mechanism check
    (hasattr), not ``__all__``. Permanent guard against the dead surface returning."""
    from conacq.oracle import FMOracle
    for name in ("get_fm_data", "get_root_feature", "get_num_constraints",
                 "get_next_available_id", "get_cnf_clauses"):
        assert not hasattr(FMOracle, name), f"FMOracle still exposes dead getter {name}"


def test_one_task_preparation_strategy_and_no_dead_mode_name():
    """The twin prep-strategy ABCs collapse to one ``TaskPreparationStrategy``, and
    the dead ``mode_name`` is gone from all three concrete strategies. ``mode_name``
    had 0 call sites — the ABC forced every implementer to supply something nobody
    read (the inverse of ADR-0010, where the fat ABC carried real enforcement).
    Checked at the DOOR (attribute) AND the LABEL (__all__), per the 4c2 lesson."""
    import explanation.api as api
    from explanation.models.task_preparation import (
        DiagnosisTaskPreparation, TestCaseTaskPreparation)
    from conacq.algorithms.acqmss.task_preparation import ConGenTaskPreparation

    for name in ("TestCaseTaskPreparationStrategy", "DiagnosisTaskPreparationStrategy"):
        assert not hasattr(api, name), f"{name} still exported (door)"
        assert name not in getattr(api, "__all__", []), f"{name} still in api.__all__ (label)"
    assert hasattr(api, "TaskPreparationStrategy"), "the merged ABC is not exported"
    for cls in (DiagnosisTaskPreparation, TestCaseTaskPreparation, ConGenTaskPreparation):
        assert not hasattr(cls, "mode_name"), f"{cls.__name__} still carries the dead mode_name"


def test_no_post_negation_build_hook():
    """The 0-override ``_post_negation_build`` hook is gone. Its docstring reserved it
    for folding a frozen OracleData snapshot at build time — 4c shipped and never
    used it; the reservation expired. T6: a 0-override hook that survives one more
    task starts to grow roots. Permanent guard."""
    from conacq.oracle_bias_model_builder import OracleBiasModelBuilder
    assert not hasattr(OracleBiasModelBuilder, "_post_negation_build")


def test_declaring_a_role_without_implementing_it_fails_at_construction():
    """The good half of the deleted fat ABC, restored via ``@abstractmethod`` on the
    narrow protocol members (ADR-0010): a class that DECLARES a role by inheriting
    its protocol but never implements the method is abstract — it raises TypeError
    at construction, not silently at the first query deep in QuAcq's inner loop after
    the eval has been running (the A6 shape: fails silently, no exception, no red
    test). This is the machine-checked half; the class-line declaration is the point
    (ADR-0010). Permanent guard."""
    from conacq.oracle import MembershipOracle

    class ForgotIsValid(MembershipOracle):
        pass

    with pytest.raises(TypeError):
        ForgotIsValid()


def test_prepare_task_is_unified_across_models():
    """The three SOLVE-TASK models share one facade: prepare_task(self, task_input).
    FMOracleModel is deliberately NOT here — its task is fully FM-determined, so it
    left the contract for prepare() -> OracleData (no per-task input) rather than keep
    a received-then-discarded task_input. Signature is only a PROXY for the real T11.4
    invariant (purity); test_prepare_is_pure_no_task_state_leaks checks the property
    itself."""
    from explanation.models.pysat_diagnosis_model import DiagnosisModel
    from conacq.algorithms.acqmss.congen_model import ConGenModel
    from conacq.algorithms.quacq.quacq_model import QuAcqModel

    for model in (DiagnosisModel, ConGenModel, QuAcqModel):
        assert hasattr(model, "prepare_task"), f"{model.__name__} lacks prepare_task"
        sig = inspect.signature(model.prepare_task)
        params = list(sig.parameters)
        # The FACADE is the required prefix: every model is callable as
        # prepare_task(task_input) and nothing else is mandatory. Extra parameters are
        # allowed only if optional — that is how `minimize` and `profiler` are carried,
        # and ConGen takes an optional `profiler` so GenerateNE's preprocessing
        # QuickXplain is counted. A NEW REQUIRED parameter is what the guard forbids,
        # because that is what would fork the facade.
        assert params[:2] == ["self", "task_input"], f"{model.__name__}: {params}"
        required_extra = [
            n for n in params[2:]
            if sig.parameters[n].default is inspect.Parameter.empty
            and sig.parameters[n].kind not in (inspect.Parameter.VAR_POSITIONAL,
                                               inspect.Parameter.VAR_KEYWORD)
        ]
        assert not required_extra, \
            f"{model.__name__} adds required params beyond task_input: {required_extra}"


def test_prepare_is_pure_no_task_state_leaks():
    """The real T11.4 invariant the unified-signature guard only PROXIES: preparing does
    not mutate the model, and each call returns a fresh independent task. A model could
    satisfy the signature check yet still do ``self._task = ...; return new`` — this
    checks the property directly: vars(model) unchanged across two prepares, distinct
    task objects, equal content. Covers the three oracle-data models (FMOracle via its
    OracleData facade, ConGen, QuAcq). DiagnosisModel is NOT covered here (its
    construction needs an FM transform) and is not covered elsewhere — measured; → T17.
    Skips without the REAL-FM-7 fixtures."""
    from tests.resource_paths import FM_PATH, BIAS_PATH
    if not (FM_PATH.exists() and BIAS_PATH.exists()):
        pytest.skip("REAL-FM-7 fixtures not found")
    from conacq.oracle import FMOracle
    from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
    from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
    from conacq.algorithms.quacq.quacq_model_builder import QuAcqModelBuilder
    from conacq.algorithms.quacq.task_preparation import QuAcqTaskInput

    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    try:
        od = oracle.oracle_data
        congen = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
                  .with_oracle_data(od).build())
        quacq = (QuAcqModelBuilder.from_bias(str(BIAS_PATH))
                 .with_oracle_data(od).build())
        cases = [
            (oracle._oracle_model, lambda m: m.prepare()),
            (congen, lambda m: m.prepare_task(
                ConGenTaskInput.from_examples(od, [{"java": True}], []))),
            (quacq, lambda m: m.prepare_task(QuAcqTaskInput(od))),
        ]
        for model, prep in cases:
            before = dict(vars(model))
            p1 = prep(model)
            p2 = prep(model)
            assert vars(model) == before, f"{type(model).__name__} mutated on prepare"
            assert p1.task is not p2.task, f"{type(model).__name__} reused a task object"
            assert p1.task.set_c == p2.task.set_c, f"{type(model).__name__} content drifted"
    finally:
        oracle.cleanup()


def test_every_prepare_strategy_inherits_the_contract():
    """Population sweep — the guard that watches the author, not a remembered list.

    AST-scan explanation/ + conacq/ for EVERY class defining a method named
    ``prepare`` that returns ``PreparedTask``, then assert each is a subclass of
    ``TaskPreparationStrategy``. It names no concrete strategy in its assertion: it
    enumerates the population by the contract's own shape, so a strategy added later
    that forgets to inherit is caught without editing this test.

    Two exclusions, both by MECHANISM, not by a by-name exception list:
      - ``issubclass`` is reflexive, so ``TaskPreparationStrategy`` itself passes free.
      - the filter is the method NAME ``prepare`` + a ``PreparedTask`` return, so
        ``prepare_task`` (the MODEL contract, guarded by
        ``test_prepare_task_is_unified_across_models``) and ``build_oracle_data``
        (``-> OracleData``, a different operation) drop out on their own.

    Why it exists: the model-layer guard above checks ``prepare_task`` and never saw
    ``QuAcqTaskPreparation``'s drifted strategy signature. This guard watches the
    strategy layer the model-layer guard is blind to. Permanent guard."""
    import ast
    import importlib
    import pathlib

    from explanation.api import TaskPreparationStrategy

    repo = pathlib.Path(__file__).resolve().parent.parent
    checked = []
    offenders = []
    for pkg in ("explanation", "conacq"):
        for path in (repo / pkg).rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if (isinstance(item, ast.FunctionDef)
                            and item.name == "prepare"
                            and item.returns is not None
                            and "PreparedTask" in ast.unparse(item.returns)):
                        module = ".".join(path.relative_to(repo).with_suffix("").parts)
                        cls = getattr(importlib.import_module(module), node.name)
                        checked.append(node.name)
                        if not issubclass(cls, TaskPreparationStrategy):
                            offenders.append(f"{node.name} ({module})")
    assert checked, "population scan found no prepare()->PreparedTask classes — the scan itself is broken"
    assert not offenders, (
        "classes with prepare()->PreparedTask that do not inherit TaskPreparationStrategy: "
        + ", ".join(offenders))


def test_quacq_strategy_signature_matches_the_contract():
    """QuAcqTaskPreparation.prepare takes (self, model, task_input) like every other
    strategy — not (self, model, oracle_data). The drift existed because prepare_task
    unpacked task_input.oracle_data before handing it down; the strategy now receives
    the whole QuAcqTaskInput and extracts oracle_data itself. Permanent guard."""
    from conacq.algorithms.quacq.task_preparation import QuAcqTaskPreparation
    params = list(inspect.signature(QuAcqTaskPreparation.prepare).parameters)
    assert params == ["self", "model", "task_input"], params


def test_fm_oracle_task_prep_is_one_oracle_data_method():
    """FMOracleTaskPreparation collapses to a single ``prepare(model) -> OracleData``.
    The T11b.3 two-view split (``build_oracle_data`` + ``prepare_task`` sharing the
    unnamed 5-tuple ``_prepare``) is gone: OracleData already carries ``.task`` +
    ``.assignment_map`` — the only things any consumer reads (``describe``: 0 readers).
    One view needs no shared private core. It still does NOT inherit
    TaskPreparationStrategy — ``prepare`` here returns OracleData, a different
    operation, so the population guard excludes it by return type. This supersedes the
    T11b.3 intermediate rename guard. Permanent guard."""
    from conacq.oracle.fm.task_preparation import FMOracleTaskPreparation
    from explanation.api import TaskPreparationStrategy
    assert hasattr(FMOracleTaskPreparation, "prepare"), "the single OracleData factory is missing"
    for gone in ("build_oracle_data", "prepare_task", "_prepare"):
        assert not hasattr(FMOracleTaskPreparation, gone), f"{gone} should be folded away"
    assert not issubclass(FMOracleTaskPreparation, TaskPreparationStrategy), \
        "the static OracleData factory must not be forced into the strategy hierarchy"


def test_fm_oracle_model_facade_returns_oracle_data():
    """FMOracleModel's facade is ``prepare() -> OracleData`` — no received-then-discarded
    ``task_input``. The oracle's snapshot is fully FM-determined, so unlike the three
    solve-task models it takes no per-task input and returns OracleData, not a
    PreparedTask. ``prepare_task`` is gone from the oracle model. Permanent guard."""
    from conacq.oracle.fm.model import FMOracleModel
    from conacq.oracle import OracleData
    assert hasattr(FMOracleModel, "prepare"), "FMOracleModel lost its prepare facade"
    assert "prepare_task" not in vars(FMOracleModel), "the discarded-input prepare_task lingers"
    params = list(inspect.signature(FMOracleModel.prepare).parameters)
    assert params == ["self"], params
    assert inspect.signature(FMOracleModel.prepare).return_annotation is OracleData


def test_fm_oracle_has_no_model_to_config_wrapper():
    """FMOracle._model_to_config — a 1-line wrapper over ``variable_literals_to_config``
    with two call-sites three lines apart in one function — is inlined (same family as
    the ``config_to_assumptions`` wrapper deleted at 4b2; it survived only because it
    was private). ``QuAcqModel.model_to_config`` STAYS: identical code, different role —
    a public facade with cross-module callers. Same code, two fates, decided by who
    calls from where. Permanent guard."""
    from conacq.oracle import FMOracle
    assert not hasattr(FMOracle, "_model_to_config")


def test_oracle_prepares_through_the_model_facade():
    """The oracle goes through the model facade (``self._oracle_model.prepare()``)
    instead of reaching straight into the strategy — the three solve-task models all
    go through their facade; the oracle was the only one climbing through the window.
    So ``oracle.py`` no longer imports FMOracleTaskPreparation. Permanent guard."""
    import conacq.oracle.fm.oracle as oracle_mod
    assert not hasattr(oracle_mod, "FMOracleTaskPreparation"), \
        "oracle.py still imports the strategy directly instead of going through model.prepare()"


def test_oracle_data_snapshot_is_frozen():
    """Job ② is an immutable value: OracleData is a frozen dataclass, so nothing
    a query does can rebind what the provisioning consumers read. Permanent
    guard (landed with the role split)."""
    from conacq.oracle import OracleData
    assert OracleData.__dataclass_params__.frozen


def test_base_set_c_is_gone_from_source():
    """The cached base-set_c bridge is gone from the oracle source; set_c is read
    from the frozen task. Permanent guard."""
    hits = _grep_source("base_set_c")
    assert hits == [], "base_set_c still present:\n  " + "\n  ".join(hits)


def test_no_call_prepare_first_runtime_error_in_source():
    hits = _grep_source("Call prepare() first")
    assert hits == [], "call-ordering RuntimeError still present:\n  " + "\n  ".join(hits)


def test_generate_ne_not_exported_from_algorithms():
    """GenerateNE is a task-preparation internal — its only production caller is
    ConGenTaskPreparation and it is not in the solve loop — not an algorithm. It must
    be absent from BOTH algorithm facades (top-level ``conacq.algorithms`` and the
    ``conacq.algorithms.acqmss`` subpackage), checked at BOTH levels:

    - the LABEL — ``__all__``, which only governs ``import *``; and
    - the DOOR — the bound attribute. ``from pkg import GenerateNE`` works off the
      module's ``from .generate_ne import GenerateNE`` statement, NOT ``__all__``, so
      a re-added import binding that never touches ``__all__`` would leave the label
      clean while the door swings open. Checking only the label is the same
      one-symbol-watched / wrong-symbol-lives-on hole; this mirrors the fat-ABC guard,
      which pins ``not hasattr(...)`` and ``not in __all__`` both."""
    import conacq.algorithms as algorithms
    import conacq.algorithms.acqmss as acqmss
    for pkg in (algorithms, acqmss):
        assert "GenerateNE" not in getattr(pkg, "__all__", []), f"GenerateNE in {pkg.__name__}.__all__ (label)"
        assert not hasattr(pkg, "GenerateNE"), f"GenerateNE bound on {pkg.__name__} (door)"


# ---------------------------------------------------------------------------
# Deep-immutable Task — list-valued solve fields are tuples (permanent guard).
# ---------------------------------------------------------------------------
def test_task_is_deeply_frozen():
    """The Task family is deeply immutable: the list-valued solve fields are tuples
    that reject in-place mutation, and ``negation_map`` is a ``FrozenDict``, so a
    task cannot be poisoned after construction — the same silent-drift class the
    oracle arc kept killing. Built with a plain ``list``/``dict`` so it passes only
    if ``__post_init__`` actually coerces, not merely if the annotation changed —
    the mechanism, not the label. ``negation_map`` is a ``FrozenDict`` (a read-only
    ``dict`` subclass that still pickles) rather than the abandoned
    ``MappingProxyType`` (ADR-0007/0012), which does not pickle → FastDiagP ships
    tasks to workers. Both the identity type AND the mutate-block are pinned."""
    from explanation.models.task_preparation import DiagnosisTask, TestCaseTask
    from conacq.algorithms.acqmss.task_preparation import ConGenTask
    from conacq.algorithms.quacq.task_preparation import QuAcqTask

    for task_cls in (DiagnosisTask, TestCaseTask, ConGenTask, QuAcqTask):
        task = task_cls(set_c=[1], negation_map={1: 2})
        # list-valued solve field → tuple (rejects in-place mutation)
        with pytest.raises((TypeError, AttributeError)):
            task.set_c.append(999)  # a tuple rejects this; a list would not
        # mapping-valued field → FrozenDict: pin the identity type ...
        assert type(task.negation_map).__name__ == "FrozenDict"
        # ... AND the mutate-block mechanism (a plain dict would accept this).
        with pytest.raises(TypeError):
            task.negation_map[3] = 4


def test_no_position_slicing_in_task_preparation():
    """Set carving reads the primitives' RETURNED originals, not offset+stride over the
    flat assumption list. So ``slice_assumptions``, its stride constant, and the
    per-call re-inference (``has_negated_forms``: prepare_kb already knows whether it
    called allocate_pair or allocate) are gone — along with the position batons that
    made two ID-mismatch bugs shippable. ``_assign_sets`` survives (assigning roles per
    scenario is a real operation); only its inputs changed. Permanent guard."""
    import explanation.api as api
    import explanation.models.task_preparation as tp
    assert not hasattr(tp, "slice_assumptions"), "position-slicing helper is back"
    assert not hasattr(tp, "_ASSUMPTION_PAIR_STRIDE"), "the magic stride constant is back"
    assert not hasattr(api, "slice_assumptions"), "slice_assumptions still exported (door)"
    assert "slice_assumptions" not in getattr(api, "__all__", []), "still in api.__all__ (label)"



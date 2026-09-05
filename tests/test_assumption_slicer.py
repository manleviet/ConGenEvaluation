"""Safety net pinning the assumption-ID layout produced by every slice site.

The five ``_assign_sets`` / FM-only slice sites carve set_b / set_c / set_tc /
set_tv out of the flat ``assumptions`` list by offset+stride arithmetic. That
arithmetic determines which assumption literal ends up in which set, so the
whole system's diagnoses depend on it being byte-identical.

These tests pin the EXACT output IDs (length + boundary values + stride) for
controlled inputs BEFORE the arithmetic is refactored behind a shared
``slice_assumptions`` helper. Same inputs → same IDs must hold after the
refactor; a red test means the ID layout drifted. This net also guards the
future AssumptionIdAllocator work.

The four ``_assign_sets`` methods are pure functions of (assumptions, indices,
flags), so they are exercised directly with synthetic lists (values = 100+index,
etc., making the picked indices obvious). Site 5 (an inline slice) is pinned via
a synthetic ``FMOracleModel.prepare()``, plus one real end-to-end anchor through
a transformed feature model.
"""
from flamapy.metamodels.fm_metamodel.transformations import UVLReader

from explanation.models.task_preparation import (
    DiagnosisTaskPreparation,
    # Aliased: leading-"Test" name would trip pytest's class collector.
    TestCaseTaskPreparation as _TestCaseTaskPreparation,
    TaskInput,
)
import pytest

from explanation.transformations.fm_to_diag_pysat import FmToDiagPysat
from conacq.oracle import FMOracle
from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
from conacq.algorithms.quacq.quacq_model_builder import QuAcqModelBuilder
from conacq.algorithms.quacq.task_preparation import QuAcqTaskInput
from conacq.oracle.fm.model import FMOracleModel
from tests.resource_paths import DATA_DIR

FM_PATH = DATA_DIR / "fms" / "REAL-FM-7.uvl"
BIAS_PATH = DATA_DIR / "bias" / "REAL-FM-7-bias.json"


def _strided(seq):
    """True iff seq is a constant-stride arithmetic sequence (len < 2 → True)."""
    return all(seq[k + 1] - seq[k] == seq[1] - seq[0] for k in range(len(seq) - 1))


# ---------------------------------------------------------------------------
# Site 1 — DiagnosisTaskPreparation._assign_sets (5 use-case branches)
# Now a pure role-assignment over the primitives' RETURNED originals (no offset+
# stride slicing). Exercised directly with synthetic originals lists — the file's
# stated design — where fm_originals[0] is the root. Expected set_b/set_c are the
# same old-code literals the position-slicing version produced; the real-prepare()
# integration is independently gated by the immobile layer-2 golden
# (test_t11_prepared_task_ids::test_diagnosis_factory_id_layout_is_pinned, 7/7).
# ---------------------------------------------------------------------------
def test_site1_config_no_cf():
    """C = configuration, B = FM + root."""
    dia = DiagnosisTaskPreparation()
    set_b, set_c = dia._assign_sets(
        TaskInput(configuration={"x": True}),
        fm_originals=[100, 102, 104], config_originals=list(range(106, 116)), tc_originals=[])
    assert set_b == [100, 102, 104]
    assert set_c == list(range(106, 116))


def test_site1_config_with_cf():
    """C = configuration + FM (no root), B = root only."""
    dia = DiagnosisTaskPreparation()
    set_b, set_c = dia._assign_sets(
        TaskInput(configuration={"x": True}, with_cf_in_c=True),
        fm_originals=[100, 102, 104], config_originals=list(range(106, 116)), tc_originals=[])
    assert set_b == [100]
    assert set_c == [102, 104] + list(range(106, 116))


def test_site1_test_case():
    """C = FM constraints (no root), B = root + test case."""
    dia = DiagnosisTaskPreparation()
    set_b, set_c = dia._assign_sets(
        TaskInput(test_case={"x": True}),
        fm_originals=[100, 102, 104, 106, 108], config_originals=[],
        tc_originals=[110, 111, 112, 113, 114, 115])
    assert set_b == [100, 110, 111, 112, 113, 114, 115]
    assert set_c == [102, 104, 106, 108]


def test_site1_redundancy_fm():
    """WipeOutR_FM: C = FM constraint originals (no root), B = {}."""
    dia = DiagnosisTaskPreparation()
    set_b, set_c = dia._assign_sets(
        TaskInput(for_redundancy=True),
        fm_originals=[100, 102, 104, 106, 108, 110, 112, 114], config_originals=[], tc_originals=[])
    assert set_b == []
    assert set_c == [102, 104, 106, 108, 110, 112, 114]
    assert _strided(set_c)


def test_site1_fm_diagnosis():
    """FM diagnosis: B = root, C = FM constraints (no root)."""
    dia = DiagnosisTaskPreparation()
    set_b, set_c = dia._assign_sets(
        TaskInput(), fm_originals=list(range(100, 116)), config_originals=[], tc_originals=[])
    assert set_b == [100]
    assert set_c == list(range(101, 116))


# ---------------------------------------------------------------------------
# Site 2 — TestCaseTaskPreparation._assign_sets (KBDiag role assignment)
# Now a pure role assignment: TC = positive originals, TV = negative originals
# (the returns of prepare_testsuite_with_negation). The non-empty set_tv branch is
# pinned HERE with synthetic values — the layer-2 golden has no ±negatives scenario
# (measured: its testcases/redundancy_t both have set_tv == []).
# ---------------------------------------------------------------------------
def test_site2_testcase_with_negatives():
    tc = _TestCaseTaskPreparation()
    set_b, set_c, set_tc, set_tv = tc._assign_sets(
        fm_originals=[200, 201, 202, 203],
        pos_original_ids=[204, 206], neg_original_ids=[208, 210, 212, 214])
    assert set_b == [200]
    assert set_c == [201, 202, 203]
    assert set_tc == [204, 206]                # positive test-case originals
    assert set_tv == [208, 210, 212, 214]      # negative test-case originals


def test_site2_testcase_without_negatives():
    tc = _TestCaseTaskPreparation()
    set_b, set_c, set_tc, set_tv = tc._assign_sets(
        fm_originals=[200, 201, 202, 203],
        pos_original_ids=[204, 206, 208, 210], neg_original_ids=[])
    assert set_b == [200]
    assert set_c == [201, 202, 203]
    assert set_tc == [204, 206, 208, 210]
    assert set_tv == []


# ---------------------------------------------------------------------------
# Site 3 — ConGenTaskPreparation.prepare() set layout (conacq)
# The bias-originals + E+-originals now come straight off the allocator (set_c =
# prepare_kb(...)), not a stride slice. Pinned on the OUTPUT of the real prepare(),
# with literals RECORDED FROM THE PRE-ALLOCATOR CODE (git-stash), so this is not a
# tautology with the rewire. set_tv == [] is ConGen's real behaviour: E- becomes NE
# in set_neg_tv, never set_tv — the non-empty set_tv carve lives on the surviving
# TestCaseTaskPreparation._assign_sets and is pinned by site 2.
# ---------------------------------------------------------------------------
def test_site3_congen_prepared_set_layout():
    if not FM_PATH.exists() or not BIAS_PATH.exists():
        pytest.skip("REAL-FM-7 fixtures not found")
    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data).build())
    # 1 positive example, no negatives → set_tc non-empty, set_tv empty.
    task = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, [{"java": True}], [])).task
    # Acquisition BG is domain-only (∅ for a boolean FM); root assumption 28 is a
    # post-acquisition axiom on root_axiom, not runtime BG. QuAcq (site 4) keeps 28
    # in set_b — its prep is a separate strategy, deliberately untouched here.
    assert list(task.set_b) == []
    assert list(task.root_axiom) == [28]
    assert list(task.set_c[:4]) == [116, 118, 120, 122]   # bias originals, stride 2
    assert len(task.set_c) == 295
    assert _strided(task.set_c)
    assert list(task.set_tc) == [706]               # the E+ testcase original
    assert list(task.set_tv) == []                  # E- → NE (set_neg_tv), not set_tv
    oracle.cleanup()


# ---------------------------------------------------------------------------
# Site 4 — QuAcqTaskPreparation.prepare() set layout (conacq)
# set_c = bias originals off the allocator; set_b = the BG root. Literals recorded
# from the pre-allocator code (git-stash).
# ---------------------------------------------------------------------------
def test_site4_quacq_prepared_set_layout():
    if not FM_PATH.exists() or not BIAS_PATH.exists():
        pytest.skip("REAL-FM-7 fixtures not found")
    oracle = FMOracle(str(FM_PATH))
    model = (QuAcqModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data).build())
    task = model.prepare_task(QuAcqTaskInput(oracle.oracle_data)).task
    assert list(task.set_b) == [28]
    assert list(task.set_c[:4]) == [116, 118, 120, 122]   # bias originals, stride 2
    assert len(task.set_c) == 295
    assert _strided(task.set_c)
    oracle.cleanup()


# ---------------------------------------------------------------------------
# Site 5 — fm_oracle_model FM-only slice (originals of Part 3), via a synthetic
# FMOracleModel. Pins: stride 2, starts at the first assumption id, and is
# DISJOINT from the Part-4 variable-assignment assumptions.
# ---------------------------------------------------------------------------
def _synthetic_oracle_model():
    model = FMOracleModel()
    model.constraint_map = {"root": [[1]], "c2": [[-1, 2]], "c3": [[-1, 3]]}
    model.negated_constraint_map = {
        "NOT(root)": [[-1]], "NOT(c2)": [[1], [-2]], "NOT(c3)": [[1], [-3]],
    }
    model.name_to_id = {"f1": 1, "f2": 2, "f3": 3}
    model.next_available_id = 4
    return model


def test_site5_fm_only_slice_layout():
    model = _synthetic_oracle_model()
    first_id = model.next_available_id
    prepared = model.prepare()

    # With no prep-time configuration, task.set_c IS the FM-only slice.
    fm_only = list(prepared.task.set_c)
    assert fm_only == [4, 6, 8]          # originals of the three FM-constraint pairs
    assert fm_only[0] == first_id
    assert _strided(fm_only)             # stride 2

    assignment_assumptions = (
        list(prepared.assignment_map.pos_assignment_to_assumption.values())
        + list(prepared.assignment_map.neg_assignment_to_assumption.values())
    )
    # FM-only slice must contain NO variable-assignment assumption.
    assert set(fm_only).isdisjoint(assignment_assumptions)


# ---------------------------------------------------------------------------
# Real end-to-end anchor — a transformed FM through DiagnosisModel.prepare_task.
# arcade-game reserves next_available_id 156 (see test_transformations_*), so the
# redundancy set_c (FM originals, root pair skipped) starts at 158, stride 2.
# ---------------------------------------------------------------------------
def test_arcade_game_redundancy_set_c_layout():
    fm = UVLReader(str(DATA_DIR / "fms" / "arcade-game.uvl")).transform()
    model = FmToDiagPysat(fm, create_negation=True).transform()
    set_c = model.prepare_task(TaskInput.redundancy_fm()).task.set_c
    assert len(set_c) == 70
    assert set_c[0] == 158       # 156 (root) + 2 → skip the root pair
    assert set_c[-1] == 296
    assert _strided(set_c)       # stride 2 throughout

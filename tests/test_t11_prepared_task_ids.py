"""Layer 2 of the T11 oracle safety net — prepared-task ID golden.

T11 rewrites task preparation across the models; the assumption-ID layout must
not move (this repo has been bitten twice by exactly that). The golden
(``fixtures/t11_oracle_net/layer23_prepared_and_e2e.json``) was recorded from the
CURRENT code and is frozen; these tests re-run preparation on the (possibly
refactored) code and compare to it — literal-ID characterization, not
call-compare-to-call.

Coverage: DiagnosisModel.prepare_task over all 7 TaskInput factories, the ConGen
and QuAcq prepared-task ID layouts, and the GenerateNE per-testcase sub-problem
(NE-clause ids + set_kb growth) — the seam where NE ids could drift while the
learned bias KB stays identical.
"""
import pytest

from tests import t11_e2e_harness as harness
from tests.t11_oracle_net_helpers import FIXTURES_DIR, load_json

# Re-baselined 2026-08-28: the negative examples are prepared as one constraint each
# rather than folded into a single assumption, so ``set_neg_tv`` carries three ids on
# the ff fixture instead of one and each gains a ``negation_map`` entry. The diagnosis
# and QuAcq id layouts held, which is what says the change is confined to ConGen.
_GOLDEN_PATH = FIXTURES_DIR / "layer23_prepared_and_e2e.json"


@pytest.fixture(scope="module")
def layer2_golden():
    if not _GOLDEN_PATH.exists():
        pytest.fail(
            "golden fixture missing — the net is NOT running; "
            "run PYTHONPATH=. python3 scripts/build_t11_oracle_net_fixtures.py"
        )
    return load_json(_GOLDEN_PATH)["layer2"]


def test_diagnosis_factory_id_layout_is_pinned(layer2_golden):
    assert harness.diagnosis_factory_ids() == layer2_golden["diagnosis_factory_ids"]


def test_congen_rs_prepared_task_ids(layer2_golden):
    assert harness.congen_prep_ids(harness.EXAMPLES_RS_1N_PATH) == \
        layer2_golden["congen_rs_prep"]


def test_congen_ff_prepared_task_ids(layer2_golden):
    assert harness.congen_prep_ids(harness.EXAMPLES_FF_PATH) == \
        layer2_golden["congen_ff_prep"]


def test_quacq_prepared_task_ids(layer2_golden):
    assert harness.quacq_prep_ids() == layer2_golden["quacq_prep"]


def test_generate_ne_subproblem_ids(layer2_golden):
    """The GenerateNE per-testcase NE-clause ids + set_kb growth must not move.

    Pinned directly (not just via E2E): the learned bias KB can stay identical
    while NE-clause ids drift, and GenerateNE reads the A6-affected get_c() and
    is relocated by the purity work — so this seam needs its own golden.
    """
    assert harness.generate_ne_subproblem() == layer2_golden["generate_ne_subproblem"]


# --- readable structural anchors (mirror the T5 slicer len/first/strided style) ---
def _strided(seq, step):
    return all(seq[i + 1] - seq[i] == step for i in range(len(seq) - 1))


def test_redundancy_fm_set_c_is_strided_originals(layer2_golden):
    """redundancy_fm C = FM-constraint originals (paired layout, stride 2)."""
    set_c = layer2_golden["diagnosis_factory_ids"]["redundancy_fm"]["set_c"]
    assert set_c and _strided(set_c, 2)


def test_fm_diagnosis_set_b_is_the_root_only(layer2_golden):
    """fm_diagnosis B = the single root assumption; C = all remaining FM ids."""
    fields = layer2_golden["diagnosis_factory_ids"]["fm_diagnosis"]
    assert len(fields["set_b"]) == 1
    assert fields["set_b"][0] < fields["set_c"][0]

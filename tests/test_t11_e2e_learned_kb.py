"""Layer 3 of the T11 oracle safety net — end-to-end learned-KB golden.

Runs ConGen and QuAcq end-to-end through the oracle on REAL-FM-7 and pins the
learned KB + counts against a frozen golden recorded from the CURRENT code. This
is the brief's stated acceptance ("diagnoses / membership / completion identical
to baseline") and the only layer that exercises the algorithms *through* the
oracle. It is trustworthy because the generators are now instance-seeded
(determinism precondition) and the inputs are fixed fixtures.

Note: neither result type exposes a ``diagnoses`` attribute; the pinnable
learned-KB quantities are ``kb_assumption_ids`` (both), ``n_mss`` (ConGen only),
and ``n_kb``. At the golden's low budget (``_QUACQ_MAX_QUERIES``) QuAcq's oracle
arm learns few/no constraints, so it pins the exact query TRAJECTORY
(``query_history``) plus convergence — a deterministic regression tripwire.
(Oracle-mode LEARNING at a generous budget — non-empty KB, converges via
no_query — is asserted separately in tests/test_quacq.py::TestQuAcqOracleProgress,
after the liveness fix that stopped the FindC=⊥ spin.)

**Re-baselined 2026-08-28** for the memorized-negative fixes. Only the ConGen
entries moved (``n_kb`` 17→16 on rs, 15→17 on ff, and the assumption-id lists);
the QuAcq entry held byte-for-byte, as it must — QuAcq builds no memorized
negatives and never calls Reduce, so it shares no code path with the change.
"""
import pytest

from tests import t11_e2e_harness as harness
from tests.t11_oracle_net_helpers import FIXTURES_DIR, load_json

_GOLDEN_PATH = FIXTURES_DIR / "layer23_prepared_and_e2e.json"


@pytest.fixture(scope="module")
def layer3_golden():
    if not _GOLDEN_PATH.exists():
        pytest.fail(
            "golden fixture missing — the net is NOT running; "
            "run PYTHONPATH=. python3 scripts/build_t11_oracle_net_fixtures.py"
        )
    return load_json(_GOLDEN_PATH)["layer3"]


def test_congen_rs_learned_kb_identical(layer3_golden):
    assert harness.run_congen(harness.EXAMPLES_RS_1N_PATH) == layer3_golden["congen_rs"]


def test_congen_ff_learned_kb_identical(layer3_golden):
    assert harness.run_congen(harness.EXAMPLES_FF_PATH) == layer3_golden["congen_ff"]


def test_quacq_learned_kb_identical(layer3_golden):
    assert harness.run_quacq() == layer3_golden["quacq"]

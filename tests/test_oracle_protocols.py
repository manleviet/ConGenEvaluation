"""The narrow oracle protocols are real contracts, and they distinguish.

The oracle does two jobs, and ADR-0009 split them across two objects:
- **FMOracle answers questions (job ①)** — it satisfies the *answer* protocols
  (MembershipOracle, CompletableOracle, CatalogProvider, GeneratorOracle) and
  deliberately does NOT satisfy the *provision* protocols.
- **OracleData provisions the algorithm (job ②)** — the frozen snapshot satisfies
  BGProvider + KBProvider (and thus the PreparationOracle composite).

FMOracleModel satisfies CatalogProvider (it owns the catalog). Crucially, the
protocols must DISCRIMINATE: an object with only is_valid is a MembershipOracle
but not a KBProvider, and vice versa. A protocol that everything satisfies is a
decorative protocol — this test is what keeps these honest.
"""
import pytest

from conacq.oracle import (
    FMOracle,
    CachedOracle,
    UserPromptOracle,
    MembershipOracle,
    CompletableOracle,
    CatalogProvider,
    BGProvider,
    KBProvider,
    GeneratorOracle,
    PreparationOracle,
)
from tests.resource_paths import FM_PATH

# Job ① — what the oracle answers.
_ANSWER_PROTOCOLS = [
    MembershipOracle, CompletableOracle, CatalogProvider, GeneratorOracle,
]
# Job ② — what the frozen OracleData snapshot provisions (never the live oracle).
_PROVISION_PROTOCOLS = [BGProvider, KBProvider, PreparationOracle]


@pytest.fixture(scope="module")
def fm_oracle():
    if not FM_PATH.exists():
        pytest.skip(f"feature model not found: {FM_PATH}")
    return FMOracle(str(FM_PATH))


@pytest.mark.parametrize("protocol", _ANSWER_PROTOCOLS, ids=lambda p: p.__name__)
def test_fm_oracle_satisfies_answer_protocols(fm_oracle, protocol):
    """The oracle answers questions (job ①): membership, completion, catalog."""
    assert isinstance(fm_oracle, protocol)


@pytest.mark.parametrize("protocol", _PROVISION_PROTOCOLS, ids=lambda p: p.__name__)
def test_fm_oracle_does_not_satisfy_provision_protocols(fm_oracle, protocol):
    """The oracle does NOT provision (job ②) — that surface moved to the frozen
    OracleData snapshot (ADR-0009). The structural expression of that cure."""
    assert not isinstance(fm_oracle, protocol)


@pytest.mark.parametrize("protocol", _PROVISION_PROTOCOLS, ids=lambda p: p.__name__)
def test_oracle_data_satisfies_provision_protocols(fm_oracle, protocol):
    """OracleData is the provisioning surface: BGProvider + KBProvider, hence the
    PreparationOracle composite."""
    assert isinstance(fm_oracle.oracle_data, protocol)


def test_fm_oracle_exposes_the_model_catalog(fm_oracle):
    """The catalog DATA lives on FMOracleModel (name_to_id/id_to_name); the oracle
    is the CatalogProvider and derives its answer from that data. The model no
    longer carries get_variables/get_variable_ids accessors (a pure KB, like
    DiagnosisModel) — two accessors for one truth is the pattern T3 removes."""
    model = fm_oracle._oracle_model
    assert isinstance(fm_oracle, CatalogProvider)
    assert fm_oracle.get_variable_ids() == dict(model.name_to_id)
    assert fm_oracle.get_variables() == set(model.name_to_id.keys())


# --- discrimination: the roles must be distinguishable, not decorative ---
class _OnlyMembership:
    def is_valid(self, assignments):
        return True


class _OnlyKB:
    def get_kb(self):
        return []

    def get_assumptions(self):
        return []

    def get_c(self):
        return []


def test_membership_only_object_is_not_a_kb_provider():
    obj = _OnlyMembership()
    assert isinstance(obj, MembershipOracle)
    assert not isinstance(obj, KBProvider)
    # ...and it is not a composite that demands more than membership.
    assert not isinstance(obj, GeneratorOracle)


def test_kb_only_object_is_not_a_membership_oracle():
    obj = _OnlyKB()
    assert isinstance(obj, KBProvider)
    assert not isinstance(obj, MembershipOracle)


def test_kb_provider_and_bg_provider_are_distinct_roles():
    """The A6-affected KB surface is its own role, not merged into BGProvider."""
    # An object with only BG methods is not a KBProvider (and vice versa).
    class _OnlyBG:
        def get_bg_data(self):
            return None

        def get_root_clauses(self):
            return []

    assert isinstance(_OnlyBG(), BGProvider)
    assert not isinstance(_OnlyBG(), KBProvider)
    assert not isinstance(_OnlyKB(), BGProvider)


# --- ADR-0010: the oracles we own declare their roles by inheritance ---
@pytest.mark.parametrize(
    "cls,roles",
    [
        (FMOracle, (MembershipOracle, CompletableOracle, CatalogProvider)),
        (CachedOracle, (MembershipOracle,)),
        (UserPromptOracle, (MembershipOracle,)),
    ],
    ids=["FMOracle", "CachedOracle", "UserPromptOracle"],
)
def test_our_oracles_declare_their_roles_by_inheritance(cls, roles):
    """Second-class guard (primary is the enforcement test above): the oracles we
    own DECLARE their ADR-0009 roles by inheriting the protocols, so the role split
    is machine-checked at every implementation site, not prose in a docstring.
    Nominal (MRO) check, not structural isinstance — a class that merely has the
    methods passes isinstance yet must fail here; that is what catches 'forgot to
    inherit'. Third-party oracles and test doubles need not declare — that is what
    structural substitutability is for (ADR-0010)."""
    for role in roles:
        assert role in cls.__mro__, f"{cls.__name__} must declare {role.__name__}"

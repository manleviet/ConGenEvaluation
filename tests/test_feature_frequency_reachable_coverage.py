"""FF coverage must be measured against what a feature model can actually attain.

``main-r1.tex`` l. 622 defines feature frequency as "each feature is at least once
included and excluded in an example" — polarity-agnostic. The implementation asked
for something strictly stronger and unattainable: every feature True *and* False
within the positive set alone. A mandatory feature is True in every valid
configuration, starting with the root, so that condition is false on every real
feature model. The positive loop consequently never stopped on coverage and burned
its entire attempt budget on all six knowledge bases (1,400 attempts for REAL-FM-7,
85,400 for busybox), while ``fully_covered`` reported False forever.

These tests pin the fix: the attainable (feature, value) set is computed up front
and the loop stops once it is met.
"""
import pytest

from conacq.example_generators import FeatureFrequencyGenerator

# REAL-FM-7 has 14 features. `interface` and `jplug` are mandatory, so they can
# never be False in a valid configuration -- and they are exactly the two entries
# the pre-fix generator reported as permanently uncovered after 1,400 attempts.
_EXPECTED_UNREACHABLE = {("interface", False), ("jplug", False)}


@pytest.fixture
def generator(oracle):
    return FeatureFrequencyGenerator(oracle)


def test_reachable_pairs_exclude_exactly_the_mandatory_features(oracle, generator):
    """The attainable set drops (f, False) for mandatory features and nothing else."""
    features = sorted(oracle.get_variables())
    reachable = generator._reachable_positive_pairs(features)
    everything = {(f, value) for f in features for value in (True, False)}

    assert everything - reachable == _EXPECTED_UNREACHABLE
    assert len(reachable) == 2 * len(features) - len(_EXPECTED_UNREACHABLE)


def test_every_unreachable_pair_really_is_unreachable(oracle, generator):
    """Each excluded pair must be contradicted by the oracle, not merely assumed.

    A feature excluded at False must come back True from every completion that
    asks for False; otherwise the exclusion is wrong and FF would stop early on
    coverage it never achieved.
    """
    features = sorted(oracle.get_variables())
    reachable = generator._reachable_positive_pairs(features)

    for f, value in {(f, v) for f in features for v in (True, False)} - reachable:
        config = oracle.complete_configuration({f: value})
        assert config is None or config[f] is not value, (
            f"({f}, {value}) was excluded but the oracle can produce it"
        )


def test_reachability_check_is_not_fooled_by_the_completion_fallback(oracle, generator):
    """Guards the reason this cannot be written as ``complete_configuration(...) is not None``.

    ``FMOracle.complete_configuration`` (oracle.py:149-151) does not report
    unsatisfiability for an unsatisfiable partial — it falls back to returning
    *any* valid configuration. A None-check would therefore mark every pair
    reachable, the attainable set would be all 2n pairs, and the stopping
    condition would be exactly as unreachable as before while the diff looked
    correct. Red if that fallback is ever removed, which is the point: the check
    in _reachable_positive_pairs could then be simplified.
    """
    features = sorted(oracle.get_variables())
    reachable = generator._reachable_positive_pairs(features)
    unreachable = {(f, v) for f in features for v in (True, False)} - reachable
    assert unreachable, "fixture model has no mandatory feature; pick another model"

    # sorted, not the set: iterating a set of strings here would make this
    # assertion depend on PYTHONHASHSEED — the very defect under test.
    fooled = [(f, value) for f, value in sorted(unreachable)
              if oracle.complete_configuration({f: value}) is not None]
    assert fooled == sorted(unreachable), (
        "expected the documented fallback to return a config for every "
        f"unsatisfiable partial; got {fooled}"
    )


def test_positive_loop_stops_on_attainable_coverage(generator):
    """FF must finish because it is done, not because it ran out of attempts."""
    max_examples = 140
    examples = generator.generate(max_examples=max_examples, seed=82)
    md = examples.metadata

    assert md["fully_covered"] is True
    assert md["coverage"]["percentage"] == 100.0
    assert md["coverage"]["uncovered_features"] == []
    # The budget is max_examples * 10; finishing on coverage means using a tiny
    # fraction of it. Pre-fix this was exactly 1,400.
    assert md["pos_attempts"] < max_examples, (
        f"positive loop used {md['pos_attempts']} attempts — it is still not "
        f"stopping on coverage"
    )
    assert md["reachable_positive_pairs"] < md["total_pairs"]

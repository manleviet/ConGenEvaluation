"""Characterization tests pinning example-generator RNG behavior.

The example generators must draw randomness from a *per-instance* RNG rather
than the process-global ``random`` stream. Two properties follow, and both are
required for any downstream end-to-end replay (fixed seed -> pinned learned KB
+ diagnoses) to be trustworthy:

1. **Reproducible** — the same generator, run twice with the same seed, yields
   byte-identical examples, even if unrelated code consumes the global RNG in
   between. A shared global RNG makes this fragile to call ordering.
2. **Isolated** — running a generator must NOT consume from or reset the
   process-global RNG stream. A generator that reseeds/draws on the global RNG
   silently perturbs every other component that shares it.

The isolation tests are deliberately *falsifiable*: against a generator that
touches the global RNG they go red (proving the test can detect the defect);
against a per-instance RNG they pass. Without that property they would prove
nothing.

Uses the shared REAL-FM-7 ``oracle`` fixture (tests/conftest.py). The oracle /
SAT path is itself free of global ``random`` usage, so the seeded example
sequence is preserved — these tests lock the RNG discipline, not new numbers.
"""
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from conacq.example_generators import (
    RandomSamplingGenerator,
    ControlledRandomSamplingGenerator,
    FeatureFrequencyGenerator,
    QueryProvider,
)
from tests.resource_paths import FM_PATH

# Fixed seed for probing the GLOBAL stream — unrelated to generator seeds.
_PROBE_SEED = 20260712
_SEED = 42


def _ex_key(example):
    """Order-stable, hashable fingerprint of one Example."""
    return (
        example.id,
        tuple(sorted(example.assignments.items())),
        example.example_type.value,
    )


def _fingerprint(example_set):
    """Canonical representation capturing the exact generated sequence."""
    return (
        tuple(_ex_key(e) for e in example_set.positive),
        tuple(_ex_key(e) for e in example_set.negative),
    )


# Each factory runs one generator with a small, fast workload. Kept tiny so the
# SAT-backed generators (Controlled, FF) stay quick on the real feature model.
def _make_rs(oracle, seed=_SEED):
    return RandomSamplingGenerator(oracle).generate(n=8, seed=seed)


def _make_controlled(oracle, seed=_SEED):
    return ControlledRandomSamplingGenerator(oracle).generate(total=12, seed=seed)


def _make_ff(oracle, seed=_SEED):
    return FeatureFrequencyGenerator(oracle).generate(max_examples=12, seed=seed)


GENERATORS = [
    pytest.param(_make_rs, id="random_sampling"),
    pytest.param(_make_controlled, id="controlled_random_sampling"),
    pytest.param(_make_ff, id="feature_frequency"),
]


# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------
@pytest.mark.parametrize("make", GENERATORS)
def test_same_seed_same_output(oracle, make):
    """Two fresh generators with the same seed produce identical examples."""
    assert _fingerprint(make(oracle)) == _fingerprint(make(oracle))


@pytest.mark.parametrize("make", GENERATORS)
def test_reproducible_despite_global_interleave(oracle, make):
    """Global RNG activity between runs must not change seeded output.

    Passes on either RNG design, so it stays green after the refactor and
    permanently locks reproducibility against future regressions.
    """
    first = _fingerprint(make(oracle))
    random.random()
    random.seed(999)  # actively corrupt the global stream
    random.random()
    second = _fingerprint(make(oracle))
    assert first == second


# --------------------------------------------------------------------------
# Isolation from the global RNG stream (falsifiable)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("make", GENERATORS)
def test_generator_does_not_disturb_global_rng_stream(oracle, make):
    """A generator run must be transparent to the process-global RNG.

    Reference: six consecutive global draws. Actual: the same six draws with a
    generator run injected after the third. If the generator draws from or
    reseeds the global RNG, the last three draws diverge from the reference.
    """
    random.seed(_PROBE_SEED)
    reference = [random.random() for _ in range(6)]

    random.seed(_PROBE_SEED)
    observed = [random.random() for _ in range(3)]
    make(oracle)
    observed += [random.random() for _ in range(3)]

    assert observed == reference


@pytest.mark.parametrize("make", GENERATORS)
def test_seed_none_generator_does_not_skew_seeded_generator(oracle, make):
    """An unseeded generator must not perturb a seeded one's reproducibility."""
    reference = _fingerprint(make(oracle, seed=_SEED))
    make(oracle, seed=None)  # non-deterministic content; must stay self-contained
    assert _fingerprint(make(oracle, seed=_SEED)) == reference


# --------------------------------------------------------------------------
# QueryProvider pool shuffle (own class, same discipline)
# --------------------------------------------------------------------------
def _pool():
    return [
        {"a": True, "b": False},
        {"a": False, "b": True},
        {"a": True, "b": True},
        {"a": False, "b": False},
    ]


def test_query_provider_pool_shuffle_reproducible():
    """Same seed -> same shuffled pool order."""
    assert QueryProvider(pool=_pool(), seed=_SEED)._pool == \
        QueryProvider(pool=_pool(), seed=_SEED)._pool


def test_query_provider_seed_none_does_not_disturb_global_rng_stream():
    """Unseeded pool shuffle must not consume the global RNG stream.

    Targets the seed=None branch (the seeded branch is already isolated). Red
    while that branch calls ``random.shuffle`` on the global RNG; green once it
    shuffles via a per-call ``random.Random`` instance.
    """
    random.seed(_PROBE_SEED)
    reference = [random.random() for _ in range(6)]

    random.seed(_PROBE_SEED)
    observed = [random.random() for _ in range(3)]
    QueryProvider(pool=_pool(), seed=None)  # constructor shuffles the pool
    observed += [random.random() for _ in range(3)]

    assert observed == reference


# --------------------------------------------------------------------------
# Reproducibility ACROSS processes (falsifiable)
# --------------------------------------------------------------------------
# ``test_same_seed_same_output`` above runs both generators inside one process,
# where PYTHONHASHSEED is fixed for the process lifetime. That makes it blind to
# a generator whose output depends on the iteration order of a set of strings:
# both runs see the same order, so both agree, and the test passes while the
# property in this module's docstring — same seed, byte-identical examples — is
# false for anyone who runs the generator twice in separate processes.
#
# These tests cross that boundary. Two child processes, two different
# PYTHONHASHSEED values, same generator seed; the fingerprints must match.
_HASH_SEEDS = ("0", "12345")

_CHILD = r'''
import hashlib, json, sys
from conacq.oracle import FMOracle
from conacq.example_generators import (
    RandomSamplingGenerator, ControlledRandomSamplingGenerator, FeatureFrequencyGenerator)

fm_path, seed = sys.argv[1], int(sys.argv[2])
oracle = FMOracle(fm_path)

def fingerprint(example_set):
    # assignments are sorted so this pins the SEQUENCE of examples, not the key
    # order of any one dict -- the defect changes which examples are drawn.
    rows = [[[e.id, sorted(e.assignments.items()), e.example_type.value] for e in bucket]
            for bucket in (example_set.positive, example_set.negative)]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

print("random_sampling", fingerprint(
    RandomSamplingGenerator(oracle).generate(n=8, seed=seed)))
print("controlled_random_sampling", fingerprint(
    ControlledRandomSamplingGenerator(oracle).generate(total=12, seed=seed)))
print("feature_frequency", fingerprint(
    FeatureFrequencyGenerator(oracle).generate(max_examples=12, seed=seed)))
'''


def _fingerprints_under(hash_seed):
    """Generator fingerprints from a child process with PYTHONHASHSEED=*hash_seed*."""
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH=str(repo_root))
    proc = subprocess.run([sys.executable, "-c", _CHILD, str(FM_PATH), str(_SEED)],
                          cwd=repo_root, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"child failed:\n{proc.stderr[-2000:]}"
    return dict(line.split() for line in proc.stdout.split("\n") if line.strip())


@pytest.fixture(scope="module")
def cross_process_fingerprints():
    """One child run per PYTHONHASHSEED, shared by the tests below."""
    if not FM_PATH.exists():
        pytest.skip(f"Feature model not found: {FM_PATH}")
    return {h: _fingerprints_under(h) for h in _HASH_SEEDS}


@pytest.mark.parametrize(
    "generator_id",
    ["random_sampling", "controlled_random_sampling", "feature_frequency"])
def test_same_seed_same_output_across_processes(cross_process_fingerprints, generator_id):
    """A seeded generator must not depend on string-hash iteration order.

    Red against a generator that iterates a ``set`` of feature names to decide
    what to generate next (proving the test detects the defect); green once that
    iteration is ordered.
    """
    first, second = (cross_process_fingerprints[h][generator_id] for h in _HASH_SEEDS)
    assert first == second, (
        f"{generator_id} produced different examples under "
        f"PYTHONHASHSEED={_HASH_SEEDS[0]} vs {_HASH_SEEDS[1]} "
        f"({first[:16]} vs {second[:16]}) — seed {_SEED} does not pin its output"
    )

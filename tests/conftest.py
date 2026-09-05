"""Shared pytest fixtures.

Centralizes the REAL-FM-7 ``bias`` / ``oracle`` fixtures previously copied
across test_congen and test_quacq. Resource PATHS live in
``tests/resource_paths.py``; the ``slow`` marker is registered in
``pyproject.toml`` under ``[tool.pytest.ini_options]``.

Existing test modules keep their local fixtures for now and migrate onto
these shared ones incrementally as each subsystem is refactored.
"""
import pytest

from conacq.bias import BiasIO
from conacq.oracle import FMOracle
from tests.resource_paths import FM_PATH, BIAS_PATH


@pytest.fixture
def bias():
    """REAL-FM-7 bias (shared)."""
    if not BIAS_PATH.exists():
        pytest.skip(f"Bias file not found: {BIAS_PATH}")
    return BiasIO.load_from_json(str(BIAS_PATH))


@pytest.fixture
def oracle():
    """REAL-FM-7 feature-model oracle (shared)."""
    if not FM_PATH.exists():
        pytest.skip(f"Feature model not found: {FM_PATH}")
    return FMOracle(str(FM_PATH))

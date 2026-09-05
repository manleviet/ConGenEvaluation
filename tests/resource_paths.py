"""Single source of truth for test resource paths.

Replaces the per-file ``DATA_DIR`` / ``FM_PATH`` / ``BIAS_PATH`` / ... blocks
duplicated across test_congen, test_evaluation and others. Named
``resource_paths`` (not ``resources``) to avoid colliding with the
``tests/resources/`` data directory.

Tests migrate onto these constants incrementally as each subsystem is
refactored; this module only establishes the shared source.
"""
from pathlib import Path

# Repo-root data/ — real feature models, bias, examples, results.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

FM_PATH = DATA_DIR / "fms" / "REAL-FM-7.uvl"
BIAS_PATH = DATA_DIR / "bias" / "REAL-FM-7-bias.json"
EXAMPLES_RS_1N_PATH = DATA_DIR / "examples" / "REAL-FM-7_rs_1n.json"
EXAMPLES_FF_PATH = DATA_DIR / "examples" / "REAL-FM-7_ff.json"
RESULT_PATH = DATA_DIR / "results" / "old_results" / "REAL-FM-7_rs_1n_non-incremental_fold1_kb.json"

# Cross-model regression set (name, fm_path, bias_path) for oracle-id tests.
MODELS = [
    ("REAL-FM-7", str(DATA_DIR / "fms" / "REAL-FM-7.uvl"), str(DATA_DIR / "bias" / "REAL-FM-7-bias.json")),
    ("arcade-game", str(DATA_DIR / "fms" / "arcade-game.uvl"), str(DATA_DIR / "bias" / "arcade-game-bias.json")),
    ("REAL-FM-4", str(DATA_DIR / "fms" / "REAL-FM-4.uvl"), str(DATA_DIR / "bias" / "REAL-FM-4-bias.json")),
]

# tests/resources/ — diagnosis fixtures (.fide, .cnf, .uvl, .testcases).
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
FM_INCONSISTENT = RESOURCES_DIR / "smartwatch_inconsistent.fide"
# Real product-line FM as DIMACS CNF (~6.5k clauses) — a large KB for
# exercising FastDiagP's deep recursion / speculative lookahead.
CNF_PROD = RESOURCES_DIR / "prod_1_1.cnf"

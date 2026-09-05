"""Fold-level granularity and resume for cross-validation.

The sweep runs in windows shorter than some of its units, so a fold that is still
running when a window closes has to be redone from zero. These tests hold the line
that makes windowed execution safe: a fold computed on its own, in its own process,
in any order, must produce exactly what the same fold produces inside a monolithic
run — otherwise the split silently changes the paper's numbers.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conacq.eval.cv_partials import (
    PARTIAL_SCHEMA, fold_result_from_dict, load_partials, partial_filename,
)
from tests.resource_paths import REPO_ROOT

# Toggle individual tests during development (repo convention).
ENABLED_TESTS = {
    'split_matches_monolithic': True,
    'partial_roundtrip': True,
    'unseeded_pool_refused': True,
    'stale_partial_refused': True,
    'congen_schema_unchanged': True,
    'query_mode_partials_distinct': True,
    'incomplete_window_writes_nothing': True,
    'committed_results_guarded': True,
    'guard_is_wired': True,
}

CONFIG = """
[general]
seed = 42
output_dir = "MUST_PASS_-o"
verbose = false

[evaluation]
algorithm = "{algorithm}"
n_folds = 3
solver_name = "glucose4"
solver_mode = "incremental"
shuffle_bias = {shuffle_bias}

[evaluation.interactive]
max_queries = 200
query_mode = "example_first"

[[models]]
name = "REAL-FM-7_rs_1n"
oracle = "data/fms/REAL-FM-7.uvl"
bias = "data/bias/REAL-FM-7-bias.json"
examples = "data/examples/REAL-FM-7_rs_1n.json"
folds_path = "data/folds/REAL-FM-7_rs_1n_folds.json"
"""

# Wall-clock and tracemalloc peak are not reproducible and are not meant to be:
# two identical monolithic runs already differ on exactly these, and a fold that
# runs in its own process has a different allocation history by construction.
# Everything outside this set must match.
NOISE = ('runtime', '_time', 'time_', 'memory', '_mb')


def _write_config(tmp_path: Path, algorithm: str, shuffle_bias: str = "true") -> Path:
    path = tmp_path / f"cv_{algorithm}.toml"
    path.write_text(CONFIG.format(algorithm=algorithm, shuffle_bias=shuffle_bias))
    return path


def _run_cv(config: Path, out_dir: Path, *extra) -> subprocess.CompletedProcess:
    """Invoke run_cv as a subprocess: a separate process per fold is the condition
    the sweep actually runs under, and importing the module would not test it."""
    return subprocess.run(
        [sys.executable, '-m', 'apps.run_cv', str(config), '-o', str(out_dir), *extra],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def _semantic_diffs(a, b, path=""):
    """Differences outside the timing/memory noise set."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k} present in only one")
            else:
                out += _semantic_diffs(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path} length {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += _semantic_diffs(x, y, f"{path}[{i}]")
    elif a != b and not any(n in path.lower() for n in NOISE):
        out.append(f"{path}: {a!r} != {b!r}")
    return out


@pytest.mark.skipif(not ENABLED_TESTS['split_matches_monolithic'], reason="disabled")
@pytest.mark.slow
def test_per_fold_runs_merge_to_the_monolithic_result(tmp_path):
    """Three single-fold processes, run out of order, merge to what one run produces.

    This is the gate the windowed sweep rests on. It runs the folds in the order
    2, 0, 1 so that a runner carrying state from one fold into the next would move
    the result and fail here.
    """
    config = _write_config(tmp_path, 'congen')

    mono_dir = tmp_path / 'mono'
    assert _run_cv(config, mono_dir).returncode == 0

    split_dir = tmp_path / 'split'
    for fold in (2, 0, 1):
        proc = _run_cv(config, split_dir, '--folds', str(fold))
        assert proc.returncode == 0, proc.stderr

    name = 'REAL-FM-7_rs_1n_cv_incremental.json'
    mono = json.loads((mono_dir / 'congen' / name).read_text())
    split = json.loads((split_dir / 'congen' / name).read_text())

    diffs = _semantic_diffs(mono, split)
    assert not diffs, "per-fold merge diverged from the monolithic run:\n" + "\n".join(diffs[:20])


@pytest.mark.skipif(not ENABLED_TESTS['incomplete_window_writes_nothing'], reason="disabled")
@pytest.mark.slow
def test_a_window_that_ends_early_writes_no_cv_result(tmp_path):
    """A run that finishes only some folds leaves the partials and nothing else.

    The hazard this closes has no symptom: assembling from the folds that happen to
    be present would emit a CV JSON with the ordinary name and shape, whose
    accuracy mean, std and intersected KB were computed over a subset. Nothing
    downstream distinguishes it from a complete run, so the check has to be that
    the file is absent, not that its contents look right.
    """
    config = _write_config(tmp_path, 'congen')
    out = tmp_path / 'out'

    proc = _run_cv(config, out, '--folds', '0')
    assert proc.returncode == 0, proc.stderr

    cv_file = out / 'congen' / 'REAL-FM-7_rs_1n_cv_incremental.json'
    assert not cv_file.exists(), "assembled a CV result from 1 of 3 folds"
    partials = sorted((out / 'congen' / 'partials').glob('*.json'))
    assert len(partials) == 1, f"expected exactly fold 0 durable, got {partials}"

    # ...and once the remaining folds land, the result appears.
    assert _run_cv(config, out, '--folds', '1,2').returncode == 0
    assert cv_file.exists()
    assert json.loads(cv_file.read_text())['n_folds'] == 3


@pytest.mark.skipif(not ENABLED_TESTS['partial_roundtrip'], reason="disabled")
@pytest.mark.slow
def test_partial_roundtrip_preserves_the_fold(tmp_path):
    """A partial read back off disk re-serializes to the same fold dict.

    Guards the reconstruction in ``fold_result_from_dict``: a field dropped there
    would vanish from every merged result while the file on disk still looked
    complete.
    """
    config = _write_config(tmp_path, 'congen')
    out = tmp_path / 'out'
    assert _run_cv(config, out, '--folds', '0').returncode == 0

    partial_path = (out / 'congen' / 'partials' /
                    partial_filename('REAL-FM-7_rs_1n', 'incremental', 0))
    payload = json.loads(partial_path.read_text())

    assert payload['schema'] == PARTIAL_SCHEMA
    assert payload['fold_index'] == 0
    restored = fold_result_from_dict(payload['fold'], 'congen')
    assert restored.to_dict() == payload['fold']


@pytest.mark.skipif(not ENABLED_TESTS['unseeded_pool_refused'], reason="disabled")
def test_interactive_refuses_an_unseeded_query_pool(tmp_path):
    """shuffle_bias=false leaves the query pool seeded from OS entropy.

    ``query_provider.py`` takes the per-fold seed straight into
    ``random.Random(seed)``; a None there means the pool order, and so the learned
    KB, differs between runs with nothing reporting it. Until ADR-0015 decouples
    the seed from this knob, the run must be refused rather than produced.
    """
    config = _write_config(tmp_path, 'interactive', shuffle_bias="false")
    proc = _run_cv(config, tmp_path / 'out')
    assert proc.returncode != 0
    assert 'shuffle_bias' in (proc.stderr + proc.stdout)

    from conacq.eval import n_fold_cross_validation_interactive
    with pytest.raises(ValueError, match="shuffle_bias"):
        n_fold_cross_validation_interactive(
            positive_examples=[{'a': True}], negative_examples=[{'a': False}],
            n_folds=2, fm_path='unused.uvl', bias_path='unused.json', seed=1,
            shuffle_bias=False)


@pytest.mark.skipif(not ENABLED_TESTS['stale_partial_refused'], reason="disabled")
def test_partials_from_another_shape_are_refused(tmp_path):
    """A partial from a different schema, algorithm or fold count is refused.

    Merging one silently would yield a well-formed CV JSON built from the wrong
    computation — the failure mode with no symptom.
    """
    partial_dir = tmp_path / 'partials'
    partial_dir.mkdir()
    good = {'schema': PARTIAL_SCHEMA, 'model': 'm', 'algorithm': 'congen',
            'solver_mode': 'incremental', 'query_mode': None, 'n_folds': 3,
            'fold_index': 0, 'commit': None, 'fold': {}}

    for bad_key, bad_value in (('schema', 'acqmss.cv.partial/0'),
                               ('algorithm', 'interactive'),
                               ('n_folds', 5)):
        payload = dict(good)
        payload[bad_key] = bad_value
        (partial_dir / partial_filename('m', 'incremental', 0)).write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            load_partials(partial_dir, 'm', 'incremental', 'congen', 3)


@pytest.mark.skipif(not ENABLED_TESTS['congen_schema_unchanged'], reason="disabled")
@pytest.mark.slow
def test_query_budget_fields_stay_off_the_passive_schema(tmp_path):
    """``n_queries`` / ``convergence_reason`` reach interactive folds and only those.

    Tables 13/14 need the budget columns, but the ConGen fold dict is compared
    against recorded results that cannot be regenerated, so the two keys are
    omitted rather than serialized as null on the passive algorithms.
    """
    congen_out = tmp_path / 'c'
    assert _run_cv(_write_config(tmp_path, 'congen'), congen_out).returncode == 0
    congen = json.loads((congen_out / 'congen' /
                         'REAL-FM-7_rs_1n_cv_incremental.json').read_text())
    for fold in congen['folds']:
        assert 'n_queries' not in fold
        assert 'convergence_reason' not in fold

    inter_out = tmp_path / 'i'
    assert _run_cv(_write_config(tmp_path, 'interactive'), inter_out).returncode == 0
    inter = json.loads((inter_out / 'interactive' /
                        'REAL-FM-7_rs_1n_cv_incremental_example_first.json').read_text())
    for fold in inter['folds']:
        assert isinstance(fold['n_queries'], int)
        assert fold['convergence_reason']


@pytest.mark.skipif(not ENABLED_TESTS['committed_results_guarded'], reason="disabled")
def test_committed_results_tree_is_not_written_by_accident(tmp_path, monkeypatch):
    """Writing into data/results/ requires saying so.

    The config default sends output there, so a run that merely omits -o overwrites
    the committed results with nothing failing and nothing looking wrong. The guard
    is on the resolved destination, not on whether -o was spelled out, so naming
    the directory explicitly is caught the same way; only the environment variable
    distinguishes a deliberate regeneration from an accident.
    """
    from apps.run_cv import guard_committed_output, ALLOW_DEFAULT_OUTPUT_ENV

    monkeypatch.delenv(ALLOW_DEFAULT_OUTPUT_ENV, raising=False)
    for spelling in (REPO_ROOT / 'data' / 'results', Path('data/results')):
        with pytest.raises(SystemExit) as exc:
            guard_committed_output(spelling)
        assert exc.value.code != 0

    monkeypatch.setenv(ALLOW_DEFAULT_OUTPUT_ENV, '1')
    guard_committed_output(REPO_ROOT / 'data' / 'results')

    # Inert everywhere else, including the sweep's own output root.
    monkeypatch.delenv(ALLOW_DEFAULT_OUTPUT_ENV, raising=False)
    guard_committed_output(tmp_path)
    guard_committed_output(REPO_ROOT / 'data' / 'results_sosym')


@pytest.mark.skipif(not ENABLED_TESTS['guard_is_wired'], reason="disabled")
def test_the_guard_is_wired_into_the_run_path(tmp_path, monkeypatch):
    """The guard runs on every invocation, not only when -o is omitted.

    Testing guard_committed_output() on its own cannot see the call site. A guard
    reached only when -o is absent would pass that test and still let
    `-o data/results` through, which is the same destination by another spelling.
    The protected directory is redirected to tmp_path so a regression fails the
    test instead of overwriting the real results.
    """
    import apps.run_cv as run_cv
    from apps.run_cv import ALLOW_DEFAULT_OUTPUT_ENV

    protected = tmp_path / 'protected'
    monkeypatch.setattr(run_cv, 'COMMITTED_RESULTS_DIR', protected)
    monkeypatch.delenv(ALLOW_DEFAULT_OUTPUT_ENV, raising=False)
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(
        sys, 'argv',
        ['run_cv', str(_write_config(tmp_path, 'congen')), '-o', str(protected)])

    with pytest.raises(SystemExit) as exc:
        run_cv.main()
    assert exc.value.code == 2
    assert not protected.exists(), "the run created the protected tree despite the guard"


@pytest.mark.skipif(not ENABLED_TESTS['query_mode_partials_distinct'], reason="disabled")
def test_query_modes_get_separate_partials():
    """example_only and example_first are separate conditions sharing an output
    directory; colliding partial names would let one resume from the other's folds."""
    first = partial_filename('m', 'incremental', 0, 'example_first')
    only = partial_filename('m', 'incremental', 0, 'example_only')
    passive = partial_filename('m', 'incremental', 0)
    assert first != only != passive
    assert passive == 'm_incremental_fold0.json'

"""ConGen's negative-example encoding switch (``neg_mode`` = reduced | raw).

GenerateNE reduces each e⁻ to a subset-minimal conflict with QuickXplain against the
oracle by default. ``raw`` negates the full assignment instead and never consults the
oracle. The switch is what lets the claim "ConGen needs no oracle" be measured rather
than asserted, so these tests hold three things:

- the default is the published path, untouched (same prepared task as before the
  switch existed);
- raw really is raw: every ¬e⁻ covers the whole e⁻ and no preprocessing QuickXplain
  runs, while the assumption-ID layout is the same as under reduced;
- a raw theory still rejects every training e⁻ (KB ∪ BG ⊨ ¬e⁻, Definition 6), and a
  resumed run cannot merge partials computed under the other encoding.
"""

import json

import pytest

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
from conacq.eval.accuracy import AccuracyCalculator
from conacq.eval.cv_partials import PARTIAL_SCHEMA, load_partials, partial_filename
from conacq.examples import ExampleIO
from conacq.oracle import FMOracle
from conacq.runners import ConGenRunner
from tests.resource_paths import BIAS_PATH, DATA_DIR, FM_PATH

# Four negatives (rs_1n has one): enough for the per-e⁻ split to be exercised.
EXAMPLES_PATH = DATA_DIR / 'examples' / 'REAL-FM-7_rs_3n.json'

# Toggle individual tests during development (repo convention).
ENABLED_TESTS = {
    'default_is_reduced': True,
    'raw_negates_full_assignment': True,
    'raw_theory_rejects_training_negatives': True,
    'bad_neg_mode_refused': True,
    'partials_keyed_by_neg_mode': True,
}


def _examples():
    examples = ExampleIO.load_json(str(EXAMPLES_PATH))
    return ([e.assignments for e in examples.positive],
            [e.assignments for e in examples.negative])


@pytest.fixture
def model_and_input():
    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data).build())
    pos, neg = _examples()
    try:
        yield model, ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg), neg
    finally:
        oracle.cleanup()


@pytest.mark.skipif(not ENABLED_TESTS['default_is_reduced'], reason="disabled")
def test_default_prepare_is_the_reduced_encoding(model_and_input):
    """No argument and ``minimize=True`` build the same task: the published path."""
    model, task_input, _ = model_and_input
    default = model.prepare_task(task_input).task
    reduced = model.prepare_task(task_input, minimize=True).task
    assert default == reduced


@pytest.mark.skipif(not ENABLED_TESTS['raw_negates_full_assignment'], reason="disabled")
def test_raw_negates_the_full_assignment_without_the_oracle(model_and_input):
    from profiling import ProfilerPreset, profiler_session
    model, task_input, neg = model_and_input
    reduced = model.prepare_task(task_input, minimize=True).task
    with profiler_session(ProfilerPreset.BENCHMARK) as prof:
        raw = model.prepare_task(task_input, minimize=False, profiler=prof).task
        # No oracle QuickXplain ran, so its counter was never created.
        assert prof.get_metric('shared_preprocessing_quickxplain_checks', 0) == 0

    # Same assumption-ID layout: only the ¬e⁻ clause content differs.
    assert raw.set_c == reduced.set_c and raw.set_tc == reduced.set_tc
    assert raw.set_neg_tv == reduced.set_neg_tv
    assert raw.negation_map == reduced.negation_map

    # Each raw ¬e⁻ is a blocking clause over the WHOLE e⁻ (+ its guard literal);
    # the reduced one is strictly shorter for at least one e⁻, or the switch is inert.
    # A ¬e⁻ clause is the one ending in its own guard literal -ne_id.
    def ne_clauses(task):
        guards = {-ne for ne in task.set_neg_tv}
        return [c for c in task.set_kb if len(c) > 1 and c[-1] in guards]

    width = {len(e) for e in neg}
    assert len(neg) > 1 and len(width) == 1, "fixture: several complete negatives"
    full = width.pop() + 1
    raw_ne, red_ne = ne_clauses(raw), ne_clauses(reduced)
    assert len(raw_ne) == len(red_ne) == len(neg)
    assert all(len(c) == full for c in raw_ne)
    assert any(len(c) < full for c in red_ne)


@pytest.mark.skipif(not ENABLED_TESTS['raw_theory_rejects_training_negatives'],
                    reason="disabled")
def test_raw_theory_rejects_every_training_negative():
    """Delivered theory B' ∪ NE ∪ root rejects each e⁻ it was trained on. Reduce only
    removes what the rest entails, so this holds whatever it discards."""
    pos, neg = _examples()
    runner = ConGenRunner(str(BIAS_PATH), str(FM_PATH), neg_mode='raw')
    try:
        result = runner.run(pos, neg, shuffle_seed=7)
        theory = (list(result.kb_clauses) + [list(c) for c in result.ne_clauses]
                  + list(result.bg_clauses))
        with AccuracyCalculator(theory, runner.feature_ids) as calc:
            m = calc.calculate([], neg).metrics
    finally:
        runner.cleanup()
    assert m.true_negatives == len(neg) and m.false_positives == 0


@pytest.mark.skipif(not ENABLED_TESTS['bad_neg_mode_refused'], reason="disabled")
def test_unknown_neg_mode_is_refused():
    with pytest.raises(ValueError):
        ConGenRunner(str(BIAS_PATH), str(FM_PATH), neg_mode='minimal')


@pytest.mark.skipif(not ENABLED_TESTS['partials_keyed_by_neg_mode'], reason="disabled")
def test_partials_from_the_other_encoding_are_refused(tmp_path):
    """The partial filename carries no mode, so the payload must: a raw run resuming
    over reduced partials would otherwise merge them as its own folds."""
    base = {'schema': PARTIAL_SCHEMA, 'model': 'm', 'algorithm': 'congen',
            'solver_mode': 'incremental', 'query_mode': None, 'n_folds': 3,
            'fold_index': 0, 'commit': None, 'fold': {}}
    path = tmp_path / partial_filename('m', 'incremental', 0)

    path.write_text(json.dumps({**base, 'neg_mode': 'raw'}))
    with pytest.raises(ValueError, match='neg_mode'):
        load_partials(tmp_path, 'm', 'incremental', 'congen', 3, neg_mode='reduced')

    # A partial from before the switch was computed under the only encoding there was.
    path.write_text(json.dumps(base))
    with pytest.raises(ValueError, match='neg_mode'):
        load_partials(tmp_path, 'm', 'incremental', 'congen', 3, neg_mode='raw')

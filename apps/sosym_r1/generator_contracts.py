#!/usr/bin/env python3
"""Contracts of the example-generation pipeline: four the paper states, two it no longer does.

S6.1.3 (new in the submitted revision) describes the sampling protocol in four claims,
and each is asserted here with its section reference:

  (a) under random sampling, nine tenths positive and one tenth negative -- exactly
      n_neg = max(1, total // 10), which is "one tenth" up to that rounding;
  (b) a negative example is a random complete assignment the model rejects, and a
      positive one a valid configuration obtained by letting the oracle complete a
      random partial assignment; FF builds both kinds the same way;
  (c) the 2-wise sample is computed over the feature domains without regard to the
      model's constraints, so on these models it holds 0, 0, 1, 1, 0 positives;
  (d) FF's coverage target for POSITIVE examples is restricted to the attainable
      (feature, value) pairs, while its target for negatives is all of them.

Two more hold properties the paper stopped stating at the 2026-09-23 minimal-change
review, and carry NO section reference for that reason:

  * the feature-frequency sampler's safety bound, 10n examples;
  * one solver per negative example in GenerateNE's preprocessing.

They are the contracts the committed example sets and preprocessing costs were produced
under, so a later change to either would move data the paper does print, silently.

EVERY PROCESS CLAIM IS ASSERTED BEHAVIOURALLY. "Completed by the oracle" and "without
regard to the constraints" are claims about how an example came to exist, which no
example file records. They are checked by regenerating committed sets from their
recorded seed with a spy on the oracle -- the regenerated set must equal the committed
one, so the spy watched the run that produced the paper's data, not a lookalike -- and by
counting which oracle calls each generator makes. A source-shape assertion would pass a
refactor that keeps the text and changes the behaviour.

One nuance is recorded rather than smoothed over: FF's positives complete a partial
assignment that fixes the uncovered target pair plus at most five random features, and
its negatives are random complete assignments with up to five features steered toward
uncovered pairs. That is "the same way" in kind -- oracle completion of a random partial;
random complete assignment, kept if rejected -- but not the same distribution as RS.
"""
from __future__ import annotations

from pathlib import Path

EXAMPLES = Path('data') / 'examples'
# A model with several negative examples, so "one per negative" is distinguishable from
# "one in total" and from "one per fold".
CONTRACT_MODEL, CONTRACT_SAMPLING = 'REAL-FM-7', '2cov'


def ff_target_size(n_features: int) -> int:
    """What the FF sampler is asked to generate for a model of ``n_features``."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from apps.generate_examples import STRATEGY_COUNTS
    return STRATEGY_COUNTS['ff'](n_features, None)


def checkers_built_by_generate_ne(repo: Path, stem: str, sampling: str) -> tuple[int, int]:
    """(checkers GenerateNE built, negative examples it was given).

    Counted by wrapping ``build_checker`` in generate_ne's own namespace and preparing
    one task. Everything else in the pipeline builds its checkers elsewhere, so the
    count is GenerateNE's alone.
    """
    from conacq.algorithms.acqmss import generate_ne as gen
    from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder
    from conacq.algorithms.acqmss.task_preparation import ConGenTaskInput
    from conacq.examples import ExampleIO
    from conacq.oracle import FMOracle

    examples = ExampleIO.load_json(str(repo / EXAMPLES / f'{stem}_{sampling}.json'))
    negatives = [e.assignments for e in examples.negative]

    built = 0
    original = gen.build_checker

    def counting(*args, **kwargs):
        nonlocal built
        built += 1
        return original(*args, **kwargs)

    oracle = FMOracle(str(repo / 'data' / 'fms' / f'{stem}.uvl'), use_incremental=False)
    gen.build_checker = counting
    try:
        model = (ConGenModelBuilder
                 .from_bias(str(repo / 'data' / 'bias' / f'{stem}-bias.json'))
                 .with_oracle_data(oracle.oracle_data).build())
        model.prepare_task(ConGenTaskInput.from_examples(
            oracle.oracle_data, [e.assignments for e in examples.positive], negatives))
    finally:
        gen.build_checker = original
        oracle.cleanup()
    return built, len(negatives)


def _cells(repo: Path, samplings: tuple) -> list:
    """(stem, sampling) cells WITH a result -- the paper's grid, not every file on disk.
    The development tree also holds busybox RS(2n)/RS(3n) example sets that produced no
    number; quantifying over them would assert something the paper does not claim."""
    from revision_cells import KNOWLEDGE_BASES, folds
    return [(stem, s) for s in samplings for stem, _label in KNOWLEDGE_BASES
            if folds(repo, stem, s, 'congen')]


def _example_set(repo: Path, stem: str, sampling: str) -> dict:
    import json
    return json.loads((repo / EXAMPLES / f'{stem}_{sampling}.json').read_text())


def _regenerate_with_spy(repo: Path, stem: str, sampling: str):
    """Regenerate one committed set from its recorded parameters, recording every
    oracle call. Returns (positives, negatives, completions, n_is_valid, n_features)."""
    import sys
    sys.path.insert(0, str(repo))
    from conacq.example_generators.feature_frequency import FeatureFrequencyGenerator
    from conacq.example_generators.nwise_coverage import TwoCoverageGenerator
    from conacq.example_generators.random_sampling import ControlledRandomSamplingGenerator
    from conacq.oracle import FMOracle

    meta = _example_set(repo, stem, sampling)['metadata']
    oracle = FMOracle(str(repo / 'data' / 'fms' / f'{stem}.uvl'))
    completions, valid_calls = [], [0]
    complete, is_valid = oracle.complete_configuration, oracle.is_valid

    def spy_complete(partial):
        result = complete(partial)
        completions.append((dict(partial), result))
        return result

    def spy_valid(config):
        valid_calls[0] += 1
        return is_valid(config)
    oracle.complete_configuration, oracle.is_valid = spy_complete, spy_valid
    try:
        if sampling.startswith('rs_'):
            ex = ControlledRandomSamplingGenerator(oracle).generate(
                total=meta['total'], valid_configs=meta['valid_configs'], seed=meta['seed'])
        elif sampling == 'ff':
            ex = FeatureFrequencyGenerator(oracle).generate(
                max_examples=meta['max_examples'], seed=meta['seed'])
        else:
            ex = TwoCoverageGenerator(oracle).generate(seed=meta['seed'])
        n = len(oracle.get_variables())
    finally:
        oracle.complete_configuration, oracle.is_valid = complete, is_valid
        oracle.cleanup()
    return ([e.assignments for e in ex.positive], [e.assignments for e in ex.negative],
            completions, valid_calls[0], n)


def _pair_coverage_gaps(examples: list, features: list) -> int:
    """Feature pairs missing at least one of their four value combinations. Bitmask per
    feature over the examples, so 854 features cost 364k pair tests, not 7.6M."""
    full = (1 << len(examples)) - 1
    on = [sum(1 << i for i, e in enumerate(examples) if e[f]) for f in features]
    gaps = 0
    for a in range(len(features)):
        for b in range(a + 1, len(features)):
            x, y = on[a], on[b]
            if not (x & y and x & ~y & full and ~x & y & full and ~x & ~y & full):
                gaps += 1
    return gaps


def run(check, repo: Path) -> None:
    sampling_protocol(check, repo)
    print('\n[contract] generator properties, not quoted in the paper or the letter')

    # The FF sampler's safety bound. The committed FF example sets are far below it --
    # generation stops on coverage -- but the bound is what keeps a model whose
    # coverage is unreachable from generating without end.
    for n in (14, 179, 854):
        check(f'FF asks for 10n examples, n={n}', ff_target_size(n), 10 * n)

    built, negatives = checkers_built_by_generate_ne(repo, CONTRACT_MODEL, CONTRACT_SAMPLING)
    check(f'{CONTRACT_MODEL} {CONTRACT_SAMPLING}: negative examples given', negatives, 9)
    check('   ... and GenerateNE builds one checker per negative', built, negatives)


def sampling_protocol(check, repo: Path) -> None:
    """S6.1.3's four claims about how the examples were made."""
    import sys
    sys.path.insert(0, str(repo))
    from conacq.example_generators.random_sampling import ControlledRandomSamplingGenerator
    from conacq.oracle import FMOracle
    from revision_cells import KNOWLEDGE_BASES

    rs_cells = _cells(repo, ('rs_1n', 'rs_2n', 'rs_3n', 'rs_m'))
    ff_cells = _cells(repo, ('ff',))

    print('\n[S6.1.3 (a)] random sampling: nine tenths positive, one tenth negative')
    check('S6.1.3: random-sampling example sets behind a result', len(rs_cells), 18)
    off, clamped = [], []
    for stem, s in rs_cells:
        d = _example_set(repo, stem, s)
        total = len(d['positive']) + len(d['negative'])
        if len(d['negative']) != max(1, total // 10):
            off.append((stem, s))
        cap = d['metadata'].get('valid_configs')
        if cap is not None and total - max(1, total // 10) > cap:
            clamped.append((stem, s))
    check('S6.1.3: sets whose negatives are not max(1, total // 10)', off, [])
    # The generator can move positives into negatives when a model has fewer valid
    # configurations than nine tenths of the sample; if that had fired anywhere, "one
    # tenth" would be false there. It is a property of the inputs, so it is checked.
    check('   ... sets where the valid-configuration cap moved that split', clamped, [])
    check('   ... and the generator computes exactly that split, for every committed total',
          all(ControlledRandomSamplingGenerator.calculate_distribution(t)
              == (t - max(1, t // 10), max(1, t // 10))
              for t in {len(_example_set(repo, st, s)['positive'])
                        + len(_example_set(repo, st, s)['negative']) for st, s in rs_cells}),
          True)

    print('\n[S6.1.3 (b)] every example is complete, and classified the way the paper says')
    checked, wrong = 0, []
    for stem, _label in KNOWLEDGE_BASES:
        oracle = FMOracle(str(repo / 'data' / 'fms' / f'{stem}.uvl'), use_incremental=False)
        features = set(oracle.get_variables())
        try:
            for st, s in rs_cells + ff_cells:
                if st != stem:
                    continue
                d = _example_set(repo, stem, s)
                for kind, want in (('positive', True), ('negative', False)):
                    for e in d[kind]:
                        checked += 1
                        a = e['assignments']
                        if set(a) != features or oracle.is_valid(a) is not want:
                            wrong.append((stem, s, kind, e.get('id')))
        finally:
            oracle.cleanup()
    check('S6.1.3: RS and FF example sets checked', len(rs_cells) + len(ff_cells), 23)
    check('   ... examples checked against their model, one by one', checked, 4849)
    check('   ... that are incomplete, or that the model classifies the other way', wrong, [])
    for sampling in ('rs_1n', 'ff'):
        stem = 'REAL-FM-7'
        pos, neg, completions, _valid, n = _regenerate_with_spy(repo, stem, sampling)
        d = _example_set(repo, stem, sampling)
        check(f'S6.1.3: KB1 {sampling} regenerated from its seed equals the committed set',
              (pos, neg), ([e['assignments'] for e in d['positive']],
                           [e['assignments'] for e in d['negative']]))
        outputs = [result for _partial, result in completions]
        check('   ... and every positive is the oracle completing a strictly partial assignment',
              all(p in outputs for p in pos) and all(len(partial) < n
                                                     for partial, _r in completions), True)
        if sampling == 'rs_1n':
            check('   ... that fixes at most half the features (RS)',
                  max(len(partial) for partial, _r in completions) <= n // 2, True)

    print('\n[S6.1.3 (c)] the 2-wise sample ignores the model, so it is almost all negative')
    two_cov = _cells(repo, ('2cov',))
    check('S6.1.3: 2-COV sets behind a result', len(two_cov), 5)
    check('Table 8: 2-COV positives per knowledge base, KB1..KB5',
          [len(_example_set(repo, stem, '2cov')['positive']) for stem, _s in
           sorted(two_cov, key=lambda c: [k for k, _ in KNOWLEDGE_BASES].index(c[0]))],
          [0, 0, 1, 1, 0])
    # Control: the gap counter reports a gap when one exists, so its zeros mean something.
    check('   ... control: one example over two features leaves that pair uncovered',
          _pair_coverage_gaps([{'a': True, 'b': True}], ['a', 'b']), 1)
    gaps = {}
    for stem, _s in two_cov:
        d = _example_set(repo, stem, '2cov')
        examples = [e['assignments'] for e in d['positive'] + d['negative']]
        gaps[stem] = _pair_coverage_gaps(examples, sorted(examples[0]))
    check('   ... feature pairs missing a value combination, over all five', gaps,
          {stem: 0 for stem, _s in two_cov})
    pos, neg, completions, valid_calls, _n = _regenerate_with_spy(repo, 'REAL-FM-7', '2cov')
    check('   ... KB1 regenerated from its seed equals the committed set',
          (pos, neg), ([e['assignments'] for e in _example_set(repo, 'REAL-FM-7', '2cov')['positive']],
                       [e['assignments'] for e in _example_set(repo, 'REAL-FM-7', '2cov')['negative']]))
    check('   ... generated without consulting the model: completions requested', len(completions), 0)
    check('   ... and the model is asked only to classify, once per example',
          valid_calls, len(pos) + len(neg))

    print('\n[S6.1.3 (d)] FF restricts the positive target to what is attainable, not the negative')
    check('S6.1.3: FF sets behind a result', len(ff_cells), 5)
    for stem, _s in ff_cells:
        d = _example_set(repo, stem, 'ff')
        meta, n = d['metadata'], d['metadata']['n_features']
        pos_pairs = {(f, v) for e in d['positive'] for f, v in e['assignments'].items()}
        neg_pairs = {(f, v) for e in d['negative'] for f, v in e['assignments'].items()}
        check(f'{stem} FF: positive target is the attainable pairs, fewer than all 2n',
              (meta['reachable_positive_pairs'] < meta['total_pairs'] == 2 * n,
               len(pos_pairs) == meta['reachable_positive_pairs']), (True, True))
        check('   ... negative target is all 2n pairs, and the negatives cover them',
              (meta['coverage']['total_needed'] == meta['reachable_positive_pairs'] + 2 * n,
               len(neg_pairs) == 2 * n, meta['fully_covered']), (True, True, True))
    from conacq.example_generators.feature_frequency import FeatureFrequencyGenerator
    oracle = FMOracle(str(repo / 'data' / 'fms' / 'REAL-FM-7.uvl'))
    try:
        gen = FeatureFrequencyGenerator(oracle)
        reachable = gen._reachable_positive_pairs(sorted(gen.features))
    finally:
        oracle.cleanup()
    check('   ... KB1 attainable pairs recomputed by the generator, against its metadata',
          len(reachable), _example_set(repo, 'REAL-FM-7', 'ff')['metadata']['reachable_positive_pairs'])

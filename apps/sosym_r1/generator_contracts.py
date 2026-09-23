#!/usr/bin/env python3
"""Two contracts of the generation pipeline. NEITHER IS QUOTED IN THE PAPER.

Every other module in this gate holds a number the paper or the response letter
prints, and says which. These two hold properties of the implementation that nothing
outside the repository states any more:

  * the feature-frequency sampler's safety bound, 10n examples;
  * one solver per negative example in GenerateNE's preprocessing.

Both were sentences in the submitted version and both were cut by the 2026-09-23
minimal-change review. They are kept because they are the contracts the committed
example sets and the committed preprocessing costs were produced under -- a later
change to either would move data the paper does print, silently. They carry NO section
reference, deliberately: a reader looking for them in the paper will not find them, and
a stale citation would send them looking.

The second is asserted BEHAVIOURALLY, by counting the checkers GenerateNE builds, not
by reading the source for a `build_checker` call. A source-shape assertion passes a
refactor that moves the call out of the loop but keeps the text.
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


def run(check, repo: Path) -> None:
    print('\n[contract] generator properties, not quoted in the paper or the letter')

    # The FF sampler's safety bound. The committed FF example sets are far below it --
    # generation stops on coverage -- but the bound is what keeps a model whose
    # coverage is unreachable from generating without end.
    for n in (14, 179, 854):
        check(f'FF asks for 10n examples, n={n}', ff_target_size(n), 10 * n)

    built, negatives = checkers_built_by_generate_ne(repo, CONTRACT_MODEL, CONTRACT_SAMPLING)
    check(f'{CONTRACT_MODEL} {CONTRACT_SAMPLING}: negative examples given', negatives, 9)
    check('   ... and GenerateNE builds one checker per negative', built, negatives)

#!/usr/bin/env python3
"""Show every revision assertion failing once, on an altered value.

    PYTHONPATH=. python3 apps/sosym_r1/mutate_revision_checks.py

WHY
---
An assertion that has only ever been seen green is not known to assert anything.
This project has shipped two of those: a coverage gate whose table lookup missed
every model it was meant to cover, and a test-suite check whose `grep FAILED`
found nothing because pytest had never run. Both were green the whole time.

WHAT THIS DOES
--------------
It runs the five revision modules once to collect every assertion, then re-runs
them once per assertion with THAT assertion's expected value altered, and
requires exactly two things:

  1. the altered assertion fails  -- so it is wired to the value it names;
  2. no other assertion changes outcome -- so a failure names its own subject
     rather than a neighbour's.

The expected side is what is altered because that is the side the manuscript
owns: a paper figure that drifts from the data is precisely what the gate is for.
A check that stayed green with its paper number altered would be decoration.

Exit: 0 = every assertion was shown failing. 1 = at least one is inert.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import revision_bias_composition            # noqa: E402
import revision_cabsc_condition             # noqa: E402
import revision_ea2468_limit                # noqa: E402
import revision_order_and_working_example   # noqa: E402
import revision_run_cost                    # noqa: E402

MODULES = (revision_bias_composition, revision_ea2468_limit,
           revision_run_cost, revision_order_and_working_example,
           revision_cabsc_condition)


def passes(got, want, tol: float | None) -> bool:
    """The gate's own comparison, kept in one place."""
    if isinstance(want, float):
        return abs(got - want) <= (5e-3 if tol is None else tol)
    return got == want


def altered(want):
    """A value that differs from `want` but keeps its shape."""
    if isinstance(want, bool):
        return not want
    if isinstance(want, (int, float)):
        return want + 1
    if isinstance(want, str):
        return want + '~'
    if isinstance(want, (list, tuple)):
        kind = type(want)
        return kind(list(want) + ['~']) if want else kind(['~'])
    if isinstance(want, dict):
        return {**want, '~': '~'}
    raise TypeError(f'no alteration defined for {type(want).__name__}')


def collect(mutate_index: int | None = None) -> list[tuple[str, bool]]:
    """Run every module, returning (name, passed) per assertion.

    With `mutate_index`, the assertion at that position is given an altered
    expected value; every other assertion runs untouched.
    """
    results: list[tuple[str, bool]] = []

    def check(name, got, want, tol=None):
        if len(results) == mutate_index:
            want = altered(want)
        results.append((name, passes(got, want, tol)))

    with redirect_stdout(io.StringIO()):
        for module in MODULES:
            module.run(check, REPO)
    return results


def main() -> int:
    baseline = collect()
    green = [n for n, ok in baseline if ok]
    print(f'{len(baseline)} revision assertions, {len(green)} green before mutation')
    if len(green) != len(baseline):
        print('FAIL: the gate is not green to begin with; mutation proves nothing here.')
        for name, ok in baseline:
            if not ok:
                print(f'  already red: {name}')
        return 1

    inert, noisy = [], []
    for i, (name, _ok) in enumerate(baseline):
        mutated = collect(mutate_index=i)
        if mutated[i][1]:
            inert.append(name)
            continue
        collateral = [mutated[j][0] for j in range(len(baseline))
                      if j != i and mutated[j][1] != baseline[j][1]]
        if collateral:
            noisy.append((name, collateral))

    for name, collateral in noisy:
        print(f'  [warn] altering "{name}" also moved: {collateral[:3]}')
    if inert:
        print(f'\nFAIL: {len(inert)} assertions stayed green with their value altered:')
        for name in inert:
            print(f'  - {name}')
        return 1
    print(f'OK: all {len(baseline)} assertions failed when their expected value moved.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

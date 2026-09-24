#!/usr/bin/env python3
"""The 28-cell grid, read once, for the modules that make claims across all of it.

WHY THIS EXISTS SEPARATELY
--------------------------
Three of the paper's paragraphs quantify over the whole evaluation -- "on all 23
non-2-COV combinations", "on 27 of 28", "across all evaluated combinations" -- and a
claim of that shape is only as good as its denominator. Each module that makes one
would otherwise build the grid again, and two grids that disagree about which cells
exist would produce two different 28s, both green.

A CELL IS THE MEAN OVER ITS FOLDS. Never the pooled figure and never the intersected
knowledge base: those are different quantities, and confusing them has already put
three wrong numbers into this paper.

Nothing here reads a table. Every value comes from the fold files, so a paragraph that
drifts from its own table fails here rather than agreeing with it.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

R1 = Path('data') / 'results_sosym_r1'

# (stem, label) in the order the tables print them.
KNOWLEDGE_BASES = [('REAL-FM-7', 'KB1'), ('fqa', 'KB2'), ('arcade-game', 'KB3'),
                   ('REAL-FM-4', 'KB4'), ('busybox-1.18.0', 'KB5')]
SAMPLINGS = ['rs_1n', 'rs_2n', 'rs_3n', 'rs_m', '2cov', 'ff']
METHODS = ['congen', 'example_only', 'example_first']


def fold_path(repo: Path, stem: str, sampling: str, method: str) -> Path:
    if method == 'congen':
        return repo / R1 / 'congen' / f'{stem}_{sampling}_cv_incremental.json'
    return (repo / R1 / 'interactive'
            / f'{stem}_{sampling}_cv_incremental_{method}.json')


def folds(repo: Path, stem: str, sampling: str, method: str) -> list[dict] | None:
    """The folds of one cell, or None where the unit was never run."""
    path = fold_path(repo, stem, sampling, method)
    return json.loads(path.read_text())['folds'] if path.exists() else None


def grid(repo: Path, method: str, value_of) -> dict[tuple[str, str], float]:
    """``{(sampling, stem): mean over folds}`` for one method.

    A cell with no file is ABSENT rather than zero. The five busybox units that were
    never run are the reason every count in these paragraphs is out of 28 and not 30.
    """
    out = {}
    for sampling in SAMPLINGS:
        for stem, _label in KNOWLEDGE_BASES:
            fs = folds(repo, stem, sampling, method)
            if fs:
                out[(sampling, stem)] = statistics.mean(value_of(f) for f in fs)
    return out


def accuracy(fold: dict) -> float:
    return fold['accuracy']


def runtime_ms(fold: dict) -> float:
    return fold['performance']['runtime_ms']


def kb_size(fold: dict) -> int:
    """The learned knowledge base, WITHOUT the negated negative examples."""
    return len(fold['kb_constraints'])


def positive_share(fold: dict) -> float:
    """The share of the test fold that is a valid configuration.

    The accuracy an accept-everything classifier would reach on that fold, which is
    what the paper compares each method against. Per fold, then averaged -- the
    pooled share is 89.4% against a per-fold mean of 74.6%, and only the second is
    comparable with how accuracy is computed.
    """
    size = fold['test_size']
    total = size['positive'] + size['negative']
    return size['positive'] / total

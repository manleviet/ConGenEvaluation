#!/usr/bin/env python3
"""The ea2468 feasibility figures: what recomputes here, and what does not.

S5.3 ends with the practical limit of the study: "one QuickXplain run of the
preprocessing step took about 95 seconds against the two-million-candidate bias
... and the projected preprocessing for all sampling strategies exceeded 46 hours
before acquisition could start."

THE TWO FIGURES HAVE DIFFERENT STANDING, AND THE PAPER MUST SAY SO
------------------------------------------------------------------
  * 95 s per negative example is a READING OFF A RUN THAT NO LONGER EXISTS. The
    probe sampled a detached process into `ea2468_probe.jsonl` and `ea2468_run.log`
    in session scratch; neither was ever committed, and neither survives. What is
    committed is the probe's report,
    `plans/reports/measurement-260822-0149-ea2468-congen-feasibility-probe-report.md`,
    which records the rate, the window it was measured over, and the machine.
    That machine was an Apple M1 Pro / 16 GB -- NOT the M4 Pro / 48 GB of S5.3.
    So the rate is a cited report, not a measurement of the reported setup, and
    the gate below pins it to the committed report rather than pretending
    otherwise. Fabricating a data file to make it look recomputed would make the
    artifact assert something no one measured.

  * 46 hours IS recomputable, and is recomputed here. It is the rate times the
    number of QuickXplain runs the sweep would perform, and that count comes from
    committed fold files: GenerateNE runs once per TRAINING negative, so a
    3-fold sweep over six sampling strategies performs
    sum over strategies, folds of (|E-| - |held-out fold|) runs. Nothing about
    that count depends on the lost log.

The split is the point. A projection is an arithmetic claim over committed inputs
and a rate; only the rate is external, and the artifact should show exactly which
part a reader has to take on the report's word.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

PROBE_REPORT = ('plans/reports/'
                'measurement-260822-0149-ea2468-congen-feasibility-probe-report.md')

# The probe's own figures, as its report states them.
REPORT_RATE_S_PER_NEGATIVE = 94.8
REPORT_TOTAL_HOURS = 46.2
# The raw sampler output the report names. Absent by design: see the docstring.
LOST_RAW_ARTEFACTS = ('ea2468_probe.jsonl', 'ea2468_run.log', 'probe_ea2468.py')


def quickxplain_runs_from_folds(folds_dir: Path) -> tuple[int, dict[str, int]]:
    """How many QuickXplain runs the full ea2468 sweep would perform.

    One run per negative example in a TRAINING split, so a fold contributes every
    negative outside its own held-out share, and the three folds of a strategy
    contribute 2x its negatives in total.
    """
    per_strategy: dict[str, int] = {}
    for path in sorted(folds_dir.glob('ea2468_*_folds.json')):
        neg_folds = json.loads(path.read_text())['negative_folds']
        total = sum(len(f) for f in neg_folds)
        per_strategy[path.stem] = sum(total - len(f) for f in neg_folds)
    return sum(per_strategy.values()), per_strategy


def figures_from_report(report: Path) -> dict[str, float]:
    """Read the rate and the projected total out of the committed report.

    Parsing rather than hardcoding: if someone edits the report's numbers, this
    gate goes red and the paper's citation is re-checked, which is the only
    protection a figure with no recomputable source can have.
    """
    text = report.read_text()

    def one(pattern: str) -> float:
        m = re.search(pattern, text)
        if not m:
            raise ValueError(f'{report.name}: no figure matching {pattern!r}')
        return float(m.group(1))

    return {
        'rate_s': one(r'\*\*([\d.]+) s per negative example\*\*'),
        'runs': one(r'\|\s*\*\*total\*\*.*?\*\*(\d+) QX\*\*'),
        'total_h': one(r'\|\s*\*\*total\*\*.*?\*\*([\d.]+) h\*\*'),
    }


def run(check, repo: Path) -> None:
    print('\n[limit] the ea2468 limit: the projection recomputes, the rate is a cited report')
    report = repo / PROBE_REPORT

    tracked = subprocess.run(['git', 'ls-files', PROBE_REPORT], cwd=repo,
                             capture_output=True, text=True).stdout.split()
    check('the probe report is committed, so the citation resolves', tracked, [PROBE_REPORT])

    fig = figures_from_report(report)
    check('report states the per-negative rate, in seconds',
          fig['rate_s'], REPORT_RATE_S_PER_NEGATIVE, tol=1e-9)
    check('   ... which is the "about 95 seconds" S5.3 quotes', round(fig['rate_s']), 95)
    check('report states the projected total, in hours',
          fig['total_h'], REPORT_TOTAL_HOURS, tol=1e-9)

    runs, per_strategy = quickxplain_runs_from_folds(repo / 'data' / 'folds')
    for name, n in per_strategy.items():
        print(f'      {name:28s} {n:5d} QuickXplain runs over its three folds')
    check('QuickXplain runs the sweep would perform, from committed folds', runs, 1752)
    check('   ... and the report counted the same number', int(fig['runs']), runs)
    projected_h = runs * REPORT_RATE_S_PER_NEGATIVE / 3600
    check('projected preprocessing, hours (runs x the report rate)',
          round(projected_h, 1), 46.1, tol=1e-9)
    check('   ... which "exceeded 46 hours", as S5.3 says', projected_h > 46.0, True)

    # The absence is reported, never asserted: a later run that DOES commit raw
    # output should not turn this gate red.
    missing = [n for n in LOST_RAW_ARTEFACTS
               if not list(repo.rglob(n))]
    if missing:
        print('      note: the probe\'s raw output is not in the artifact '
              f'({", ".join(missing)}).')
        print('      The 95 s rate is therefore cited from the report above, and was '
              'measured on an')
        print('      Apple M1 Pro / 16 GB -- not the M4 Pro / 48 GB machine of S5.3.')

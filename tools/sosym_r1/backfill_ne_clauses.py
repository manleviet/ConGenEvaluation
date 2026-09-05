#!/usr/bin/env python
"""Recover the NE clauses the CV layer never stored, and write them into the folds.

Algorithm 3 delivers KB <- B' u NE, so exact-equivalence needs the memorised
negative-example clauses. ``ConGenRunResult`` carries them; ``CrossValidationFoldResult``
never did — ``cross_validation.py`` uses them to compute accuracy and drops them. So
they are in no saved artefact, and the only surviving trace is a rendered description
string. Parsing that back would be reconstructing structured data from a rendering,
which has gone wrong three times on this project already.

Instead, regenerate them. NE is a deterministic function of the fold's training
negatives, produced by GenerateNE during ``prepare_task`` — 2.4 % of a ConGen run,
measured — so no acquisition is re-run. The split and the shuffle must come from the
same machinery as the original: a different negative ORDER lets QuickXplain minimise to
a different but equally valid conflict, so determinism here is a property of the path,
not of the algorithm.

This is a RECOVERY path, not the provenance of any committed tree. Since
cross_validation.py:230 stores ne_clauses natively from the run result, a fold produced
by current code already carries them and must not be regenerated over.

Two different quantities share the name. GenerateNE produces one blocking clause per
training negative; Reduce then discharges most of them, and what a fold STORES is what
survived — ``statistics.n_ne``, which is 1 where 11 negatives were seen. So the
regeneration invariant is stated against train_size.negative, and the stored field is
not that number. A fold whose record says n_ne == 0 therefore needs no regeneration at
all: its NE is empty by record, and filling it reads a stored fact rather than
recomputing one.

Algorithms differ here. QuAcqTaskInput carries only oracle_data, so the iterative
baseline never sees an example and cannot memorise one; every interactive fold records
n_ne == 0 and takes the record path below. Regenerating NE for those folds would
manufacture a theory the algorithm never delivered.

    backfill_ne_clauses.py --dry-run          # check the invariant, write nothing
    backfill_ne_clauses.py --cv-dir <dir>     # target a copied tree, never the source
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from conacq.algorithms.acqmss.congen_model_builder import ConGenModelBuilder  # noqa: E402
from conacq.algorithms.acqmss.task_preparation import (                        # noqa: E402
    ConGenTaskInput, ConGenTaskPreparation)
from conacq.eval import apply_folds, load_folds                                # noqa: E402
from conacq.examples import ExampleIO                                          # noqa: E402
from conacq.oracle import FMOracle                                            # noqa: E402

STEMS = ['busybox-1.18.0', 'arcade-game', 'REAL-FM-7', 'REAL-FM-4', 'fqa']


def stem_of(filename: str) -> str | None:
    for stem in STEMS:
        if filename.startswith(stem + '_'):
            return stem
    return None


def model_of(filename: str) -> str:
    """'arcade-game_rs_1n_cv_incremental.json' -> 'arcade-game_rs_1n'."""
    return filename.split('_cv_')[0]


class _CapturingPreparation(ConGenTaskPreparation):
    """ConGen preparation that keeps the per-negative blocking clauses.

    GenerateNE builds one blocking clause per negative — ``[-l1 … -lk, -ne_id]`` at
    generate_ne.py:183 — and ``_prepare_negative_examples`` then combines them into a
    single assumption and drops the per-negative objects. Everything downstream sees
    only the combined id, whose clauses are implications into auxiliary variables
    rather than exclusions over features, so the delivered theory reconstructed from it
    is semantically empty.

    Capturing here takes the clauses from where they are produced. The alternative —
    picking them back out of set_kb — means re-deriving the very disambiguation that
    ``_resolve_fallback_clause`` documents itself as REFUSING to guess.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.captured_blocking_clauses: list = []

    def _prepare_negative_examples(self, set_kb, assumptions, negation_map,
                                   set_neg_tv, provider, model, oracle_data,
                                   testsuite, alloc) -> None:
        before = len(set_kb)
        super()._prepare_negative_examples(
            set_kb, assumptions, negation_map, set_neg_tv, provider, model,
            oracle_data, testsuite, alloc)
        # GenerateNE appends exactly one blocking clause per negative, in order, before
        # the combine and negate steps append theirs. Take the first N and strip each
        # clause's own ``-ne_id`` guard, leaving the negated minimal conflict over
        # feature variables.
        n = len(testsuite.testcases)
        feature_ids = set(model.name_to_id.values())
        for clause in set_kb[before:before + n]:
            body = [lit for lit in clause if abs(lit) in feature_ids]
            if not body:
                raise SystemExit(
                    f"blocking clause {list(clause)} has no feature literal — it is "
                    f"auxiliary-only and would be vacuous in the checker")
            self.captured_blocking_clauses.append(body)


def ne_clauses_for_fold(model, oracle, pos, neg, fold_data, fold_idx):
    """Regenerate one fold's NE clauses through the same split and seed as the sweep."""
    train_pos, train_neg, _, _ = apply_folds(fold_data, pos, neg, fold_idx)
    rng = random.Random(fold_data.shuffle_seeds[fold_idx])
    rng.shuffle(train_pos)
    rng.shuffle(train_neg)

    prep = _CapturingPreparation()
    prep.prepare(model, ConGenTaskInput.from_examples(
        oracle.oracle_data, train_pos, train_neg))
    return prep.captured_blocking_clauses, train_pos, train_neg


def _unused(model, task):

    # set_neg_tv holds ONE combined id per fold, not one per negative. When there is
    # more than one negative, task_preparation allocates ne_id and appends
    # [neg_tv_id, -ne_id] for each of them: ne_id implies every per-e- id, a
    # conjunction. Resolving the combined id yields a single clause that carries none
    # of the individual exclusions, so the per-e- ids are what must be resolved.
    #
    # They are recovered structurally from those implication clauses rather than from
    # the description string, which renders them as ' AND '-joined text.
    out = []
    for combined in task.set_neg_tv:
        per_negative = [c[0] for c in task.set_kb
                        if len(c) == 2 and c[1] == -combined] or [combined]
        for aid in per_negative:
            clause = model._resolve_fallback_clause(aid, task.set_kb, task.negation_map)
            if not clause:
                raise SystemExit(
                    f"fold {fold_idx}: per-e- assumption {aid} resolved to no clause "
                    f"({len(task.set_kb)} set_kb clauses, negation_map "
                    f"{'has' if aid in task.negation_map else 'MISSING'} it)")
            out.append(list(clause))
    return out, train_pos, train_neg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--kbs', nargs='+')
    ap.add_argument('--cv-dir', required=True,
                    help="directory of CV files to fill, searched recursively. Required "
                         "and deliberately so: this tool rewrites what it is pointed at, "
                         "and the default it used to carry pointed into the tree every "
                         "comparison in the effort measures against. Point it at copies.")
    args = ap.parse_args()

    cv_files = sorted(Path(args.cv_dir).rglob('*_cv_*.json'))
    if not cv_files:
        print(f"no CV files under {args.cv_dir}", file=sys.stderr)
        return 1
    failures, checked, written, from_record = [], 0, 0, 0

    by_stem: dict = {}
    for cv in cv_files:
        stem = stem_of(cv.name)
        if stem and (not args.kbs or stem in args.kbs):
            by_stem.setdefault(stem, []).append(cv)

    for stem, files in by_stem.items():
        print(f"\n{stem}: {len(files)} CV files", flush=True)
        oracle = FMOracle(str(REPO / 'data' / 'fms' / f'{stem}.uvl'))
        model = (ConGenModelBuilder
                 .from_bias(str(REPO / 'data' / 'bias' / f'{stem}-bias.json'))
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        try:
            for cv in files:
                name = model_of(cv.name)
                examples = ExampleIO.load_json(
                    str(REPO / 'data' / 'examples' / f'{name}.json'))
                pos = [e.assignments for e in examples.positive]
                neg = [e.assignments for e in examples.negative]
                fold_data = load_folds(str(REPO / 'data' / 'folds' / f'{name}_folds.json'))

                data = json.loads(cv.read_text())
                for fold in data['folds']:
                    idx = fold['fold_index']
                    checked += 1

                    # The record already answers it: no NE survived Reduce, so the
                    # delivered theory carries none. Reading that beats regenerating,
                    # which for an algorithm that never memorises would invent clauses
                    # it did not deliver.
                    if fold['statistics']['n_ne'] == 0:
                        fold['ne_clauses'] = []
                        from_record += 1
                        continue

                    clauses, _, _ = ne_clauses_for_fold(
                        model, oracle, pos, neg, fold_data, idx)
                    expected = fold['train_size']['negative']
                    if len(clauses) != expected:
                        failures.append(
                            f"{cv.name} fold{idx}: regenerated {len(clauses)} NE "
                            f"clauses, expected {expected} (train negatives)")
                    fold['ne_clauses'] = clauses
                if not args.dry_run:
                    cv.write_text(json.dumps(data, indent=2))
                    written += 1
                print(f"  {cv.name}: "
                      f"{[len(f['ne_clauses']) for f in data['folds']]} NE clauses",
                      flush=True)
        finally:
            oracle.cleanup()

    print(f"\nchecked {checked} folds ({from_record} empty by record, "
          f"{checked - from_record} regenerated), wrote {written} files"
          f"{' (dry run)' if args.dry_run else ''}")
    if failures:
        print(f"\nINVARIANT VIOLATED on {len(failures)} fold(s):")
        for f in failures:
            print(f"  {f}")
        return 1
    if checked == from_record:
        print("nothing regenerated: every fold recorded n_ne == 0, so every ne_clauses "
              "came from the fold's own record. The invariant below was not exercised.")
    else:
        print(f"invariant holds: each of the {checked - from_record} regenerated folds "
              f"produced exactly train_size.negative NE clauses")
    return 0


if __name__ == '__main__':
    sys.exit(main())

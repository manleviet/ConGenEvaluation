#!/usr/bin/env bash
# Reproduce every table in the SoSyM revision, end to end, from one command.
#
#   ./reproduce_tables_sosym.sh            # from the committed trees   (~1 min)
#   ./reproduce_tables_sosym.sh --draft    # tables to a scratch dir, nothing official
#   ./reproduce_tables_sosym.sh --print-fingerprint   # the generator's hash, nothing else
#
# Output: data/results_sosym_r1/tables/ — results_tables.{md,tex}, corrected-gap-table.md,
#         significance.md, target-clause-counts.md, PROVENANCE.md
#
# Every step is gated. The script stops at the first failure and says which one;
# it never emits tables from inputs it could not verify. Both gates existed before
# this script and nothing called them, which is why a stale timing figure or a
# number that had quietly moved could reach a table unchallenged.
#
# The sweep is NOT re-runnable from here, deliberately. It took three weeks of
# machine time and one busybox fold alone is 15.5 h; the acquisition results are
# committed evidence, not something a table script should be able to overwrite.
# See tools/sosym_r1/sweep_queue.py if a sweep genuinely has to be redone.
set -euo pipefail

R1="data/results_sosym_r1"
TABLES_DIR="$R1/tables"
OFFICIAL=1

for a in "$@"; do
  case "$a" in
    # mktemp -d, not a fixed /tmp path: a predictable name can be pre-created by
    # another user as a symlink, and mkdir -p then succeeds and writes through it.
    # The cost is that the draft directory changes between runs, so the path is
    # echoed at both the generate step and DONE.
    --draft) OFFICIAL=0; TABLES_DIR="$(mktemp -d "${TMPDIR:-/tmp}/tables-sosym-draft.XXXXXX")" ;;
    # Prints the fingerprint and nothing else, so whatever records it alongside the
    # tables uses THIS implementation rather than a copy. Two implementations of one
    # hash drift silently, and the drift would look exactly like the mismatch the
    # fingerprint exists to detect.
    --print-fingerprint) PRINT_FP=1 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")"
export PYTHONPATH=.

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[31mFAILED: %s\033[0m\n' "$*" >&2; exit 1; }

# The five files whose bytes ARE the generator. Hashed rather than resolved to a
# commit; see the long note at the fingerprint's use below.
GENERATOR_FILES="reproduce_tables_sosym.sh
apps/extract_results.py
apps/sosym_r1/measure_corrected_gap_table.py
apps/sosym_r1/significance_tests.py
apps/sosym_r1/count_target_clauses.py"

compute_fingerprint() {
  # Each file asserted present before hashing. A missing file would otherwise hash to
  # nothing and still yield a confident-looking fingerprint — the empty-set-reads-as-a-
  # pass shape that has already produced two false greens in this project.
  while IFS= read -r gf; do
    [ -f "$gf" ] || die "generator file missing, cannot fingerprint: $gf"
  done <<< "$GENERATOR_FILES"
  printf '%s\n' "$GENERATOR_FILES" | python3 -c '
import hashlib, pathlib, sys
h = hashlib.sha256()
for name in sys.stdin.read().split():
    h.update(name.encode())
    h.update(pathlib.Path(name).read_bytes())
print(h.hexdigest()[:12])'
}

# Answered before the environment checks: the carve needs this in a tree that has no
# venv and no installed dependencies, and the fingerprint depends on neither.
if [ "${PRINT_FP:-0}" = "1" ]; then
  fp=$(compute_fingerprint)
  [ -n "$fp" ] || die "could not compute the generator fingerprint"
  printf '%s\n' "$fp"
  exit 0
fi

# ---------------------------------------------------------------- 0. environment
say "0/6  environment"
python3 -c "import sys; assert sys.version_info >= (3,11), sys.version" \
  || die "Python >= 3.11 required"
python3 -c "import explanation, flamapy" 2>/dev/null \
  || die "the 'explanation' package is not importable — run: pip install ."
python3 -c "import conacq" 2>/dev/null || die "conacq not importable (run from the repo root)"
python3 -c "import scipy" 2>/dev/null \
  || die "scipy missing — the significance tests and 18 of the verifier's checks need it (pip install -e .)"
echo "  ok: $(python3 -V), explanation + conacq + scipy importable"

# ---------------------------------------------------------------- 1. the evidence
say "1/6  the two trees this revision rests on"
# OLD and NEW are the pairing the N item rests on, and their paths are asserted by
# the verifier. Named here so a reader sees which is which before any table appears.
[ -d "data/results" ] \
  || die "data/results missing — that is OLD, the tree the published tables came from"
{ [ -d "$R1/congen" ] && [ -d "$R1/interactive" ]; } \
  || die "$R1 incomplete — that is NEW, the re-scored tree"
echo "  OLD = data/results        $(ls data/results/congen/*_cv_*.json 2>/dev/null | wc -l | tr -d ' ') congen, $(ls data/results/interactive/*_cv_*.json 2>/dev/null | wc -l | tr -d ' ') interactive"
echo "  NEW = $R1  $(ls $R1/congen/*_cv_*.json | wc -l | tr -d ' ') congen, $(ls $R1/interactive/*_cv_*.json | wc -l | tr -d ' ') interactive"

# ---------------------------------------------------------------- 2. timing gate
say "2/6  timing provenance gate"
echo "  Refuses a timing figure measured while another sweep unit was in flight."
python3 apps/sosym_r1/check_timing_provenance.py \
  || die "timing provenance — a reported runtime overlaps another run; re-time those units first"

# ---------------------------------------------------------------- 3. numbers gate
say "3/6  paper-numbers gate"
echo "  Every number quoted in the revision, recomputed from the committed data."
python3 apps/sosym_r1/check_paper_numbers.py \
  || die "paper numbers — a quoted number no longer reproduces. Update the note to the
       measurement, never the assertion to the number you hoped for."

# --porcelain, not `git diff`: diff does not see UNTRACKED files, so a brand-new
# generator module would slip past and the fingerprint would be computed over a
# generator that is not the one that ran. An unseen file passing a check is the same
# shape as a skipped assertion reading like a passing one.
#
# Checked BEFORE generating, not after: a run that fails this at the end has already
# written tables from code it cannot name, and those files outlive the failure.
# This script is itself part of the generator, so it is in the list -- it decides
# which tools run and with which trees.
dirty=$(git status --porcelain -- apps/ tools/sosym_r1/ "$(basename "$0")" || true)
if [ "$OFFICIAL" = "1" ] && [ -n "$dirty" ]; then
  printf '%s\n' "$dirty" >&2
  die "the generator has uncommitted or untracked changes (above). Commit the
       GENERATOR first, then re-run: what is published must be a state someone else
       can check out, not a working tree only you have. Use --draft to iterate."
fi

# A pass must be a positive count, not the absence of a failure. This caught nothing
# here and exists because it caught something twice elsewhere: a suite reported an
# empty set of failures while pytest was not installed, and a targeted run reported
# success against a test file that did not exist. Both exited 0. Collection is cheap;
# certifying a tree whose tests cannot even be collected is not.
say "3b/6  the suite is collectable"
if command -v python3 >/dev/null && python3 -c "import pytest" 2>/dev/null; then
  # A SMOKE CHECK, deliberately, and it says so rather than inventing a floor. The
  # count differs between repositories (681 here, 343 in the artifact), so any minimum
  # would be a chosen number needing a per-target patch -- and a reader has no baseline
  # to compare it against anyway. The gate that catches a partially-broken suite is
  # running it with its expected count, which is a separate acceptance criterion.
  #
  # What this MUST not do is discard pytest's own signal. A broken conftest.py kills a
  # directory and still collects the rest: measured, 2 collected from a 3-test tree,
  # which passes any low floor. But pytest exits 2. Suppressing stderr and reading only
  # a grep count threw that away -- the failure was visible and the check was not looking.
  # `|| collect_rc=$?` is required, not stylistic: under `set -e` a failing command
  # substitution aborts the script before the next line runs, so the die below never
  # printed and the run exited 2 with no explanation -- a gate that fails silently is
  # worse than none.
  collect_rc=0
  collect_out=$(python3 -m pytest tests/ --collect-only -q 2>&1) || collect_rc=$?
  n=$(printf '%s\n' "$collect_out" | grep -cE '::')
  [ "$collect_rc" -eq 0 ] || { printf '%s\n' "$collect_out" | tail -5 >&2
    die "pytest exited $collect_rc while collecting. Collection errors hide whole
       directories -- the remaining tests still collect, and any count-based check
       passes."; }
  [ "${n:-0}" -ge 1 ] \
    || die "pytest collected $n tests. An empty collection is not a passing suite."
  echo "  ok: $n tests collectable, collection clean"
else
  echo "  pytest not installed - skipping (install with: pip install '.[dev]')"
fi

# ---------------------------------------------------------------- 4. tables
say "4/6  generate tables -> $TABLES_DIR"
mkdir -p "$TABLES_DIR"
python3 -m apps.extract_results --results-dir "$R1" --output-dir "$TABLES_DIR" \
  || die "extract_results"
python3 apps/sosym_r1/measure_corrected_gap_table.py > "$TABLES_DIR/corrected-gap-table.md" \
  || die "gap table"
python3 apps/sosym_r1/significance_tests.py > "$TABLES_DIR/significance.md" \
  || die "significance tests"
python3 apps/sosym_r1/count_target_clauses.py > "$TABLES_DIR/target-clause-counts.md" \
  || die "target clause counts"

# ---------------------------------------------------------------- 5. verify
say "5/6  verify the emitted artifacts"
# A CONTENT fingerprint of the generator, deliberately NOT `git rev-parse HEAD`.
#
# HEAD names a commit, and a commit is not the thing that made these tables — it is
# whatever happened to be checked out when they were made. That distinction is not
# academic; it cost a defect at each end. Here, the recorded SHA went stale on every
# unrelated commit. In the carved artifact HEAD is a root commit the tables predate,
# so a reader's very first reproduction rewrote this file and reported a modified
# tree — the artifact telling its own reader that reproducing it broke something.
#
# Hashing the generator's own bytes fixes both ends at once: identical wherever the
# same code runs, changes exactly when the generator changes, and a reader recomputes
# it and gets back the committed value. The source commit is not recorded here at all,
# because nothing regenerable can hold it — it lives in this repository's root commit
# message, which no reproduction can overwrite.
fingerprint=$(compute_fingerprint)
[ -n "$fingerprint" ] || die "could not compute the generator fingerprint"
for f in results_tables.md results_tables.tex corrected-gap-table.md significance.md \
         target-clause-counts.md; do
  [ -s "$TABLES_DIR/$f" ] || die "missing or empty artifact: $TABLES_DIR/$f"
done
echo "  ok: five artifacts present and non-empty"

# An artifact must state the state at generation time, never a plan.
if grep -qniE 'pending|tonight|overnight|TODO|FIXME' "$TABLES_DIR"/*.md; then
  grep -niE 'pending|tonight|overnight|TODO|FIXME' "$TABLES_DIR"/*.md || true
  die "artifact hygiene — a generated artifact states a plan rather than a measurement"
fi
echo "  ok: no plan strings"

# CONTENT, not determinism. Every other gate here compares the artifact against itself:
# the 93 numbers are recomputed from the result trees and never open a table, and
# "byte-identical" compares a regenerated table with the committed one -- which agree
# perfectly when both are wrong. v1.0.0 shipped `KB3 & - & - & - & - & - & -` and no
# busybox row at all, through seven rounds of green gates, because nothing asked whether
# a table contained the data it claimed to.
python3 apps/sosym_r1/check_table_coverage.py --tables "$TABLES_DIR" \
  || die "table coverage -- a model with results is missing from the tables, or a row is
       blank while its neighbours have data. Fix the mapping, never the expectation."

cat > "$TABLES_DIR/PROVENANCE.md" <<EOF
# Provenance

Generated by \`reproduce_tables_sosym.sh\`, generator fingerprint \`$fingerprint\`$([ "$OFFICIAL" = "1" ] && echo ", clean" || echo " (DRAFT — generator may be dirty)").

The fingerprint is a SHA-256 over the bytes of the five generator files, not a commit
id. Re-running this script recomputes it, so a reader who reproduces these tables gets
this file back unchanged; a differing fingerprint means the generating code differs,
which a commit id could not have told you. The commit this artifact was derived from
is recorded in the repository's root commit message.

## Trees

| role | path | meaning |
|---|---|---|
| OLD | \`data/results\` | the tree the published tables were computed from |
| NEW | \`$R1\` | re-scored ConGen + interactive, each fold against its own oracle |

Both are required. The correction rests on the PAIRING of the two, and a table
that mixes a column from one with a column from the other reproduces from
neither. That defect is what the N-item report was superseded for.

## Gates passed

- \`check_timing_provenance.py\` — no reported runtime overlaps another run
- \`check_paper_numbers.py\` — every quoted number recomputes from committed data

## Not re-runnable from here

The acquisition sweep is committed evidence, not a table input. One busybox fold
at cap 5,000 is 15.5 h and the full sweep took three weeks of machine time.
EOF
echo "  ok: PROVENANCE.md written"

# ---------------------------------------------------------------- 6. the recipe
# A DOCUMENTED RECIPE IS AN EXECUTABLE CLAIM, and until now nothing executed it. The
# gates above check the numbers the pipeline produces; the README describes a second,
# independent route to those numbers, and that route was wrong for the entire life of
# the published artifact -- it sent reviewers through an entry point that reads a
# different schema, so it reported that the method learned nothing, and exited 0.
#
# RUNS LAST, AFTER THE TABLES ARE WRITTEN, and that ordering is deliberate. Placed
# before them it withheld every table whenever the recipe failed, including for reasons
# unrelated to any number. A mismatch here still fails the run loudly -- but the reader
# already holds the tables, and can see which of the two disagrees. A warning in the
# middle of a long log would have been the wrong fix: nobody reads those.
#
# Costs about 0.4 s against the pipeline's five, measured as the median of three clean
# runs; REAL-FM-7 is the cheapest cell by design. Compares n_kb and all three F1 values
# against the committed result, never the exit status -- an exit status is exactly what
# hid the defect this check exists for.
say "6/6  the README's worked example reproduces the committed numbers"
REF="$R1/congen/REAL-FM-7_ff_cv_incremental.json"
RECIPE_CFG="data/results_sosym/configs/congen_REAL-FM-7_ff.toml"
# Both inputs are tracked in this tree. A "skipped" branch here would be a check that
# cannot go red, which is the shape that has already produced two false greens in this
# project -- so their absence is a failure, not a reason to pass quietly.
#
# NOT EXERCISED, and said plainly so nobody assumes otherwise: both files are also read
# by the paper-numbers gate at step 3, so removing either turns THAT red first and this
# line is never reached. It is here for a tree assembled differently, not because it has
# been seen to fire. Treat it as untested code.
[ -f "$REF" ] || die "missing $REF -- the worked example has nothing to compare against"
[ -f "$RECIPE_CFG" ] || die "missing $RECIPE_CFG -- the worked example cannot be run"

# run_cv SKIPS any fold whose partial already exists (apps/run_cv.py:116), and a partial
# records neither seed nor shuffle_bias -- so one produced by a different configuration
# is indistinguishable from a correct one and is silently reused. Reproduced: a cell run
# once with shuffle_bias = false leaves partials that make the next run report n_kb
# 13/15/16 with three plausible-looking F1 triples, none of them right. See ADR-0019 §2.
# Clearing the scratch tree is what makes this measure the current code rather than
# whatever is lying around.
rm -rf scratch/congen
python3 -m apps.run_cv "$RECIPE_CFG" -o scratch > /dev/null 2>&1 \
  || die "the README's run_cv step failed. The worked example is broken."
python3 -m apps.run_compare \
    "$R1/compare_configs/score_one_cell_example.toml" > /dev/null 2>&1 \
  || die "the README's scoring step failed. The worked example is broken."
python3 - "scratch/congen/REAL-FM-7_ff_cv_incremental.json" "$REF" <<'PYEOF' \
  || die "the README's worked example no longer reproduces the committed numbers.
       The tables above are already written; this says the documented recipe and the
       pipeline disagree. Fix the recipe or the code -- never the reference."
import json, sys


def rows(path):
    with open(path) as fh:
        data = json.load(fh)
    return [(fold['statistics']['n_kb'],
             *(round(fold['evaluation'][s]['metrics']['f1_score'], 4)
               for s in ('description', 'clause', 'semantic')))
            for fold in data['folds']]


got, ref = rows(sys.argv[1]), rows(sys.argv[2])
# n_kb 0 is the specific shape of the defect this check exists for, so it is named
# rather than left to fall out of the comparison.
if any(row[0] == 0 for row in got):
    sys.exit('  the recipe scored an EMPTY knowledge base (n_kb 0)')
if got != ref:
    for i, (g, r) in enumerate(zip(got, ref)):
        if g != r:
            print(f'  fold {i}: recipe {g} != committed {r}')
    sys.exit(1)
print(f'  ok: {len(got)} folds match — n_kb {got[0][0]}, '
      f'semantic F1 ' + ', '.join(f'{row[3]:.4f}' for row in got))
PYEOF

printf '\n\033[32mDONE\033[0m — artifacts in %s\n' "$TABLES_DIR"

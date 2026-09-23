# ConGen — evaluation artifact

Source code, data and result tables for the ConGen paper. This repository is the **frozen
evaluation artifact**: the ConGen implementation as evaluated in the paper, together with
every input the reported numbers were computed from.

Ongoing development continues in a private working repository referred to in the code as
`AcqMSS`; nothing here depends on it, and nothing here is intended as a maintained
library. Comments, tests and documentation throughout this tree refer to `AcqMSS` — that
is the repository they mean.

## Install

Requires Python ≥ 3.11.

```bash
pip install .
```

The SAT infrastructure (`explanation`) is pinned to a public tag and installed
automatically. No sibling checkout is needed.

## Reproduce the tables

One command, from the committed data:

```bash
./reproduce_tables_sosym.sh
```

It writes `data/results_sosym_r1/tables/` — `results_tables.{md,tex}`,
`significance.md`, `target-clause-counts.md`, a `PROVENANCE.md` recording a
fingerprint of the generator's own bytes, and `tables/paper/` — one LaTeX fragment
per table the paper prints.

Running it here leaves the repository unchanged: `git status` stays clean, because every
one of those files is regenerated identical to the committed copy. That is the check —
if a file does change, the tables you are reading are not the ones this code produces.
The fingerprint is a hash of the generator rather than a commit id precisely so that it
survives this round trip; a commit id would name the checkout, not the code.

Every step is gated and the script stops at the first failure. Two gates run before any
table is written:

- **`apps/sosym_r1/check_timing_provenance.py`** — refuses a runtime measured while
  another sweep unit was in flight.
- **`apps/sosym_r1/check_paper_numbers.py`** — recomputes every number quoted in the
  paper's prose from the committed data. 345 checks.

and one runs after the tables are written:

- **`apps/sosym_r1/check_paper_tables.py`** — re-derives every cell of every paper
  fragment from the same result files, with a reader that shares no aggregation or
  formatting code with the generator. 1,420 cells. A fragment it cannot parse is a
  failure, not a skip.

  It also checks properties that do not depend on the generator's expressions at all:
  no printed duration is negative, phases sum within their total, declared parts sum to
  the declared total, and the profiler's timing scopes really do contain what is
  subtracted from them. A re-derivation shares the generator's definition and will
  agree with a wrong one; these will not.

### The paper's tables

`data/results_sosym_r1/tables/paper/` holds one `.tex` per table, named after the
label the paper uses (`tab_AcqMssruntime.tex`, `tab_kb_size.tex`, …). Each file is a
single `tabular` environment, optionally preceded by a `%` header naming each column's
source field, unit and — for a derived column — its exact expression. The caption, the
`\label` and the `table*` wrapper live in the manuscript. The journal's template forbids
`\input` of other TeX files, so the manuscript carries a transcription of each fragment
rather than including it: the fragment is the source these cells are checked against,
and the gate below holds the fragment to the data, not the manuscript to the fragment.

Every quality metric is the **mean over the three folds**. The two other aggregations
these files admit — the intersected knowledge base, and a pooled figure — are
different quantities, and neither is reachable from the generator. Two cell markers
appear and both are generated: `n/a` means the (knowledge base, sampling) unit was
not run, and `--` means it ran but the quantity is not defined there. Neither is ever
a zero.

### Re-running the acquisition itself

The **whole sweep** is not re-runnable from here: it took weeks of machine time and one
busybox fold alone is 15.5 h. The results are committed evidence, not a table input.

A **single cell** is a different matter, and worth trying — REAL-FM-7 completes in under
a second. `data/results_sosym/configs/` holds one generated config per cell:

```bash
python3 -m apps.run_cv data/results_sosym/configs/congen_REAL-FM-7_ff.toml -o scratch
```

To score that fold against its target theory, use `run_compare`'s **config mode**, with a
config whose `kb_dir` names your scratch copy:

```bash
python3 -m apps.run_compare data/results_sosym_r1/compare_configs/score_one_cell_example.toml
```

That config is 24 lines and points at `scratch/`; read it before running it. For any
other cell, generate the equivalent rather than editing it by hand:

```bash
python3 tools/sosym_r1/make_score_configs.py --cv-dir scratch/congen --out scratch
python3 -m apps.run_compare scratch/score_congen.toml
```

The evaluation is written back into the CV file itself, so read the results from
`scratch/congen/REAL-FM-7_ff_cv_incremental.json` — each fold gains an `evaluation`
block. For this cell they should read `n_kb` 16 and semantic F1 0.8462, 0.8462, 0.8627,
matching `data/results_sosym_r1/congen/REAL-FM-7_ff_cv_incremental.json`.

⚠ **Do not aim `kb_dir` at the committed trees.** Config mode writes each evaluation back
into the file it names, which is what you want for your own scratch copy and destructive
for `data/results_sosym_r1/` — it would re-score the committed results in place.

⚠ **`--kb` CLI mode cannot score a cross-validation file.** It expects a single
knowledge base with `kb_constraints` at the top level; a CV file holds its constraints
inside `folds[]`. Handed one it now refuses, names the reason, points here, and exits 1.

Until that check existed it did something worse: it scored an empty knowledge base and
reported `n_kb: 0` with precision and recall `0.0` for every strategy, exiting `0` with
no warning — zeros that were an artefact of the wrong entry point rather than a result.
That history is recorded in `docs/adr/0019-defects-found-reviewing-the-artifact.md`.

**What matches on a re-run, and what does not.** The learned knowledge base, the
accuracy, the negative examples, the metric values and the summary all reproduce
exactly. The *byte layout* of a scored JSON does not: the scorer's output order depends
on `PYTHONHASHSEED`, so element order within a result — and the timing block, which
measures your machine — will differ between runs. This is expected. Compare values, not
file hashes.

Cost varies enormously across cells — seconds for REAL-FM-7, hours for busybox — so read
the cell name before launching one.

## What is not included

The released example sets cover the cells reported in the paper. Sets for
busybox RS(2n) and RS(3n), and the `ea2468` family, were generated during the
study, never completed a run, and are **not** included — they produced no number
here, and shipping them tripled the size of every clone. `apps/conf/generate_cv_folds_config.toml`
lists the 28 cells that do have results, and no more.

The `ea2468` **fold** files are the one exception, and they are here because a
number in the paper is computed from them: the projected preprocessing for that
model is one QuickXplain run per training negative, 1,752 of them, and the fold
files are what that count is read from. 112 KB. Their example sets stay out.

## Provenance

This repository is derived from a private working repository where ConGen is developed
alongside unrelated work. It holds what the paper rests on and nothing else: the
implementation as evaluated, the inputs those results were computed from, the results
themselves in `data/results_sosym_r1`, and the code that turns them into the tables. The
derivation is scripted, so it can be repeated for a later version rather than assembled
by hand.

## Layout

```
conacq/          the ConGen implementation
apps/            entry points; apps/sosym_r1/ is what the table pipeline runs
tools/sosym_r1/  sweep machinery and one-off measurements — not part of reproduction
data/            feature models, examples, folds, bias, and the results
plans/reports/   the two ea2468 feasibility probes; the size limit in §5.3 cites them
tests/           the suite
```

## Citing

See `CITATION.cff`.

## License

MIT — see `LICENSE`.

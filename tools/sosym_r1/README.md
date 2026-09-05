# tools/sosym_r1 — how the results were produced

Everything here is **provenance, not reproduction**. Nothing in this directory is called
by `reproduce_tables_sosym.sh`; the tools that regenerate the paper's numbers live in
`apps/sosym_r1/`. These record how the underlying sweep was scheduled, costed and
checked, and they are kept so the results are auditable rather than merely present.

The sweep itself is **not re-runnable from this repository**. It took weeks of machine
time — one busybox fold alone is 15.5 h — and the acquisition results under `data/` are
committed evidence, not something a reader is expected to regenerate.

## One exception, and it matters

`sweep-ledger.json` is **not** inert. `apps/sosym_r1/check_timing_provenance.py` reads it
to verify that no reported runtime was measured while another unit shared the machine,
and that check is one of the two gates `reproduce_tables_sosym.sh` runs before it will
emit a table. Deleting the ledger does not tidy this directory — it breaks a gate in the
reproduction path.

## Contents

| file | what it is |
|---|---|
| `sweep-ledger.json` | when every unit ran; **read by the timing gate** |
| `sweep_queue.py` | ran the sweep in windows, losing at most the unit in flight |
| `sweep_units.py` | the atomic unit — one fold of one (kb, sampling, algorithm) cell — and its cost model |
| `measurements.jsonl` | recorded measurements from the sweep |
| `calibrate_multiplier.py` | measures a cost ratio from finished ledger units |
| `congen_check_unit_factors.py` | node-vs-solver-call unit factors |
| `make_score_configs.py` | generates the stage-2 scoring configs, one block per CV file |
| `backfill_ne_clauses.py` | recovery path for NE clauses the CV layer did not store |
| `verify_examples_bundle.py` | independent check of an example-set + fold bundle |

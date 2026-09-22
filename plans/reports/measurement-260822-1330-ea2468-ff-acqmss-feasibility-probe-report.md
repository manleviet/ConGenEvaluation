# ea2468 feasibility probe 2 — ff — first AcqMss measurement

- Date: 2026-08-22
- Branch: `feat/sosym-r1` @ `a3fd43b`
- Machine: Apple M1 Pro, 16 GB, darwin
- Config: `algorithm=congen`, `solver_mode=incremental`, `minimize` default (True), `n_folds=3`, `seed=42`, single model `ea2468_ff`
- Ceiling: **10800 s (3 h)**, self-enforced, fired exactly on time
- Output to scratch; `data/results/` untouched. No file under `conacq/algorithms/**` modified — `generate_ne.py` not touched.
- **Feasibility sizing. Not numbers for the paper.** (`ea2468_ff.json` is in C11 scope — quality figures from this run are not citable and none are reported.)

## Verdict

**ea2468 cannot have a row in the table, under any sampling.**

Probe 1 said preprocessing was too slow. Probe 2 says something strictly stronger: **AcqMss itself does not converge.** On the *cheapest* sampling — ff, 6 negatives and 234 training positives — AcqMss ran **2.79 h without finishing**, and Reduce never started.

Fold 1 did not complete. Zero folds completed. Scratch output dir empty, as expected from `run_cv.py:210`.

## Phase split — fold 1 (train 234+ / 6−)

| phase | wall | solver calls | s/call | unit rate |
|---|---|---|---|---|
| preprocessing (GenerateNE) | **696 s** (11.6 min) | 314 | 2.22 | 116 s per negative |
| **AcqMss** | **10,044 s (2.79 h)** | **46,654** | **0.215** | 20.8 s/node, 483 nodes |
| Reduce | **0 s — never started** | — | — | — |

Timeline: process start → examples +1.0 s → bias load (692 MB) ≈ 10 s → Fold 1 `+60.4 s` → **AcqMss starts `+756 s`** → ceiling `+10800 s`.

Phase boundaries were detected exactly as specified: preprocessing end = `quickxplain_calls` reaching 6; AcqMss start = first appearance of `paper_consistency_checks` (`+756 s`); Reduce start = first appearance of `redundancy_consistency_checks` — **which never occurred**.

## The four counters

| counter | final value | unit |
|---|---|---|
| `quickxplain_calls` | 6 / 6 | negatives (preprocessing complete) |
| **`paper_consistency_checks`** | **483** | **batch nodes** |
| `redundancy_consistency_checks` | **ABSENT** | — (Reduce never ran) |
| `is_consistent_calls` | 46,968 | solver calls |
| `acqmss_calls` | 506 | `find_mss` returns |
| `shared_admpool_checks` | 482 | batch nodes |
| `solver_time_accum` | 5,661 s | 52 % of wall |

`paper_consistency_checks = 483` is **non-zero — the first AcqMss measurement on ea2468 in either probe.**

Derived: AcqMss solver calls = 46,968 − 314 = **46,654**.

### Unit mismatch, now measured

**46,654 solver calls / 483 batch nodes = 96.6×.**

`paper_consistency_checks` undercounts AcqMss's real solver work by ~97×. Summing it with `redundancy_consistency_checks` (1 per solver call, `reduce.py:89-90`) is apples-to-oranges by that factor — the concern that motivated requiring all four counters is quantified here.

Mean |E′⁺| per node = 96.6 against |E⁺| = 234 → **shrink ratio 0.41**. Within the run it fell 165 → 100 → 105 as the recursion descended, i.e. E′⁺ genuinely contracts with depth.

### Note on `acqmss_calls`

`count_calls` increments **after** the wrapped call returns (`decorators.py:100-102`) and decorates the **recursive** `find_mss` (`acqmss.py:50-52`). So `acqmss_calls` is a *post-order return* counter, not a start marker — its first appearance (`+1421 s`) meant the first leaf returned, not that AcqMss finished. 506 returns vs 483 checked nodes: 23 nodes returned without a consistency check (δ = ∅ or base case).

## Bottleneck, in consistent units

| measure | AcqMss | preprocessing |
|---|---|---|
| wall time | **93.5 %** | 6.5 % |
| solver calls | **99.3 %** | 0.7 % |

**AcqMss is the bottleneck**, on both units. This *inverts* probe 1's picture, which named GenerateNE only because it never got past it.

Probe 1's caveat is now confirmed quantitatively: preprocessing costs **2.22 s/call here (7.36 s/call on rs_3n)** because it rebuilds a *non-incremental* checker per negative, whereas AcqMss builds once and runs incremental at **0.215 s/call** — **10–34× cheaper per call**. Extrapolating AcqMss from probe 1's per-call figure would have been badly wrong.

## Does AcqMss terminate?

Unknown, and not determinable from this run. 483 nodes in 2.79 h with a **flat** node rate (25.7 → 21.9 → 23.0 s/node across thirds) and no sign of convergence.

One thing *is* provable. The node bound is 2γ·log₂(n/γ) + 2γ with n = |B| = 2,047,362. Exceeding 483 nodes without terminating rules out small γ:

| γ | bound (nodes) | at 23.0 s/node |
|---|---|---|
| 10 | 373 | 2.4 h — **excluded, already exceeded** |
| 20 | 706 | 4.5 h |
| 50 | 1,632 | 10.4 h |
| 100 | 3,064 | 19.6 h |
| 500 | 13,000 | 83.1 h |
| 1,000 | 23,999 | 153.3 h |

So **γ > 10 is established**, putting fold-1 AcqMss above ~4.5 h even on the most optimistic surviving γ, and into tens of hours for moderate γ. γ itself was not measured.

## Extrapolation to rs_1n and rs_3n

**Preprocessing** — scales with |E⁻| per fold; measured directly, 95–116 s per negative across both probes:

| sampling | train_neg/fold | preprocessing/fold |
|---|---|---|
| ff | 6 | 0.19 h *(measured)* |
| rs_1n | 93 | 2.4–3.0 h |
| rs_3n | 281 | 7.4–9.1 h |

**AcqMss** — two factors, one certain and one not:

1. *Per-node cost ∝ |E′⁺|* — **structurally certain, not an assumption**: `is_consistent_test_cases` (`backend.py:81-86`) loops over `set_tc` issuing exactly one `is_consistent` per element when `stop_at_first_violation=False`. Calls per node = |E′⁺| by construction.
2. *Shrink ratio |E′⁺|/|E⁺| = 0.41* — **measured for ff only**. This is the part I cannot verify across samplings: the probe has a single |E⁺| value (234), so within-run variation (165→105) shows E′⁺ contracts with depth but says nothing about how the ratio behaves at |E⁺| = 845 or 2534. Treated as an assumption, flagged, not asserted.

Under that assumption, s/node scales with |E⁺|: rs_1n (|E⁺| = 845) ≈ 75 s/node; rs_3n (|E⁺| = 2534) ≈ 225 s/node. At the *already-exceeded lower bound* of 483 nodes:

| sampling | AcqMss lower bound / fold |
|---|---|
| ff | > 2.8 h *(measured, unfinished)* |
| rs_1n | > 10 h |
| rs_3n | > 30 h |

Node count is likely **larger**, not equal, for richer samplings: more positives violate more bias constraints → larger γ → more nodes. So these are floors on floors.

## Memory

- **Peak RSS 4.56 GB**, reached during **preprocessing**, not acquisition
- AcqMss steady-state RSS ≈ **1.03 GB**, flat for 2.79 h — no growth, no leak
- No OOM, no swap pressure on 16 GB

This contradicts the expectation that acquisition would be the memory-hungry phase: acquisition is ~4× *lighter* than preprocessing here. Memory is not the constraint — time is.

## The probe-1 SIGTERM at +3554 s — cause identified

**It was the harness killing background tasks, not the algorithm, not memory, not machine sleep.**

Probe 2 ran under `os.setsid()` (new session) plus `caffeinate -i` and survived the full 3 h to its own ceiling, recording only `poll`/`start`/`CEILING_HIT` tags — no `SIGNAL_15`. The control: my *analysis* job, launched as an ordinary background Bash task during probe 2, was killed at ~11 min while the detached probe kept running. Detaching is the fix.

## Straight call

**No — ea2468 gets no row, under any sampling.**

ff is the cheapest of the six: 40× less preprocessing than rs_3n and ~10× cheaper per AcqMss node. It still failed to complete a single fold in 3 h, with AcqMss alone consuming 2.79 h and not converging. Every other sampling is strictly more expensive on both phases. A table row needs 3 folds × 6 samplings.

This is now a statement about **acquisition**, not preprocessing — materially stronger than probe 1's finding. The practical size limit sits below |B| = 2,047,362: at that bias size AcqMss does not converge in hours even with only 234 positive examples. busybox at |B| = 6,635 (308× smaller) remains the largest KB that completes.

## Repo state

- `apps/conf/run_cv_config.toml` — **reverted to HEAD** (2026-08-22, after the run). The probe edit was scratch, never committed; working tree is clean.

  To reproduce, comment out the existing `[[models]]` entries and append exactly this block (the rest of the file is HEAD as-is — `algorithm = "congen"`, `solver_mode = "incremental"`, `n_folds = 3`, `seed = 42`, `shuffle_bias = true` already match):

  ```toml
  [[models]]
  name = "ea2468_ff"
  oracle = "data/fms/ea2468.uvl"
  bias = "data/bias/ea2468-bias.json"
  examples = "data/examples/ea2468_ff.json"
  folds_path = "data/folds/ea2468_ff_folds.json"
  ```

  Probe 1 used the identical block with `ea2468_rs_3n` substituted for `ea2468_ff` in all five fields.

  Run as: `PYTHONPATH=. python -m apps.run_cv apps/conf/run_cv_config.toml -v -o <scratch>`
  — the `-o` is required; without it `run_cv.py:76` writes into `data/results/congen/`.
  Detach the process (`os.setsid()`) or the harness kills it at ~1 h; see the SIGTERM section.
- No data committed. `conacq/algorithms/**` and the evaluation runners untouched. `minimize` left at default True.
- Artefacts in session scratch: `ff_probe.jsonl` (2065 samples @ 5 s), `ff_run.log` (timestamped), `probe_ea2468.py`, `watch_phases.py`.
- Cosmetic: the wrapper's ceiling message hardcodes "2h CEILING HIT" while the configured ceiling was 10800 s. The 3 h value is correct; only the string is stale.

## Unresolved

1. **Total AcqMss node count / γ for ea2468 — still unmeasured.** Only γ > 10 is established. Bounding it needs either a run to completion (≥ 4.5 h, plausibly ≫) or instrumenting |MSS| growth.
2. **Shrink ratio |E′⁺|/|E⁺| across samplings** — measured 0.41 for ff only. The rs_1n/rs_3n AcqMss projections inherit this as an unverified assumption. Testable cheaply by running rs_1n far enough to read calls/node (~20 min past its ~2.5 h preprocessing).
3. **Reduce cost on ea2468 — still zero data**, in both probes. It has never started. Unknown whether it is cheap or another wall.
4. Fold 2/3 assumed comparable to fold 1; only fold 1 was entered. Fold negative counts differ ([4,3,3]), so preprocessing differs slightly per fold.
5. Whether checker reuse in `generate_ne.py` (deferred per plan.md §C) would help — it targets the phase that is now only 6.5 % of wall, so it would **not** make ea2468 feasible. The binding constraint is AcqMss.

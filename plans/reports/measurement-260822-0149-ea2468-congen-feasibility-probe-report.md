# ea2468 ConGen feasibility probe — sizing, not results

- Date: 2026-08-22
- Branch: `feat/sosym-r1` @ `a3fd43b`
- Machine: Apple M1 Pro, 16 GB, darwin
- Config: `algorithm=congen`, `solver_mode=incremental`, `n_folds=3`, `seed=42`, `shuffle_bias=true`, single model `ea2468_rs_3n`
- Output redirected to scratch (`-o`); `data/results/` untouched. No algorithm file modified.
- **Purpose: feasibility sizing. Not numbers for the paper.**

## Verdict

**ea2468 is not evaluable in the remaining budget.** GenerateNE preprocessing alone projects to **≈46 h** for the 6-sampling × 3-fold sweep, before a single AcqMss or Reduce check runs.

And the framing question cannot be answered as posed: **the bottleneck is neither AcqMss nor Reduce.** Neither phase was ever reached. The cost sits upstream in `GenerateNE`.

## What actually happened

Run started 00:50:05, terminated by SIGTERM at 01:49:19 — **+3554 s (59.2 min)**. This was *not* the 2 h ceiling (7200 s); the process was stopped externally at ~59 min. The self-enforced ceiling never fired.

Fold 1 **did not complete**. It never left GenerateNE preprocessing.

| milestone | elapsed |
|---|---|
| process start | +0.1 s |
| examples loaded (E⁺ 3802, E⁻ 422) | +1.0 s |
| **bias load (692 MB JSON)** | **+1.0 → +11.1 s ≈ 10 s** |
| fold data loaded, INCREMENTAL entered | +11.1 s |
| `=== ConGen Fold 1/3 ===` | +56.9 s |
| `ConGenRunner.run(E+=2534, E-=281)` | +56.9 s |
| first QuickXplain completes | +234 s |
| **SIGTERM (external)** | **+3554 s** |

Fold-1 train split: **2534 positives / 281 negatives** (test 1268+/141−). The 2534 matches your ≈2535 figure.

`run_cv.py` writes JSON only after all three folds — confirmed, the scratch output dir is **empty**. The out-of-band sampler (10 s poll + SIGTERM handler) is the only surviving data.

## The three mandated counters

At termination (+3554 s):

| counter | value | reading |
|---|---|---|
| `paper_consistency_checks` | **never appeared** | AcqMss never started |
| `redundancy_consistency_checks` | **never appeared** | Reduce never started |
| `is_consistent_calls` | **463** | entirely GenerateNE QuickXplain |

Only three keys ever appeared in the profiler across all 347 samples: `is_consistent_calls`, `quickxplain_calls`, `qx_calls`.

Applying your formula:

```
AcqMss solver calls ≈ is_consistent_calls − redundancy − preprocessing
                    ≈ 463 − 0 − 463 = 0
```

**AcqMss did zero solver work.** The unit-mismatch concern that motivated requiring all three counters is real and correctly anticipated — but here it is moot, because the batch counter is not merely undercounting, it is *absent*: the phase never ran.

Progress markers: `quickxplain_calls = 36` of **281** negatives (**12.8 %**), `qx_calls = 835` (recursive QX nodes).

## Measured rates

Window +234 s → +3554 s (3320 s, 35 negatives):

- **94.8 s per negative example**
- **7.36 s per `is_consistent` call**, 12.9 calls per negative

Linear, no degradation — 99.4 s/neg over the first 8, 93.4 s over the next 7. The KB grows by one `ne_clause` per negative, negligible against 2 M.

## Why it is slow — structural

`generate_ne.py:155-171` runs, **per negative example**:

```python
with build_checker(task, SolverBackend.PYSAT_NON_INCREMENTAL, profiler=profiler) as checker:
    quickxplain = QuickXPlain(checker, profiler)
    minimal_conflict = quickxplain.find_conflict(task.set_c, task.set_b)
```

A **fresh non-incremental checker built per negative**, over the full |B| = 2,047,362 bias. At 12.9 SAT calls per negative and 94.8 s wall, most of the per-negative cost is plausibly **solver construction**, not solving — but this probe cannot separate the two.

## Projection

Train negatives = ⅔ of E⁻ per fold. All six sets measured directly from the example files:

| sampling | E⁺ | E⁻ | train_neg/fold | GenerateNE 1 fold | 3 folds |
|---|---|---|---|---|---|
| rs_3n | 3802 | 422 | 281 | 7.40 h | 22.21 h |
| rs_2n | 2535 | 281 | 187 | 4.93 h | 14.78 h |
| rs_1n | 1268 | 140 | 93 | 2.45 h | 7.35 h |
| 2cov | 0 | 22 | 15 | 0.40 h | 1.19 h |
| ff | 351 | 10 | 7 | 0.18 h | 0.55 h |
| rs_m | 20 | 2 | 1 | 0.03 h | 0.08 h |
| **total** | | | **1752 QX** | | **46.2 h** |

**Assumptions**: linear in negative count (measured, holds over 35 negatives); constant per-negative cost across samplings — same bias, same 2468 features, so the dominant per-negative work is identical. Fold splits assumed even at ⅔; actual splits vary by ±1.

This is a **lower bound on preprocessing only**. AcqMss and Reduce add unknown, unbounded time on top.

## Memory

- **Peak RSS 4.86 GB** (4976.6 MB), max sampled 4.62 GB
- Oscillates 2.4–3.5 GB steady-state; the 692 MB bias JSON expands to ≈2.4 GB resident within 10 s of load
- **No OOM, no swap death.** But AcqMss — where the MSS search would stress memory — was never reached, so 4.86 GB is *not* a peak for a complete fold.

## Answer to the framing question

> Một fold ConGen trên ea2468 / rs_3n tốn bao nhiêu, và nút thắt nằm ở AcqMss hay Reduce?

- **Cost of one fold**: unknown, but **> 7.4 h**, since GenerateNE alone projects to 7.40 h and neither acquisition phase had begun at 59 min.
- **Bottleneck**: neither. It is `GenerateNE`, the per-negative QuickXplain preprocessing. The AcqMss-vs-Reduce question is not reachable at this scale without first fixing preprocessing.

## Straight call

**No — ea2468 cannot be evaluated before 2026-08-26.** 46 h of preprocessing alone, on a single machine, with acquisition cost unmeasured on top, against a deadline four days out and a single-combined-sweep decision that yields no partial results.

This is a **measured non-completion**, which is the usable form of the reviewers' request to state the practical size limit: at |B| = 2,047,362 (308× busybox's 6,635, which itself cost 16.6 h at rs_1n), the pipeline does not reach acquisition within an hour on an M1 Pro. The limit sits below ea2468.

If ea2468 is wanted later, the target is GenerateNE, not AcqMss/Reduce — the per-negative non-incremental checker rebuild is the thing to attack.

## Repo state

- `apps/conf/run_cv_config.toml` — **reverted to HEAD** (2026-08-22, after probe 2). The edit was scratch, never committed.

  Block used for this probe (rest of file HEAD as-is):

  ```toml
  [[models]]
  name = "ea2468_rs_3n"
  oracle = "data/fms/ea2468.uvl"
  bias = "data/bias/ea2468-bias.json"
  examples = "data/examples/ea2468_rs_3n.json"
  folds_path = "data/folds/ea2468_rs_3n_folds.json"
  ```
- No data committed. No file under `conacq/algorithms/**` and no evaluation runner touched.
- Raw artefacts in session scratch: `ea2468_probe.jsonl` (347 samples), `ea2468_run.log` (timestamped), `probe_ea2468.py`.

## Unresolved

1. ~~**AcqMss and Reduce cost on ea2468 — entirely unmeasured.**~~ **RESOLVED for AcqMss by probe 2** (`measurement-260822-1330-ea2468-ff-acqmss-feasibility-probe-report.md`): on ff, AcqMss ran 2.79 h without converging — 483 nodes, 46,654 solver calls, **0.215 s/call**. The caveat here was correct: preprocessing's 7.36 s/call overstates AcqMss by 10–34×, and AcqMss — not GenerateNE — is the real bottleneck (93.5 % of wall, 99.3 % of solver calls). **Reduce remains unmeasured** — it has never started in either probe.
2. **Construction vs solving split** inside the 94.8 s/negative not separable from these counters. Needs a timer around `build_checker` in `generate_ne.py` — additive, but a source change.
3. ~~**Who terminated the run at +3554 s**~~ **RESOLVED by probe 2**: the harness kills background Bash tasks at ~1 h. Not resource pressure, not machine sleep, not the algorithm. Probe 2 ran under `os.setsid()` and survived a full 3 h with no `SIGNAL_15`; the control was an ordinary background analysis job killed at ~11 min while the detached probe kept running. Peak RSS 4.86 GB therefore stands as a real reading, not a truncated trajectory.
4. Whether `minimize=false` (raw negatives, skipping the oracle QuickXplain per `generate_ne.py:150`) would make ea2468 tractable — that path skips the entire measured bottleneck. Not probed; would change the negatives semantics and so is a design decision, not a tuning knob.
5. Fold 2/3 costs assumed equal to fold 1. Unverified — only fold 1 was entered.

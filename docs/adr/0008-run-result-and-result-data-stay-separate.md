# ADR-0008: `ConGenRunResult` and `ConGenResultData` stay separate — write-product ≠ read-projection

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Viet-Man Le

## Context

Two dataclasses describe the ConGen result JSON:

| | `ConGenRunResult` (`conacq/runners/`) | `ConGenResultData` (`conacq/eval/result_loader.py`) |
|---|---|---|
| Produced by | a **run** — the runner emits it | a **load** — `from_json` parses a file |
| Shared fields (6) | `kb_constraints`, `redundant_constraints`, `n_bias`, `n_mss`, `n_kb`, `bg_clauses` | the same 6 |
| Write-only (6) | `kb_clauses` (live CNF), `runtime_ms`, `consistency_checks`, `memory_peak_mb`, `profiler_data`, `metrics` (a live `RunMetrics`) | — |
| Read-only (1) | — | `metadata` |

Six field names in common invites the obvious conclusion: *this is duplication, unify them*. The earlier redesign branch did exactly that (`UnifiedConGenResult`), and the plan for this redesign carried the item forward.

**It is not duplication.** `ConGenResultData` deliberately reads **less** than the runner writes — it is the projection `kb_comparator`, `progressive_evaluation` and `run_compare` actually need out of a file. A *load* never reconstructs the CNF, the profiler dump, or the metric bundle, and none of its consumers ask for them. The six shared names are the **domain's vocabulary**, not evidence that one type is the other.

## Decision

**Keep them separate. The `UnifiedConGenResult` item is rejected, not deferred.**

## Options considered

### Option A: Merge, carrying all write fields

`from_json` cannot populate `kb_clauses` / `profiler_data` / `metrics`, so a loaded object comes back **half-populated**. `.metrics` on a loaded result would be `None` — a silent footgun sitting exactly where `kb_comparator` lives. A wide object full of `None`s replaces a narrow object that is complete.

### Option B: Merge, dropping the write-only fields

The runner loses `kb_clauses` and `metrics`, which `cross_validation` consumes. Breaks the write path to tidy the read path.

### Option C: A shared mixin for the six overlapping field names

Carries no behaviour, adds a layer of indirection, and — worse — manufactures pressure to keep the two types in sync **when they should be free to diverge**. If the runner grows a metric, the loader has no business growing one.

### Option D: Leave them separate (chosen)

Costs: two dataclasses naming six common fields. That is the entire cost.

## Trade-off analysis

The decisive argument came from the T9 refactor that immediately preceded this. T9 rewrote the metrics **write** path — container, reducer, on-disk schema — and the byte-identical guarantee on `paper/tables/*` held **for free**, because `extract_results` and `result_loader` read raw JSON and never touch the write-side types.

> **That insulation is the read≠write wall. A merge would demolish it — re-importing precisely the coupling T9 had just removed.**

A read model that is narrower than the write model is not debt. It is a boundary, and boundaries are what let one side change without the other noticing.

## Consequences

**Easier**
- The write path (runner, metrics, CNF, profiler) can evolve without touching anything that reads a result file, and vice versa.
- A loaded `ConGenResultData` is **complete**: every field it has is populated. There is no "is this one of the fields that only exists after a live run?" question.

**Harder**
- Six field names live in two files. If the *shared* part of the schema changes, both must be updated — a real, small cost, and the only one.

**Non-obvious, on purpose**
- **Two dataclasses describing one JSON file is deliberate.** If you are here because you noticed them and reached for the refactor: that is what this ADR is for. The earlier branch made that merge; it was wrong for the reasons above.

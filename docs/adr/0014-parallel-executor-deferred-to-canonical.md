# ADR-0014: The parallel executor is deferred to the canonical repo — `FastDiagP`, `get_instance`, and `ProfilerMode.MULTI_PROCESS` are scaffolding, not dead code

**Status:** Accepted
**Date:** 2026-07-18
**Deciders:** Viet-Man Le
**Relates to:** ADR-0001 (rebuild from baseline — this keeps the port diff small), ADR-0003 (`profiling` is a top-level package that ports independently), ADR-0010 (roles are declared `@abstractmethod` — why `get_instance` on the base is a contract, not an accident)

## Context

The ABC-v2 redesign plan carried a final task, **T4 — "executor + rewrite FastDiagP"**: build a `ConsistencyExecutor` Protocol, a `ProcessExecutor` (shared `mp.Pool`), a `MemoizingExecutor` (in-flight dedup), rewrite `FastDiagP` to consume an injected executor, fix the speculative consistency-check double-count, and delete the now-dead `ProfilerMode`/multiprocess path.

A **separate, earlier decision** — `parallel-executor-roadmap-2026-06-22.md`, tagged *canonical* — had already ruled the opposite:

> *"The parallelism redesign of `ConsistencyExecutor` / `ProcessExecutor` / `FastDiagP` is **deferred to the canonical `explanation` repo, to be done AFTER migration**, not on the AcqMSS prototype."*

The two documents conflict. This ADR reconciles them: **the defer decision wins.** The T4 row of the plan had simply never been squared against the roadmap.

Evidence gathered on the redesign branch (`feat/redesign-abc-v2`, HEAD after T17) confirms the roadmap's premises still hold:

- **`executor.py` was never built** on this branch — there is no `ProcessExecutor`/`MemoizingExecutor` to finish.
- **`FastDiagP` is test-only** — exactly one consumer, `the canonical explanation repository's diagnosis tests`. No runner, app, or production diagnosis path uses it. Production diagnosis is serial `FastDiag` via the HSDAG labeler.
- **HSDAG is fully sequential** — one `self.labeler` instance, no node-level parallelism, no executor hook.
- **`IHSLabelable.get_instance` is 0-caller** repo-wide, and **`ProfilerMode.MULTI_PROCESS`** (the `Manager.dict` path in `profiling/core.py`) has no caller that passes `MULTI_PROCESS`.

The roadmap's reasons for deferring are unchanged and decisive: the real design is a **new capability, not a bug fix** (it replaces the bare `mp.Pool` with a custom executor carrying priority lanes, cooperative cancellation, and a subsumption/bitmask cache — research-grade); AcqMSS is a **validation sandbox about to be migrated**, so a large executor rewrite here inflates the port diff and the drift; there is **no production pressure** (nothing is slow because of this today); and parallelism should have **one home** — HSDAG and WipeOutR parallelization will also live in canonical, so the executor foundation should be built there once.

## Decision

**Do not build the executor in AcqMSS. Keep the parallelism scaffolding intact, and record here why it is not dead.**

1. **`FastDiagP` stays as-is** — raw `mp.Pool`, test-only. Not rewritten here.
2. **`IHSLabelable.get_instance` stays** — it is `@abstractmethod` on the base (ADR-0010: a declared role), implemented by all four labelers. Its docstring states its purpose: *"create a new instance of this labeler with a different checker … when HSDAG needs multiple labeler instances (e.g. for parallelization)."* It is the **labeler-level counterpart of `checker.copy()`** (`CopyableChecker`), which already runs inside FastDiagP. It is 0-caller only because its driver — parallel HSDAG — is the deferred work.
3. **`ProfilerMode.MULTI_PROCESS` + the `Manager.dict` path stay** — the multi-process profiling support the parallel workers will need.

All three are **halves of one coherent parallel design whose other halves either run today (`checker.copy()`) or get built in canonical (the executor, HSDAG/WipeOutR node-parallelism).** Deleting any of them now does not remove a feature; it forces canonical to rebuild half a design. **"0 caller" is a question — "why has no one called it yet?" — and here the answer is "its consumer is built in the canonical repo," not "it is dead."** This is the same trap the redesign hit repeatedly (`get_instance` itself was misread as dead three times in one session); the ADR is the standing answer so the next tidy-up does not re-litigate it.

## Options considered

### Option A: build the executor in AcqMSS (the plan's original T4)
Rejected. Inflates the port diff of a sandbox that is about to be migrated; builds a research-grade executor (priority scheduling, subsumption cache, cooperative cancellation) in the wrong home; serves a test-only algorithm under no production pressure. Directly contradicts the 2026-06-22 defer decision without new justification.

### Option B: defer the executor **and delete** the scaffolding (`get_instance`, `ProfilerMode.MULTI_PROCESS`)
Rejected. Canonical would immediately rebuild what was deleted. Worse, deleting one half of a design whose other half is running (`checker.copy()`) is exactly the "0-caller ⇒ dead" over-reach this project has been bitten by. Cheaper to keep a documented, guarded stub than to re-derive it.

### Option C: defer the executor, **keep** the scaffolding, guard it, and record why (chosen)
The scaffolding ports to canonical ready to use; a lightweight guard plus this ADR stop a future `tech-debt` sweep from deleting it. T4 in AcqMSS collapses to this ADR + the guard — the redesign's code work is essentially complete after T17.

## Consequences

**Easier**
- The port diff stays small — the whole point of the prototype (ADR-0001).
- Whoever ports `explanation/` to canonical inherits the parallel scaffolding and the design input (`parallel-executor-roadmap-2026-06-22.md`) together, and builds the executor once, in one home.

**Harder / carried debt**
- **FastDiagP's speculative-CC double-count bug is not fixed here** (the lookahead submits a CC and the main path may re-derive it; worker-process profiler increments are lost). It affects only **test-only** profiler metrics under no production use, and is fixed in canonical when the `MemoizingExecutor` in-flight dedup lands. Recorded so it is not mistaken for a live-path defect.
- Three 0-caller / test-only artifacts remain in the tree. Mitigated by the guard below and by this ADR.

**Guarded**
- `test_parallel_scaffolding_is_intentional` (or equivalent) — asserts `get_instance` is `@abstractmethod` on `IHSLabelable` and present on all four labelers, and that `ProfilerMode.MULTI_PROCESS` exists — with a comment pointing here. A guard enforces *that* the scaffolding stays; this ADR explains *why*.

## What this ADR does not touch

- **The canonical executor design itself** lives in `parallel-executor-roadmap-2026-06-22.md` (priority lanes, subsumption bitmask cache from the paper's importance values, cooperative cancellation, `n_workers` on the Protocol, batch/gather). That note is the design input to carry across; nothing in it is decided or discarded here.
- The roadmap's small AcqMSS-sanctioned cleanups are already resolved: **Q2** (merge preparation strategies) landed in T11b; **Q7** (dead field `counter_readyCC`) landed in T17; **Q1** (`PreparationOutput.task` typed too narrowly) is moot — that type no longer exists after the T3/T11b preparation restructure.

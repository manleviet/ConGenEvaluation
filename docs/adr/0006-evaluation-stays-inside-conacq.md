# ADR-0006: `evaluation` stays inside `conacq` — it is not the next `profiling`

**Status:** Accepted
**Date:** 2026-07-11
**Deciders:** Viet-Man Le

## Context

`conacq/eval/` is large — **2880 LOC across 12 modules**, roughly a quarter of the application. Having just promoted `profiling` to a top-level package (ADR-0003), the obvious next question is whether `eval` deserves the same treatment. It has a symptom that suggests it might: a **circular import** with `conacq/runners/`, worked around by a deferred import inside a function body (`base_runner.py`).

Reading it revealed that `conacq/eval/` is really **two different concerns wearing one name**:

**(A) Evaluating the quality of a learned KB** — this is the real evaluation, and it is fine:
`kb_comparator` (description / clause / semantic strategies) · `semantic_equivalence` (bidirectional SAT entailment) · `accuracy` + `metrics` (TP/TN/FP/FN) · `cross_validation` + `folds` · `progressive_evaluation` (ConGen at successive query budgets) · `result_loader` · `report`. Two of these (`cross_validation`, `progressive_evaluation`) *drive* runners repeatedly — that is a harness, and it is the correct layer for it.

**(B) A performance-metrics container that is in the wrong place and badly built** — `performance_metrics.py` (652 LOC):
- `PerformanceMetrics`: ~29 hardcoded fields — 5 core, 8 ConGen, 16 QuAcq. The QuAcq fields sit inside the ConGen container defaulting to zero, with a comment explaining that this keeps "the ConGen path unaffected".
- `AggregatedPerformanceMetrics`: ~100 hardcoded fields — every metric spelled out four times (`_mean`, `_std`, `_min`, `_max`).
- `to_dict()` hand-written (~170 lines); `aggregate_metrics()` hand-written (~195 lines).
- Net effect: **adding one metric means editing ~10 places**, and forgetting one line of `to_dict` silently drops the metric from the JSON export.

And the irony: `profiling` (ADR-0003) already collects metrics **generically**, in a dict, with `increment` / `record_time` / `set_gauge`. `PerformanceMetrics` flattens that dict into hardcoded fields, discarding the generality.

The circular import is a symptom of (B), not of (A): **`runners` imports `eval` for exactly one thing — `PerformanceMetrics`.** Everything else flows one way (`eval` → `runners`/`oracle`/`bias`; `apps` → `eval`).

## Decision

**`evaluation` does not become a top-level package. Instead:**

1. **Move the metrics container out of `eval` into `conacq/runners/`.** It is the *output a runner produces*, not the *evaluation that consumes runs*. This removes the only `runners → eval` edge — the cycle dies **structurally**, not by a deferred import.
2. **Rebuild the container**: dict-backed, with a declarative spec; `to_dict()` *is* the dict; aggregation becomes **one generic reducer** (`{key: {mean, std, min, max}}`); the metric map is **declared per algorithm**, so QuAcq stops injecting zeroed fields into ConGen's container and a third algorithm costs nobody anything.
3. **Add a guard rule** (extending ADR-0002 to inside `conacq`): `conacq.{runners, algorithms, models, oracle, bias, examples}` **must not import** `conacq.eval`. This declares `eval` a layer of its own and enforces it — **without moving a single file**.
4. `conacq/config.py` moves to `conacq/config.py`: it holds `ModelConfig` / `load_pipeline_config`, which six `apps/` scripts use. It is application configuration, not evaluation.

Hard constraint throughout: **the on-disk export is frozen.** `data/results/**` must stay `from_json`-readable and CSV/LaTeX byte-identical — the paper pipeline reads them. So the dict must serialise with the same key names in the same order, which means an explicit ordered key list per algorithm, generated from the same declaration. The safety net is a **golden-file test written before the refactor**.

## Options considered

### Option A: Extract a top-level `evaluation/` package, mirroring `profiling`

| Dimension | Assessment |
|---|---|
| Portability gain | **None.** Unlike `profiling` (stdlib-only leaf, reusable anywhere), `evaluation` depends on `conacq` — its result types, oracle, bias. It would sit *above* `conacq`, not beside it |
| Churn | ~20 import sites (6 apps, 2 test files, the runners) |
| Cycle | Fixed — but the move only *forces* the one-way dependency that step 1 above achieves anyway |
| Verdict | Rejected for now: the benefit is aesthetic, the cost is real |

### Option B: Fix the cycle in place + declare the layer with a guard rule (chosen)

| Dimension | Assessment |
|---|---|
| Churn | Near zero — one file moves, one guard rule added |
| Cycle | Dies structurally (the only offending edge is removed) |
| Layer boundary | **Enforced**, by the same AST-guard mechanism as the package boundaries |
| Verdict | ~90% of the benefit at ~0% of the cost |

## Trade-off analysis

The instinct "`profiling` was extracted, so extract `evaluation` too" is wrong, and it is worth writing down *why*, because it will recur:

> **`profiling` is a leaf: stdlib-only, depended on by everything, depending on nothing. Extracting a leaf buys real portability.
> `evaluation` is a ceiling: it depends on `conacq`'s result types, oracle and bias. Extracting a ceiling buys nothing but a directory rename.**

The value in this area is almost entirely in (a) putting the metrics container where it belongs and rebuilding it, and (b) making the layer boundary executable. Neither requires a new top-level package.

## Consequences

**Easier**
- Adding a metric becomes a one-line declaration instead of a ten-place edit; the JSON export can no longer silently lose a field.
- A third algorithm adds zero dead fields to the other two.
- The `runners ↔ eval` cycle cannot come back — the guard fails if it does.

**Harder**
- The frozen on-disk format constrains the new container: key order and key names must be preserved exactly. This is a real constraint, and the golden-file test must be written *first*.

**To revisit**
- The physical extraction of `evaluation/` to top level is deliberately left available. Once the container has moved and the guard rule is in place, it is a `git mv` plus ~20 imports, and the layering it would express (`apps → evaluation → conacq → explanation → profiling`) is already true. Do it only if the directory boundary starts earning its keep on its own.

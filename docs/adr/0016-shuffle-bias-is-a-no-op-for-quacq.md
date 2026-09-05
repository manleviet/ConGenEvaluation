# ADR-0016: `shuffle_bias` is a no-op for QuAcq — the bias order is discarded by `set(set_c)`, and restoring it changes the golden tables

**Status:** Accepted — implemented and committed on `feat/redesign-abc-v2`. B2 also moves the paper's iterative tables (`quacq.py:140` runs in example mode too), which are regenerated once with the B1+B2+B3 bundle at the ConGen revision — this is **not** a "0 paper impact" change.
**Date:** 2026-07-19
**Deciders:** Viet-Man Le
**Relates to:** ADR-0015 (the sibling determinism defect on the example path), ADR-0001 (behaviour held identical to `main`)

## Context

`conacq/algorithms/quacq/quacq.py:140`, at the top of the QuAcq run loop:

```python
# Local mutable state
remaining_bias = set(set_c)
```

`set_c` is the bias constraint assumption-id sequence — the order a `shuffle_bias`-style knob is meant to control. Converting it to a `set` immediately **discards that order**: the loop `while remaining_bias:` iterates in set-iteration order (hash order), and the whole point of shuffling the bias is lost. The `shuffle_bias` knob is therefore **inert for QuAcq** — turning it on or off changes nothing.

The golden tables stay green today only because integer-set iteration is **deterministic per build**, so the discarded order is replaced by a *stable* one. The defect is "the experiment knob does nothing", not "the results flicker".

**The knob is genuinely wired — QuAcq is *meant* to depend on bias order.** The QuAcq runner already shuffles `task.set_c` under `shuffle_seed`, byte-for-byte the same as the ConGen runner:

```python
# conacq/runners/quacq_runner.py   (≈ conacq/runners/congen_runner.py, identical)
if shuffle_seed is not None:
    shuffled_set_c = list(task.set_c)
    random.Random(shuffle_seed).shuffle(shuffled_set_c)
    task = replace(task, set_c=shuffled_set_c)
```

So the runner hands QuAcq an already-shuffled `set_c`, and `quacq.py:140` then throws that order away with `set(...)`. This settles the earlier open question: bias order is a real, intended experimental input for QuAcq (same mechanism as ConGen), not an accident — so the fix is to **honor** the order, not to delete the knob.

## Why this is blocked (not a Group-A refactor)

The fix — keep a list for iteration order and use a set only for O(1) membership — **restores** the bias order into the loop. That changes the sequence in which constraints are queried/tested → changes the KB QuAcq learns → changes the accuracy and KB-size metrics → **changes the QuAcq golden tables**. There is no behaviour-inert version of this change; it is a behaviour change by construction.

## Decision (proposed)

Record the defect and **gate the fix behind a golden regeneration**. Do not "quietly" rewrite line 140 as if it were a cleanup — it is a results-affecting change.

When approved, the fix is:

```python
remaining_bias = list(set_c)          # preserve (shuffled) order for iteration
remaining_bias_set = set(set_c)       # O(1) membership for removals
```

with every `remaining_bias` membership/removal site updated to keep the list and set in sync, and the iteration reading the list.

## Options considered

### Option A — restore bias order and honor the (already-wired) shuffle — **CHOSEN**
Makes the knob real: the runner-shuffled order actually drives QuAcq. Requires regenerating the QuAcq golden tables and re-validating the paper's QuAcq numbers. Chosen because the runner evidence above shows QuAcq is *designed* to consume the shuffled order.

### Option B — remove `shuffle_bias` as a knob and document QuAcq as order-insensitive
Rejected: the runner shuffles `set_c` exactly like ConGen, so order is an intended input, not dead scaffolding. Deleting the knob would contradict the wired behaviour.

### Option C — status quo
Rejected as a silent trap: a future reader will "fix" the `set()` and unknowingly move the golden numbers.

## Implementation contract (deferred — executes on a separate, gated command)

The fix at `quacq.py:140` (and its `remaining_bias` removal sites) preserves the runner-supplied order — an ordered list for iteration, a set only for O(1) membership — adding/removing **no** knob. When the gated command runs, it MUST satisfy:

1. **Prove the knob now has teeth.** Add/point to a test showing: same `shuffle_seed` → identical constraint-test order (reproducible); two *different* seeds → *different* order (before the fix both were identical because hash order erased the seed). If two seeds can't be distinguished, the fix has not taken.
2. **Regenerate golden, itemized.** List exactly which golden file(s) changed and how many cells/rows moved; for each, show the move is caused by the reorder (not a new bug). This itemization is a review artifact, produced *before* commit.
3. **No collateral regression.** The rest of the suite (outside the regenerated QuAcq golden) stays green.
4. **Close the loop.** Flip this ADR's status note to record which golden was regenerated, and add a paper-regen note that the QuAcq numbers changed vs the old draft.

## What must be regenerated

- **Golden:** QuAcq golden tables (accuracy, learned-KB size, and any per-query trajectory pins).
- **Paper:** the QuAcq results columns/tables.
- AcqMSS/ConGen tables are **not** touched by this change (ADR-0017 is the separate AcqMSS/ConGen reorder).
- Seed source ties into ADR-0015 so the regenerated tables are themselves reproducible.

## Implemented (2026-07-19)

Fix: `quacq.py:140` `set(set_c)` → `dict.fromkeys(set_c)` (insertion-ordered membership: iteration follows the runner's shuffled `set_c`; O(1) `in`/`pop`). Mutation sites updated: `sat_utils.py:40` `-= set(pruned)` → per-id `pop`; `quacq.py:230/239`, `findc.py:135` `.discard` → `.pop(x, None)`. Consumer annotations `remaining_bias: set` → `dict` (findscope/findc/sat_utils/quacq_model/query_provider).

- **Knob-has-teeth guard:** `test_bias_order_drives_quacq_query_trajectory` — same order → reproducible trajectory; two different shuffles → different trajectories. Verified red-first: reverting line 140 to `set()` makes it **fail** (both orders collapse to one hash order), restoring makes it pass. Not a tautology.
- **In-repo golden regenerated:** `tests/fixtures/t11_oracle_net/layer23_prepared_and_e2e.json` — **only** `.layer3.quacq.query_history` changed (via `record_layer2_layer3()`; ConGen keys + prepared-task IDs byte-unchanged). The terminal invariants held: `n_kb=0`, `n_queries=15`, `convergence_reason=max_queries`, `kb_assumption_ids=[]`. Only the exploration *path* differs — the intended effect of honoring the bias order.
- **`test_quacq.py` needed no change** — every hard KB pin there is a synthetic `QuAcqResult(...)` literal (data-structure tests), not a `learn()` output; the `learn()` tests use structural asserts. (This corrects the earlier "regen test_quacq.py pins" expectation.)
- **Paper impact is NOT zero.** `quacq.py:140` runs *before* the mode branch, so it also affects `example_only`/`example_first`. The paper's iterative tables (`tab:iterative_*` in `paper/evaluation.tex`, from `data/results/interactive/`) run through this line and therefore move — but they sit under B1+B2+B3 and are **deferred to the single B1 bundle regen at paper-writing** (regenerating them now would bake in the still-unseeded example order). This ADR does **not** claim "0 paper impact".
- **Suite:** 507 passed (506 + the knob guard). Not committed; awaiting golden-diff review.

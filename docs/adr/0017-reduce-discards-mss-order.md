# ADR-0017: REDUCE discards the MSS ordering through `set()` — restoring it changes which redundant constraint survives, and the golden tables

**Status:** Accepted — code and in-repo goldens committed. The passive-ConGen cross-validation regen this ADR gated has since been run: its output is the acquisition tree this artifact ships, `data/results_sosym_r1/congen`.
**Date:** 2026-07-19
**Deciders:** Viet-Man Le
**Relates to:** ADR-0016 (the sibling `set()`-drops-order defect in QuAcq), ADR-0001 (behaviour held identical to `main`)

## Context

`conacq/algorithms/acqmss/reduce.py:63`, forming the KB that REDUCE minimizes:

```python
# KB ← B' ∪ NE
kb = list(set(set_b_prime) | set(set_neg_tv))
```

AcqMSS produces its KB as an ordered `gamma1 + gamma2` (`set_b_prime` then `set_neg_tv`). Wrapping both in `set()` and unioning **discards that order**; `kb` is then iterated (`for c in kb:`) in hash order. When two constraints are **mutually redundant**, REDUCE keeps whichever it reaches first — so *which representative survives* depends on the discarded order. That can move `n_kb`, `kb_reduction_ratio`, and the TP/FP split.

As with ADR-0016, the golden tables are green today only because integer-set iteration is deterministic per build — a stable substitute for the intended order, not the intended order itself.

## Why this is blocked (not a Group-A refactor)

The fix — preserve `gamma1 + gamma2` order while de-duplicating — changes which mutually-redundant constraint is removed → changes the reduced KB → changes `n_kb` / `kb_reduction_ratio` / TP / FP → **changes the AcqMSS golden tables**. It is a behaviour change by construction; there is no behaviour-inert form.

## Decision (proposed)

Record the defect and **gate the fix behind a golden regeneration.** Do not rewrite line 63 as a cleanup.

When approved, the fix preserves order with a first-occurrence dedup, e.g.:

```python
# KB ← B' ∪ NE, preserving AcqMSS's gamma1+gamma2 order
kb = list(dict.fromkeys(list(set_b_prime) + list(set_neg_tv)))
```

(`dict.fromkeys` keeps first occurrence and insertion order; the two `set()`s only ever provided membership dedup, which this preserves.)

## Options considered

### Option A — preserve `gamma1 + gamma2` order — **CHOSEN**
Makes the surviving-representative choice deterministic *and* faithful to the algorithm's stated ordering. Requires regenerating the AcqMSS golden tables and re-validating the paper's AcqMSS numbers.

### Option B — status quo
Rejected as a silent trap: the current numbers depend on Python's hash-iteration order of ints, which is stable per build but is not the algorithm's defined semantics; a future reader "tidying" the `set()` would move the golden numbers unknowingly.

## Sequencing: run separately from ADR-0016

Although ADR-0016 and ADR-0017 are both "`set()` drops order" in the same conacq layer, they are implemented and regenerated **as two separate, gated commits — B2 (0016) first, then B3 (0017)** — so each golden diff maps to exactly one code change and is reviewable in isolation.

## Implementation contract (deferred — executes on a separate, gated command, after ADR-0016)

The fix at `reduce.py:63` preserves the `gamma1 + gamma2` appearance order while de-duplicating (`dict.fromkeys(list(set_b_prime) + list(set_neg_tv))`, or an equivalent seen-set), never routing through `set()`. When the gated command runs, it MUST satisfy:

1. **Prove the reorder now bites.** Add/point to a test showing the surviving redundant representative follows `gamma1+gamma2` order deterministically, distinguishable from the old hash-order outcome (if it can't be distinguished, the fix has not taken).
2. **Regenerate golden, itemized.** List exactly which golden file(s) changed and how many `n_kb` / `kb_reduction_ratio` / TP / FP cells moved; for each, show the move is caused by the reorder, not a new bug — a review artifact produced *before* commit.
3. **No collateral regression.** The rest of the suite (outside the regenerated AcqMSS/ConGen golden) stays green.
4. **Close the loop.** Record here which golden was regenerated, and note that the AcqMSS/ConGen results have to be regenerated rather than re-extracted.

## What must be regenerated

- **Golden:** AcqMSS / ConGen golden tables — `n_kb`, `kb_reduction_ratio`, and TP/FP-derived metrics.
- **Paper:** the AcqMSS results tables that report KB size / reduction ratio / precision-recall.
- QuAcq-only tables are unaffected (ADR-0016 handles those separately).

## Implemented (2026-07-19)

Fix: `reduce.py:63` `list(set(set_b_prime) | set(set_neg_tv))` → `list(dict.fromkeys(list(set_b_prime) + list(set_neg_tv)))` — dedup preserving the `gamma1+gamma2` appearance order, never through `set()`.

- **Knob-has-teeth guard:** `TestReduce::test_reduce_survivor_follows_input_order` — three mutually-redundant constraints; the survivor is the last one reached, so two different input orders keep different survivors. Verified red-first: reverting line 63 to `list(set(...))` makes it **fail** (both orders collapse to one hash order), restoring makes it pass.
- **In-repo goldens regenerated (fast, in-process):**
  - `layer23_prepared_and_e2e.json` — `.layer3.congen_rs` and `.layer3.congen_ff`: `n_kb` (17→14, 18→16) and `kb_assumption_ids` (different membership) changed; **`n_mss` (78/102), `n_bias`, and prepared-task IDs UNCHANGED** (`n_mss` is pre-reduce). The QuAcq arm is untouched by B3 (QuAcq learns an empty KB on REAL-FM-7 → `reduce([])→[]`).
  - `congen_runner.json` — `seed_none`/`seed_42`: `kb_constraints`/`kb_clauses`/`n_kb`/`redundant_constraints` changed; **`n_mss`, `n_bias`, `bg_clauses`, `consistency_checks`, and all pinned counts UNCHANGED** (reduce still does the same number of checks, keeps different survivors). Regenerated deliberately — this is an ADR-gated behaviour change, not the unintended `run()` drift the golden's "do not regenerate" warning targets.
- **`test_quacq.py` needs no change** — its KB pins are synthetic `QuAcqResult(...)` literals (same as ADR-0016), and QuAcq's REAL-FM-7 KB is empty, so B3 is a no-op there.
- **Suite:** 508 passed. Not committed.

### Passive-ConGen cross-validation regen — done

B3 changes ConGen's learned knowledge base, so every passive result had to be
recomputed rather than re-extracted. That regen was run: `data/results_sosym_r1/congen`
holds its output, one file per (knowledge base, sampling) unit, and every table in the
paper is computed from it by `reproduce_tables_sosym.sh`.

Re-running it is a multi-hour pipeline and is deliberately not wired into that script —
the acquisition results are committed evidence, not a table input. One cell at a time is
cheap and is what the README documents; `data/results_sosym/configs/` holds a generated
config per cell.

# ADR-0017: REDUCE discards the MSS ordering through `set()` — restoring it changes which redundant constraint survives, and the golden tables

**Status:** Accepted — code + in-repo goldens committed on `feat/redesign-abc-v2`. The passive-ConGen CV regen (`data/results/congen` → t9 golden → paper Tables 7/9/10/11) is a multi-hour pipeline run **pending the ConGen revision**; the byte-identical extraction test is skipped (loud, not green) until then. Tracked in an internal effort log, not shipped.
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
4. **Close the loop.** Record here which golden was regenerated, and add a paper-regen note that the AcqMSS/ConGen numbers changed vs the old draft.

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

### Passive-ConGen CV regen — PENDING (multi-hour pipeline)

The paper's passive tables come from `data/results/congen/*.json` (19 committed CV files) via `apps.extract_results`; the t9 byte-frozen golden (`tests/resources/t9_extraction_golden/`) re-extracts that same frozen data. B3 changes ConGen's learned KB, so these must be regenerated by **re-running the CV pipeline**, then re-extracting:

```
# per FM group enabled in the config (edit [[models]] to uncomment each FM):
PYTHONPATH=. python -m apps.run_cv apps/conf/run_cv_config.toml            # writes data/results/congen/*
PYTHONPATH=. python -m apps.extract_results apps/conf/extract_results_config.toml   # -> paper/tables/* + refresh t9 golden
```

Canonical config: `apps/conf/run_cv_config.toml` (`algorithm=congen`, `n_folds=3`, `seed=42`, `shuffle_bias=true`). **Not run inline:** REAL-FM-4 alone is ~734 s/cell × 3 folds, and the full 4-FM set is multi-hour. `data/results/interactive/` is **out of scope** here (B1 bundle).

Because re-extracting the still-stale `data/results/congen` against the still-stale golden would pass while proving nothing, `test_extraction_tables_are_byte_identical` (`tests/test_t9_metrics_safety_net.py`) is **skipped loud** (`@pytest.mark.skip`, reason cites this ADR) rather than left green — so the pending regen stays visible. After the CV regen: refresh the t9 golden + paper tables, **remove the skip**, and confirm the extraction is byte-identical to the *new* golden. The schema/parse t9 tests (incl. `test_extract_handles_mixed_old_and_new_schema`) are B3-independent and stay active. Checklist: an internal effort log, not shipped.

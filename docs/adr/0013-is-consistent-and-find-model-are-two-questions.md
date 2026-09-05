# ADR-0013: `is_consistent` and `find_model` are two questions — split the port

**Status:** Accepted
**Date:** 2026-07-17
**Deciders:** Viet-Man Le
**Relates to:** ADR-0009 (the oracle answers, it does not provision — same "one method, one question" shape), ADR-0011 (completion bypasses the checker port)

## Context

The incremental checker's `is_consistent(set_c)` was doing two jobs at once, and paying for the second on every call to the first.

Every candidate constraint in the bias is encoded with a **guard assumption**: `set_kb` carries `[-a, literal]` = `(¬a ∨ literal)` = **`a → literal`**. This is a **one-directional** activation: asserting `a` turns the constraint on; not asserting it lets the solver set `a = false`, which satisfies the clause trivially and leaves the constraint off.

`is_consistent` computed, on **every call**:

```python
enabled, disabled = self._compute_delta(set_c)          # disabled ≈ 617 of ~620
final = list(enabled) + [-1 * item for item in disabled] # build 617 negative ints
return self.solver.solve(assumptions=final)
```

For a REAL-FM-7 run: `assumptions ≈ 620` (≈310 bias candidates × 2), `enabled ≈ 3`, `disabled ≈ 617`. At **4489 calls/run that is ~2.8 million throwaway ints** — measured at **~60% of `run()`** (perf_counter, not cProfile, which inflates Python ~13×). The SAT solver itself is ~7%.

**The 617 negatives do not change the SAT answer.** Because the guard is one-directional, `solve([enabled])` and `solve([enabled] + [¬a for disabled])` return the *same* SAT/UNSAT — the unasserted guards default off either way. Verified across glucose3, glucose4, minisat22, cadical153.

Measured, dropping the negatives from the answer path:

```
ConGenRunner.run(), REAL-FM-7, incremental
  before : 950 ms   after : 226 ms   =  4.2×
  n_kb=17 · consistency_checks=536 · is_consistent_calls=4489 — byte-identical
```

Noise band ~16% before / ~3% after; **the 4.2× dwarfs the noise** — this is a real effect, unlike the tuple question (ADR-0012), which was always sub-noise. This is the redesign's **first measurable runtime win**; everything before it was structural.

### But the negatives are load-bearing for the model

Two call sites read the model right after the check (`query_provider`, `discriminating_generator`, both QuAcq):

```python
if checker.is_consistent(x):
    model = checker.get_model()      # QuAcq needs the assignment
```

**Drop the negatives and the model can change.** Without `¬a`, the solver is free to set `a = true`, and `(¬a ∨ literal)` then **forces `literal`** — pinning a variable the query did not intend to constrain.

```
KB = [[-10,1],[-11,-1],[2,3]]   solve([]), read model:
  glucose3   : a10=-10  x=-1   (guard off, x free)
  cadical153 : a10= 10  x= 1   ← guard ON, x forced — DIFFERENT model
```

glucose's default-false polarity *happens* to leave the guards off; **cadical does not**. And the divergence is **formula-dependent** (the same KB without `[2,3]` leaves cadical false too). So "the model is fine without the negatives" is a **coincidence of the solver and the formula, not an invariant** — exactly the failure shape ADR-0009 named: *"the defusing mechanism is a coincidence, not an invariant."* A test written under glucose would be **green and wrong**.

## Decision

**Split the port. One method, one question.**

```python
def is_consistent(self, set_c) -> bool:               # the answer — drop the negatives
    enabled, _ = self._compute_delta(set_c)
    return self.solver.solve(assumptions=list(enabled))

def find_model(self, set_c) -> Optional[List[int]]:   # the model — keep the negatives
    enabled, disabled = self._compute_delta(set_c)
    final = list(enabled) + [-1 * item for item in disabled]
    return self.solver.get_model() if self.solver.solve(assumptions=final) else None
```

`get_model()` **leaves the port**. The two QuAcq callers become `m = find_model(x); if m is not None:`. Every other `is_consistent` call — thousands, in the recursive diagnosis algorithms — takes the fast path.

The rule *"reading a model requires pinning the guards"* is now **enforced by the signature**, not by a comment someone will delete. And the stateful `is_consistent`-then-`get_model` ordering hazard is gone: there is no separate `get_model` to call out of order.

## Options considered

### Option A: split into `is_consistent` + `find_model` (chosen)
| Dimension | Assessment |
|---|---|
| Answer path | ~620 → ~3 assumptions ⇒ **4.2× on `run()`** |
| Model correctness | `find_model` keeps the negatives ⇒ pinned under **both** glucose and cadical |
| Enforcement | signature-level — you cannot get a model without the pinning path |
| Cost | 2 call sites updated; `get_model` removed from protocol + base + 3 backends |

### Option B: keep one method, drop the negatives, re-pin lazily inside `get_model`
Rejected — `get_model` reads the *last* solve's model; to re-pin it would have to re-solve with the full assumptions, i.e. pay the 617 cost anyway, plus a second solve. No saving, more complexity.

### Option C: keep the negatives everywhere (status quo)
Rejected — pays the 4.2× tax on thousands of answer-only calls to serve two model-reading calls.

### Option D: drop the negatives everywhere, accept the model as-is
Rejected — **green under glucose, wrong under cadical.** Trades a permanent, solver-dependent correctness bug for a 4.2× that Option A already captures safely.

## Consequences

**Easier**
- `run()` is **4.2× faster** on the incremental path — the number the papers report.
- The model contract is explicit: `find_model` is the only door to a model, and it pins the guards.

**Harder**
- Two methods where there was one. But they answer two genuinely different questions, and conflating them was the cost.

**Guarded**
- `test_find_model_keeps_guards_pinned_under_glucose_and_cadical` — **parametrized on both solvers**, and it has teeth: dropping the negatives makes cadical set the guard `true`; the test fails without the pin. **glucose alone would not catch it** — the net exists specifically because the safe-looking solver hides the bug.
- 8-algorithm md5 identity (`test_diagnosis` exact-string asserts), ConGenRunner + Layer goldens, `git diff tests/fixtures/ data/results/` = 0. The split changes the *execution path*, never the *result*.

## What this ADR does not touch

- `oracle/fm/oracle.py` uses a **raw** `Solver().get_model()`, not the checker port (ADR-0011 territory) — untouched.
- Non-incremental and SAT4J backends split the same way for parity, though they are test-only.

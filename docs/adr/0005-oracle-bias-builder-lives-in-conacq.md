# ADR-0005: `OracleBiasModelBuilder` lives in `conacq`, not in `explanation`

**Status:** Accepted
**Date:** 2026-07-11
**Deciders:** Viet-Man Le

## Context

`ConGenModelBuilder` (162 LOC) and `QuAcqModelBuilder` (85 LOC) were copies of each other. Both carried the same fields (`_bias_path`, `_oracle`, `_use_incremental`), the same fluent API (`from_bias`, `with_oracle`, `use_incremental`), the same validation — and, critically, the same **build body**:

```python
next_tseitin_var = self._oracle.get_bg_data().next_available_id
for key, clauses in model.constraint_map.items():
    neg_clauses, next_tseitin_var = negate_cnf_tseitin(clauses, next_tseitin_var)
    model.negated_constraint_map[f"NOT({key})"] = neg_clauses
model.next_available_id = next_tseitin_var
```

Those six lines are **the hand-off point of the assumption-ID space** from the oracle to the acquisition algorithm. This repository has already been bitten twice by bugs at exactly this seam (`plans/260218-1055-fix-assumption-id-mismatch/`, `plans/260226-1646-fix-bg-assumption-bug/`). Two copies of an ID-allocating loop is the recipe for producing a third: fix one, forget the other.

Factoring the shared skeleton out is obviously right. **Where to put it** is the decision.

The earlier redesign branch put it in `explanation/` — with the framework's other builders. It looked natural. It is also a framework file that does `from conacq.bias import BiasIO` and is typed against the `conacq` class `FeatureModelOracle`.

## Decision

**Two tiers, split along the package boundary (ADR-0002):**

| Class | Package | Knows about |
|---|---|---|
| `AbstractModelBuilder` | **`explanation`** (framework) | Nothing but the build template: `build()` = `_validate()` → `_create_model()`, plus the two abstract hooks. Zero references to `conacq` |
| `OracleBiasModelBuilder` | **`conacq`** (application) | Bias files, oracles, the Tseitin/ID hand-off. Inherits `AbstractModelBuilder` through the single public door, `explanation.api` |
| `ConGenModelBuilder`, `QuAcqModelBuilder` | `conacq` | Two hooks each: which model class to instantiate, what to do after negation |

Result: `QuAcqModelBuilder` shrank **85 → 37 LOC** (two hooks and a docstring); `ConGenModelBuilder` **162 → 112**.

## Options considered

### Option A: Put the shared builder in `explanation` (what the old branch did)

| Dimension | Assessment |
|---|---|
| Feels natural? | Yes — it sits with the other builders |
| Guard rule 4 (`explanation` never imports `conacq`) | **Violated.** It imports `conacq.bias` and is typed against `FeatureModelOracle` |
| Consequence | The framework can no longer be extracted; it now knows what a bias and an oracle are |

### Option B: Two tiers — neutral template in the framework, bias/oracle tier in the application (chosen)

| Dimension | Assessment |
|---|---|
| Guard | Clean — the framework base has zero `conacq` references |
| Duplication | Removed where it mattered: **one** copy of the ID hand-off |
| Cost | One extra class |

### Option C: Composition instead of inheritance — a free function `build_oracle_bias_model(bias_path, oracle, make_model, post_build)`

| Dimension | Assessment |
|---|---|
| Duplication of *logic* | Removed |
| Duplication of *API* | **Returns** — each builder must re-declare `from_bias`, `with_oracle`, `use_incremental` (3 setters × 2 builders) |
| Verdict | Rejected: what is shared here is a fluent API *and* a fixed lifecycle, not just an algorithm |

## Trade-off analysis

**On placement.** This is the case the boundary guard exists for. The builder *looks* like framework code; it *is* application code, because it is typed against application concepts. The guard turned an architectural principle into a failing test — the leak was not a matter of opinion, it was a red bar.

**On inheritance.** Elsewhere in this redesign, inheritance was deliberately *removed* (the `Task` family is plain frozen data; composition beats inheritance there — inheriting only to reuse fields buys nothing). Here it is deliberately *kept*, and the distinction is real:

- A `Task` is **data** → inheritance adds nothing.
- A builder is **behaviour with a fixed lifecycle** → this is Template Method: the base owns the invariant sequence, the subclass fills two variation points. That is what inheritance is for.

This is also **not** the bad pattern being removed elsewhere (`inherit-then-override`, where a subclass stubs out behaviour it inherited). No subclass here disables anything from the base.

## Consequences

**Easier**
- **One** place where the assumption-ID hand-off happens. The class of bug that hit this repo twice is now structurally unable to recur.
- Because there is exactly one such place, an `AssumptionIdAllocator` can later replace the raw-integer baton with a single change — with two copies, that refactor would not have been worth attempting.
- The framework stays extractable.

**Harder**
- Three levels of builder inheritance (`AbstractModelBuilder` → `OracleBiasModelBuilder` → `ConGen`/`QuAcq`). Shallow, but a reader must follow the chain to see the whole build.
- The framework base is currently typed with `Any` (it does not know what model type it builds); a `Generic[TModel]` parameterisation is scheduled.

**Non-obvious, on purpose**
- The builder writes to the model's private catalog fields (`_name_to_id`, `_id_to_name`). This is the *one* place the read-only views are bypassed, and it is sanctioned: builders are the intended populator, callers get `MappingProxyType`. Do not "fix" it by widening the model's public API.

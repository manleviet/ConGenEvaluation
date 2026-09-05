# ADR-0009: The oracle answers questions; it does not provision the algorithm

**Status:** Accepted
**Date:** 2026-07-12
**Deciders:** Viet-Man Le

## Context

`FeatureModelOracle` had fourteen public methods. Splitting its consumers into narrow role protocols (ADR-0004's principle, applied to the oracle) made the shape of the class impossible to miss — it was doing **two unrelated jobs**:

| Job | Protocols | Methods |
|---|---|---|
| **① Answer questions about the target** | `MembershipOracle`, `CompletableOracle`, `CatalogProvider` | `is_valid` · `complete_configuration` · `get_variables` · `get_variable_ids` |
| **② Provision the algorithm's inputs** | `BGProvider`, `KBProvider` | `get_bg_data` · `get_root_clauses` · `get_kb` · `get_assumptions` · `get_c` |

Job ① is what an oracle *is*, in constraint acquisition: the thing you ask. Job ② is **setup** — handing the algorithm the SAT encoding it needs before it can start. An oracle has no business doing that, and nothing about job ② requires an oracle to perform it.

**The two jobs were entangled through mutable state, and that entanglement was a bug.**

`is_valid()` (job ①) called `with_configuration()`, which rebound `self._task` so that `set_c` became `base_set_c + the assumptions of that query`. `get_c()` (job ②) then returned that — the background knowledge, polluted by whichever question happened to be asked last. `GenerateNE` reads `oracle.get_c()` **live** and hands it to QuickXPlain as the *background*, i.e. as facts assumed true. So the NE clause generated for a test case could depend on **which query was asked last** — non-determinism by state, silent, with no exception and no failing test.

It had never actually corrupted a result, but only because of two accidents: ConGen never calls `is_valid` (only QuAcq does), and each runner builds its own oracle, so QuAcq's pollution never reached ConGen's `GenerateNE`. **The defusing mechanism was a coincidence, not an invariant.** One obvious optimisation — *"the oracle is expensive to build, let's share it between QuAcq and ConGen"* — arms it.

## Decision

**Split the two jobs. The oracle answers; a frozen snapshot provisions.**

| | Holds | Nature |
|---|---|---|
| **`FMOracle`** | `is_valid` · `complete_configuration` · `get_variables` · `get_variable_ids` · `cleanup` | A live actor, owns a solver, answers queries |
| **`OracleData`** | `bg_data` · `root_clauses` · `kb` · `assumptions` · `c` | A **frozen** snapshot, built once, satisfies `BGProvider` + `KBProvider` |

Both are derived from the same `FMOracleModel`. The consumers of job ② — `GenerateNE`, the model builders, both task-preparation strategies — take **`OracleData`**, never the live oracle.

**Enforced by a guard:**

```python
assert not isinstance(FMOracle(...), KBProvider)
assert not isinstance(FMOracle(...), BGProvider)
```

If the oracle ever satisfies those again, job ② has leaked back in and the door to the next A6 is open.

## Options considered

### Option A: Fix the symptom — make `get_c()` compute locally instead of rebinding `self._task`

| Dimension | Assessment |
|---|---|
| Effort | Small |
| Fixes A6 | Yes |
| Fixes the **class** of bug | **No.** The oracle still owns mutable state that job ② reads live. The next method that rebinds `self._task` reopens the same hole, and nothing fails |

### Option B: Split the roles; job ② becomes a frozen snapshot (chosen)

| Dimension | Assessment |
|---|---|
| Effort | Larger — it lands with the oracle-purity work rather than as a one-line fix |
| Fixes A6 | Yes, **by construction**: the oracle cannot touch what it does not own |
| Fixes the class | **Yes.** With job ② frozen and job ① unable to reach it, "a query corrupts the background" is not expressible |
| Bonus | The expensive-to-build oracle *can* now be shared between algorithms — the very optimisation that would have armed A6 becomes safe |

## Trade-off analysis

Option A is the fix you write when you are looking at the bug. Option B is the fix you write when you ask *why the bug was possible*.

> **A6 was not a mistake in a line of code. It was the visible symptom of one object holding two jobs that should never have been able to see each other's state.** Repairing the line leaves the arrangement that produced it.

The narrow role protocols (T11.1) did not fix anything by themselves — but they made the two jobs *legible*, and once legible, the entanglement was obvious. That is what role protocols are for: they are a way of asking a class what it is actually doing.

## Consequences

**Easier**
- `GenerateNE` and the preparation strategies receive an immutable snapshot. There is no live object whose state a query can shift under them.
- The oracle becomes safely shareable across algorithms — including the QuAcq→ConGen pipeline, where sharing was previously a loaded gun.
- The guard (`not isinstance(FMOracle, KBProvider)`) states the boundary in one line and fails the day someone reopens it.

**Harder**
- `OracleData` must be built eagerly, at model-build time, rather than lazily on first request. That is the intended direction (a KB is immutable after build), but it means the build does slightly more work up front.

**Non-obvious, on purpose**
- **`FMOracle` deliberately does *not* expose `get_kb` / `get_assumptions` / `get_c`.** If you are here because a caller wants them from the oracle: it should take `OracleData` instead. Adding them back to the oracle re-creates the entanglement this ADR exists to remove.

## Related

- **Naming, decided alongside:** protocols use the **general** vocabulary of constraint acquisition — **`variables`**, not `features`. A feature model is one instantiation of the domain (and the one the evaluation happens to use); the protocols must not assume it. Hence `CatalogProvider.get_variable_ids()`, not `get_feature_ids()`. Feature-model-specific *implementations* may of course say `FM` (`FMOracle`, `FMData`).
- `FeatureModelOracle` → **`FMOracle`**, so the family reads uniformly: `FMOracle` / `FMOracleModel`, exactly as `ConGen` / `ConGenModel` and `QuAcq` / `QuAcqModel`. The old pair — one spelled out, one abbreviated — read as near-anagrams of each other.

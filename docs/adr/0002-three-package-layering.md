# ADR-0002: Three-package layering, enforced by an AST guard

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Viet-Man Le

## Context

The codebase has three kinds of code with genuinely different lifetimes and audiences:

- **`explanation/`** — the diagnosis/explanation *framework*: tasks, KB models, consistency checking, SAT operations, HSDAG. This is the part intended to be extracted and published as a flamapy plugin (`pysat_metamodel` / `flamapy-sat`), and it already exists in drifted copies inside three other research repos (AcqMSS, DiagEnergy, KBDiag).
- **`conacq/`** — the *application*: constraint-acquisition algorithms (ConGen, QuAcq), the feature-model oracle, the bias, runners, evaluation.
- **`profiling/`** — neutral measurement infrastructure (counters, timers, gauges).

If the framework is ever going to be published on its own, it must not know anything about the application. Nothing prevented that. A framework file importing `conacq.bias` compiles fine and passes the tests — the coupling is only discovered years later, when someone tries to extract the package and finds it will not come loose.

The old branch had exactly this leak: a bias/oracle-aware builder placed inside `explanation/` (see ADR-0005).

## Decision

**Three packages, a one-way dependency chain, and an executable guard:**

```
profiling  (leaf, stdlib only)  ←  explanation  (framework)  ←  conacq  (application)
```

Five rules, enforced by `tests/test_boundary_guard.py` (an AST scan of every import in the three packages):

1. `conacq` reaches `explanation` **only** through `explanation.api` — no deep imports into modules.
2. `conacq` reaches `profiling` **only** through the `profiling` facade — no deep imports.
3. `explanation` reaches `profiling` **only** through the `profiling` facade.
4. **`explanation` never imports `conacq`.** (The rule that keeps the framework extractable.)
5. **`profiling` imports neither** — it is a leaf: stdlib plus its own internals.

**One public door per package.** `explanation` has internals worth hiding, so its door is a curated `explanation/api.py` and its `__init__.py` is empty. `profiling` is small and entirely public, so its door is its `__init__.py`. The *rule* is symmetric (one door, no deep imports, guard-enforced); only the *mechanism* differs, and adding a `profiling/api.py` that re-exports everything would be ceremony.

## Options considered

### Option A: Convention only — document the layering, trust reviewers

| Dimension | Assessment |
|---|---|
| Cost | Zero |
| Reliability | Poor — a violating import is one line, passes all tests, and looks harmless in review |
| Failure mode | Silent. Discovered at extraction time, when it is expensive |

### Option B: Split into separate installable distributions immediately

| Dimension | Assessment |
|---|---|
| Cost | High — packaging, versioning, editable installs across three consuming repos, all before the design has settled |
| Benefit now | None that the guard does not already provide |
| Risk | Freezes an interface that is still being redesigned |

### Option C: One repo, three packages, AST guard (chosen)

| Dimension | Assessment |
|---|---|
| Cost | ~100 lines of test |
| Reliability | A violation fails the suite, in the commit that introduces it, with a message naming the file |
| Extraction readiness | The day we extract, we already know it will come loose — the guard has been asserting it all along |

## Trade-off analysis

The guard was verified against the code **before** it was written: all five rules already held on `main`. That is the point — the guard is not a refactor, it is a **ratchet**. It costs nothing today and makes the one failure mode that actually matters (silent re-coupling of the framework to the application) impossible to reach.

Rule 4 is the load-bearing one. Rules 1–3 are hygiene (they keep the public surface honest); rule 5 keeps the measurement layer portable; **rule 4 is what makes the framework a framework.**

## Consequences

**Easier**
- The framework can be extracted and published without archaeology.
- The public surface of `explanation` is a single file that a reader can hold in their head.
- Any attempt to re-couple the layers fails loudly, in the offending commit.

**Harder**
- Application-aware code cannot be placed in the framework "just for now". When something *seems* to belong in `explanation` but needs `conacq` types, the guard forces the question — and the answer is usually that it belongs in `conacq` (ADR-0005).
- Adding a symbol to the framework's public surface is a deliberate act (edit `api.py`), not a side effect of importing it somewhere.

**To revisit**
- When `explanation` is actually extracted into its own distribution, rules 1–5 become package boundaries rather than test assertions. The guard can then be retired — but not before.

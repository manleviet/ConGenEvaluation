# ADR-0011: `complete_configuration` bypasses the checker port — knowingly, for now

**Status:** Accepted
**Date:** 2026-07-15
**Deciders:** Viet-Man Le
**Resolves:** the T11.0 ratchet `test_complete_configuration_builds_solver_once` (deleted — it demanded a behaviour change disguised as a refactor)

## Context

`FMOracle` reaches a SAT solver by **two roads that do not know about each other**:

```python
def __init__(self, fm_path, solver_name='glucose4', use_incremental=True, ...):
    self._checker = build_checker(                       # road 1 — the port (ADR-0004)
        self.oracle_data.task,
        SolverBackend.from_flags(use_incremental=use_incremental), ...)

def is_valid(self, assignments):                          # uses road 1
    return self._checker.is_consistent(set_c + config_assumptions)

def complete_configuration(self, partial):                # road 2 — raw pysat
    solver = Solver(name=self.solver_name)                # ignores use_incremental
    for clause in self._fm_clauses(): solver.add_clause(clause)
```

Two things are wrong with this, and they are not the same thing:

1. **`use_incremental` half-lies.** `is_valid` honours it; `complete_configuration` never sees it. A caller passing `use_incremental=True` gets a persistent solver for membership and a fresh one per call for completion, with nothing saying so.
2. **`conacq` imports `pysat` directly** (`fm/oracle.py:10`), reaching past the port to the adapter. ADR-0004 exists to stop exactly this, and T7 removed the same shape once already (`generate_ne.py:115` hardcoded `NonIncrementalPySATChecker`).

The obvious fix — *route `complete_configuration` through `self._checker`* — **is not a refactor. It is a behaviour change**, and the measurements say so.

## The measurement: two axes, only one of them matters

Routing completion through the port changes **two** things at once. They had to be separated before anything could be decided. On a 60-variable FM-shaped CNF, 20 queries:

| Axis | Change | Witness differs |
|---|---|---|
| **Formula** | raw FM clauses → assumption-guarded KB (all guards enabled), fresh solver both | **0 / 20** |
| **Solver** | fresh per call → one persistent solver, same formula | **18 / 20** (both raw and guarded) |

**The formula axis is free.** Guards only add variables the assumptions force true; the search over feature variables is unchanged, and `variable_literals_to_config` drops guard/Tseitin variables from the model anyway.

**The solver axis is the whole question.** A persistent solver accumulates learned clauses, variable activity and saved phases. `solve(assumptions=...)` is scoped per call; **the search that answers it is not**. `complete_configuration` returns a *witness* — one of many valid completions — and which one you get depends on that accumulated state. Reordering the queries on a persistent solver changed **18/18** answers; on fresh solvers, **0/18**.

Reuse is **9.9× faster**.

> **Caveat, recorded because it nearly produced the wrong decision.** A 14-variable CNF showed fresh and reused agreeing *perfectly*. Had the measurement stopped there, "solver reuse is safe" would have been the conclusion. Small instances agree by luck. These numbers are strong signals, not proofs — the Layer-1 golden on three real FMs is the arbiter.

## The fact that settles it

`complete_configuration`'s only callers are the offline example generators (`example_generators/base.py:80`, `feature_frequency.py:197,199`), and **the app that drives them builds its oracle with the default**:

```python
apps/generate_examples.py:143    FMOracle(fm_path)        # use_incremental=True
```

So routing completion through `self._checker` **today** hands it the **persistent** solver — the 18/20 case. The generated examples change, which changes ConGen's input, which changes the numbers in the paper. The correct architecture and this branch's premise (*behaviour identical to `main`*) point in opposite directions.

## Decision

**Leave the bypass in place for this branch. Record why. Delete the ratchet that demanded otherwise.**

1. **`complete_configuration` keeps building its own fresh solver.** Not because that is the right architecture — it is not — but because changing it is a dataset migration, not a refactor, and this branch promised not to move the numbers.
2. **Delete `test_complete_configuration_builds_solver_once`.** It asserted `constructions["n"] == 1` — single-solver reuse — on an untested belief that reuse preserves behaviour. It does not. **An `xfail` is a standing instruction to finish the job**; this one pointed at the 18/20 case. Leaving it would be leaving a note telling the next person to change the dataset by accident.
3. **Take the free part.** `_fm_clauses()` rebuilds its list from `constraint_map` on every call — a pure comprehension over data that is immutable after build, no solver state, no behaviour. Precompute it once: **7.7%** of per-call cost, zero risk.
4. **State the target.** The end state is completion going through the port, with fresh-vs-reuse chosen by `SolverBackend` like everywhere else. Getting there costs one experiment re-run. It is a task, not a cleanup, and it needs its own commit and its own decision to move the numbers.

## Options considered

### Option A: route completion through `self._checker` now

| Dimension | Assessment |
|---|---|
| Architecture | Correct — the bypass and the half-lying parameter both die |
| Behaviour | **Breaks it.** `generate_examples.py` uses `use_incremental=True`, so completion inherits the persistent solver: 18/20 witnesses change → different examples → different ConGen input → **re-run every experiment** |
| Verdict | Right destination, wrong branch. The premise here is behaviour-identical |

### Option B: give the oracle a second checker, hardcoded non-incremental

```python
self._completion_checker = build_checker(task, SolverBackend.NON_INCREMENTAL, ...)
```

| Dimension | Assessment |
|---|---|
| Architecture | Goes through the port ✅ |
| Behaviour | Fresh per call — main path preserved (0/20 signal) |
| **Fails because** | It **hardcodes an adapter choice inside the oracle** — precisely the shape T7 deleted from `generate_ne.py`. It moves the bypass rather than removing it, and buys a second live solver per oracle. It also changes the **fallback** path: today's fallback re-solves on the *same, warm* solver; through the port it would be a second `is_consistent` on a *cold* one. Unverified, and the fallback likely fires often (the caller passes a random half-assignment, which is usually UNSAT) |

### Option C: two constructor flags (`use_incremental`, `completion_incremental`)

Rejected: one caller, no second use case. Building a dual API for a hypothetical future is the thing this branch keeps deleting.

### Option D: leave the bypass, delete the ratchet, take the free win, write this down (chosen)

| Dimension | Assessment |
|---|---|
| Behaviour | Untouched |
| Debt | **Unchanged, but no longer silent** — the reasoning, the numbers, and the exit path are here |
| Cost | Completion stays ~10× slower than it could be, on an offline path that runs once per dataset and is then cached |

## Trade-off analysis

> The bypass looks like an oversight. It is a debt with a receipt. What made it expensive to see is that the cheap fix and the correct fix look identical from the outside — both are "use the checker you already built" — and only a measurement separates "9.9× faster" from "9.9× faster and a different dataset."

The value of doing nothing here is not zero: the golden already catches the mistake. Someone who routes completion through the checker will get a red Layer-1 trace. What they will not get, without this ADR, is any idea **why** — and a red golden with no explanation is usually resolved by regenerating the golden.

## Consequences

**Easier**
- `complete_configuration(p)` is a function of `p`: same partial, same completion, on any FM, regardless of what was asked before. That holds by construction, not by luck.
- The next person to touch this has the numbers already: they do not need to rediscover that reuse is 9.9× and costs 18/20 witnesses.

**Harder**
- The completion path stays ~10× slower than achievable.
- `conacq` still imports `pysat` directly in three places (`fm/oracle.py`, `eval/accuracy.py`, `eval/semantic_equivalence.py`), so the ADR-0004 boundary is not fully enforceable by the guard yet.

**Non-obvious, on purpose**
- **`complete_configuration` constructs a `Solver` on every call, and `use_incremental` does not reach it.** Both look like bugs. If you are about to "just use `self._checker`": the Layer-1 golden will go red, and that red is correct — you changed the dataset. Read this file before regenerating anything.
- The `# TODO: need check` and *"a persistent completion solver (issue #10) belongs here"* comments are gone. A TODO is an instruction, and that one pointed at the 18/20 case.

## If completion is ever used online

The answer is the port, and the reasoning inverts cleanly:

Online (QuAcq-style) the contract is *"give me a discriminating query"* — **any** valid witness serves, and the answer is consumed and discarded rather than frozen into a file. QuAcq already lives with witness-depends-on-history: it calls `checker.get_model()` (`query_provider.py:134`, `discriminating_generator.py:66`) on a possibly-persistent checker, and that is correct there.

So an online completion should go through `self._checker` and take `use_incremental=True` — 9.9×, and the history dependence is a property you chose rather than one you inherited.

**The dividing line is not the function. It is whether the answer gets kept.** A witness that ends up in a file must be reproducible from its inputs alone; a witness consumed inside a loop need not be. `FMOracle` cannot know which it is — only the caller can, which is why the choice belongs on `SolverBackend` at construction and not inside `complete_configuration`.

## What I would revisit

- **The fallback's diversity.** When `solve(assumptions)` is UNSAT, `complete_configuration` re-solves with **no** assumptions and returns "any valid config", discarding the caller's partial. On a fresh solver, an unassumed `solve()` is deterministic — so **every** UNSAT partial yields the *same* configuration. The generator asks for diversity via a random partial and, on the fallback path, may be handed the same config each time. Not touched here (behaviour is frozen), but it deserves its own measurement.
- The two-call `is_consistent()` → `get_model()` protocol on the port carries hidden ordering state, and the three backends implement it differently (Incremental reads its live solver; NonIncremental and SAT4J return a model cached during `is_consistent`). Any future port-based completion must confront that.

## Related

- **ADR-0004** — checker is the port, backend is the adapter. This is the one place `conacq` still reaches past it on the acquisition path.
- **ADR-0007** — the last optimisation chosen without measuring first (`MappingProxyType`, −25% on `is_valid`). The rule it produced — *measure before you care* — is what produced this decision, in the opposite direction: here the measurement **stopped** an optimisation.

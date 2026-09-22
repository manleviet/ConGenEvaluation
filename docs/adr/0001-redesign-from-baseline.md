# ADR-0001: Rebuild from `main` rather than re-apply the old redesign branch

**Status:** Accepted
**Date:** 2026-06-28 (reaffirmed 2026-07-11)
**Deciders:** Viet-Man Le

## Context

A first attempt at this redesign existed as `feat/redesign-abc` — 37 commits on top of `main`. It contained genuinely good work (the boundary idea, the task-as-unit model, the profiler split), but it had three problems:

1. **The commits were ordered by time, not by subsystem.** Changes belonging to one concern were scattered across commits that were far apart; some single commits mixed several unrelated concerns. The branch was not reviewable step by step.
2. **It carried design defects that had spread deep.** Examples later confirmed: a model class that stayed mutable and was read live throughout the run; a builder placed in the framework that imported the application; abstractions named for the wrong side of the dependency (see ADR-0004).
3. Those defects were *load-bearing* by the end of the branch — later commits depended on them, so they could not be excised commit-by-commit.

The choice was how to get the good parts without the bad.

## Decision

**Do not re-apply or cherry-pick the old branch. Rebuild from `main`, applying the improved design directly, with behaviour held identical.**

The old branch is demoted to a *reference for the good parts* — read it, do not merge it.

Two invariants make this safe:
- **Behaviour is preserved exactly**: diagnoses, membership queries, completions, and the on-disk exports (`data/results/**` readable by `from_json`; CSV/LaTeX byte-identical). The pre-existing test suite is the safety net.
- **Work is organised by subsystem, not by commit**, in a task list with a green gate (full suite passes) after each task.

## Options considered

### Option A: Cherry-pick / re-apply the branch, then fix the defects afterwards

| Dimension | Assessment |
|---|---|
| Effort to first green | Low |
| Effort to *correct* end state | High — every defect is touched twice: once to introduce it, once to remove it |
| Reviewability | Poor — the reviewer must hold "this is wrong but will be fixed later" in their head for weeks |
| Risk | High — later commits depend on the defects, so removing them is a second refactor on top of an unreviewed first one |

### Option B: Rebuild from `main` with the improved design applied immediately

| Dimension | Assessment |
|---|---|
| Effort to first green | Higher — nothing is reused mechanically |
| Effort to correct end state | Lower — each subsystem is touched **once**, in its final shape |
| Reviewability | Good — one task = one subsystem = one reviewable green checkpoint |
| Risk | Contained — behaviour is pinned by the existing suite plus characterization tests written *before* each refactor |

## Trade-off analysis

Option A is cheaper only if you measure "time to a branch that compiles". It is more expensive at everything that matters: it introduces churn (add-then-remove), it forces a second refactor pass on code nobody has reviewed, and it makes the diff against `main` unreadable — which is exactly what made the first branch unusable.

The deciding argument: **the defects had spread**. A defect confined to one module can be fixed after re-applying. A defect that shapes the interfaces between modules cannot — you would be re-applying the very structure you intend to replace.

## Consequences

**Easier**
- Every task produces a clean, self-contained, green checkpoint that can be reviewed on its own.
- The final diff against `main` describes the *intended* design, with no introduce-then-remove noise.

**Harder**
- Nothing can be reused mechanically; every change is re-derived from `main`. Slower up front.
- The good ideas in the old branch must be *re-read and re-implemented*, not merged — with a standing rule that "it was verified on the old branch tip" is **not** verification. Anchor on `main` (`git show main:<file>`).

**To revisit**
- Nothing. The old branch can be deleted once this one merges; it has no unique value left.

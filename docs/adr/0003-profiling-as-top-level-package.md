# ADR-0003: `profiling` is a top-level package, not part of `explanation`

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Viet-Man Le

## Context

Performance measurement lived in `explanation/operations/algorithms/profiler.py` — a **1220-line module** holding: an abstract profiler, a concrete one, a null object, metric types, decorators, presets, a global registry, and the multi-process mode used by the parallel FastDiagP.

Two things were wrong with that address:

1. **It is not part of the explanation framework.** It counts things and times things. Nothing about it knows what a diagnosis is. It has no dependency on `explanation` at all.
2. **Both other packages need it.** `conacq` (runners, algorithms) profiles just as much as `explanation` does. With the profiler inside `explanation`, `conacq` reached measurement infrastructure *through the framework* — which means the framework's public API had to re-export something it does not own, and `conacq` could not use the profiler without depending on `explanation`.

## Decision

**Extract `profiling/` as a top-level package, a sibling of `explanation/` and `conacq/`** — the leaf of the dependency chain (ADR-0002 rule 5): stdlib only, importing neither of the other two.

Split by concern:

| Module | Holds |
|---|---|
| `protocol.py` | `Profiler` (`@runtime_checkable` Protocol) · `AbstractProfiler` · `NullProfiler` · `MetricType` · `ProfilerError` |
| `core.py` | the concrete profiler |
| `decorators.py` | `measure_time`, `count_calls` |
| `presets.py` | `ProfilerPreset`, `create_profiler` |
| `registry.py` | global get/set, `profiler_session` |
| `__init__.py` | the facade — the package's single public door |

Naming: the public `Profiler` is the **concrete** class (that is what callers construct); the structural type is exported as `ProfilerProtocol`. Consumers depend on the protocol, not the class.

## Options considered

### Option A: Keep it inside `explanation`, just split the 1220-line file

| Dimension | Assessment |
|---|---|
| Effort | Lowest |
| Layering | Wrong — `conacq` still gets its profiler *through the framework*; `explanation.api` must re-export something it does not own |
| Portability | Poor — the framework cannot be extracted without dragging measurement code with it, or the reverse |

### Option B: Top-level `profiling/` package (chosen)

| Dimension | Assessment |
|---|---|
| Effort | Moderate — ~35 import sites rewritten; `pyproject.toml` packaging updated |
| Layering | Correct — a neutral leaf that both packages depend on directly |
| Portability | Both `explanation` and `profiling` become independently extractable |
| Risk | Contained — a pure move plus a protocol; behaviour unchanged, suite is the net |

## Trade-off analysis

The test that settles it: **does `profiling` depend on anything in this repo?** No — it is stdlib only. Anything that depends on nothing, and that everything else depends on, is a leaf. Nesting a leaf inside one of its consumers is an accident of history, not a design.

The cost is honest (35 import sites, packaging config) and one-time. The benefit compounds: `explanation` no longer has a public API polluted by measurement types, `conacq` no longer imports the framework in order to count solver calls, and both packages can be lifted out separately.

## Consequences

**Easier**
- `explanation.api` carries **no** profiler symbols. Measurement is orthogonal, and now looks it.
- The profiler is reusable in the sibling research repos (DiagEnergy, KBDiag) without dragging the framework along.
- The 1220-line module is now six focused ones; the multi-process path is isolated rather than tangled with the single-threaded one.

**Harder**
- One more top-level package to package and ship (`pyproject.toml` `include = ["conacq*", "explanation*", "apps*", "profiling*"]`).
- Deep imports (`from profiling.core import ...`) are forbidden by the guard; everything goes through the facade.

**To revisit**
- If `profiling` ever needs a curated public surface (it does not today — it is small and entirely public), it gets an `api.py` like `explanation`. Until then, adding one would be ceremony.

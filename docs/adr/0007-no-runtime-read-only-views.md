# ADR-0007: The name↔id catalog is a plain `dict` — no runtime read-only view

**Status:** Accepted
**Date:** 2026-07-11
**Deciders:** Viet-Man Le
**Supersedes:** the `MappingProxyType` part of the KB-catalog design (this reverses a decision made earlier in the same redesign)

## Context

Every KB in this system carries a name↔id catalog: feature name → SAT variable id, and back. It is read on the hottest path in the system — `FeatureModelOracle.is_valid()`, the membership query QuAcq issues thousands of times per run, and the runtime/energy figures the papers report.

Earlier in this redesign we decided to expose that catalog through **read-only views**:

```python
@property
def name_to_id(self) -> Mapping[str, int]:
    return MappingProxyType(self._name_to_id)
```

The stated goal was a KB that could not be used as a live mutable store — nobody should be able to reach in and edit the catalog, and two tasks derived from one KB should be safe to run in parallel.

It was a mistake, and the redesign paid for it in three separate places before anyone connected them:

1. **~25% of `is_valid`, measured.** The property builds a *new* `MappingProxyType` on every access, and the caller read it inside a generator — so it was rebuilt once **per feature**. On `busybox` (854 features) the guard alone cost 47 µs/call that `main` did not pay. This violated the redesign's own rule that the hot path must not be touched without measurement.
2. **A serialisation landmine.** `feature_ids` returned the proxy while annotated `Dict[str, int]`; `json.dumps` cannot encode a `mappingproxy`. The frozen on-disk export was one `json.dump` away from breaking.
3. **Six fields for two dicts.** Because the builders *rebind* the catalog (`model._name_to_id = bias.feature_ids`), a view cached in `__init__` would have pointed at the stale empty dict. The fix was identity-memoisation — two extra bookkeeping fields per dict.

Then the decisive question: **who was the protection actually protecting against?** A grep for assignments into the catalog across the whole repository returned exactly one hit:

```
tests/test_encoding.py:71:   kb.name_to_id["x"] = 9      # asserts the view is read-only
```

**The only consumer of the guarantee was the test of the guarantee.** No production code has ever mutated the catalog. And the one task that would have leaned on the immutability (`#9`, routing live reads through an accessor) was dropped once the measurement showed the cost was the proxy, not the reads.

## Decision

**Remove the runtime read-only view. Expose the catalog as a plain `dict`. Keep the read-only guarantee at the type level, where it is free.**

Two classes, two different answers — the distinction matters:

| Class | Property? | Runtime view? |
|---|---|---|
| **`conacq.KBModel`** (ours: `ConGenModel`, `QuAcqModel`, `FMOracleModel`) | **No.** Its storage is ours and already named `name_to_id` / `id_to_name`. There is nothing to translate; the property existed *only* to wrap the proxy | **No** — public `dict` attributes |
| **`explanation.DiagnosisModel`** (extends flamapy's `PySATModel`) | **Yes — keep.** flamapy owns the storage and calls it `variables` / `features`; we cannot rename it. The property **is the translation layer** to the `KBProtocol` names | **No** — `return self.variables`, no proxy |

`KBProtocol` continues to declare the catalog as `Mapping[str, int]`. A `dict` **is** a `Mapping`, so both models still satisfy the protocol structurally, static readers still see a read-only interface, and the runtime pays nothing.

## Options considered

### Option A: Keep the view, memoise it (identity check per read)

| Dimension | Assessment |
|---|---|
| Hot path | Fixed (one pointer comparison per read) |
| Complexity | Six fields for two dicts, plus a comment explaining why they must not be simplified |
| Benefit | Still guards against a mutation that **does not occur anywhere** |
| Verdict | Rejected — paying complexity to protect a hypothetical |

### Option B: Make the catalog set-once (a `set_catalog()` method), then the view is built once

| Dimension | Assessment |
|---|---|
| Hot path | Fixed |
| Complexity | Four fields, plus a new method builders must remember to call |
| Benefit | Same hypothetical |
| Verdict | Rejected — cheaper than A, still buys nothing |

### Option C: Plain `dict` + `Mapping` in the protocol (chosen)

| Dimension | Assessment |
|---|---|
| Hot path | **Identical to `main`** — nothing is constructed on read |
| Complexity | Five fields, no properties, no views, no memoisation, no explanatory comment needed |
| Serialisation | `json.dump` just works |
| Guarantee lost | Runtime enforcement — which nothing was using |
| Guarantee kept | Type-level: the protocol says `Mapping`, so a mutating caller is a type error |

## Trade-off analysis

The general lesson, which is why this ADR exists rather than a quiet revert:

> **A safety mechanism that no caller was ever going to trip is not safety, it is cost.** This one had a *measured* price (25% of the hottest path), a *latent* price (a `json.dumps` that would have broken the frozen export), and a *structural* price (six fields and a memoisation dance) — in exchange for a guarantee whose only consumer was its own unit test.

The instinct behind it was not wrong: a KB *should not* be a live mutable store. But that is a statement about **how the code is written**, and it is better enforced by the type (`Mapping`), by a test if it ever matters, or simply by nobody doing it — not by paying a per-read tax forever.

Note also that runtime immutability is not even universally available here: `MappingProxyType` **cannot be pickled**, so applying the same idea to `Task.negation_map` would break FastDiagP's multiprocessing outright. The mechanism does not scale to the place immutability would actually have mattered.

> **⚠️ CORRECTION (2026-07-17, ADR-0012).** The first sentence is true; **the conclusion is false**. `MappingProxyType` is *one mechanism*; "freezing a dict" is a *category*. A `dict` subclass with `__reduce__` pickles fine **and** blocks every mutator — verified. `Task.negation_map` is frozen this way in ADR-0012.
>
> This paragraph tested a mechanism, failed, and concluded about the category. The conclusion then hardened as it circulated — a design brief wrote *"`negation_map` **must** stay a `dict`"*, this ADR recorded *"the mechanism does not scale"*, an implementation report escalated it to *"structurally cannot be frozen"* — and nobody re-tested, because each reader checked the thing the previous one pointed at.
>
> **The decision in this ADR still stands** (the catalog is a plain `dict`, and for the reasons given: a *per-read* tax of ~25% protecting a mutation nobody performs). Only this closing generalisation is withdrawn. See ADR-0012 for the rule that separates the two cases: **immutability at construction is free; immutability at read is a tax.**

## Consequences

**Easier**
- `is_valid` costs what it cost on `main`.
- `KBModel` is five plain fields. `feature_ids` is a `dict` and serialises.
- The builders' rebinding of the catalog is harmless again — no memoisation to keep in sync with it.

**Harder**
- Nothing at runtime stops a future caller from writing into the catalog. If that ever becomes a real risk (rather than a hypothetical one), enforce it with an AST test — free, and it fails at the offending commit rather than taxing every read.

**Deleted**
- `tests/test_encoding.py`'s read-only-view assertion — the test of a feature that no longer exists.

**Still true**
- The KB is *conceptually* immutable after build, and `KBProtocol` says so in its types. That was always the part with value.

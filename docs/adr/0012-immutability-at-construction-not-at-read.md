# ADR-0012: `Task` and `OracleData` are deep-frozen — immutability at *construction* is free; immutability at *read* is a tax

**Status:** Accepted
**Date:** 2026-07-17
**Deciders:** Viet-Man Le
**Relates to:** ADR-0007 (does **not** supersede it — see "Reconciling with ADR-0007"), ADR-0009, ADR-0010
**Corrects:** a factual error in ADR-0007's closing paragraph (see "The error this ADR corrects")

## Context

`Task` and `OracleData` are declared `@dataclass(frozen=True)`. `frozen=True` blocks **rebinding** (`task.set_c = [...]` raises `FrozenInstanceError`) but does nothing about **contents**: `task.set_c.append(99)` succeeds silently on a list field. The label said immutable; the object was not.

Both are **public contracts** — `explanation` ships as a flamapy plugin, and consumers outside this repository construct a `Task` and hand it to our algorithms. A silent in-place mutation between construction and `find_diagnosis` changes the result with nothing to show for it.

T11c.2 coerces the list-valued solve fields to tuples in `__post_init__`. It was held for one reason: **a claimed performance penalty.** That claim, and every claim that grew out of it, turned out to be measurement error. This ADR exists because the numbers are the whole argument, and without them someone will "clean this up" in a year.

### What was measured

**The penalty does not exist.**

| Claim | Origin | Measurement |
|---|---|---|
| `run()` **+0.58%**, `prepare_task` **+1.30%**, `is_valid` **+1.85%** | single-shot, one run per arm | **Refuted.** Same code, same input, 7 runs of `run()`: **4926–5962 ms**, spread **20.08%**, sd **6.94%**. The claimed effect (31.6 ms) is **33× smaller than the noise**. Re-measured with min-primary, warm-up 8, `gc.disable()`, n≥8: `run()` **sign-flipped to −3.0%** |
| tuple penalty in FastDiag | — | n=61, min-primary: **−0.00%** (config task) and **−1.65%** (FM task). No penalty at any input size tried |

Two independent measurements, made separately, both reaching **"cannot measure"**, one of them by refuting its own prior numbers.

**Nothing mutates a `Task` field.** Runtime instrumentation — every field wrapped in a recording `list`/`dict` subclass with taint propagation through `+`, slicing and `copy()`, so the recorder follows the value **into the algorithms' parameters** — over 13 scenarios (FastDiag ×2, QuickXPlain ×2, KBDiag ×2, KBDiag+neg ×2, QXP+TestCases ×2, WipeOutR_FM, WipeOutR_T, HSDAG+FastDiag):

```
1663 operations · 20 (field, operation) pairs · MUTATIONS: 0
```

The entire contact surface is **9 operations**: `len` · `iter` · `in` · `[a:b]` · `[i]` · `+` · `bool` · `reversed` · `[k]`. Every one works on a tuple. The code already treats `Task` as a value; it simply never said so.

## Decision

**Deep-freeze the solve fields. Keep `frozen=True`. Annotate `Tuple[int, ...]`. Freeze `negation_map` with a picklable `FrozenDict`.**

```python
@dataclass(frozen=True)
class DiagnosisTask:
    set_c: Tuple[int, ...] = ()
    set_kb: Tuple[Tuple[int, ...], ...] = ()
    negation_map: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self) -> None:
        # Constructors pass lists for convenience; storing tuples makes in-place
        # mutation raise AttributeError — a loud failure at the call site.
        object.__setattr__(self, 'set_c', tuple(self.set_c))
        ...
```

The algorithms keep their entry conversion (`set_c, set_b = list(set_c), list(set_b)`). **That boundary is the design, not a workaround**: immutable storage → mutable working copy at the algorithm's door. It exists because the algorithms *concatenate* (`set_b + set_c`), not because they mutate.

### Why `Tuple[int, ...]` and not `Sequence[int]`

`Sequence[int]` was proposed first, on the reasoning that "a read-only sequence" is the honest contract and it lets constructors pass lists. **The operation profile killed it:**

> **`+` accounts for 200 of 1663 operations = 12.0%** — ranks 5, 11 and 12 in the table. **`typing.Sequence` has no `__add__`.** Annotating `Sequence[int]` makes mypy reject `set_b + set_c` at the 200 hottest sites. Rewriting them as `(*set_b, *set_c)` is **1.42× slower** than `list(a) + b` (measured — CPython special-cases `list + list`).

The annotation that sounds better is not the annotation the code uses.

## Options considered

### Option A: `Tuple[int, ...]` + `frozen=True` + `FrozenDict` (chosen)

| Dimension | Assessment |
|---|---|
| Runtime cost | **Below the noise floor** (two independent measurements, one sign-flipped) |
| Reach | Every consumer, at runtime — including the untyped external caller `py.typed` + mypy never reaches |
| Failure mode | **Loud** — `AttributeError` at the offending call |
| Honesty | The `frozen=True` label becomes true |
| Pickle | `tuple` ✅; `FrozenDict.__reduce__` ✅ (verified) — FastDiagP green |

### Option B: revert to `list` + an AST population guard

| Dimension | Assessment |
|---|---|
| Runtime cost | Zero |
| Reach | **This repository only.** Blind to the flamapy plugin consumer — the population `Task` exists to serve |
| Failure mode | CI-time — and **this repo has no CI** (`.github/workflows/` does not exist); the guard runs only when someone types `pytest` |
| Verdict | Rejected — buys back an unmeasurable cost by giving up the only mechanism that reaches outside the repo |

### Option C: freeze the flat fields only, leave `set_kb` a list

| Dimension | Assessment |
|---|---|
| Rationale | `tuple(tuple(c) for c in set_kb)` costs 37.73 µs vs 0.93 µs for a flat field — 40× |
| Arithmetic | `__post_init__` runs **3× per run** (counted, not inherited). 3 × 64 µs = **0.19 ms** of a 31.6 ms claimed penalty = **0.4%** |
| Verdict | **Rejected — the worst of both.** Pays ~99.6% of a cost that does not exist, keeps an asymmetry ("why is `set_kb` different?") needing a permanent explanation. The 40× was real *per call* and irrelevant *per run*: an ingredient measured and mistaken for the dish |

### Option D: tuple-native algorithms — **built, measured, rejected on the numbers**

Two variants were argued, one was built end-to-end. The user's argument for them was the strongest in the whole review, and it deserves recording verbatim, because the numbers — not the reasoning — are what defeated it:

> *"If tuple and list tie on speed, then use **one type only**. Supporting both means **converting forever**. Transformation is a **natural boundary** — it runs once at setup, not in the loop, and the algorithm benchmark doesn't include it. And tuple **gets the honest label for free**. Therefore: tuple everywhere."*

Every premise is sound. The conclusion is still wrong, and only a build could show why.

| | measured |
|---|---|
| **Workload** | synthetic k=5 inconsistent UVL → **647-node** HSDAG, real checker/labeler/Task. (The earlier 3-node workload could not measure a per-node cost at all.) |
| **Method** | `perf_counter` around `hsdag.execute()` directly (not pytest), `gc.disable()`, warm-up 8, 15 reps, **min-primary**, arms in isolated `git worktree`s, **interleaved A↔B per round** |
| **Controls** | `is_consistent` = 4440 **in all three arms**; nodes 647; diagnoses 243; **result md5 `4778f31` identical**. Same tree explored, same output — the arms differ in timing only |
| **S4** (tuple everywhere) | **+3.5% vs S0**, **26/26 interleaved rounds slower** ⇒ two-sided **p ≈ 3×10⁻⁸** |
| **S1** (this ADR's decision) | **+0.12–0.4%**, 17/27 rounds ⇒ **p = 0.25** ⇒ **not measurable** |

**Why tuple-native loses — the mechanism, not the microbenchmark:**

- **Labeler**: `index() + slice + concat` = **3 tuple allocations**; `copy() + remove()` = **1 list allocation, mutated in place**. **× 647 nodes.**
- **`diff()`**: `tuple(genexpr)` runs the **Python iterator protocol**; `[listcomp]` is a **single C-loop opcode**.

Eliminating the entry `list()` costs more than it saves. **Immutability buys safety, not speed** — and tuple-native pays for that safety 647 times per run, in the one place it was supposed to save.

**Verdict: rejected.** Not because it is infeasible (it was built, and it is *functionally identical* — same md5), and not because "S1 was already done" (that was inertia, and it was named as such). **Because it is a measured 3.5% regression with no payoff.**

> ⚠️ **Two errors in the design brief cost real work here, and are recorded so the next reader does not repeat them:**
> 1. **Under-spec:** the S3 brief said *"internals: Tuple"* but omitted **`return [] → return ()`**. The implementer followed the letter and hit **178 red tests**. The S3 that *did* run had the `return ()` — a change the brief's author made and never wrote down. **Measured one thing, specified another.**
> 2. **Over-spec:** the S4 brief said `@dataclass(frozen=True)` **+** `Tuple` fields for `AbstractHSParameters`. **`frozen` was the brief's own addition** — "tuple everywhere" does not require it. It collided with `parameters.set_tcp = ...` in `get_label`, which the code's own comment explains is a **cache passed to the node's children** (*"update the parameters, which will be used by the children's nodes"*). Freezing it deletes that cache ⇒ re-run `find_diagnosis` per child ⇒ a real regression. The implementer correctly reported this as an **S4-killer** — **correct, against a wrong spec**. Dropping `frozen` and keeping `Tuple` leaves the rebind working: no bridge, no cache loss, and the conversions still vanish. **The corrected S4 is the one measured above, and it still lost.**
>
> **Root cause of both: two properties fused into one spec link** ("tuple" ≠ "frozen"; "tuple internals" ≠ "tuple base case"). **Read a type spec as a coherent system, not a checklist:** *"if I do all N links, is there anywhere a tuple still meets a list?"* and *"does any link demand two things — split it."*

> **⚠️ CORRECTION (same day, before this ADR was acted on).** The first draft of this row read *"Rejected — it buys nothing; the cost it removes is below the noise floor."* **That argument answers a performance question. S3 is a design question**, and on design S3 is arguably *better*: the entry conversions (`list(set_c), list(set_b)`) exist because `set_b + set_c` **mixes types** — not because the algorithms mutate (0 mutations in 1663 recorded operations). They are a type accident, not a boundary.
>
> The draft also claimed the radius was **"8 `return []` sites"**. That number came from reading **one file** (`fastdiag.py`). The real population: **7 `utils.py` functions** (3 of them type-sensitive — `get_hashcode` hashes `str(sorted(x))`, so `'[1, 2]' ≠ '(1, 2)'`; `contains` compares `==`, so `[1,2] != (1,2)`; `negate_cnf_tseitin` does `clause + [ti]`), **16 public entry points across 11 classes** (7 with no entry conversion — they convert at the *caller* instead, e.g. `pysat_redundancy_constraints.py:59`), and `AbstractHSParameters`, which **genuinely is mutated** (`new_c.remove(arc_label)`) and which S3 can only *move* the boundary around, not remove.
>
> **S1 is what ships** — it is done, green, and independent of this. But it ships because it is *finished and safe*, **not** because S3 was weighed and lost. S3 has not been weighed. → **T20**.

### Option E: drop `frozen=True` for `__slots__` (proposed by an external LLM consult)

| Dimension | Assessment |
|---|---|
| Is it faster? | **Yes, and the number is the answer:** `frozen=True` costs **260 ns per construction**. `Task` is constructed **3× per `run()`** (instrumented count). **260 ns × 3 = 0.0008 ms of 1204 ms = 0.000065%** |
| `__slots__` speeds up reads? | **No.** 15.76 ns → 15.21 ns. The headline benefit does not materialise |
| Hand-rolled `__slots__` vs `@dataclass(slots=True)` | The hand-rolled version is **slower** (172.6 ns vs 161.8 ns) |
| Verdict | Rejected — **780 nanoseconds per run** in exchange for the label |

### Option F: `@dataclass(frozen=True, slots=True)` — have both

| Dimension | Assessment |
|---|---|
| Gain | 46 ns/construction (×3 = **138 ns**), **63% less memory** per object (×3 objects) |
| Cost | `slots=True` **rebuilds the class**, so every zero-argument `super()` inside it breaks. `TestCaseTask.__post_init__` calls exactly that. Fixable (`Task.__post_init__(self)` explicitly) — but it becomes a silent trap for the next person who adds a subclass |
| Verdict | Rejected **for `Task`** — 138 ns and 300 bytes for a landmine. **Revisit for `AbstractHSParameters`** (constructed per HSDAG node — the actual high-count object). → T17 |

## Reconciling with ADR-0007 — they agree; the rule is not "let the number decide"

ADR-0007 removed a `MappingProxyType` view from the KB catalog. This ADR adds `tuple` to `Task`. That looks like a reversal. It is not, and the reason is worth stating precisely, because "measure and let the number decide" is *too weak* a rule — it would leave the next reader thinking the answer is a coin toss decided by benchmarks.

> **Immutability at *construction* is free. Immutability at *read* is a tax.**

| | ADR-0007 (`MappingProxyType`) | ADR-0012 (`tuple`) |
|---|---|---|
| Where the cost lands | **every read** — the property rebuilt the proxy per access, once *per feature* inside a generator | **every construction** — `__post_init__`, **3× per run** |
| Measured cost | **~25% of `is_valid`**, the hottest path in the system | **below a 20% noise floor**; two independent attempts, one sign-flipped |
| Who wanted the guarantee | **nobody.** One grep hit: the test asserting the view was read-only. *The only consumer of the guarantee was the test of the guarantee* | **every external consumer.** `Task` is a published contract handed to our algorithms by code we cannot see |
| Verdict | Remove | Keep |

Same rule, opposite answers — because the cost profiles are opposite and the beneficiaries are opposite. A design that pays per *read* on a hot path to protect a mutation nobody performs is waste. A design that pays per *construction* (three times) to stop a public label from lying is not.

ADR-0007's own remedy — *"keep the read-only guarantee at the type level, where it is free"* — still holds for `KBModel`, whose consumer is this repository. It does not transfer to `Task`, whose consumer is a stranger who never runs mypy: **this repository ships no `py.typed`, so an installed-package consumer's mypy reports `Skipping analyzing "explanation"` and checks nothing at all** (verified against a real `pip install` into a venv, not `MYPYPATH`). Type-level enforcement reaches nobody outside this repo today.

## The error this ADR corrects

ADR-0007 closes with:

> *"runtime immutability is not even universally available here: `MappingProxyType` cannot be pickled, so applying the same idea to `Task.negation_map` would break FastDiagP's multiprocessing outright. The mechanism does not scale to the place immutability would actually have mattered."*

**The first clause is true. The conclusion is false.**

```python
class FrozenDict(dict):
    __slots__ = ()
    def _no(self, *a, **k): raise TypeError("FrozenDict is immutable")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _no
    def __reduce__(self): return (FrozenDict, (dict(self),))
```

Verified: **pickles**, blocks `[k]=` / `update()` / `del[k]` / `pop()`, and reads (`fd[k]`, `k in fd`, `len(fd)`) are untouched — which is all `negation_map` ever needs (the operation profile records exactly `in` ×8 and `[k]` ×3, both read-only).

`MappingProxyType` is **one mechanism**. "Freezing a dict" is a **category**. ADR-0007 tested the mechanism, failed, and concluded about the category — then that conclusion hardened as it circulated: a design brief wrote *"`negation_map` **must** stay a `dict`"*, this ADR recorded *"the mechanism does not scale"*, and a later implementation report escalated it to *"structurally cannot be frozen"*. Nobody re-tested; each reader checked the thing the previous one pointed at.

**The lie was not load-bearing. It was inherited.**

## Consequences

**Easier**
- `@dataclass(frozen=True)` on `Task`/`OracleData` is now **true**, contents included. The label and the mechanism say the same thing.
- A plugin consumer who writes `task.set_c.append(x)` gets an `AttributeError` at the call — not a silently wrong diagnosis three frames later.
- The remaining four "frozen label + mutable field" classes (`BGData` ×7 fields, `OracleData`, `QuAcqTask`, `AssignmentAssumptionMap`) now have **no technical excuse** — only a scheduling one.

**Harder**
- Constructors must accept lists and coerce; the annotation says `Tuple[int, ...]` while `__init__` tolerates a list. That gap is deliberate and lives in `__post_init__`.
- `negation_map` is a `FrozenDict`, not a `dict`. It **is** a `dict` subclass, so `isinstance` and every read still work; anything that mutated it would now raise — nothing does.

**Watch out for**
- **Do not "optimise" `list(enabled) + [...]` into `[*enabled, *...]`.** Measured: `[*a, *(gen)]` = **1.42×**, `[*a, *[...]]` = **1.12×**, vs `list(a) + [...]` = **1.03×**. CPython special-cases `list + list`. This was nearly recommended and withdrawn.
- **`ConGenRunner` defaults to `use_incremental=True`.** The golden test pins `use_incremental=False` deliberately — that arm is a research control (`apps/extract_results.py::generate_incremental_comparison`), **not** an unoptimised path. Measured: 5057 ms → 1121 ms (**4.5×**), identical results (`n_kb=17`, `checks=536`). Do not "fix" it.

## What this ADR does *not* claim

Coverage is bounded, and the boundary is part of the record:

- **`set_tv` and `set_neg_tc`: 0 operations recorded** — no exercised path touches them. *Not measured* is not *safe*.
- **FastDiagP, ConGen and QuAcq are not in the operation profile.** The recorder cannot cross `multiprocessing` (a `Counter` is not shared between processes). FastDiagP's *correctness* under S1 is verified separately (6 passed — tuple and dict survive pickling).
- **`set_kb` enters pysat's C extension**, which bypasses Python-level method overrides — the recorder is blind to a C-level mutation. Covered by different evidence: `Solver(bootstrap_with=((1,2),(-1,3)))` works, so pysat accepts tuples and does not mutate its input.
- **In incremental mode, `solve` (5.56%) + `is_consistent` (2.43%) + `add_clause` (0.81%) ≈ 9% of profiled time. Where the other ~90% goes is unknown.** Nothing in this decision touches it. → own task.

## Action items

🔴 **Order matters, and it is not the order this ADR was drafted in.** The deep-freeze **cannot be committed before S1-vs-S3 is settled**: freezing the field *alone* breaks the code (`tuple + list`), so **one of the two must ship with it — they are one decision, not two commits**. Measured: of the 21 files in the working tree, **30 added lines are the `list(...)` entry conversions S3 would delete**, across 5 algorithm files.

**The uncommitted working tree *is* the S1 experiment.** Committing it now freezes a choice that has not been weighed. T20 measures it live; if S3 wins we rework before it enters history — no revert, no churn in the record.

**Gate — CLEARED 2026-07-17**
0. [x] **T20** — type-boundary inventory: 7 `utils` functions (6 type-sensitive *in principle*, **0 live** across ~1600 recorded calls), 16 entry points across 11 classes (**8 annotations lie**), `AbstractHSParameters` genuinely mutated
0b. [x] **T21/T21b/T21c/T21d** — S3 and S4 **built**; S4 measured at 647 HSDAG nodes: **+3.5%, p ≈ 3×10⁻⁸ ⇒ rejected**. S1: **p = 0.25 ⇒ not measurable ⇒ free**. **S0 (drop `frozen=True`) is not a live candidate — there is no measurable speed to reclaim by giving up immutability.**

**One commit, shape S1**
1. [ ] Solve fields on `Task` / `OracleData` → `Tuple[int, ...]` (**not** `Sequence[int]`) — *invariant: true under both S1 and S3*
2. [ ] `negation_map` → `FrozenDict`; assert it pickles under FastDiagP — *invariant*
3. [ ] Flip `test_task_is_deeply_frozen` (drop the xfail) **and** delete `test_task_is_only_shallow_frozen` **in the same commit** — the two contradict on purpose — *invariant*
4. [ ] **Keep the entry conversions** (they are the boundary, and they are cheap: p = 0.25). **Annotate the 8 lying public entry points `Sequence[int]`** — they declare `List` and are handed `task.set_c`, a `Tuple`; every call site is currently a type error, i.e. this ADR's own "labels must not lie" rule, freshly broken by its own decision.
   **Fields and parameters are different roles and take different answers:** a field is *stored*, and `get_cf()` does `set_b + set_c` **on it** ⇒ **`Tuple`** (`Sequence` has no `__add__`, and `+` is 12% of recorded operations). A parameter is *received and copied immediately* ⇒ **`Sequence`**; the `+` happens on the local list afterwards. Internal recursion (`_fd`, `_qx`) and `is_consistent` keep **`List`** — they receive local lists and are already honest.

**Independent of the gate**
5. [ ] Commit this ADR + the ADR-0007 correction + the index as a **docs-only commit** — they record decisions already settled and are what the implementer reads
6. [ ] T17: measure `@dataclass(slots=True)` on `AbstractHSParameters` (per-HSDAG-node — the real high-count object; `Task` is 3×/run, which is why it does not qualify)
7. [ ] T17: freeze-for-honesty on `BGData` / `OracleData` / `QuAcqTask` / `AssignmentAssumptionMap`, or drop `frozen=True` from them — a label that lies is not a third option
8. [ ] T19: **617 of the 620 assumptions passed to every SAT call may be redundant.** Dropping them: `run()` 1119 → 241 ms (**−78.5%**), learned KB identical (8/10 fields; the 2 that differ are timing). The encoding `[-a, literal]` is one-directional, so the **SAT answer** is provably unaffected — but the **model is not**: without `-a` the solver may set `a=true`, and `get_model()` then depends on the polarity heuristic (verified: glucose/minisat default false, **cadical does not**). Any test of this **must run cadical** — glucose will pass it silently. → own task, own ADR.

# Architecture Decision Records

Each ADR captures **one architectural decision and the reasoning behind it** — including the options that were rejected and why.

## Why these exist

The tests tell you *what* the architecture is. `tests/test_boundary_guard.py` will fail if `explanation` imports `conacq`; it will not tell you why that rule exists, what it protects, or what breaks if you "just add one import". A guard can enforce a boundary; only an ADR can explain it.

These decisions were made during the **ABC-v2 redesign** (July 2026), a rebuild of the `conacq` / `explanation` / `profiling` architecture from `main` with behaviour held identical. The construction plan for that redesign was a temporary working document and no longer exists. The reasoning does — here.

**When you are about to "tidy up" something in this codebase that looks misplaced, read the relevant ADR first.** Several of these decisions look wrong until you know what they are protecting.

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-redesign-from-baseline.md) | Rebuild from `main` rather than re-apply the old branch | Accepted |
| [0002](0002-three-package-layering.md) | Three-package layering, enforced by an AST guard | Accepted |
| [0003](0003-profiling-as-top-level-package.md) | `profiling` is a top-level package, not part of `explanation` | Accepted |
| [0004](0004-checker-is-the-port-backend-is-the-adapter.md) | `checker` = port (algorithm-facing), `solver_backend` = adapter (solver-facing) | Accepted |
| [0005](0005-oracle-bias-builder-lives-in-conacq.md) | `OracleBiasModelBuilder` lives in `conacq`, not `explanation` | Accepted |
| [0006](0006-evaluation-stays-inside-conacq.md) | `evaluation` stays inside `conacq` — it is *not* the next `profiling` | Accepted |
| [0007](0007-no-runtime-read-only-views.md) | The name↔id catalog is a plain `dict` — no runtime read-only view | Accepted |
| [0008](0008-run-result-and-result-data-stay-separate.md) | `ConGenRunResult` and `ConGenResultData` stay separate — write-product ≠ read-projection | Accepted |
| [0009](0009-the-oracle-answers-it-does-not-provision.md) | The oracle answers questions; it does not provision the algorithm | Accepted |
| [0010](0010-roles-are-declared-not-inferred.md) | Roles are declared, not inferred — protocol members are `@abstractmethod`; our oracles inherit the roles they play | Accepted |
| [0011](0011-completion-bypasses-the-checker-port.md) | `complete_configuration` bypasses the checker port — knowingly; routing it through is a dataset migration, not a refactor | Accepted |
| [0012](0012-immutability-at-construction-not-at-read.md) | `Task`/`OracleData` are deep-frozen — immutability at *construction* is free; immutability at *read* is a tax (reconciles with 0007; corrects its closing generalisation) | Accepted |
| [0013](0013-is-consistent-and-find-model-are-two-questions.md) | Split `is_consistent`/`find_model` — the ~617 guard-negations are redundant for the SAT answer, load-bearing for the model; **4.2× on `run()`** (first measurable runtime win) | Accepted |
| [0014](0014-parallel-executor-deferred-to-canonical.md) | The parallel executor is deferred to the canonical repo — `FastDiagP`, `get_instance`, `ProfilerMode.MULTI_PROCESS` are scaffolding, not dead code (guarded) | Accepted |
| [0015](0015-example-mode-pool-shuffle-must-be-seeded.md) | The example-mode pool shuffle must be seeded (per-fold) — its OS-entropy shuffle makes one paper table irreproducible; impl+regen deferred to paper-writing | Accepted |
| [0016](0016-shuffle-bias-is-a-no-op-for-quacq.md) | `shuffle_bias` is a no-op for QuAcq — `set(set_c)` drops the runner's shuffle; honor the order; impl+QuAcq-golden regen deferred to a gated command | Accepted |
| [0017](0017-reduce-discards-mss-order.md) | REDUCE discards the MSS ordering through `set()` — preserve `gamma1+gamma2` order; impl+AcqMSS/ConGen-golden regen deferred to a gated command (after 0016) | Accepted |

## Writing a new one

Copy the shape of an existing ADR: Context → Decision → Options considered → Trade-offs → Consequences. Write it **when the decision is made**, not at the end of the project — by then the alternatives you rejected have faded, and those are the most valuable part of the record.

Number sequentially. Never edit a decision after it is accepted: supersede it with a new ADR and mark the old one `Superseded by ADR-XXXX`.

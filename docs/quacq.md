# QuAcq - Constraint Acquisition via Partial Queries (IJCAI 2013)

**Last Updated**: 2026-02-28 (Merged ExampleProvider + QueryGenerator → unified QueryProvider)

**Paper:** Bessiere, Coletta, Hebrard, Katsirelos, Lazaar, Narodytska, Quimper, Walsh

## Overview

QuAcq (Quick Acquisition) — active learning algorithm that learns constraint networks by asking the user **partial queries** (assignments to subsets of variables), instead of membership queries on all variables.

## Implementation Modes

AcqMSS implements QuAcq in **two modes**:

### 1. Oracle-Based Mode (Original Algorithm 1)

Interactive learning through membership queries:
1. Init `C_L = {}` (empty learned network)
2. Generate query `e` satisfying `C_L` but violating at least 1 constraint in bias `B`
3. Ask oracle: `ASK(e)`
   - **yes** → remove all constraints in `B` that `e` violates
   - **no** → call FindScope + FindC to find and add 1 constraint to `C_L`
4. Repeat until convergence or collapse

**Implementation**:
- `conacq/algorithms/quacq/quacq.py` — Main QuAcq algorithm (oracle mode)
- `conacq/example_generators/query_provider.py` — Unified QueryProvider (pool + SAT strategies)
- `conacq/oracle/` — Oracle implementations (FMOracle, UserPromptOracle, CachedOracle)

### 2. Example-Based Mode (Batch Learning with FindScope/FindC)

Learn from pre-collected positive/negative examples without an interactive oracle:
1. Init `C_L = {}`, load pre-collected E+/E- examples
2. For each `e` in E- (negative examples):
   - Call `FindScope` to identify violated scope via oracle.is_valid() partial queries
   - Call `FindC` to identify specific constraint using DiscriminatingGenerator
   - Add found constraint to `C_L`
3. Prune bias using E+ (valid examples reject false positive constraints)
4. Return learned `C_L`

**New: Paper-Aligned Discriminating Examples** (commit 260227):
- DiscriminatingGenerator uses C_L[Y] (learned KB restricted to scope) + BG
- No longer uses FM clauses (ground truth) for discrimination
- All queries via oracle.is_valid() — no SAT discrimination
- Query history tagged with 'main', 'findscope', 'findc' sources

**Implementation**:
- `conacq/algorithms/quacq/quacq.py` — QuAcq.learn_from_examples() method (oracle.is_valid())
- `conacq/algorithms/quacq/findscope.py` — FindScope (Algorithm 2, 134 LOC, oracle-based)
- `conacq/algorithms/quacq/findc.py` — FindC (Algorithm 3, oracle.is_valid() + DiscriminatingGenerator)
- `conacq/algorithms/quacq/discriminating_generator.py` — DiscriminatingGenerator (NEW, 66 LOC, C_L[Y] + BG)
- `conacq/example_generators/query_provider.py` — QueryProvider handles both pool-based and SAT-based query generation

## FindScope (Algorithm 2)

Finds the scope (variable set) of a violated constraint using a QuickXPlain-like technique — binary split on variable set, ask partial queries on each half via oracle.is_valid().

**Implementation Details** (commit 260228 - SAT-based bias pruning):
- Uses `oracle.is_valid(partial)` for membership queries on variable subsets
- All partial queries recorded via `record_query(partial, answer, 'findscope')` callback
- **NEW: Bias pruning uses SAT-based consistency checking** via `checker.is_consistent(base + [c_id])`
  - For each constraint in remaining_bias: check if partial assignment + constraint is UNSAT
  - Prune constraints that are inconsistent with partial assignment
- Paper-aligned: membership queries only, no discriminating examples needed
- **DI Pattern**: Receives oracle, ConsistencyChecker, and model at construction

**Process**:
1. Start with all variables in scope candidate
2. Binary search: split variables in half
3. Ask partial query on each half via oracle
4. Recurse on half that caused violation
5. Converge to minimal scope
6. Prune rejecting constraints from bias during search

- **Complexity:** O(|S| * log|X|) queries per call

## FindC (Algorithm 3)

After scope `Y` is found, identifies the specific constraint violated by generating discriminating examples from C_L[Y] (learned KB restricted to scope) + BG clauses.

**Implementation Details** (commit 260228 - SAT-based rejection filtering):

**Constraint Filtering** (NEW):
- **Scope matching**: Find bias constraints whose scope matches Y (prefer exact, fallback to subset)
- **SAT-based rejection**: Filter candidates using `checker.is_consistent(base + [c_id] + config_assumptions)`
  - A constraint is rejected if assuming it makes the partial assignment UNSAT
  - Narrows candidates to only those consistent with negative example e

**DiscriminatingGenerator** (commit 260227):
- Generates discriminating examples from C_L[Y] + BG, NOT from FM clauses (ground truth)
- Paper Algorithm 3 line 5: find e' in sol(BG + C_L[Y]) s.t. e' |= c_i, e' |/= c_j
- SAT formula: BG + C_L[Y] + c_i + neg(c_j)
- Returns config dict or None if UNSAT

**Query Recording**:
- All queries recorded via `record_query(config, answer, 'findc')` callback

**DI Pattern** (commit 260228):
- Receives oracle, ConsistencyChecker, model, and optional DiscriminatingGenerator at construction
- SAT-based rejection filtering replaces raw clause violation checks
- No longer accepts example_provider or query_mode params

**Process**:
1. Collect constraints matching scope (exact match preferred, fallback to subset)
2. Filter to constraints that actually reject example e
3. Use DiscriminatingGenerator to narrow candidates via discriminating examples
4. Return first remaining candidate

- **Complexity:** O(|Gamma|) queries per call

## Complexity Analysis

| Component | Queries |
|---|---|
| Find target network or collapse | O(\|C_T\| * (log\|X\| + \|Gamma\|)) |
| Prove convergence | O(\|B\|) |
| FindScope per call | O(\|S\| * log\|X\|) |
| FindC per call | O(\|Gamma\|) |

## Optimality

- **Optimal** on language `{=, !=}` with Boolean domain → O(n log n) queries
- **Not optimal** on language `{<}` — QuAcq needs Omega(n log n) while O(n) is achievable

## Experimental Results (Paper)

| Benchmark | \|C_L\| | #queries | avg query size | time/query |
|---|---|---|---|---|
| Random (50 vars, sparse) | 12 | 196 | 24 | 0.23s |
| Random (50 vars, dense) | 86 | 1074 | 14 | 0.14s |
| Golomb-8 | 91 | 488 | 5 | 0.32s |
| Zebra | 62 | 656 | 8 | 0.10s |
| Sudoku 9x9 | 810 | 8645 | 21 | 0.16s |

## Key Advantages

1. **Partial queries** — shorter, easier for users to answer
2. **No positive examples needed** — unlike Conacq.1 and ModelSeeker
3. **Fast query generation** — uses heuristics (max-1, sol), no expensive optimization
4. **Scalable** — queries grow logarithmically with |B|
5. **Usable as solver** — stop when a complete positive example is found
6. **Batch mode** (NEW) — Example-based learning with FindScope/FindC requires no oracle

## Query Generation (QueryProvider)

Unified `QueryProvider` class (conacq/example_generators/query_provider.py) merges pool-based and SAT-based strategies with injected ConsistencyChecker.

**Architecture** (NEW: commit 260228):
- **No ad-hoc solver creation**: QueryProvider uses injected `checker` + `model` parameters
- **ConsistencyChecker protocol**: Both conditions (satisfies KB+BG, violates bias) use `checker.is_consistent()`
- **SAT model extraction**: `checker.get_model()` returns parsed SAT assignment for config generation
- **Assumption-based filtering**: All SAT queries use assumption IDs for KB, BG, and bias constraints

**Constructor** (NEW):
```python
QueryProvider(
    pool: Optional[List[Dict[str, bool]]] = None,
    seed: Optional[int] = None,
    checker: ConsistencyChecker = None,  # Injected (NEW)
    model: QuAcqModel = None,            # Injected for config_to_assumptions (NEW)
    profiler_instance: AbstractProfiler = None
)
```

**Three methods** mapping to three modes:
- `generate_from_pool(remaining_bias, learned_kb, set_b)` → `example_only` mode
  - Condition 1: `checker.is_consistent(C_L + BG + config_assumptions)` (satisfies KB+BG)
  - Condition 2: `checker.is_consistent([c_id] + config_assumptions)` (violates bias constraint)
- `generate_from_sat(remaining_bias, learned_kb, set_b, negation_map, id_to_feature)` → `oracle` mode
  - For each remaining constraint c_id: `checker.is_consistent(C_L + BG + [neg(c_id)])`
  - Extract model: `model_lits = checker.get_model()` → convert to config dict
- `generate(remaining_bias, learned_kb, set_b, negation_map, id_to_feature)` → `example_first` mode
  - Try pool first, fallback to SAT

**SAT Heuristics** (in generate_from_sat):
- **max-1**: Find solution of `C_L` maximizing violated constraints in `B` (1s cutoff) — NO LONGER IMPLEMENTED
- **sol**: Find first solution of `C_L` violating at least 1 constraint in `B` (cheapest) — CURRENT HEURISTIC

**Pool Filtering** (paper Algorithm 1 condition):
- Query `e` must satisfy C_L ∪ BG ∪ config_assumptions: `checker.is_consistent(C_L + BG + config_assumptions)`
- Query `e` must violate ≥1 constraint in remaining bias: `not checker.is_consistent([c_id] + config_assumptions)`

## Relation to Codebase

**Core Implementation**:
- `conacq/algorithms/quacq/quacq.py` — QuAcq algorithm + QuAcqResult (DI pattern, mode dispatch, assumption-based learn())
- `conacq/algorithms/quacq/sat_utils.py` — Shared SAT utilities (config/scope conversion, consistency pruning, constraint clause extraction)
- `conacq/algorithms/quacq/findscope.py` — FindScope (Algorithm 2, 134 LOC, oracle.is_valid() instead of SAT)
- `conacq/algorithms/quacq/findc.py` — FindC (Algorithm 3, oracle.is_valid() + DiscriminatingGenerator narrowing)
- `conacq/algorithms/quacq/discriminating_generator.py` — DiscriminatingGenerator (66 LOC, C_L[Y] + BG)
- `conacq/algorithms/quacq/quacq_model.py` — QuAcqModel (dual to ConGenModel) for interactive learning
- `conacq/algorithms/quacq/quacq_model_builder.py` — QuAcqModelBuilder (fluent builder, auto-prepares on build())
- `conacq/algorithms/quacq/task_preparation.py` — QuAcqTask + QuAcqTaskPreparation (inherited from DiagnosisTask)

- `conacq/oracle/` — Oracle implementations: FMOracle, UserPromptOracle, CachedOracle, OracleData, BGData
- `conacq/example_generators/` — QueryProvider: unified pool + SAT query generation (query_provider.py)

**Evaluation Support**:
- `conacq/eval/folds.py` — Shared CV fold generation for CONGEN/QuAcq comparison
- `conacq/runners/quacq_runner.py` — QuAcq pipeline runner (238 LOC, moved from eval/)
- `conacq/eval/cross_validation.py` — Cross-validation framework (424 LOC)
- `apps/generate_cv_folds.py` — CLI to pre-generate folds (68 LOC)

**Two Paradigms** (Now Unified via Assumption IDs):

1. **CONGEN** (passive): Learns from E+/E- in one batch pass (GenerateNE → ACQMSS → REDUCE)
   - **GenerateNE called internally by `ConGenModel.prepare_task()`** (not by callers)
   - Uses `ConGenTask` (assumption-based constraint IDs)
   - Immutable checkers after construction

2. **QuAcq** (active/interactive): Two modes via `QuAcqModel` + `QuAcqTask`
   - **Oracle mode**: Queries user via GenerateQuery
     - `QuAcq.learn(oracle_mode='automated'/'interactive')`
     - Real-time user interaction via oracle
   - **Example mode**: Learns from pre-collected E+/E- using FindScope/FindC (no oracle)
     - `QuAcq.learn_from_examples(positive_examples, negative_examples)`
     - Fair comparison via shared CV folds
   - **Shared Infrastructure**: Both modes use `QuAcqModel` + `QuAcqTask` with assumption IDs

**Key Architectural Change** (commit 260226):
- **Assumption-Based ID Representation**: Both ConGen and QuAcq now use **int assumption IDs** exclusively
- **ConGenTask** — CONGEN constraints identified by assumption IDs
- **QuAcqTask** — QuAcq constraints identified by assumption IDs (parallel to ConGenTask)
- **Enables Symmetry**: QuAcq and ConGen share identical SAT-based semantics via assumption literals

**Query History Source Tagging** (NEW):

QuAcqRunner.run() now tracks source of each query for progressive evaluation:
- `record_query(config, answer, source='main')` — Tag query as 'main' or 'findc'
- `query_history: List[Tuple[Dict, bool, str]]` — 3-tuple with source tag
- `QuAcqRunResult.query_history` — Propagates query history with tags
- Use case: ProgressiveEvaluator filters main-loop queries for ConGen comparison

```python
# Query history format
quacq_result = quacq_runner.run(mode='automated')
for config, answer, source in quacq_result.query_history:
    if source == 'main':
        # Main learning loop query
    elif source == 'findc':
        # FindC discrimination query
```

**Assumption ID Architecture** (Current):

QuAcq mirrors ConGen's assumption-based design. Both use `prepare_kb()` to assign int assumption IDs:

```
Assumption ID Layout (shared between ConGen and QuAcq):
  Part 1: Root feature assumption IDs (from Oracle FM)
  Part 2: Root feature negated assumptions (from Oracle FM)
  Part 3: BG constraint pair (root + negated, from Oracle BGData)
  Part 4: Tseitin variables (for negation encoding)
  Part 5: Bias constraint pairs (original + negated) [QuAcq]
  Part 6: NE pairs (original + negated) [ConGen, from GenerateNE]

Key Classes (in conacq/algorithms/quacq/):
- QuAcqTask(DiagnosisTask): Pure data container for interactive learning state (no methods)
  - Inherited from DiagnosisTask: set_kb, assumptions, set_b, set_c, negation_map
  - Interactive-specific fields:
    - bias: Set[int] — Remaining bias constraint assumption IDs
    - learned_kb: List[int] — Discovered constraint assumption IDs
    - background_clauses: List[List[int]] — Raw BG CNF (no guards; for SAT violation checking)
    - constraint_clauses: Dict[int, List[List[int]]] — Constraint CNF by assumption ID
    - negated_clauses: Dict[int, List[List[int]]] — Negated constraint CNF by assumption ID
    - feature_ids: Dict[str, int] — Feature name → SAT variable ID
    - id_to_feature: Dict[int, str] — SAT variable ID → feature name
  - **Note**: Behavior (algorithms) moved to sat_utils.py standalone functions, not task methods
- QuAcqModel: QuAcq dual to ConGenModel (quacq_model.py)
- QuAcqModelBuilder: Fluent builder, auto-prepares on build() (quacq_model_builder.py)
- QuAcqTaskPreparation: Prepares QuAcqTask via prepare_kb() (task_preparation.py)

```

**Inheritance Pattern** (Refactored):
- **DiagnosisTask** (Base): Common assumption-based fields
  - `set_kb: List[List[int]]` — CNF clauses with assumption literals
  - `assumptions: List[int]` — All possible assumption IDs
  - `set_b: List[int]` — Background knowledge assumption IDs
  - `set_c: List[int]` — Bias assumption IDs
  - `negation_map: Dict[int, int]` — Mapping: original_id → negated_id
- **QuAcqTask(DiagnosisTask)** (Derived): Interactive learning specifics
  - All inherited fields from DiagnosisTask
  - Adds interactive state: bias (Set[int]), learned_kb (List[int])
  - Adds raw clause storage: background_clauses, constraint_clauses, negated_clauses
  - Adds feature mapping: feature_ids, id_to_feature

**Field Semantics** (Consistent with ConGen):
- `set_b: List[int]` — Assumption IDs for background knowledge constraints
  - Used for KB operations in SAT-based queries
- `background_clauses: List[List[int]]` — Raw CNF clauses (without assumption guards)
  - Extracted from Oracle's BG constraint data
  - Used for violation detection and SAT discrimination paths
  - Fixes: Correct interpretation of assumptions vs. clause structures

**Shared Infrastructure**:
- Both use same SAT solvers (IncrementalPySATChecker, NonIncrementalPySATChecker)
- Both use same FM representation and bias generation pipeline
- Both use same evaluation framework (cross_validation, accuracy metrics)
- Fair comparison via shared CV folds (folds.py)
- Both support n-fold cross-validation with pre-generated folds
- Constraint name resolution moved to runner layer (QuAcqRunner.resolve_kb() pattern)

## Oracle Implementations

**Base Classes** (conacq/oracle/base.py):
- `Oracle` — Abstract base class for configuration validators

**Concrete Oracles** (conacq/oracle/):
- `FMOracle` — FM-based oracle using flamapy (fm_oracle.py)
- `UserPromptOracle` — Interactive user oracle (prompts on command line) (user_prompt.py)
- `CachedOracle` — Caching wrapper to avoid re-asking same query (cached.py)

**Query Generation** (conacq/example_generators/):
- `QueryProvider` — Unified query provider: pool-filtered + SAT-based strategies (query_provider.py) (commit 260228)
  - Uses injected `checker` (ConsistencyChecker) + `model` (QuAcqModel) for all SAT operations
  - `generate_from_pool()`: Pool iteration with paper condition via `checker.is_consistent()`
  - `generate_from_sat()`: SAT-based generation via `checker.is_consistent()` + `checker.get_model()`
  - `generate()`: Combined pool-first + SAT fallback
  - No longer creates ad-hoc solvers: all SAT checks delegated to injected checker

**ConsistencyChecker Integration** (NEW):
- **get_model()**: Abstract method in ConsistencyChecker, returns `Optional[List[int]]`
- Implementations (IncrementalPySATChecker, NonIncrementalPySATChecker) return SAT model after satisfiable check
- QueryProvider calls `checker.get_model()` to extract assignment and convert to feature config
- Enables decoupling query generation from solver implementation details

**Critical**: Feature ID consistency
- Uses flamapy's variable mapping (tree traversal order) as authoritative source
- Ensures feature_ids match SAT variable IDs in CNF clauses
- Alphabetical sorting would cause critical mismatch between Oracle and SAT solver
- `id_to_feature: Dict[int, str]` maps SAT variables → feature names for config generation

## Removed Classes (Deleted This Session)

The following classes are **no longer available**:

| Class | Replacement | File Deleted | Reason |
|-------|-------------|--------------|--------|
| `InteractiveTask` | `QuAcqTask` | `task.py` | String-based constraint names; QuAcqTask uses assumption IDs |
| `InteractiveLearner` | `QuAcqModelBuilder` + `QuAcq` | `learner.py` | High-level facade; use builder pattern instead |
| `InteractiveResult` (alias) | `QuAcqResult` | `result.py` | Merged into `quacq.py` |

**Recommended Pattern** (DI-based, post-refactor, commit 260228):
```python
from conacq.algorithms.quacq import QuAcqModelBuilder, QuAcq, DiscriminatingGenerator
from conacq.algorithms.quacq.task_preparation import QuAcqTaskInput
from conacq.example_generators import QueryProvider
from conacq.oracle import FMOracle
from explanation.api import build_checker, SolverBackend
from profiling import get_global_profiler

# Build model (unprepared — prepare_task is pure, called per run)
oracle = FMOracle('data/fms/model.uvl')
model = (QuAcqModelBuilder
         .from_bias('data/bias/model.json')
         .with_oracle_data(oracle.oracle_data)
         .build())

# Pure prepare: model keeps no task; `prepared` holds task + describe + assignment_map
prepared = model.prepare_task(QuAcqTaskInput(oracle.oracle_data))
task = prepared.task
profiler = get_global_profiler()

# Checker built from the Task
checker = build_checker(task, SolverBackend.from_flags(use_incremental=True))

# DI wiring (mirrors conacq/algorithms/quacq/__init__ example + QuAcqRunner._run_oracle_mode)
query_provider = QueryProvider(assignment_map=prepared.assignment_map)
discrim_gen = DiscriminatingGenerator(
    checker=checker, model=model, profiler=profiler,
    root_assumption=task.set_b[0], task=task)
quacq = QuAcq.for_oracle(checker, oracle, query_provider, discrim_gen, model=model,
                         task=task, assignment_map=prepared.assignment_map)

# Run learning — real signature: set_c, set_b, negation_map, mode, max_queries (quacq.py:114-120)
result = quacq.learn(
    set_c=task.set_c, set_b=task.set_b,
    negation_map=task.negation_map, mode='oracle', max_queries=1000)

# Runner layer resolves constraint names — describe comes from the PreparedTask
kb_names, kb_clauses = model.resolve_kb(prepared.describe, result.kb_assumption_ids)
print(f"Learned KB: {kb_names}")
print(f"Queries: {result.n_queries}")
```

**Example-Based Mode**:
```python
from conacq.example_generators import QueryProvider
from explanation.api import build_checker, SolverBackend

# Build checker from the task (from `prepared.task` above)
checker = build_checker(task, SolverBackend.from_flags(use_incremental=True))

# QueryProvider with pool for example-based learning (injected dependencies)
query_provider = QueryProvider(
    pool=examples_list,
    seed=42,
    checker=checker,    # Injected (NEW)
    model=model         # For config_to_assumptions (NEW)
)

quacq = QuAcq.for_examples(checker, oracle, query_provider, discrim_gen=None)

# Run with pool only (no SAT, no discriminating generator needed)
result = quacq.learn(..., mode='example_only', ...)

# Or pool + SAT fallback (requires discriminating generator)
query_provider_mixed = QueryProvider(
    pool=examples_list,
    seed=42,
    checker=checker,
    model=model
)
quacq_mixed = QuAcq.for_examples(checker, oracle, query_provider_mixed, discrim_gen=discrim_gen)
result = quacq_mixed.learn(..., mode='example_first', ...)
```

**QuAcqResult Representation** (NEW: Algorithm returns IDs only):
- `kb_assumption_ids: List[int]` — Primary: learned constraints as assumption IDs (from algorithm)
- `kb_constraints: List[str]` — Secondary: resolved names (populated by runner via `model.resolve_kb()`)

Pattern matches ConGen: algorithm returns assumption IDs, runner resolves names.

## Cross-Validation Support

Both CONGEN and QuAcq support n-fold cross-validation with shared infrastructure:

```python
# Shared fold generation and loading
from conacq.eval.folds import generate_folds, load_folds, save_folds

# Pre-generate folds once for reproducible evaluation
folds = generate_folds(E_plus, E_minus, n_splits=5, seed=42)
save_folds(folds, 'data/cv_folds.json')

# Load same folds for both ConGen and QuAcq
fold_data = load_folds('data/cv_folds.json')

# Fair comparison: both algorithms use identical train/test splits
congen_results = cross_validation_congen(..., fold_data=fold_data)
quacq_results = cross_validation_interactive(..., fold_data=fold_data)
```

**Key Features**:
- Per-fold bias shuffling (shuffle_seeds in FoldData)
- Query mode control: `example_only` or `example_first` (SAT fallback)
- Convergence tracking (query count, termination reason)
- Intersected KB (consensus across folds)

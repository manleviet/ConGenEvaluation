# ConGen - Constraint Acquisition With Maximum Satisfiable Subsets

**Last Updated**: 2026-02-18

**Paper:** Leviet M. — MSS-based Passive Constraint Acquisition for Feature Models

## Overview

ConGen — passive/batch learning algorithm that acquires constraint networks from positive and negative example configurations. Unlike interactive approaches (QuAcq), ConGen requires **no user interaction**: given a set of valid (E+) and invalid (E-) examples, it finds a Maximum Satisfiable Subset (MSS) of a constraint bias B that accepts all E+ and rejects all E-.

**Key idea**: Start with a large bias B (all candidate constraints), then systematically remove constraints that conflict with positive examples while preserving those needed to reject negative examples.

**Pipeline**: `GenerateNE` (negate E-) → `AcqMSS` (find MSS of B) → `REDUCE` (remove redundant constraints)

## Formal Definitions

### Definition 1: Vocabulary

A **vocabulary** (V, D) consists of a finite set of variables V = {x1, ..., xn} and a set of domains D = {D(x1), ..., D(xn)} where each D(xi) is a finite set of values.

### Definition 2: Constraint Theory

A **constraint theory** C = {c1, ..., cm} is a conjunction of constraints where each ci is a relation over a subset of V.

### Definition 3: Target Constraint Theory

The **target constraint theory** C_T is the (unknown) ground truth that the algorithm attempts to learn.

### Definition 4: Constraint Language

A **constraint language** L defines the set of allowed constraint types (e.g., implications, mutual exclusions, conjunctions).

### Definition 5: Constraint Bias

The **bias** B is the set of all candidate constraints generated from language L over vocabulary V. B is a superset of C_T.

### Definition 6: Constraint Acquisition Problem

Given:
- Bias B (candidate constraints from L)
- Background knowledge BG (known constraints)
- Training examples E = E+ ∪ E- (valid and invalid configurations)

**Find**: KB ⊆ B such that:
- KB **accepts** all e+ ∈ E+ (consistent with positive examples)
- KB **rejects** all e- ∈ E- (inconsistent with negative examples)

## Working Example

From the paper — 3 Boolean variables representing feature model selections.

### Variables (Table 1)

| Variable | Meaning |
|----------|---------|
| id | Feature "id" |
| db | Feature "db" |
| ga | Feature "ga" |

### Target Theory (Table 2)

| Constraint | Meaning |
|-----------|---------|
| id → db | Selecting id requires db |
| id NOT_AND ga | id and ga are mutually exclusive |

### Bias B (Table 3)

18 binary constraints (c1..c18): all combinations of {→, AND, NOT_AND} over {id, db, ga} pairs:

| # | Constraint | # | Constraint | # | Constraint |
|---|-----------|---|-----------|---|-----------|
| c1 | id → db | c7 | id → ¬ga | c13 | db → ¬ga |
| c2 | db → id | c8 | ga → ¬id | c14 | ga → ¬db |
| c3 | id ∧ db | c9 | ¬id ∧ ¬ga | c15 | ¬db ∧ ¬ga |
| c4 | ¬id ∧ ¬db | c10 | id ∧ ga | c16 | db ∧ ga |
| c5 | id → ¬db | c11 | id ∧ ¬ga | c17 | db ∧ ¬ga |
| c6 | db → ¬id | c12 | ¬id ∧ ga | c18 | ¬db ∧ ga |

### Training Set (Table 4)

| Type | Example | Meaning |
|------|---------|---------|
| E+ | {¬id, ga} | Valid: ga selected, id not selected |
| E+ | {id, db, ¬ga} | Valid: id and db selected, ga not |
| E- | {id, ¬db} | Invalid: id without db |

### Background Knowledge (Table 5)

| Constraint | Meaning |
|-----------|---------|
| ga → db | Selecting ga requires db |

### ConGen Execution (Table 6)

1. **GenerateNE**: NE = {¬(id ∧ ¬db)} — negation of negative example
2. **IsConsistent check**: Verify E+ ∪ NE ∪ BG is consistent → yes, proceed
3. **AcqMSS**: Divide-and-conquer on B, returns B' = {c7, c12, c13, c18}
4. **REDUCE**: Test each constraint for redundancy
   - c18 (¬db ∧ ga) is redundant given BG ∪ {c7, c12, c13} → removed
5. **Result**: KB = {c7, c12, c13} = {id → ¬ga, ¬id ∧ ga, db → ¬ga}

## Algorithm Pipeline

ConGen orchestrates three sub-algorithms in sequence:

### Algorithm 1: ConGen(E+, E-, B, BG)

```
Input:  E+ (positive examples), E- (negative examples),
        B (constraint bias), BG (background knowledge)
Output: KB (learned knowledge base)

1: NE ← GenerateNE(E-)
2: B' ← ∅
3: if IsConsistent(E+, NE, BG) then
4:     B' ← AcqMSS(∅, B, NE, E+, BG)
5: else
6:     print "examples inconsistent"
7:     return ∅
8: end if
9: return REDUCE(B', NE, BG)
```

**Line 3 check**: If positive examples conflict with negated negative examples under BG, the training set itself is inconsistent — no valid KB exists.

## GenerateNE

Converts negative examples E- into NE constraints that the KB must satisfy.

**Process**:
1. For each e- ∈ E-: create ¬(e-) as a constraint
2. Use QuickXPlain to find minimal conflict set per negative example
3. Each NE constraint ensures the KB rejects the corresponding e-

**Subset minimality**: Assumes negative examples are subset-minimal — no proper subset of an e- is also negative.

**Implementation**: `conacq/algorithms/acqmss/generate_ne.py` — Pure function returning `NEPerTestcase` list (138 LOC)
- Called internally by `ConGenModel.prepare_task()`, not by callers directly
- Uses QuickXPlain from `explanation/operations/algorithms/quickxplain.py` (80 LOC, in canonical `../explanation`)

## AcqMSS (Algorithm 2)

Finds a Maximum Satisfiable Subset of B — the largest subset that remains consistent with E+ ∪ NE ∪ BG. Uses divide-and-conquer strategy inspired by KBDiag.

### Algorithm 2: AcqMSS(delta, B={c1..cn}, NE, E+, BG)

```
Input:  delta (recently added constraints), B (current bias subset),
        NE (negated examples), E+ (positive examples), BG (background)
Output: B' ⊆ B (maximum satisfiable subset)

1:  if delta ≠ ∅ then
2:      if IsConsistent(NE, E+, B, BG) then
3:          return B
4:      end if
5:  end if
6:  if |B| = 1 then
7:      return ∅
8:  end if
9:  k = ⌊|B|/2⌋
10: B1 = {c1, ..., ck}
11: B2 = {ck+1, ..., cn}
12: B'_beta  ← AcqMSS(B1, B1, NE, E+, BG)
13: B'_alpha ← AcqMSS(B1 − B'_beta, B2, NE, E+, BG ∪ B'_beta)
14: return B'_alpha ∪ B'_beta
```

**Key mechanics**:
- **Line 2**: Early termination — if adding delta doesn't cause inconsistency, keep all of B
- **Lines 9-11**: Binary split of B into two halves
- **Line 12**: Recursively find MSS of first half
- **Line 13**: Find MSS of second half, with first half's MSS added to BG
- **Lines 6-8**: Base case — single constraint that causes inconsistency is removed

**Implementation**: `conacq/algorithms/acqmss/acqmss.py` — `AcqMSS.find_mss()` (104 LOC)
- Uses KBDiag from `explanation/operations/algorithms/kbdiag.py` (100 LOC, in canonical `../explanation`)

## REDUCE (Algorithm 3)

Eliminates redundant constraints from B' ∪ NE. A constraint c is **redundant** if BG ∪ (KB − {c}) logically entails c.

### Algorithm 3: REDUCE(B', NE, BG)

```
Input:  B' (MSS from AcqMSS), NE (negated examples), BG (background)
Output: KB (reduced knowledge base)

1: KB ← B' ∪ NE
2: for ci ∈ KB do
3:     if IsInconsistent(BG ∪ (KB − {ci}) ∪ {¬ci}) then
4:         KB ← KB − {ci}
5:     end if
6: end for
7: return KB
```

**Line 3 logic**: If adding ¬ci to the remaining KB causes inconsistency, then KB − {ci} already entails ci, so ci is redundant.

**Implementation**: `conacq/algorithms/acqmss/reduce.py` — `Reduce.reduce()` (155 LOC)
- Uses `negation_map` (Dict[int, int]) mapping assumption ID → negated form
- Tseitin encoding used to negate CNF clauses

## Complexity Analysis

### AcqMSS Complexity

| Metric | Best Case | Worst Case |
|--------|-----------|------------|
| Consistency checks | log2(n/γ) + 2γ | 2γ · log2(n/γ) + 2γ |

Where:
- n = number of constraints in B
- γ = number of elements deleted from B (conflicts removed)

### Conflict Determination

| Metric | Best Case | Worst Case |
|--------|-----------|------------|
| Consistency checks | log2(n/γ) + 2π | 2γ · log2(n/γ) + 2π |

Where π = assumed conflict set size.

### REDUCE Complexity

- Linear in |KB|: one IsInconsistent call per constraint
- Each call tests BG ∪ (KB − {ci}) ∪ {¬ci}

## Correctness and Completeness

### Theorem 1 (Correctness)

Let B' ⊆ B be returned by AcqMSS. Then B' **accepts all positive examples**:
- ∀e+ ∈ E+: IsConsistent({e+} ∪ NE ∪ BG ∪ B') = true

**Proof sketch**: AcqMSS only activates if IsConsistent(E+ ∪ NE ∪ BG). It incrementally aggregates B'_beta into BG, maintaining the invariant: ∀e+ ∈ E+: consistent({e+} ∪ NE ∪ BG ∪ B'_beta).

### Theorem 2 (Completeness)

If ∀e+ ∈ E+: IsConsistent({e+} ∪ NE ∪ BG), ConGen returns B' ⊆ B.

- Worst case: B' = ∅ (all constraints conflict with some e+)

### Corollary 1

AcqMSS fails bias reduction iff ∃e+ ∈ E+: ¬IsConsistent({e+} ∪ NE).

### Remark 1

If B' = ∅, ConGen returns only NE derived from E-. The learned KB contains only negated negative examples.

## Experimental Setup

### Oracle-Based Evaluation

Feature model knowledge bases published on UVLHub (Romero-Organvidez et al. 2024, JSS 216:112150;
see `data/fms/SOURCES.md`) serve as oracle:
- Root feature constraint → background knowledge BG
  (BG is the root constraint alone, not the hierarchy: see `conacq/oracle/bg_data.py`.
  The distinction matters for how recall is read — everything above the root is
  learned, not assumed.)
- Component requirements/incompatibilities → bias B
- FM solver validates configurations against target C_T

### Sampling Methods

| Method | Description | Coverage |
|--------|-------------|----------|
| RS (Random Sampling) | Random valid/invalid configurations | Statistical |
| 2-COV (Pairwise Coverage) | All pairwise feature combinations | Systematic |
| FF (Feature Frequency) | Feature frequency balanced | Balanced |

### Example Sizes

| Size | Definition |
|------|-----------|
| n | Number of features |
| 2n | Twice number of features |
| 3n | Three times number of features |
| m | Minimum valid configs including all pairs |

### Evaluation Methodology

- **n-fold cross-validation**: Train on (n-1) folds, test on 1 fold
- **Accuracy**: (TP + TN) / (TP + TN + FP + FN)
- **TP**: Correctly accepted positive example
- **TN**: Correctly rejected negative example
- **FP**: Incorrectly accepted negative example
- **FN**: Incorrectly rejected positive example

## Key Advantages

1. **Passive learning** — no user interaction required, fully automated
2. **Partial examples supported** — works with incomplete configurations
3. **Divide-and-conquer efficiency** — logarithmic consistency checks
4. **MSS guarantees** — accepts all positive examples by construction (Theorem 1)
5. **Redundancy elimination** — REDUCE removes logically entailed constraints
6. **Oracle integration** — automated evaluation via FM knowledge bases
7. **Batch processing** — process all examples in one pass

## Relation to Codebase

### Core Implementation

| File | LOC | Purpose |
|------|-----|---------|
| `conacq/algorithms/acqmss/congen.py` | 149 | Main ConGen algorithm (Algorithm 1) |
| `conacq/algorithms/acqmss/acqmss.py` | 104 | AcqMSS MSS finding (Algorithm 2) |
| `conacq/algorithms/acqmss/reduce.py` | 104 | REDUCE redundancy elimination (Algorithm 3) |
| `conacq/algorithms/acqmss/generate_ne.py` | 138 | GenerateNE negative example processing |
| `conacq/algorithms/acqmss/task_preparation.py` | 239 | ConGenTaskPreparation setup |
| `conacq/algorithms/acqmss/congen_model.py` | 257 | ConGenModel data container |
| `conacq/algorithms/acqmss/congen_model_builder.py` | 162 | Builder for ConGenModel construction |

### Supporting Infrastructure

| File | LOC | Purpose |
|------|-----|---------|
| `conacq/bias/` | ~1,176 | BiasGenerator, ClauseGenerator |
| `conacq/example_generators/` | ~1,097 | RS, FF, 2-COV sampling strategies |
| `conacq/oracle/` | ~1,090 | role protocols, FMOracle, OracleData/BGData |
| `conacq/eval/cross_validation.py` | 504 | n-fold cross-validation framework |
| `conacq/runners/congen_runner.py` | 235 | ConGenRunner pipeline (moved from eval/) |
| `conacq/eval/accuracy.py` | 170 | AccuracyCalculator metrics |

### SAT Solver Layer (Canonical `../explanation` Package)

| File | LOC | Purpose |
|------|-----|---------|
| `explanation/operations/algorithms/quickxplain.py` | 80 | QuickXPlain (used by GenerateNE) |
| `explanation/operations/algorithms/kbdiag.py` | 100 | KBDiag (used by AcqMSS) |
| `explanation/checker/protocols.py` | 62 | Consistency-checker **port** (`ConsistencyChecker`/`TestCaseChecker`/`CopyableChecker` Protocols) |
| `explanation/checker/backend.py` | 296 | Solver **adapters** (`CheckerBase` + PySAT/SAT4J checkers) + `build_checker` construction door |

## Implementation Details Beyond Paper

1. **ConGenModel.prepare_task()**: Runs GenerateNE internally — callers don't invoke it separately
2. **Builder pattern**: `ConGenModelBuilder` encapsulates file loading + model construction (auto-prepares if oracle+examples set)
3. **Checker building**: Task passed to `build_checker(task, backend=...)` (from `explanation.api`) to create solver instance
4. **Assumption-based representation**: All data as `List[int]` assumption IDs, solver mode-agnostic
5. **negation_map**: `Dict[int, int]` maps assumption ID → negated form for REDUCE
6. **Tseitin encoding**: Used to negate CNF clauses for REDUCE redundancy checks
7. **BGData extraction**: Post-preparation, `FMOracleModel.get_bg_data()` returns frozen dataclass with root constraint + negation map
8. **CV fold reuse**: `model.prepare_task(task_input)` supports multiple fold evaluations (pure per-fold)
9. **Profiler integration**: `@measure_time`, `@count_calls` decorators on all algorithm methods

## Shared Infrastructure with QuAcq

ConGen and QuAcq share significant infrastructure:

| Component | Shared Module | Usage |
|-----------|--------------|-------|
| SAT solvers | `explanation/operations/algorithms/` (canonical `../explanation`) | IncrementalPySATChecker, NonIncrementalPySATChecker |
| FM representation | `explanation/transformations/` (canonical `../explanation`) | FM → SAT conversion pipeline |
| Bias generation | `conacq/bias/` | Same BiasGenerator for both paradigms |
| Oracle | `conacq/oracle/` | role protocols, FMOracle, OracleData/BGData |
| Evaluation | `conacq/eval/` | Same accuracy metrics and cross-validation |
| CV folds | `conacq/eval/folds.py` | Pre-generated folds for fair comparison |
| Feature IDs | flamapy tree traversal | Authoritative variable mapping (NOT alphabetical) |

**Two paradigms, one framework**:
- **ConGen** (passive): E+/E- → GenerateNE → AcqMSS → REDUCE → KB
- **QuAcq** (active): GenerateQuery → Oracle → Update KB → Repeat → REDUCE

## Cross-Validation Support

ConGen supports n-fold cross-validation with shared folds for fair comparison with QuAcq:

```python
from conacq.algorithms.congen import ConGenModelBuilder
from conacq.oracle import FMOracle
from conacq.eval.folds import load_folds
from conacq.eval.cross_validation import n_fold_cross_validation

# Load pre-generated folds (shared with QuAcq)
fold_data = load_folds('data/cv_folds.json')

# Build model (auto-prepare: oracle + examples passed at build time)
oracle = FMOracle('data/fms/model.uvl')
model = (ConGenModelBuilder
    .from_bias('data/bias/model.json')
    .with_oracle(oracle)
    .with_examples('data/examples/examples.json')
    .build())

# Run cross-validation
results = n_fold_cross_validation(model, fold_data=fold_data, n_splits=5)
```

**Key features**:
- Per-fold bias shuffling (shuffle_seeds in FoldData)
- Shared folds with QuAcq for fair comparison via `folds.py`
- Accuracy, precision, recall, F1 per fold and aggregated
- CSV/JSON/LaTeX export of results

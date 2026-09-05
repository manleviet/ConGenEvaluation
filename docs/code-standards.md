# AcqMSS Code Standards & Guidelines

**Last Updated**: 2026-02-28 (QuAcq DescriptionProvider refactoring: removed from learn(), pattern now matches ConGen)

## Language & Environment

- **Primary Language**: Python 3.13+
- **Type Hints**: Mandatory on all public functions
- **Docstring Style**: Google-style or NumPy (consistent per module)
- **Code Formatting**: ruff check/format
- **Type Checking**: mypy strict mode recommended
- **Testing**: pytest with @parameterized.expand
- **Module File Size**: ~200 lines (max ~300 for complex modules)

## Naming Conventions

### Modules & Files

- **Convention**: `snake_case` for all `.py` filenames
- **Rationale**: Python import convention, improves discoverability with tools (Glob, Grep)
- **Examples**:
  - ✓ `fastdiag.py`, `task_preparation.py`, `random_sampling.py`
  - ✗ `FastDiag.py`, `task-preparation.py` (breaks imports or conventions)

### Classes

- **Convention**: `PascalCase`
- **Examples**:
  ```python
  class FastDiag:          # Algorithm
  class DiagnosisModel:    # Data model
  class ConsistencyChecker: # Abstract base
  ```

### Functions & Methods

- **Convention**: `snake_case`
- **Private methods**: Prefix with `_`
- **Examples**:
  ```python
  def acquire(self, task):           # Public
  def _find_mss(self, bias, ne):     # Private
  def is_consistent(self, clauses):  # Query-like
  ```

### Constants & Enums

- **Convention**: `UPPER_SNAKE_CASE` for module-level constants
- **Examples**:
  ```python
  DEFAULT_SOLVER = 'glucose4'
  MAX_SOLVER_CALLS = 10000
  TIMEOUT_SECONDS = 300.0

  class ConstraintType(Enum):
      REQUIRES = 'requires'
      EXCLUDES = 'excludes'
  ```

### Variables

- **Convention**: `snake_case` (local, instance, class)
- **Boolean prefixes**: Prefer `is_`, `has_`, `should_`
- **Examples**:
  ```python
  self.learned_kb = []           # Instance
  is_consistent = checker(task)  # Local boolean
  has_conflict = len(diag) > 0   # Query result
  ```

## File Organization

### Module Structure

```python
"""
Module docstring: Brief description of module purpose.

Longer explanation if needed. May reference related modules.
"""

# Imports (grouped: stdlib → third-party → local)
from __future__ import annotations
from typing import Sequence, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pysat.solvers import Solver
from flamapy.metamodels.fm_metamodel import FeatureModel

from explanation.models import DiagnosisModel
from .data_structures import Constraint

# Constants
DEFAULT_SOLVER = 'glucose4'
TIMEOUT_SECONDS = 300.0

# Classes
class MyAlgorithm(ABC):
    """Public class docstring."""
    pass

# Functions
def acquire(model: DiagnosisModel) -> list[Constraint]:
    """Function docstring with type hints."""
    pass

# Private functions
def _helper_function() -> None:
    """Private function."""
    pass
```

### Import Order

1. **Standard library** (abc, typing, pathlib, etc.)
2. **Third-party** (pysat, flamapy, pytest, etc.)
3. **Local relative** (from . or .. imports)

Use `from __future__ import annotations` for modern type syntax.

## Design Patterns

### 1. Abstract Base Classes (Strategy Pattern)

Used for pluggable solver implementations:

```python
from abc import ABC, abstractmethod

class ConsistencyChecker(ABC):
    """Abstract solver interface."""

    @abstractmethod
    def is_consistent(self, clauses: list[list[int]]) -> bool:
        """Check if clauses are satisfiable."""
        pass

class IncrementalPySATChecker(ConsistencyChecker):
    """Persistent solver with assumptions."""
    def is_consistent(self, clauses):
        # Persistent solver reuses state
        pass

class NonIncrementalPySATChecker(ConsistencyChecker):
    """Fresh solver per call."""
    def is_consistent(self, clauses):
        # Create new solver each time
        pass
```

**Benefits**:
- Testable with mock solvers
- Easy to swap implementations
- Clear contract for new solvers

### 2. Builder Pattern

For complex object construction:

```python
class DiagnosisModelBuilder:
    """Fluent builder for DiagnosisModel."""

    def __init__(self):
        self._feature_model = None
        self._solver_name = 'glucose4'

    def with_feature_model(self, fm: FeatureModel) -> DiagnosisModelBuilder:
        self._feature_model = fm
        return self

    def with_solver(self, name: str) -> DiagnosisModelBuilder:
        self._solver_name = name
        return self

    def build(self) -> DiagnosisModel:
        return DiagnosisModel(self._feature_model, self._solver_name)

# Usage
model = (DiagnosisModelBuilder()
         .with_feature_model(fm)
         .with_solver('glucose4')
         .build())
```

### 3. Facade Pattern

High-level interfaces hiding complexity. QuAcqRunner demonstrates the pattern with name resolution:

```python
from conacq.algorithms.quacq import QuAcqModelBuilder, QuAcq, DiscriminatingGenerator
from conacq.example_generators import QueryProvider
from conacq.oracle import FMOracle

class QuAcqRunner:
    """High-level interface for QuAcq learning (DI-based, returns resolved KB)."""

    def run(self, positive_examples=None, negative_examples=None, mode='oracle'):
        """Learn constraints interactively, resolve names."""
        from explanation.api import build_checker, SolverBackend
        # Pure prepare — the model keeps no task; `prepared` carries the frozen
        # task + describe + assignment_map (quacq_runner.py:167-169).
        prepared = self.model.prepare_task(QuAcqTaskInput(self.oracle.oracle_data))
        task = prepared.task

        # Checker built from the Task; solver mode is the runner's (quacq_runner.py:180-184).
        checker = build_checker(
            task,
            SolverBackend.from_flags(use_incremental=self.use_incremental),
            self.solver_name, profiler)

        # DI wiring (quacq_runner.py:250-263):
        query_prov = QueryProvider(checker=checker, model=self.model,
                                   assignment_map=prepared.assignment_map,
                                   profiler_instance=profiler)
        discrim_gen = DiscriminatingGenerator(
            checker=checker, model=self.model, profiler=profiler,
            root_assumption=task.set_b[0], task=task)
        quacq = QuAcq.for_oracle(checker, self.oracle, query_prov, discrim_gen,
                                 model=self.model, profiler=profiler,
                                 task=task, assignment_map=prepared.assignment_map)

        # Algorithm returns raw assumption IDs. Real learn signature = 3 data
        # params + mode + max_queries (quacq.py:114-120).
        result = quacq.learn(
            set_c=task.set_c, set_b=task.set_b, negation_map=task.negation_map,
            mode=mode, max_queries=self.max_queries)

        # Runner resolves names (matches ConGen pattern)
        kb_names, kb_clauses = self.model.resolve_kb(result.kb_assumption_ids)
        return QuAcqRunResult(
            kb_constraints=kb_names, kb_clauses=kb_clauses,
            n_kb=result.n_kb, n_queries=result.n_queries, ...)

# Usage
oracle = FMOracle('model.uvl')
model = QuAcqModelBuilder.from_bias('bias.json').with_oracle(oracle).build()
runner = QuAcqRunner(bias_path, fm_path)
result = runner.run(mode='oracle')
```

### 4. Template Method Pattern

Base class defines algorithm skeleton, subclasses fill steps:

```python
from abc import abstractmethod

class PySATAbstractHSDAGExplanation(ABC):
    """Template for diagnosis operations."""

    def execute(self) -> list[Diagnosis]:
        """Execute diagnosis algorithm (template method)."""
        solver_instance = self._prepare_solver()
        result = self._diagnose(solver_instance)
        self._finalize(solver_instance)
        return result

    @abstractmethod
    def _diagnose(self, solver) -> list[Diagnosis]:
        """Subclass implements specific algorithm."""
        pass

class FastDiag(PySATAbstractHSDAGExplanation):
    def _diagnose(self, solver):
        # FastDiag-specific implementation
        pass
```

### 5. Dependency Injection

Pass dependencies as constructor parameters and via factories:

**ConGen** (passive learning):
```python
class ConGen:
    """Constraint acquisition via AcqMSS (mode-agnostic)."""

    def __init__(self, checker: ConsistencyChecker, profiler: Optional[Profiler] = None):
        self.checker = checker  # Injected (Incremental or NonIncremental)
        self.profiler = profiler or NullProfiler()

    def acquire(
            self,
            set_b: List[int],  # Bias assumption IDs
            set_bg: List[int],  # Background assumption IDs
            set_tc: List[int],  # E+ assumption IDs
            set_neg_tv: List[int],  # NE assumption IDs
            negation_map: Dict[int, int]  # Maps assumption ID → negated ID for REDUCE
    ) -> CONGENResult:
        """Learn constraints using injected checker."""
        with self.profiler.measure('acqmss'):
            mss = self._acqmss(set_b, set_neg_tv, set_tc, set_bg)
        return Result(mss)
```

**QuAcq** (interactive learning with DI + mode dispatch):
```python
class QuAcq:
    """Interactive learning with DI pattern and mode dispatch (oracle/example)."""

    def __init__(self, oracle: Oracle,
                 query_provider: QueryProvider = None,
                 discriminating_generator: DiscriminatingGenerator = None,
                 profiler_instance: AbstractProfiler = None):
        # All collaborators injected
        self.oracle = oracle
        self.query_provider = query_provider
        self.discriminating_generator = discriminating_generator

    @classmethod
    def for_oracle(cls, checker: ConsistencyChecker, oracle: Oracle, query_prov: QueryProvider,
                   discrim_gen: DiscriminatingGenerator,
                   profiler: AbstractProfiler = None) -> 'QuAcq':
        """Factory for oracle mode."""
        return cls(checker, oracle, query_provider=query_prov, model=None,
                   discriminating_generator=discrim_gen, profiler_instance=profiler)

    @classmethod
    def for_examples(cls, checker: ConsistencyChecker, oracle: Oracle, query_provider: QueryProvider,
                     discrim_gen: DiscriminatingGenerator = None,
                     profiler: AbstractProfiler = None) -> 'QuAcq':
        """Factory for example-based modes."""
        return cls(checker, oracle, query_provider=query_provider, model=None,
                   discriminating_generator=discrim_gen, profiler_instance=profiler)

    def learn(self, set_c, set_b, set_kb, negation_map, assumptions,
              background_clauses, feature_ids, id_to_feature,
              constraint_clauses, negated_clauses,
              mode='oracle', max_queries=1000) -> QuAcqResult:
        """Run learning (returns raw assumption IDs, no name resolution).

        Runner layer resolves names via model.resolve_kb(result.kb_assumption_ids)
        to match ConGen pattern: algorithm → IDs, runner → names.

        Modes:
        - 'oracle'/'automated'/'interactive': Query oracle via query_provider.generate_from_sat()
        - 'example_only': Select from pool via query_provider.generate_from_pool()
        - 'example_first': Pool first (via generate_from_pool()), fallback to SAT
        """
        # Mode dispatch: 'oracle', 'example_only', or 'example_first'
        ...
```


# Usage with ConGenModelBuilder (fluent pattern)

# Pattern: Build once, prepare+shuffle per fold (cross-validation)
oracle = FMOracle('data/fms/model.uvl')
model = (ConGenModelBuilder
         .from_bias('data/bias/model.json')
         .with_oracle(oracle)  # Required for build-time negation
         .use_incremental(True)
         .build())  # Returns unprepared model (negation computed at build time)

# Cross-validation pattern: build once, prepare per fold (prepare_task is pure)
import random
from dataclasses import replace
from explanation.api import build_checker, SolverBackend
from conacq.algorithms.acqmss import ConGen, ConGenTaskInput

for fold_idx, (fold_pos, fold_neg) in enumerate(folds):
    # Step 1: Prepare this fold's task (pure — runs GenerateNE). The model keeps
    # no task; the prepared task + describe live locally (congen_runner.py:118-126).
    prepared = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, fold_pos, fold_neg))
    task = prepared.task

    # Step 2: Shuffle bias order. Task is frozen — shuffle a copy and rebind,
    # never mutate in place (congen_runner.py:130-133).
    shuffle_seed = fold_idx + 42
    shuffled_set_c = list(task.set_c)
    random.Random(shuffle_seed).shuffle(shuffled_set_c)
    task = replace(task, set_c=shuffled_set_c)

    # Step 3: Build checker from the (possibly shuffled) task and run ConGen
    # (congen_runner.py:139-151). Solver mode / name come from the runner.
    checker = build_checker(
        task,
        SolverBackend.from_flags(use_incremental=use_incremental),
        solver_name, profiler)
    congen = ConGen(checker, profiler)
    result = congen.acquire(
        set_b=task.set_c,
        set_bg=task.set_b,
        set_tc=task.set_tc,
        set_neg_tv=task.set_neg_tv,
        negation_map=task.negation_map)  # assumption ID → negated ID for REDUCE

# Alternative: Use ConGenRunner facade (recommended for production)
from conacq.runners import ConGenRunner

runner = ConGenRunner('data/bias/model.json', 'data/fms/model.uvl')
try:
    for fold_idx, (fold_pos, fold_neg) in enumerate(folds):
        result = runner.run(fold_pos, fold_neg, shuffle_seed=fold_idx + 42)
        # Result contains KB and metrics
finally:
    runner.cleanup()
```

**Benefits**:
- Easy to test (inject mock checker)
- Loose coupling
- **Mode-agnostic**: No `if is_incremental` branching in algorithms

### 6. Shared Utility Methods

Extract duplicated logic into static/class methods. Example: Violation checking logic centralized in `QuAcqTask` and reused by QuAcq, FindScope, and FindC.

### 7. Interactive Learning Patterns

`QuAcqRunner` provides high-level facade for QuAcq learning. QuAcq processes negative examples with FindScope/FindC to identify violated constraints in both oracle and example-based modes.

### 8. Checker Construction from Tasks

The checker is built from a Task via `build_checker()` (from `explanation.api`):

```python
from explanation.api import build_checker, SolverBackend

# Build checker from a task
checker = build_checker(
    task,
    backend=SolverBackend.PYSAT_INCREMENTAL,
    solver_name='glucose4',
    profiler=profiler  # optional
)
```

Models are pure knowledge base containers (bias + constraint maps) — they do NOT implement a checker protocol. The task contains all solver-related data (CNF clauses with assumption literals, assumption IDs, negation maps), which is what `build_checker` needs. Checker mode (incremental vs non-incremental) is selected via the `SolverBackend` enum, not on the model or builder.

## Oracle Module Conventions

**Package**: `conacq/oracle/` — Minimal, focused oracle abstraction

**Oracle ABC**: Minimal interface — only `is_valid(assignments)` abstract; `ask()` concrete alias.

**Key Classes**:

1. **OracleData** (`@dataclass(frozen=True)`): Frozen provisioning snapshot (ADR-0009/0012)
   - Carries the algorithm's SAT inputs (`kb`/`assumptions`/`c`/`bg_data`/`root_clauses`); satisfies `KBProvider`+`BGProvider`
   - Built once from the oracle model, then handed to `GenerateNE`, the builders, and task-prep — a snapshot, not the live oracle

2. **BGData** (`@dataclass(frozen=True)`): Root background knowledge constraint data
   - Fields: `set_kb` (assumption-guarded clauses), `assumptions` (tuple of root and negated IDs), `negation_map`, `descriptions`, `next_available_id`
   - Created by `FMOracleModel.get_bg_data()` after task preparation
   - Enables ConGen to cleanly allocate assumption IDs without overlap with oracle assumptions

3. **FMOracle**: Main FM oracle
   - ABC methods: `is_valid()`, `ask()`
   - FM extensions: `get_fm_data()`, `get_features()`, `get_feature_ids()`, `get_root_feature()`, `get_num_constraints()`, `get_next_available_id()`, `complete_configuration()`, `get_cnf_clauses()`, `get_constraint_descriptions()`
   - Delegates to `FMOracleModel` for consistency checking
   - Uses incremental solver by default

4. **FMOracleModel**: Assumption-guarded FM model
   - FM clauses in `set_kb` (always active)
   - Feature assignments as assumption-guarded unit clauses: `[-a_pos_i, fid]`, `[-a_neg_i, -fid]`
   - Its prepared Task carries the assumption-guarded clauses that `build_checker()` consumes
   - Exposes `bg_data` property and `get_bg_data()` method to extract root constraint

5. **UserPromptOracle**: Interactive human oracle (implements `is_valid()` only)

6. **CachedOracle**: Transparent caching wrapper (caches `is_valid()`, delegates FM methods)

**Design Principles**:
- Minimal ABC (only `is_valid()`)
- Provisioning via a frozen `OracleData` snapshot (ADR-0009)
- FM-specific methods on `FMOracle` (not ABC)
- Example generators typed as `FMOracle` (not generic `Oracle`)

**Critical**: Feature ID consistency — `FMOracleModel.variables` uses flamapy's tree traversal order (source: `FmToPysat.variables`). **Never** sort alphabetically — breaks SAT clause literal mapping.

## Testing Strategy

### Test Structure

Use `@parameterized.expand` for testing across solver modes:

```python
from parameterized import parameterized

class TestFastDiag(unittest.TestCase):

    ENABLED_TESTS = {
        'fastdiag_basic': True,
        'fastdiag_hsdag': True,
        'fastdiag_large': False,  # Disabled for quick runs
    }

    ENABLED_PARAMS = {
        'incremental': True,
        'non_incremental': True,
        'sat4j': False,  # Optional Java solver
    }

    @parameterized.expand([
        ('incremental', IncrementalPySATChecker),
        ('non_incremental', NonIncrementalPySATChecker),
    ])
    def test_fastdiag_basic(self, name, checker_class):
        if not self.ENABLED_PARAMS[name]:
            self.skipTest(f'{name} disabled')

        result = fastdiag(self.model, checker=checker_class(self.solver))
        self.assertGreater(len(result), 0)
```

### Test Naming Conventions

- `test_<algorithm>_<scenario>` — Algorithm tests
- `test_<class>_<method>` — Class method tests
- `test_<feature>` — Feature tests
- Use descriptive names over generic `test_1`, `test_2`

### Coverage Requirements

- Core algorithms: ≥90%
- SAT operations: ≥85%
- Data structures: ≥80%
- I/O utilities: ≥70% (less critical)
- CLI applications: ≥60% (tested via integration)

## Documentation Standards

### Module Docstrings

```python
"""
constraint_acquisition.py

Constraint acquisition algorithms for learning from examples.

This module implements ConGen (passive learning) and QuAcq (interactive learning)
paradigms for discovering constraints from feature models using SAT solvers.

Classes:
    ConGen: Divide-and-conquer constraint acquisition
    QuAcq: Interactive query-based learning

Functions:
    acquire_constraints(): High-level acquisition function

Dependencies:
    - explanation.operations.algorithms: Diagnosis algorithms
    - acqmss.bias: Bias constraint handling
"""
```

### Class Docstrings

```python
class CONGEN:
    """Learn constraints via divide-and-conquer MSS finding.

    ConGen (Constraint Generalization) acquires constraints from positive and
    negative example sets by:
    1. Generating negated examples from negative examples
    2. Finding maximum satisfiable subset of bias constraints
    3. Removing redundant constraints

    Args:
        checker: Consistency checker (incremental or non-incremental)
        profiler: Optional profiler for timing/counting (default: NullProfiler)

    Attributes:
        checker (ConsistencyChecker): Solver interface
        profiler (Profiler): Execution profiler

    Example:
        >>> checker = IncrementalPySATChecker(solver)
        >>> congen_root = ConGen(checker, profiler=None)
        >>> result = congen_root.acquire(task)
        >>> print(len(result.kb))
    """
```

### Function/Method Docstrings

```python
def is_consistent(
    self,
    clauses: list[list[int]],
    assumptions: Optional[list[int]] = None
) -> bool:
    """Check if clauses are satisfiable under assumptions.

    Evaluates SAT consistency using the configured solver.

    Args:
        clauses: List of clauses (list of integer literals)
        assumptions: Optional list of unit assumptions (int literals)

    Returns:
        True if satisfiable, False if unsatisfiable

    Raises:
        ValueError: If clauses not in valid CNF format
        TimeoutError: If solver exceeds timeout

    Example:
        >>> checker = IncrementalPySATChecker(solver)
        >>> clauses = [[1, -2], [-1, 3]]
        >>> checker.is_consistent(clauses)
        True
    """
```

## Type Hints

### Requirements

- **All public functions/methods**: Type hints on parameters and return
- **Private functions**: Type hints recommended
- **Complex types**: Use `from __future__ import annotations`

### Examples

```python
from typing import Optional, Sequence, Callable
from pathlib import Path

def load_feature_model(path: Path) -> FeatureModel:
    """Load FM from file."""
    pass

def acquire(
    bias: list[Constraint],
    examples: tuple[list[Configuration], list[Configuration]],
    checker: ConsistencyChecker,
    timeout: Optional[float] = None
) -> Result:
    """Acquire constraints."""
    pass

def create_checker(
    solver_factory: Callable[[], Solver],
    name: str = 'glucose4'
) -> ConsistencyChecker:
    """Create solver checker."""
    pass
```

## Error Handling

### Exception Hierarchy

Create domain-specific exceptions:

```python
class AcqMSSException(Exception):
    """Base exception for AcqMSS."""
    pass

class SolverException(AcqMSSException):
    """Solver-related errors."""
    pass

class TimeoutException(SolverException):
    """Solver timeout exceeded."""
    pass

class InconsistentBiasException(AcqMSSException):
    """Bias constraints are unsatisfiable."""
    pass
```

### Usage

```python
def is_consistent(self, clauses):
    try:
        result = self.solver.solve(clauses)
    except TimeoutError as e:
        raise TimeoutException(f"Solver timeout after {self.timeout}s") from e
    except Exception as e:
        raise SolverException(f"Solver error: {e}") from e

    if result is None:
        raise InconsistentBiasException("Unsatisfiable formula")

    return result
```

## Configuration Management

### No Hard-Coded Values

All configuration via TOML files:

```python
# Bad
SOLVER_NAME = 'glucose4'
MAX_CALLS = 10000

# Good
config = load_config('apps/conf/run_congen_config.toml')
solver_name = config['settings']['solver']
max_calls = config['settings']['max_solver_calls']
```

### Configuration Structure

```toml
[input]
bias_file = "data/bias/arcade-game.json"
examples_file = "data/examples/arcade-game_RS_100.json"

[settings]
incremental = true
solver = "glucose4"
max_solver_calls = 10000
timeout_seconds = 300.0

[output]
result_file = "data/results/arcade-game_CONGEN.json"
profiling_file = "data/results/arcade-game_profile.json"
```

## Performance Considerations

### Solver Efficiency

1. **Incremental solver** (default):
   - Persistent solver instance
   - Reuse across calls with assumptions
   - ~50x faster for repeated checks

2. **Non-incremental mode**:
   - Fresh solver per call
   - Memory-light baseline
   - Use for verification/comparison

3. **HSDAG optimization**:
   - Tree search reduces solver calls
   - ~10x speedup typical
   - Automatic when available

### Profiling

Use decorator pattern for minimal overhead:

```python
from explanation.operations.profiler import Profiler

profiler = Profiler()

@profiler.measure('algorithm_name')
def run_algorithm(task):
    # Automatically timed
    pass

# Access results
timing = profiler.get_timing('algorithm_name')
call_count = profiler.get_count('sat_check')
```

## Security Considerations

### Input Validation

- Validate all external input (files, configs, command-line args)
- Type-check function parameters
- Reject malformed feature models early

### Resource Limits

- Set `timeout_seconds` for solver invocations
- Limit `max_solver_calls` to prevent infinite loops
- Monitor memory usage for large models

### File Handling

Use `pathlib.Path` for cross-platform safety:

```python
from pathlib import Path

# Good
config_path = Path('apps/conf/config.toml')
data_path = Path('data/results') / 'output.json'

# Less safe
config_path = 'apps/conf/config.toml'
```

## Code Review Checklist

Before submitting PR:
- [ ] Type hints on all public functions
- [ ] Docstrings on all public modules/classes/functions
- [ ] Error handling for all exception cases
- [ ] Tests for new code (≥80% coverage, pass both incremental/non-incremental modes)
- [ ] Code follows naming conventions
- [ ] No unused imports or variables
- [ ] Configuration externalized (not hard-coded)

## Style Guide Quick Reference

| Element | Convention | Example |
|---------|-----------|---------|
| Module | snake_case | `task_preparation.py` |
| Class | PascalCase | `class FastDiag` |
| Function | snake_case | `def acquire()` |
| Constant | UPPER_SNAKE_CASE | `MAX_CALLS = 10000` |
| Variable | snake_case | `learned_kb` |
| Boolean | is_/has_/should_ | `is_consistent` |
| Type hints | ✓ Required on public | `def acquire(task: Task)` |
| Docstrings | Google-style | Module, class, function |


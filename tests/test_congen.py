"""
Tests for ConGen constraint acquisition algorithm.

Uses REAL-FM-7 feature model with generated bias and examples.
Supports both incremental and non-incremental solver modes.
"""

from pathlib import Path

import pytest

from conacq.algorithms import (
    ConGen, AcqMSS, Reduce,
    ConGenModelBuilder, ConGenTaskInput
)
from conacq.bias import BiasIO
from conacq.oracle import FMOracle
from explanation.checker.backend import (
    IncrementalPySATChecker,
    build_checker,
    SolverBackend,
)
from profiling import get_global_profiler

# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
FM_PATH = DATA_DIR / "fms" / "REAL-FM-7.uvl"
BIAS_PATH = DATA_DIR / "bias" / "REAL-FM-7-bias.json"
EXAMPLES_RS_1N_PATH = DATA_DIR / "examples" / "REAL-FM-7_rs_1n.json"
EXAMPLES_FF_PATH = DATA_DIR / "examples" / "REAL-FM-7_ff.json"
# The only REAL-FM-7 cell that both KEEPS its ¬e⁻ through Reduce and has exactly one
# negative. Both properties are load-bearing for the NE tests below; see their
# docstrings.
EXAMPLES_RS_M_PATH = DATA_DIR / "examples" / "REAL-FM-7_rs_m.json"


@pytest.fixture
def bias():
    """Load REAL-FM-7 bias."""
    if not BIAS_PATH.exists():
        pytest.skip(f"Bias file not found: {BIAS_PATH}")
    return BiasIO.load_from_json(str(BIAS_PATH))


def create_checker_and_task(bias_path, fm_path, examples_path, is_incremental=True):
    """Helper to create checker and task for tests.

    Args:
        bias_path: Path to bias JSON file
        fm_path: Path to feature model (.uvl) file
        examples_path: Path to examples JSON file
        is_incremental: Use incremental mode

    Returns:
        Tuple of (checker, task, profiler, describe)
    """
    from conacq.examples import ExampleIO

    profiler = get_global_profiler()

    # Create oracle
    oracle = FMOracle(fm_path, use_incremental=False)

    # Build the pure-KB model, then prepare this example set's task explicitly.
    model = (ConGenModelBuilder
             .from_bias(bias_path)
             .with_oracle_data(oracle.oracle_data)
             .build())

    examples = ExampleIO.load_json(examples_path)
    pos = [e.assignments for e in examples.positive]
    neg = [e.assignments for e in examples.negative]
    prepared = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg))
    task = prepared.task

    checker = build_checker(
        task, SolverBackend.from_flags(use_incremental=is_incremental),
        'glucose4', profiler)

    return checker, task, profiler, prepared.describe


class TestCONGEN:
    """Tests for main ConGen algorithm."""

    def test_congen_incremental_with_rs_examples(self, bias):
        """Test ConGen incremental mode with random sampling examples."""
        if not FM_PATH.exists() or not EXAMPLES_RS_1N_PATH.exists():
            pytest.skip("Test data files not found")
        checker, task, profiler, provider = create_checker_and_task(
            str(BIAS_PATH), str(FM_PATH), str(EXAMPLES_RS_1N_PATH), is_incremental=True
        )

        try:
            # The acquisition BG is domain-only: root non-emptiness is a
            # POST-acquisition axiom on task.root_axiom, not runtime BG (keeping it
            # in BG made Reduce entailment-drop every `X -> root` constraint). For a
            # boolean FM the domain BG is empty, so assert the root is ACCOUNTED FOR
            # rather than that set_b is non-empty.
            assert list(task.set_b) == [], "acquisition BG should be domain-only"
            assert len(task.root_axiom) > 0, "root axiom should be recorded"

            congen = ConGen(checker, profiler)
            result = congen.acquire(
                set_b=task.set_c,
                set_bg=task.set_b,
                set_tc=task.set_tc,
                set_neg_tv=task.set_neg_tv,
                negation_map=task.negation_map,
            )

            # Verify result
            assert result is not None
            # n_bias excludes FM constraints (moved to BG in migration)
            assert result.n_bias > 0
            assert result.n_kb >= 0
            assert isinstance(result.kb_assumption_ids, list)

            print(f"\nConGen Incremental Result (RS 1n):")
            print(f"  Bias: {result.n_bias}")
            print(f"  MSS: {result.n_mss}")
            print(f"  KB: {result.n_kb}")
            if result.kb_assumption_ids:
                for c in result.kb_assumption_ids:
                    # Bridge assumption ID (int) → constraint name (str) → Constraint
                    cname = provider.get_description(c)
                    constraint = bias.get_constraint_by_id(cname)
                    print(f"  Constraint: {constraint if constraint else cname} (ID: {c})")

            profiler.print_summary(include_raw_timers=True)

        finally:
            checker.cleanup()

    def test_congen_non_incremental_with_rs_examples(self, bias):
        """Test ConGen non-incremental mode with random sampling examples."""
        if not FM_PATH.exists() or not EXAMPLES_RS_1N_PATH.exists():
            pytest.skip("Test data files not found")
        checker, task, profiler, provider = create_checker_and_task(
            str(BIAS_PATH), str(FM_PATH), str(EXAMPLES_RS_1N_PATH), is_incremental=False
        )

        try:
            # The acquisition BG is domain-only: root non-emptiness is a
            # POST-acquisition axiom on task.root_axiom, not runtime BG (keeping it
            # in BG made Reduce entailment-drop every `X -> root` constraint). For a
            # boolean FM the domain BG is empty, so assert the root is ACCOUNTED FOR
            # rather than that set_b is non-empty.
            assert list(task.set_b) == [], "acquisition BG should be domain-only"
            assert len(task.root_axiom) > 0, "root axiom should be recorded"

            congen = ConGen(checker, profiler)
            result = congen.acquire(
                set_b=task.set_c,
                set_bg=task.set_b,
                set_tc=task.set_tc,
                set_neg_tv=task.set_neg_tv,
                negation_map=task.negation_map,
            )

            # Verify result
            assert result is not None
            # n_bias excludes FM constraints (moved to BG in migration)
            assert result.n_bias > 0
            assert result.n_kb >= 0
            assert isinstance(result.kb_assumption_ids, list)

            print(f"\nConGen Non-Incremental Result (RS 1n):")
            print(f"  Bias: {result.n_bias}")
            print(f"  MSS: {result.n_mss}")
            print(f"  KB: {result.n_kb}")

            if result.kb_assumption_ids:
                for c in result.kb_assumption_ids:
                    # Bridge assumption ID (int) → constraint name (str) → Constraint
                    cname = provider.get_description(c)
                    constraint = bias.get_constraint_by_id(cname)
                    print(f"  Constraint: {constraint} (ID: {c})")

            profiler.print_summary(include_raw_timers=True)

        finally:
            checker.cleanup()

    def test_congen_incremental_with_ff_examples(self, bias):
        """Test ConGen incremental mode with feature frequency examples."""
        if not FM_PATH.exists() or not EXAMPLES_FF_PATH.exists():
            pytest.skip("Test data files not found")
        checker, task, profiler, provider = create_checker_and_task(
            str(BIAS_PATH), str(FM_PATH), str(EXAMPLES_FF_PATH), is_incremental=True
        )

        try:
            # The acquisition BG is domain-only: root non-emptiness is a
            # POST-acquisition axiom on task.root_axiom, not runtime BG (keeping it
            # in BG made Reduce entailment-drop every `X -> root` constraint). For a
            # boolean FM the domain BG is empty, so assert the root is ACCOUNTED FOR
            # rather than that set_b is non-empty.
            assert list(task.set_b) == [], "acquisition BG should be domain-only"
            assert len(task.root_axiom) > 0, "root axiom should be recorded"

            congen = ConGen(checker, profiler)
            result = congen.acquire(
                set_b=task.set_c,
                set_bg=task.set_b,
                set_tc=task.set_tc,
                set_neg_tv=task.set_neg_tv,
                negation_map=task.negation_map,
            )

            # Verify result
            assert result is not None
            # n_bias excludes FM constraints (moved to BG in migration)
            assert result.n_bias > 0

            print(f"\nConGen Incremental Result (FF):")
            print(f"  Bias: {result.n_bias}")
            print(f"  MSS: {result.n_mss}")
            print(f"  KB: {result.n_kb}")

            if result.kb_assumption_ids:
                for c in result.kb_assumption_ids:
                    # Bridge assumption ID (int) → constraint name (str) → Constraint
                    cname = provider.get_description(c)
                    constraint = bias.get_constraint_by_id(cname)
                    print(f"  Constraint: {constraint} (ID: {c})")

            profiler.print_summary(include_raw_timers=True)

        finally:
            checker.cleanup()


class TestACQMSS:
    """Tests for AcqMSS algorithm."""

    def test_acqmss_empty_bias(self):
        """Test AcqMSS with empty bias returns empty."""
        # Create simple checker
        checker = IncrementalPySATChecker([[1]], [1], 'glucose4')

        try:
            acqmss = AcqMSS(checker)
            result = acqmss.find_mss([], [], [], [1], [])

            assert result == []
        finally:
            checker.cleanup()

    def test_acqmss_single_constraint(self):
        """Test AcqMSS with single constraint."""
        # Create checker with simple clauses
        # Clause: (1 ∨ a) where a is assumption
        kb = [[1, 2]]  # 2 is assumption
        checker = IncrementalPySATChecker(kb, [2], 'glucose4')

        try:
            acqmss = AcqMSS(checker, m=1)
            # B = [2], should return [] since |B| <= m
            result = acqmss.find_mss([], [2], [], [1], [])

            assert result == []
        finally:
            checker.cleanup()


class TestReduce:
    """Tests for REDUCE algorithm."""

    def test_reduce_empty(self):
        """Test REDUCE with empty input returns empty."""
        checker = IncrementalPySATChecker([[1]], [1], 'glucose4')

        try:
            reduce = Reduce(checker)
            redundant, kb = reduce.reduce([], [], [], {})

            assert redundant == []
            assert kb == []
        finally:
            checker.cleanup()

    def test_reduce_survivor_follows_input_order(self):
        """The surviving representative of mutually-redundant constraints must
        follow the input (gamma1+gamma2) order, not hash order. REDUCE removes a
        constraint when the rest entail it, so with three mutually-redundant
        constraints it keeps the LAST one reached — and two different input orders
        keep different survivors. Before the fix (``list(set(...))``) both orders
        collapse to one hash order and keep the same survivor, so this guard fails
        on pre-fix code (teeth, not a tautology).
        """
        class _MutualRedundancyChecker:
            """Any single remaining constraint entails all others: BG ∪ (KB-{c}) ∪
            {¬c} is inconsistent iff a positive constraint remains alongside ¬c."""
            NEG = {101, 102, 103}
            POS = {1, 2, 3}

            def is_consistent(self, test_set):
                has_neg = any(a in self.NEG for a in test_set)
                has_pos = any(a in self.POS for a in test_set)
                return not (has_neg and has_pos)

        negation_map = {1: 101, 2: 102, 3: 103}
        reduce = Reduce(_MutualRedundancyChecker())

        _, kb_fwd = reduce.reduce([1, 2, 3], [], [], negation_map)
        _, kb_rev = reduce.reduce([3, 2, 1], [], [], negation_map)

        assert kb_fwd == [3]      # input order [1,2,3] -> last (3) survives
        assert kb_rev == [1]      # input order [3,2,1] -> last (1) survives
        assert kb_fwd != kb_rev   # different input order -> different survivor (teeth)


class TestGenerateNE:
    """Tests for GenerateNE algorithm."""

    def test_generate_ne_empty_testsuite(self):
        """Test GenerateNE with empty testsuite returns empty."""
        if not FM_PATH.exists():
            pytest.skip("FM file not found")

        from conacq.algorithms.acqmss.generate_ne import GenerateNE
        from explanation.api import AssumptionIdAllocator
        from explanation.models.testsuite import TestSuite

        oracle = FMOracle(str(FM_PATH))
        generate_ne = GenerateNE(oracle.oracle_data)
        empty_ts = TestSuite(testcases=[])
        alloc = AssumptionIdAllocator(1000)
        results = generate_ne.generate(empty_ts, {}, [], [], alloc)

        assert results == []
        assert alloc.next_id == 1000
        del oracle


def _load_ff_examples():
    """Load REAL-FM-7 FF examples as (pos, neg) dict lists."""
    from conacq.examples import ExampleIO
    examples = ExampleIO.load_json(str(EXAMPLES_FF_PATH))
    pos = [e.assignments for e in examples.positive]
    neg = [e.assignments for e in examples.negative]
    return pos, neg


class TestConGenModelBuilder:
    """Tests for ConGenModelBuilder (pure KB) + prepare_task patterns."""

    def test_prepare_task_from_file(self):
        """Build a pure-KB model, then prepare a task from file-loaded examples."""
        if not FM_PATH.exists() or not EXAMPLES_FF_PATH.exists():
            pytest.skip("Test data files not found")

        oracle = FMOracle(str(FM_PATH), use_incremental=False)
        model = (ConGenModelBuilder
                 .from_bias(str(BIAS_PATH))
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        pos, neg = _load_ff_examples()
        prepared = model.prepare_task(
            ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg))
        assert prepared.task is not None
        assert len(prepared.task.set_kb) > 0

    def test_prepare_task_from_data(self):
        """prepare_task consumes raw example dicts directly (no builder plumbing)."""
        if not FM_PATH.exists() or not EXAMPLES_FF_PATH.exists():
            pytest.skip("Test data files not found")

        pos, neg = _load_ff_examples()
        oracle = FMOracle(str(FM_PATH), use_incremental=False)
        model = (ConGenModelBuilder
                 .from_bias(str(BIAS_PATH))
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        prepared = model.prepare_task(
            ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg))
        assert prepared.task is not None

    def test_build_without_oracle_raises(self):
        """build() without oracle → ValueError."""
        if not BIAS_PATH.exists():
            pytest.skip("Bias file not found")

        with pytest.raises(ValueError, match="OracleData required"):
            ConGenModelBuilder.from_bias(str(BIAS_PATH)).build()

    def test_prepare_task_is_pure_and_repeatable(self):
        """Build once, prepare_task per fold: same input → same task, fresh object."""
        if not FM_PATH.exists() or not EXAMPLES_FF_PATH.exists():
            pytest.skip("Test data files not found")

        oracle = FMOracle(str(FM_PATH), use_incremental=False)
        model = (ConGenModelBuilder
                 .from_bias(str(BIAS_PATH))
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        pos, neg = _load_ff_examples()
        task_input = ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg)

        p1 = model.prepare_task(task_input)
        p2 = model.prepare_task(task_input)

        assert p1.task.set_kb == p2.task.set_kb
        assert p1.task is not p2.task


class TestOracleFeatureIds:
    """Regression tests: Oracle feature_ids must match flamapy and bias IDs."""

    MODELS = [
        ("REAL-FM-7", "data/fms/REAL-FM-7.uvl", "data/bias/REAL-FM-7-bias.json"),
        ("arcade-game", "data/fms/arcade-game.uvl", "data/bias/arcade-game-bias.json"),
        ("REAL-FM-4", "data/fms/REAL-FM-4.uvl", "data/bias/REAL-FM-4-bias.json"),
    ]

    @pytest.mark.parametrize("name,fm_path,bias_path", MODELS)
    def test_oracle_ids_match_flamapy(self, name, fm_path, bias_path):
        """Oracle feature_ids must match flamapy's variable assignment."""
        from flamapy.metamodels.fm_metamodel.transformations import UVLReader
        from flamapy.metamodels.pysat_metamodel.transformations import FmToPysat

        if not Path(fm_path).exists():
            pytest.skip(f"FM not found: {fm_path}")

        oracle = FMOracle(fm_path)
        fm = UVLReader(fm_path).transform()
        sat = FmToPysat(fm).transform()

        assert oracle.get_variable_ids() == dict(sat.variables), \
            f"{name}: Oracle IDs don't match flamapy"
        del oracle

    @pytest.mark.parametrize("name,fm_path,bias_path", MODELS)
    def test_oracle_ids_match_bias(self, name, fm_path, bias_path):
        """Oracle feature_ids must match bias file IDs."""
        if not Path(fm_path).exists() or not Path(bias_path).exists():
            pytest.skip(f"Files not found: {fm_path} or {bias_path}")

        oracle = FMOracle(fm_path)
        bias = BiasIO.load_from_json(bias_path)
        bias_ids = bias.feature_ids

        assert oracle.get_variable_ids() == bias_ids, \
            f"{name}: Oracle IDs don't match bias"
        del oracle


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# --- C7: root non-emptiness is a post-acquisition axiom, not runtime BG ---------

def test_root_kept_out_of_acquisition_bg_but_recorded():
    """The acquisition BG carries no root fact; the root is recorded on root_axiom.

    Guards the C7 invariant directly: if the root is put back into set_b, Reduce
    entailment-drops every `X -> root` constraint and they can never be learned.
    Asserting root_axiom is non-empty also catches the opposite failure — dropping
    the root from BG without recording it anywhere, which loses it silently.
    """
    if not FM_PATH.exists() or not BIAS_PATH.exists():
        pytest.skip("REAL-FM-7 fixtures not found")
    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data).build())
    task = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, [{"java": True}], [])).task

    assert list(task.set_b) == [], "root must not be in the acquisition BG"
    assert len(task.root_axiom) == 1, "root must still be recorded, not lost"
    # The root assumption is the Oracle's first BG assumption — not re-derived here,
    # so a change in Part-3 layout surfaces rather than being absorbed.
    assert task.root_axiom[0] == oracle.oracle_data.get_bg_data().assumptions[0]


def test_root_implying_constraints_are_learnable():
    """`X -> root` constraints survive Reduce and reach the learned KB.

    This is the behavioural point of C7, independent of any golden: with the root in
    BG these constraints are provably redundant and Reduce removes all of them, so
    the intersection below is empty. Red here means the recall regression is back.
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, EXAMPLES_RS_1N_PATH)):
        pytest.skip("REAL-FM-7 fixtures not found")
    import json

    from conacq.runners import ConGenRunner

    ex = json.loads(EXAMPLES_RS_1N_PATH.read_text())
    runner = ConGenRunner(str(BIAS_PATH), str(FM_PATH), use_incremental=False)
    result = runner.run([e["assignments"] for e in ex["positive"]],
                        [e["assignments"] for e in ex["negative"]])

    learned = set(result.kb_constraints)
    # c6/c14/c18 are REAL-FM-7's `X -> root` relations; all three were unlearnable
    # while the root sat in BG (they landed in redundant_constraints instead).
    root_implying = {"c6", "c14", "c18"}
    assert root_implying <= learned, (
        f"root-implying constraints missing from KB: {sorted(root_implying - learned)}")
    assert not (root_implying & set(result.redundant_constraints)), \
        "root-implying constraints were classified redundant again"


# --- C6: NE reported apart from bias constraints -------------------------------

@pytest.mark.parametrize("examples_path,ne_kept", [
    (EXAMPLES_RS_M_PATH, True),
    (EXAMPLES_RS_1N_PATH, False),
], ids=["ne-kept", "ne-discharged"])
def test_ne_split_out_of_kb_names(examples_path, ne_kept):
    """kb_constraints is bias-only; memorized ¬e⁻ facts go to ne_constraints.

    They used to share one name list, so an NE inflated n_kb and entered the
    description/clause/semantic tiers, whose
    vocabulary is the bias. Asserts BOTH directions — no NE in kb, no bias in ne — so
    a split that merely moves the boundary the wrong way still goes red.

    Run in both regimes. Reduce keeps a ¬e⁻ whose minimal conflict is root-dependent
    (rs_m) and discharges one that is root-independent (rs_1n) — root sits outside the
    reduction background by design, so a conflict that needs it is not provably
    redundant there. A kept-NE cell alone leaves the discard path untested; a
    discharged-NE cell alone makes the count assertion pass vacuously.

    If acquisition changes character and a cell flips regime, this goes red loudly.
    That is the good case, and it is why the regime is asserted rather than assumed:
    the earlier version pinned a cell whose NE always survived, which held only
    because Reduce could not discharge one at all.
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, examples_path)):
        pytest.skip("REAL-FM-7 fixtures not found")
    import json

    from conacq.runners import ConGenRunner

    bias_names = set(BiasIO.load_from_json(str(BIAS_PATH)).to_constraint_map())
    ex = json.loads(examples_path.read_text())
    result = ConGenRunner(str(BIAS_PATH), str(FM_PATH), use_incremental=False).run(
        [e["assignments"] for e in ex["positive"]],
        [e["assignments"] for e in ex["negative"]])

    assert set(result.kb_constraints) <= bias_names, \
        f"non-bias names in kb_constraints: {sorted(set(result.kb_constraints) - bias_names)}"
    assert not (set(result.ne_constraints) & bias_names), \
        f"bias names in ne_constraints: {sorted(set(result.ne_constraints) & bias_names)}"
    assert result.n_kb == len(result.kb_constraints)
    assert result.n_ne == len(result.ne_constraints)
    if ne_kept:
        assert result.n_ne > 0, (
            "fixture no longer memorizes a ¬e⁻, so the assertions above pass "
            "vacuously on an empty ne list — pick a cell whose minimal conflict is "
            "root-dependent")
    else:
        assert result.n_ne == 0 and result.redundant_ne_constraints, (
            "fixture no longer discharges its ¬e⁻, so the discard path is untested")


def test_ne_count_comes_from_the_post_reduce_kb():
    """n_kb and n_ne partition the POST-Reduce KB id list, not the prepared NE.

    Reduce runs on B′ ∪ NE and can drop an NE the rest of the KB already entails, so
    a count taken at prep time over-reports |KB|. Asserting the partition against
    ``ConGenResult.kb_assumption_ids`` — Reduce's own output — pins the source
    structurally, so it holds on any fixture. (On every REAL-FM-7 fixture Reduce
    happens to drop 0 NE, so a value comparison against the prepared count would pass
    vacuously here; this does not.)
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, EXAMPLES_RS_1N_PATH)):
        pytest.skip("REAL-FM-7 fixtures not found")
    from conacq.examples import ExampleIO

    checker, task, profiler, describe = create_checker_and_task(
        str(BIAS_PATH), str(FM_PATH), str(EXAMPLES_RS_1N_PATH), is_incremental=False)
    try:
        oracle = FMOracle(str(FM_PATH), use_incremental=False)
        model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
                 .with_oracle_data(oracle.oracle_data).build())
        result = ConGen(checker, profiler).acquire(
            set_b=task.set_c, set_bg=task.set_b, set_tc=task.set_tc,
            set_neg_tv=task.set_neg_tv, negation_map=task.negation_map)

        (_bg, _cl, kb_names, ne_clauses, ne_names,
         _red, _red_ne) = model.resolve_result(
            result, describe, oracle.oracle_data.get_root_clauses(),
            set_kb=task.set_kb, negation_map=task.negation_map)

        # The two populations exactly partition Reduce's output — nothing invented,
        # nothing dropped.
        assert len(kb_names) + len(ne_names) == len(result.kb_assumption_ids)
        assert len(ne_names) <= len(task.set_neg_tv), \
            "more NE reported than were ever prepared"
        # Every reported NE resolves to a delivered clause — none is dropped.
        assert len(ne_clauses) == len(ne_names)
    finally:
        checker.cleanup()


# --- Algorithm 3: the delivered theory is B′ ∪ NE ------------------------------

def test_delivered_theory_carries_the_memorized_negatives():
    """The delivered theory contains the ¬e⁻ clauses, and they do the rejecting.

    Algorithm 3 delivers KB ← B′ ∪ NE and Definition 6 asks for a theory rejecting all
    e⁻ ∈ E⁻. The NE clauses used to be dropped on the way out — an NE name has no
    constraint_map entry, so it resolved to no clause — leaving a theory that could
    ACCEPT a training negative.

    The load-bearing assertion is on the NE clauses ALONE: bias constraints often
    already reject the training negatives (on every REAL-FM-7 / fqa / arcade-game fold
    measured post-C7 they do, so the full-theory FP count does not discriminate here),
    but ¬e⁻ must reject them BY ITSELF, whatever the bias learned. That fails the moment
    an NE is dropped.

    SCOPE, and it is narrow. rs_m is used because it is the only REAL-FM-7 cell that
    both keeps its ¬e⁻ through Reduce and has exactly ONE negative. With more than one,
    the negatives are folded into a single combined assumption whose resolved clause is
    over an auxiliary variable and carries none of the exclusions — measured on ff
    ([[732]], rejects 1 of 3), rs_3n ([[796]], 2 of 4) and 2cov ([[720]], 4 of 9). On
    2cov the DELIVERED theory then accepts 2 of 9 training negatives, violating
    Definition 6. That defect is in resolution, predates the NE negation fix (verified
    against reverted code, identical numbers), and is not what this test guards.
    A green run here therefore does NOT establish Definition 6 in general.
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, EXAMPLES_RS_M_PATH)):
        pytest.skip("REAL-FM-7 fixtures not found")
    import json

    from conacq.eval.accuracy import AccuracyCalculator
    from conacq.oracle import FMOracle
    from conacq.runners import ConGenRunner

    ex = json.loads(EXAMPLES_RS_M_PATH.read_text())
    pos = [e["assignments"] for e in ex["positive"]]
    neg = [e["assignments"] for e in ex["negative"]]
    assert neg, "fixture must have at least one negative or this proves nothing"

    result = ConGenRunner(str(BIAS_PATH), str(FM_PATH), use_incremental=False).run(pos, neg)
    assert result.n_ne > 0, (
        "fixture must memorize at least one ¬e⁻ — Reduce discharged it, so pick a cell "
        "whose minimal conflict is root-dependent")
    assert len(result.ne_clauses) == result.n_ne, "an NE was dropped from the theory"

    model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(FMOracle(str(FM_PATH), use_incremental=False).oracle_data)
             .build())

    # ¬e⁻ alone must reject every training negative — this is what the NE IS.
    ne_only = [list(c) for c in result.ne_clauses] + list(result.bg_clauses)
    with AccuracyCalculator(ne_only, model.name_to_id, 'glucose4') as acc:
        m_ne = acc.calculate([], neg).metrics
    assert m_ne.false_positives == 0, \
        "the memorized ¬e⁻ clauses do not reject the negatives they encode"
    assert m_ne.true_negatives == len(neg)

    # And the full delivered theory keeps that property (Definition 6).
    theory = (list(result.kb_clauses) + [list(c) for c in result.ne_clauses]
              + list(result.bg_clauses))
    with AccuracyCalculator(theory, model.name_to_id, 'glucose4') as acc:
        m_all = acc.calculate(pos, neg).metrics
    assert m_all.false_positives == 0, (
        f"delivered theory ACCEPTS {m_all.false_positives} training negative(s) — "
        f"Definition 6 requires all e⁻ rejected")


def test_ne_accounting_closes_when_reduce_discards_an_ne():
    """|KB| accounting stays closed: prepared NE = kept NE + NE Reduce discarded.

    An NE that Reduce drops as entailed used to fall out of EVERY returned list — not
    kb_constraints (correct), not ne_constraints (built from the kept ids), and not
    redundant_constraints, because the non-bias names were discarded when resolving
    redundant_ids. The NE simply vanished from the output.

    Driven synthetically: rs_m KEEPS its ¬e⁻ (its minimal conflict is root-dependent),
    and moving that NE id from kb_assumption_ids to redundant_ids is exactly what Reduce
    does when it finds one entailed. Synthetic input, real resolution path, so the
    assertion can fail. The sibling test below covers the same accounting on a cell
    where Reduce discards for real.
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, EXAMPLES_RS_M_PATH)):
        pytest.skip("REAL-FM-7 fixtures not found")
    import copy
    import json

    from conacq.oracle import FMOracle
    from explanation.checker.backend import SolverBackend, build_checker

    ex = json.loads(EXAMPLES_RS_M_PATH.read_text())
    pos = [e["assignments"] for e in ex["positive"]]
    neg = [e["assignments"] for e in ex["negative"]]

    oracle = FMOracle(str(FM_PATH), use_incremental=False)
    model = (ConGenModelBuilder.from_bias(str(BIAS_PATH))
             .with_oracle_data(oracle.oracle_data).build())
    prepared = model.prepare_task(
        ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg))
    task, describe = prepared.task, prepared.describe
    profiler = get_global_profiler()
    checker = build_checker(task, SolverBackend.PYSAT_NON_INCREMENTAL, 'glucose4', profiler)
    try:
        result = ConGen(checker, profiler).acquire(
            set_b=task.set_c, set_bg=task.set_b, set_tc=task.set_tc,
            set_neg_tv=task.set_neg_tv, negation_map=task.negation_map)
    finally:
        checker.cleanup()

    n_prepared = len(task.set_neg_tv)
    assert n_prepared > 0, "fixture must prepare an NE or this proves nothing"
    ne_id = task.set_neg_tv[0]
    assert ne_id in result.kb_assumption_ids, (
        "fixture must keep the NE, to then drop it — Reduce discharged it, so this "
        "cell can no longer stage the synthetic drop")

    def resolve(res):
        return model.resolve_result(
            res, describe, oracle.oracle_data.get_root_clauses(),
            set_kb=task.set_kb, negation_map=task.negation_map)

    # As acquired: the NE is kept, nothing is redundant-NE.
    *_, ne_names, _red, red_ne = resolve(result)
    assert len(ne_names) + len(red_ne) == n_prepared

    # Now with Reduce having discarded it.
    dropped = copy.copy(result)
    dropped.kb_assumption_ids = [a for a in result.kb_assumption_ids if a != ne_id]
    dropped.redundant_ids = list(result.redundant_ids) + [ne_id]
    *_, ne_names2, _red2, red_ne2 = resolve(dropped)

    assert describe.get_description(ne_id) in red_ne2, \
        "an NE discarded by Reduce is not reported anywhere"
    assert len(ne_names2) + len(red_ne2) == n_prepared, \
        f"|KB| accounting does not close: {len(ne_names2)} + {len(red_ne2)} != {n_prepared}"


def test_ne_accounting_closes_when_reduce_really_discards_an_ne():
    """The same accounting, on a cell where Reduce discards the ¬e⁻ for real.

    The sibling above stages the drop by hand because for most of this project's life
    Reduce could not perform one: it tested the negated NE's auxiliary guard, which is
    always satisfiable, so every ¬e⁻ survived — 79 of 79 folds with training negatives.
    rs_1n's minimal conflict is root-independent, so with the negation asserting the
    example instead of switching off its guard, Reduce now discharges it.

    A discarded ¬e⁻ must still be REPORTED, or it vanishes from the output entirely:
    not in kb_constraints (correct), not in ne_constraints (built from kept ids), and
    not in redundant_constraints (bias-filtered). Then prepared != kept + discarded and
    |KB| stops closing.
    """
    if not all(p.exists() for p in (FM_PATH, BIAS_PATH, EXAMPLES_RS_1N_PATH)):
        pytest.skip("REAL-FM-7 fixtures not found")
    import json

    from conacq.runners import ConGenRunner

    ex = json.loads(EXAMPLES_RS_1N_PATH.read_text())
    neg = [e["assignments"] for e in ex["negative"]]
    assert neg, "fixture must have a negative or this proves nothing"

    result = ConGenRunner(str(BIAS_PATH), str(FM_PATH), use_incremental=False).run(
        [e["assignments"] for e in ex["positive"]], neg)

    assert result.n_ne == 0, (
        "Reduce no longer discharges this ¬e⁻ — the real discard path is untested")
    assert len(result.redundant_ne_constraints) == 1, (
        "the discarded ¬e⁻ is reported nowhere: "
        f"n_ne={result.n_ne}, redundant_ne={result.redundant_ne_constraints}")
    assert result.n_ne + len(result.redundant_ne_constraints) == 1, \
        "|KB| accounting does not close over the prepared ¬e⁻"
    # It left kb_constraints too — a discarded NE must not linger as a bias name.
    assert result.redundant_ne_constraints[0] not in result.kb_constraints

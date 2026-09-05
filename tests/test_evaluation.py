"""
Unit tests for the evaluation module.

Uses REAL-FM-7 feature model with generated bias and results.
"""

import pytest
from pathlib import Path

from conacq.eval import (
    EvaluationMetrics,
    compute_metrics,
    Bias,
    BiasIO,
    ConGenResultData,
    AccuracyCalculator,
    AccuracyResult,
    KBComparator,
    ComparationStrategy,
    generate_evaluation_report,
    generate_accuracy_report,
)
# Metrics container moved to conacq/runners/metrics.py (ADR-0006).
from conacq.runners.metrics import (
    CONGEN_METRICS,
    QUACQ_METRICS,
    COMMON_KEYS,
    RunMetrics,
    aggregate,
)


# Test data paths
DATA_DIR = Path(__file__).parent.parent / "data"
FM_PATH = DATA_DIR / "fms" / "REAL-FM-7.uvl"
BIAS_PATH = DATA_DIR / "bias" / "REAL-FM-7-bias.json"
RESULT_PATH = DATA_DIR / "results" / "old_results" / "REAL-FM-7_rs_1n_non-incremental_fold1_kb.json"
EXAMPLES_RS_1N_PATH = DATA_DIR / "examples" / "REAL-FM-7_rs_1n.json"


class TestEvaluationMetrics:
    """Test EvaluationMetrics class."""

    def test_accuracy_calculation(self):
        """Test accuracy formula: (TP + TN) / (TP + TN + FP + FN)"""
        metrics = EvaluationMetrics(
            true_positives=8,
            true_negatives=2,
            false_positives=0,
            false_negatives=0
        )
        assert metrics.accuracy == 1.0

    def test_accuracy_with_errors(self):
        """Test accuracy with some errors."""
        metrics = EvaluationMetrics(
            true_positives=7,
            true_negatives=1,
            false_positives=1,
            false_negatives=1
        )
        # (7 + 1) / (7 + 1 + 1 + 1) = 8/10 = 0.8
        assert metrics.accuracy == 0.8

    def test_precision(self):
        """Test precision = TP / (TP + FP)"""
        metrics = EvaluationMetrics(
            true_positives=8,
            true_negatives=1,
            false_positives=2,
            false_negatives=1
        )
        # 8 / (8 + 2) = 0.8
        assert metrics.precision == 0.8

    def test_recall(self):
        """Test recall = TP / (TP + FN)"""
        metrics = EvaluationMetrics(
            true_positives=8,
            true_negatives=1,
            false_positives=0,
            false_negatives=2
        )
        # 8 / (8 + 2) = 0.8
        assert metrics.recall == 0.8

    def test_f1_score(self):
        """Test F1 = 2 * P * R / (P + R)"""
        metrics = EvaluationMetrics(
            true_positives=8,
            true_negatives=0,
            false_positives=2,
            false_negatives=2
        )
        # P = 8/10 = 0.8, R = 8/10 = 0.8
        # F1 = 2 * 0.8 * 0.8 / (0.8 + 0.8) = 0.8
        assert abs(metrics.f1_score - 0.8) < 1e-10

    def test_zero_division_handling(self):
        """Test handling of zero division cases."""
        metrics = EvaluationMetrics(
            true_positives=0,
            true_negatives=0,
            false_positives=0,
            false_negatives=0
        )
        assert metrics.accuracy == 0.0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = EvaluationMetrics(
            true_positives=5,
            true_negatives=3,
            false_positives=1,
            false_negatives=1
        )
        d = metrics.to_dict()
        assert 'accuracy' in d
        assert 'precision' in d
        assert 'recall' in d
        assert 'f1_score' in d
        assert d['true_positives'] == 5


class TestComputeMetrics:
    """Test compute_metrics function for clause comparison."""

    def test_perfect_match(self):
        """Test when KB exactly matches Oracle."""
        kb_set = {(1, 2), (3, 4), (5, 6)}
        oracle_set = {(1, 2), (3, 4), (5, 6)}
        bias_set = {(1, 2), (3, 4), (5, 6), (7, 8)}

        metrics = compute_metrics(kb_set, oracle_set, bias_set)
        assert metrics.true_positives == 3
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0

    def test_partial_match(self):
        """Test partial match between KB and Oracle."""
        kb_set = {(1, 2), (3, 4)}
        oracle_set = {(1, 2), (5, 6)}

        metrics = compute_metrics(kb_set, oracle_set)
        assert metrics.true_positives == 1  # (1, 2)
        assert metrics.false_positives == 1  # (3, 4)
        assert metrics.false_negatives == 1  # (5, 6)


class TestBiasLoading:
    """Test Bias loading via BiasIO."""

    def test_load_from_json(self, tmp_path):
        """Test loading bias from JSON file."""
        # Create a test bias file
        bias_json = tmp_path / "test_bias.json"
        bias_json.write_text('''
        {
            "features": [
                {"name": "A", "id": 1},
                {"name": "B", "id": 2}
            ],
            "constraints": [
                {
                    "id": "c1",
                    "operator": "mandatory",
                    "clauses": [[-1, 2], [-2, 1]],
                    "description": "A --mandatory--> B"
                }
            ]
        }
        ''')

        bias = BiasIO.load_from_json(str(bias_json))

        assert len(bias.features) == 2
        assert bias.feature_ids['A'] == 1
        assert len(bias) == 1
        assert bias.get_description('c1') == "A --mandatory--> B"

    def test_get_clauses(self, tmp_path):
        """Test getting clauses for a constraint."""
        bias_json = tmp_path / "test_bias.json"
        bias_json.write_text('''
        {
            "features": [],
            "constraints": [
                {"id": "c1", "operator": "mandatory", "clauses": [[1, 2], [3]], "description": "test"}
            ]
        }
        ''')

        bias = BiasIO.load_from_json(str(bias_json))
        clauses = bias.get_clauses('c1')

        assert len(clauses) == 2
        assert clauses[0] == [1, 2]


class TestCONGENResultData:
    """Test ConGenResultData loading."""

    def test_load_from_json(self, tmp_path):
        """Test loading result from JSON file."""
        result_json = tmp_path / "test_result.json"
        result_json.write_text('''
        {
            "kb_constraints": ["c1", "c2", "c3"],
            "redundant_constraints": ["c4"],
            "statistics": {
                "n_bias": 100,
                "n_mss": 50,
                "n_kb": 3
            },
            "metadata": {}
        }
        ''')

        result = ConGenResultData.from_json(result_json)

        assert len(result.kb_constraints) == 3
        assert result.n_bias == 100
        assert result.n_kb == 3

    def test_bg_clauses_default_empty(self):
        """Verify bg_clauses defaults to empty, no impact on eval."""
        result = ConGenResultData(kb_constraints=[], n_bias=10, n_kb=0)
        assert result.bg_clauses == []

    def test_kb_reduction_ratio(self, tmp_path):
        """Test KB reduction ratio calculation."""
        result_json = tmp_path / "test_result.json"
        result_json.write_text('''
        {
            "kb_constraints": ["c1", "c2"],
            "redundant_constraints": [],
            "statistics": {"n_bias": 100, "n_mss": 50, "n_kb": 20}
        }
        ''')

        result = ConGenResultData.from_json(result_json)

        # reduction = 1 - (20/100) = 0.8
        assert result.kb_reduction_ratio == 0.8


class TestAccuracyCalculator:
    """Test AccuracyCalculator class."""

    def test_perfect_accuracy(self):
        """Test when KB accepts all E+ and rejects all E-."""
        # KB: A must be true
        kb_clauses = [[1]]

        with AccuracyCalculator(kb_clauses, {'A': 1}) as calc:
            positive = [{'A': True}]
            negative = [{'A': False}]

            result = calc.calculate(positive, negative)

            assert result.metrics.accuracy == 1.0
            assert result.metrics.true_positives == 1
            assert result.metrics.true_negatives == 1
            assert result.metrics.false_positives == 0
            assert result.metrics.false_negatives == 0

    def test_false_negative(self):
        """Test when KB incorrectly rejects a positive example."""
        # KB: A and B must be true
        kb_clauses = [[1], [2]]

        with AccuracyCalculator(kb_clauses, {'A': 1, 'B': 2}) as calc:
            # E+ has A=True, B=False (should be rejected by this KB)
            positive = [{'A': True, 'B': False}]
            negative = []

            result = calc.calculate(positive, negative)

            assert result.metrics.false_negatives == 1

    def test_false_positive(self):
        """Test when KB incorrectly accepts a negative example."""
        # KB: A or B (always satisfiable if A=True)
        kb_clauses = [[1, 2]]

        with AccuracyCalculator(kb_clauses, {'A': 1, 'B': 2}) as calc:
            positive = []
            # E- has A=True (should be accepted by this KB)
            negative = [{'A': True, 'B': False}]

            result = calc.calculate(positive, negative)

            assert result.metrics.false_positives == 1


def _congen(**vals) -> RunMetrics:
    """A ConGen RunMetrics with the named values; the rest zeroed."""
    return RunMetrics(CONGEN_METRICS, {m.key: vals.get(m.key, 0.0) for m in CONGEN_METRICS})


def _quacq(**vals) -> RunMetrics:
    """A QuAcq RunMetrics with the named values; the rest zeroed."""
    return RunMetrics(QUACQ_METRICS, {m.key: vals.get(m.key, 0.0) for m in QUACQ_METRICS})


class TestPerformanceMetrics:
    """Test the declarative RunMetrics container + generic aggregate() reducer."""

    def test_aggregate_metrics(self):
        """Aggregating core metrics from multiple runs (mean/min/max)."""
        agg = aggregate([
            _congen(runtime_ms=100, consistency_checks=50, memory_peak_mb=10, n_mss=20, n_kb=5),
            _congen(runtime_ms=200, consistency_checks=70, memory_peak_mb=15, n_mss=25, n_kb=7),
        ])
        assert agg['n_runs'] == 2
        assert agg['runtime']['mean_ms'] == 150  # (100 + 200) / 2
        assert agg['runtime']['min_ms'] == 100
        assert agg['runtime']['max_ms'] == 200
        assert agg['consistency_checks']['mean'] == 60  # (50 + 70) / 2
        assert agg['memory']['max_mb'] == 15
        assert agg['kb_size']['n_mss_mean'] == 22.5  # (20 + 25) / 2
        assert agg['kb_size']['n_kb_mean'] == 6  # (5 + 7) / 2

    def test_aggregate_single_run(self):
        """A single run has std == 0."""
        agg = aggregate([_congen(runtime_ms=100, consistency_checks=50, memory_peak_mb=10, n_kb=5)])
        assert agg['n_runs'] == 1
        assert agg['runtime']['std_ms'] == 0.0

    def test_aggregate_extended_metrics(self):
        """Extended profiler metrics reduce correctly."""
        agg = aggregate([
            _congen(runtime_ms=100, congen_runtime_ms=90, acqmss_runtime_ms=60, acqmss_calls=10,
                    reduce_runtime_ms=20, solver_time_ms=50, is_consistent_calls=30,
                    is_consistent_test_cases_calls=5, redundancy_consistency_checks=15),
            _congen(runtime_ms=200, congen_runtime_ms=180, acqmss_runtime_ms=120, acqmss_calls=20,
                    reduce_runtime_ms=40, solver_time_ms=100, is_consistent_calls=50,
                    is_consistent_test_cases_calls=7, redundancy_consistency_checks=25),
        ])
        assert agg['congen_runtime']['mean_ms'] == 135  # (90 + 180) / 2
        assert agg['congen_runtime']['min_ms'] == 90
        assert agg['congen_runtime']['max_ms'] == 180
        assert agg['acqmss_runtime']['mean_ms'] == 90  # (60 + 120) / 2
        assert agg['reduce_runtime']['mean_ms'] == 30  # (20 + 40) / 2
        assert agg['solver_time']['mean_ms'] == 75  # (50 + 100) / 2
        assert agg['acqmss_calls']['mean'] == 15  # (10 + 20) / 2
        assert agg['acqmss_calls']['min'] == 10
        assert agg['acqmss_calls']['max'] == 20
        assert agg['is_consistent_calls']['mean'] == 40  # (30 + 50) / 2
        assert agg['is_consistent_test_cases_calls']['mean'] == 6  # (5 + 7) / 2
        assert agg['redundancy_consistency_checks']['mean'] == 20  # (15 + 25) / 2

    def test_run_metrics_to_dict_is_spec_ordered(self):
        """RunMetrics.to_dict() is derived from the spec, so a metric cannot vanish."""
        rm = _quacq(runtime_ms=100, quacq_runtime_ms=90, findc_calls=7)
        d = rm.to_dict()
        assert list(d.keys()) == [m.key for m in QUACQ_METRICS]
        assert d['quacq_runtime_ms'] == 90
        assert d['findc_calls'] == 7
        assert d['findscope_runtime_ms'] == 0.0

    def test_aggregate_quacq_metrics(self):
        """The QuAcq table aggregates its own metrics under the frozen group names."""
        agg = aggregate([
            _quacq(runtime_ms=100, quacq_runtime_ms=80, findscope_calls=4, findc_consistency_checks=20),
            _quacq(runtime_ms=200, quacq_runtime_ms=160, findscope_calls=8, findc_consistency_checks=40),
        ])
        assert agg['quacq_runtime']['mean_ms'] == 120  # (80+160)/2
        assert agg['quacq_runtime']['min_ms'] == 80
        assert agg['quacq_runtime']['max_ms'] == 160
        assert agg['findscope_calls']['mean'] == 6  # (4+8)/2
        assert agg['findc_checks']['mean'] == 30  # (20+40)/2 — abbreviation lives in the group

    def test_congen_and_quacq_tables_are_disjoint(self):
        """ConGen's aggregate carries NO QuAcq groups, and vice versa (ADR-0006):
        a third algorithm can no longer inject zeroed fields into everyone's file.
        Any shared metric key is in the declared common core.
        """
        cg = aggregate([_congen(runtime_ms=1)])
        qa = aggregate([_quacq(runtime_ms=1)])
        assert 'quacq_runtime' not in cg and 'findscope_calls' not in cg
        assert 'congen_runtime' not in qa and 'acqmss_calls' not in qa
        shared = {m.key for m in CONGEN_METRICS} & {m.key for m in QUACQ_METRICS}
        assert shared <= COMMON_KEYS

    def test_aggregate_empty_list(self):
        """An empty run list raises."""
        with pytest.raises(ValueError):
            aggregate([])


class TestReportGeneration:
    """Test report generation functions."""

    def test_generate_evaluation_report(self):
        """Test evaluation report generation."""
        from conacq.eval import ComparationResult

        result = ComparationResult(
            strategy='description',
            metrics=EvaluationMetrics(
                true_positives=5,
                true_negatives=3,
                false_positives=1,
                false_negatives=1
            ),
            kb_constraints=['c1', 'c2', 'c3'],
            matched_constraints=['c1', 'c2'],
            missed_constraints=['m1'],
            extra_constraints=['e1'],
            kb_reduction_ratio=0.9
        )

        report = generate_evaluation_report(result)

        assert 'ConGen Evaluation Report' in report
        assert 'Accuracy' in report
        assert 'Precision' in report
        assert 'description' in report

    def test_generate_accuracy_report(self):
        """Test accuracy report generation."""
        result = AccuracyResult(
            metrics=EvaluationMetrics(
                true_positives=8,
                true_negatives=2,
                false_positives=0,
                false_negatives=0
            ),
            tp_examples=['e1+', 'e2+'],
            tn_examples=['e1-'],
            fp_examples=[],
            fn_examples=[]
        )

        report = generate_accuracy_report(result)

        assert 'KB Accuracy Report' in report
        assert 'Formula 1' in report

    def test_cv_report_and_unified_dict_read_dict_performance(self):
        """Regression (report.py:157 + :262): since the T9 metrics refactor,
        CrossValidationResult.performance is the aggregate() DICT — generate_cv_report
        must NOT attribute-access it (`p.runtime_mean_ms`) and generate_unified_cv_dict
        must NOT call `.to_dict()` on it. Both crashed for every algorithm's CV CLI."""
        from conacq.eval import generate_cv_report, generate_unified_cv_dict
        from conacq.eval.cross_validation import (
            CrossValidationResult, CrossValidationFoldResult)
        from conacq.runners.metrics import aggregate

        perf = aggregate([_congen(runtime_ms=100, consistency_checks=50,
                                  memory_peak_mb=10, n_mss=20, n_kb=5)])
        assert isinstance(perf, dict)          # the shape both functions must handle

        fr = CrossValidationFoldResult(
            fold_index=0, accuracy=0.9,
            metrics=EvaluationMetrics(true_positives=4, true_negatives=3,
                                      false_positives=1, false_negatives=0),
            performance=_congen(runtime_ms=100, n_kb=5),
            kb_constraints=['c1', 'c2'], bg_clauses=[[1]], redundant_constraints=[],
            n_bias=10, n_kb=5, n_train_pos=8, n_train_neg=2, n_test_pos=2,
            n_test_neg=1, n_mss=20)
        cv = CrossValidationResult(
            n_folds=1, fold_accuracies=[0.9], mean_accuracy=0.9, std_accuracy=0.0,
            fold_results=[fr], performance=perf, intersected_kb=['c1'],
            bg_clauses=[[1]], total_runtime_ms=123.0)

        # :157 — reads the dict, no AttributeError, and shows the real aggregated numbers.
        report = generate_cv_report(cv)
        assert 'Runtime (per fold)' in report
        assert f"{perf['runtime']['mean_ms']:.2f} ms" in report
        assert f"{perf['kb_size']['n_kb_mean']:.1f}" in report

        # :262 — emits the dict directly (no .to_dict()).
        class _FakeBias:
            def has_constraint(self, cid): return False
            def get_description(self, cid): return cid

        unified = generate_unified_cv_dict(cv, _FakeBias())
        assert unified['performance'] == perf
        assert unified['performance']['consistency_checks']['mean'] == 50

    def test_cv_report_tolerates_missing_kb_size_group(self):
        """QuAcq's aggregate() has no kb_size group; generate_cv_report must not
        KeyError on it (defensive dict reads)."""
        from conacq.eval import generate_cv_report
        from conacq.eval.cross_validation import (
            CrossValidationResult, CrossValidationFoldResult)
        from conacq.runners.metrics import aggregate

        perf = aggregate([_quacq(runtime_ms=100)])   # no kb_size group
        assert 'kb_size' not in perf
        fr = CrossValidationFoldResult(
            fold_index=0, accuracy=1.0,
            metrics=EvaluationMetrics(true_positives=1, true_negatives=1,
                                      false_positives=0, false_negatives=0),
            performance=_quacq(runtime_ms=100), kb_constraints=[], bg_clauses=[[1]],
            redundant_constraints=[], n_bias=1, n_kb=0, n_train_pos=1, n_train_neg=1,
            n_test_pos=1, n_test_neg=1)
        cv = CrossValidationResult(
            n_folds=1, fold_accuracies=[1.0], mean_accuracy=1.0, std_accuracy=0.0,
            fold_results=[fr], performance=perf, intersected_kb=[], bg_clauses=[[1]],
            total_runtime_ms=1.0)
        report = generate_cv_report(cv)          # must not raise
        assert 'KB Size' in report and '0.0' in report


class TestIntegration:
    """Integration tests with actual data files."""

    def test_evaluate_real_fm_7(self):
        """Test evaluation with REAL-FM-7 data."""
        comparator = KBComparator.from_files(FM_PATH, BIAS_PATH)
        result = ConGenResultData.from_json(RESULT_PATH)

        eval_result = comparator.compare(result, ComparationStrategy.DESCRIPTION)

        # Basic sanity checks
        assert eval_result.metrics.accuracy >= 0
        assert eval_result.metrics.accuracy <= 1
        assert len(eval_result.kb_constraints) > 0

    def test_accuracy_with_real_examples(self):
        """Test accuracy calculation with real examples."""
        from conacq.examples import ExampleIO

        bias = BiasIO.load_from_json(str(BIAS_PATH))
        examples = ExampleIO.load_json(EXAMPLES_RS_1N_PATH)
        result = ConGenResultData.from_json(RESULT_PATH)

        # Build KB clauses
        kb_clauses = []
        for cid in result.kb_constraints:
            if bias.has_constraint(cid):
                kb_clauses.extend(bias.get_clauses(cid))

        with AccuracyCalculator(kb_clauses, bias.feature_ids) as calc:
            pos_assignments = [e.assignments for e in examples.positive]
            neg_assignments = [e.assignments for e in examples.negative]
            accuracy_result = calc.calculate(
                pos_assignments,
                neg_assignments
            )

        # Sanity checks - accuracy should be valid
        assert 0 <= accuracy_result.metrics.accuracy <= 1
        # Should have processed all examples
        total = (accuracy_result.metrics.true_positives +
                 accuracy_result.metrics.true_negatives +
                 accuracy_result.metrics.false_positives +
                 accuracy_result.metrics.false_negatives)
        assert total == len(examples.positive) + len(examples.negative)

    def test_clause_eval_includes_bg_clauses(self):
        """Verify bg_clauses are unioned with kb_clauses in clause eval."""
        comparator = KBComparator.from_files(FM_PATH, BIAS_PATH)

        # Get root feature ID from ground truth
        root_id = comparator.ground_truth.feature_map[comparator.ground_truth.root_feature]

        # Result with NO KB but WITH bg_clauses containing root
        result_with_bg = ConGenResultData(
            kb_constraints=[],
            n_bias=len(comparator.bias.constraints),
            n_kb=0,
            bg_clauses=[[root_id]]
        )

        # Result with NO KB and NO bg_clauses
        result_without_bg = ConGenResultData(
            kb_constraints=[],
            n_bias=len(comparator.bias.constraints),
            n_kb=0,
            bg_clauses=[]
        )

        eval_with = comparator.compare(result_with_bg, ComparationStrategy.CLAUSE)
        eval_without = comparator.compare(result_without_bg, ComparationStrategy.CLAUSE)

        # With bg_clauses: root clause should be TP → more TP, fewer FN
        assert eval_with.metrics.true_positives >= eval_without.metrics.true_positives
        assert eval_with.metrics.false_negatives <= eval_without.metrics.false_negatives

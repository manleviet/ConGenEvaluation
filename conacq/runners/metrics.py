"""Run metrics — one declaration, three derivations.

A runner produces performance metrics; this module is where they are *declared*
(not where a run is *evaluated* — that is ``conacq/eval``). Living here, it
removes the only ``runners → eval`` edge (ADR-0006).

The profiler (ADR-0003) already collects metrics generically, in a dict. Rather
than flatten that into hardcoded fields and pay to rebuild it, a single
``MetricSpec`` table per algorithm drives all three derivations:

    MetricSpec table  ─┬─►  collect(profiler)     one RunMetrics per run
                       ├─►  RunMetrics.to_dict()  per-run JSON  (spec order)
                       └─►  aggregate(runs)        on-disk block (spec order)

Adding a metric is one line in a table; it cannot silently vanish from the JSON
because ``to_dict`` is *derived* from the table, not typed in parallel to it.

**Naming rule (reproduces the frozen on-disk schema).** A group with ONE metric
emits ``{stat}{unit}``; a group with MORE THAN ONE emits ``{key}_{stat}{unit}``.
The rule exists only to reproduce a legacy schema — not a design principle. If
the export is ever un-frozen, delete it and emit ``{key}_{stat}`` uniformly.
"""
from __future__ import annotations

import statistics
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Mapping, Optional, Tuple


class Kind(Enum):
    """How a metric is read out of the profiler."""

    COUNTER = auto()    # profiler.get_metric(source, 0)              -> int
    TIMER_SEC = auto()  # sum(profiler.get_metric(source, [0])) * 1e3 -> ms
    GAUGE = auto()      # profiler.get_metric(source, 0.0)            -> float


@dataclass(frozen=True)
class MetricSpec:
    """One metric, declared once across all three naming spaces.

    ``key``    in-memory + per-run JSON key   e.g. ``'query_generation_runtime_ms'``
    ``source`` profiler key                   e.g. ``'query_generation_runtime'``
    ``group``  on-disk group name             e.g. ``'query_gen_runtime'`` — the
               abbreviation lives HERE, declared, not hidden in a third hand-list.
    ``unit``   ``''`` | ``'_ms'`` | ``'_mb'`` — the suffix the aggregated stat carries.
    ``stats``  which reductions the aggregated block emits, in order.
    """

    key: str
    source: str
    kind: Kind
    group: str
    unit: str = ''
    stats: Tuple[str, ...] = ('mean', 'std', 'min', 'max')


# --------------------------------------------------------------------------- #
# Metric tables — one per algorithm, disjoint but for a declared common core.  #
# --------------------------------------------------------------------------- #

# Metrics shared by every acquisition run (same key + meaning). Declared once so
# the disjointness check can allow them in both tables without re-polluting.
_CORE: Tuple[MetricSpec, ...] = (
    MetricSpec('consistency_checks', 'paper_consistency_checks', Kind.COUNTER, 'consistency_checks'),
    MetricSpec('memory_peak_mb', 'memory_peak_mb', Kind.GAUGE, 'memory', '_mb', stats=('mean', 'max')),
    MetricSpec('reduce_runtime_ms', 'reduce_runtime', Kind.TIMER_SEC, 'reduce_runtime', '_ms'),
    MetricSpec('solver_time_ms', 'solver_time', Kind.TIMER_SEC, 'solver_time', '_ms'),
    MetricSpec('is_consistent_calls', 'is_consistent_calls', Kind.COUNTER, 'is_consistent_calls'),
    MetricSpec('is_consistent_test_cases_calls', 'is_consistent_test_cases_calls', Kind.COUNTER,
               'is_consistent_test_cases_calls'),
    MetricSpec('redundancy_consistency_checks', 'redundancy_consistency_checks', Kind.COUNTER,
               'redundancy_consistency_checks'),
)

# Keys the MSS-based passive algorithms emit — each builds an
# admissible MSS, calls AcqMSS, and reports a final KB size — so they are shared by
# meaning. Kept OUT of COMMON_KEYS on purpose: COMMON_KEYS stays the NARROW core so
# the ConGen∩QuAcq guard still trips if QuAcq ever grows an MSS key.
#
_MSS_SHARED: frozenset = frozenset(
    {'n_mss', 'n_kb', 'acqmss_runtime_ms', 'acqmss_calls'}
)

# Keys allowed to appear in more than one algorithm table (the declared common
# core). ``runtime_ms`` is here too: both algorithms emit it, from *different*
# timers (congen_total_time vs quacq_total_time), so it is a shared output key.
COMMON_KEYS: frozenset = frozenset(
    {'runtime_ms'} | {m.key for m in _CORE}
)

CONGEN_METRICS: Tuple[MetricSpec, ...] = (
    MetricSpec('runtime_ms', 'congen_total_time', Kind.TIMER_SEC, 'runtime', '_ms'),
    _CORE[0],  # consistency_checks
    _CORE[1],  # memory
    MetricSpec('n_mss', 'n_mss', Kind.GAUGE, 'kb_size', '', stats=('mean',)),
    MetricSpec('n_kb', 'n_kb', Kind.GAUGE, 'kb_size', '', stats=('mean',)),
    MetricSpec('congen_runtime_ms', 'congen_runtime', Kind.TIMER_SEC, 'congen_runtime', '_ms'),
    MetricSpec('acqmss_runtime_ms', 'acqmss_runtime', Kind.TIMER_SEC, 'acqmss_runtime', '_ms'),
    MetricSpec('acqmss_calls', 'acqmss_calls', Kind.COUNTER, 'acqmss_calls'),
    _CORE[2],  # reduce_runtime
    _CORE[3],  # solver_time
    _CORE[4],  # is_consistent_calls
    _CORE[5],  # is_consistent_test_cases_calls
    _CORE[6],  # redundancy_consistency_checks
)

QUACQ_METRICS: Tuple[MetricSpec, ...] = (
    MetricSpec('runtime_ms', 'quacq_total_time', Kind.TIMER_SEC, 'runtime', '_ms'),
    _CORE[0],  # consistency_checks
    _CORE[1],  # memory
    MetricSpec('quacq_runtime_ms', 'quacq_runtime', Kind.TIMER_SEC, 'quacq_runtime', '_ms'),
    MetricSpec('query_generation_runtime_ms', 'query_generation_runtime', Kind.TIMER_SEC,
               'query_gen_runtime', '_ms'),
    MetricSpec('findscope_runtime_ms', 'findscope_runtime', Kind.TIMER_SEC, 'findscope_runtime', '_ms'),
    MetricSpec('findc_runtime_ms', 'findc_runtime', Kind.TIMER_SEC, 'findc_runtime', '_ms'),
    MetricSpec('dis_gen_runtime_ms', 'dis_gen_runtime', Kind.TIMER_SEC, 'dis_gen_runtime', '_ms'),
    _CORE[2],  # reduce_runtime
    _CORE[3],  # solver_time
    _CORE[4],  # is_consistent_calls
    _CORE[5],  # is_consistent_test_cases_calls
    MetricSpec('quacq_calls', 'quacq_calls', Kind.COUNTER, 'quacq_calls'),
    MetricSpec('query_generation_calls', 'query_generation_calls', Kind.COUNTER, 'query_gen_calls'),
    MetricSpec('query_generation_consistency_checks', 'query_generation_consistency_checks',
               Kind.COUNTER, 'query_gen_checks'),
    MetricSpec('prune_calls', 'prune_calls', Kind.COUNTER, 'prune_calls'),
    MetricSpec('prune_is_consistent_calls', 'prune_is_consistent_calls', Kind.COUNTER, 'prune_ic_calls'),
    MetricSpec('findscope_calls', 'findscope_calls', Kind.COUNTER, 'findscope_calls'),
    MetricSpec('findc_calls', 'findc_calls', Kind.COUNTER, 'findc_calls'),
    MetricSpec('findc_consistency_checks', 'findc_consistency_checks', Kind.COUNTER, 'findc_checks'),
    MetricSpec('dis_gen_calls', 'dis_gen_calls', Kind.COUNTER, 'dis_gen_calls'),
    MetricSpec('dis_gen_consistency_checks', 'dis_gen_consistency_checks', Kind.COUNTER, 'dis_gen_checks'),
    MetricSpec('reduce_calls', 'reduce_calls', Kind.COUNTER, 'reduce_calls'),
    _CORE[6],  # redundancy_consistency_checks
)




# Profiler keys a run emits that are deliberately NOT exported as metrics — the
# explicit "collected but not a metric" list. It makes the omission a decision on
# the record, so the completeness test can prove no metric silently vanishes (the
# failure mode of the old hand-written design). ConGen's set is pinned against the
# profiler snapshot in the recorded results; ``reduce_calls`` is a QuAcq metric,
# not a ConGen one, so ConGen ignores it.
CONGEN_IGNORED: frozenset = frozenset({
    'congen_calls',
    'quickxplain_calls', 'quickxplain_runtime', 'qx_calls', 'qx_runtime',
    'reduce_calls',
    'solver_time_accum',
})


@dataclass(frozen=True)
class RunMetrics:
    """One run's metric values, tied to the spec that produced them."""

    spec: Tuple[MetricSpec, ...]
    values: Mapping[str, float]

    def to_dict(self) -> dict:
        """Per-run JSON body, in spec (declaration) order."""
        return {m.key: self.values[m.key] for m in self.spec}


def collect(profiler, spec: Tuple[MetricSpec, ...],
            extra: Optional[Mapping[str, float]] = None) -> RunMetrics:
    """Read one run's metrics out of the profiler, per the spec.

    ``extra`` supplies values that do not live in the profiler (memory from
    tracemalloc, KB sizes from the result), keyed by the spec's ``source``.
    """
    extra = extra or {}
    values: Dict[str, float] = {}
    for m in spec:
        if m.source in extra:
            values[m.key] = extra[m.source]
        elif m.kind is Kind.COUNTER:
            values[m.key] = profiler.get_metric(m.source, 0)
        elif m.kind is Kind.TIMER_SEC:
            values[m.key] = sum(profiler.get_metric(m.source, [0])) * 1000
        else:  # GAUGE
            values[m.key] = profiler.get_metric(m.source, 0.0)
    return RunMetrics(spec, values)


def _reduce(stat: str, values: List[float]):
    if stat == 'mean':
        return statistics.mean(values)
    if stat == 'std':
        return statistics.stdev(values) if len(values) > 1 else 0.0
    if stat == 'min':
        return min(values)
    if stat == 'max':
        return max(values)
    raise ValueError(f"unknown stat {stat!r}")


def aggregate(runs: List[RunMetrics]) -> dict:
    """Aggregate runs into the on-disk ``{group: {stat: value}}`` block.

    Groups by ``spec.group`` (spec order preserved), applies each metric's
    ``stats``, and names each entry by the rule in the module docstring — one
    generic reducer where there used to be ~365 hand-written lines.
    """
    if not runs:
        raise ValueError("Empty metrics list")

    spec = runs[0].spec
    out: dict = {'n_runs': len(runs)}

    grouped: "OrderedDict[str, List[MetricSpec]]" = OrderedDict()
    for m in spec:
        grouped.setdefault(m.group, []).append(m)

    for group_name, specs in grouped.items():
        multi = len(specs) > 1
        block: dict = {}
        for m in specs:
            series = [runs[i].values[m.key] for i in range(len(runs))]
            for stat in m.stats:
                name = f"{m.key}_{stat}{m.unit}" if multi else f"{stat}{m.unit}"
                block[name] = _reduce(stat, series)
        out[group_name] = block

    return out

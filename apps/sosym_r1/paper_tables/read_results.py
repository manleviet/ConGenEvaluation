"""The generator's readers: committed JSON in, per-fold aggregates out.

ONE AGGREGATION, STATED ONCE. Every quality metric here is the mean over folds,
per the standing rule that a quoted number must name its aggregation. The two
other aggregations that exist in these files -- the intersected KB, and a pooled
figure -- are deliberately unreachable from this module: each has already produced
a published number that was not the one the paper computes.

The gate (``check_paper_tables.py``) does NOT import this module. It re-reads the
same JSON with its own code, so a mistake here has to be made twice, identically,
to survive.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from .frozen import is_not_run


class Missing(Exception):
    """A file the tables need is absent. Never swallowed into a blank cell."""


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _folds(doc: dict | None) -> list[dict]:
    return (doc or {}).get("folds") or []


def _tier(fold: dict, tier: str) -> dict:
    """``evaluation.<tier>.metrics``.

    The nesting matters: one level shallower holds the strategy label rather than
    numbers, and reading it returns a ``.get`` default of 0 on every fold -- which
    is how "the precision and recall do not exist anywhere" was once reported.
    """
    return ((fold.get("evaluation") or {}).get(tier) or {}).get("metrics") or {}


def mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return st.mean(values), (st.stdev(values) if len(values) > 1 else 0.0)


class ResultTree:
    """The one acquisition tree every table is computed from."""

    def __init__(self, root: Path):
        self.root = root
        self.congen = root / "congen"
        self.interactive = root / "interactive"

    # ---------------------------------------------------------------- passive
    def congen_doc(self, stem: str, sampling: str) -> dict | None:
        return _load(self.congen / f"{stem}_{sampling}_cv_incremental.json")

    def congen_folds(self, stem: str, sampling: str) -> list[dict]:
        return _folds(self.congen_doc(stem, sampling))

    # --------------------------------------------------------------- iterative
    def iterative_folds(self, stem: str, sampling: str, mode: str) -> list[dict]:
        return _folds(_load(
            self.interactive / f"{stem}_{sampling}_cv_incremental_{mode}.json"))

    # ------------------------------------------------------------------ values
    def accuracy(self, folds: list[dict]) -> tuple[float | None, float | None]:
        return mean_sd([f["accuracy"] for f in folds if f.get("accuracy") is not None])

    def tier_f1(self, folds: list[dict], tier: str) -> float | None:
        vals = [_tier(f, tier).get("f1_score") for f in folds if _tier(f, tier)]
        vals = [v for v in vals if v is not None]
        return st.mean(vals) if vals else None

    def semantic(self, folds: list[dict], key: str) -> float | None:
        vals = [_tier(f, "semantic").get(key) for f in folds if _tier(f, "semantic")]
        vals = [v for v in vals if v is not None]
        return st.mean(vals) if vals else None

    def exact_equivalence(self, folds: list[dict]) -> tuple[int, int]:
        """(attained, scored). Scored counts folds where the check actually ran."""
        scored = [f for f in folds if (f.get("evaluation") or {}).get("exact_equiv") is not None]
        attained = [f for f in scored
                    if (f.get("evaluation") or {})["exact_equiv"] in (1, True)]
        return len(attained), len(scored)

    def statistic(self, folds: list[dict], key: str) -> float | None:
        vals = [(f.get("statistics") or {}).get(key) for f in folds]
        vals = [v for v in vals if v is not None]
        return st.mean(vals) if vals else None

    def runtime_ms(self, folds: list[dict]) -> float | None:
        vals = [(f.get("performance") or {}).get("runtime_ms") for f in folds]
        vals = [v for v in vals if v is not None]
        return st.mean(vals) if vals else None

    def kb_size(self, folds: list[dict]) -> float | None:
        """Mean over folds of the number of constraints in the learned KB.

        Counted from the ``kb_constraints`` LIST, not from the recorded
        ``statistics.n_kb``. The two agree on every committed fold, which is why
        reading the list costs nothing and is the stronger source: a summary field
        is written once and can outlive the thing it summarises.

        The negated negative examples are NOT here. They sit in ``ne_constraints``
        and are a record of what the oracle rejected, not knowledge the method
        acquired; counting them would make a method look more productive the more
        often it was wrong.
        """
        vals = [len(f["kb_constraints"]) for f in folds if f.get("kb_constraints") is not None]
        return st.mean(vals) if vals else None

    def queries(self, folds: list[dict]) -> float | None:
        vals = [f.get("n_queries") for f in folds if f.get("n_queries") is not None]
        return st.mean(vals) if vals else None

    def stop_reasons(self, folds: list[dict]) -> list[str]:
        return sorted({f["convergence_reason"] for f in folds
                       if f.get("convergence_reason")})

    # ------------------------------------------------------------------ phases
    # ------------------------------------------------------------------ phases
    #
    # NO DEFAULTING. Every read below either finds its key or raises, with one
    # justified exception stated at the point it is taken. A ``.get(key, 0)`` cannot
    # tell "the phase cost nothing" from "the fold never recorded it", and the two
    # produce different means; reading the second as the first is how a preprocessing
    # cost would be silently understated.

    @staticmethod
    def _perf(fold: dict, key: str) -> float:
        perf = fold.get("performance") or {}
        if key not in perf:
            raise Missing(f"fold {fold.get('fold_index')} has no performance.{key}")
        return perf[key]

    @staticmethod
    def _prof(fold: dict, key: str) -> float:
        prof = (fold.get("performance") or {}).get("profiler") or {}
        if key not in prof:
            raise Missing(f"fold {fold.get('fold_index')} has no profiler.{key}")
        return prof[key]

    @staticmethod
    def _prof_ms(fold: dict, key: str) -> float:
        block = ResultTree._prof(fold, key)
        return block["total"] * 1000.0

    @staticmethod
    def _preprocessing(fold: dict, key: str, ms: bool) -> float:
        """GenerateNE/QuickXplain, whose counters exist only if the phase ran.

        THE ONE JUSTIFIED ZERO IN THIS MODULE, and it is justified from the fold
        rather than from the absence. GenerateNE explains negative examples:
        ``generate_ne.py`` returns before the loop that creates these counters when
        the test suite is empty, so a fold with no negative training example never
        creates them. The phase ran zero times and cost zero -- a MEASURED zero, not
        a missing measurement, and the fold belongs in the mean at 0.

        Measured over all 84 folds: the counters are absent in exactly the 5 folds
        with ``train_size.negative == 0``, and present in the other 79. The
        correspondence is exact in both directions, so a key missing while the fold
        HAS negatives is something else entirely -- and raises.
        """
        prof = (fold.get("performance") or {}).get("profiler") or {}
        if key in prof:
            return prof[key]["total"] * 1000.0 if ms else prof[key]
        negatives = (fold.get("train_size") or {}).get("negative")
        if negatives == 0:
            return 0.0
        raise Missing(
            f"fold {fold.get('fold_index')} has no profiler.{key} but its training "
            f"split holds {negatives} negative example(s). The phase should have run. "
            f"This is not the empty-test-suite case and must not be read as zero.")

    def phases_ms(self, folds: list[dict]) -> dict[str, float | None]:
        """Per-phase wall clock in milliseconds, as per-fold means over ALL folds.

        THE SCOPES, measured over all 84 folds rather than assumed:

          ``reduce_runtime_ms`` is INSIDE ``congen_runtime_ms``     (0 violations)
          ``shared_preprocessing_runtime`` is DISJOINT from it      (0 violations)
          their sum is within ``runtime_ms``                        (0 violations)
          ``profiler.congen_total_time`` == ``runtime_ms``          (0 violations)

        So AcqMss is the acquisition loop minus Reduce, and preprocessing is NOT
        subtracted from the loop -- it was never part of it. Subtracting it anyway
        printed a NEGATIVE AcqMss duration, and the cell gate agreed, because a
        re-derivation shares the definition and will agree with a wrong one.

        The three phases sum to LESS than the total. The remainder is setup and
        teardown outside every timing scope and stays unattributed.

        ``acqmss_runtime`` is NOT read: it accumulates over thousands of nested
        recursive calls -- 149.9 s against a 15.2 s run -- so it is not a duration.
        """
        acq, red, pre, tot = [], [], [], []
        for f in folds:
            loop = self._perf(f, "congen_runtime_ms")
            reduce_ms = self._perf(f, "reduce_runtime_ms")
            red.append(reduce_ms)
            pre.append(self._preprocessing(f, "shared_preprocessing_runtime", ms=True))
            acq.append(loop - reduce_ms)
            tot.append(self._perf(f, "runtime_ms"))
        m = lambda xs: st.mean(xs) if xs else None  # noqa: E731
        return {"acqmss": m(acq), "reduce": m(red), "preprocessing": m(pre),
                "total": m(tot), "n_folds": len(acq)}

    def phase_checks(self, folds: list[dict]) -> dict[str, float | None]:
        """Per-phase consistency checks, as per-fold means over ALL folds."""
        acq = [self._prof(f, "paper_consistency_checks") for f in folds]
        red = [self._perf(f, "redundancy_consistency_checks") for f in folds]
        pre = [self._preprocessing(f, "shared_preprocessing_quickxplain_checks", ms=False)
               for f in folds]
        m = lambda xs: st.mean(xs) if xs else None  # noqa: E731
        out = {"acqmss": m(acq), "reduce": m(red), "preprocessing": m(pre),
               "n_folds": len(acq)}
        out["total"] = (None if out["acqmss"] is None
                        else out["acqmss"] + out["reduce"] + out["preprocessing"])
        return out

    def consistency_checks(self, folds: list[dict]) -> float | None:
        vals = [(f.get("performance") or {}).get("consistency_checks") for f in folds]
        vals = [v for v in vals if v is not None]
        return st.mean(vals) if vals else None

    # ------------------------------------------------------------------- guard
    def require(self, stem: str, sampling: str) -> list[dict]:
        """Folds for a unit that is supposed to have them, or a loud failure."""
        folds = self.congen_folds(stem, sampling)
        if not folds and not is_not_run(stem, sampling):
            raise Missing(f"no ConGen result for {stem} {sampling}, and it is not "
                          f"declared as not-run in frozen.py")
        return folds


def example_sizes(examples_dir: Path, stem: str, sampling: str) -> tuple[int, int] | None:
    """(|E+|, |E-|) counted from the committed example set.

    COUNTED, not read from the file's own ``statistics`` block -- and then checked
    against it. The block is a summary written at generation time; the lists are
    what every run actually consumed. If the two ever disagree, the summary is
    stale and the table would otherwise print the stale number without a murmur.
    """
    doc = _load(examples_dir / f"{stem}_{sampling}.json")
    if doc is None:
        return None
    pos, neg = len(doc["positive"]), len(doc["negative"])
    stats = doc.get("statistics") or {}
    declared = (stats.get("n_positive"), stats.get("n_negative"))
    if declared != (None, None) and declared != (pos, neg):
        raise Missing(f"{stem} {sampling}: example lists hold {pos}/{neg} but the "
                      f"file's statistics block declares {declared[0]}/{declared[1]}")
    return pos, neg


def bias_stats(bias_dir: Path, stem: str) -> dict[str, int]:
    """#features, |B| and #clauses, parsed from the committed bias statistics."""
    path = bias_dir / f"{stem}-bias-stats.txt"
    if not path.exists():
        raise Missing(f"bias statistics missing for {stem}: {path}")
    want = {"Total features": "features", "Total constraints": "bias",
            "Total clauses": "clauses"}
    out: dict[str, int] = {}
    for line in path.read_text().splitlines():
        for prefix, key in want.items():
            if line.startswith(prefix):
                out[key] = int(line.split(":")[1].strip())
    missing = set(want.values()) - set(out)
    if missing:
        raise Missing(f"{path} does not state {sorted(missing)}")
    return out

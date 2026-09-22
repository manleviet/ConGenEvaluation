"""Rule-learner baselines (C4) — feature table, rule→CNF conversion, learner adapters.

Comparison baselines only; nothing here is part of the acquisition pipeline. The
learner adapters import their libraries lazily (``baselines`` / ``baselines-cn2``
extras), so importing this package on a clean environment is safe.
"""
from .feature_table import INVALID, VALID, FeatureTable, build_feature_table

__all__ = ["INVALID", "VALID", "FeatureTable", "build_feature_table"]

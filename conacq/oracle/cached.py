"""
Caching wrapper for any membership oracle.

Caches membership query results to avoid redundant queries.
Only caches is_valid() — a MembershipOracle wrapper, no base class.
"""

from typing import Dict

from conacq.oracle.protocols import MembershipOracle


class CachedOracle(MembershipOracle):
    """Oracle wrapper that caches answers to avoid redundant queries.

    Declares the MembershipOracle role (ADR-0010) — delegates is_valid to the
    wrapped oracle. Useful when the same configuration might be queried repeatedly.

    Example:
        >>> base_oracle = FMOracle('model.uvl')
        >>> oracle = CachedOracle(base_oracle)
        >>> oracle.is_valid({'A': True})  # Asks base oracle
        >>> oracle.is_valid({'A': True})  # Returns cached answer
    """

    def __init__(self, base_oracle: "MembershipOracle"):
        """Initialize cached oracle.

        Args:
            base_oracle: Underlying oracle to cache (any MembershipOracle)
        """
        self.base_oracle = base_oracle
        self._cache: Dict[tuple, bool] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _config_to_key(self, config: Dict[str, bool]) -> tuple:
        """Convert configuration to hashable cache key."""
        return tuple(sorted(config.items()))

    def is_valid(self, assignments: Dict[str, bool]) -> bool:
        """Answer query, using cache if available.

        Args:
            assignments: Configuration as {feature_name: True/False}

        Returns:
            Cached or fresh answer from base oracle
        """
        key = self._config_to_key(assignments)

        if key in self._cache:
            self._cache_hits += 1
            return self._cache[key]

        self._cache_misses += 1
        answer = self.base_oracle.is_valid(assignments)
        self._cache[key] = answer
        return answer

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'size': len(self._cache)
        }

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def __repr__(self):
        return (f"CachedOracle(hits={self._cache_hits}, "
                f"misses={self._cache_misses}, size={len(self._cache)})")

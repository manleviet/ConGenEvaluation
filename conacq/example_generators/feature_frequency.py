"""
Feature Frequency (FF) generator for test case generation.

Ensures each feature appears in both True and False states
in both positive and negative examples.
"""

import random
from typing import Optional, Dict, Set, List, Tuple
from conacq.examples.data_structures import Example, ExampleSet, ExampleType
from .base import ExampleGenerator


class FeatureFrequencyGenerator(ExampleGenerator):
    """
    Feature Frequency (FF) generator.

    Generates examples ensuring each feature appears:
    - As True in at least one positive example
    - As False in at least one positive example
    - As True in at least one negative example
    - As False in at least one negative example

    This ensures 4-way coverage for each feature.

    Example:
        >>> oracle = FMOracle('model.uvl')
        >>> gen = FeatureFrequencyGenerator(oracle)
        >>> examples = gen.generate(max_examples=500)
    """

    def generate(self,
                 max_examples: int = 1000,
                 seed: Optional[int] = None) -> ExampleSet:
        """
        Generate examples with feature frequency coverage.

        Uses SAT solver to generate positive examples (valid configs)
        and random generation for negative examples (invalid configs).

        Args:
            max_examples: Maximum examples to generate before stopping
            seed: Random seed for reproducibility

        Returns:
            ExampleSet with FF coverage
        """
        self._rng = random.Random(seed)

        example_set = ExampleSet(metadata={
            'method': 'FF',
            'max_examples': max_examples,
            'seed': seed
        })

        # Track coverage: {feature: {True: {'pos', 'neg'}, False: {'pos', 'neg'}}}
        coverage: Dict[str, Dict[bool, Set[str]]] = {
            f: {True: set(), False: set()}
            for f in sorted(self.features)
        }

        features_list = sorted(self.features)
        # What each half of the run can actually attain. A positive example is a
        # valid configuration, so mandatory and dead features put some pairs out
        # of reach; a negative example is an arbitrary invalid assignment, so no
        # pair is out of reach there. Both loops then share one stopping rule.
        pos_targets = self._reachable_positive_pairs(features_list)
        neg_targets = {(f, value) for f in features_list for value in (True, False)}
        generated_configs = set()  # Avoid duplicates
        count = 0

        # Phase 1: Generate positive examples to cover E+ requirements
        pos_count = 0
        max_pos_attempts = max_examples * 10

        while (not self._is_target_covered(coverage, pos_targets, 'pos')
               and pos_count < max_pos_attempts and count < max_examples):
            # Find uncovered (feature, value) for positive
            uncovered = self._get_uncovered(coverage, pos_targets, 'pos')
            if not uncovered:
                break

            # Try to generate a valid config that covers some uncovered requirements
            config = self._generate_valid_config_for_coverage(features_list, uncovered)
            if config:
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_configs:
                    generated_configs.add(config_tuple)
                    example = Example(
                        id=f"ff_{count + 1}",
                        assignments=config,
                        example_type=ExampleType.POSITIVE
                    )
                    example_set.positive.append(example)

                    # Update coverage
                    for f, val in config.items():
                        coverage[f][val].add('pos')
                    count += 1

            pos_count += 1

        # Phase 2: Generate negative examples to cover E- requirements
        neg_count = 0
        max_neg_attempts = max_examples * 10

        while (not self._is_target_covered(coverage, neg_targets, 'neg')
               and neg_count < max_neg_attempts and count < max_examples):
            # Find uncovered (feature, value) for negative
            uncovered = self._get_uncovered(coverage, neg_targets, 'neg')
            if not uncovered:
                break

            # Generate random config biased toward uncovered requirements
            config = self._generate_biased_invalid_config(features_list, uncovered)

            # Check if invalid
            if not self.oracle.is_valid(config):
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_configs:
                    generated_configs.add(config_tuple)
                    example = Example(
                        id=f"ff_{count + 1}",
                        assignments=config,
                        example_type=ExampleType.NEGATIVE
                    )
                    example_set.negative.append(example)

                    # Update coverage
                    for f, val in config.items():
                        coverage[f][val].add('neg')
                    count += 1

            neg_count += 1

        # Add coverage statistics to metadata
        example_set.metadata['coverage'] = self._coverage_stats(
            coverage, pos_targets, neg_targets)
        example_set.metadata['fully_covered'] = (
            self._is_target_covered(coverage, pos_targets, 'pos')
            and self._is_target_covered(coverage, neg_targets, 'neg'))
        example_set.metadata['reachable_positive_pairs'] = len(pos_targets)
        example_set.metadata['total_pairs'] = 2 * len(features_list)
        example_set.metadata['pos_attempts'] = pos_count
        example_set.metadata['neg_attempts'] = neg_count

        return example_set

    def _reachable_positive_pairs(self, features_list: List[str]) -> Set[Tuple[str, bool]]:
        """(feature, value) pairs that some valid configuration can exhibit.

        A mandatory feature is True in every valid configuration, so ``(f, False)``
        can never appear in a positive example; a dead feature rules out
        ``(f, True)``. The stopping condition used to demand all 2n pairs, which no
        feature model with a root can meet, so the positive loop never stopped on
        coverage and always burned its whole attempt budget.

        ``complete_configuration`` cannot serve as a plain satisfiability oracle:
        for an unsatisfiable partial it falls back to returning *any* valid
        configuration rather than None (``oracle.py:149-151``). The witness it
        returns is therefore checked -- if the fallback fired, ``config[f]`` is not
        the value that was asked for.

        That check is what makes this function do anything. Testing only
        ``is not None`` marks every pair attainable, so the target set becomes all
        2n pairs and the stopping condition stays exactly as unreachable as it was
        before, behind a diff that looks correct. Measured on REAL-FM-7: the naive
        test yields 28 pairs, the witness-checked one 26, and the two it removes
        are ``(interface, False)`` and ``(jplug, False)`` -- precisely the pairs the
        pre-fix generator reported as permanently uncovered after 1,400 attempts.

        Costs 2n oracle calls.
        """
        reachable = set()
        for f in features_list:
            for value in (True, False):
                config = self.oracle.complete_configuration({f: value})
                if config is not None and config.get(f) is value:
                    reachable.add((f, value))
        return reachable

    @staticmethod
    def _is_target_covered(coverage: Dict[str, Dict[bool, Set[str]]],
                           targets: Set[Tuple[str, bool]], bucket: str) -> bool:
        """True once every attainable pair has been seen in *bucket* ('pos'/'neg')."""
        return all(bucket in coverage[f][value] for f, value in targets)

    @staticmethod
    def _get_uncovered(coverage: Dict[str, Dict[bool, Set[str]]],
                       targets: Set[Tuple[str, bool]], bucket: str) -> List[Tuple[str, bool]]:
        """Attainable pairs still missing from *bucket*, in a deterministic order."""
        return [(f, value) for f, value in sorted(targets)
                if bucket not in coverage[f][value]]

    def _generate_valid_config_for_coverage(
            self,
            features_list: List[str],
            uncovered: List[Tuple[str, bool]]
    ) -> Optional[Dict[str, bool]]:
        """
        Generate a valid configuration that covers some uncovered requirements.

        Args:
            features_list: List of all features
            uncovered: List of (feature, value) pairs to try to cover

        Returns:
            Valid configuration dict, or None if failed
        """
        self._rng.shuffle(uncovered)
        target_feature, target_value = uncovered[0]

        # Build partial with target + random extras for diversity
        partial = {target_feature: target_value}
        other_features = [f for f in features_list if f != target_feature]
        self._rng.shuffle(other_features)
        n_extra = min(len(other_features) // 3, 5)
        for f in other_features[:n_extra]:
            partial[f] = self._rng.choice([True, False])

        # Try full partial, then target-only fallback
        config = self.oracle.complete_configuration(partial)
        if config is None:
            config = self.oracle.complete_configuration({target_feature: target_value})
        return config

    def _generate_biased_invalid_config(
            self,
            features_list: List[str],
            uncovered: List[Tuple[str, bool]]
    ) -> Dict[str, bool]:
        """
        Generate a random configuration biased toward covering uncovered requirements.

        Args:
            features_list: List of all features
            uncovered: List of (feature, value) pairs to try to cover

        Returns:
            Configuration dict (may be valid or invalid)
        """
        # Start with random
        config = {f: self._rng.choice([True, False]) for f in features_list}

        # Bias toward uncovered requirements
        self._rng.shuffle(uncovered)
        for f, val in uncovered[:5]:  # Try to satisfy up to 5 uncovered
            config[f] = val

        return config

    def _coverage_stats(self, coverage: Dict[str, Dict[bool, Set[str]]],
                        pos_targets: Set[Tuple[str, bool]],
                        neg_targets: Set[Tuple[str, bool]]) -> Dict:
        """
        Calculate coverage statistics against what is attainable.

        Counting against ``len(self.features) * 4`` reported every mandatory
        feature as a permanent gap, so the figure could never reach 100 % and said
        nothing about whether the run had finished its job.

        Args:
            coverage: Coverage tracking dictionary
            pos_targets: (feature, value) pairs a valid configuration can exhibit
            neg_targets: (feature, value) pairs an invalid assignment can exhibit

        Returns:
            Dictionary with coverage statistics
        """
        wanted = {(f, value, 'pos') for f, value in pos_targets}
        wanted |= {(f, value, 'neg') for f, value in neg_targets}
        total_needed = len(wanted)
        covered = sum(1 for f, value, bucket in wanted if bucket in coverage[f][value])

        missing_by_feature: Dict[str, List[str]] = {}
        for f, value, bucket in sorted(wanted):
            if bucket not in coverage[f][value]:
                missing_by_feature.setdefault(f, []).append(f"{value}/{bucket}")
        uncovered_features = [{'feature': f, 'missing': missing}
                              for f, missing in sorted(missing_by_feature.items())]

        return {
            'total_needed': total_needed,
            'covered': covered,
            'percentage': covered / total_needed * 100,
            'uncovered_features': uncovered_features[:10]  # Limit for readability
        }

"""
Random Sampling example_generators for test case generation.

Provides:
- RandomSamplingGenerator: Pure random configuration generation
- BalancedRandomSamplingGenerator: Balanced E⁺/E⁻ generation
- ControlledRandomSamplingGenerator: Controlled E⁺/E⁻ ratio with deduplication
"""

import random
from typing import Optional

from conacq.examples.data_structures import Example, ExampleSet, ExampleType
from .base import ExampleGenerator


class RandomSamplingGenerator(ExampleGenerator):
    """
    Random Sampling (RS) generator.

    Generates n random complete configurations and classifies them
    using the oracle. The ratio of positive to negative examples
    depends on the feature model structure.

    Example:
        >>> oracle = FMOracle('model.uvl')
        >>> gen = RandomSamplingGenerator(oracle)
        >>> examples = gen.generate(n=100, seed=42)
        >>> print(examples)
        ExampleSet(E⁺=45, E⁻=55)
    """

    def generate(self, n: int, seed: Optional[int] = None) -> ExampleSet:
        """
        Generate n random examples.

        Args:
            n: Number of examples to generate
            seed: Random seed for reproducibility

        Returns:
            ExampleSet with classified examples
        """
        self._rng = random.Random(seed)

        example_set = ExampleSet(metadata={
            'method': 'RS',
            'n': n,
            'seed': seed
        })

        features_list = sorted(self.features)

        for i in range(n):
            # Random complete assignment
            assignments = {f: self._rng.choice([True, False]) for f in features_list}

            example = Example(
                id=f"rs_{i + 1}",
                assignments=assignments
            )

            self._classify_and_add(example, example_set)

        return example_set


class BalancedRandomSamplingGenerator(ExampleGenerator):
    """
    Balanced Random Sampling generator.

    Generates roughly equal numbers of positive and negative examples.
    Uses SAT solver to generate valid configurations for E⁺.

    Example:
        >>> oracle = FMOracle('model.uvl')
        >>> gen = BalancedRandomSamplingGenerator(oracle)
        >>> examples = gen.generate(n_positive=50, n_negative=50)
        >>> print(examples)
        ExampleSet(E⁺=50, E⁻=50)
    """

    def generate(self,
                 n_positive: int,
                 n_negative: int,
                 seed: Optional[int] = None,
                 max_attempts_multiplier: int = 10) -> ExampleSet:
        """
        Generate balanced examples.

        Args:
            n_positive: Number of positive examples to generate
            n_negative: Number of negative examples to generate
            seed: Random seed for reproducibility
            max_attempts_multiplier: Max attempts = n * multiplier

        Returns:
            ExampleSet with balanced examples
        """
        self._rng = random.Random(seed)

        example_set = ExampleSet(metadata={
            'method': 'BalancedRS',
            'n_positive': n_positive,
            'n_negative': n_negative,
            'seed': seed
        })

        features_list = sorted(self.features)

        # Generate positive examples using SAT solver
        generated_pos = set()
        attempts = 0
        max_attempts = n_positive * max_attempts_multiplier

        while len(example_set.positive) < n_positive and attempts < max_attempts:
            config = self._generate_valid_config(features_list)
            if config:
                # Check for duplicates
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_pos:
                    generated_pos.add(config_tuple)
                    example = Example(
                        id=f"e{len(example_set.positive) + 1}+",
                        assignments=config,
                        example_type=ExampleType.POSITIVE
                    )
                    example_set.positive.append(example)
            attempts += 1

        # Generate negative examples by random + rejection
        generated_neg = set()
        neg_attempts = 0
        max_neg_attempts = n_negative * max_attempts_multiplier

        while len(example_set.negative) < n_negative and neg_attempts < max_neg_attempts:
            # Random configuration
            config = {f: self._rng.choice([True, False]) for f in features_list}

            # Check if invalid (negative)
            if not self.oracle.is_valid(config):
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_neg:
                    generated_neg.add(config_tuple)
                    example = Example(
                        id=f"e{len(example_set.negative) + 1}-",
                        assignments=config,
                        example_type=ExampleType.NEGATIVE
                    )
                    example_set.negative.append(example)

            neg_attempts += 1

        # Update metadata with actual counts
        example_set.metadata['actual_positive'] = len(example_set.positive)
        example_set.metadata['actual_negative'] = len(example_set.negative)

        return example_set


class ControlledRandomSamplingGenerator(ExampleGenerator):
    """
    Controlled Random Sampling generator with E⁺/E⁻ ratio control.

    Generates examples with controlled distribution:
    - n_negative = total // 10 (minimum 1)
    - n_positive = total - n_negative
    - If n_positive > valid_configs: adjust to use valid_configs for E⁺

    Ensures no duplicate examples.

    Example:
        >>> oracle = FMOracle('model.uvl')
        >>> gen = ControlledRandomSamplingGenerator(oracle)
        >>> examples = gen.generate(total=100, valid_configs=80, seed=42)
        >>> print(examples)
        ExampleSet(E⁺=80, E⁻=20)
    """

    @staticmethod
    def calculate_distribution(total: int, valid_configs: Optional[int] = None) -> tuple:
        """
        Calculate E⁺/E⁻ distribution.

        Args:
            total: Total number of examples to generate
            valid_configs: Number of valid configurations (optional)

        Returns:
            Tuple of (n_positive, n_negative)
        """
        # Default: 10% negative, minimum 1
        n_negative = max(1, total // 10)
        n_positive = total - n_negative

        # If positive exceeds valid configs, move excess to negative
        if valid_configs is not None and n_positive > valid_configs:
            excess = n_positive - valid_configs
            n_positive = valid_configs
            n_negative += excess

        return n_positive, n_negative

    def generate(self,
                 total: int,
                 valid_configs: Optional[int] = None,
                 seed: Optional[int] = None,
                 max_attempts_multiplier: int = 100) -> ExampleSet:
        """
        Generate controlled examples.

        Args:
            total: Total number of examples to generate
            valid_configs: Number of valid configurations (optional)
            seed: Random seed for reproducibility
            max_attempts_multiplier: Max attempts = n * multiplier

        Returns:
            ExampleSet with controlled E⁺/E⁻ distribution
        """
        self._rng = random.Random(seed)

        n_positive, n_negative = self.calculate_distribution(total, valid_configs)

        example_set = ExampleSet(metadata={
            'method': 'ControlledRS',
            'total': total,
            'target_positive': n_positive,
            'target_negative': n_negative,
            'valid_configs': valid_configs,
            'seed': seed
        })

        features_list = sorted(self.features)

        # Track all generated examples to avoid duplicates
        generated_configs = set()

        # Generate positive examples using SAT solver
        attempts = 0
        max_attempts = n_positive * max_attempts_multiplier

        while len(example_set.positive) < n_positive and attempts < max_attempts:
            config = self._generate_valid_config(features_list)
            if config:
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_configs:
                    generated_configs.add(config_tuple)
                    example = Example(
                        id=f"e{len(example_set.positive) + 1}+",
                        assignments=config,
                        example_type=ExampleType.POSITIVE
                    )
                    example_set.positive.append(example)
            attempts += 1

        # Generate negative examples by random + rejection
        neg_attempts = 0
        max_neg_attempts = n_negative * max_attempts_multiplier

        while len(example_set.negative) < n_negative and neg_attempts < max_neg_attempts:
            # Random configuration
            config = {f: self._rng.choice([True, False]) for f in features_list}

            # Check if invalid (negative)
            if not self.oracle.is_valid(config):
                config_tuple = tuple(sorted(config.items()))
                if config_tuple not in generated_configs:
                    generated_configs.add(config_tuple)
                    example = Example(
                        id=f"e{len(example_set.negative) + 1}-",
                        assignments=config,
                        example_type=ExampleType.NEGATIVE
                    )
                    example_set.negative.append(example)

            neg_attempts += 1

        # Update metadata with actual counts
        example_set.metadata['actual_positive'] = len(example_set.positive)
        example_set.metadata['actual_negative'] = len(example_set.negative)
        example_set.metadata['total_generated'] = len(example_set)

        return example_set

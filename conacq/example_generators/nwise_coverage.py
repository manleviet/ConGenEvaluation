"""
N-wise Coverage generator for test case generation.

Uses allpairspy library for efficient pairwise (2-wise) test generation.
"""

from typing import Optional, List
from allpairspy import AllPairs

from conacq.examples.data_structures import Example, ExampleSet
from conacq.oracle import GeneratorOracle
from .base import ExampleGenerator


class NWiseCoverageGenerator(ExampleGenerator):
    """
    N-wise Coverage generator using allpairspy.

    Generates configurations that cover all n-tuples of feature values.
    For 2-COV (pairwise): each combination of 2 features appears at least once.

    Example:
        >>> oracle = FMOracle('model.uvl')
        >>> gen = NWiseCoverageGenerator(oracle, n=2)
        >>> examples = gen.generate(seed=42)
    """

    def __init__(self, oracle: GeneratorOracle, n: int = 2):
        """
        Initialize n-wise coverage generator.

        Args:
            oracle: GeneratorOracle for classifying/completing examples
            n: Coverage strength (2 for pairwise, 3 for 3-wise, etc.)
        """
        super().__init__(oracle)
        self.n = n

    def generate(self, seed: Optional[int] = None) -> ExampleSet:
        """
        Generate examples with n-wise coverage.

        Args:
            seed: Random seed (note: allpairspy doesn't support seed directly)

        Returns:
            ExampleSet with n-wise coverage
        """
        example_set = ExampleSet(metadata={
            'method': f'{self.n}-COV',
            'n_wise': self.n,
            'seed': seed
        })

        features_list = sorted(self.features)

        # Create parameters for allpairspy
        # Each feature has domain [True, False]
        parameters = [[True, False] for _ in features_list]

        # Generate pairwise combinations using allpairspy
        try:
            pairwise_combinations = list(AllPairs(parameters, n=self.n))
        except Exception:
            # Fallback for older versions of allpairspy that don't support n parameter
            pairwise_combinations = list(AllPairs(parameters))

        # Convert to examples and classify
        for i, combination in enumerate(pairwise_combinations):
            # Create assignment dictionary
            assignments = {
                features_list[j]: bool(combination[j])
                for j in range(len(features_list))
            }

            example = Example(
                id=f"{self.n}cov_{i + 1}",
                assignments=assignments
            )

            self._classify_and_add(example, example_set)

        example_set.metadata['total_combinations'] = len(pairwise_combinations)

        return example_set


class TwoCoverageGenerator(NWiseCoverageGenerator):
    """
    2-wise (pairwise) coverage generator.

    Convenience class for 2-COV which is the most common coverage criterion.

    Each pair of features (f1, f2) appears in at least one example
    for all value combinations: (T,T), (T,F), (F,T), (F,F).
    """

    def __init__(self, oracle: GeneratorOracle):
        super().__init__(oracle, n=2)

    def generate(self, seed: Optional[int] = None) -> ExampleSet:
        examples = super().generate(seed)
        examples.metadata['method'] = '2-COV'
        return examples

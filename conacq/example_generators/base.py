"""
Base class for example example_generators.
"""

import random
from abc import ABC, abstractmethod
from typing import Optional, Dict

from conacq.examples.data_structures import Example, ExampleSet, ExampleType
from conacq.oracle import GeneratorOracle


class ExampleGenerator(ABC):
    """
    Abstract base class for example example_generators.

    Generators use an oracle to classify generated configurations
    as positive or negative examples.

    Attributes:
        oracle: GeneratorOracle for classifying and completing examples
        features: Set of all feature names
    """

    def __init__(self, oracle: GeneratorOracle):
        """
        Initialize generator with an oracle.

        Args:
            oracle: GeneratorOracle for classifying examples
        """
        self.oracle = oracle
        self.features = oracle.get_variables()
        # Per-instance RNG so generation never touches the process-global
        # ``random`` stream. Each ``generate`` call reseeds it via
        # ``self._rng = random.Random(seed)``; this default keeps the attribute
        # present for any helper reached before ``generate`` sets a seed.
        self._rng = random.Random()

    @abstractmethod
    def generate(self, **kwargs) -> ExampleSet:
        """
        Generate examples.

        Returns:
            ExampleSet with classified positive and negative examples
        """
        pass

    def _classify_and_add(self, example: Example, example_set: ExampleSet):
        """
        Classify example using oracle and add to example set.

        Args:
            example: Example to classify
            example_set: ExampleSet to add to
        """
        is_valid = self.oracle.is_valid(example.assignments)
        example.example_type = ExampleType.POSITIVE if is_valid else ExampleType.NEGATIVE
        example_set.add(example)

    def _generate_valid_config(self, features_list: list) -> Optional[Dict[str, bool]]:
        """
        Generate a valid configuration with randomness.

        Uses partial random assumptions to get diverse valid configs.

        Args:
            features_list: List of feature names

        Returns:
            Valid configuration dict, or None if failed
        """
        shuffled = list(features_list)
        self._rng.shuffle(shuffled)

        n_fixed = self._rng.randint(0, len(shuffled) // 2)
        partial = {f: self._rng.choice([True, False]) for f in shuffled[:n_fixed]}

        return self.oracle.complete_configuration(partial)

"""
Human-in-the-loop oracle via terminal prompts.

Prompts user for membership query answers in interactive mode.
Implements is_valid() only — a MembershipOracle, no base class.
"""

from typing import Dict

from conacq.oracle.protocols import MembershipOracle


class UserPromptOracle(MembershipOracle):
    """Interactive oracle that prompts user for answers.

    Declares the MembershipOracle role (ADR-0010). Used for truly interactive
    constraint acquisition where a human expert answers membership queries.

    Example:
        >>> oracle = UserPromptOracle(features=['A', 'B', 'C'])
        >>> answer = oracle.is_valid({'A': True, 'B': False, 'C': True})
        Query: A=True, B=False, C=True
        Is this configuration valid? (y/n):
    """

    def __init__(self, features: list, verbose: bool = True):
        """Initialize user prompt oracle.

        Args:
            features: List of feature names (for display)
            verbose: If True, show detailed query information
        """
        self.features = set(features)
        self.verbose = verbose
        self._query_count = 0

    def is_valid(self, assignments: Dict[str, bool]) -> bool:
        """Prompt user for membership query answer.

        Args:
            assignments: Configuration as {feature_name: True/False}

        Returns:
            True if user answers 'y' or 'yes'
        """
        self._query_count += 1

        # Format query for display
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Query #{self._query_count}")
            print(f"{'='*60}")

            # Show selected features
            selected = sorted([f for f, v in assignments.items() if v])
            deselected = sorted([f for f, v in assignments.items() if not v])

            print(f"Selected features ({len(selected)}):")
            for f in selected:
                print(f"  + {f}")

            if deselected:
                print(f"\nDeselected features ({len(deselected)}):")
                for f in deselected[:10]:  # Show first 10
                    print(f"  - {f}")
                if len(deselected) > 10:
                    print(f"  ... and {len(deselected) - 10} more")
        else:
            # Compact format
            config_str = ', '.join(f"{k}={v}" for k, v in sorted(assignments.items())[:5])
            if len(assignments) > 5:
                config_str += f", ... ({len(assignments) - 5} more)"
            print(f"\nQuery #{self._query_count}: {config_str}")

        # Get user answer
        while True:
            answer = input("\nIs this configuration valid? (y/n): ").strip().lower()
            if answer in ('y', 'yes', '1', 'true'):
                return True
            elif answer in ('n', 'no', '0', 'false'):
                return False
            else:
                print("Please answer 'y' for yes or 'n' for no.")

    def get_query_count(self) -> int:
        """Get number of queries asked so far."""
        return self._query_count

    def __repr__(self):
        return f"UserPromptOracle(features={len(self.features)}, queries={self._query_count})"

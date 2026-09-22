"""Converter A — a learned rule set to CNF (C4).

The rule set is a DNF for the class ``invalid`` (see ``feature_table``), so a
configuration is valid exactly when NO rule fires:

    valid(x) ⟺ ⋀ᵢ ¬(lᵢ₁ ∧ … ∧ lᵢₖ) = ⋀ᵢ (¬lᵢ₁ ∨ … ∨ ¬lᵢₖ)

which is already CNF — one clause per rule, no Tseitin variables, no auxiliary
encoding. Both rule-list learners (RIPPER, CN2) land here directly; the decision tree
reaches it through converter B, which turns root→leaf paths into the same ``Rule``.

Literals are resolved through ``FeatureTable.literal`` — by NAME. This module never
sees a column index, which is the pairing bug the table layer documents.

Two degenerate shapes are handled explicitly rather than falling out of the loop,
because both are semantically loud and easy to produce:

- **empty rule set** ⇒ empty CNF ⇒ ⊤ ⇒ accepts everything. Frequent here: several
  (KB, sampling, fold) cells give the learner too few instances of the target class
  to induce any rule. Callers must report those cells as degenerate, never as a score.
- **a rule with no conditions** (fires unconditionally) ⇒ the empty clause ⇒ ⊥ ⇒
  rejects everything. Kept, not silently dropped: dropping it would turn "everything
  is invalid" into "nothing is constrained", the exact opposite theory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .feature_table import FeatureTable


@dataclass(frozen=True)
class Rule:
    """One conjunction of feature tests, predicting ``invalid`` when all hold."""

    conditions: Tuple[Tuple[str, bool], ...]

    @classmethod
    def of(cls, *conditions: Tuple[str, bool]) -> "Rule":
        return cls(tuple(conditions))

    def fires_on(self, assignment) -> bool:
        """Whether this rule matches an assignment — used to check a rule set's
        semantics directly, without going through the CNF."""
        return all(assignment[f] == v for f, v in self.conditions)


def rules_to_cnf(rules: Sequence[Rule], table: FeatureTable) -> List[List[int]]:
    """Negate a DNF-for-invalid into CNF-for-valid: one clause per rule.

    Literals within a clause are de-duplicated while preserving first-seen order, so a
    learner that repeats a test does not inflate the clause. A rule testing a feature
    both ways can never fire; its clause holds both polarities and is a tautology,
    which is harmless in CNF and deliberately not special-cased — removing it would
    require proving the rule unsatisfiable, and getting that wrong drops a real
    constraint.
    """
    cnf: List[List[int]] = []
    for rule in rules:
        clause: List[int] = []
        seen = set()
        for feature, value in rule.conditions:
            # ¬(feature == value) is (feature == not value).
            lit = table.literal(feature, not value)
            if lit not in seen:
                seen.add(lit)
                clause.append(lit)
        cnf.append(clause)  # [] when the rule is unconditional ⇒ ⊥, intentionally
    return cnf


def is_degenerate(rules: Sequence[Rule]) -> bool:
    """True when the rule set carries no information (no rules at all).

    Exposed so the eval layer can MARK such a cell rather than print a score for it:
    the resulting ⊤ theory accepts everything, which is an artifact of the fold split,
    not a measurement.
    """
    return len(rules) == 0

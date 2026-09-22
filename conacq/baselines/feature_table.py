"""Feature table for the rule-learner baselines (C4).

Rows are the fold's training examples, columns the FM's features, label 1 for a
negative (``invalid``) and 0 for a positive. **The positive class is `invalid`** —
that is what makes the CNF conversion trivial downstream: a rule set is then a DNF
for ``invalid``, a configuration is valid exactly when no rule fires, and

    ⋀ᵢ ¬(lᵢ₁ ∧ … ∧ lᵢₖ)  =  ⋀ᵢ (¬lᵢ₁ ∨ … ∨ ¬lᵢₖ)

is already CNF, one clause per rule. Learning ``valid`` instead would yield a DNF
needing a real encoding.

Deliberately dependency-free (plain lists, no numpy/pandas) so this layer and its
tests run on a machine without the ``baselines`` extra; the learner adapters convert
at their own boundary.

THE SILENT FAILURE THIS GUARDS. Column order and variable-id order are independent:
ids come from flamapy's tree traversal, not alphabetical order. Pairing a column
*index* with a variable *id* yields a CNF over permuted variables that is internally
consistent — nothing raises, every downstream call succeeds, accuracy lands somewhere
plausible. So literals are resolved **by name** only, and `build_feature_table`
verifies the id→name→id round trip up front rather than trusting the caller's dict.

WHY THAT GUARD IS A REGRESSION GUARD, NOT A LIVE BUG FIX — measured 2026-08-23, and
recorded because the two statements above and below otherwise read as contradictory.
The default column order below sorts by variable id, and on every KB in this repo the
ids are CONTIGUOUS FROM 1 (REAL-FM-7 1–14, arcade-game 1–65, fqa 1–179, REAL-FM-4
1–291). So in production, column index *i* and variable id *i+1* coincide exactly, and
an index-paired implementation would be right BY ACCIDENT everywhere.

**Name-resolution does not fix a wrong answer — it removes the coincidence the
correctness rests on.** A non-contiguous catalog (an FM whose features do not own the
whole low id range, e.g. once ids are reserved elsewhere) breaks index-pairing
immediately and silently. The tests therefore use a NON-contiguous catalog and a
permuted column order by default, so agreeing with the bug is the exception there
rather than the rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence, Tuple

# Label convention. Kept as named constants because "1" and "0" read identically at
# the call site and swapping them silently inverts every learned rule.
INVALID = 1  # e⁻ — the class the learner is asked to characterise
VALID = 0    # e⁺


@dataclass(frozen=True)
class FeatureTable:
    """A learner-ready table plus the mapping back to CNF variables."""

    feature_names: Tuple[str, ...]
    rows: Tuple[Tuple[bool, ...], ...]
    labels: Tuple[int, ...]
    name_to_id: Mapping[str, int]

    def literal(self, feature: str, value: bool) -> int:
        """CNF literal asserting ``feature == value``: +id when true, -id when false.

        Resolved by NAME. There is deliberately no index-based variant — that is the
        pairing bug this module exists to prevent.
        """
        try:
            var = self.name_to_id[feature]
        except KeyError:
            raise KeyError(
                f"feature {feature!r} has no variable id; known features: "
                f"{sorted(self.name_to_id)[:8]}…") from None
        return var if value else -var

    @property
    def n_invalid(self) -> int:
        return sum(1 for lab in self.labels if lab == INVALID)

    @property
    def n_valid(self) -> int:
        return sum(1 for lab in self.labels if lab == VALID)

    def column(self, feature: str) -> Tuple[bool, ...]:
        idx = self.feature_names.index(feature)
        return tuple(row[idx] for row in self.rows)


def build_feature_table(
        positive: Sequence[Mapping[str, bool]],
        negative: Sequence[Mapping[str, bool]],
        name_to_id: Mapping[str, int],
        feature_order: Sequence[str] | None = None,
) -> FeatureTable:
    """Build the table from raw example assignments.

    ``feature_order`` overrides the column order; it exists so a test can permute the
    columns and assert the resulting CNF is unchanged (the canary for index-pairing).
    Production callers omit it and get a deterministic order sorted by variable id,
    which is flamapy's traversal order — NOT alphabetical.

    Raises when an example omits a feature: every example in this repo carries a
    complete assignment, so a missing key means the caller mixed sources, and filling
    a default would fabricate a training row.
    """
    if not name_to_id:
        raise ValueError("name_to_id is empty — no variables to build a table over")

    # Round trip id→name→id. A duplicated id (two features mapped to one variable)
    # silently merges columns downstream; catch it here rather than in a CNF.
    id_to_name: Dict[int, str] = {}
    for name, var in name_to_id.items():
        if var in id_to_name:
            raise ValueError(
                f"variable id {var} maps to both {id_to_name[var]!r} and {name!r}; "
                f"the name↔id catalog is not bijective")
        id_to_name[var] = name
    for name, var in name_to_id.items():
        if id_to_name[var] != name:
            raise ValueError(f"id round trip failed for {name!r}")

    if feature_order is None:
        names = tuple(sorted(name_to_id, key=lambda n: name_to_id[n]))
    else:
        names = tuple(feature_order)
        if set(names) != set(name_to_id):
            missing = sorted(set(name_to_id) - set(names))
            extra = sorted(set(names) - set(name_to_id))
            raise ValueError(
                f"feature_order does not cover the catalog exactly "
                f"(missing={missing[:5]}, unexpected={extra[:5]})")

    rows: list[Tuple[bool, ...]] = []
    labels: list[int] = []
    for examples, label in ((positive, VALID), (negative, INVALID)):
        for ex in examples:
            missing = [n for n in names if n not in ex]
            if missing:
                raise ValueError(
                    f"example is missing {len(missing)} feature assignment(s) "
                    f"(e.g. {missing[:5]}); examples must be complete assignments")
            rows.append(tuple(bool(ex[n]) for n in names))
            labels.append(label)

    return FeatureTable(
        feature_names=names,
        rows=tuple(rows),
        labels=tuple(labels),
        name_to_id=dict(name_to_id),
    )

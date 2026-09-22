"""Scoring the rule-learner baselines against the same folds as acquisition (C4).

Reports **predictive accuracy** and **semantic F1** only.

No description tier, deliberately. That tier scores the NAMES of bias constraints, and
a rule set carries none — its description F1 is ~0 by construction, so printing it
would be a straw man. The semantic tier IS well defined here: it is clause ENTAILMENT
against the ground-truth theory, so the learned CNF goes to the same
``SemanticEquivalenceChecker`` ConGen's semantic tier uses, resolved from rules instead
of from bias names.

REPORT RECALL AND PRECISION SEPARATELY. LEAD WITH RECALL. This is not stylistic — the
two sides' precision denominators count different objects, and F1 inherits that:

- **Recall is comparable.** Its denominator is ``n_ct_checked``, the clauses of C_τ,
  identical for both sides. It is also the number that carries the argument: ConGen ≈0.9
  against a baseline ≈0.04.
- **Precision is NOT comparable.** ConGen expands each learned constraint into clauses
  and counts clauses (``kb_comparator.py:291-295``); a rule set contributes one clause
  per rule. Measured expansion (clauses per constraint): REAL-FM-7 1.06, arcade-game
  1.12, busybox 1.14, REAL-FM-4 1.31, **fqa 2.03** — and fqa supplies 3 of the 4
  configurations C4 can score, so the distortion sits exactly where the comparison
  lives. Distortion appears when a constraint's clauses are only partly entailed.

So: **build no claim on a precision difference between the two sides**, and state in any
table carrying both that the denominators count different objects. The two WILL appear
together — that is the point of C4 — so the sentence is required, not conditional.

DEGENERATE CELLS ARE MARKED, NEVER SCORED. An empty rule set is the empty CNF, i.e. ⊤,
which accepts every configuration; printing the resulting accuracy would report an
artifact of the fold split as a measurement. Two distinct causes are distinguished
because they mean different things in the write-up:

- ``too_few_instances`` — the fold is below the declared reporting threshold. This
  criterion was fixed BEFORE any number existed (see the C4 plan), which is what
  forecloses "why only these cells?" after the fact.
- ``no_rules_learned`` — the fold met the threshold and the learner still induced
  nothing.

Both yield ``None`` scores, never 0.0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence

from .feature_table import build_feature_table
from .rule_cnf import rules_to_cnf

# Declared in advance (C4 plan, 2026-08-23): a cell is reported only when BOTH classes
# carry at least this many training instances.
MIN_CLASS_INSTANCES = 10


@dataclass
class BaselineCell:
    """One (learner, KB, sampling, fold) result — or the reason there is none."""

    learner: str
    n_train_valid: int
    n_train_invalid: int
    n_rules: int
    degenerate: Optional[str] = None      # None ⇒ scored
    accuracy: Optional[float] = None
    true_positives: Optional[int] = None
    true_negatives: Optional[int] = None
    false_positives: Optional[int] = None
    false_negatives: Optional[int] = None
    sem_precision: Optional[float] = None
    sem_recall: Optional[float] = None
    sem_f1: Optional[float] = None
    extra: Dict[str, object] = field(default_factory=dict)

    def to_row(self) -> dict:
        d = dict(self.__dict__)
        d.pop("extra")
        d.update(self.extra)
        return d


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def evaluate_fold(
        learner_name: str,
        learn,
        train_pos: Sequence[Mapping[str, bool]],
        train_neg: Sequence[Mapping[str, bool]],
        test_pos: Sequence[Mapping[str, bool]],
        test_neg: Sequence[Mapping[str, bool]],
        name_to_id: Mapping[str, int],
        ct_clauses: Sequence[Sequence[int]],
        bg_clauses: Sequence[Sequence[int]] = (),
        solver_name: str = "glucose4",
) -> BaselineCell:
    """Train one learner on a fold and score it, or mark the cell degenerate."""
    from conacq.eval.accuracy import AccuracyCalculator
    from conacq.eval.semantic_equivalence import SemanticEquivalenceChecker

    table = build_feature_table(train_pos, train_neg, name_to_id)
    cell = BaselineCell(
        learner=learner_name,
        n_train_valid=table.n_valid,
        n_train_invalid=table.n_invalid,
        n_rules=0,
    )

    if min(table.n_valid, table.n_invalid) < MIN_CLASS_INSTANCES:
        cell.degenerate = "too_few_instances"
        return cell

    rules = learn(table)
    cell.n_rules = len(rules)
    if not rules:
        # ⊤ — accepts everything. An artifact of the split, not a measurement.
        cell.degenerate = "no_rules_learned"
        return cell

    cnf = [list(c) for c in rules_to_cnf(rules, table)]
    theory = cnf + [list(c) for c in bg_clauses]

    with AccuracyCalculator(theory, dict(name_to_id), solver_name) as acc:
        m = acc.calculate(list(test_pos), list(test_neg)).metrics
    cell.accuracy = m.accuracy
    cell.true_positives, cell.true_negatives = m.true_positives, m.true_negatives
    cell.false_positives, cell.false_negatives = m.false_positives, m.false_negatives

    # Semantic tier: clause entailment against C_τ, exactly as the acquisition side
    # measures it — the learned CNF stands in for the bias-resolved clauses.
    sem = SemanticEquivalenceChecker(
        kb_clauses=cnf,
        ct_clauses=[list(c) for c in ct_clauses],
        bg_clauses=[list(c) for c in bg_clauses],
        solver_name=solver_name,
    ).check_equivalence()

    n_ct_entailed = sem.n_ct_checked - len(sem.unentailed_ct)
    n_kb_entailed = sem.n_kb_checked - len(sem.unentailed_kb)
    cell.sem_recall = n_ct_entailed / sem.n_ct_checked if sem.n_ct_checked else 0.0
    cell.sem_precision = n_kb_entailed / sem.n_kb_checked if sem.n_kb_checked else 0.0
    cell.sem_f1 = _f1(cell.sem_precision, cell.sem_recall)
    return cell


def summarise(cells: Sequence[BaselineCell]) -> dict:
    """Counts by outcome. Reported alongside any table so the marked cells are visible
    rather than inferred from blanks."""
    scored = [c for c in cells if c.degenerate is None]
    out = {
        "cells": len(cells),
        "scored": len(scored),
        "too_few_instances": sum(1 for c in cells if c.degenerate == "too_few_instances"),
        "no_rules_learned": sum(1 for c in cells if c.degenerate == "no_rules_learned"),
    }
    if scored:
        out["mean_accuracy"] = sum(c.accuracy for c in scored) / len(scored)
        # Recall first, and precision reported beside it rather than folded away: only
        # recall shares a denominator with the acquisition side. F1 is emitted last
        # because it inherits precision's incomparability — do not lead a table with it.
        out["mean_sem_recall"] = sum(c.sem_recall for c in scored) / len(scored)
        out["mean_sem_precision"] = sum(c.sem_precision for c in scored) / len(scored)
        out["mean_sem_f1"] = sum(c.sem_f1 for c in scored) / len(scored)
    return out

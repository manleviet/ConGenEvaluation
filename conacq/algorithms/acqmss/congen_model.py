"""
Model for ConGen algorithm.

An immutable KB: bias constraint_map + name↔id catalog (inherited from KBModel).
``prepare_task`` derives a fresh PreparedTask per call (pure); the model stores no
task state, no description provider, no root constraint, and no solver-mode field
(that is a caller/checker concern). ``resolve_result`` is STATELESS — the describe
provider (from the PreparedTask) and the root clauses (from the OracleData snapshot)
are passed in per call, never read off stored task state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from conacq.kb_model import KBModel
from explanation.api import DescriptionProvider, PreparedTask

from .task_preparation import ConGenTaskInput, ConGenTaskPreparation

if TYPE_CHECKING:
    from .congen import ConGenResult


class ConGenModel(KBModel):
    """Immutable ConGen KB (bias constraints + name↔id catalog).

    Pure data container. prepare_task builds a fresh ConGenTask (via
    ConGenTaskPreparation); the model holds no task, no description provider, no
    root constraint, no solver mode.

    Usage:
        oracle = FMOracle('data/fms/model.uvl')
        model = (ConGenModelBuilder
                 .from_bias('data/bias/model.json')
                 .with_oracle_data(oracle.oracle_data)
                 .build())
        task_input = ConGenTaskInput.from_examples(oracle.oracle_data, pos, neg)
        prepared = model.prepare_task(task_input)
        task = prepared.task  # ConGenTask with assumption IDs
    """

    def prepare_task(self, task_input: ConGenTaskInput, profiler=None) -> PreparedTask:
        """Assign assumption IDs and build a fresh ConGenTask (pure).

        Consumes a ConGenTaskInput carrying the oracle's frozen provisioning
        snapshot plus this fold's E+/E-; returns a new PreparedTask (task +
        describe). Can be called repeatedly (e.g. per CV fold) — no state is kept.
        The signature is unified with the other models; the input TYPE is ConGen's
        own (not a shared union — ADR-0006). ``profiler`` (optional) counts
        GenerateNE's preprocessing QuickXplain separately (GAP B).
        """
        return ConGenTaskPreparation(profiler=profiler).prepare(self, task_input)

    def resolve_result(
            self,
            result: "ConGenResult",
            describe: DescriptionProvider,
            root_clauses: Sequence[Sequence[int]],
            set_kb: Sequence[Sequence[int]] = (),
            negation_map: Optional[Dict[int, int]] = None,
    ) -> Tuple[List[List[int]], List[List[int]], List[str],
               List[List[int]], List[str], List[str], List[str]]:
        """Resolve a ConGenResult into clauses and names (stateless).

        The describe provider (from the PreparedTask) and the root BG clauses (from
        the OracleData snapshot) are passed in — the model keeps no baton between
        prepare and resolve, so a wrong call order cannot silently drop the BG (a
        stored root-clause baton with an ``or []`` fallback masked exactly that).

        Returns:
            (bg_clauses, kb_clauses, kb_names, ne_clauses, ne_names,
             redundant_names, redundant_ne_names)

        ``kb_names`` is bias constraints ONLY and ``ne_names`` the memorized ¬e⁻
        facts, reported apart. They used to share one list, which put NE names into
        the KB name-space: it inflated ``n_kb`` and fed NE into the
        description/clause/semantic tiers,
        whose vocabulary is the bias. The ids resolved here are POST-Reduce, so an NE
        that Reduce dropped as entailed is not counted — it surfaces in
        ``redundant_ne_names`` instead. Both redundant lists are split the same way as
        the KB ones: an NE Reduce discards used to fall out of every returned list at
        once, so |KB| accounting could not be closed against the NE prepared for
        acquisition.

        ``ne_clauses`` are those NE names resolved back to their blocking clauses.
        Algorithm 3 delivers KB ← B′ ∪ NE, and Definition 6 asks for a theory that
        rejects every e⁻ ∈ E⁻; a delivered theory without them can accept a training
        negative, which the problem definition forbids. They were previously dropped
        because an NE name has no entry in ``constraint_map``, so it resolved to no
        clause at all. ``set_kb`` + ``negation_map`` come from the prepared task
        (stateless — passed in, never stored); the defaults are safe only for callers
        with no NE, where no resolution is attempted.
        """
        negation_map = negation_map or {}
        bg_clauses = root_clauses
        kb_clauses, kb_names, ne_names = self._resolve_ids(
            describe, result.kb_assumption_ids)

        # Resolve each NE id back to its blocking clause. Fail loud rather than deliver
        # a theory that silently omits a memorized ¬e⁻, using the shared resolver
        # on KBModel.
        ne_clauses: List[List[int]] = []
        for aid in result.kb_assumption_ids:
            if describe.get_description(aid) in self.constraint_map:
                continue
            clause = self._resolve_fallback_clause(aid, set_kb, negation_map)
            if not clause:  # None (no match) or [] (degenerate empty ⇒ UNSAT)
                raise ValueError(
                    f"ConGen kb id {aid} is a memorized ¬e⁻ (name not a bias "
                    f"constraint) but its clause could not be resolved: set_kb has "
                    f"{len(set_kb)} clauses, negation_map "
                    f"{'has' if aid in negation_map else 'MISSING'} id {aid}. Pass the "
                    f"prepared task's set_kb + negation_map; Algorithm 3 delivers "
                    f"B' u NE, so an NE must not be dropped from the theory.")
            ne_clauses.append(clause)

        _, redundant_names, redundant_ne_names = self._resolve_ids(
            describe, result.redundant_ids)
        return (bg_clauses, kb_clauses, kb_names, ne_clauses, ne_names,
                redundant_names, redundant_ne_names)

    def _resolve_ids(
            self,
            describe: DescriptionProvider,
            assumption_ids: List[int],
    ) -> Tuple[List[List[int]], List[str], List[str]]:
        """Resolve assumption IDs to clauses (from this KB's constraint_map) and names
        (from the given describe provider), split by whether the name is a bias
        constraint. Stateless.

        Returns (clauses, fm_names, non_fm_names). A name absent from constraint_map is
        a memorized ¬e⁻ (NE), not a bias constraint — it belongs in the second list.
        """
        clauses: List[List[int]] = []
        fm_names: List[str] = []
        non_fm_names: List[str] = []
        for aid in assumption_ids:
            name = describe.get_description(aid)
            if name in self.constraint_map:
                fm_names.append(name)
                clauses.extend(self.constraint_map[name])
            else:
                non_fm_names.append(name)
        return clauses, fm_names, non_fm_names

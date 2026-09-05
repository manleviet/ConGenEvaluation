"""KBModel: generic base holding the shared KB fields + the name↔id catalog.

Domain-neutral: the base owns the fields every conacq KB shares (constraint maps,
next assumption id, and the two name↔id direction dicts). Subclasses call
``super().__init__()`` then set only model-specific values; builders populate the
fields at build time. No feature-model terms in the base.

The name↔id catalog is exposed as plain ``dict`` attributes — no runtime
read-only view (see ADR-0007). ``KBProtocol`` types it as ``Mapping``, so the
read-only guarantee stays at the type level, where it costs nothing.
"""
from typing import Dict, List, Optional, Sequence


class KBModel:
    """Base holding shared KB fields and the name↔id catalog."""

    def __init__(self) -> None:
        # Constraint name -> raw CNF clauses
        self.constraint_map: Dict[str, List[List[int]]] = {}
        # Constraint NOT(name) -> negated CNF clauses (for redundancy detection)
        self.negated_constraint_map: Dict[str, List[List[int]]] = {}
        # Starting id for assumption literals; 0 until the builder computes the
        # real value from the FM/oracle at build time.
        self.next_available_id: int = 0
        # name↔id catalog (plain dicts; populated at build).
        self.name_to_id: Dict[str, int] = {}
        self.id_to_name: Dict[int, str] = {}

    @staticmethod
    def _resolve_fallback_clause(
            ne_id: int,
            set_kb: Sequence[Sequence[int]],
            negation_map: Dict[int, int],
    ) -> Optional[List[int]]:
        """The fallback clause for a NE id, from the task KB. Its blocking clause is
        ``[-l1,…,-lk, -ne_id]`` (the l_i are the minimal-conflict feature literals);
        distinguish it from the NE's negation clause ``[-ne_id, -negation_map[ne_id]]``
        by the ABSENCE of ``-negation_map[ne_id]`` (the combine clause ``[+ne_id, …]``
        never matches ``-ne_id``), then strip the ``-ne_id`` guard — returns the
        negation of the minimal conflict.

        Returns None (⇒ the caller fails loud) when no clause matches OR when ``ne_id``
        has no ``negation_map`` entry: without it the ne-clause cannot be safely told
        apart from the negation clause, so guessing the first ``-ne_id`` clause (which
        could return a wrong remainder — the P3-Critical bug class) is REFUSED, not
        silently attempted.

        NOTE on the FM/fallback split at the call site: per-e⁻ ids are registered in
        ``describe`` with their own ``NOT(…)`` conflict text, which is never a bias name
        (those are ``c``-prefixed), so they classify as fallbacks correctly. They used
        to be left unregistered — only the combined id was — and resolving that combined
        id returned a clause over an AUXILIARY variable carrying none of the exclusions,
        so a delivered theory could accept a training negative it had memorized
        (measured: REAL-FM-7 2cov accepted 2 of 9). Registering each e⁻ separately is
        what makes the resolved clause a real one over feature variables."""
        neg = negation_map.get(ne_id)
        if neg is None:
            return None  # cannot safely disambiguate ne-clause vs negation clause
        for clause in set_kb:
            if -ne_id in clause and -neg not in clause:
                return [lit for lit in clause if lit != -ne_id]
        return None

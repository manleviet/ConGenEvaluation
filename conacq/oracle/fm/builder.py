"""Builder for FMOracleModel — loads an FM file into the immutable FM KB.

Extracted from FMOracleModel's old ``from_fm``/``build`` self-builder so the model
is a pure KB and none of the four models builds itself (T6). Inherits the framework
template ``AbstractModelBuilder`` (validate, then construct) through the single
public door, ``explanation.api``.
"""

from __future__ import annotations

from typing import Optional

from explanation.api import AbstractModelBuilder

from conacq.oracle.fm.model import FMOracleModel


class FMOracleModelBuilder(AbstractModelBuilder[FMOracleModel]):
    """Fluent builder: load an FM (.uvl) file into an FMOracleModel KB.

    ``build()`` (inherited template) runs ``_validate`` then ``_create_model``.
    """

    def __init__(self) -> None:
        self._fm_path: Optional[str] = None

    @classmethod
    def from_fm(cls, fm_path: str) -> 'FMOracleModelBuilder':
        """Create a builder bound to an FM (.uvl) file."""
        builder = cls()
        builder._fm_path = fm_path
        return builder

    def _validate(self) -> None:
        """Require an FM path."""
        if not self._fm_path:
            raise ValueError("FM path required (use from_fm())")

    def _create_model(self) -> FMOracleModel:
        """Load the FM into a fresh FMOracleModel (constraint maps + catalog + next id)."""
        from flamapy.metamodels.fm_metamodel.transformations import UVLReader
        from explanation.api import FmToDiagPysat

        fm = UVLReader(self._fm_path).transform()
        # FmToDiagPysat creates both constraint_map and negated_constraint_map for
        # redundancy detection.
        fm_model = FmToDiagPysat(fm, create_negation=True).transform()

        model = FMOracleModel()
        model.constraint_map = fm_model.constraint_map
        model.negated_constraint_map = fm_model.negated_constraint_map
        model.name_to_id = fm_model.variables
        model.id_to_name = fm_model.features
        model.next_available_id = fm_model.next_available_id
        # Store the FM's declared root name explicitly at build — an independent
        # witness (from the FM tree, not constraint_map's ordering) that lets the
        # "root = first constraint_map key" invariant be machine-checked without a
        # get_root_feature() getter (T11.4c). Preparation derives root_clauses as the
        # first key's clauses; if FmToDiagPysat ever reorders, this witness diverges
        # and the guard goes red instead of ConGen learning on a wrong background.
        model.root_feature = fm.root.name
        return model

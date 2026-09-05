"""Narrow, role-based oracle protocols — the contracts consumers depend on.

The concrete ``FMOracle`` exposes 14 public methods, but no consumer
needs all of them. These ``@runtime_checkable`` protocols carve that surface into
the roles consumers actually use (measured, not guessed), so a consumer depends
on a 1-3 method contract rather than the concrete class — which makes alternative
oracles (``UserPromptOracle``, ``CachedOracle``) substitutable.

Critically, the KB-reading surface (``get_kb``/``get_assumptions``/``get_c``) is
named as its own role, ``KBProvider``. That is exactly the surface through which
the last-query pollution of ``get_c`` leaks, and its sole consumer is
``GenerateNE``. Giving it a name makes that blast radius visible in the type
system instead of hiding it inside a 14-method class.

There is no ONE fat ``Oracle`` base owning four roles — that class lied (it stubbed
``get_variables``/``complete_configuration`` to None) and it is gone. But "no fat
base" is not "no base": every atomic member here is ``@abstractmethod``, and the
oracles we own DECLARE the roles they play by inheriting the narrow protocols
(``FMOracle(MembershipOracle, CompletableOracle, CatalogProvider)`` etc). N narrow
bases, each carrying exactly its own contract and none of them lying, IS the role
design — the class line states ADR-0009's split in code the machine checks, instead
of a docstring the reader must match by hand (ADR-0010).

Substitutability is untouched and remains the point: ``@runtime_checkable`` means
anything with the methods satisfies the protocol via ``isinstance`` without
inheriting, so consumers still bind to the 1-3 method role they use, and test
doubles / third-party oracles need not declare. A couple of consumers span several
roles — they type against the composite protocols (``GeneratorOracle``,
``PreparationOracle``), which are unions of the atomic roles, not new roles.
If you are here to "simplify" those base lists away, read ADR-0010 first.
"""
from __future__ import annotations

from abc import abstractmethod
from typing import (
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    TYPE_CHECKING,
    runtime_checkable,
)

if TYPE_CHECKING:
    from conacq.oracle.bg_data import BGData


@runtime_checkable
class MembershipOracle(Protocol):
    """Answer membership queries: is this configuration valid?"""

    @abstractmethod
    def is_valid(self, assignments: Dict[str, bool]) -> bool: ...


@runtime_checkable
class CompletableOracle(Protocol):
    """Complete a partial configuration to a full valid one."""

    @abstractmethod
    def complete_configuration(
        self, partial: Dict[str, bool]
    ) -> Optional[Dict[str, bool]]: ...


@runtime_checkable
class CatalogProvider(Protocol):
    """Expose the variable-name <-> SAT-variable-id catalog."""

    @abstractmethod
    def get_variables(self) -> Set[str]: ...

    @abstractmethod
    def get_variable_ids(self) -> Dict[str, int]: ...


@runtime_checkable
class BGProvider(Protocol):
    """Provide the root background-knowledge surface for task preparation."""

    @abstractmethod
    def get_bg_data(self) -> "BGData": ...

    @abstractmethod
    def get_root_clauses(self) -> List[List[int]]: ...


@runtime_checkable
class KBProvider(Protocol):
    """Read the knowledge base + assumption surface.

    This is the surface the last-query pollution leaks through (``get_c``), and
    its only consumer is ``GenerateNE``. Kept as its own role so that blast
    radius is visible in the type system, not buried in a 14-method class.
    """

    @abstractmethod
    def get_kb(self) -> List[List[int]]: ...

    @abstractmethod
    def get_assumptions(self) -> List[int]: ...

    @abstractmethod
    def get_c(self) -> List[int]: ...


@runtime_checkable
class GeneratorOracle(MembershipOracle, CompletableOracle, CatalogProvider, Protocol):
    """Composite: what example generators need — classify + complete + catalog."""


@runtime_checkable
class PreparationOracle(BGProvider, KBProvider, Protocol):
    """Composite: what the ConGen preparation chain needs — background + KB."""

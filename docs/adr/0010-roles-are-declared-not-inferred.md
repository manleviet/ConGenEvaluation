# ADR-0010: Roles are declared, not inferred

**Status:** Accepted
**Date:** 2026-07-15
**Deciders:** Viet-Man Le
**Amends:** ADR-0009 (which split the oracle's roles; this decides how a class *states* which roles it plays)

## Context

ADR-0009 split `FMOracle`'s two jobs and named the roles as narrow `@runtime_checkable` protocols. T11.1 wrote those protocols. T11.4c then deleted the `Oracle` ABC they replaced — a base class that promised a "minimal membership interface" while carrying an `ask` alias and two methods stubbed to `None`:

```python
class Oracle(ABC):
    @abstractmethod
    def is_valid(self, assignments) -> bool: ...   # real
    def ask(self, query): return self.is_valid(query)
    def get_variables(self): pass                  # returns None
    def complete_configuration(self, partial): pass  # returns None
```

Deleting it was right. But **that class was carrying two things, and only one of them was bad.**

| In the ABC | Where it actually came from | Verdict |
|---|---|---|
| Two `None` stubs | **One class holding four roles** | The lie. Kill it. |
| Enforcement — a subclass missing `is_valid` raises `TypeError` **at instantiation** | **`@abstractmethod`** | Valuable. We lost it by accident. |

They looked like one thing because `main` bundled them in one `class`. They are independent.

After the deletion, `FMOracle` / `CachedOracle` / `UserPromptOracle` had no base at all and satisfied `MembershipOracle` purely structurally. A protocol *describes*; it does not *require*. A new oracle that forgets `is_valid` — or misspells it `isValid` — now constructs fine and fails later, at query time, deep in QuAcq's inner loop. **That is the A6 shape: fails silently, no exception, no failing test.**

## Decision

**Every atomic protocol member is `@abstractmethod`. Every concrete oracle we own declares its roles by inheriting them.**

```python
@runtime_checkable
class MembershipOracle(Protocol):
    @abstractmethod
    def is_valid(self, assignments: Dict[str, bool]) -> bool: ...

class FMOracle(MembershipOracle, CompletableOracle, CatalogProvider): ...
class CachedOracle(MembershipOracle): ...
class UserPromptOracle(MembershipOracle): ...
```

**The primary reason is not enforcement.** It is that the class declaration becomes a *statement of ADR-0009's role split, written in code and checked by the machine*. `class FMOracle(MembershipOracle, CompletableOracle, CatalogProvider)` tells a reader — and an IDE, and a type checker — the three roles it plays. `class FMOracle:` tells them nothing; they must open `protocols.py` and match method names in their head.

This project has been bitten three times in one arc by the same thing: knowledge living where no machine checks it. `with_oracle` naming a value that was not an oracle. `oracle: OracleData` doing it again one layer down. The pair-stride invariant restated in five prose comments because the constant was unreachable. **The roles of `FMOracle` were the next one in that queue** — they lived in a docstring.

Enforcement is a bonus that comes free with the same edit.

**Structural satisfaction is untouched and remains the point.** Inheritance is opt-in; anything that merely has the methods still satisfies the protocol:

| | Missing `is_valid` | Typo `isValid` | `isinstance(…, MembershipOracle)` |
|---|---|---|---|
| Declares the role (inherits) | `TypeError` at instantiation | `TypeError` | `True` |
| Structural (no inheritance) | constructs; fails at call | constructs; fails at call | `False` |

Test doubles (`_OnlyMembership`, `_OnlyKB` in `tests/test_oracle_protocols.py`) and third-party oracles do **not** inherit and are unaffected. That is what protocols are for.

## Options considered

### Option A: leave it structural; add a test asserting `isinstance(cls, MembershipOracle)` for the three classes

| Dimension | Assessment |
|---|---|
| Effort | 3 lines |
| Restores enforcement | Partly — at test time, not at instantiation |
| States the roles in the code | **No.** The class still says nothing about what it is |
| **Fails because** | The test only covers classes someone remembered to list. A fourth oracle added and not listed is uncovered — and whoever forgets to list it is the same person who would forget to inherit. **Symmetric.** The test buys little that the declaration doesn't buy better |

### Option B: keep a minimal ABC — `class MembershipOracle(ABC)` with only `is_valid`

| Dimension | Assessment |
|---|---|
| Restores enforcement | Yes |
| Kills the stubs | Yes |
| **Fails because** | An oracle plays 1–3 roles. Nominal ABCs make that multiple inheritance of ABCs *and* forfeit structural substitutability — third-party oracles would be **required** to inherit. It solves the stub problem by giving up the reason ADR-0009 chose protocols |

### Option C: `@abstractmethod` on protocol members + explicit inheritance (chosen)

| Dimension | Assessment |
|---|---|
| Kills the stubs | Yes — each protocol carries only its own method; **there is nowhere for a `get_variables` stub to live** |
| Restores enforcement | Yes, at instantiation, for anything that declares the role |
| States the roles in the code | **Yes — checked** |
| Keeps structural substitutability | **Yes** — verified: a non-inheriting class with the right methods still satisfies `isinstance` |
| Cost | **Measured at zero** — see below |

## Cost, measured (not assumed)

| Risk | Result |
|---|---|
| **Pickling** (FastDiagP is multiprocessing; `MappingProxyType` already broke this once) | Protocol-inheriting instances pickle fine |
| **Metaclass conflict** with a non-protocol base | None |
| **ADR-0009's negative guard** `not isinstance(FMOracle, KBProvider)` | Still `False` — the guard holds |
| **Composite protocols** (`GeneratorOracle` = union of atomics) | Still satisfied structurally |
| **Does an inheriting class become a `Protocol`** (and thus abstract)? | No — `_is_protocol` is `False`; it instantiates |

## Trade-off analysis

The honest case against Option C is that enforcement only reaches classes that opt in — which are exactly the classes a test would cover. **That argument is correct, and it is why enforcement is not the reason for this decision.**

> A protocol *describes* a shape. Inheriting it *declares* an intent. The first is for consumers — bind to the 1–3 methods you need. The second is for authors — say what you are, and let the machine hold you to it.

We keep both because they answer different questions. The registry of who-plays-what stops being tribal knowledge in a docstring.

## Consequences

**Easier**
- A reader of `fm_oracle.py` sees the three roles without leaving the file.
- An oracle that forgets or misspells a role method fails at construction, not in QuAcq's inner loop after the eval has been running for an hour.
- ADR-0009's split is now legible at every implementation site, not just in this folder.

**Harder**
- Our concrete oracles now name their protocols, so a role rename touches the class line. That is the cost of the declaration being real. It is also a feature: the rename cannot silently miss an implementer.

**Non-obvious, on purpose**
- **The docstring in `protocols.py` said "There is no `Oracle` base class."** Its true claim was about *substitutability*, and that still holds. What had to die was **one fat base holding four roles** — not *bases*. N narrow bases, each carrying exactly its own contract and none of them lying, **is** the role design. The docstring is amended accordingly; if you are here to "simplify" those base lists away, read this ADR first.
- **A known hole, unchanged from before:** `runtime_checkable` and `@abstractmethod` both check method *names*, never *signatures*. `def is_valid(self)` (missing the argument) satisfies both and fails at call time. The old ABC had the identical hole — this is not a regression, and closing it needs a static type checker, not a base class.

## Related

- **ADR-0009** — split the oracle's roles and named them. This ADR decides how a class states which of those roles it plays.
- **ADR-0004** — the same instinct at the checker boundary: a port names the contract; the adapter declares it implements it.

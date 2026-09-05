"""RNG-isolation guard for the example generators (executable ratchet).

The generators MUST draw randomness only from a per-instance ``random.Random``,
never from the process-global ``random`` stream (``random.shuffle``,
``random.choice``, ``random.seed``, ...). A shared global RNG makes seeded runs
fragile to call ordering and silently perturbs every other component that draws
from it — which would make any fixed-seed end-to-end replay untrustworthy.

Converting the generators to per-instance RNGs is a one-time change; this guard
is what keeps it from rotting. It fixes nothing — it fails the suite the moment
a global ``random.<attr>`` call (or a ``from random import <name>`` other than
``Random``) reappears under ``conacq/example_generators/``, in the commit that
introduces it, naming the file and line. Same ratchet principle as the layering
guard (ADR-0002): a guard blocks regression, it does not repair.

Allowed:   ``import random`` (optionally ``as x``) + ``x.Random(...)``, and
           ``from random import Random``.
Forbidden: any other attribute on the ``random`` module.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATORS_DIR = REPO_ROOT / "conacq" / "example_generators"

# The only member of the ``random`` module the generators may touch.
_ALLOWED = "Random"


def _iter_source_files(root: Path):
    """Yield every ``.py`` file under ``root`` (skipping bytecode caches)."""
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _random_aliases(tree: ast.AST) -> set:
    """Local names bound to the stdlib ``random`` module in this file.

    ``import random`` -> {"random"}; ``import random as r`` -> {"r"}.
    """
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random":
                    aliases.add(alias.asname or "random")
    return aliases


def _global_random_breaches(path: Path) -> list:
    """Uses of the global ``random`` module other than ``Random``."""
    rel = path.relative_to(REPO_ROOT)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _random_aliases(tree)
    breaches = []
    for node in ast.walk(tree):
        # `random.<attr>` where attr != "Random"  (e.g. random.shuffle(...))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in aliases and node.attr != _ALLOWED:
                breaches.append(
                    f"{rel}:{node.lineno}: global `{node.value.id}.{node.attr}` "
                    f"(draw from a per-instance random.Random instead)"
                )
        # `from random import <name>` where name != "Random"
        elif isinstance(node, ast.ImportFrom) and node.module == "random":
            for alias in node.names:
                if alias.name != _ALLOWED:
                    breaches.append(
                        f"{rel}:{node.lineno}: `from random import {alias.name}` "
                        f"(only Random may be imported)"
                    )
    return breaches


def test_example_generators_use_only_per_instance_random():
    """No global ``random.<attr>`` use survives under example_generators/.

    Turns the one-time '0 global random.*' grep into a permanent invariant: a
    reintroduced ``random.shuffle`` / ``random.choice`` / ``random.seed`` — the
    natural thing to type when no ``self._rng`` is in reach — fails right here.
    """
    breaches = []
    for path in _iter_source_files(GENERATORS_DIR):
        breaches.extend(_global_random_breaches(path))
    assert not breaches, (
        "global RNG use in example_generators "
        "(generators must use a per-instance random.Random):\n  "
        + "\n  ".join(breaches)
    )

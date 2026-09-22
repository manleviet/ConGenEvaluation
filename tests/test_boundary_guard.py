"""Architectural boundary guard — keep the three packages cleanly layered.

The repo is a three-tier stack with strictly one-directional dependencies::

    conacq        (application)      ── may use ──▶ explanation.api, profiling
      │
      ▼
    explanation   (framework)       ── may use ──▶ profiling
      │
      ▼
    profiling     (neutral leaf)    ── uses nothing but stdlib + itself

Each tier reaches the tier below ONLY through that tier's public façade, never
through submodule paths or underscore-private names. The leaf depends on
neither tier above it, so it stays a reusable, cycle-free port.

These tests parse every source file's imports with ``ast`` and pin the current,
clean state, enforcing six rules:

  (1) conacq → explanation : only ``explanation.api`` (no deep paths, no privates)
  (2) conacq → profiling   : only the ``profiling`` façade (no deep paths)
  (3) explanation → profiling : only the ``profiling`` façade (no deep paths)
  (4) explanation ⊥ conacq : the framework never imports the app
  (5) profiling is a leaf  : it never imports explanation or conacq
  (6) conacq core ⊥ conacq.eval : the app core (runners/algorithms/oracle/bias/
      examples/example_generators) never imports the ``eval`` layer, so the
      ``eval → core`` flow stays one-directional and the old runners↔eval cycle
      cannot return (ADR-0006). Catches absolute *and* relative imports.

A red test means a real breach (an import cycle or a leaked internal), not a
false alarm — report it rather than loosening the rule.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONACQ_DIR = REPO_ROOT / "conacq"
EXPLANATION_DIR = REPO_ROOT / "explanation"
PROFILING_DIR = REPO_ROOT / "profiling"

# The sole façade module of each tier that the tier above may import from.
EXPLANATION_FACADE = frozenset({"explanation.api"})
PROFILING_FACADE = frozenset({"profiling"})


def _iter_source_files(root: Path):
    """Yield every ``.py`` file under ``root`` (skipping bytecode caches)."""
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _iter_imports(path: Path):
    """Yield ``(module, imported_name, lineno)`` for each absolute import.

    ``import a.b.c``        -> ("a.b.c", None, lineno)
    ``from a.b import c``   -> ("a.b", "c", lineno)

    Relative imports (``from . import x``) stay within their own package and can
    never cross a tier boundary, so they are skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0:  # relative import — intra-package
                continue
            module = node.module or ""
            for alias in node.names:
                yield module, alias.name, node.lineno


def _top_package(module: str) -> str:
    return module.split(".", 1)[0]


def _facade_breaches(root: Path, target_top: str, facade: frozenset) -> list:
    """Imports of ``target_top`` from ``root`` that bypass the façade.

    A breach is a deep submodule path (anything under ``target_top`` other than
    the blessed façade module) or an underscore-private symbol name.
    """
    allowed = " / ".join(sorted(facade))
    breaches = []
    for path in _iter_source_files(root):
        rel = path.relative_to(REPO_ROOT)
        for module, name, lineno in _iter_imports(path):
            if _top_package(module) != target_top:
                continue
            if module not in facade:
                breaches.append(f"{rel}:{lineno}: deep import `{module}` (route through {allowed})")
                continue
            if name is not None and name.startswith("_"):
                breaches.append(f"{rel}:{lineno}: private symbol `{name}` from `{module}`")
    return breaches


def _dependency_breaches(root: Path, forbidden_top: str) -> list:
    """Any import of ``forbidden_top`` from files under ``root``."""
    breaches = []
    for path in _iter_source_files(root):
        rel = path.relative_to(REPO_ROOT)
        for module, _name, lineno in _iter_imports(path):
            if _top_package(module) == forbidden_top:
                breaches.append(f"{rel}:{lineno}: imports `{module}`")
    return breaches


def test_conacq_imports_explanation_only_through_public_api():
    """(1) App reaches the framework solely via ``explanation.api``."""
    breaches = _facade_breaches(CONACQ_DIR, "explanation", EXPLANATION_FACADE)
    assert not breaches, "conacq → explanation breaches:\n  " + "\n  ".join(breaches)


def test_conacq_imports_profiling_only_through_facade():
    """(2) App reaches the profiling leaf solely via the ``profiling`` façade."""
    breaches = _facade_breaches(CONACQ_DIR, "profiling", PROFILING_FACADE)
    assert not breaches, "conacq → profiling breaches:\n  " + "\n  ".join(breaches)








# The application core — everything under conacq except ``eval`` itself (and the
# conacq root, which may wire eval up). ``eval`` is a layer *above* these.
CONACQ_CORE_SUBPACKAGES = (
    "algorithms", "bias", "example_generators", "examples", "oracle", "runners",
)


def _resolves_to_eval(importer_pkg, level: int, module: str) -> bool:
    """Whether a (possibly relative) import from ``importer_pkg`` targets ``conacq.eval``.

    ``level`` is the ImportFrom dot count (0 = absolute). A relative import climbs
    ``level - 1`` packages up from the importing file's package before appending
    ``module`` — the same resolution Python's import machinery performs.
    """
    if level == 0:
        target = module
    else:
        up = level - 1
        base = list(importer_pkg[:len(importer_pkg) - up]) if up <= len(importer_pkg) else []
        target = ".".join(base + (module.split(".") if module else []))
    return target == "conacq.eval" or target.startswith("conacq.eval.")


def _eval_layer_breaches() -> list:
    """Imports of ``conacq.eval`` from the application core (absolute or relative)."""
    breaches = []
    for sub in CONACQ_CORE_SUBPACKAGES:
        root = CONACQ_DIR / sub
        if not root.exists():
            continue
        for path in _iter_source_files(root):
            rel = path.relative_to(REPO_ROOT)
            importer_pkg = rel.parts[:-1]  # package path of the importing file
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _resolves_to_eval(importer_pkg, 0, alias.name):
                            breaches.append(f"{rel}:{node.lineno}: imports `{alias.name}`")
                elif isinstance(node, ast.ImportFrom):
                    if _resolves_to_eval(importer_pkg, node.level, node.module or ""):
                        kind = "relative " if node.level else ""
                        breaches.append(f"{rel}:{node.lineno}: {kind}imports the eval layer")
    return breaches


def test_conacq_core_does_not_import_eval():
    """(6) The application core never imports ``conacq.eval`` (ADR-0006).

    ``eval`` (cross-validation, comparators, reports) consumes runs; the core
    produces them. Keeping the edge one-directional means the runners↔eval cycle
    — once papered over with a deferred import — cannot come back.
    """
    breaches = _eval_layer_breaches()
    assert not breaches, "conacq core → eval breaches (ADR-0006):\n  " + "\n  ".join(breaches)

# Rules (3), (4) and (5) were REMOVED, not disabled. They scanned REPO_ROOT/explanation
# and REPO_ROOT/profiling, which this repository has not held since 4b47c9b -- those
# packages are consumed from the canonical ../explanation checkout. rglob over a missing
# directory yields nothing, so _iter_source_files returned 0 files and all three
# asserted over an empty list: green forever, having examined nothing.
#
# Measured at removal: conacq/ = 74 files scanned, explanation/ = 0, profiling/ = 0.
# The surviving rules are the real boundary this repository can enforce. A guard that
# cannot fail is worse than an absent one: it reports a safety it is not providing.

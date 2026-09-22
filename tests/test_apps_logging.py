"""Logging contract for the apps/ CLI scripts.

Two things the print->logging pass must hold:

1. **Verbose-unification (the trap).** Apps set the log level *after* loading the
   config, from ``args.verbose or config['verbose']``. A config ``verbose=true``
   with no ``-v`` flag must therefore raise the level to DEBUG — otherwise the
   config's verbosity would silently stop working once ``if verbose: print``
   became ``logger.debug``.
2. **stdout is for the PRODUCT, stderr is for diagnostics.** An app's product
   (run_cv's CV report) goes to stdout via ``print``; banners, progress, warnings
   and errors go through the logger (stderr). So ``run_cv … > report.txt`` yields
   the clean report, not a banner-polluted file.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

from apps._harness import setup_logging

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_config_verbose_alone_enables_debug():
    """`verbose=true` in config (no -v) -> DEBUG level. This is the trap-fix:
    the app calls setup_logging(verbose=args.verbose or config.get('verbose')).
    """
    args_verbose = False              # no -v on the command line
    config_verbose = True             # but [general] verbose = true
    setup_logging(verbose=args_verbose or config_verbose)
    assert logging.getLogger().isEnabledFor(logging.DEBUG)


def test_default_level_is_info_not_debug():
    """Default (no verbosity) shows INFO progress but hides DEBUG detail —
    the level model that preserves the pre-refactor default output.
    """
    setup_logging(verbose=False)
    root = logging.getLogger()
    assert root.isEnabledFor(logging.INFO)
    assert not root.isEnabledFor(logging.DEBUG)


def test_run_cv_stdout_carries_only_the_product():
    """run_cv has exactly one print — the CV report; everything else is logged.

    Guards the stdout discipline: if a future edit sends a diagnostic to stdout
    via print, this fails.
    """
    src = (REPO_ROOT / "apps" / "run_cv.py").read_text()
    prints = [ln.strip() for ln in src.splitlines() if ln.lstrip().startswith("print(")]
    assert prints == ["print(cv_report)"], prints


def test_run_cv_diagnostics_go_to_stderr_not_stdout():
    """The config-not-found error is logged to stderr; stdout stays empty.

    Proves diagnostics route to stderr (the logger) — combined with the
    single-product-print guard above, stdout carries the product and nothing else.
    """
    env = {**os.environ, "PYTHONPATH": "."}
    result = subprocess.run(
        [sys.executable, "-m", "apps.run_cv", "/no/such/config.toml"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 1
    assert result.stdout == ""                       # nothing on stdout
    assert "Config not found" in result.stderr       # diagnostic on stderr

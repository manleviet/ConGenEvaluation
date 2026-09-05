"""Shared CLI harness for the ``apps/`` scripts.

Every app repeats the same skeleton: a TOML config path, a ``-v/--verbose`` flag,
logging setup, config loading, top-level error handling. This centralizes those so
each app declares only what is unique to it.

Flag **names and semantics are preserved** — ``build_parser`` adds the standard
``config`` positional and ``-v/--verbose`` exactly as the apps declared them (help
text is normalized). Apps whose CLI does not follow the standard shape (e.g.
``generate_bias_config``, whose positionals are ``fm_path``/``output`` and whose
``--config`` is an optional flag) keep their own parser and use only
``setup_logging`` / ``load_config``.
"""
from __future__ import annotations

import logging
import tomllib
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, Union


def build_parser(description: str, *, config: str = "required",
                 verbose: bool = True, verbose_help: str = "Verbose output",
                 **kwargs) -> ArgumentParser:
    """An ``ArgumentParser`` pre-loaded with the standard args; the app adds its own.

    ``config``: ``"required"`` (positional), ``"optional"`` (``nargs='?'``), or
    ``"none"``. ``verbose`` adds ``-v/--verbose``; ``verbose_help`` is its help
    string (pass an app's original text to keep ``--help`` unchanged, or ``None``
    for no description). Extra ``kwargs`` (e.g. ``formatter_class``, ``epilog``)
    pass straight through to ``ArgumentParser``.
    """
    parser = ArgumentParser(description=description, **kwargs)
    if config == "required":
        parser.add_argument("config", help="Path to TOML configuration file")
    elif config == "optional":
        parser.add_argument("config", nargs="?", default=None,
                            help="Path to TOML configuration file")
    elif config != "none":
        raise ValueError(f"config must be 'required' | 'optional' | 'none', got {config!r}")
    if verbose:
        parser.add_argument("-v", "--verbose", action="store_true", help=verbose_help)
    return parser


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure root logging once (to stderr).

    Diagnostics — banners, progress, warnings, errors — go to the logger (stderr);
    an app's actual PRODUCT stays on stdout via ``print``. Level: **INFO** by
    default so progress shows exactly as it did when it was ``print``; ``-v`` or a
    config ``verbose=true`` raises it to **DEBUG** to reveal the detail lines that
    used to sit behind ``if verbose:``.
    """
    level = logging.DEBUG if (verbose or debug) else logging.INFO
    # force=True so a later call (e.g. after config load, with the OR'd verbose)
    # actually re-applies the level — plain basicConfig is a no-op once handlers exist.
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)


def load_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load a TOML config file into a dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)

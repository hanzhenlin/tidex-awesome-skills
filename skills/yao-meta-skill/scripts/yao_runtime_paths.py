#!/usr/bin/env python3
"""Platform-aware user cache and state paths for Yao runtime data."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by update and telemetry helpers to keep runtime state outside skill source and install directories."

APP_DIR_NAME = "yao-meta-skill"


def _home_dir(home: Path | None) -> Path:
    return (home or Path.home()).expanduser().resolve()


def default_cache_dir(
    environ: dict[str, str] | None = None,
    *,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    environ = os.environ if environ is None else environ
    configured = environ.get("XDG_CACHE_HOME")
    if configured:
        return Path(configured).expanduser().resolve() / APP_DIR_NAME
    platform = platform or sys.platform
    home_dir = _home_dir(home)
    if platform == "darwin":
        return home_dir / "Library" / "Caches" / APP_DIR_NAME
    if platform.startswith("win") and environ.get("LOCALAPPDATA"):
        return Path(environ["LOCALAPPDATA"]).expanduser().resolve() / APP_DIR_NAME / "Cache"
    return home_dir / ".cache" / APP_DIR_NAME


def default_state_dir(
    environ: dict[str, str] | None = None,
    *,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    environ = os.environ if environ is None else environ
    configured = environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured).expanduser().resolve() / APP_DIR_NAME
    platform = platform or sys.platform
    home_dir = _home_dir(home)
    if platform == "darwin":
        return home_dir / "Library" / "Application Support" / APP_DIR_NAME
    if platform.startswith("win") and environ.get("LOCALAPPDATA"):
        return Path(environ["LOCALAPPDATA"]).expanduser().resolve() / APP_DIR_NAME / "State"
    return home_dir / ".local" / "state" / APP_DIR_NAME

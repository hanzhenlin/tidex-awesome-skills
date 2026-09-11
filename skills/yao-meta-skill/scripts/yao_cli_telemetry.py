#!/usr/bin/env python3
"""Metadata-only CLI telemetry helpers for yao.py."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from render_adoption_drift_report import append_event, normalize_event, skill_defaults, utc_now
from yao_runtime_paths import default_state_dir


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by yao.py to record opt-in metadata-only CLI run telemetry."

ENABLE_ENV = "YAO_CLI_TELEMETRY"
EVENTS_ENV = "YAO_CLI_TELEMETRY_EVENTS"
TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}


def add_telemetry_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--record-cli-telemetry",
        action="store_true",
        help="Record metadata-only yao.py command telemetry in the user state directory.",
    )
    parser.add_argument(
        "--no-cli-telemetry",
        action="store_true",
        help="Disable yao.py command telemetry even when YAO_CLI_TELEMETRY is enabled.",
    )
    parser.add_argument(
        "--telemetry-events-jsonl",
        help="Override the local metadata-only telemetry JSONL path.",
    )


def telemetry_enabled(args: argparse.Namespace, environ: dict[str, str] | None = None) -> bool:
    environ = os.environ if environ is None else environ
    if getattr(args, "no_cli_telemetry", False):
        return False
    if getattr(args, "record_cli_telemetry", False):
        return True
    raw = environ.get(ENABLE_ENV, "").strip().lower()
    if raw in TRUTHY:
        return True
    if raw in FALSY:
        return False
    return False


def telemetry_path(root: Path, args: argparse.Namespace, environ: dict[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    configured = getattr(args, "telemetry_events_jsonl", None) or environ.get(EVENTS_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return default_state_dir(environ) / "cli-telemetry-events.jsonl"


def telemetry_skill_root(engine_root: Path, args: argparse.Namespace) -> Path:
    context = getattr(args, "target_context", None)
    target_root = getattr(context, "target_root", None)
    if isinstance(target_root, Path) and (target_root / "SKILL.md").is_file():
        return target_root
    return engine_root


def normalize_command_name(value: Any) -> str:
    raw = str(value or "unknown")
    lowered = raw.strip().lower()
    safe = "".join(char for char in lowered if char.isalnum() or char in {"-", "_"})
    return safe[:64] or "unknown"


def cli_event(root: Path, args: argparse.Namespace, returncode: int) -> dict[str, str]:
    defaults = skill_defaults(root)
    ok = returncode == 0
    return {
        "event": "script_run",
        "skill": defaults["skill"],
        "version": defaults["version"],
        "activation_type": "manual",
        "outcome": "accepted" if ok else "failed",
        "failure_type": "none" if ok else "script_error",
        "timestamp": utc_now(),
        "source": "yao_cli",
        "command": normalize_command_name(getattr(args, "command", "unknown")),
    }


def maybe_record_cli_event(root: Path, args: argparse.Namespace, returncode: int) -> None:
    if not telemetry_enabled(args):
        return
    event_root = telemetry_skill_root(root, args)
    path = telemetry_path(root, args)
    event, failures = normalize_event(cli_event(event_root, args, returncode), skill_defaults(event_root), "yao-cli")
    if failures or event is None:
        sys.stderr.write(f"Telemetry skipped: {'; '.join(failures)}\n")
        return
    try:
        append_event(path, event)
    except OSError as exc:
        sys.stderr.write(f"Telemetry skipped: {exc}\n")

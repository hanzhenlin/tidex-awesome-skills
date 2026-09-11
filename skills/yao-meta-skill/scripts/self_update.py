#!/usr/bin/env python3
"""Safely update a verified managed yao-meta-skill installation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from check_update import (
    CACHE_PATH,
    DEFAULT_MANIFEST_URL,
    DEFAULT_VERSION_URL,
    check_update,
    is_newer,
)
from update_installation import (
    build_update_plan,
    detect_installation_channels,
    execute_update_plan,
)


ROOT = Path(__file__).resolve().parent.parent


def _excerpt(value: str, limit: int = 1200) -> str:
    text = value.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _managed_version(snapshot: dict[str, Any], channel_name: str) -> str:
    for item in snapshot.get("managed", []):
        if item.get("name") == channel_name:
            return str(item.get("version") or "")
    return ""


def run_self_update(
    *,
    root: Path,
    yes: bool,
    timeout: float,
    cache_path: Path = CACHE_PATH,
    update_result: dict[str, Any] | None = None,
    detector: Callable[[Path], dict[str, Any]] = detect_installation_channels,
    executor: Callable[[dict[str, Any]], dict[str, Any]] = execute_update_plan,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    update = update_result or check_update(
        root=root,
        cache_path=cache_path,
        version_url=DEFAULT_VERSION_URL,
        manifest_url=DEFAULT_MANIFEST_URL,
        timeout=timeout,
        max_age_days=1,
        force=True,
        no_cache=True,
        allow_custom_url=False,
        notice=False,
    )
    if not update.get("ok"):
        return {
            "ok": False,
            "status": "check-failed",
            "stage": "check",
            "update": update,
            "failures": [str(update.get("error") or "Update check failed.")],
        }

    before = detector(root)
    if not update.get("update_available"):
        return {
            "ok": True,
            "status": "current",
            "stage": "complete",
            "applied": False,
            "restart_required": False,
            "update": update,
            "installation_before": before,
            "plan": {},
            "failures": [],
        }

    plan = build_update_plan(before)
    if not plan.get("ok"):
        return {
            "ok": False,
            "status": "blocked",
            "stage": "plan",
            "applied": False,
            "restart_required": False,
            "update": update,
            "installation_before": before,
            "plan": plan,
            "failures": [str(plan.get("message") or "Update planning failed.")],
        }

    if not yes:
        return {
            "ok": True,
            "status": "confirmation-required",
            "stage": "plan",
            "applied": False,
            "restart_required": False,
            "update": update,
            "installation_before": before,
            "plan": plan,
            "failures": [],
        }

    execution = executor(plan)
    execution_summary = {
        "ok": bool(execution.get("ok")),
        "returncode": execution.get("returncode"),
        "stdout_excerpt": _excerpt(str(execution.get("stdout") or "")),
        "stderr_excerpt": _excerpt(str(execution.get("stderr") or "")),
    }
    if not execution_summary["ok"]:
        return {
            "ok": False,
            "status": "update-failed",
            "stage": "execute",
            "applied": False,
            "restart_required": False,
            "update": update,
            "installation_before": before,
            "plan": plan,
            "execution": execution_summary,
            "failures": [execution_summary["stderr_excerpt"] or "Installer command failed."],
        }

    after = detector(root)
    installed_version = _managed_version(after, str(plan.get("channel") or ""))
    remote_version = str(update.get("remote_version") or "")
    try:
        verified = bool(installed_version and remote_version and not is_newer(remote_version, installed_version))
    except ValueError:
        verified = False
    if not verified:
        return {
            "ok": False,
            "status": "verification-failed",
            "stage": "verify",
            "applied": True,
            "restart_required": False,
            "update": update,
            "installation_before": before,
            "installation_after": after,
            "plan": plan,
            "execution": execution_summary,
            "failures": [
                f"Installed version {installed_version or 'unknown'} did not reach {remote_version or 'unknown'}."
            ],
        }

    return {
        "ok": True,
        "status": "updated",
        "stage": "complete",
        "applied": True,
        "restart_required": True,
        "restart_message": "Restart Codex or the active AI client to load the updated skill.",
        "update": update,
        "installation_before": before,
        "installation_after": after,
        "plan": plan,
        "execution": execution_summary,
        "installed_version": installed_version,
        "failures": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a verified managed yao-meta-skill installation.")
    parser.add_argument("--yes", action="store_true", help="Apply the verified update plan.")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    result = run_self_update(root=ROOT, yes=args.yes, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()

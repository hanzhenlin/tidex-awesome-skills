#!/usr/bin/env python3
"""Update-check and self-update command handlers for the Yao CLI."""

import argparse
import json
import sys

from yao_cli_runtime import run_script


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by yao.py to keep update checks and the mutating self-update surface outside the CLI orchestrator."


def _emit_payload(result: dict) -> dict:
    payload = result["payload"] if result["payload"] is not None else result
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def command_check_update(args: argparse.Namespace) -> int:
    cmd = []
    if args.force:
        cmd.append("--force")
    if args.no_cache:
        cmd.append("--no-cache")
    if args.notice:
        cmd.append("--notice")
    if args.version_url:
        cmd.extend(["--version-url", args.version_url])
    if args.manifest_url:
        cmd.extend(["--manifest-url", args.manifest_url])
    if args.timeout is not None:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.max_age_days is not None:
        cmd.extend(["--max-age-days", str(args.max_age_days)])
    if args.allow_custom_update_url:
        cmd.append("--allow-custom-update-url")
    result = run_script("check_update.py", cmd)
    payload = _emit_payload(result)
    if args.notice and payload.get("notify_user") and payload.get("notice_text"):
        sys.stderr.write(str(payload["notice_text"]) + "\n")
    return 0 if result["ok"] else 2


def command_self_update(args: argparse.Namespace) -> int:
    cmd = []
    if args.yes:
        cmd.append("--yes")
    if args.timeout is not None:
        cmd.extend(["--timeout", str(args.timeout)])
    result = run_script("self_update.py", cmd)
    payload = _emit_payload(result)
    if payload.get("status") == "updated" and payload.get("restart_message"):
        sys.stderr.write(str(payload["restart_message"]) + "\n")
    return 0 if result["ok"] else 2

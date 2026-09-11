#!/usr/bin/env python3
"""Installation-channel discovery and safe update command construction."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by update check and self-update entrypoints for safe installation discovery and command execution."

SKILL_NAME = "yao-meta-skill"
OFFICIAL_REPOSITORY = "yaojingang/yao-meta-skill"
OFFICIAL_REPOSITORY_URL = "https://github.com/yaojingang/yao-meta-skill"
CommandRunner = Callable[[list[str], Path | None], subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]
MARKETPLACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def default_command_runner(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_version(path: Path) -> str:
    version_path = path / "VERSION"
    if version_path.is_file():
        value = version_path.read_text(encoding="utf-8", errors="replace").strip()
        if value:
            return value
    manifest = _load_json(path / "manifest.json")
    return str(manifest.get("version") or "").strip()


def is_official_repository(value: Any) -> bool:
    if isinstance(value, dict):
        value = value.get("url") or value.get("repository") or ""
    normalized = str(value or "").strip().removesuffix(".git").rstrip("/")
    return normalized in {OFFICIAL_REPOSITORY, OFFICIAL_REPOSITORY_URL}


def _skills_lock_entry(lock_path: Path) -> dict[str, Any]:
    payload = _load_json(lock_path)
    skills = payload.get("skills", payload)
    if not isinstance(skills, dict):
        return {}
    entry = skills.get(SKILL_NAME, {})
    return entry if isinstance(entry, dict) else {}


def _plugin_manifest(source_path: Path) -> dict[str, Any]:
    for candidate in (
        source_path / ".codex-plugin" / "plugin.json",
        source_path / "plugin.json",
    ):
        payload = _load_json(candidate)
        if payload:
            return payload
    return {}


def _official_plugin(item: dict[str, Any]) -> tuple[bool, str]:
    source = item.get("source", {})
    source_path = Path(str(source.get("path") or "")).expanduser()
    if not source_path.is_absolute() or not source_path.exists():
        return False, "Codex plugin source path is missing or invalid."
    manifest = _plugin_manifest(source_path.resolve())
    repository = manifest.get("repository") or manifest.get("homepage")
    if not is_official_repository(repository):
        return False, "Codex plugin repository does not match the official GitHub source."
    return True, str(source_path.resolve())


def _codex_plugins(
    executable: str,
    runner: CommandRunner,
) -> tuple[list[dict[str, Any]], list[str]]:
    proc = runner([executable, "plugin", "list", "--json"], None)
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "codex plugin list failed"
        return [], [message]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], ["codex plugin list returned invalid JSON."]
    installed = payload.get("installed", []) if isinstance(payload, dict) else []
    return ([item for item in installed if isinstance(item, dict)], [])


def detect_installation_channels(
    root: Path,
    *,
    home: Path | None = None,
    runner: CommandRunner = default_command_runner,
    which: Which = shutil.which,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    home = (home or Path.home()).expanduser().resolve()
    agents_lock = home / ".agents" / ".skill-lock.json"
    agents_install = home / ".agents" / "skills" / SKILL_NAME
    codex_skill = home / ".codex" / "skills" / SKILL_NAME
    managed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    warnings: list[str] = []

    lock_entry = _skills_lock_entry(agents_lock)
    lock_source = lock_entry.get("source") or lock_entry.get("sourceUrl")
    if lock_entry and is_official_repository(lock_source) and (agents_install / "SKILL.md").is_file():
        managed.append(
            {
                "name": "skills-cli",
                "version": _load_version(agents_install),
                "source": str(lock_source),
                "install_path": str(agents_install),
                "marketplace": "",
                "executable": which("npx") or "",
            }
        )
    elif (agents_install / "SKILL.md").is_file():
        reason = (
            "The skills lock source is not the official GitHub repository."
            if lock_entry
            else "The active .agents skill copy has no managed install record."
        )
        blocked.append(
            {
                "name": "unmanaged-agents-copy",
                "version": _load_version(agents_install),
                "path": str(agents_install),
                "reason": reason,
            }
        )

    codex_executable = which("codex")
    if codex_executable:
        plugins, plugin_warnings = _codex_plugins(codex_executable, runner)
        warnings.extend(plugin_warnings)
        for item in plugins:
            plugin_id = str(item.get("pluginId") or "")
            if item.get("name") != SKILL_NAME and not plugin_id.startswith(f"{SKILL_NAME}@"):
                continue
            official, detail = _official_plugin(item)
            if official:
                managed.append(
                    {
                        "name": "codex-plugin",
                        "version": str(item.get("version") or ""),
                        "source": OFFICIAL_REPOSITORY_URL,
                        "install_path": detail,
                        "marketplace": str(item.get("marketplaceName") or ""),
                        "executable": codex_executable,
                    }
                )
            else:
                blocked.append(
                    {
                        "name": "untrusted-codex-plugin",
                        "version": str(item.get("version") or ""),
                        "path": detail,
                        "reason": detail,
                    }
                )

    if (codex_skill / "SKILL.md").is_file():
        blocked.append(
            {
                "name": "unmanaged-codex-copy",
                "version": _load_version(codex_skill),
                "path": str(codex_skill),
                "reason": "The direct .codex skill copy has no verified marketplace record.",
            }
        )

    git_marker = root / ".git"
    if git_marker.exists():
        dirty = None
        git_executable = which("git")
        if git_executable:
            proc = runner([git_executable, "-C", str(root), "status", "--porcelain"], root)
            dirty = bool(proc.stdout.strip()) if proc.returncode == 0 else None
            if proc.returncode != 0:
                warnings.append(proc.stderr.strip() or "git status failed during update discovery.")
        blocked.append(
            {
                "name": "development-checkout",
                "version": _load_version(root),
                "path": str(root),
                "dirty": dirty,
                "reason": "Development checkouts are never modified by self-update.",
            }
        )

    managed_paths = {
        str(Path(str(item.get("install_path") or "")).expanduser().resolve())
        for item in managed
        if item.get("install_path")
    }
    has_target_block = any(
        item.get("name") in {"development-checkout", "unmanaged-agents-copy", "unmanaged-codex-copy"}
        and item.get("path") == str(root)
        for item in blocked
    )
    if (root / "SKILL.md").is_file() and str(root) not in managed_paths and not has_target_block:
        blocked.append(
            {
                "name": "unmanaged-source-copy",
                "version": _load_version(root),
                "path": str(root),
                "reason": "The running Skill directory has no verified managed install record.",
            }
        )

    return {
        "managed": managed,
        "blocked": blocked,
        "warnings": warnings,
        "summary": {
            "managed_count": len(managed),
            "blocked_count": len(blocked),
            "managed_channels": [item["name"] for item in managed],
        },
    }


def build_update_plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    managed = list(snapshot.get("managed", []))
    blocked = list(snapshot.get("blocked", []))
    protected_target = next(
        (
            item
            for item in blocked
            if item.get("name") in {"development-checkout", "unmanaged-source-copy"}
        ),
        None,
    )
    if protected_target:
        return {
            "ok": False,
            "error": str(protected_target.get("name")),
            "message": str(protected_target.get("reason") or "The running Skill directory is read-only."),
            "channels": [item.get("name") for item in managed],
            "argv": [],
        }
    if len(managed) > 1:
        return {
            "ok": False,
            "error": "multiple-managed-channels",
            "message": "Multiple managed install channels were found; refusing to choose one automatically.",
            "channels": [item.get("name") for item in managed],
            "argv": [],
        }
    if not managed:
        return {
            "ok": False,
            "error": "no-managed-channel",
            "message": "No verified managed install channel is available for one-confirmation update.",
            "channels": [],
            "argv": [],
        }
    channel = managed[0]
    if not is_official_repository(channel.get("source")):
        return {
            "ok": False,
            "error": "untrusted-source",
            "message": "The managed channel source does not match the official GitHub repository.",
            "channels": [channel.get("name")],
            "argv": [],
        }
    executable = str(channel.get("executable") or "")
    if not executable:
        return {
            "ok": False,
            "error": "installer-unavailable",
            "message": f"The installer for {channel.get('name')} is unavailable.",
            "channels": [channel.get("name")],
            "argv": [],
        }
    if channel.get("name") == "skills-cli":
        argv = [executable, "-y", "skills", "update", SKILL_NAME, "-g", "-y"]
    elif channel.get("name") == "codex-plugin":
        marketplace = str(channel.get("marketplace") or "")
        if not MARKETPLACE_RE.fullmatch(marketplace):
            return {
                "ok": False,
                "error": "marketplace-missing",
                "message": "The installed Codex plugin has no safe marketplace identity.",
                "channels": [channel.get("name")],
                "argv": [],
            }
        argv = [executable, "plugin", "marketplace", "upgrade", marketplace]
    else:
        return {
            "ok": False,
            "error": "unsupported-channel",
            "message": f"Unsupported managed update channel: {channel.get('name')}",
            "channels": [channel.get("name")],
            "argv": [],
        }
    return {
        "ok": True,
        "error": None,
        "message": "Explicit confirmation is required before updating the installed skill.",
        "channel": channel.get("name"),
        "channels": [channel.get("name")],
        "source": channel.get("source"),
        "argv": argv,
    }


def _plan_argv_is_allowlisted(plan: dict[str, Any], argv: list[str]) -> bool:
    if not is_official_repository(plan.get("source")):
        return False
    if plan.get("channel") == "skills-cli":
        return len(argv) == 7 and Path(argv[0]).name == "npx" and argv[1:] == [
            "-y",
            "skills",
            "update",
            SKILL_NAME,
            "-g",
            "-y",
        ]
    if plan.get("channel") == "codex-plugin":
        return (
            len(argv) == 5
            and Path(argv[0]).name == "codex"
            and argv[1:4] == ["plugin", "marketplace", "upgrade"]
            and bool(MARKETPLACE_RE.fullmatch(argv[4]))
        )
    return False


def execute_update_plan(
    plan: dict[str, Any],
    *,
    runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    argv = [str(item) for item in plan.get("argv", [])]
    if not plan.get("ok") or not argv or not _plan_argv_is_allowlisted(plan, argv):
        return {
            "ok": False,
            "returncode": 2,
            "stdout": "",
            "stderr": "Update plan is not executable or does not match the command allowlist.",
        }
    proc = runner(argv, None)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

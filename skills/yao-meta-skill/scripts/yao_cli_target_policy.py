#!/usr/bin/env python3
"""Target binding and self-write authorization for the unified Yao CLI."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skill_ir_paths import load_manifest, read_frontmatter


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by yao.py to bind every CLI command to an explicit target before execution."

NEW_TARGET_COMMANDS = {"init", "quickstart"}
GLOBAL_COMMANDS = {
    "check-update",
    "install-status",
    "localized-doc-sync-check",
    "pr-review-report",
}
WORKSPACE_COMMANDS = {"skill-atlas"}
SELF_SKILL_NAME = "yao-meta-skill"
WRITE_PATH_DESTINATIONS = {
    "events_jsonl",
    "install_root",
    "output_dir",
    "output_html",
    "output_json",
    "output_jsonl",
    "output_md",
    "registry_dir",
    "telemetry_events_jsonl",
}
COMMAND_WRITE_PATH_DESTINATIONS = {
    "adapt-apply": {"approval_ledger"},
    "daily-skillops": {"patterns_json", "proposals_json"},
    "output-eval": {"blind_answer_key_json", "blind_pack_json", "blind_pack_md"},
    "output-review-import": {"adjudication_json", "adjudication_md"},
    "output-review-kit": {"decisions"},
    "output-review": {"decisions"},
    "review-annotations": {"annotations_json"},
    "skill-atlas": {"report_html", "report_json"},
}


@dataclass(frozen=True)
class TargetContext:
    command: str
    policy: str
    engine_root: Path
    target_root: Path | None
    skill_name: str | None
    self_authorized: bool


class TargetPolicyError(RuntimeError):
    """Stable target-policy failure with a machine-readable payload."""

    def __init__(self, code: str, command: str, message: str) -> None:
        super().__init__(message)
        self.payload = {
            "ok": False,
            "error": code,
            "command": command,
            "message": message,
        }


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _argument(command_parser: argparse.ArgumentParser, dest: str) -> argparse.Action | None:
    return next((action for action in command_parser._actions if action.dest == dest), None)


def _add_self_authorization(command_parser: argparse.ArgumentParser) -> None:
    if _argument(command_parser, "self_authorized") is None:
        command_parser.add_argument(
            "--self",
            dest="self_authorized",
            action="store_true",
            help="Explicitly authorize this command to target yao-meta-skill itself.",
        )


def configure_target_policies(parser: argparse.ArgumentParser) -> None:
    """Attach a complete target policy to every public subcommand."""

    for command, command_parser in _subcommands(parser).items():
        skill_dir = _argument(command_parser, "skill_dir")
        if skill_dir is not None:
            skill_dir.default = None
            _add_self_authorization(command_parser)
            command_parser.set_defaults(target_policy="skill")
            continue
        if command in NEW_TARGET_COMMANDS:
            _add_self_authorization(command_parser)
            command_parser.set_defaults(target_policy="new")
            continue
        if command in GLOBAL_COMMANDS:
            _add_self_authorization(command_parser)
            command_parser.set_defaults(target_policy="global")
            continue
        if command in WORKSPACE_COMMANDS:
            workspace_root = _argument(command_parser, "workspace_root")
            if workspace_root is None:
                raise RuntimeError(f"Workspace command is missing --workspace-root: {command}")
            workspace_root.default = None
            _add_self_authorization(command_parser)
            command_parser.set_defaults(target_policy="workspace")
            continue
        _add_self_authorization(command_parser)
        command_parser.set_defaults(target_policy="self")


def _skill_identity(skill_dir: Path) -> str | None:
    manifest: dict[str, Any] = {}
    frontmatter: dict[str, Any] = {}
    try:
        manifest = load_manifest(skill_dir)
    except Exception:
        pass
    try:
        frontmatter = read_frontmatter(skill_dir)
    except Exception:
        pass
    value: Any = manifest.get("name") or frontmatter.get("name")
    if not value:
        try:
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            parts = text.split("---", 2)
            raw_frontmatter = parts[1] if len(parts) >= 3 and not parts[0].strip() else ""
            match = re.search(r"(?m)^name\s*:\s*[\"']?([^\"'\n#]+)", raw_frontmatter)
            value = match.group(1).strip() if match else None
        except OSError:
            pass
    return str(value).strip() if value else None


def is_self_skill(skill_dir: Path, engine_root: Path, *, skill_name: str | None = None) -> bool:
    """Return whether a path or declared identity requires self authorization."""

    target = skill_dir.expanduser().resolve()
    engine = engine_root.expanduser().resolve()
    identity = skill_name if skill_name is not None else _skill_identity(target)
    return target == engine or engine in target.parents or identity == SELF_SKILL_NAME


def _resolve_existing_target(raw_target: str, command: str) -> Path:
    target = Path(raw_target).expanduser().resolve()
    if not target.is_dir():
        raise TargetPolicyError(
            "target-invalid",
            command,
            f"Target directory does not exist: {target}",
        )
    return target


def _require_self_authorization(
    *,
    command: str,
    target: Path,
    engine_root: Path,
    skill_name: str | None,
    authorized: bool,
) -> None:
    targets_self = is_self_skill(target, engine_root, skill_name=skill_name)
    if targets_self and not authorized:
        raise TargetPolicyError(
            "self-target-blocked",
            command,
            f"Command '{command}' resolves to yao-meta-skill. Re-run with --self to authorize modifying it.",
        )


def _bind_declared_write_paths(
    *,
    args: argparse.Namespace,
    base_root: Path,
    engine_root: Path,
    command: str,
    authorized: bool,
) -> None:
    """Resolve declared write destinations and protect the engine subtree."""

    destinations = set(WRITE_PATH_DESTINATIONS)
    destinations.update(COMMAND_WRITE_PATH_DESTINATIONS.get(command, set()))
    if command == "daily-skillops" and getattr(args, "no_refresh_source_reports", False):
        destinations.difference_update({"patterns_json", "proposals_json"})
    if command == "review-annotations" and not (
        getattr(args, "write_template", False) or getattr(args, "add_annotation", False)
    ):
        destinations.discard("annotations_json")
    if command in {"output-review", "output-review-kit"} and not getattr(args, "write_template", False):
        destinations.discard("decisions")
    if command == "output-review-import" and not getattr(args, "run_adjudication", False):
        destinations.difference_update({"adjudication_json", "adjudication_md"})

    for destination in destinations:
        raw_value = getattr(args, destination, None)
        if not raw_value:
            continue
        raw_path = Path(str(raw_value)).expanduser()
        resolved = (raw_path if raw_path.is_absolute() else base_root / raw_path).resolve()
        if (resolved == engine_root or engine_root in resolved.parents) and not authorized:
            raise TargetPolicyError(
                "self-target-blocked",
                command,
                f"Command '{command}' would write inside yao-meta-skill at {resolved}. Re-run with --self to authorize it.",
            )
        setattr(args, destination, str(resolved))


def prepare_target_context(engine_root: Path, args: argparse.Namespace) -> TargetContext:
    """Resolve and validate command identity before any command handler can write."""

    engine_root = engine_root.resolve()
    command = str(getattr(args, "command", "unknown"))
    policy = str(getattr(args, "target_policy", ""))
    authorized = bool(getattr(args, "self_authorized", False))

    if policy == "skill":
        raw_target = getattr(args, "skill_dir", None)
        if not raw_target:
            raise TargetPolicyError(
                "target-required",
                command,
                f"Command '{command}' requires an explicit skill_dir. Pass '.' to use the current directory.",
            )
        target = _resolve_existing_target(str(raw_target), command)
        skill_name = _skill_identity(target)
        _require_self_authorization(
            command=command,
            target=target,
            engine_root=engine_root,
            skill_name=skill_name,
            authorized=authorized,
        )
        args.skill_dir = str(target)
        context = TargetContext(command, policy, engine_root, target, skill_name, authorized)
    elif policy == "workspace":
        raw_target = getattr(args, "workspace_root", None)
        if not raw_target:
            raise TargetPolicyError(
                "target-required",
                command,
                f"Command '{command}' requires an explicit --workspace-root.",
            )
        target = _resolve_existing_target(str(raw_target), command)
        _require_self_authorization(
            command=command,
            target=target,
            engine_root=engine_root,
            skill_name=None,
            authorized=authorized,
        )
        args.workspace_root = str(target)
        context = TargetContext(command, policy, engine_root, target, None, authorized)
    elif policy == "self":
        if not authorized:
            raise TargetPolicyError(
                "self-target-blocked",
                command,
                f"Command '{command}' operates on yao-meta-skill. Re-run with --self to authorize modifying it.",
            )
        context = TargetContext(command, policy, engine_root, engine_root, SELF_SKILL_NAME, True)
    elif policy == "new":
        name = getattr(args, "name", None)
        output_dir = Path(getattr(args, "output_dir", ".")).expanduser().resolve()
        target = (output_dir / str(name)).resolve() if name else None
        if target is not None:
            _require_self_authorization(
                command=command,
                target=target,
                engine_root=engine_root,
                skill_name=str(name) if name else None,
                authorized=authorized,
            )
        args.output_dir = str(output_dir)
        context = TargetContext(command, policy, engine_root, target, str(name) if name else None, authorized)
    elif policy == "global":
        context = TargetContext(command, policy, engine_root, None, None, False)
    else:
        raise TargetPolicyError(
            "target-policy-missing",
            command,
            f"Command '{command}' has no declared target policy.",
        )

    if policy in {"skill", "workspace", "self"} and context.target_root is not None:
        _bind_declared_write_paths(
            args=args,
            base_root=context.target_root,
            engine_root=engine_root,
            command=command,
            authorized=authorized,
        )
    elif policy == "global":
        _bind_declared_write_paths(
            args=args,
            base_root=Path.cwd().resolve(),
            engine_root=engine_root,
            command=command,
            authorized=authorized,
        )

    args.target_context = context
    return context

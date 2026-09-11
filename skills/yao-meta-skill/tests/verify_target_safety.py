#!/usr/bin/env python3
"""Regression checks for explicit target binding and self-write protection."""

import json
import os
import subprocess
import sys
import tempfile
import hashlib
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "yao.py"
sys.path.insert(0, str(ROOT / "scripts"))

import yao as yao_cli  # noqa: E402
from yao_cli_telemetry import telemetry_enabled, telemetry_path  # noqa: E402
from yao_runtime_paths import default_cache_dir, default_state_dir  # noqa: E402


def run_cli(*args: str, cwd: Path, env: dict[str, str] | None = None, cli: Path = CLI) -> dict:
    child_env = dict(os.environ)
    child_env["YAO_CLI_TELEMETRY"] = "0"
    child_env.pop("YAO_CLI_TELEMETRY_EVENTS", None)
    if env:
        child_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(cli), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=child_env,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else None
    return {
        "returncode": proc.returncode,
        "payload": payload,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def tracked_tree_hash() -> str:
    paths = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    digest = hashlib.sha256()
    for raw_path in paths:
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        path = ROOT / relative
        if not path.is_file():
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def file_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="yao-target-safety-") as raw_tmp:
        tmp_root = Path(raw_tmp)
        missing_target = run_cli("validate", cwd=tmp_root)
        assert missing_target["returncode"] == 2, missing_target
        assert missing_target["payload"] == {
            "ok": False,
            "error": "target-required",
            "command": "validate",
            "message": "Command 'validate' requires an explicit skill_dir. Pass '.' to use the current directory.",
        }, missing_target

        init_result = run_cli(
            "init",
            "external-skill",
            "--description",
            "Validate an explicitly selected external skill.",
            "--output-dir",
            str(tmp_root),
            cwd=tmp_root,
        )
        assert init_result["returncode"] == 0, init_result
        external_skill = tmp_root / "external-skill"
        default_init = run_cli(
            "init",
            "cwd-created-skill",
            "--description",
            "Default creation must stay under the caller working directory.",
            cwd=tmp_root,
        )
        assert default_init["returncode"] == 0, default_init
        assert (tmp_root / "cwd-created-skill" / "SKILL.md").is_file(), default_init
        assert not (ROOT / "cwd-created-skill").exists(), default_init
        blocked_nested_init_name = "blocked-nested-init-safety-fixture"
        blocked_nested_init_path = ROOT / blocked_nested_init_name
        assert not blocked_nested_init_path.exists(), blocked_nested_init_path
        blocked_nested_init = run_cli(
            "init",
            blocked_nested_init_name,
            "--description",
            "Creating inside the engine requires self authorization.",
            cwd=ROOT,
        )
        assert blocked_nested_init["returncode"] == 2, blocked_nested_init
        assert blocked_nested_init["payload"]["error"] == "self-target-blocked", blocked_nested_init
        assert not blocked_nested_init_path.exists(), blocked_nested_init
        explicit_target = run_cli("validate", str(external_skill), cwd=tmp_root)
        assert explicit_target["returncode"] == 0, explicit_target
        engine_before = tracked_tree_hash()
        external_report = run_cli("skill-report", str(external_skill), cwd=tmp_root)
        assert external_report["returncode"] == 0, external_report
        assert tracked_tree_hash() == engine_before

        relative_report_dir = external_skill / "relative-review"
        relative_output = run_cli(
            "architecture-audit",
            str(external_skill),
            "--output-json",
            "relative-review/architecture.json",
            "--output-md",
            "relative-review/architecture.md",
            cwd=tmp_root,
        )
        assert relative_output["returncode"] == 0, relative_output
        assert (relative_report_dir / "architecture.json").is_file(), relative_output
        assert (relative_report_dir / "architecture.md").is_file(), relative_output
        assert not (ROOT / "relative-review").exists(), relative_output

        engine_external_zip = ROOT / "dist" / "external-skill.zip"
        engine_external_zip_before = engine_external_zip.read_bytes() if engine_external_zip.exists() else None
        external_package = run_cli(
            "package",
            str(external_skill),
            "--platform",
            "generic",
            "--zip",
            cwd=tmp_root,
        )
        assert external_package["returncode"] == 0, external_package
        assert (external_skill / "dist" / "external-skill.zip").is_file(), external_package
        engine_external_zip_after = engine_external_zip.read_bytes() if engine_external_zip.exists() else None
        assert engine_external_zip_after == engine_external_zip_before

        blocked_engine_output = run_cli(
            "architecture-audit",
            str(external_skill),
            "--output-json",
            str(ROOT / "reports" / "blocked-external-output.json"),
            cwd=tmp_root,
        )
        assert blocked_engine_output["returncode"] == 2, blocked_engine_output
        assert blocked_engine_output["payload"]["error"] == "self-target-blocked", blocked_engine_output
        assert not (ROOT / "reports" / "blocked-external-output.json").exists(), blocked_engine_output

        blocked_global_output = run_cli(
            "localized-doc-sync-check",
            "--source",
            str(ROOT / "README.md"),
            "--localized",
            str(ROOT / "docs" / "README.zh-CN.md"),
            "--output-json",
            "reports/blocked-global-output.json",
            cwd=ROOT,
        )
        assert blocked_global_output["returncode"] == 2, blocked_global_output
        assert blocked_global_output["payload"]["error"] == "self-target-blocked", blocked_global_output
        assert not (ROOT / "reports" / "blocked-global-output.json").exists(), blocked_global_output

        external_registry = run_cli("registry-audit", str(external_skill), cwd=tmp_root)
        assert external_registry["returncode"] in {0, 2}, external_registry
        assert external_registry["payload"].get("error") != "self-target-blocked", external_registry
        assert (external_skill / "registry" / "index.json").is_file(), external_registry
        assert (external_skill / "reports" / "registry_audit.json").is_file(), external_registry

        workspace_atlas = run_cli(
            "skill-atlas",
            "--workspace-root",
            str(tmp_root),
            cwd=tmp_root,
        )
        assert workspace_atlas["returncode"] == 0, workspace_atlas
        assert (tmp_root / "skill_atlas" / "catalog.json").is_file(), workspace_atlas
        assert (tmp_root / "reports" / "skill_atlas.json").is_file(), workspace_atlas

        blocked_guard_root = ROOT / "tests" / "tmp_target_safety_write_guards"
        assert not blocked_guard_root.exists(), blocked_guard_root
        blocked_atlas_report = run_cli(
            "skill-atlas",
            "--workspace-root",
            str(tmp_root),
            "--report-json",
            str(blocked_guard_root / "atlas.json"),
            cwd=tmp_root,
        )
        assert blocked_atlas_report["returncode"] == 2, blocked_atlas_report
        assert blocked_atlas_report["payload"]["error"] == "self-target-blocked", blocked_atlas_report

        daily_source = tmp_root / "daily-source.jsonl"
        daily_source.write_text(
            json.dumps({"category": "format", "signal": "use concise headings"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        blocked_daily_patterns = run_cli(
            "daily-skillops",
            str(external_skill),
            "--source",
            str(daily_source),
            "--patterns-json",
            str(blocked_guard_root / "patterns.json"),
            cwd=tmp_root,
        )
        assert blocked_daily_patterns["returncode"] == 2, blocked_daily_patterns
        assert blocked_daily_patterns["payload"]["error"] == "self-target-blocked", blocked_daily_patterns

        blocked_approval_ledger = run_cli(
            "adapt-apply",
            str(external_skill),
            "--write-template",
            "--approval-ledger",
            str(blocked_guard_root / "approval-ledger.json"),
            cwd=tmp_root,
        )
        assert blocked_approval_ledger["returncode"] == 2, blocked_approval_ledger
        assert blocked_approval_ledger["payload"]["error"] == "self-target-blocked", blocked_approval_ledger

        blocked_annotations_source = run_cli(
            "review-annotations",
            str(external_skill),
            "--write-template",
            "--annotations-json",
            str(blocked_guard_root / "annotations.json"),
            cwd=tmp_root,
        )
        assert blocked_annotations_source["returncode"] == 2, blocked_annotations_source
        assert blocked_annotations_source["payload"]["error"] == "self-target-blocked", blocked_annotations_source
        assert not blocked_guard_root.exists(), blocked_guard_root

        original_skill = (external_skill / "SKILL.md").read_bytes()
        collision = run_cli(
            "init",
            "external-skill",
            "--description",
            "This second initialization must be refused.",
            "--output-dir",
            str(tmp_root),
            cwd=tmp_root,
        )
        assert collision["returncode"] == 2, collision
        assert collision["payload"]["error"] == "target-exists", collision
        assert (external_skill / "SKILL.md").read_bytes() == original_skill

        file_collision = tmp_root / "file-collision"
        original_file = b"existing user file\n"
        file_collision.write_bytes(original_file)
        collision_with_file = run_cli(
            "init",
            "file-collision",
            "--description",
            "Initialization must also preserve an existing file target.",
            "--output-dir",
            str(tmp_root),
            cwd=tmp_root,
        )
        assert collision_with_file["returncode"] == 2, collision_with_file
        assert collision_with_file["payload"]["error"] == "target-exists", collision_with_file
        assert file_collision.read_bytes() == original_file

        blocked_self = run_cli("validate", str(ROOT), cwd=tmp_root)
        assert blocked_self["returncode"] == 2, blocked_self
        assert blocked_self["payload"]["error"] == "self-target-blocked", blocked_self
        allowed_self = run_cli("validate", str(ROOT), "--self", cwd=tmp_root)
        assert allowed_self["payload"].get("error") != "self-target-blocked", allowed_self
        assert allowed_self["payload"].get("skill_dir") == str(ROOT), allowed_self

        root_alias = tmp_root / "root-alias"
        root_alias.symlink_to(ROOT, target_is_directory=True)
        blocked_alias = run_cli("validate", str(root_alias), cwd=tmp_root)
        assert blocked_alias["returncode"] == 2, blocked_alias
        assert blocked_alias["payload"]["error"] == "self-target-blocked", blocked_alias

        cloned_self_init = run_cli(
            "init",
            "yao-meta-skill",
            "--description",
            "A separate Yao identity fixture.",
            "--output-dir",
            str(tmp_root),
            "--self",
            cwd=tmp_root,
        )
        assert cloned_self_init["returncode"] == 0, cloned_self_init
        cloned_self = tmp_root / "yao-meta-skill"
        (cloned_self / "manifest.json").write_text("{invalid", encoding="utf-8")
        (cloned_self / "SKILL.md").write_text(
            "---\nname: yao-meta-skill\nbroken: [\n---\n# Invalid identity fixture\n",
            encoding="utf-8",
        )
        blocked_identity = run_cli("validate", str(cloned_self), cwd=tmp_root)
        assert blocked_identity["returncode"] == 2, blocked_identity
        assert blocked_identity["payload"]["error"] == "self-target-blocked", blocked_identity

        blocked_root_command = run_cli("report", cwd=tmp_root)
        assert blocked_root_command["returncode"] == 2, blocked_root_command
        assert blocked_root_command["payload"]["error"] == "self-target-blocked", blocked_root_command

        parser = yao_cli.build_parser()
        command_parsers = next(
            action.choices
            for action in parser._actions
            if isinstance(action, __import__("argparse")._SubParsersAction)
        )
        assert command_parsers, parser.format_help()
        for command, command_parser in command_parsers.items():
            assert command_parser._defaults.get("target_policy"), command
            skill_dir = next((action for action in command_parser._actions if action.dest == "skill_dir"), None)
            if skill_dir is not None:
                assert skill_dir.default is None, command
                assert any(action.dest == "self_authorized" for action in command_parser._actions), command

        state_home = tmp_root / "state-home"
        cache_home = tmp_root / "cache-home"
        default_telemetry = telemetry_path(
            ROOT,
            Namespace(telemetry_events_jsonl=None),
            environ={"XDG_STATE_HOME": str(state_home)},
        )
        expected_telemetry = state_home.resolve() / "yao-meta-skill" / "cli-telemetry-events.jsonl"
        assert default_telemetry == expected_telemetry, default_telemetry
        isolated_home = tmp_root / "isolated-home"
        assert default_cache_dir({}, home=isolated_home, platform="linux") == isolated_home.resolve() / ".cache" / "yao-meta-skill"
        assert default_state_dir({}, home=isolated_home, platform="linux") == isolated_home.resolve() / ".local" / "state" / "yao-meta-skill"
        with patch.dict(os.environ, {"YAO_CLI_TELEMETRY": "1"}, clear=True):
            assert telemetry_enabled(Namespace(no_cli_telemetry=False, record_cli_telemetry=False), environ={}) is False

        path_env = dict(os.environ)
        path_env["PYTHONPATH"] = str(ROOT / "scripts")
        path_env["XDG_CACHE_HOME"] = str(cache_home)
        cache_path_proc = subprocess.run(
            [sys.executable, "-c", "import check_update; print(check_update.CACHE_PATH)"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            env=path_env,
        )
        expected_cache = cache_home.resolve() / "yao-meta-skill" / "update-check.json"
        assert Path(cache_path_proc.stdout.strip()) == expected_cache, cache_path_proc.stdout

        root_telemetry = ROOT / "reports" / "telemetry_events.jsonl"
        root_telemetry_before = root_telemetry.read_bytes() if root_telemetry.exists() else None
        telemetry_run = run_cli(
            "validate",
            str(external_skill),
            cwd=tmp_root,
            env={
                "YAO_CLI_TELEMETRY": "1",
                "XDG_STATE_HOME": str(state_home),
            },
        )
        assert telemetry_run["returncode"] == 0, telemetry_run
        telemetry_events_path = expected_telemetry
        telemetry_events = [json.loads(line) for line in telemetry_events_path.read_text(encoding="utf-8").splitlines()]
        assert telemetry_events[-1]["skill"] == "external-skill", telemetry_events
        root_telemetry_after = root_telemetry.read_bytes() if root_telemetry.exists() else None
        assert root_telemetry_after == root_telemetry_before

        root_cache = ROOT / ".yao" / "update-check.json"
        root_cache_before = root_cache.read_bytes() if root_cache.exists() else None
        update_env = dict(os.environ)
        update_env["XDG_CACHE_HOME"] = str(cache_home)
        update_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_update.py"),
                "--force",
                "--allow-custom-update-url",
                "--version-url",
                "https://127.0.0.1:1/VERSION",
                "--manifest-url",
                "https://127.0.0.1:1/manifest.json",
                "--timeout",
                "0.01",
            ],
            cwd=tmp_root,
            capture_output=True,
            text=True,
            env=update_env,
        )
        assert update_proc.returncode == 2, update_proc.stdout
        assert expected_cache.exists(), update_proc.stdout
        root_cache_after = root_cache.read_bytes() if root_cache.exists() else None
        assert root_cache_after == root_cache_before

        optional_target_scripts = []
        for script in (ROOT / "scripts").glob("*.py"):
            if script.name.startswith("yao_cli_parser"):
                continue
            text = script.read_text(encoding="utf-8")
            if 'add_argument("skill_dir"' in text and 'nargs="?"' in text:
                optional_target_scripts.append(script.name)
        assert optional_target_scripts == [], optional_target_scripts

        package_dir = tmp_root / "package"
        package_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "cross_packager.py"),
                str(ROOT),
                "--output-dir",
                str(package_dir),
                "--zip",
            ],
            cwd=tmp_root,
            capture_output=True,
            text=True,
        )
        assert package_proc.returncode == 0, package_proc.stderr
        install_root = tmp_root / "installed"
        with zipfile.ZipFile(package_dir / "yao-meta-skill.zip") as archive:
            archive.extractall(install_root)
        installed_skill = install_root / "yao-meta-skill"
        installed_cli = installed_skill / "scripts" / "yao.py"
        assert installed_cli.is_file(), installed_cli
        installed_before = file_tree_hash(installed_skill)
        installed_external = run_cli(
            "skill-report",
            str(external_skill),
            cwd=tmp_root,
            cli=installed_cli,
        )
        assert installed_external["returncode"] == 0, installed_external
        assert file_tree_hash(installed_skill) == installed_before
        installed_self = run_cli(
            "validate",
            str(installed_skill),
            cwd=tmp_root,
            cli=installed_cli,
        )
        assert installed_self["returncode"] == 2, installed_self
        assert installed_self["payload"]["error"] == "self-target-blocked", installed_self

    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

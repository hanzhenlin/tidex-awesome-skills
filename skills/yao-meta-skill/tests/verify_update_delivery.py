#!/usr/bin/env python3
"""Focused update-check and one-confirmation self-update verification."""

from __future__ import annotations

import json
import io
import shutil
import subprocess
import sys
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tests" / "tmp_update_delivery"
sys.path.insert(0, str(ROOT / "scripts"))

from check_update import (  # noqa: E402
    DEFAULT_MANIFEST_URL,
    DEFAULT_VERSION_URL,
    check_update,
    fetch_remote_version,
    is_newer,
    normalize_version,
)
from self_update import run_self_update  # noqa: E402
from update_installation import (  # noqa: E402
    build_update_plan,
    detect_installation_channels,
    execute_update_plan,
)
from yao_cli_update_commands import command_check_update, command_self_update  # noqa: E402


def write_version(root: Path, version: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")


def completed(argv: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def test_versions_and_manifest_fallback() -> None:
    assert normalize_version("v2.10.3") == (2, 10, 3)
    assert is_newer("2.0.0", "1.99.99")
    assert not is_newer("2.0.0", "2.0.0")
    assert not is_newer("1.9.9", "2.0.0")
    try:
        normalize_version("release-2")
    except ValueError as exc:
        assert "Invalid stable semantic version" in str(exc)
    else:
        raise AssertionError("Malformed semantic version was accepted.")

    def fake_fetch(url: str, _timeout: float) -> str:
        if url == DEFAULT_VERSION_URL:
            raise URLError("VERSION unavailable")
        return json.dumps({"version": "3.0.0"})

    with patch("check_update.fetch_text", side_effect=fake_fetch):
        version, source = fetch_remote_version(DEFAULT_VERSION_URL, DEFAULT_MANIFEST_URL, 0.1)
    assert version == "3.0.0"
    assert source == DEFAULT_MANIFEST_URL

    def malformed_version_fetch(url: str, _timeout: float) -> str:
        if url == DEFAULT_VERSION_URL:
            return "release-3"
        return json.dumps({"version": "3.0.0"})

    with patch("check_update.fetch_text", side_effect=malformed_version_fetch):
        version, source = fetch_remote_version(DEFAULT_VERSION_URL, DEFAULT_MANIFEST_URL, 0.1)
    assert version == "3.0.0" and source == DEFAULT_MANIFEST_URL

    malformed_root = TMP / "malformed-local"
    malformed_root.mkdir(parents=True, exist_ok=True)
    (malformed_root / "manifest.json").write_text("{broken", encoding="utf-8")
    malformed = check_update(
        root=malformed_root,
        cache_path=malformed_root / "cache.json",
        version_url=DEFAULT_VERSION_URL,
        manifest_url=DEFAULT_MANIFEST_URL,
        timeout=0.1,
        max_age_days=1,
        force=True,
        no_cache=True,
        notice=True,
        now=datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc),
    )
    assert not malformed["ok"] and malformed["notice_suppressed_error"], malformed


def check_fixture(
    case_root: Path,
    cache_path: Path,
    *,
    notice: bool,
    now: datetime,
    force: bool = False,
    no_cache: bool = False,
) -> dict:
    return check_update(
        root=case_root,
        cache_path=cache_path,
        version_url=DEFAULT_VERSION_URL,
        manifest_url=DEFAULT_MANIFEST_URL,
        timeout=0.1,
        max_age_days=1,
        force=force,
        no_cache=no_cache,
        notice=notice,
        now=now,
    )


def test_cache_notice_and_offline_degradation() -> None:
    case_root = TMP / "cache"
    write_version(case_root, "1.0.0")
    cache_path = case_root / "cache.json"
    started = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
    with (
        patch("check_update.fetch_remote_version", return_value=("1.1.0", DEFAULT_VERSION_URL)),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        first = check_fixture(case_root, cache_path, notice=True, now=started)
    assert first["ok"] and first["notify_user"] and not first["cached"], first
    assert "回复“更新”即可升级" in first["notice_text"], first

    with (
        patch("check_update.fetch_remote_version", side_effect=AssertionError("fresh cache should avoid network")),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        cached = check_fixture(case_root, cache_path, notice=True, now=started + timedelta(hours=2))
    assert cached["cached"] and not cached["notify_user"], cached

    with (
        patch("check_update.fetch_remote_version", return_value=("1.1.0", DEFAULT_VERSION_URL)),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        stale_same = check_fixture(case_root, cache_path, notice=True, now=started + timedelta(hours=25))
    assert stale_same["checked"] and not stale_same["notify_user"], stale_same

    with (
        patch("check_update.fetch_remote_version", return_value=("2.0.0", DEFAULT_VERSION_URL)),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        next_version = check_fixture(
            case_root,
            cache_path,
            notice=True,
            now=started + timedelta(hours=26),
            force=True,
        )
    assert next_version["notify_user"] and next_version["remote_version"] == "2.0.0", next_version

    with (
        patch("check_update.fetch_remote_version", side_effect=URLError("offline")),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        offline = check_fixture(
            case_root,
            case_root / "offline-cache.json",
            notice=True,
            now=started,
            force=True,
            no_cache=True,
        )
    assert not offline["ok"] and offline["notice_suppressed_error"], offline

    with (
        patch("check_update.fetch_remote_version", return_value=("release-9", DEFAULT_VERSION_URL)),
        patch("check_update._installation_snapshot", return_value={}),
    ):
        malformed = check_fixture(
            case_root,
            case_root / "bad-cache.json",
            notice=False,
            now=started,
            force=True,
            no_cache=True,
        )
    assert not malformed["ok"] and "Invalid stable semantic version" in malformed["error"], malformed


def install_skills_fixture(home: Path, *, source: str = "yaojingang/yao-meta-skill", version: str = "1.0.0") -> None:
    lock_path = home / ".agents" / ".skill-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"skills": {"yao-meta-skill": {"source": source}}}) + "\n",
        encoding="utf-8",
    )
    install = home / ".agents" / "skills" / "yao-meta-skill"
    write_version(install, version)
    (install / "SKILL.md").write_text("---\nname: yao-meta-skill\n---\n", encoding="utf-8")


def install_plugin_fixture(home: Path, version: str = "1.0.0") -> dict:
    plugin = home / "marketplaces" / "yao" / "plugins" / "yao-meta-skill"
    manifest_path = plugin / ".codex-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "name": "yao-meta-skill",
                "version": version,
                "repository": "https://github.com/yaojingang/yao-meta-skill",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "pluginId": "yao-meta-skill@yao-meta-skill",
        "name": "yao-meta-skill",
        "marketplaceName": "yao-meta-skill",
        "version": version,
        "installed": True,
        "source": {"source": "local", "path": str(plugin)},
    }


def test_installation_channels_and_safe_commands() -> None:
    skills_home = TMP / "skills-home"
    install_skills_fixture(skills_home)
    which_skills = lambda name: {"npx": "/opt/tools/npx"}.get(name)
    skills = detect_installation_channels(TMP / "plain-root", home=skills_home, which=which_skills)
    assert skills["summary"]["managed_channels"] == ["skills-cli"], skills
    skills_plan = build_update_plan(skills)
    assert skills_plan["argv"] == [
        "/opt/tools/npx", "-y", "skills", "update", "yao-meta-skill", "-g", "-y"
    ], skills_plan

    untrusted_plan = build_update_plan(
        {
            "managed": [
                {
                    "name": "skills-cli",
                    "source": "attacker/yao-meta-skill",
                    "executable": "/opt/tools/npx",
                }
            ],
            "blocked": [],
        }
    )
    assert untrusted_plan["error"] == "untrusted-source", untrusted_plan

    untrusted_home = TMP / "untrusted-home"
    install_skills_fixture(untrusted_home, source="attacker/yao-meta-skill")
    untrusted = detect_installation_channels(TMP / "plain-root", home=untrusted_home, which=which_skills)
    assert untrusted["summary"]["managed_count"] == 0, untrusted
    assert build_update_plan(untrusted)["error"] == "no-managed-channel", untrusted

    plugin_home = TMP / "plugin-home"
    plugin_item = install_plugin_fixture(plugin_home)

    def plugin_runner(argv: list[str], _cwd: Path | None) -> subprocess.CompletedProcess[str]:
        assert argv == ["/opt/tools/codex", "plugin", "list", "--json"], argv
        return completed(argv, stdout=json.dumps({"installed": [plugin_item]}))

    which_plugin = lambda name: {"codex": "/opt/tools/codex"}.get(name)
    plugin = detect_installation_channels(
        TMP / "plain-root", home=plugin_home, which=which_plugin, runner=plugin_runner
    )
    plugin_plan = build_update_plan(plugin)
    assert plugin_plan["argv"] == [
        "/opt/tools/codex", "plugin", "marketplace", "upgrade", "yao-meta-skill"
    ], plugin_plan

    multiple_home = TMP / "multiple-home"
    install_skills_fixture(multiple_home)
    multiple_item = install_plugin_fixture(multiple_home)

    def multiple_runner(argv: list[str], _cwd: Path | None) -> subprocess.CompletedProcess[str]:
        return completed(argv, stdout=json.dumps({"installed": [multiple_item]}))

    which_all = lambda name: {"npx": "/opt/tools/npx", "codex": "/opt/tools/codex"}.get(name)
    multiple = detect_installation_channels(
        TMP / "plain-root", home=multiple_home, which=which_all, runner=multiple_runner
    )
    assert build_update_plan(multiple)["error"] == "multiple-managed-channels", multiple

    dirty_root = TMP / "dirty-checkout"
    write_version(dirty_root, "1.0.0")
    (dirty_root / ".git").mkdir()

    def git_runner(argv: list[str], _cwd: Path | None) -> subprocess.CompletedProcess[str]:
        assert "--porcelain" in argv, argv
        return completed(argv, stdout=" M SKILL.md\n")

    which_git = lambda name: {"git": "/usr/bin/git"}.get(name)
    dirty = detect_installation_channels(dirty_root, home=TMP / "empty-home", which=which_git, runner=git_runner)
    checkout = next(item for item in dirty["blocked"] if item["name"] == "development-checkout")
    assert checkout["dirty"] is True, dirty
    assert build_update_plan(dirty)["error"] == "development-checkout", dirty

    copied_root = TMP / "copied-skill"
    write_version(copied_root, "1.0.0")
    (copied_root / "SKILL.md").write_text("---\nname: yao-meta-skill\n---\n", encoding="utf-8")
    copied = detect_installation_channels(copied_root, home=TMP / "copy-home", which=lambda _name: None)
    assert build_update_plan(copied)["error"] == "unmanaged-source-copy", copied


def test_confirmation_execution_and_post_verification() -> None:
    update = {
        "ok": True,
        "local_version": "1.0.0",
        "remote_version": "1.1.0",
        "update_available": True,
        "source": DEFAULT_VERSION_URL,
    }
    before = {
        "managed": [{"name": "skills-cli", "version": "1.0.0", "source": "yaojingang/yao-meta-skill", "executable": "/opt/tools/npx"}],
        "blocked": [],
        "warnings": [],
    }
    after = {
        "managed": [{"name": "skills-cli", "version": "1.1.0", "source": "yaojingang/yao-meta-skill", "executable": "/opt/tools/npx"}],
        "blocked": [],
        "warnings": [],
    }
    calls = {"detect": 0, "execute": 0}

    def detector(_root: Path) -> dict:
        calls["detect"] += 1
        return before if calls["detect"] == 1 else after

    def executor(plan: dict) -> dict:
        calls["execute"] += 1
        assert isinstance(plan["argv"], list) and plan["argv"][0] == "/opt/tools/npx", plan
        return {"ok": True, "returncode": 0, "stdout": "updated", "stderr": ""}

    dry_run = run_self_update(
        root=TMP / "plain-root", yes=False, timeout=0.1, update_result=update, detector=detector, executor=executor
    )
    assert dry_run["status"] == "confirmation-required" and calls["execute"] == 0, dry_run

    calls["detect"] = 0
    applied = run_self_update(
        root=TMP / "plain-root", yes=True, timeout=0.1, update_result=update, detector=detector, executor=executor
    )
    assert applied["status"] == "updated" and applied["restart_required"], applied
    assert calls["execute"] == 1 and applied["installed_version"] == "1.1.0", applied

    blocked = run_self_update(
        root=TMP / "plain-root",
        yes=True,
        timeout=0.1,
        update_result=update,
        detector=lambda _root: {"managed": [], "blocked": [{"name": "development-checkout"}]},
        executor=executor,
    )
    assert blocked["status"] == "blocked" and blocked["stage"] == "plan", blocked

    captured: list[list[str]] = []

    def argv_runner(argv: list[str], _cwd: Path | None) -> subprocess.CompletedProcess[str]:
        captured.append(argv)
        return completed(argv)

    outcome = execute_update_plan(build_update_plan(before), runner=argv_runner)
    assert outcome["ok"] and captured == [build_update_plan(before)["argv"]], captured

    crafted = {
        "ok": True,
        "channel": "skills-cli",
        "source": "yaojingang/yao-meta-skill",
        "argv": ["/bin/sh", "-c", "touch", "/tmp/unsafe", "-g", "-y"],
    }
    rejected = execute_update_plan(crafted, runner=argv_runner)
    assert not rejected["ok"] and len(captured) == 1, rejected

    failed = run_self_update(
        root=TMP / "plain-root",
        yes=True,
        timeout=0.1,
        update_result=update,
        detector=lambda _root: before,
        executor=lambda _plan: {"ok": False, "returncode": 9, "stdout": "", "stderr": "network down"},
    )
    assert failed["status"] == "update-failed" and failed["stage"] == "execute", failed


def test_cli_stream_contract() -> None:
    notice_text = "发现 Yao Meta Skill 1.0.0 → 1.1.0，回复“更新”即可升级；当前任务可以继续。"
    args = Namespace(
        force=False,
        no_cache=False,
        notice=True,
        version_url=None,
        manifest_url=None,
        timeout=3.0,
        max_age_days=1,
        allow_custom_update_url=False,
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch(
            "yao_cli_update_commands.run_script",
            return_value={
                "ok": True,
                "payload": {"ok": True, "notify_user": True, "notice_text": notice_text},
            },
        ),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        assert command_check_update(args) == 0
    assert json.loads(stdout.getvalue())["notify_user"] is True
    assert stderr.getvalue().strip() == notice_text

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch(
            "yao_cli_update_commands.run_script",
            return_value={
                "ok": True,
                "payload": {"ok": True, "status": "updated", "restart_message": "Restart Codex."},
            },
        ),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        assert command_self_update(Namespace(yes=True, timeout=3.0)) == 0
    assert json.loads(stdout.getvalue())["status"] == "updated"
    assert stderr.getvalue().strip() == "Restart Codex."


def main() -> None:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    test_versions_and_manifest_fallback()
    test_cache_notice_and_offline_degradation()
    test_installation_channels_and_safe_commands()
    test_confirmation_execution_and_post_verification()
    test_cli_stream_contract()
    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

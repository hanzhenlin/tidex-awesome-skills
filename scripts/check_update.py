#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tidex Update Checker - 零阻塞、低开销、带 24 小时缓存的自动更新检查器。

核心设计规范：
1. 24 小时本地缓存节流（同一天内秒级读缓存，零网络开销）
2. 极短超时与静默兜底（超时 2.5s，断网或失败完全静默，绝不阻塞用户主任务）
3. 单一版本只提醒一次（notified_version 避免重复骚扰）
4. 缓存数据严格收敛于 ~/.tidex/<project>/cache/update-check.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_semver(v_str: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(v_str.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {v_str}")
    return tuple(int(x) for x in match.groups())


def is_newer(remote: str, local: str) -> bool:
    try:
        return parse_semver(remote) > parse_semver(local)
    except ValueError:
        return False


def get_cache_path(project_name: str) -> Path:
    return Path.home() / ".tidex" / project_name / "cache" / "update-check.json"


def load_local_version(root_dir: Path) -> str:
    version_file = root_dir / "VERSION"
    if version_file.is_file():
        try:
            val = version_file.read_text(encoding="utf-8").strip()
            if val:
                return val
        except OSError:
            pass
    return "1.0.0"


def fetch_remote_version(repo: str, timeout: float = 2.5) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/main/VERSION"
    req = Request(url, headers={"User-Agent": "tidex-update-checker"})
    with urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8").strip()
        lines = content.splitlines()
        if lines:
            candidate = lines[0].strip()
            parse_semver(candidate)
            return candidate
    raise ValueError("Empty or invalid remote VERSION")


def read_cache(cache_path: Path) -> dict:
    if not cache_path.is_file():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_cache(cache_path: Path, data: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        pass


def check_update(
    project_name: str = "tidex-agent-skills",
    repo: str = "hanzhenlin/tidex-agent-skills",
    root_dir: Optional[Path] = None,
    timeout: float = 2.5,
    max_age_hours: int = 24,
    force: bool = False,
    notice: bool = True,
) -> dict:
    """执行更新检查，返回检查结果字典。绝不抛出未捕获异常。"""
    if root_dir is None:
        root_dir = Path(__file__).resolve().parent.parent

    local_ver = load_local_version(root_dir)
    cache_path = get_cache_path(project_name)
    now_utc = datetime.now(timezone.utc)
    cache = read_cache(cache_path)

    # 检查缓存新鲜度
    cached_at_str = cache.get("checked_at")
    cache_fresh = False
    if not force and cached_at_str:
        try:
            cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
            if now_utc - cached_at < timedelta(hours=max_age_hours):
                cache_fresh = True
        except Exception:
            cache_fresh = False

    remote_ver = None
    update_available = False
    err_msg = None

    if cache_fresh:
        remote_ver = cache.get("remote_version")
        if remote_ver:
            update_available = is_newer(remote_ver, local_ver)
    else:
        # 联网探测
        try:
            remote_ver = fetch_remote_version(repo, timeout=timeout)
            update_available = is_newer(remote_ver, local_ver)
        except Exception as e:
            err_msg = str(e)
            # 联网失败时沿用上次缓存的远端版本（如果有）
            remote_ver = cache.get("remote_version")
            if remote_ver:
                update_available = is_newer(remote_ver, local_ver)

        # 更新缓存
        cache["checked_at"] = now_utc.isoformat().replace("+00:00", "Z")
        cache["local_version"] = local_ver
        if remote_ver:
            cache["remote_version"] = remote_ver
        if err_msg:
            cache["last_error"] = err_msg
        write_cache(cache_path, cache)

    # 判断是否需要通知用户（同一版本只通知一次）
    notice_text = ""
    notify_user = False
    if notice and update_available and remote_ver:
        if cache.get("notified_version") != remote_ver:
            notify_user = True
            notice_text = (
                f"💡 [Tidex 升级提示] 发现 {project_name} 新版本 v{local_ver} → v{remote_ver}\n"
                f"   可运行: bash install.sh 一键更新；当前任务不受影响，继续执行中..."
            )
            # 记录已提醒版本
            cache["notified_version"] = remote_ver
            cache["notified_at"] = now_utc.isoformat().replace("+00:00", "Z")
            write_cache(cache_path, cache)

    return {
        "ok": err_msg is None,
        "local_version": local_ver,
        "remote_version": remote_ver,
        "update_available": update_available,
        "notify_user": notify_user,
        "notice_text": notice_text,
        "cached": cache_fresh,
        "error": err_msg,
    }


def check_update_silent(
    project_name: str = "tidex-agent-skills",
    repo: str = "hanzhenlin/tidex-agent-skills",
    root_dir: Optional[Path] = None,
) -> Optional[str]:
    """供业务脚本调用的极简入口，发现新版本且未提醒过时返回提示文案，否则返回 None。"""
    try:
        res = check_update(
            project_name=project_name,
            repo=repo,
            root_dir=root_dir,
            timeout=2.0,
            notice=True,
        )
        if res.get("notify_user") and res.get("notice_text"):
            return res["notice_text"]
    except Exception:
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Tidex 自动更新检查工具")
    parser.add_argument("--project", default="tidex-agent-skills", help="项目名称")
    parser.add_argument("--repo", default="hanzhenlin/tidex-agent-skills", help="GitHub 仓库名")
    parser.add_argument("--force", action="store_true", help="强制忽略缓存联网检查")
    parser.add_argument("--notice", action="store_true", default=True, help="是否生成提醒文案")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    res = check_update(
        project_name=args.project,
        repo=args.repo,
        force=args.force,
        notice=args.notice,
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("update_available"):
        print(
            f"[!] 发现新版本: v{res['local_version']} -> v{res['remote_version']} (可运行 bash install.sh 升级)"
        )
    else:
        print(f"[✓] 当前已是最新版本 (v{res['local_version']})")


if __name__ == "__main__":
    main()

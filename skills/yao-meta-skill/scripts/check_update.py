#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from yao_runtime_paths import default_cache_dir


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERSION_URL = "https://raw.githubusercontent.com/yaojingang/yao-meta-skill/main/VERSION"
DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/yaojingang/yao-meta-skill/main/manifest.json"
CACHE_DIR = default_cache_dir()
CACHE_PATH = CACHE_DIR / "update-check.json"
ALLOWED_UPDATE_HOST = "raw.githubusercontent.com"
ALLOWED_UPDATE_PATH_PREFIX = "/yaojingang/yao-meta-skill/"
UPDATE_DETAILS_URL = "https://github.com/yaojingang/yao-meta-skill/commits/main"
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def load_local_version(root: Path) -> str:
    version_file = root / "VERSION"
    if version_file.is_file():
        try:
            value = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        if value:
            try:
                normalize_version(value)
            except ValueError:
                pass
            else:
                return value
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if isinstance(payload, dict):
            version = str(payload.get("version", "")).strip()
            if version:
                try:
                    normalize_version(version)
                except ValueError:
                    return ""
                return version
    return ""


def normalize_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid stable semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())


def is_newer(remote: str, local: str) -> bool:
    return normalize_version(remote) > normalize_version(local)


def fetch_text(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "yao-meta-skill-update-check"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8").strip()


def validate_update_url(url: str, allow_custom: bool) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Update URL scheme is not allowed: {parsed.scheme or 'missing'}")
    is_default_source = (
        parsed.netloc == ALLOWED_UPDATE_HOST
        and parsed.path.startswith(ALLOWED_UPDATE_PATH_PREFIX)
    )
    if not is_default_source and not allow_custom:
        raise ValueError("Custom update URLs require --allow-custom-update-url.")


def validate_update_urls(version_url: str, manifest_url: str, allow_custom: bool) -> None:
    validate_update_url(version_url, allow_custom)
    validate_update_url(manifest_url, allow_custom)


def fetch_remote_version(version_url: str, manifest_url: str, timeout: float) -> tuple[str, str]:
    try:
        value = fetch_text(version_url, timeout)
        if value:
            candidate = value.splitlines()[0].strip()
            normalize_version(candidate)
            return candidate, version_url
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        pass
    manifest_text = fetch_text(manifest_url, timeout)
    payload = json.loads(manifest_text)
    version = str(payload.get("version", "")).strip()
    if not version:
        raise ValueError("Remote manifest does not contain a version.")
    return version, manifest_url


def read_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_checked_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def cache_is_fresh(
    cache: dict,
    *,
    local_version: str,
    max_age_days: int,
    now: datetime,
) -> bool:
    checked_at = _parse_checked_at(cache.get("checked_at"))
    if checked_at is None or cache.get("local_version") != local_version:
        return False
    age = now - checked_at
    return timedelta(0) <= age < timedelta(days=max_age_days)


def build_result(
    local_version: str,
    remote_version: str | None,
    source: str | None,
    checked: bool,
    skipped: bool = False,
    error: str | None = None,
) -> dict:
    update_available = False
    if error is None and remote_version:
        try:
            update_available = is_newer(remote_version, local_version)
        except ValueError as exc:
            error = str(exc)
    return {
        "ok": error is None,
        "checked": checked,
        "skipped": skipped,
        "local_version": local_version,
        "remote_version": remote_version,
        "update_available": update_available,
        "source": source,
        "notify_user": False,
        "notice_text": "",
        "update_details_url": UPDATE_DETAILS_URL if update_available else "",
        "install_channels": [],
        "installation": {},
        "suggested_action": "reply-update" if update_available else "none",
        "install_hint": (
            "python3 scripts/yao.py self-update --self --yes" if update_available else ""
        ),
        "error": error,
    }


def _installation_snapshot(root: Path, update_available: bool) -> dict:
    if not update_available:
        return {}
    try:
        from update_installation import detect_installation_channels

        return detect_installation_channels(root)
    except Exception as exc:  # noqa: BLE001 - installation hints must not break update checks.
        return {
            "managed": [],
            "blocked": [],
            "warnings": [f"Installation detection failed: {exc}"],
        }


def _cache_payload(
    *,
    checked_at: str,
    local_version: str,
    result: dict,
    previous: dict,
) -> dict:
    payload = {
        "checked_at": checked_at,
        "local_version": local_version,
        "remote_version": result.get("remote_version"),
        "source": result.get("source"),
        "error": result.get("error"),
    }
    if previous.get("notified_version"):
        payload["notified_version"] = previous["notified_version"]
    if previous.get("notified_at"):
        payload["notified_at"] = previous["notified_at"]
    return payload


def check_update(
    root: Path,
    cache_path: Path,
    version_url: str,
    manifest_url: str,
    timeout: float,
    max_age_days: int,
    force: bool,
    no_cache: bool,
    allow_custom_url: bool = False,
    notice: bool = False,
    now: datetime | None = None,
) -> dict:
    if max_age_days < 0:
        raise ValueError("max_age_days must be zero or greater.")
    local_version = load_local_version(root)
    checked_now = _utc_now(now)
    cache = {} if no_cache else read_cache(cache_path)
    use_cache = (
        not force
        and not no_cache
        and cache_is_fresh(
            cache,
            local_version=local_version,
            max_age_days=max_age_days,
            now=checked_now,
        )
    )
    if use_cache:
        result = build_result(
            local_version=local_version,
            remote_version=cache.get("remote_version"),
            source=cache.get("source"),
            checked=False,
            skipped=True,
            error=cache.get("error"),
        )
        checked_at = str(cache.get("checked_at"))
    else:
        try:
            validate_update_urls(version_url, manifest_url, allow_custom_url)
            normalize_version(local_version)
            remote_version, source = fetch_remote_version(version_url, manifest_url, timeout)
            normalize_version(remote_version)
            result = build_result(local_version, remote_version, source, checked=True)
        except Exception as exc:  # noqa: BLE001 - update checks should never break authoring.
            result = build_result(local_version, None, None, checked=True, error=str(exc))
        checked_at = checked_now.isoformat().replace("+00:00", "Z")

    cache_payload = _cache_payload(
        checked_at=checked_at,
        local_version=local_version,
        result=result,
        previous=cache,
    )
    remote_version = result.get("remote_version")
    notify_user = bool(
        notice
        and result.get("update_available")
        and remote_version
        and cache.get("notified_version") != remote_version
    )
    if notify_user:
        cache_payload["notified_version"] = remote_version
        cache_payload["notified_at"] = checked_now.isoformat().replace("+00:00", "Z")
        result["notify_user"] = True
        result["notice_text"] = (
            f"发现 Yao Meta Skill {local_version} → {remote_version}，"
            "回复“更新”即可升级；当前任务可以继续。"
        )

    installation = _installation_snapshot(root, bool(result.get("update_available")))
    result["installation"] = installation
    result["install_channels"] = [
        str(item.get("name")) for item in installation.get("managed", []) if item.get("name")
    ]
    if not no_cache:
        write_cache(cache_path, cache_payload)
    result["cached"] = use_cache
    result["checked_at"] = checked_at
    result["max_age_days"] = max_age_days
    result["notice_mode"] = notice
    result["notice_suppressed_error"] = bool(notice and result.get("error"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether yao-meta-skill has a newer GitHub version.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--cache-path", default=str(CACHE_PATH))
    parser.add_argument("--version-url", default=os.environ.get("YAO_UPDATE_VERSION_URL", DEFAULT_VERSION_URL))
    parser.add_argument("--manifest-url", default=os.environ.get("YAO_UPDATE_MANIFEST_URL", DEFAULT_MANIFEST_URL))
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--notice", action="store_true", help="Return a once-per-version activation notice.")
    parser.add_argument(
        "--allow-custom-update-url",
        action="store_true",
        default=os.environ.get("YAO_ALLOW_CUSTOM_UPDATE_URL") == "1",
        help="Allow custom HTTPS update URLs. file:// and non-HTTPS schemes are always blocked.",
    )
    args = parser.parse_args()
    result = check_update(
        root=Path(args.root).resolve(),
        cache_path=Path(args.cache_path).resolve(),
        version_url=args.version_url,
        manifest_url=args.manifest_url,
        timeout=args.timeout,
        max_age_days=args.max_age_days,
        force=args.force,
        no_cache=args.no_cache,
        allow_custom_url=args.allow_custom_update_url,
        notice=args.notice,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] or args.notice else 2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from simulate_install import simulate_install


ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "yao-meta-skill"
SENTINEL_NAME = ".yao-local-install.json"
DEFAULT_INSTALL_DIR = Path.home() / ".agents" / "skills.disabled" / SKILL_NAME
ACTIVE_INSTALL_DIR = Path.home() / ".agents" / "skills" / SKILL_NAME
DEFAULT_PACKAGE_DIR = ROOT / "dist"
DEFAULT_VERIFICATION_JSON = ROOT / "reports" / "package_verification.json"
ALLOW_UNTRACKED_PREFIXES = {
    ".github",
    "agents",
    "docs",
    "evals",
    "failures",
    "references",
    "scripts",
    "templates",
    "tests",
}
ALLOW_UNTRACKED_ROOT_FILES = {
    ".gitignore",
    "LICENSE",
    "Makefile",
    "README.md",
    "SKILL.md",
    "VERSION",
    "manifest.json",
    "requirements-ci.txt",
}
PROTECTED_INSTALL_PREFIXES = {".git"}
LOCAL_ONLY_PATHS = {
    Path("reports/.current-run.json"),
    Path("reports/artifact-index.json"),
}


def git_files(root: Path, *args: str) -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", *args],
        cwd=root,
        capture_output=True,
        check=True,
    )
    raw = proc.stdout.decode("utf-8")
    return [Path(item) for item in raw.split("\0") if item]


def allow_untracked(path: Path) -> bool:
    parts = path.parts
    if len(parts) == 1:
        return path.name in ALLOW_UNTRACKED_ROOT_FILES
    return parts[0] in ALLOW_UNTRACKED_PREFIXES


def candidate_files(root: Path) -> tuple[list[Path], list[Path]]:
    tracked = set(git_files(root)) - LOCAL_ONLY_PATHS
    untracked = set(git_files(root, "--others", "--exclude-standard"))
    allowed_untracked = {path for path in untracked if allow_untracked(path)}
    skipped_untracked = sorted(untracked - allowed_untracked)
    return sorted(tracked | allowed_untracked), skipped_untracked


def resolve_install_dir(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def read_frontmatter_name(skill_md: Path) -> str:
    if not skill_md.exists():
        return ""
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    return ""


def load_sentinel(install_dir: Path) -> dict:
    sentinel = install_dir / SENTINEL_NAME
    if not sentinel.exists():
        return {}
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid install sentinel: {sentinel}")
    if payload.get("skill_name") != SKILL_NAME:
        raise ValueError(f"Install sentinel is not for {SKILL_NAME}: {sentinel}")
    return payload


def validate_install_dir(root: Path, install_dir: Path) -> None:
    home = Path.home().resolve()
    filesystem_root = Path(install_dir.anchor).resolve()
    dangerous_exact = {
        filesystem_root,
        home,
        home / ".agents",
        home / ".agents" / "skills",
        root,
        root.parent,
    }
    if install_dir in dangerous_exact:
        raise ValueError(f"Refusing dangerous install directory: {install_dir}")
    if install_dir.is_symlink():
        raise ValueError(f"Refusing symlink install directory: {install_dir}")
    if not install_dir.exists():
        return
    sentinel = load_sentinel(install_dir)
    if sentinel:
        return
    if read_frontmatter_name(install_dir / "SKILL.md") == SKILL_NAME:
        return
    if install_dir in {DEFAULT_INSTALL_DIR.resolve(), ACTIVE_INSTALL_DIR.resolve()} and not any(install_dir.iterdir()):
        return
    raise ValueError(
        f"Refusing to sync into a directory that is not a managed {SKILL_NAME} install: {install_dir}"
    )


def write_sentinel(root: Path, install_dir: Path, dry_run: bool) -> None:
    if dry_run:
        return
    payload = {
        "managed_by": "yao-meta-skill sync_local_install.py",
        "skill_name": SKILL_NAME,
        "source_root": str(root),
    }
    (install_dir / SENTINEL_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_preflight(root: Path, package_dir: Path, generated_at: str) -> dict:
    package_dir = package_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="yao-local-install-preflight-") as temp_dir:
        report = simulate_install(root, package_dir, Path(temp_dir), generated_at)
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    permission_failures = int(summary.get("installer_permission_failure_count", 0) or 0)
    if not report.get("ok") or permission_failures:
        failure_preview = "; ".join(str(item) for item in report.get("failures", [])[:3])
        if permission_failures and not failure_preview:
            failure_preview = f"{permission_failures} installer permission failures"
        raise ValueError(f"Install preflight failed for {package_dir}: {failure_preview or 'unknown failure'}")
    return {
        "ok": True,
        "package_dir": str(package_dir),
        "archive_extracted": bool(summary.get("archive_extracted")),
        "adapter_count": int(summary.get("adapter_count", 0) or 0),
        "installer_permission_enforced_count": int(summary.get("installer_permission_enforced_count", 0) or 0),
        "installer_permission_failure_count": permission_failures,
        "permission_target_count": int(summary.get("permission_target_count", 0) or 0),
        "permission_capability_count": int(summary.get("permission_capability_count", 0) or 0),
        "failure_count": int(summary.get("failure_count", 0) or 0),
        "warning_count": int(summary.get("warning_count", 0) or 0),
    }


def verify_archive_attestation(package_dir: Path, verification_json: Path) -> dict:
    archive_path = package_dir / f"{SKILL_NAME}.zip"
    if not archive_path.is_file():
        raise ValueError(f"Verified install archive is missing: {archive_path}")
    if not verification_json.is_file():
        raise ValueError(f"Package verification report is missing: {verification_json}")
    try:
        report = json.loads(verification_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Package verification report is invalid JSON: {verification_json}") from exc
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    expected_sha256 = str(summary.get("archive_sha256") or "")
    actual_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if report.get("ok") is not True or int(summary.get("failure_count", 1) or 0) != 0:
        raise ValueError(f"Package verification report is not passing: {verification_json}")
    if expected_sha256 != actual_sha256:
        raise ValueError(
            "Install archive hash does not match package verification report: "
            f"expected {expected_sha256 or 'missing'}, actual {actual_sha256}"
        )
    return {
        "ok": True,
        "verification_json": str(verification_json),
        "archive_sha256": actual_sha256,
    }


def remove_stale_files(install_dir: Path, desired_files: set[Path], dry_run: bool) -> list[str]:
    removed = []
    if not install_dir.exists():
        return removed
    for path in sorted(install_dir.rglob("*"), reverse=True):
        rel = path.relative_to(install_dir)
        if rel.parts and rel.parts[0] in PROTECTED_INSTALL_PREFIXES:
            continue
        if path.is_dir():
            continue
        if rel not in desired_files:
            removed.append(str(rel))
            if not dry_run:
                path.unlink()
    for path in sorted((item for item in install_dir.rglob("*") if item.is_dir()), reverse=True):
        rel = path.relative_to(install_dir)
        if rel.parts and rel.parts[0] in PROTECTED_INSTALL_PREFIXES:
            continue
        try:
            if not dry_run:
                path.rmdir()
        except OSError:
            pass
    return removed


def copy_files(root: Path, install_dir: Path, files: list[Path], dry_run: bool) -> tuple[list[str], list[str]]:
    copied = []
    skipped = []
    for rel in files:
        source = root / rel
        target = install_dir / rel
        if source.is_symlink() or not source.is_file():
            skipped.append(str(rel))
            continue
        copied.append(str(rel))
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return copied, skipped


def extract_archive_source(package_dir: Path, destination: Path) -> tuple[Path, list[Path]]:
    archive_path = package_dir / f"{SKILL_NAME}.zip"
    if not archive_path.is_file():
        raise ValueError(f"Verified install archive is missing: {archive_path}")
    package_root = destination / SKILL_NAME
    files: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != SKILL_NAME:
                raise ValueError(f"Unsafe install archive member: {info.filename}")
            mode = info.external_attr >> 16
            if mode & 0o170000 == 0o120000:
                raise ValueError(f"Symlink install archive member is forbidden: {info.filename}")
            relative = Path(*path.parts[1:])
            if not relative.parts or info.is_dir():
                continue
            target = package_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            files.append(relative)
    return package_root, sorted(files)


def sync_local_install(
    root: Path,
    install_dir: Path,
    dry_run: bool = False,
    package_dir: Path | None = None,
    verification_json: Path | None = None,
    generated_at: str | None = None,
    skip_install_preflight: bool = False,
) -> dict:
    root = root.resolve()
    install_dir = install_dir.resolve()
    validate_install_dir(root, install_dir)
    resolved_package_dir = (package_dir or DEFAULT_PACKAGE_DIR).resolve()
    resolved_verification_json = (verification_json or DEFAULT_VERIFICATION_JSON).resolve()
    archive_attestation = verify_archive_attestation(resolved_package_dir, resolved_verification_json)
    preflight = {"ok": True, "skipped": True}
    if not skip_install_preflight:
        preflight = install_preflight(root, resolved_package_dir, generated_at or str(date.today()))
    _, skipped_untracked = candidate_files(root)
    with tempfile.TemporaryDirectory(prefix="yao-local-install-archive-") as temp_dir:
        archive_root, files = extract_archive_source(resolved_package_dir, Path(temp_dir))
        desired_files = set(files)
        desired_files.add(Path(SENTINEL_NAME))
        removed = remove_stale_files(install_dir, desired_files, dry_run)
        if not dry_run:
            install_dir.mkdir(parents=True, exist_ok=True)
        copied, skipped_sources = copy_files(archive_root, install_dir, files, dry_run)
    write_sentinel(root, install_dir, dry_run)
    return {
        "ok": True,
        "root": str(root),
        "install_dir": str(install_dir),
        "dry_run": dry_run,
        "copied_count": len(copied),
        "removed_count": len(removed),
        "skipped_source_count": len(skipped_sources),
        "skipped_untracked_count": len(skipped_untracked),
        "install_preflight": preflight,
        "archive_attestation": archive_attestation,
        "install_source": "verified-archive",
        "copied_samples": copied[:10],
        "removed_samples": removed[:10],
        "skipped_source_samples": skipped_sources[:10],
        "skipped_untracked_samples": [str(path) for path in skipped_untracked[:10]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync the current yao-meta-skill source into a managed local skill mirror.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--install-dir", default=str(DEFAULT_INSTALL_DIR))
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--verification-json", default=str(DEFAULT_VERIFICATION_JSON))
    parser.add_argument("--generated-at", default=str(date.today()))
    parser.add_argument("--skip-install-preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    package_dir = Path(args.package_dir)
    if not package_dir.is_absolute():
        package_dir = root / package_dir
    verification_json = Path(args.verification_json)
    if not verification_json.is_absolute():
        verification_json = root / verification_json
    try:
        result = sync_local_install(
            root,
            resolve_install_dir(args.install_dir),
            dry_run=args.dry_run,
            package_dir=package_dir,
            verification_json=verification_json,
            generated_at=args.generated_at,
            skip_install_preflight=args.skip_install_preflight,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        result = {"ok": False, "failures": [str(exc)]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

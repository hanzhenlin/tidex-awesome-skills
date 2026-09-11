"""Governed source selection and local-noise filtering for skill archives."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by cross_packager.py to keep Git source selection and archive-noise policy separate from package assembly."

EXCLUDED_ARCHIVE_PARTS = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".previews",
    ".pytest_cache",
    ".ruff_cache",
    ".yao",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
}
EXCLUDED_LOCAL_EVIDENCE_PATHS = {
    ("reports", ".current-run.json"),
    ("reports", "artifact-index.json"),
}
UNTRACKED_SOURCE_ROOTS = {
    ".github",
    "agents",
    "assets",
    "docs",
    "evals",
    "references",
    "scripts",
    "security",
    "skill-ir",
    "tests",
}
UNTRACKED_SOURCE_FILES = {
    "AGENTS.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSE.md",
    "Makefile",
    "README.md",
    "SKILL.md",
    "VERSION",
    "manifest.json",
    "pyproject.toml",
    "requirements.txt",
}


def should_skip_archive_path(rel_path: Path) -> bool:
    parts = rel_path.parts
    if any(part in EXCLUDED_ARCHIVE_PARTS for part in parts):
        return True
    if rel_path.suffix in {".pyc", ".pyo"}:
        return True
    if parts in EXCLUDED_LOCAL_EVIDENCE_PATHS:
        return True
    if rel_path.name == "SKILL.md" and parts != ("SKILL.md",):
        return True
    if parts == ("reports", "telemetry_events.jsonl"):
        return True
    if len(parts) >= 2 and parts[:2] == ("reports", "release_snapshots"):
        return True
    if len(parts) >= 3 and parts[:3] == ("evidence", "world_class", "submissions"):
        return True
    if parts and parts[0] == "tests" and any(part.startswith("tmp") for part in parts[1:]):
        return True
    return False


def allowed_untracked_source_path(rel_path: Path) -> bool:
    if len(rel_path.parts) == 1:
        return rel_path.name in UNTRACKED_SOURCE_FILES
    return rel_path.parts[0] in UNTRACKED_SOURCE_ROOTS


def git_archive_source_paths(skill_dir: Path) -> list[Path] | None:
    """Return the governed Git-backed source set, or None outside a repo root."""

    source_root = skill_dir
    skill_dir = skill_dir.resolve()
    git_marker_present = any((candidate / ".git").exists() for candidate in (skill_dir, *skill_dir.parents))
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=skill_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        if git_marker_present:
            raise ValueError("Cannot inspect Git-backed archive sources because git is unavailable.") from exc
        return None
    if probe.returncode != 0:
        if git_marker_present:
            raise ValueError(f"Cannot inspect Git-backed archive sources: {probe.stderr.strip() or 'git rev-parse failed'}")
        return None

    repo_root = Path(probe.stdout.strip()).resolve()
    try:
        skill_prefix = skill_dir.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Skill directory is outside the detected Git repository: {skill_dir}") from exc
    pathspec = "." if skill_prefix == Path(".") else skill_prefix.as_posix()

    def listed(*args: str) -> set[Path]:
        result = subprocess.run(
            ["git", "ls-files", "-z", *args, "--", pathspec],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"Cannot enumerate Git-backed archive sources: {os.fsdecode(result.stderr).strip()}")
        paths: set[Path] = set()
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            absolute = repo_root / Path(os.fsdecode(raw))
            try:
                paths.add(absolute.relative_to(skill_dir))
            except ValueError:
                continue
        return paths

    tracked = listed("--cached")
    untracked = {path for path in listed("--others", "--exclude-standard") if allowed_untracked_source_path(path)}
    return sorted(source_root / relative for relative in tracked | untracked)


def archive_source_paths(skill_dir: Path) -> list[Path]:
    governed = git_archive_source_paths(skill_dir)
    return governed if governed is not None else sorted(skill_dir.rglob("*"))

#!/usr/bin/env python3
"""Resolve official report reads through the current evidence collection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from evidence_store import (
    CANONICAL_INDEX_PATH,
    POINTER_PATH,
    EvidenceError,
    read_json,
    sha256_file,
)


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by reports, Review Studio, and evidence gates to resolve the published evidence collection."


def _safe_relative(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise EvidenceError("unsafe-evidence-path", f"Unsafe evidence path: {value}")
    return relative


def _assert_safe_candidate(path: Path, boundary: Path) -> None:
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise EvidenceError("unsafe-evidence-path", f"Evidence path escapes its boundary: {path}") from exc
    cursor = boundary
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise EvidenceError("unsafe-evidence-path", f"Evidence path traverses a symlink: {path}")
    try:
        path.resolve(strict=False).relative_to(boundary.resolve())
    except ValueError as exc:
        raise EvidenceError("unsafe-evidence-path", f"Evidence path escapes its boundary: {path}") from exc


def _authoring_candidate_active(root: Path) -> bool:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return status.returncode == 0 and bool(status.stdout.strip())


def resolve_evidence_path(skill_dir: Path | str, relative_path: str | Path) -> Path:
    root = Path(skill_dir).resolve()
    relative = _safe_relative(Path(relative_path).as_posix())
    if not relative.parts or relative.parts[0] != "reports":
        raise EvidenceError("unsafe-evidence-path", f"Published evidence must stay under reports/: {relative}")
    canonical = root / relative
    _assert_safe_candidate(canonical, root)
    pointer_path = root / POINTER_PATH
    if not pointer_path.exists():
        return canonical
    if _authoring_candidate_active(root) and canonical.is_file():
        return canonical
    pointer = read_json(pointer_path, code="invalid-current-run")
    index_path = root / CANONICAL_INDEX_PATH
    index = read_json(index_path, code="invalid-artifact-index")
    expected_index_hash = pointer.get("artifact_index_sha256")
    if expected_index_hash and sha256_file(index_path) != expected_index_hash:
        raise EvidenceError("artifact-index-hash-mismatch", "Canonical artifact index does not match the current run")
    entries = {
        str(entry.get("path")): entry
        for entry in index.get("artifacts", [])
        if isinstance(entry, dict) and entry.get("path")
    }
    entry = entries.get(relative.as_posix())
    if entry is None:
        raise EvidenceError("artifact-not-published", f"Artifact is outside the current evidence collection: {relative}")
    if pointer.get("mode") == "portable":
        if pointer.get("artifact_index") != CANONICAL_INDEX_PATH.as_posix():
            raise EvidenceError("invalid-current-run", "Portable evidence pointer names an unexpected artifact index")
        candidate = canonical
        if not candidate.is_file():
            raise EvidenceError("artifact-missing", f"Portable evidence artifact is missing: {relative}")
        if sha256_file(candidate) != entry.get("sha256"):
            raise EvidenceError("artifact-hash-mismatch", f"Portable evidence artifact hash mismatch: {relative}")
        return candidate
    release_relative = _safe_relative(str(pointer.get("release_dir", "")))
    if len(release_relative.parts) != 3 or release_relative.parts[:2] != (".yao", "releases"):
        raise EvidenceError("unsafe-evidence-path", f"Current release pointer is outside .yao/releases: {release_relative}")
    release_root = root / release_relative
    _assert_safe_candidate(release_root, root)
    _assert_safe_candidate(release_root, root / ".yao" / "releases")
    release_candidate = root / release_relative / "artifacts" / relative
    _assert_safe_candidate(release_candidate, release_root / "artifacts")
    candidate = release_candidate if release_candidate.is_file() else canonical
    if not candidate.is_file():
        raise EvidenceError("artifact-missing", f"Published artifact is missing: {relative}")
    if sha256_file(candidate) != entry.get("sha256"):
        raise EvidenceError("artifact-hash-mismatch", f"Published artifact hash mismatch: {relative}")
    return candidate


def resolve_report_path(path: Path) -> Path:
    resolved = path.resolve(strict=False)
    for parent in [path.parent, *path.parents]:
        if parent.name == "reports":
            skill_dir = parent.parent
            if (skill_dir / POINTER_PATH).exists():
                return resolve_evidence_path(skill_dir, path.relative_to(skill_dir))
            break
    return resolved


def load_evidence_json(skill_dir: Path | str, relative_path: str | Path) -> dict[str, Any]:
    path = resolve_evidence_path(skill_dir, relative_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid-evidence-json", f"Cannot load evidence JSON {relative_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("invalid-evidence-json", f"Evidence JSON root must be an object: {relative_path}")
    return payload

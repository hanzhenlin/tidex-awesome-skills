"""Safety policy for replacing generated cross-packager output directories."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by cross_packager.py to validate generated output ownership before recursive replacement."


def _stream_sha256(reader) -> str:
    digest = hashlib.sha256()
    while chunk := reader.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_output_dir(skill_dir: Path, requested_output_dir: Path, cwd: Path) -> Path:
    skill_dir = skill_dir.resolve()
    cwd = cwd.resolve()
    requested_output_dir = requested_output_dir.expanduser()
    candidate = requested_output_dir if requested_output_dir.is_absolute() else cwd / requested_output_dir
    if candidate.is_symlink():
        raise ValueError(f"Refusing symlink output directory: {candidate}")
    out_dir = candidate.resolve()
    home = Path.home().resolve()
    filesystem_root = Path(out_dir.anchor).resolve()

    dangerous_exact = {filesystem_root, home, cwd, skill_dir, skill_dir.parent.resolve()}
    if out_dir in dangerous_exact or out_dir in skill_dir.parents:
        raise ValueError(f"Refusing dangerous output directory: {out_dir}")
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"Output path exists but is not a directory: {out_dir}")
    if not (is_relative_to(out_dir, cwd) or is_relative_to(out_dir, skill_dir)):
        raise ValueError(f"Output directory must stay under the current workspace or skill directory: {out_dir}")
    return out_dir


def _managed_output_paths(package_name: str, platform_names: set[str]) -> set[Path]:
    files = {Path("manifest.json"), Path(f"{package_name}.zip")}
    for platform in platform_names:
        files.add(Path("targets") / platform / "adapter.json")
    files.update(
        {
            Path("targets/openai/agents/openai.yaml"),
            Path("targets/claude/README.md"),
            Path("targets/vscode/README.md"),
        }
    )
    paths = set(files)
    for path in files:
        paths.update(parent for parent in path.parents if parent != Path("."))
    return paths


def _verified_install_simulation_paths(out_dir: Path, package_name: str) -> set[Path]:
    """Return paths for an exact extraction of the existing generated archive."""

    simulation_root = out_dir / "install-simulation"
    if not simulation_root.exists():
        return set()
    if simulation_root.is_symlink() or not simulation_root.is_dir():
        raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)")

    archive_path = out_dir / f"{package_name}.zip"
    installed_root = simulation_root / f"simulate-{package_name}" / package_name
    if archive_path.is_symlink() or not archive_path.is_file() or not installed_root.is_dir():
        raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            archive_files: dict[Path, tuple[int, str]] = {}
            for info in archive.infolist():
                member = Path(info.filename)
                if info.is_dir():
                    continue
                if member.is_absolute() or ".." in member.parts or not member.parts or member.parts[0] != package_name:
                    raise ValueError("unsafe archive member")
                relative = Path(*member.parts[1:])
                if not relative.parts:
                    raise ValueError("invalid archive member")
                if relative in archive_files:
                    raise ValueError("duplicate archive member")
                with archive.open(info) as reader:
                    archive_files[relative] = (info.file_size, _stream_sha256(reader))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)") from exc

    installed_files: dict[Path, Path] = {}
    for path in simulation_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)")
        if path.is_file():
            try:
                relative = path.relative_to(installed_root)
            except ValueError as exc:
                raise ValueError(
                    f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)"
                ) from exc
            installed_files[relative] = path
    if set(installed_files) != set(archive_files):
        raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)")
    for relative, path in installed_files.items():
        try:
            archive_size, archive_sha256 = archive_files[relative]
            with path.open("rb") as reader:
                installed_sha256 = _stream_sha256(reader)
            if path.stat().st_size != archive_size or installed_sha256 != archive_sha256:
                raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)")
        except OSError as exc:
            raise ValueError(
                f"Refusing unmanaged non-empty output directory: {out_dir} (install-simulation)"
            ) from exc

    paths = {Path("install-simulation")}
    paths.update(path.relative_to(out_dir) for path in simulation_root.rglob("*"))
    return paths


def reset_managed_output_dir(out_dir: Path, platform_names: set[str]) -> None:
    """Replace only a directory whose existing contents match generated package outputs."""

    if out_dir.exists() and any(out_dir.iterdir()):
        manifest_path = out_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            package_name = str(manifest["name"]).strip()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir}") from exc
        compiler = manifest.get("compiler", {})
        if (
            manifest.get("platform") != "generic"
            or manifest.get("canonical_format") != "agent-skills"
            or not isinstance(compiler, dict)
            or compiler.get("name") != "yao-skill-ir-compiler"
        ):
            raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir}")
        allowed = _managed_output_paths(package_name, platform_names)
        allowed.update(_verified_install_simulation_paths(out_dir, package_name))
        unexpected = []
        for path in out_dir.rglob("*"):
            relative = path.relative_to(out_dir)
            if path.is_symlink() or relative not in allowed:
                unexpected.append(relative.as_posix())
        if unexpected:
            preview = ", ".join(sorted(unexpected)[:5])
            raise ValueError(f"Refusing unmanaged non-empty output directory: {out_dir} ({preview})")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

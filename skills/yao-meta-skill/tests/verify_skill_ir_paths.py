#!/usr/bin/env python3
"""Canonical Skill IR resolution and identity-drift tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from skill_ir_paths import SkillIRResolutionError, candidate_paths, find_skill_ir, find_skill_ir_path  # noqa: E402


TMP = ROOT / "tests" / "tmp_skill_ir_paths"
DESCRIPTION = "Create reliable demo skills from a recurring workflow."


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_skill(root: Path, name: str = "demo-skill", *, source: str | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{DESCRIPTION}"\n---\n\n# Demo\n',
        encoding="utf-8",
    )
    manifest = {"name": name, "version": "1.0.0", "owner": "Yao", "updated_at": "2026-08-12"}
    if source is not None:
        manifest["skill_ir_source"] = source
    write_json(root / "manifest.json", manifest)


def ir_payload(name: str = "demo-skill", description: str = DESCRIPTION) -> dict:
    return {
        "schema_version": "2.0.0",
        "name": name,
        "job_to_be_done": description,
        "trigger_surface": {
            "description": description,
            "should_trigger": ["Create a reusable skill."],
            "should_not_trigger": ["Summarize a document."],
            "edge_cases": [],
        },
        "workflow": {"steps": ["Build."], "decision_points": [], "failure_modes": []},
        "resources": {"references": [], "scripts": [], "assets": [], "reports": []},
        "eval_plan": {"trigger": [], "output": [], "adversarial": [], "baseline": ""},
        "risk": {"output_risk": "low", "execution_risk": "low", "trust_boundary": "personal"},
        "governance": {"owner": "Yao", "maturity": "scaffold", "review_cadence": "per-release", "review_due": "2026-11-10"},
    }


def expect_error(root: Path, code: str) -> None:
    try:
        find_skill_ir(root, "demo-skill", require_schema=True)
    except SkillIRResolutionError as exc:
        assert exc.code == code, exc
    else:
        raise AssertionError(f"Expected Skill IR error: {code}")


def main() -> None:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)

    root_ir, root_path = find_skill_ir(ROOT, "yao-meta-skill", require_schema=True)
    assert root_path == "skill-ir/examples/yao-meta-skill.json", root_path
    assert root_ir["schema_version"] == "2.0.0", root_ir
    assert find_skill_ir_path(ROOT, "yao-meta-skill", require_schema=True) == root_path
    root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    manifest_schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    assert root_manifest["skill_ir_source"] == root_path, root_manifest
    assert "skill_ir_source" in manifest_schema["properties"], manifest_schema

    declared = TMP / "declared"
    write_skill(declared, source="contracts/canonical.json")
    write_json(declared / "contracts" / "canonical.json", ir_payload(description="  Create reliable demo skills\nfrom a recurring workflow.  "))
    write_json(declared / "reports" / "skill-ir.json", ir_payload(name="wrong-copy"))
    payload, source = find_skill_ir(declared, "demo-skill", require_schema=True)
    assert source == "contracts/canonical.json", source
    assert payload["name"] == "demo-skill", payload

    reports_fallback = TMP / "reports-fallback"
    write_skill(reports_fallback)
    write_json(reports_fallback / "reports" / "skill-ir.json", ir_payload())
    payload, source = find_skill_ir(reports_fallback, "demo-skill", require_schema=True)
    assert source == "reports/skill-ir.json", source
    assert payload["name"] == "demo-skill", payload

    example_fallback = TMP / "example-fallback"
    write_skill(example_fallback)
    write_json(example_fallback / "skill-ir" / "examples" / "demo-skill.json", ir_payload())
    payload, source = find_skill_ir(example_fallback, "demo-skill", require_schema=True)
    assert source == "skill-ir/examples/demo-skill.json", source
    assert payload["name"] == "demo-skill", payload

    wildcard = TMP / "wildcard"
    write_skill(wildcard)
    write_json(wildcard / "skill-ir" / "examples" / "zzz-extra.json", ir_payload(name="zzz-extra"))
    payload, source = find_skill_ir(wildcard, "demo-skill", require_schema=True, fallback_source="missing")
    assert payload == {}, payload
    assert source == "missing", source
    assert all(path.name != "zzz-extra.json" for path in candidate_paths(wildcard, "demo-skill"))

    wrong_name = TMP / "wrong-name"
    write_skill(wrong_name)
    write_json(wrong_name / "reports" / "skill-ir.json", ir_payload(name="other-skill"))
    expect_error(wrong_name, "name-mismatch")

    wrong_schema = TMP / "wrong-schema"
    write_skill(wrong_schema)
    invalid_schema = ir_payload()
    invalid_schema["schema_version"] = "1.0.0"
    write_json(wrong_schema / "reports" / "skill-ir.json", invalid_schema)
    expect_error(wrong_schema, "schema-mismatch")

    wrong_description = TMP / "wrong-description"
    write_skill(wrong_description)
    write_json(wrong_description / "reports" / "skill-ir.json", ir_payload(description="Generate unrelated reports."))
    expect_error(wrong_description, "description-mismatch")

    escape = TMP / "escape"
    write_skill(escape, source="../outside.json")
    write_json(TMP / "outside.json", ir_payload())
    expect_error(escape, "unsafe-manifest-source")

    invalid_manifest = TMP / "invalid-manifest-contract"
    write_skill(invalid_manifest)
    write_json(invalid_manifest / "reports" / "skill-ir.json", ir_payload())
    manifest_payload = json.loads((invalid_manifest / "manifest.json").read_text(encoding="utf-8"))
    manifest_payload["skill_ir_source"] = 123
    write_json(invalid_manifest / "manifest.json", manifest_payload)
    invalid_manifest_proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(invalid_manifest)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid_manifest_proc.returncode == 2, invalid_manifest_proc.stdout
    invalid_manifest_result = json.loads(invalid_manifest_proc.stdout)
    assert any("skill_ir_source" in failure for failure in invalid_manifest_result["failures"]), invalid_manifest_result

    symlink_fallback = TMP / "symlink-fallback"
    write_skill(symlink_fallback)
    external_reports = TMP / "external-reports"
    write_json(external_reports / "skill-ir.json", ir_payload())
    (symlink_fallback / "reports").symlink_to(external_reports, target_is_directory=True)
    expect_error(symlink_fallback, "unsafe-ir-source")

    unsafe_name = TMP / "unsafe-name"
    write_skill(unsafe_name)
    try:
        find_skill_ir(unsafe_name, "../../outside", require_schema=True)
    except SkillIRResolutionError as exc:
        assert exc.code == "unsafe-skill-name", exc
    else:
        raise AssertionError("path traversal in Skill IR identity was accepted")

    paths = [str(path.relative_to(reports_fallback)) for path in candidate_paths(reports_fallback, "demo-skill")]
    assert paths == ["reports/skill-ir.json", "skill-ir/examples/demo-skill.json"], paths

    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

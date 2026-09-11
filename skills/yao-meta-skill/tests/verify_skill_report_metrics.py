#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CLI = SCRIPTS / "yao.py"
sys.path.insert(0, str(SCRIPTS))


def run(*args: str) -> dict:
    if "--self" not in args and any(value.startswith(f"{ROOT}{os.sep}") for value in args):
        args = (*args, "--self")
    proc = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    return {
        "ok": proc.returncode == 0,
        "payload": payload,
        "stderr": proc.stderr,
    }


def assert_metric(metric: dict) -> None:
    assert isinstance(metric.get("score"), int), metric
    assert 0 <= metric["score"] <= 100, metric
    assert metric.get("label"), metric
    assert metric.get("reasons"), metric
    assert all(isinstance(reason, str) and reason for reason in metric["reasons"]), metric


def main() -> None:
    from skill_report_metrics import calculate_scorecard

    tmp_root = ROOT / "tests" / "tmp_skill_report_metrics"
    if tmp_root.exists():
        subprocess.run(["rm", "-rf", str(tmp_root)], check=True)
    tmp_root.mkdir(parents=True, exist_ok=True)

    result = run(
        "init",
        "metric-demo-skill",
        "--description",
        "Turn customer research notes into a reusable strategy brief skill.",
        "--output-dir",
        str(tmp_root),
    )
    assert result["ok"], result
    created = tmp_root / "metric-demo-skill"

    scorecard = calculate_scorecard(created)
    expected_keys = {
        "completeness_score",
        "trigger_score",
        "evidence_score",
        "maintainability_score",
        "portability_score",
        "context_cost",
    }
    assert expected_keys.issubset(scorecard.keys()), scorecard
    for key in expected_keys:
        assert_metric(scorecard[key])

    assert scorecard["completeness_score"]["score"] >= 70, scorecard
    assert scorecard["trigger_score"]["score"] >= 50, scorecard
    assert any("SKILL.md" in reason for reason in scorecard["completeness_score"]["reasons"]), scorecard

    sparse_root = tmp_root / "sparse-skill"
    sparse_root.mkdir()
    (sparse_root / "SKILL.md").write_text(
        "---\nname: sparse-skill\ndescription: Sparse demo.\n---\n\n# Sparse Skill\n",
        encoding="utf-8",
    )
    sparse_scorecard = calculate_scorecard(sparse_root)
    assert sparse_scorecard["evidence_score"]["score"] < scorecard["evidence_score"]["score"], sparse_scorecard
    assert any("证据不足" in reason for reason in sparse_scorecard["evidence_score"]["reasons"]), sparse_scorecard

    unrelated_ir_root = tmp_root / "unrelated-ir-skill"
    unrelated_ir_root.mkdir()
    (unrelated_ir_root / "SKILL.md").write_text(
        "---\nname: unrelated-ir-skill\ndescription: Verify canonical Skill IR evidence.\n---\n\n# Unrelated IR Skill\n",
        encoding="utf-8",
    )
    unrelated_examples = unrelated_ir_root / "skill-ir" / "examples"
    unrelated_examples.mkdir(parents=True)
    (unrelated_examples / "other-skill.json").write_text(
        json.dumps({"name": "other-skill"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    unrelated_scorecard = calculate_scorecard(unrelated_ir_root)
    assert unrelated_scorecard["evidence_score"]["score"] == 0, unrelated_scorecard
    assert all(
        "skill-ir.json 已存在" not in reason for reason in unrelated_scorecard["evidence_score"]["reasons"]
    ), unrelated_scorecard

    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

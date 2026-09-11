#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_portability_report.py"
sys.path.insert(0, str(ROOT / "scripts"))

from render_portability_report import find_ir


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="renamed-skill-root-") as tmp:
        tmp_root = Path(tmp)
        ir_dir = tmp_root / "skill-ir" / "examples"
        ir_dir.mkdir(parents=True)
        ir_path = ir_dir / "yao-meta-skill.json"
        shutil.copy2(ROOT / "SKILL.md", tmp_root / "SKILL.md")
        shutil.copy2(ROOT / "manifest.json", tmp_root / "manifest.json")
        shutil.copy2(ROOT / "skill-ir" / "examples" / "yao-meta-skill.json", ir_path)
        ir_payload, ir_source = find_ir(tmp_root)
        assert ir_payload["schema_version"] == "2.0.0", ir_payload
        assert ir_source == "skill-ir/examples/yao-meta-skill.json", ir_source

    missing_target = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert missing_target.returncode == 2, missing_target
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)
    payload = json.loads(proc.stdout)
    failures = []
    if payload.get("score", 0) < 95:
        failures.append(f"portability score too low: {payload.get('score')}")
    if payload.get("summary", {}).get("adapter_target_count", 0) < 3:
        failures.append("adapter target coverage too low")
    if payload.get("summary", {}).get("degradation_coverage", 0) < 3:
        failures.append("degradation coverage too low")
    if payload.get("summary", {}).get("snapshot_count", 0) < 3:
        failures.append("snapshot coverage too low")

    report = {"ok": not failures, "failures": failures, "payload": payload}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render credential-safe provider evaluation readiness without making API calls."""

import argparse
import json
from pathlib import Path

from output_provider_matrix import load_provider_matrix, provider_status


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Renders credential-safe DeepSeek provider-matrix readiness without making API calls."


def main() -> None:
    parser = argparse.ArgumentParser(description="Render DeepSeek provider-matrix readiness without calling the provider.")
    parser.add_argument("skill_dir", help="Explicit Skill directory to inspect")
    parser.add_argument("--output-json", default="reports/provider_output_evaluation.json")
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    matrix = load_provider_matrix(skill_dir / "evals" / "output" / "provider_matrix.json")
    payload = provider_status(matrix)
    output = Path(args.output_json)
    if not output.is_absolute():
        output = skill_dir / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

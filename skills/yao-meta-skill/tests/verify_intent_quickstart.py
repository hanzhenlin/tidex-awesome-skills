#!/usr/bin/env python3
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from yao_cli_helpers import BENCHMARK_FIXTURE_DIR, ROOT, run

import yao_cli_create_commands


def main() -> None:
    tmp_root = ROOT / "tests" / "tmp_intent_quickstart"
    shutil.rmtree(tmp_root, ignore_errors=True)
    tmp_root.mkdir(parents=True, exist_ok=True)

    result = run(
        "quickstart",
        "--output-dir",
        str(tmp_root),
        "--github-fixture-dir",
        str(BENCHMARK_FIXTURE_DIR),
        "--no-update-check",
        input_text=(
            "inferred-intent-skill\n"
            "帮我做一个skill\n"
            "跳过\n"
            "跳过\n"
            "scaffold\n"
            "scaffold\n"
            "\n"
            "\n"
        ),
    )
    assert result["ok"], result
    skill_root = Path(result["payload"]["root"])
    context = json.loads((skill_root / "reports" / "intent-context.json").read_text(encoding="utf-8"))
    state = context["clarification_state"]
    assert state["decision"] == "infer", context
    assert state["rounds_used"] == 2, context
    assert state["stop_reason"] == "round-limit", context
    assert state["inference_quality"] == "low", context
    inferred_slots = {
        item["slot"]
        for item in context["assumptions"]
        if item["source"] == "preferred-inference"
    }
    assert {"job", "primary_output"} <= inferred_slots, context
    assert context["job"] != "帮我做一个skill", context
    assert context["primary_output"], context
    assert result["stderr"].count("[skip]:") == 2, result["stderr"]
    assert "我们先锁定最关键的一点" in result["stderr"], result["stderr"]
    assert result["payload"]["archetype"] == "scaffold", result
    assert "Best starting archetype: scaffold" in result["stderr"], result["stderr"]
    assert result["payload"]["intent_confidence"]["authoring_ready"], result
    assert not result["payload"]["intent_confidence"]["gate_passed"], result
    generated_skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    assert context["job"] in generated_skill, generated_skill
    assert context["primary_output"] in generated_skill, generated_skill
    confidence_report = json.loads((skill_root / "reports" / "intent-confidence.json").read_text(encoding="utf-8"))
    dialogue_report = json.loads((skill_root / "reports" / "intent-dialogue.json").read_text(encoding="utf-8"))
    studio_report = json.loads((skill_root / "reports" / "review-studio.json").read_text(encoding="utf-8"))
    viewer_report = json.loads((skill_root / "reports" / "review-viewer.json").read_text(encoding="utf-8"))
    assert confidence_report["clarification_plan"]["decision"] == "infer", confidence_report
    assert dialogue_report["recommended_next_move"] == "infer", dialogue_report
    intent_gate = next(item for item in studio_report["gates"] if item["key"] == "intent-canvas")
    assert intent_gate["status"] == "warn", intent_gate
    intent_readiness = next(
        item for item in viewer_report["evidence_readiness"]["checks"] if item["label"] == "Intent clarity"
    )
    assert intent_readiness["status"] == "warn", intent_readiness

    explicit_result = run(
        "quickstart",
        "--name",
        "explicit-intent-skill",
        "--job",
        "Turn release notes into a reusable launch brief",
        "--real-input",
        "release notes",
        "--primary-output",
        "Launch brief",
        "--description",
        "Turn release notes into a reusable launch brief",
        "--archetype",
        "production",
        "--mode",
        "production",
        "--user-reference",
        "Release workflow::method::Keep the hand-back concise.::Do not publish it.",
        "--local-constraint",
        "privacy",
        "--output-dir",
        str(tmp_root),
        "--github-fixture-dir",
        str(BENCHMARK_FIXTURE_DIR),
        "--no-update-check",
        input_text="",
    )
    assert explicit_result["ok"], explicit_result
    explicit_context = json.loads(
        (Path(explicit_result["payload"]["root"]) / "reports" / "intent-context.json").read_text(encoding="utf-8")
    )
    assert explicit_context["clarification_state"]["rounds_used"] == 0, explicit_context
    assert explicit_result["stderr"].count("[skip]:") == 0, explicit_result["stderr"]
    assert "If I am off" not in explicit_result["stderr"], explicit_result["stderr"]
    assert not any(
        item.get("slot") == "constraints" and item.get("source") == "inferred-default"
        for item in explicit_context["assumptions"]
    ), explicit_context

    correction_context = {
        "job": "Draft release email copy",
        "real_inputs": ["release notes"],
        "primary_output": "Release email",
        "description": "Draft release email copy",
        "exclusions": [],
        "constraints": [],
        "standards": [],
        "correction": "Use a product launch brief as the main direction.",
        "clarification_state": {
            "rounds_used": 0,
            "max_rounds": 2,
            "asked_ambiguities": [],
            "correction_pending": True,
        },
    }
    seen_questions = []
    correction_answers = iter(["Summarize release notes for product launch decisions", "Product launch brief"])

    def answer_correction(question: str, _default: str) -> str:
        seen_questions.append(question)
        return next(correction_answers)

    with patch.object(yao_cli_create_commands, "prompt_optional", side_effect=answer_correction):
        correction_summary = yao_cli_create_commands.run_intent_clarification(
            correction_context,
            skill_name="launch-helper",
        )
    assert correction_summary["authoring_ready"], correction_summary
    assert correction_summary["context"]["primary_output"] == "Product launch brief", correction_summary
    assert correction_summary["context"]["clarification_state"]["rounds_used"] == 2, correction_summary
    assert len(seen_questions) == 2, seen_questions
    assert "different capability boundaries" in seen_questions[0], seen_questions

    output_correction_context = {
        "job": "Draft a weekly launch summary",
        "real_inputs": ["release notes"],
        "primary_output": "Markdown launch brief",
        "description": "Draft a weekly launch summary",
        "correction": "Actually, the output should be a PDF report.",
        "clarification_state": {
            "rounds_used": 0,
            "max_rounds": 2,
            "asked_ambiguities": [],
            "correction_pending": True,
        },
    }
    output_questions = []

    def answer_output_correction(question: str, _default: str) -> str:
        output_questions.append(question)
        return "Executive PDF report"

    with patch.object(yao_cli_create_commands, "prompt_optional", side_effect=answer_output_correction):
        output_correction_summary = yao_cli_create_commands.run_intent_clarification(
            output_correction_context,
            skill_name="launch-helper",
        )
    assert output_correction_summary["authoring_ready"], output_correction_summary
    assert output_correction_summary["context"]["job"] == "Draft a weekly launch summary", output_correction_summary
    assert output_correction_summary["context"]["primary_output"] == "Executive PDF report", output_correction_summary
    assert output_correction_summary["context"]["clarification_state"]["rounds_used"] == 1, output_correction_summary
    assert "confirmed hand-back" in output_questions[0], output_questions

    alternative_context = {
        "job": "Create a report or dashboard",
        "primary_output": "Decision support artifact",
        "description": "Create a report or dashboard",
        "clarification_state": {"rounds_used": 0, "max_rounds": 2, "asked_ambiguities": []},
    }
    with patch.object(yao_cli_create_commands, "prompt_optional", return_value="Create a dashboard"):
        alternative_summary = yao_cli_create_commands.run_intent_clarification(
            alternative_context,
            explicit_description="Create a report or dashboard",
            skill_name="decision-helper",
        )
    assert alternative_summary["authoring_ready"], alternative_summary
    assert " or " not in alternative_summary["context"]["description"].lower(), alternative_summary

    invalid_fixture_result = run(
        "quickstart",
        "--name",
        "invalid-fixture-skill",
        "--job",
        "Summarize release notes for launch decisions",
        "--real-input",
        "release notes",
        "--primary-output",
        "Launch brief",
        "--description",
        "Summarize release notes for launch decisions",
        "--archetype",
        "scaffold",
        "--mode",
        "scaffold",
        "--user-reference",
        "Release workflow",
        "--local-constraint",
        "privacy",
        "--output-dir",
        str(tmp_root),
        "--github-fixture-dir",
        str(ROOT / "tests" / "fixtures" / "missing-intent-fixture"),
        "--no-update-check",
        input_text="",
    )
    assert not invalid_fixture_result["ok"], invalid_fixture_result
    assert invalid_fixture_result["payload"]["error"] == "initialization-io-error", invalid_fixture_result
    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

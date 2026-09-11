#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_intent_confidence.py"
SCRIPTS_PATH = str(ROOT / "scripts")
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from intent_clarification import apply_preferred_inference, compact_excerpt, detect_language  # noqa: E402
from render_intent_confidence import assess_intent_confidence  # noqa: E402


def main() -> None:
    tmp_root = ROOT / "tests" / "tmp_intent_confidence"
    if tmp_root.exists():
        subprocess.run(["rm", "-rf", str(tmp_root)], check=True)
    skill_dir = tmp_root / "intent-confidence-demo"
    (skill_dir / "reports").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: intent-confidence-demo\ndescription: Turn repeated incident notes into a reusable incident packet.\n---\n\n# Intent Confidence Demo\n",
        encoding="utf-8",
    )
    context_path = skill_dir / "reports" / "context.json"
    context_path.write_text(
        json.dumps(
            {
                "job": "Turn repeated incident notes into a reusable incident packet.",
                "real_inputs": ["incident notes", "chat timeline"],
                "primary_output": "A reusable incident command packet.",
                "description": "Turn repeated incident notes into a reusable incident packet. Primary output: A reusable incident command packet.",
                "exclusions": ["Do not draft external PR statements."],
                "constraints": ["auditability", "portability"],
                "standards": ["consistency"],
                "correction": "",
                "user_references": ["A trusted incident workflow"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(skill_dir),
            "--context-json",
            str(context_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["summary"]["gate_passed"], payload
    assert payload["summary"]["score"] >= 70, payload
    markdown = Path(payload["artifacts"]["markdown"]).read_text(encoding="utf-8")
    assert "Intent Confidence" in markdown, markdown[:200]
    assert "Follow-Up Questions" in markdown, markdown[:500]

    chinese_context = skill_dir / "reports" / "chinese-context.json"
    chinese_context.write_text(
        json.dumps(
            {
                "job": "把候选人的面试记录整理成结构化反馈",
                "real_inputs": ["面试记录"],
                "primary_output": "候选人反馈报告",
                "description": "把候选人的面试记录整理成结构化反馈",
                "exclusions": [],
                "constraints": [],
                "standards": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    chinese_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(skill_dir),
            "--context-json",
            str(chinese_context),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    chinese_payload = json.loads(chinese_proc.stdout)
    chinese_summary = chinese_payload["summary"]
    assert chinese_summary["authoring_ready"], chinese_summary
    assert chinese_summary["clarification_plan"]["decision"] == "proceed", chinese_summary
    assert chinese_summary["clarification_plan"]["language"] == "zh-CN", chinese_summary

    missing_output_context = skill_dir / "reports" / "missing-output-context.json"
    missing_output_context.write_text(
        json.dumps(
            {
                "job": "Turn interview notes into structured candidate feedback",
                "real_inputs": ["interview notes"],
                "primary_output": "",
                "description": "Turn interview notes into structured candidate feedback",
                "exclusions": [],
                "constraints": [],
                "standards": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    missing_output_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(skill_dir),
            "--context-json",
            str(missing_output_context),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    missing_output_summary = json.loads(missing_output_proc.stdout)["summary"]
    missing_output_plan = missing_output_summary["clarification_plan"]
    assert not missing_output_summary["authoring_ready"], missing_output_summary
    assert missing_output_plan["decision"] == "ask", missing_output_plan
    assert missing_output_plan["ambiguity_type"] == "deliverable_missing", missing_output_plan
    assert missing_output_plan["target_slot"] == "primary_output", missing_output_plan
    assert "Turn interview notes into structured candidate feedback" in missing_output_plan["question"], missing_output_plan
    assert missing_output_plan["decision_impact"], missing_output_plan

    generic_job_context = assess_intent_confidence(
        {
            "job": "Create a skill",
            "real_inputs": ["release notes"],
            "primary_output": "Launch brief",
            "description": "Create a skill",
            "exclusions": [],
            "constraints": [],
            "standards": [],
        }
    )
    assert generic_job_context["clarification_plan"]["target_slot"] == "job", generic_job_context
    assert generic_job_context["clarification_plan"]["ambiguity_type"] == "task_too_broad", generic_job_context
    assert "Launch brief" in generic_job_context["clarification_plan"]["question"], generic_job_context
    assert detect_language("请把 release notes 整理成 launch brief") == "zh-CN"
    assert assess_intent_confidence(
        {
            "job": "Should this create a report or a dashboard?",
            "primary_output": "Decision support artifact",
            "description": "Should this create a report or a dashboard?",
        }
    )["clarification_plan"]["ambiguity_type"] == "multi_intent"

    non_core_context = skill_dir / "reports" / "non-core-context.json"
    non_core_context.write_text(
        json.dumps(
            {
                "job": "Summarize release notes for a product launch",
                "real_inputs": [],
                "primary_output": "Release brief",
                "description": "Summarize release notes for a product launch",
                "exclusions": [],
                "constraints": [],
                "standards": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    non_core_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(skill_dir),
            "--context-json",
            str(non_core_context),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    non_core_summary = json.loads(non_core_proc.stdout)["summary"]
    assert non_core_summary["authoring_ready"], non_core_summary
    assert non_core_summary["clarification_plan"]["decision"] == "proceed", non_core_summary
    assumption_slots = {item["slot"] for item in non_core_summary["assumptions"]}
    assert {"real_inputs", "exclusions", "constraints", "standards"} <= assumption_slots, non_core_summary

    correction_context = skill_dir / "reports" / "correction-context.json"
    correction_context.write_text(
        json.dumps(
            {
                "job": "Draft launch email copy from release notes",
                "real_inputs": ["release notes"],
                "primary_output": "Launch email campaign",
                "description": "Draft launch email copy from release notes",
                "exclusions": ["Do not publish messages"],
                "constraints": ["privacy"],
                "standards": ["consistency"],
                "correction": "Actually prioritize a product launch brief instead of email copy.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    correction_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(skill_dir),
            "--context-json",
            str(correction_context),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    correction_payload = json.loads(correction_proc.stdout)
    correction_summary = correction_payload["summary"]
    correction_plan = correction_summary["clarification_plan"]
    assert correction_plan["decision"] == "ask", correction_plan
    assert correction_plan["ambiguity_type"] == "direction_conflict", correction_plan
    assert "Draft launch email copy" in correction_plan["question"], correction_plan
    assert "product launch brief" in correction_plan["question"], correction_plan
    updated_markdown = Path(correction_payload["artifacts"]["markdown"]).read_text(encoding="utf-8")
    assert "Clarification Decision" in updated_markdown, updated_markdown[:1200]
    assert "Structured Assumptions" in updated_markdown, updated_markdown[:1600]
    assert "Authoring ready" in updated_markdown, updated_markdown[:800]

    description_inference = apply_preferred_inference(
        {
            "job": "Create a skill",
            "primary_output": "A reusable skill package",
            "description": "Summarize customer interviews into a prioritized product insight brief",
            "clarification_state": {"rounds_used": 2, "max_rounds": 2},
        },
        "fallback-name",
    )
    assert description_inference["job"].startswith("Summarize customer interviews"), description_inference
    assert "fallback name" not in description_inference["job"], description_inference
    assert description_inference["clarification_state"]["inference_quality"] == "medium", description_inference
    assert len(compact_excerpt("x" * 120)) == 96

    confirmed_output_inference = apply_preferred_inference(
        {
            "job": "Create a skill",
            "primary_output": "Launch brief",
            "description": "Summarize customer interviews into product insights",
            "clarification_state": {"rounds_used": 2, "max_rounds": 2},
        },
        "fallback-name",
    )
    assert "Launch brief" in confirmed_output_inference["job"], confirmed_output_inference
    assert "customer interviews" not in confirmed_output_inference["job"], confirmed_output_inference

    correction_inference = apply_preferred_inference(
        {
            "job": "Draft launch email copy from release notes",
            "primary_output": "Launch email campaign",
            "description": "Draft launch email copy from release notes",
            "correction": "Use a product launch brief as the main direction.",
            "clarification_state": {"rounds_used": 2, "max_rounds": 2, "correction_pending": True},
        },
        "launch-helper",
    )
    correction_resolution = assess_intent_confidence(correction_inference)
    assert correction_resolution["authoring_ready"], correction_resolution
    assert correction_resolution["clarification_plan"]["decision"] == "infer", correction_resolution
    assert correction_resolution["context"]["job"].startswith("Use a product launch brief"), correction_resolution
    assert "direction_conflict" in correction_resolution["context"]["clarification_state"]["resolved_ambiguities"]

    explicit_alternative = assess_intent_confidence(
        {
            "job": "Either organize source documents or answer questions from an existing knowledge base",
            "real_inputs": ["source documents"],
            "primary_output": "A maintained knowledge workspace",
            "description": "Either organize source documents or answer questions from an existing knowledge base",
            "exclusions": ["Do not publish content"],
            "constraints": ["privacy"],
            "standards": ["consistency"],
        }
    )
    assert explicit_alternative["clarification_plan"]["ambiguity_type"] == "multi_intent", explicit_alternative
    output_alternative = assess_intent_confidence(
        {
            "job": "Summarize launch evidence for executive decisions",
            "primary_output": "A PDF report or interactive dashboard",
            "description": "Summarize launch evidence for executive decisions",
        }
    )
    assert output_alternative["clarification_plan"]["ambiguity_type"] == "multi_intent", output_alternative
    assert output_alternative["clarification_plan"]["direction_slot"] == "primary_output", output_alternative
    assert "PDF report or interactive dashboard" in output_alternative["clarification_plan"]["question"], output_alternative
    chinese_output_alternative = assess_intent_confidence(
        {
            "job": "把投放数据整理给管理层决策",
            "primary_output": "PDF 报告或交互式仪表盘",
            "description": "把投放数据整理给管理层决策",
        }
    )
    assert chinese_output_alternative["clarification_plan"]["ambiguity_type"] == "multi_intent", chinese_output_alternative
    assert chinese_output_alternative["clarification_plan"]["language"] == "zh-CN", chinese_output_alternative

    narrowed_alternative = apply_preferred_inference(
        {
            "job": "Either organize source documents or answer questions from a knowledge base",
            "primary_output": "A maintained knowledge workspace",
            "description": "Either organize source documents or answer questions from a knowledge base",
            "clarification_state": {"rounds_used": 2, "max_rounds": 2},
        },
        "knowledge-helper",
    )
    assert " or " not in narrowed_alternative["job"].lower(), narrowed_alternative
    assert narrowed_alternative["job"] == "answer questions from a knowledge base", narrowed_alternative
    assert narrowed_alternative["clarification_state"]["inference_quality"] == "medium", narrowed_alternative

    output_correction = apply_preferred_inference(
        {
            "job": "Summarize release notes",
            "primary_output": "Markdown launch brief",
            "description": "Summarize release notes",
            "correction": "Actually, the output should be a PDF report.",
            "clarification_state": {
                "rounds_used": 2,
                "max_rounds": 2,
                "correction_pending": True,
            },
        },
        "launch-helper",
    )
    assert output_correction["job"] == "Summarize release notes", output_correction
    assert output_correction["primary_output"] == "a PDF report", output_correction
    assert output_correction["clarification_state"]["inference_quality"] == "medium", output_correction

    non_core_correction = assess_intent_confidence(
        {
            "job": "Summarize release notes for launch decisions",
            "primary_output": "Launch brief",
            "description": "Summarize release notes for launch decisions",
            "correction": "The output tone should be concise.",
            "clarification_state": {"correction_pending": True},
        }
    )
    assert non_core_correction["clarification_plan"]["ambiguity_type"] != "direction_conflict", non_core_correction
    assert not non_core_correction["context"]["clarification_state"]["correction_pending"], non_core_correction

    edited_inference = assess_intent_confidence(
        {
            "job": "Summarize support calls into a decision brief",
            "primary_output": "Decision brief",
            "description": "Summarize support calls into a decision brief",
            "assumptions": [
                {
                    "slot": "job",
                    "value": "An older inferred job",
                    "source": "preferred-inference",
                    "reason": "older state",
                    "confidence": "low",
                }
            ],
        }
    )
    assert not any(
        item.get("slot") == "job" and item.get("source") == "preferred-inference"
        for item in edited_inference["assumptions"]
    ), edited_inference

    list_without_choice = assess_intent_confidence(
        {
            "job": "Turn workflows, prompts, documents, or existing skill packages into release-ready assets",
            "real_inputs": ["workflow notes"],
            "primary_output": "A release-ready skill package",
            "description": "Turn workflows, prompts, documents, or existing skill packages into release-ready assets",
            "exclusions": ["one-off summaries"],
            "constraints": ["privacy"],
            "standards": ["consistency"],
        }
    )
    assert list_without_choice["clarification_plan"]["ambiguity_type"] != "multi_intent", list_without_choice
    print(json.dumps({"ok": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

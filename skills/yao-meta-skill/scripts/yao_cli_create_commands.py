#!/usr/bin/env python3
"""Creation command handlers for the Yao CLI."""

import argparse
import json
import sys

from github_benchmark_scan import build_query
from init_skill import TargetExistsError, initialize_skill, parse_reference
from intent_clarification import apply_preferred_inference, detect_language, is_generic_intent
from render_intent_confidence import assess_intent_confidence
from yao_cli_config import (
    ARCHETYPE_MODE,
    archetype_guidance,
    diagnose_skill_candidates,
    diagnosis_note,
    discovery_summary,
    infer_archetype,
    recommendation_from_synthesis,
    reference_visibility,
)
from yao_cli_runtime import run_script


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by yao.py to keep skill creation and quickstart command handlers out of the CLI orchestrator."


SKIP_ANSWERS = {"", "skip", "none", "no", "n", "跳过", "略过", "不用", "算了"}


def normalized_answer(value: str) -> str:
    return " ".join(value.strip().lower().split())


def prompt_with_default(label: str, default: str) -> str:
    sys.stderr.write(f"{label} [{default}]: ")
    sys.stderr.flush()
    value = sys.stdin.readline().strip()
    return value or default


def prompt_optional(label: str, default: str = "skip") -> str:
    sys.stderr.write(f"{label} [{default}]: ")
    sys.stderr.flush()
    value = sys.stdin.readline().strip()
    return value or default


def prompt_optional_entries(label: str) -> list[str]:
    sys.stderr.write(f"{label} [none]: ")
    sys.stderr.flush()
    value = sys.stdin.readline().strip()
    if not value or value.lower() in {"none", "no", "n"}:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def update_context_slot(context: dict, slot: str, answer: str, list_mode: bool) -> None:
    value = answer.strip()
    if normalized_answer(value) in SKIP_ANSWERS:
        return
    if list_mode:
        context[slot] = [item.strip() for item in value.split(",") if item.strip()]
    else:
        context[slot] = value
    context["assumptions"] = [
        item
        for item in context.get("assumptions", [])
        if not (
            isinstance(item, dict)
            and item.get("slot") == slot
            and item.get("source") == "preferred-inference"
        )
    ]


def intent_confidence_note(summary: dict) -> str:
    clarification = summary.get("clarification_plan", {})
    lines = [
        f"\nIntent confidence: {summary['score']}/100 ({summary['band']}).",
        f"- Clarification decision: {clarification.get('decision', 'legacy')}; stop {clarification.get('stop_reason', 'n/a')}.",
        f"- Structured assumptions: {len(summary.get('assumptions', []) or [])}.",
        f"- Recommended action: {summary['recommended_action']}",
    ]
    if not summary.get("authoring_ready") and summary.get("gaps"):
        top_gap = summary["gaps"][0]
        lines.append(f"- Biggest gap: {top_gap['label']} — {top_gap['reason']}")
    return "\n".join(lines) + "\n"


def compose_intent_description(context: dict, explicit_description: str | None = None) -> str:
    job = str(context.get("job", "")).strip()
    primary_output = str(context.get("primary_output", "")).strip()
    state = context.get("clarification_state", {}) if isinstance(context.get("clarification_state"), dict) else {}
    resolved = {str(item) for item in state.get("resolved_ambiguities", [])}
    resolved_direction = bool({"direction_conflict", "multi_intent"} & resolved)
    description = (
        job
        if resolved_direction or not explicit_description or is_generic_intent(explicit_description)
        else explicit_description
    ).strip()
    language = detect_language(job, primary_output, description)
    if explicit_description and job and job.lower() not in description.lower():
        label = "核心任务" if language == "zh-CN" else "Recurring job"
        description = f"{description.rstrip('.。')} {label}: {job.rstrip('.。')}."
    if primary_output and primary_output.lower() not in description.lower():
        label = "主要交付物" if language == "zh-CN" else "Primary output"
        description = f"{description.rstrip('.。')} {label}: {primary_output.rstrip('.。')}."
    return description


def run_intent_clarification(context: dict, explicit_description: str | None = None, skill_name: str = "") -> dict:
    state = context.setdefault(
        "clarification_state",
        {"rounds_used": 0, "max_rounds": 2, "asked_ambiguities": []},
    )
    confidence = assess_intent_confidence(context)
    while confidence["clarification_plan"]["decision"] == "ask" and state["rounds_used"] < state["max_rounds"]:
        plan = confidence["clarification_plan"]
        answer = prompt_optional(plan["question"], "skip")
        state["rounds_used"] += 1
        asked_ambiguities = state.setdefault("asked_ambiguities", [])
        if plan["ambiguity_type"] not in asked_ambiguities:
            asked_ambiguities.append(plan["ambiguity_type"])
        if normalized_answer(answer) not in SKIP_ANSWERS:
            if plan["target_slot"] == "direction":
                direction_slot = plan.get("direction_slot") or "job"
                update_context_slot(context, direction_slot, answer, False)
                if plan["ambiguity_type"] == "direction_conflict" and direction_slot == "job":
                    context["primary_output"] = ""
                context["correction"] = ""
                state["correction_pending"] = False
                state.setdefault("resolved_ambiguities", []).append(plan["ambiguity_type"])
            else:
                update_context_slot(context, plan["target_slot"], answer, False)
        context["description"] = compose_intent_description(context, explicit_description)
        confidence = assess_intent_confidence(context)
    if confidence["clarification_plan"]["decision"] == "ask":
        context = apply_preferred_inference(context, skill_name)
        context["description"] = compose_intent_description(context, explicit_description)
        confidence = assess_intent_confidence(context)
    return confidence


def maybe_emit_update_notice(args: argparse.Namespace) -> None:
    if getattr(args, "no_update_check", False):
        return
    result = run_script("check_update.py", ["--notice"])
    payload = result["payload"] if result["payload"] is not None else {}
    if not result["ok"] and not payload:
        return
    if payload.get("notify_user") and payload.get("notice_text"):
        sys.stderr.write("\n" + str(payload["notice_text"]) + "\n")


def command_init(args: argparse.Namespace) -> int:
    cmd = [
        args.name,
        "--description",
        args.description,
        "--output-dir",
        args.output_dir,
        "--mode",
        args.mode,
        "--archetype",
        args.archetype,
        *(["--title", args.title] if args.title else []),
    ]
    for reference in args.external_reference:
        cmd.extend(["--external-reference", reference])
    for reference in args.user_reference:
        cmd.extend(["--user-reference", reference])
    for constraint in args.local_constraint:
        cmd.extend(["--local-constraint", constraint])
    if args.github_query:
        cmd.extend(["--github-query", args.github_query])
    cmd.extend(["--github-top-n", str(args.github_top_n)])
    if args.github_fixture_dir:
        cmd.extend(["--github-fixture-dir", args.github_fixture_dir])
    if args.intent_job:
        cmd.extend(["--intent-job", args.intent_job])
    for item in args.intent_real_input:
        cmd.extend(["--intent-real-input", item])
    if args.intent_primary_output:
        cmd.extend(["--intent-primary-output", args.intent_primary_output])
    for item in args.intent_exclusion:
        cmd.extend(["--intent-exclusion", item])
    for item in args.intent_constraint:
        cmd.extend(["--intent-constraint", item])
    for item in args.intent_standard:
        cmd.extend(["--intent-standard", item])
    if args.intent_correction:
        cmd.extend(["--intent-correction", args.intent_correction])
    result = run_script("init_skill.py", cmd)
    print(json.dumps(result["payload"] if result["payload"] is not None else result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def command_quickstart(args: argparse.Namespace) -> int:
    maybe_emit_update_notice(args)
    sys.stderr.write("Let's start gently. You do not need a polished brief here.\n")
    sys.stderr.write("Give me the real work in your own words, and I will help turn it into a clean first-pass skill.\n")
    sys.stderr.write("While we shape the first pass, I will quietly check a few strong public patterns in the background and only surface them if there is real uncertainty or a design conflict.\n")
    name = args.name or prompt_with_default("Skill name", "my-skill")
    job = args.job or prompt_with_default(
        "In your own words, what repeated work do you most want this skill to reliably handle",
        "Turn a repeated workflow into a reusable skill.",
    )
    intent_context = {
        "job": job,
        "real_inputs": list(args.real_input or []),
        "primary_output": args.primary_output or "",
        "description": args.description or job,
        "exclusions": [],
        "constraints": [],
        "standards": [],
        "correction": "",
        "user_references": [],
        "skill_name": name,
        "clarification_state": {"rounds_used": 0, "max_rounds": 2, "asked_ambiguities": []},
    }
    confidence = run_intent_clarification(intent_context, args.description, name)
    intent_context = confidence["context"]
    job = intent_context["job"]
    primary_output = intent_context["primary_output"]
    description = intent_context["description"]
    inferred_archetype, archetype_reason = infer_archetype(job, description)
    if intent_context.get("clarification_state", {}).get("inference_quality") == "low":
        inferred_archetype = "scaffold"
        archetype_reason = "Low-confidence preferred inference keeps the first package at scaffold scope."
    guidance = archetype_guidance(inferred_archetype)
    sys.stderr.write(discovery_summary(job, primary_output, inferred_archetype, guidance))
    confidence = assess_intent_confidence(intent_context)
    sys.stderr.write(intent_confidence_note(confidence))
    diagnosis = diagnose_skill_candidates(job, primary_output, inferred_archetype, confidence)
    if diagnosis["fuzzy"]:
        sys.stderr.write(diagnosis_note(diagnosis))
    archetype = args.archetype or prompt_with_default("I would start with this archetype (scaffold/production/library/governed)", inferred_archetype)
    archetype = archetype if archetype in ARCHETYPE_MODE else inferred_archetype
    default_mode = ARCHETYPE_MODE[archetype]
    mode = args.mode or prompt_with_default("For the first pass, I would keep the mode here (scaffold/production/library/governed)", default_mode)
    mode = mode if mode in ARCHETYPE_MODE.values() else default_mode
    diagnosis = diagnose_skill_candidates(job, primary_output, archetype, confidence)
    guidance = archetype_guidance(archetype)
    sys.stderr.write(
        f"\nGood. I will treat this as `{archetype}` in `{mode}` mode, so the first pass stays focused on {guidance['focus']}.\n"
    )
    user_references = args.user_reference or prompt_optional_entries(
        "If there is anything you admire and want me to learn from as pattern hints, send it here (repo, product, page, workflow; comma-separated)"
    )
    external_references = args.external_reference or []
    prompted_constraints = args.constraint if getattr(args, "constraint", None) else ([] if args.local_constraint else prompt_optional_entries(
        "Tell me any local constraints I must keep in view (privacy, naming, compatibility; comma-separated)"
    ))
    local_constraints = args.local_constraint or prompted_constraints or intent_context.get("constraints", [])
    intent_context["user_references"] = user_references
    intent_context["constraints"] = local_constraints
    confidence = assess_intent_confidence(intent_context)
    intent_context = confidence["context"]
    github_query = args.github_query or build_query(" ".join(filter(None, [job, primary_output, description])))
    title = args.title or name.replace("-", " ").title()
    guidance = archetype_guidance(archetype)
    try:
        payload = initialize_skill(
            name,
            description,
            title,
            args.output_dir,
            mode,
            archetype,
            external_references=[parse_reference(item, "external") for item in external_references],
            user_references=[parse_reference(item, "user") for item in user_references],
            local_constraints=[parse_reference(item, "local") for item in local_constraints],
            github_query=github_query,
            github_top_n=args.github_top_n,
            github_fixture_dir=args.github_fixture_dir,
            intent_context=intent_context,
        )
    except TargetExistsError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "target-exists",
                    "target": str(exc.target),
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    except ValueError as exc:
        print(json.dumps({"ok": False, "failures": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    except OSError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "initialization-io-error",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    result = {"ok": bool(payload.get("ok")), "payload": payload}
    reference_synthesis = payload.get("reference_synthesis") or {}
    visibility = reference_visibility(reference_synthesis)
    recommendation = recommendation_from_synthesis(reference_synthesis, visibility)
    sys.stderr.write(f"\nRecommendation: {recommendation['summary']}\n")
    if visibility["user_decision_required"]:
        if visibility["conflicts"]:
            sys.stderr.write(f"I am surfacing this because there is a real design conflict: {visibility['conflicts'][0]['summary']}\n")
        else:
            sys.stderr.write("I am surfacing this because intent is still settling and the package should not deepen on guesswork.\n")
    else:
        sys.stderr.write("I will keep the underlying benchmark evidence in the reviewer reports and move ahead with this recommendation.\n")
    if payload.get("report_view", {}).get("html_report"):
        sys.stderr.write(f"Skill report: {payload['report_view']['html_report']}\n")
    if payload.get("report_view", {}).get("interpretation_report"):
        sys.stderr.write(f"Skill interpretation: {payload['report_view']['interpretation_report']}\n")

    next_steps = [
        "Open reports/skill-interpretation.html to review the generated Skill interpretation report.",
        "Open reports/skill-overview.html to review the generated Skill audit report.",
        "Open reports/intent-dialogue.md and tighten the real job, outputs, and exclusions.",
        "Open reports/review-studio.html to inspect the Review Studio 2.0 gate view before release.",
        "Open reports/review-viewer.html to explain the package to a first-time reviewer.",
        "Use reports/iteration-directions.md to choose only one high-value next move before adding more files.",
    ]
    if visibility["user_decision_required"]:
        next_steps.insert(
            1,
            "Open reports/reference-synthesis.md if you want to inspect why the recommendation was surfaced and which tradeoff needs a call.",
        )
    report = {
        "ok": result["ok"],
        "root": payload.get("root"),
        "mode": mode,
        "archetype": archetype,
        "artifacts": payload.get("artifacts", {}),
        "report_view": payload.get("report_view", {}),
        "intent_confidence": {
            "score": confidence["score"],
            "band": confidence["band"],
            "gate_passed": confidence["gate_passed"],
            "authoring_ready": confidence["authoring_ready"],
            "clarification_plan": confidence["clarification_plan"],
            "recommended_action": confidence["recommended_action"],
        },
        "recommendation": recommendation,
        "reference_mode": {
            "mode": visibility["mode"],
            "user_decision_required": visibility["user_decision_required"],
        },
        "reviewer_evidence": {
            "visibility": "full evidence in reports and review-viewer",
            "artifacts": {
                "benchmark_scan": payload.get("artifacts", {}).get("github_benchmark_scan_md"),
                "reference_synthesis": payload.get("artifacts", {}).get("reference_synthesis_md"),
                "artifact_design_profile": payload.get("artifacts", {}).get("artifact_design_profile_md"),
                "prompt_quality_profile": payload.get("artifacts", {}).get("prompt_quality_profile_md"),
                "system_model": payload.get("artifacts", {}).get("system_model_md"),
                "skill_interpretation": payload.get("artifacts", {}).get("skill_interpretation_html"),
                "review_studio": payload.get("artifacts", {}).get("review_studio_html"),
                "review_viewer": payload.get("artifacts", {}).get("review_viewer_html"),
            },
        },
        "guidance": {
            "archetype_reason": archetype_reason,
            "problem_diagnosis": diagnosis,
            "why_this_mode": (
                "Scaffold mode keeps the first package light and lets you postpone governance-heavy work until reuse becomes real."
                if mode == "scaffold"
                else "This mode expects stronger lifecycle metadata, validation, and review discipline."
            ),
            "first_gate": guidance["first_gate"],
            "focus": guidance["focus"],
            "next_steps": next_steps,
            "experience_note": (
                "The first pass should feel more like guided co-creation than a worksheet. "
                "The system should make benchmark and pattern calls quietly unless there is a real reason to ask you to choose."
            ),
        },
    }
    if visibility["user_decision_required"]:
        report["uncertainty_or_conflict"] = {
            "reasons": visibility["reasons"],
            "conflicts": visibility["conflicts"],
            "note": "A design decision still needs your input before the package should be deepened.",
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2

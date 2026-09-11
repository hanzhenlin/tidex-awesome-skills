#!/usr/bin/env python3
import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from render_skill_os2_audit import build_audit
from world_class_evidence_contract import load_json_with_status, validate_payload


ROOT = Path(__file__).resolve().parent.parent


TASK_TEMPLATES: dict[str, dict[str, Any]] = {
    "provider-holdout": {
        "category": "external",
        "owner": "operator with provider credentials",
        "objective": "Complete the fixed 10-case DeepSeek Flash+Pro matrix with 40 real calls and governed budget evidence.",
        "runbook": [
            "Set DEEPSEEK_API_KEY in the operator shell; never commit or print the value.",
            "python3 scripts/yao.py evidence-build . --run-id <PROVIDER_RUN_ID> --self",
            "Keep the generated private answer key and role-neutral review materials inside .yao/runs/<PROVIDER_RUN_ID>.",
            "python3 scripts/yao.py skill-os2-audit . --generated-at <YYYY-MM-DD> --self",
        ],
        "success_checks": [
            "reports/provider_output_evaluation.json summary.call_count == 40",
            "reports/provider_output_evaluation.json summary.model_executed_count == 40",
            "reports/provider_output_evaluation.json summary.failure_count == 0",
            "reports/provider_output_evaluation.json summary.total_tokens <= 250000",
            "reports/skill_os2_audit.json item provider-holdout status becomes pass",
        ],
        "evidence_artifacts": [
            "evals/output/provider_matrix.json",
            "reports/provider_output_evaluation.json",
            "reports/provider_output_blind_pack.json",
            "reports/provider_output_answer_commitment.json",
            "reports/skill_os2_audit.json",
        ],
        "privacy_contract": [
            "Do not commit provider credentials or environment dumps.",
            "The output execution report records output hashes and aggregate run metadata, not raw provider prompts.",
        ],
    },
    "human-adjudication": {
        "category": "human",
        "owner": "human reviewer",
        "objective": "Collect three controlled, independent reviews of the same 20-pair provider blind pack.",
        "runbook": [
            "Give each registered reviewer an independent copy of the matching provider_review_reviewer-*.json template and the role-neutral blind pack.",
            "Collect all 20 A/B choices, reasons, controlled submission ids, timestamps, and truthful independent-review attestations.",
            "Export an access-controlled reviewer registry that binds each reviewer id to the exact packet SHA256.",
            "python3 scripts/yao.py evidence-finalize-review . --source-run <PROVIDER_RUN_ID> --decisions <reviewer-a.json> --decisions <reviewer-b.json> --decisions <reviewer-c.json> --reviewer-registry <registry.json> --run-id <FINAL_RUN_ID> --self",
            "python3 scripts/yao.py skill-os2-audit . --generated-at <YYYY-MM-DD> --self",
        ],
        "success_checks": [
            "reports/provider_output_adjudication.json summary.reviewer_count == 3",
            "reports/provider_output_adjudication.json summary.pair_count == 20",
            "reports/provider_output_adjudication.json summary.failure_count == 0",
            "reports/provider_output_adjudication.json evidence_binding.blind_pack_sha256 matches the source run",
            "reports/skill_os2_audit.json item human-adjudication status becomes pass",
        ],
        "evidence_artifacts": [
            "reports/provider_output_blind_pack.json",
            "reports/provider_reviewer_registry.json",
            "reports/provider_output_adjudication.json",
            "reports/provider_review_lineage.json",
            "scripts/adjudicate_multi_reviewer.py",
            "scripts/finalize_provider_review.py",
        ],
        "privacy_contract": [
            "Reviewer packets contain choices, reasons, hashes, and controlled submission metadata without raw prompts or answer-key roles.",
            "The private answer key remains under .yao/runs and is opened by the finalizer after all controlled packets are fixed.",
            "The adjudication and lineage artifacts preserve blind_pack_sha256 and answer_key_sha256 commitments.",
        ],
    },
    "native-permission-enforcement": {
        "category": "external",
        "owner": "target client or installer integrator",
        "objective": "Prove at least one real target client or external installer runtime guard enforces approved high-permission capabilities.",
        "runbook": [
            "Implement or connect a real target client or external installer runtime guard that blocks undeclared network, file_write, or subprocess capabilities.",
            "Update the generated target adapter only when the guard is actually enforced by that target.",
            "python3 scripts/yao.py package . --platform openai --platform claude --platform generic --platform vscode --output-dir dist --zip --self",
            "python3 scripts/yao.py install-simulate . --package-dir dist --install-root dist/install-simulation --self",
            "python3 scripts/yao.py runtime-permissions . --package-dir dist --self",
            "python3 scripts/yao.py skill-os2-audit . --generated-at <YYYY-MM-DD> --self",
        ],
        "success_checks": [
            "reports/runtime_permission_probes.json summary.native_enforcement_count > 0",
            "reports/runtime_permission_probes.json summary.failure_count == 0",
            "reports/runtime_permission_probes.json summary.installer_enforcement_pass_count records local installer enforcement but does not replace native evidence",
            "reports/skill_os2_audit.json item native-permission-enforcement status becomes pass",
        ],
        "evidence_artifacts": [
            "dist/targets/*/adapter.json",
            "reports/runtime_permission_probes.json",
            "reports/runtime_permission_probes.md",
            "reports/install_simulation.json",
            "reports/install_simulation.md",
            "security/permission_policy.json",
        ],
        "privacy_contract": [
            "Do not mark native_enforcement true for metadata-only fallbacks.",
            "Keep residual risks visible for targets that still rely on operator enforcement.",
        ],
    },
    "native-client-telemetry": {
        "category": "external",
        "owner": "Browser/Chrome/IDE/provider client integrator",
        "objective": "Import production metadata-only events from a real external client into the local drift loop.",
        "runbook": [
            "python3 scripts/telemetry_native_host.py . --write-launcher /tmp/yao-telemetry-host.sh --write-manifest /tmp/yao-telemetry-host.json --allowed-origin chrome-extension://<extension-id>/",
            "Install the generated native messaging manifest for the real client and send at least one accepted skill_activation or skill_output event.",
            "python3 scripts/yao.py telemetry-import . --input-jsonl .yao/telemetry_spool/external_events.jsonl --self",
            "python3 scripts/yao.py skill-atlas --workspace-root . --self",
            "python3 scripts/yao.py skill-os2-audit . --generated-at <YYYY-MM-DD> --self",
        ],
        "success_checks": [
            "reports/adoption_drift_report.json summary.source_types.external > 0",
            "reports/adoption_drift_report.json summary.adoption_sample_count > 0",
            "reports/skill_os2_audit.json item native-client-telemetry status becomes pass",
        ],
        "evidence_artifacts": [
            "reports/adoption_drift_report.json",
            "reports/adoption_drift_report.md",
            "reports/telemetry_hook_recipes.json",
            "scripts/telemetry_native_host.py",
        ],
        "privacy_contract": [
            "Telemetry must remain metadata-only and local-first.",
            "Do not package reports/telemetry_events.jsonl or any raw prompt, output, transcript, note, or message field.",
        ],
    },
}


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def build_task(item: dict[str, Any]) -> dict[str, Any]:
    template = TASK_TEMPLATES.get(
        item["key"],
        {
            "category": "review",
            "owner": "release reviewer",
            "objective": item.get("target", "Collect stronger evidence for this non-pass audit item."),
            "runbook": ["Open reports/skill_os2_audit.md and resolve the listed next action."],
            "success_checks": [f"reports/skill_os2_audit.json item {item['key']} status becomes pass"],
            "evidence_artifacts": [entry["path"] for entry in item.get("evidence", []) if entry.get("exists")],
            "privacy_contract": ["Do not add raw private user content to release evidence."],
        },
    )
    intake_runbook = [
        f"Copy evidence/world_class/templates/{item['key']}.intake.json to evidence/world_class/submissions/{item['key']}.json and fill only real evidence fields.",
        "python3 scripts/yao.py world-class-intake . --submissions-dir evidence/world_class/submissions --self",
    ]
    intake_artifacts = [
        "evidence/world_class/intake.schema.json",
        f"evidence/world_class/templates/{item['key']}.intake.json",
        "reports/world_class_evidence_intake.json",
        "reports/world_class_evidence_intake.md",
    ]
    return {
        "key": item["key"],
        "label": item["label"],
        "status": item["status"],
        "category": template["category"],
        "owner": template["owner"],
        "current": item["current"],
        "objective": template["objective"],
        "runbook": [*template["runbook"], *intake_runbook],
        "success_checks": template["success_checks"],
        "evidence_artifacts": [*template["evidence_artifacts"], *intake_artifacts],
        "privacy_contract": template["privacy_contract"],
        "audit_next_action": item["next_action"],
    }


def has_accepted_ledger_submission(skill_dir: Path, task: dict[str, Any], submissions_dir: Path) -> bool:
    path = submissions_dir / f"{task['key']}.json"
    payload, load_status = load_json_with_status(path)
    if load_status != "present":
        return False
    validation = validate_payload(payload, task, path=path, root=skill_dir, template_expected=False)
    return validation.get("status") == "pass"


def build_plan(skill_dir: Path, generated_at: str, submissions_dir: Path | None = None) -> dict[str, Any]:
    audit = build_audit(skill_dir, generated_at)
    submissions_dir = submissions_dir or (skill_dir / "evidence" / "world_class" / "submissions")
    evidence_keys = set(TASK_TEMPLATES)
    evidence_requirements = [build_task(item) for item in audit["items"] if item["key"] in evidence_keys]
    tasks = [
        task
        for task in evidence_requirements
        if task["status"] != "pass" or not has_accepted_ledger_submission(skill_dir, task, submissions_dir)
    ]
    category_counts: dict[str, int] = {}
    for task in tasks:
        category_counts[task["category"]] = category_counts.get(task["category"], 0) + 1
    audit_world_class_ready = audit["summary"].get("world_class_ready") is True
    return {
        "schema_version": "1.0",
        "ok": audit["ok"],
        "generated_at": generated_at,
        "skill_dir": rel_path(skill_dir, ROOT),
        "summary": {
            "audit_decision": audit["summary"]["decision"],
            "world_class_ready": bool(audit["summary"]["world_class_ready"]),
            "audit_world_class_ready": audit_world_class_ready,
            "ready_to_claim_world_class": False,
            "ledger_completion_required": True,
            "evidence_requirement_count": len(evidence_requirements),
            "task_count": len(tasks),
            "human_task_count": category_counts.get("human", 0),
            "external_task_count": category_counts.get("external", 0),
            "review_task_count": category_counts.get("review", 0),
            "decision": "audit-ready-ledger-required" if audit_world_class_ready and not tasks else "collect-external-evidence",
        },
        "tasks": tasks,
        "evidence_requirements": evidence_requirements,
        "source_audit": {
            "json": "reports/skill_os2_audit.json",
            "markdown": "reports/skill_os2_audit.md",
            "open_gap_count": audit["summary"]["open_gap_count"],
        },
        "artifacts": {
            "json": "reports/world_class_evidence_plan.json",
            "markdown": "reports/world_class_evidence_plan.md",
            "ledger": "reports/world_class_evidence_ledger.md",
            "intake": "reports/world_class_evidence_intake.md",
        },
    }


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# World-Class Evidence Plan",
        "",
        f"Generated at: `{plan['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- decision: `{summary['decision']}`",
        f"- audit decision: `{summary['audit_decision']}`",
        f"- ready to claim world-class: `{str(summary['ready_to_claim_world_class']).lower()}`",
        f"- ledger completion required: `{str(summary.get('ledger_completion_required', True)).lower()}`",
        f"- evidence requirements: `{summary.get('evidence_requirement_count', 0)}`",
        f"- tasks: `{summary['task_count']}`",
        f"- human tasks: `{summary['human_task_count']}`",
        f"- external tasks: `{summary['external_task_count']}`",
        "",
        "This report is an execution plan for the remaining world-class evidence gaps. It does not count a plan or source-report pass as completion; the ledger must still validate accepted submissions.",
        "",
        "## Task Table",
        "",
        "| Task | Status | Category | Owner | Current |",
        "| --- | --- | --- | --- | --- |",
    ]
    for task in plan["tasks"]:
        current = str(task["current"]).replace("|", "\\|")
        lines.append(
            f"| `{task['key']}` | `{task['status']}` | `{task['category']}` | {task['owner']} | {current} |"
        )
    if not plan["tasks"]:
        lines.append("| `none` | `pass` | `none` | none | audit gaps closed; ledger validation still required |")
    for task in plan["tasks"]:
        lines.extend(
            [
                "",
                f"## {task['label']}",
                "",
                f"- objective: {task['objective']}",
                f"- audit next action: {task['audit_next_action']}",
                "",
                "### Runbook",
                "",
            ]
        )
        for command in task["runbook"]:
            lines.append(f"- `{command}`" if command.startswith("python3 ") or "=" in command else f"- {command}")
        lines.extend(["", "### Success Checks", ""])
        lines.extend(f"- {check}" for check in task["success_checks"])
        lines.extend(["", "### Evidence Artifacts", ""])
        lines.extend(f"- `{artifact}`" for artifact in task["evidence_artifacts"])
        lines.extend(["", "### Privacy Contract", ""])
        lines.extend(f"- {item}" for item in task["privacy_contract"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a world-class evidence collection plan.")
    parser.add_argument("skill_dir")
    parser.add_argument("--output-json", default="reports/world_class_evidence_plan.json")
    parser.add_argument("--output-md", default="reports/world_class_evidence_plan.md")
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    plan = build_plan(skill_dir, args.generated_at)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    if not output_json.is_absolute():
        output_json = skill_dir / output_json
    if not output_md.is_absolute():
        output_md = skill_dir / output_md
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(plan), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

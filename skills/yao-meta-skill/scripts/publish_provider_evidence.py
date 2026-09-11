#!/usr/bin/env python3
"""Promote an adjudicated provider run into a public, identity-safe evidence surface."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from evidence_store import EvidenceError, EvidenceStore, read_json


SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Exports allowlisted provider and blind-review aggregates while keeping raw outputs, provider identifiers, and reviewer packets local."

PUBLIC_RUN_FIELDS = (
    "case_id",
    "variant",
    "provider",
    "model",
    "status",
    "execution_mode",
    "model_executed",
    "command_executed",
    "duration_ms",
    "usage",
    "score",
    "passed_count",
    "failed_count",
    "failed_assertions",
    "output_sha256",
    "redacted_summary",
    "reserved_tokens",
    "failure",
)
PRIVATE_FIELD_NAMES = {
    "raw_output_path",
    "response_id",
    "system_fingerprint",
    "controlled_submission_id",
    "packet_sha256",
    "registered_reviewer_identities",
    "reviewer",
    "reviewers",
}
PRIVATE_VALUE_PATTERNS = (
    re.compile(r"/Users/"),
    re.compile(r"/private/"),
    re.compile(r"/var/folders/"),
    re.compile(r"raw-outputs/"),
    re.compile(r"review-materials/"),
    re.compile(r"submission-[0-9a-z-]+", re.IGNORECASE),
)


def source_json(run_dir: Path, relative: str) -> dict[str, Any]:
    return read_json(run_dir / "artifacts" / relative, code="missing-public-provider-source")


def current_commit(skill_dir: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(skill_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def assert_ancestor(skill_dir: Path, commit: str) -> None:
    if not commit:
        raise EvidenceError("missing-provider-source-commit", "Provider review lineage has no source commit")
    proc = subprocess.run(
        ["git", "-C", str(skill_dir), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise EvidenceError(
            "provider-source-not-reachable",
            "Provider review source commit must remain reachable from the current branch",
        )


def model_breakdown(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for model in sorted({str(item.get("model", "")) for item in runs if item.get("model")}):
        model_runs = [item for item in runs if item.get("model") == model]
        payload[model] = {
            "call_count": len(model_runs),
            "total_tokens": sum(int(item.get("usage", {}).get("total_tokens", 0) or 0) for item in model_runs),
            "duration_ms": round(sum(float(item.get("duration_ms", 0) or 0) for item in model_runs), 2),
            "baseline_call_count": sum(item.get("variant") == "baseline" for item in model_runs),
            "with_skill_call_count": sum(item.get("variant") == "with_skill" for item in model_runs),
        }
    return payload


def sanitize_provider_report(
    provider_report: dict[str, Any],
    adjudication: dict[str, Any],
    *,
    generated_at: str,
    source_run_id: str,
    source_commit: str,
    commitment: dict[str, Any],
    export_commit: str = "",
) -> dict[str, Any]:
    summary = provider_report.get("summary", {})
    if not (
        provider_report.get("ok") is True
        and summary.get("call_count") == 40
        and summary.get("model_executed_count") == 40
        and summary.get("failure_count") == 0
        and int(summary.get("total_tokens", 250001) or 0) <= 250000
    ):
        raise EvidenceError("provider-evidence-incomplete", "Public provider evidence requires 40 successful governed calls")
    runs = provider_report.get("runs", []) if isinstance(provider_report.get("runs"), list) else []
    if len(runs) != 40:
        raise EvidenceError("provider-run-set-incomplete", "Public provider evidence requires exactly 40 run records")
    public_runs = [{key: item.get(key) for key in PUBLIC_RUN_FIELDS} for item in runs if isinstance(item, dict)]
    public_summary = dict(summary)
    public_summary["model_breakdown"] = model_breakdown(public_runs)
    return {
        "schema_version": "1.1-public",
        "ok": True,
        "status": "completed",
        "provider_matrix": provider_report.get("provider_matrix", {}),
        "summary": public_summary,
        "runs": public_runs,
        "failures": list(provider_report.get("failures", [])),
        "human_review": {
            "status": "completed",
            "required_reviewer_count": 3,
            "completed_reviewer_count": int(adjudication.get("summary", {}).get("reviewer_count", 0) or 0),
        },
        "quality_promotion": adjudication.get("quality_promotion", {}),
        "world_class_evidence": adjudication.get("world_class_evidence", {}),
        "public_evidence": {
            "generated_at": generated_at,
            "source_run_id": source_run_id,
            "source_commit": source_commit,
            "current_commit_at_export": export_commit,
            "blind_pack_sha256": commitment.get("blind_pack_sha256", ""),
            "answer_key_sha256": commitment.get("answer_key_sha256", ""),
            "raw_outputs_published": False,
            "provider_response_identifiers_published": False,
            "reviewer_packets_published": False,
            "reviewer_registry_published": False,
        },
    }


def sanitize_adjudication(
    adjudication: dict[str, Any],
    *,
    generated_at: str,
    source_run_id: str,
) -> dict[str, Any]:
    summary = adjudication.get("summary", {})
    promotion = adjudication.get("quality_promotion", {})
    if not (
        summary.get("reviewer_count") == 3
        and summary.get("pair_count") == 20
        and summary.get("failure_count") == 0
        and promotion.get("eligible") is True
    ):
        raise EvidenceError("provider-adjudication-incomplete", "Public adjudication requires an eligible three-reviewer result")
    pairs = adjudication.get("pairs", []) if isinstance(adjudication.get("pairs"), list) else []
    votes = Counter(str(role) for pair in pairs for role in pair.get("ratings", []))
    agreement = Counter(tuple(pair.get("ratings", [])) for pair in pairs)
    binding = adjudication.get("evidence_binding", {})
    return {
        "schema_version": "1.1-public",
        "summary": {
            **summary,
            "with_skill_vote_count": votes.get("with_skill", 0),
            "baseline_vote_count": votes.get("baseline", 0),
            "unanimous_with_skill_pair_count": agreement.get(("with_skill", "with_skill", "with_skill"), 0),
            "split_with_skill_pair_count": sum(
                count for ratings, count in agreement.items() if ratings.count("with_skill") == 2
            ),
            "unanimous_baseline_pair_count": agreement.get(("baseline", "baseline", "baseline"), 0),
        },
        "pairs": [
            {
                "pair_id": pair.get("pair_id"),
                "model": pair.get("model"),
                "ratings": list(pair.get("ratings", [])),
                "majority_role": pair.get("majority_role"),
            }
            for pair in pairs
        ],
        "failures": list(adjudication.get("failures", [])),
        "quality_promotion": promotion,
        "evidence_binding": {"blind_pack_sha256": binding.get("blind_pack_sha256", "")},
        "world_class_evidence": adjudication.get("world_class_evidence", {}),
        "public_evidence": {
            "generated_at": generated_at,
            "source_run_id": source_run_id,
            "reviewer_decision_reasons_published": False,
            "reviewer_identifiers_published": False,
        },
    }


def sanitize_commitment(commitment: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.1-public",
        "status": commitment.get("status", "private-answer-key-isolated"),
        "pair_count": commitment.get("pair_count"),
        "blind_pack_sha256": commitment.get("blind_pack_sha256", ""),
        "answer_key_sha256": commitment.get("answer_key_sha256", ""),
    }


def sanitize_lineage(lineage: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.1-public",
        "source_run_id": lineage.get("source_run_id", ""),
        "source_artifact_index_sha256": lineage.get("source_artifact_index_sha256", ""),
        "source_commit": lineage.get("source_commit", ""),
        "blind_pack_sha256": lineage.get("blind_pack_sha256", ""),
        "answer_key_sha256": lineage.get("answer_key_sha256", ""),
    }


def assert_public_boundary(payload: Any, prefix: str = "root") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).casefold() in PRIVATE_FIELD_NAMES:
                raise EvidenceError("private-provider-field", f"Private field reached public evidence: {prefix}.{key}")
            assert_public_boundary(value, f"{prefix}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_public_boundary(value, f"{prefix}[{index}]")
    elif isinstance(payload, str):
        for pattern in PRIVATE_VALUE_PATTERNS:
            if pattern.search(payload):
                raise EvidenceError("private-provider-value", f"Private value reached public evidence: {prefix}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish(skill_dir: Path, source_run_id: str, generated_at: str) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    store = EvidenceStore(skill_dir)
    run = store.verify_run(store.runs_dir / source_run_id)
    provider_report = source_json(run.run_dir, "reports/provider_output_evaluation.json")
    adjudication = source_json(run.run_dir, "reports/provider_output_adjudication.json")
    commitment = source_json(run.run_dir, "reports/provider_output_answer_commitment.json")
    lineage = source_json(run.run_dir, "reports/provider_review_lineage.json")
    source_commit = str(lineage.get("source_commit", ""))
    assert_ancestor(skill_dir, source_commit)
    if commitment.get("blind_pack_sha256") != adjudication.get("evidence_binding", {}).get("blind_pack_sha256"):
        raise EvidenceError("provider-evidence-binding-mismatch", "Adjudication and public commitment use different blind packs")
    payloads = {
        "provider_output_evaluation.json": sanitize_provider_report(
            provider_report,
            adjudication,
            generated_at=generated_at,
            source_run_id=source_run_id,
            source_commit=source_commit,
            commitment=commitment,
            export_commit=current_commit(skill_dir),
        ),
        "provider_output_adjudication.json": sanitize_adjudication(
            adjudication,
            generated_at=generated_at,
            source_run_id=source_run_id,
        ),
        "provider_output_answer_commitment.json": sanitize_commitment(commitment),
        "provider_review_lineage.json": sanitize_lineage(lineage),
    }
    for payload in payloads.values():
        assert_public_boundary(payload)
    for name, payload in payloads.items():
        write_json(skill_dir / "reports" / name, payload)
    return {
        "ok": True,
        "source_run_id": source_run_id,
        "source_commit": source_commit,
        "written": [f"reports/{name}" for name in payloads],
        "quality_promotion": payloads["provider_output_adjudication.json"]["quality_promotion"],
        "world_class_evidence": payloads["provider_output_adjudication.json"]["world_class_evidence"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish allowlisted aggregate evidence from an adjudicated provider run.")
    parser.add_argument("skill_dir")
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()
    try:
        payload = publish(Path(args.skill_dir), args.source_run, args.generated_at)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except EvidenceError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()

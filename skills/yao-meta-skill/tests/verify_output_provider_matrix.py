#!/usr/bin/env python3
"""Double-model execution, raw isolation, blind-pack, and three-reviewer gates."""

import json
import copy
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from adjudicate_multi_reviewer import adjudicate_reviews, canonical_sha256  # noqa: E402
from evidence_store import EvidenceError, EvidenceStore  # noqa: E402
from finalize_provider_review import finalize  # noqa: E402
from output_provider_matrix import (  # noqa: E402
    build_blind_materials,
    default_runner_for,
    execute_provider_matrix,
    load_provider_matrix,
    provider_status,
    resolve_provider_cases_path,
)
from publish_provider_evidence import (  # noqa: E402
    assert_public_boundary,
    sanitize_adjudication,
    sanitize_commitment,
    sanitize_lineage,
    sanitize_provider_report,
)


def main() -> None:
    tmp_root = ROOT / "tests" / "tmp_output_provider_matrix"
    shutil.rmtree(tmp_root, ignore_errors=True)
    run_dir = tmp_root / "run"
    matrix_path = ROOT / "evals" / "output" / "provider_matrix.json"
    matrix = load_provider_matrix(matrix_path)
    cases_path = resolve_provider_cases_path(matrix_path, matrix)
    assert matrix["evaluation_locale"] == "zh-CN", matrix
    assert matrix["holdout_cases"] == "holdout_cases.zh-CN.jsonl", matrix
    assert cases_path == ROOT / "evals" / "output" / "holdout_cases.zh-CN.jsonl", cases_path
    chinese_cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(chinese_cases) == 10, chinese_cases
    assert all("简体中文" in item["prompt"] for item in chinese_cases), chinese_cases
    english_cases_path = ROOT / "evals" / "output" / "holdout_cases.jsonl"
    english_cases = [json.loads(line) for line in english_cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(english_cases) == 10, english_cases
    assert all("简体中文" not in item["prompt"] for item in english_cases), english_cases
    assert [item["model"] for item in matrix["models"]] == ["deepseek-v4-flash", "deepseek-v4-pro"], matrix
    assert all(item["thinking"] == "disabled" and item["temperature"] == 0 for item in matrix["models"]), matrix
    assert matrix["limits"] == {"max_calls": 40, "max_total_tokens": 250000, "timeout_seconds": 60}, matrix
    invalid_matrix_path = tmp_root / "invalid-provider-matrix.json"
    invalid_matrix_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_matrix = copy.deepcopy(matrix)
    invalid_matrix["promotion"]["with_skill_min_wins"] = 14
    invalid_matrix_path.write_text(json.dumps(invalid_matrix), encoding="utf-8")
    try:
        load_provider_matrix(invalid_matrix_path)
    except ValueError as exc:
        assert "promotion contract" in str(exc), exc
    else:
        raise AssertionError("weakened provider promotion contract was accepted")
    readiness = provider_status(matrix)
    assert readiness["world_class_evidence"]["counts_as_completion"] is False, readiness
    readiness_text = json.dumps(readiness).lower()
    assert "authorization" not in readiness_text and "bearer " not in readiness_text, readiness
    foreign_skill = tmp_root / "foreign-skill"
    (foreign_skill / "evals" / "output").mkdir(parents=True)
    (foreign_skill / "SKILL.md").write_text("foreign skill", encoding="utf-8")
    default_command = default_runner_for(matrix, matrix["models"][0], foreign_skill)
    assert default_command[default_command.index("--skill-file") + 1] == str(foreign_skill / "SKILL.md"), default_command
    assert default_command[default_command.index("--input-root") + 1] == str(foreign_skill / "evals" / "output"), default_command

    fake_runner = ROOT / "tests" / "fixtures" / "fake_deepseek_output_runner.py"

    def runner_for(model: dict) -> list[str]:
        return [sys.executable, str(fake_runner), "--model", model["model"]]

    report = execute_provider_matrix(
        cases_path,
        matrix,
        run_dir,
        runner_for=runner_for,
    )
    assert report["summary"]["case_count"] == 10, report
    assert report["summary"]["call_count"] == 40, report
    assert report["summary"]["model_executed_count"] == 40, report
    assert report["summary"]["total_tokens"] == 1200, report
    assert report["summary"]["failure_count"] == 0, report
    assert report["quality_promotion"]["status"] == "awaiting-human-review", report
    assert report["world_class_evidence"]["counts_as_completion"] is False, report
    raw_files = sorted((run_dir / "raw-outputs").rglob("*.txt"))
    assert len(raw_files) == 40, raw_files
    serialized = json.dumps(report, ensure_ascii=False)
    assert "Write a short direct answer" not in serialized, report
    assert all(item["output_sha256"] and item["redacted_summary"] for item in report["runs"]), report
    assert all(not Path(item["raw_output_path"]).is_absolute() for item in report["runs"]), report

    blind_pack, answer_key, templates = build_blind_materials(report, run_dir)
    assert blind_pack["summary"]["pair_count"] == 20, blind_pack
    assert answer_key["summary"]["pair_count"] == 20, answer_key
    assert set(templates) == {"reviewer-a", "reviewer-b", "reviewer-c"}, templates
    assert all(len(template["decisions"]) == 20 for template in templates.values()), templates
    assert all("expected_winner_variant" not in json.dumps(template) for template in templates.values()), templates
    assert "Write a short direct answer" not in json.dumps(blind_pack, ensure_ascii=False), blind_pack
    assert all("variant_a" not in pair and "variant_b" not in pair for pair in blind_pack["pairs"]), blind_pack
    assert all((run_dir / pair["variant_a_raw_output"]).is_file() for pair in blind_pack["pairs"]), blind_pack
    assert all((run_dir / pair["variant_b_raw_output"]).is_file() for pair in blind_pack["pairs"]), blind_pack
    assert all("baseline" not in pair["variant_a_raw_output"] and "with_skill" not in pair["variant_a_raw_output"] for pair in blind_pack["pairs"]), blind_pack
    assert all("baseline" not in pair["variant_b_raw_output"] and "with_skill" not in pair["variant_b_raw_output"] for pair in blind_pack["pairs"]), blind_pack
    assert len(answer_key["blind_pack_sha256"]) == 64, answer_key
    assert all(template["review_integrity"]["blind_pack_sha256"] == answer_key["blind_pack_sha256"] for template in templates.values()), templates
    assert all(template["reviewer_attestation"]["independent_blind_review_completed"] is False for template in templates.values()), templates

    tampered_path = run_dir / report["runs"][0]["raw_output_path"]
    original_output = tampered_path.read_text(encoding="utf-8")
    tampered_path.write_text("tampered after provider execution", encoding="utf-8")
    try:
        build_blind_materials(report, run_dir)
    except ValueError as exc:
        assert "hash mismatch" in str(exc), exc
    else:
        raise AssertionError("tampered raw output produced blind-review materials")
    tampered_path.write_text(original_output, encoding="utf-8")

    linked_output = tmp_root / "linked-output.txt"
    linked_output.write_text(original_output, encoding="utf-8")
    tampered_path.unlink()
    tampered_path.symlink_to(linked_output)
    try:
        build_blind_materials(report, run_dir)
    except ValueError as exc:
        assert "unsafe raw output" in str(exc), exc
    else:
        raise AssertionError("symlinked raw output produced blind-review materials")
    tampered_path.unlink()
    tampered_path.write_text(original_output, encoding="utf-8")

    decisions = []
    for reviewer in ("reviewer-a", "reviewer-b", "reviewer-c"):
        decisions.append(
            {
                "reviewer": reviewer,
                "review_integrity": {"blind_pack_sha256": answer_key["blind_pack_sha256"]},
                "reviewer_attestation": {"independent_blind_review_completed": True},
                "decisions": [
                    {
                        "pair_id": item["pair_id"],
                        "winner_variant": "A" if item["variant_a_role"] == "with_skill" else "B",
                        "critical_failure": False,
                        "reason": "The selected answer satisfies the visible rubric.",
                    }
                    for item in answer_key["answers"]
                ],
            }
        )
    for index, packet in enumerate(decisions):
        packet["reviewer_attestation"].update(
            {"submitted_at": f"2026-08-12T00:0{index}:00Z", "controlled_submission_id": f"submission-{index}"}
        )
    registry = {
        "reviewers": {
            packet["reviewer"]: {
                "identity_verified": True,
                "packet_sha256": canonical_sha256(packet),
                "submitted_at": packet["reviewer_attestation"]["submitted_at"],
                "controlled_submission_id": packet["reviewer_attestation"]["controlled_submission_id"],
            }
            for packet in decisions
        }
    }
    adjudication = adjudicate_reviews(answer_key, decisions, registry)
    summary = adjudication["summary"]
    assert summary["reviewer_count"] == 3, adjudication
    assert summary["with_skill_pair_wins"] == 20, adjudication
    assert summary["model_with_skill_wins"] == {"deepseek-v4-flash": 10, "deepseek-v4-pro": 10}, adjudication
    assert summary["critical_failure_count"] == 0, adjudication
    assert summary["fleiss_kappa"] == 1.0, adjudication
    assert adjudication["quality_promotion"]["eligible"] is True, adjudication
    assert adjudication["world_class_evidence"]["counts_as_completion"] is False, adjudication

    public_commitment = {
        "schema_version": "1.0",
        "status": "private-answer-key-isolated",
        "pair_count": 20,
        "blind_pack_sha256": answer_key["blind_pack_sha256"],
        "answer_key_sha256": canonical_sha256(answer_key),
    }
    public_report = sanitize_provider_report(
        report,
        adjudication,
        generated_at="2026-08-16",
        source_run_id="provider-source",
        source_commit="a" * 40,
        commitment=public_commitment,
        export_commit="a" * 40,
    )
    public_adjudication = sanitize_adjudication(
        adjudication,
        generated_at="2026-08-16",
        source_run_id="provider-source",
    )
    public_lineage = sanitize_lineage(
        {
            "source_run_id": "provider-source",
            "source_artifact_index_sha256": "b" * 64,
            "source_commit": "a" * 40,
            "blind_pack_sha256": answer_key["blind_pack_sha256"],
            "answer_key_sha256": canonical_sha256(answer_key),
        }
    )
    for public_payload in (public_report, public_adjudication, sanitize_commitment(public_commitment), public_lineage):
        assert_public_boundary(public_payload)
        serialized_public = json.dumps(public_payload, ensure_ascii=False)
        assert "raw_output_path" not in serialized_public, serialized_public
        assert "controlled_submission_id" not in serialized_public, serialized_public
        assert "registered_reviewer_identities" not in serialized_public, serialized_public
    assert public_report["summary"]["model_breakdown"]["deepseek-v4-flash"]["call_count"] == 20, public_report
    assert public_adjudication["summary"]["with_skill_vote_count"] == 60, public_adjudication
    assert public_adjudication["summary"]["unanimous_with_skill_pair_count"] == 20, public_adjudication

    pending = adjudicate_reviews(answer_key, decisions[:2], registry)
    assert pending["quality_promotion"]["status"] == "pending", pending
    assert pending["quality_promotion"]["eligible"] is False, pending

    unattested = copy.deepcopy(decisions)
    unattested[0]["reviewer_attestation"]["independent_blind_review_completed"] = False
    unattested_result = adjudicate_reviews(answer_key, unattested, registry)
    assert unattested_result["quality_promotion"]["eligible"] is False, unattested_result
    assert any("attestation" in failure for failure in unattested_result["failures"]), unattested_result

    duplicate = copy.deepcopy(decisions)
    duplicate[0]["decisions"].append(copy.deepcopy(duplicate[0]["decisions"][0]))
    duplicate_result = adjudicate_reviews(answer_key, duplicate, registry)
    assert duplicate_result["quality_promotion"]["eligible"] is False, duplicate_result
    assert any("duplicate" in failure for failure in duplicate_result["failures"]), duplicate_result

    limited_matrix = copy.deepcopy(matrix)
    limited_matrix["limits"]["max_calls"] = 1
    limited = execute_provider_matrix(
        cases_path,
        limited_matrix,
        tmp_root / "limited-run",
        runner_for=runner_for,
    )
    assert limited["summary"]["call_count"] == 1, limited
    assert limited["summary"]["failure_count"] == 1, limited
    assert any(not item["command_executed"] and "budget exhausted" in item["failure"] for item in limited["runs"]), limited
    try:
        build_blind_materials(limited, tmp_root / "limited-run")
    except ValueError as exc:
        assert "40 successful" in str(exc), exc
    else:
        raise AssertionError("partial provider run produced blind materials")

    untrusted_runner = ROOT / "tests" / "fixtures" / "fake_untrusted_output_runner.py"
    untrusted = execute_provider_matrix(
        cases_path,
        matrix,
        tmp_root / "untrusted-run",
        runner_for=lambda _model: [sys.executable, str(untrusted_runner)],
    )
    assert untrusted["summary"]["failure_count"] > 0, untrusted
    try:
        build_blind_materials(untrusted, tmp_root / "untrusted-run")
    except ValueError:
        pass
    else:
        raise AssertionError("untrusted provider metadata produced blind materials")

    high_usage = execute_provider_matrix(
        cases_path,
        matrix,
        tmp_root / "high-usage-run",
        runner_for=lambda model: [sys.executable, str(fake_runner), "--model", model["model"], "--total-tokens", "249000"],
    )
    assert high_usage["summary"]["call_count"] == 1, high_usage
    assert high_usage["summary"]["total_tokens"] <= 250000, high_usage

    lifecycle_skill = tmp_root / "lifecycle-skill"
    (lifecycle_skill / "reports").mkdir(parents=True)
    (lifecycle_skill / "SKILL.md").write_text(
        '---\nname: lifecycle-skill\ndescription: "Exercise provider review finalization."\n---\n',
        encoding="utf-8",
    )
    (lifecycle_skill / "manifest.json").write_text(
        json.dumps({"name": "lifecycle-skill", "version": "1.0.0", "updated_at": "2026-08-12"}),
        encoding="utf-8",
    )
    (lifecycle_skill / "reports" / "quality.json").write_text('{"ok": true}\n', encoding="utf-8")
    (lifecycle_skill / ".gitignore").write_text(".yao/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=lifecycle_skill, check=True)
    subprocess.run(["git", "config", "user.name", "Provider Review Test"], cwd=lifecycle_skill, check=True)
    subprocess.run(["git", "config", "user.email", "provider-review@example.test"], cwd=lifecycle_skill, check=True)
    subprocess.run(["git", "add", "."], cwd=lifecycle_skill, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=lifecycle_skill, check=True)
    lifecycle_store = EvidenceStore(lifecycle_skill)
    source_run = lifecycle_store.build("provider-source")
    lifecycle_report = execute_provider_matrix(
        cases_path,
        matrix,
        source_run.run_dir,
        runner_for=runner_for,
    )
    lifecycle_blind, lifecycle_answers, lifecycle_templates = build_blind_materials(
        lifecycle_report,
        source_run.run_dir,
    )
    lifecycle_store.add_private_json(source_run, "provider_output_answer_key.json", lifecycle_answers)
    for relative, payload in (
        ("reports/provider_output_evaluation.json", lifecycle_report),
        ("reports/provider_output_blind_pack.json", lifecycle_blind),
        (
            "reports/provider_output_answer_commitment.json",
            {
                "schema_version": "1.0",
                "blind_pack_sha256": lifecycle_answers["blind_pack_sha256"],
                "answer_key_sha256": canonical_sha256(lifecycle_answers),
            },
        ),
    ):
        source_run = lifecycle_store.add_json_artifact(source_run, relative, payload)
    packet_paths = []
    lifecycle_packets = []
    for index, reviewer in enumerate(("reviewer-a", "reviewer-b", "reviewer-c")):
        packet = copy.deepcopy(lifecycle_templates[reviewer])
        packet["reviewer_attestation"] = {
            "independent_blind_review_completed": True,
            "submitted_at": f"2026-08-12T01:0{index}:00Z",
            "controlled_submission_id": f"lifecycle-{index}",
        }
        packet["decisions"] = [
            {
                "pair_id": item["pair_id"],
                "winner_variant": "A" if item["variant_a_role"] == "with_skill" else "B",
                "critical_failure": False,
                "reason": "The selected response satisfies the visible rubric.",
            }
            for item in lifecycle_answers["answers"]
        ]
        packet_path = tmp_root / f"{reviewer}.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        packet_paths.append(packet_path)
        lifecycle_packets.append(packet)
    lifecycle_registry = {
        "reviewers": {
            packet["reviewer"]: {
                "identity_verified": True,
                "packet_sha256": canonical_sha256(packet),
                "submitted_at": packet["reviewer_attestation"]["submitted_at"],
                "controlled_submission_id": packet["reviewer_attestation"]["controlled_submission_id"],
            }
            for packet in lifecycle_packets
        }
    }
    registry_path = tmp_root / "reviewer-registry.json"
    registry_path.write_text(json.dumps(lifecycle_registry), encoding="utf-8")
    final_payload = finalize(
        lifecycle_skill,
        source_run.run_id,
        packet_paths,
        registry_path,
        "final-review",
        False,
    )
    assert final_payload["quality_promotion"]["eligible"] is True, final_payload
    resumed = finalize(
        lifecycle_skill,
        source_run.run_id,
        packet_paths,
        registry_path,
        "final-review",
        False,
        True,
    )
    assert resumed["run_id"] == "final-review", resumed
    final_run = lifecycle_store.verify_run(lifecycle_store.runs_dir / "final-review")
    final_paths = {item["path"] for item in final_run.artifact_index["artifacts"]}
    assert "reports/provider_output_adjudication.json" in final_paths, final_paths
    assert not (final_run.run_dir / "private" / "provider_output_answer_key.json").exists(), final_run.run_dir
    blinded_path = source_run.run_dir / lifecycle_blind["pairs"][0]["variant_a_raw_output"]
    blinded_path.write_text("tampered reviewer material", encoding="utf-8")
    try:
        finalize(lifecycle_skill, source_run.run_id, packet_paths, registry_path, "tampered-review", False)
    except EvidenceError as exc:
        assert exc.code == "blind-output-hash-mismatch", exc
    else:
        raise AssertionError("tampered blinded output reached finalization")

    print(json.dumps({"ok": True}, indent=2))


if __name__ == "__main__":
    main()

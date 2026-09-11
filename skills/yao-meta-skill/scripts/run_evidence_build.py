#!/usr/bin/env python3
"""Build an isolated evidence run and optionally publish it transactionally."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from evidence_store import EvidenceError, EvidenceStore, read_json
from output_provider_matrix import (
    canonical_sha256,
    build_blind_materials,
    execute_provider_matrix,
    load_provider_matrix,
    provider_status,
    resolve_provider_cases_path,
)


ROOT = Path(__file__).resolve().parent.parent
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def completed_public_provider_evidence(skill_dir: Path, matrix: dict) -> dict | None:
    path = skill_dir / "reports" / "provider_output_evaluation.json"
    if not path.is_file():
        return None
    try:
        report = read_json(path, code="invalid-public-provider-evidence")
    except EvidenceError:
        return None
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    public = report.get("public_evidence", {}) if isinstance(report.get("public_evidence"), dict) else {}
    runs = report.get("runs", []) if isinstance(report.get("runs"), list) else []
    expected_models = {str(item.get("model", "")) for item in matrix.get("models", []) if item.get("model")}
    observed_models = {str(item.get("model", "")) for item in runs if isinstance(item, dict)}
    variants = [str(item.get("variant", "")) for item in runs if isinstance(item, dict)]
    if not (
        report.get("schema_version") == "1.1-public"
        and report.get("ok") is True
        and report.get("status") == "completed"
        and summary.get("call_count") == 40
        and summary.get("model_executed_count") == 40
        and summary.get("failure_count") == 0
        and int(summary.get("total_tokens", 250001) or 0) <= int(matrix["limits"]["max_total_tokens"])
        and len(runs) == 40
        and expected_models
        and observed_models == expected_models
        and variants.count("baseline") == 20
        and variants.count("with_skill") == 20
        and all(item.get("model_executed") is True for item in runs if isinstance(item, dict))
        and all(SHA256_RE.fullmatch(str(item.get("output_sha256", ""))) for item in runs if isinstance(item, dict))
        and public.get("raw_outputs_published") is False
        and public.get("provider_response_identifiers_published") is False
        and public.get("reviewer_packets_published") is False
        and public.get("reviewer_registry_published") is False
        and SHA256_RE.fullmatch(str(public.get("blind_pack_sha256", "")))
        and SHA256_RE.fullmatch(str(public.get("answer_key_sha256", "")))
    ):
        return None
    return report


def provider_evidence(store: EvidenceStore, run, skill_dir: Path):
    matrix_path = skill_dir / "evals" / "output" / "provider_matrix.json"
    if not matrix_path.exists():
        return run, {"status": "not-configured", "quality_promotion": {"status": "pending", "eligible": False}}
    matrix = load_provider_matrix(matrix_path)
    cases_path = resolve_provider_cases_path(matrix_path, matrix)
    api_key_env = str(matrix["api_key_env"])
    if not os.environ.get(api_key_env):
        completed_public = completed_public_provider_evidence(skill_dir, matrix)
        if completed_public is not None:
            return run, completed_public
        status = provider_status(matrix)
        return store.add_json_artifact(run, "reports/provider_output_evaluation.json", status), status
    report = execute_provider_matrix(cases_path, matrix, run.run_dir, skill_dir=skill_dir)
    artifacts = [("reports/provider_output_evaluation.json", report)]
    if report.get("summary", {}).get("failure_count") == 0 and len(report.get("runs", [])) == 40:
        blind_pack, answer_key, templates = build_blind_materials(report, run.run_dir)
        store.add_private_json(run, "provider_output_answer_key.json", answer_key)
        artifacts.extend(
            [
                ("reports/provider_output_blind_pack.json", blind_pack),
                (
                    "reports/provider_output_answer_commitment.json",
                    {
                        "schema_version": "1.0",
                        "run_id": run.run_id,
                        "blind_pack_sha256": answer_key["blind_pack_sha256"],
                        "answer_key_sha256": canonical_sha256(answer_key),
                        "pair_count": answer_key["summary"]["pair_count"],
                        "status": "private-answer-key-isolated",
                    },
                ),
                ("reports/provider_review_reviewer-a.json", templates["reviewer-a"]),
                ("reports/provider_review_reviewer-b.json", templates["reviewer-b"]),
                ("reports/provider_review_reviewer-c.json", templates["reviewer-c"]),
            ]
        )
    for relative, payload in artifacts:
        run = store.add_json_artifact(run, relative, payload)
    return run, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated, hash-indexed evidence for an agent skill.")
    parser.add_argument("skill_dir")
    parser.add_argument("--run-id")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--recover", action="store_true", help="Recover a pending publish transaction and exit.")
    args = parser.parse_args()

    try:
        store = EvidenceStore(Path(args.skill_dir))
        if args.recover:
            recovered = store.recover()
            print(json.dumps({"ok": True, "mode": "recovered", "recovered_previous_publish": recovered}, indent=2))
            return
        if store.transaction_path.exists() and not args.publish:
            raise EvidenceError("recovery-required", "A publish transaction is pending; rerun with --recover or --publish")
        recovered = store.recover() if store.transaction_path.exists() else False
        if args.publish:
            store.assert_clean()
        run = store.build(args.run_id)
        run, provider = provider_evidence(store, run, store.skill_dir)
        release = store.publish(run) if args.publish else None
        payload = {
            "ok": True,
            "mode": "published" if release else "dry-run",
            "run_id": run.run_id,
            "skill_name": run.manifest["skill_name"],
            "run_dir": str(run.run_dir),
            "artifact_count": run.manifest["artifact_count"],
            "provider_evidence_status": provider.get("status", provider.get("quality_promotion", {}).get("status", "pending")),
            "release_dir": str(release) if release else None,
            "recovered_previous_publish": recovered,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except EvidenceError as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Finalize one provider run with three controlled blind-review packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adjudicate_multi_reviewer import adjudicate_reviews, canonical_sha256
from evidence_store import EvidenceError, EvidenceStore, read_json, sha256_file


SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Binds three controlled reviewer submissions to one immutable provider run without rerunning the model matrix."


def source_json(source_run: Path, relative: str) -> dict:
    return read_json(source_run / "artifacts" / relative, code="missing-provider-review-source")


def validate_blinded_outputs(source_run: Path, blind_pack: dict) -> None:
    for pair in blind_pack.get("pairs", []):
        for label in ("a", "b"):
            relative = Path(str(pair.get(f"variant_{label}_raw_output", "")))
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "review-materials":
                raise EvidenceError("unsafe-blind-output", f"Unsafe blinded output path: {relative}")
            path = source_run / relative
            cursor = source_run
            for part in relative.parts:
                cursor /= part
                if cursor.is_symlink():
                    raise EvidenceError("unsafe-blind-output", f"Blinded output traverses a symlink: {relative}")
            if not path.is_file() or sha256_file(path) != pair.get(f"variant_{label}_sha256"):
                raise EvidenceError("blind-output-hash-mismatch", f"Blinded output hash mismatch: {relative}")


def finalize(
    skill_dir: Path,
    source_run_id: str,
    decision_paths: list[Path],
    registry_path: Path,
    final_run_id: str | None,
    publish: bool,
    resume: bool = False,
) -> dict:
    store = EvidenceStore(skill_dir)
    if publish:
        store.assert_clean()
    source_run = store.verify_run(store.runs_dir / source_run_id)
    current = store._git_state()
    source_state = source_run.manifest.get("source", {})
    if source_state.get("dirty") is not False or source_state.get("commit") != current.get("commit"):
        raise EvidenceError("review-source-mismatch", "Provider review source run does not match the current clean source commit")
    answer_key = read_json(
        source_run.run_dir / "private" / "provider_output_answer_key.json",
        code="missing-private-answer-key",
    )
    blind_pack = source_json(source_run.run_dir, "reports/provider_output_blind_pack.json")
    commitment = source_json(source_run.run_dir, "reports/provider_output_answer_commitment.json")
    provider_report = source_json(source_run.run_dir, "reports/provider_output_evaluation.json")
    if canonical_sha256(blind_pack) != answer_key.get("blind_pack_sha256"):
        raise EvidenceError("blind-pack-hash-mismatch", "Blind pack does not match the private answer key")
    if commitment.get("answer_key_sha256") != canonical_sha256(answer_key):
        raise EvidenceError("answer-key-hash-mismatch", "Private answer key does not match its public commitment")
    validate_blinded_outputs(source_run.run_dir, blind_pack)
    packets = [read_json(path, code="invalid-review-packet") for path in decision_paths]
    registry = read_json(registry_path, code="invalid-reviewer-registry")
    adjudication = adjudicate_reviews(answer_key, packets, registry)
    if adjudication.get("failures"):
        raise EvidenceError("review-adjudication-invalid", "; ".join(adjudication["failures"]))
    existing_run = store.runs_dir / str(final_run_id or "")
    if resume and final_run_id and existing_run.is_dir():
        final_run = store.verify_run(existing_run)
        final_source = final_run.manifest.get("source", {})
        if final_source.get("dirty") is not False or final_source.get("commit") != current.get("commit"):
            raise EvidenceError("review-resume-mismatch", "Review finalization run does not match the current clean source commit")
    else:
        final_run = store.build(final_run_id)
    artifacts = [
        ("reports/provider_output_evaluation.json", provider_report),
        ("reports/provider_output_blind_pack.json", blind_pack),
        ("reports/provider_output_answer_commitment.json", commitment),
        ("reports/provider_reviewer_registry.json", registry),
        ("reports/provider_output_adjudication.json", adjudication),
        (
            "reports/provider_review_lineage.json",
            {
                "schema_version": "1.0",
                "source_run_id": source_run.run_id,
                "source_artifact_index_sha256": source_run.manifest["artifact_index_sha256"],
                "source_commit": source_state.get("commit"),
                "blind_pack_sha256": answer_key["blind_pack_sha256"],
                "answer_key_sha256": commitment["answer_key_sha256"],
            },
        ),
    ]
    for packet in packets:
        artifacts.append((f"reports/provider_review_{packet.get('reviewer', '')}.json", packet))
    for relative, payload in artifacts:
        final_run = store.add_json_artifact(final_run, relative, payload)
    release = store.publish(final_run) if publish else None
    return {
        "ok": True,
        "mode": "published" if release else "dry-run",
        "source_run_id": source_run.run_id,
        "run_id": final_run.run_id,
        "release_dir": str(release) if release else None,
        "quality_promotion": adjudication["quality_promotion"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize a fixed provider run with three controlled reviewer packets.")
    parser.add_argument("skill_dir")
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--decisions", action="append", required=True)
    parser.add_argument("--reviewer-registry", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted named finalization run.")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        payload = finalize(
            Path(args.skill_dir).resolve(),
            args.source_run,
            [Path(path).resolve() for path in args.decisions],
            Path(args.reviewer_registry).resolve(),
            args.run_id,
            args.publish,
            args.resume,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except EvidenceError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adjudicate three independent blind-review packets for provider output eval."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCRIPT_INTERFACE = "cli"
SCRIPT_INTERFACE_REASON = "Adjudicates three independent provider-output review packets and writes promotion evidence."


def fleiss_kappa(rows: list[list[str]]) -> float | None:
    if not rows or any(len(row) < 2 for row in rows):
        return None
    categories = ("with_skill", "baseline")
    reviewer_count = len(rows[0])
    observed = []
    totals = Counter()
    for row in rows:
        counts = Counter(row)
        totals.update(counts)
        observed.append(sum(counts[category] ** 2 for category in categories) - reviewer_count)
    p_bar = sum(value / (reviewer_count * (reviewer_count - 1)) for value in observed) / len(rows)
    total_ratings = len(rows) * reviewer_count
    p_e = sum((totals[category] / total_ratings) ** 2 for category in categories)
    if p_e == 1:
        return 1.0
    return round((p_bar - p_e) / (1 - p_e), 4)


EXPECTED_REVIEWERS = {"reviewer-a", "reviewer-b", "reviewer-c"}


def canonical_sha256(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def adjudicate_reviews(
    answer_key: dict[str, Any],
    decision_packets: list[dict[str, Any]],
    reviewer_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    answers = {item["pair_id"]: item for item in answer_key.get("answers", [])}
    promotion = answer_key.get("promotion", {}) if isinstance(answer_key.get("promotion"), dict) else {}
    thresholds = {
        "reviewer_count": int(promotion.get("reviewer_count", 3)),
        "pair_count": int(promotion.get("pair_count", 20)),
        "with_skill_min_wins": int(promotion.get("with_skill_min_wins", 15)),
        "per_model_min_wins": int(promotion.get("per_model_min_wins", 7)),
        "critical_failure_max": int(promotion.get("critical_failure_max", 0)),
        "fleiss_kappa_min": float(promotion.get("fleiss_kappa_min", 0.4)),
    }
    required_reviewers = thresholds["reviewer_count"]
    failures: list[str] = []
    reviewer_maps: list[dict[str, dict[str, Any]]] = []
    reviewer_names: set[str] = set()
    registered = reviewer_registry.get("reviewers", {}) if isinstance(reviewer_registry, dict) else {}
    for packet in decision_packets:
        reviewer = str(packet.get("reviewer", "")).strip()
        if reviewer not in EXPECTED_REVIEWERS or reviewer in reviewer_names:
            failures.append("reviewers must be the unique registered identities reviewer-a, reviewer-b, and reviewer-c")
        reviewer_names.add(reviewer)
        integrity = packet.get("review_integrity", {}) if isinstance(packet.get("review_integrity"), dict) else {}
        if integrity.get("blind_pack_sha256") != answer_key.get("blind_pack_sha256"):
            failures.append(f"blind-pack commitment mismatch: {reviewer}")
        attestation = packet.get("reviewer_attestation", {}) if isinstance(packet.get("reviewer_attestation"), dict) else {}
        if attestation.get("independent_blind_review_completed") is not True:
            failures.append(f"independent-review attestation is missing: {reviewer}")
        if not str(attestation.get("submitted_at", "")).strip() or not str(attestation.get("controlled_submission_id", "")).strip():
            failures.append(f"controlled submission attestation is incomplete: {reviewer}")
        identity = registered.get(reviewer, {}) if isinstance(registered, dict) else {}
        if (
            not isinstance(identity, dict)
            or identity.get("identity_verified") is not True
            or identity.get("packet_sha256") != canonical_sha256(packet)
            or identity.get("submitted_at") != attestation.get("submitted_at")
            or identity.get("controlled_submission_id") != attestation.get("controlled_submission_id")
        ):
            failures.append(f"controlled reviewer identity verification failed: {reviewer}")
        decision_list = packet.get("decisions", []) if isinstance(packet.get("decisions"), list) else []
        decision_ids = [str(item.get("pair_id", "")) for item in decision_list if isinstance(item, dict)]
        if len(decision_ids) != len(set(decision_ids)):
            failures.append(f"duplicate pair decision: {reviewer}")
        if set(decision_ids) != set(answers):
            failures.append(f"review packet must cover the exact blind pair set: {reviewer}")
        decisions = {str(item.get("pair_id", "")): item for item in decision_list if isinstance(item, dict)}
        reviewer_maps.append(decisions)
    if reviewer_names != EXPECTED_REVIEWERS:
        failures.append("all three registered reviewer identities are required")
    rows: list[list[str]] = []
    pair_results = []
    model_wins = Counter()
    critical_failure_count = 0
    with_skill_pair_wins = 0
    for pair_id, answer in answers.items():
        ratings = []
        for decisions in reviewer_maps:
            decision = decisions.get(pair_id, {})
            selected = str(decision.get("winner_variant", "")).upper()
            if selected not in {"A", "B"} or not str(decision.get("reason", "")).strip():
                failures.append(f"incomplete decision: {pair_id}")
                continue
            if not isinstance(decision.get("critical_failure"), bool):
                failures.append(f"critical_failure must be boolean: {pair_id}")
                continue
            selected_role = answer["variant_a_role"] if selected == "A" else answer["variant_b_role"]
            ratings.append(selected_role)
            critical_failure_count += int(bool(decision.get("critical_failure")))
        rows.append(ratings)
        majority_role = Counter(ratings).most_common(1)[0][0] if ratings else ""
        if majority_role == "with_skill":
            with_skill_pair_wins += 1
            model_wins[answer["model"]] += 1
        pair_results.append({"pair_id": pair_id, "model": answer["model"], "ratings": ratings, "majority_role": majority_role})
    kappa = fleiss_kappa(rows) if len(reviewer_maps) == required_reviewers and not failures else None
    eligible = (
        len(reviewer_maps) == required_reviewers
        and len(answers) == thresholds["pair_count"]
        and not failures
        and with_skill_pair_wins >= thresholds["with_skill_min_wins"]
        and all(model_wins[model] >= thresholds["per_model_min_wins"] for model in ("deepseek-v4-flash", "deepseek-v4-pro"))
        and critical_failure_count <= thresholds["critical_failure_max"]
        and kappa is not None
        and kappa >= thresholds["fleiss_kappa_min"]
    )
    return {
        "schema_version": "1.0",
        "summary": {
            "reviewer_count": len(reviewer_maps),
            "pair_count": len(answers),
            "with_skill_pair_wins": with_skill_pair_wins,
            "model_with_skill_wins": dict(sorted(model_wins.items())),
            "critical_failure_count": critical_failure_count,
            "fleiss_kappa": kappa,
            "failure_count": len(failures),
        },
        "pairs": pair_results,
        "failures": failures,
        "quality_promotion": {
            "status": "eligible" if eligible else "pending",
            "eligible": eligible,
            "thresholds": thresholds,
        },
        "evidence_binding": {
            "blind_pack_sha256": answer_key.get("blind_pack_sha256", ""),
            "registered_reviewer_identities": sorted(reviewer_names & EXPECTED_REVIEWERS),
        },
        "world_class_evidence": {
            "status": "pending",
            "counts_as_completion": False,
            "reason": "Internal blind-review promotion does not close the world-class ledger.",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    promotion = payload["quality_promotion"]
    return "\n".join(
        [
            "# Provider Output Multi-Reviewer Adjudication",
            "",
            f"- reviewers: `{summary['reviewer_count']}/3`",
            f"- pairs: `{summary['pair_count']}/20`",
            f"- with-skill pair wins: `{summary['with_skill_pair_wins']}/20`",
            f"- per-model wins: `{json.dumps(summary['model_with_skill_wins'], ensure_ascii=False)}`",
            f"- critical failures: `{summary['critical_failure_count']}`",
            f"- Fleiss' kappa: `{summary['fleiss_kappa']}`",
            f"- quality promotion: `{promotion['status']}`",
            "- world-class ledger: `pending`",
            "",
            "This adjudication is internal quality-promotion evidence and does not close the world-class ledger.",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Adjudicate three independent provider-output blind reviews.")
    parser.add_argument("--answer-key", required=True)
    parser.add_argument("--decisions", action="append", required=True)
    parser.add_argument("--reviewer-registry", required=True)
    parser.add_argument("--output-json", default="reports/provider_output_adjudication.json")
    parser.add_argument("--output-md", default="reports/provider_output_adjudication.md")
    args = parser.parse_args()
    answer_key = json.loads(Path(args.answer_key).read_text(encoding="utf-8"))
    packets = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.decisions]
    registry = json.loads(Path(args.reviewer_registry).read_text(encoding="utf-8"))
    payload = adjudicate_reviews(answer_key, packets, registry)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not payload["failures"] else 2)


if __name__ == "__main__":
    main()

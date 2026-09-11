#!/usr/bin/env python3
"""Review Studio action-mirror checks for evidence consistency."""

from __future__ import annotations

from typing import Any

from evidence_consistency_core import REQUIRED_REPORTS


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Keeps Review Studio mirror validation isolated from the evidence-consistency orchestrator."


def build_review_studio_gate_action_mirror_check(review_studio: dict[str, Any]) -> dict[str, Any]:
    gates = review_studio.get("gates", []) if isinstance(review_studio.get("gates", []), list) else []
    actions = review_studio.get("review_actions", []) if isinstance(review_studio.get("review_actions", []), list) else []
    non_pass_gates = [gate for gate in gates if isinstance(gate, dict) and gate.get("status") != "pass"]
    pass_gates = [gate for gate in gates if isinstance(gate, dict) and gate.get("status") == "pass"]
    actions_by_gate = {
        str(action.get("gate_key", "")): action
        for action in actions
        if isinstance(action, dict) and str(action.get("gate_key", ""))
    }
    expected = {
        "non_pass_gate_keys": sorted(str(gate.get("key", "")) for gate in non_pass_gates),
        "action_gate_keys": sorted(str(gate.get("key", "")) for gate in non_pass_gates),
        "pass_gate_action_ids_empty": True,
        "gate_action_mirrors": {
            str(gate.get("key", "")): {
                "review_action_id": f"review-action-{gate.get('key', '')}",
                "review_action_status": gate.get("status", ""),
                "title_present": True,
                "next_step_present": True,
                "reason_present": True,
                "source_ref_present": True,
                "verification_command_present": True,
            }
            for gate in non_pass_gates
        },
    }
    actual = {
        "non_pass_gate_keys": sorted(str(gate.get("key", "")) for gate in non_pass_gates),
        "action_gate_keys": sorted(actions_by_gate),
        "pass_gate_action_ids_empty": all(not gate.get("review_action_id") for gate in pass_gates),
        "gate_action_mirrors": {},
    }
    for gate in non_pass_gates:
        key = str(gate.get("key", ""))
        action = actions_by_gate.get(key, {})
        actual["gate_action_mirrors"][key] = {
            "review_action_id": gate.get("review_action_id", ""),
            "review_action_status": gate.get("review_action_status", ""),
            "title_present": bool(gate.get("review_action_title")),
            "next_step_present": bool(gate.get("review_action_next_step")),
            "reason_present": bool(gate.get("review_action_reason")),
            "source_ref_present": bool(gate.get("review_action_source_ref_count")),
            "verification_command_present": bool(gate.get("review_action_verification_command")),
            "top_level_action_id": action.get("action_id", ""),
            "top_level_action_status": action.get("status", ""),
            "top_level_title_present": bool(action.get("title")),
            "top_level_next_step_present": bool(action.get("next_step")),
            "top_level_reason_present": bool(action.get("reason")),
            "top_level_source_ref_present": bool(action.get("source_refs")),
            "top_level_verification_command_present": bool(action.get("verification_command")),
        }
        expected["gate_action_mirrors"][key].update(
            {
                "top_level_action_id": f"review-action-{key}",
                "top_level_action_status": gate.get("status", ""),
                "top_level_title_present": True,
                "top_level_next_step_present": True,
                "top_level_reason_present": True,
                "top_level_source_ref_present": True,
                "top_level_verification_command_present": True,
            }
        )
    return {
        "key": "review-studio-gate-action-mirror",
        "label": "Review Studio gates mirror review actions",
        "status": "pass" if expected == actual else "fail",
        "expected": expected,
        "actual": actual,
        "paths": [REQUIRED_REPORTS["review_studio"]],
        "detail": (
            "Every non-pass Review Studio gate must have exactly one top-level review action and a gate-local "
            "action summary with source refs and a verification command."
        ),
    }

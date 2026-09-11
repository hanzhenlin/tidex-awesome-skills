#!/usr/bin/env python3
"""Execute a fixed provider matrix and build identity-safe blind-review materials."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from run_output_eval import load_cases, validate_case
from run_output_execution import command_run


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by evidence-build and matrix tests for budgeted double-model output evaluation."

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ("baseline", "with_skill")


def load_provider_matrix(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if payload.get("provider") != "deepseek":
        failures.append("provider must be deepseek")
    if payload.get("api_key_env") != "DEEPSEEK_API_KEY":
        failures.append("api_key_env must be DEEPSEEK_API_KEY")
    if payload.get("api_format") != "chat-completions":
        failures.append("api_format must be chat-completions")
    if payload.get("evaluation_locale") != "zh-CN":
        failures.append("evaluation_locale must be zh-CN")
    if payload.get("holdout_cases") != "holdout_cases.zh-CN.jsonl":
        failures.append("holdout_cases must be holdout_cases.zh-CN.jsonl")
    expected_models = ["deepseek-v4-flash", "deepseek-v4-pro"]
    models = payload.get("models", []) if isinstance(payload.get("models"), list) else []
    if [item.get("model") for item in models if isinstance(item, dict)] != expected_models:
        failures.append("models must be deepseek-v4-flash and deepseek-v4-pro in fixed order")
    for item in models:
        if item.get("thinking") != "disabled" or item.get("temperature") != 0 or item.get("max_output_tokens") != 3000:
            failures.append(f"invalid reproducibility contract for {item.get('model')}")
    limits = payload.get("limits", {})
    if limits != {"max_calls": 40, "max_total_tokens": 250000, "timeout_seconds": 60}:
        failures.append("provider limits must be 40 calls, 250000 tokens, and 60 seconds")
    promotion = payload.get("promotion", {})
    if promotion != {
        "pair_count": 20,
        "with_skill_min_wins": 15,
        "per_model_min_wins": 7,
        "critical_failure_max": 0,
        "fleiss_kappa_min": 0.4,
        "reviewer_count": 3,
    }:
        failures.append("provider promotion contract does not match the phase-one gate")
    if payload.get("world_class_counts_as_completion") is not False:
        failures.append("provider matrix cannot count as world-class completion")
    if failures:
        raise ValueError("; ".join(failures))
    return payload


def resolve_provider_cases_path(matrix_path: Path, matrix: dict[str, Any]) -> Path:
    """Resolve the fixed phase-one holdout declared by the provider contract."""
    relative = Path(str(matrix.get("holdout_cases", "")))
    if relative != Path("holdout_cases.zh-CN.jsonl") or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe or unsupported provider holdout_cases path")
    cases_path = matrix_path.parent / relative
    if not cases_path.is_file() or cases_path.is_symlink():
        raise ValueError(f"provider holdout_cases is missing or unsafe: {cases_path}")
    return cases_path


def provider_status(matrix: dict[str, Any]) -> dict[str, Any]:
    api_key_env = str(matrix["api_key_env"])
    available = bool(os.environ.get(api_key_env))
    return {
        "schema_version": "1.0",
        "ok": True,
        "provider": matrix["provider"],
        "models": [item["model"] for item in matrix["models"]],
        "status": "ready-to-run" if available else "external-required",
        "missing_environment": "" if available else api_key_env,
        "planned_call_count": 40,
        "completed_call_count": 0,
        "raw_output_count": 0,
        "quality_promotion": {"status": "pending", "eligible": False},
        "human_review": {"status": "pending", "required_reviewer_count": 3, "completed_reviewer_count": 0},
        "world_class_evidence": {"status": "pending", "counts_as_completion": False},
    }


def default_runner_for(matrix: dict[str, Any], model: dict[str, Any], skill_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts" / "provider_output_eval_runner.py"),
        "--provider",
        str(matrix["provider"]),
        "--api-format",
        str(matrix.get("api_format", "chat-completions")),
        "--api-key-env",
        str(matrix["api_key_env"]),
        "--model",
        str(model["model"]),
        "--thinking",
        str(model["thinking"]),
        "--temperature",
        str(model["temperature"]),
        "--max-output-tokens",
        str(model["max_output_tokens"]),
        "--timeout-seconds",
        str(matrix["limits"]["timeout_seconds"]),
        "--input-root",
        str(skill_dir / "evals" / "output"),
        "--skill-file",
        str(skill_dir / "SKILL.md"),
    ]


def raw_output_path(run_dir: Path, model: str, case_id: str, variant: str) -> Path:
    safe_case = "".join(character if character.isalnum() or character in "-_." else "_" for character in case_id)
    return run_dir / "raw-outputs" / model / f"{safe_case}.{variant}.txt"


def validate_raw_output(path: Path, run_dir: Path, expected_sha256: str, pair_id: str, label: str) -> None:
    raw_root = (run_dir / "raw-outputs").resolve()
    try:
        path.resolve().relative_to(raw_root)
    except ValueError as exc:
        raise ValueError(f"unsafe raw output for blind pair {pair_id} variant {label}") from exc
    cursor = run_dir
    for part in path.relative_to(run_dir).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe raw output for blind pair {pair_id} variant {label}")
    if not path.is_file():
        raise ValueError(f"missing raw output for blind pair {pair_id}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError(f"raw output hash mismatch for blind pair {pair_id} variant {label}")


def execute_provider_matrix(
    cases_path: Path,
    matrix: dict[str, Any],
    run_dir: Path,
    *,
    skill_dir: Path | None = None,
    runner_for: Callable[[dict[str, Any]], list[str]] | None = None,
) -> dict[str, Any]:
    skill_dir = Path(skill_dir or cases_path.parents[2]).resolve()
    cases = load_cases(cases_path)
    failures = [failure for case in cases for failure in validate_case(case, cases_path.parent)]
    if len(cases) != 10:
        failures.append(f"provider holdout must contain 10 cases, found {len(cases)}")
    run_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    total_tokens = 0
    max_calls = int(matrix["limits"]["max_calls"])
    max_tokens = int(matrix["limits"]["max_total_tokens"])
    if failures:
        return provider_report(matrix, cases, runs, total_tokens, failures)
    budget_exhausted = False
    for model in matrix["models"]:
        for case in cases:
            for variant in VARIANTS:
                call_count = sum(1 for item in runs if item.get("command_executed"))
                reservation = request_token_reservation(case, variant, cases_path.parent, skill_dir, model)
                if call_count >= max_calls or total_tokens + reservation > max_tokens:
                    runs.append(
                        {
                            "case_id": str(case["id"]),
                            "variant": variant,
                            "status": "fail",
                            "execution_mode": "model",
                            "model_executed": False,
                            "command_executed": False,
                            "duration_ms": None,
                            "provider": matrix["provider"],
                            "model": model["model"],
                            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated": False},
                            "score": 0,
                            "passed_count": 0,
                            "failed_count": len(case.get("assertions", [])),
                            "failed_assertions": [str(item.get("id", "assertion")) for item in case.get("assertions", [])],
                            "output_sha256": "",
                            "raw_output_path": "",
                            "redacted_summary": "request skipped before provider call",
                            "response_id": "",
                            "system_fingerprint": "",
                            "failure": "provider budget exhausted before request",
                            "reserved_tokens": reservation,
                        }
                    )
                    budget_exhausted = True
                    break
                command = runner_for(model) if runner_for else default_runner_for(matrix, model, skill_dir)
                assertions = case.get("assertions", []) if isinstance(case.get("assertions"), list) else []
                result = command_run(
                    case,
                    variant,
                    assertions,
                    command,
                    float(matrix["limits"]["timeout_seconds"]),
                    raw_output_dir=run_dir / "raw-outputs",
                    raw_output_path_override=raw_output_path(run_dir, str(model["model"]), str(case["id"]), variant),
                )
                if (
                    result.get("status") != "pass"
                    or result.get("model_executed") is not True
                    or result.get("provider") != matrix["provider"]
                    or result.get("model") != model["model"]
                ):
                    result["status"] = "fail"
                    result["failure"] = result.get("failure") or "provider execution identity did not match the fixed matrix"
                raw_path_value = str(result.get("raw_output_path", ""))
                if raw_path_value:
                    raw_path = Path(raw_path_value)
                    try:
                        result["raw_output_path"] = raw_path.relative_to(run_dir).as_posix()
                    except ValueError:
                        result["raw_output_path"] = ""
                total_tokens += int(result.get("usage", {}).get("total_tokens", 0) or 0)
                result["reserved_tokens"] = reservation
                if total_tokens > max_tokens:
                    result["status"] = "fail"
                    result["failure"] = "total token budget exceeded"
                runs.append(result)
            if budget_exhausted:
                break
        if budget_exhausted:
            break
    return provider_report(matrix, cases, runs, total_tokens, failures)


def request_token_reservation(
    case: dict[str, Any],
    variant: str,
    input_root: Path,
    skill_dir: Path,
    model: dict[str, Any],
) -> int:
    """Reserve a conservative request ceiling before spending provider budget."""
    input_bytes = len(str(case.get("prompt", "")).encode("utf-8")) + 2048
    if variant == "with_skill":
        skill_path = skill_dir / "SKILL.md"
        if skill_path.is_file():
            input_bytes += len(skill_path.read_bytes()[:8000])
    for value in case.get("input_files", []) if isinstance(case.get("input_files"), list) else []:
        relative = Path(str(value))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        path = input_root / relative
        if path.is_file() and not path.is_symlink():
            input_bytes += len(path.read_bytes()[:6000])
    return input_bytes + int(model["max_output_tokens"])


def provider_report(
    matrix: dict[str, Any],
    cases: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    total_tokens: int,
    failures: list[str],
) -> dict[str, Any]:
    run_failures = [str(item.get("failure", "")) for item in runs if item.get("failure")]
    all_failures = failures + run_failures
    failure_count = len(all_failures)
    payload = {
        "schema_version": "1.0",
        "ok": failure_count == 0 and len(runs) == 40,
        "provider_matrix": matrix,
        "summary": {
            "case_count": len(cases),
            "model_count": len(matrix["models"]),
            "call_count": sum(1 for item in runs if item.get("command_executed")),
            "run_record_count": len(runs),
            "model_executed_count": sum(1 for item in runs if item.get("model_executed")),
            "total_tokens": total_tokens,
            "failure_count": failure_count,
        },
        "runs": runs,
        "failures": all_failures,
        "quality_promotion": {
            "status": "awaiting-human-review" if failure_count == 0 and len(runs) == 40 else "pending",
            "eligible": False,
            "reason": "Three independent reviewer decision sets are required.",
        },
        "world_class_evidence": {
            "status": "pending",
            "counts_as_completion": False,
            "reason": "Internal output quality evidence does not close the world-class ledger.",
        },
    }
    return payload


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_provider_run_set(report: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    models = [str(item["model"]) for item in report.get("provider_matrix", {}).get("models", [])]
    runs = report.get("runs", [])
    case_ids = sorted({str(item.get("case_id", "")) for item in runs})
    expected = {(model, case_id, variant) for model in models for case_id in case_ids for variant in VARIANTS}
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    failures: list[str] = []
    for item in runs:
        key = (str(item.get("model", "")), str(item.get("case_id", "")), str(item.get("variant", "")))
        if key in indexed:
            failures.append(f"duplicate provider run: {key}")
        indexed[key] = item
        if (
            item.get("status") != "pass"
            or item.get("model_executed") is not True
            or item.get("provider") != report.get("provider_matrix", {}).get("provider")
            or key[0] not in models
        ):
            failures.append(f"untrusted provider run: {key}")
    if len(models) != 2 or len(case_ids) != 10 or set(indexed) != expected or len(runs) != 40:
        failures.append("provider runs must exactly cover 2 models x 10 cases x 2 variants")
    if failures:
        raise ValueError("; ".join(failures))
    return indexed


def build_blind_materials(report: dict[str, Any], run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    if report.get("summary", {}).get("failure_count") or len(report.get("runs", [])) != 40:
        raise ValueError("blind materials require 40 successful provider runs")
    runs = validate_provider_run_set(report)
    blinded_root = run_dir / "review-materials" / secrets.token_hex(16)
    blinded_root.mkdir(parents=True)
    pairs = []
    answers = []
    for model in [item["model"] for item in report["provider_matrix"]["models"]]:
        case_ids = sorted({item["case_id"] for item in report["runs"] if item["model"] == model})
        for case_id in case_ids:
            pair_id = f"{model}:{case_id}"
            role_a, role_b = ("baseline", "with_skill") if secrets.randbits(1) == 0 else ("with_skill", "baseline")
            run_a = runs[(model, case_id, role_a)]
            run_b = runs[(model, case_id, role_b)]
            path_a = raw_output_path(run_dir, model, case_id, role_a)
            path_b = raw_output_path(run_dir, model, case_id, role_b)
            validate_raw_output(path_a, run_dir, run_a["output_sha256"], pair_id, "A")
            validate_raw_output(path_b, run_dir, run_b["output_sha256"], pair_id, "B")
            blind_a = blinded_root / f"{secrets.token_hex(16)}.txt"
            blind_b = blinded_root / f"{secrets.token_hex(16)}.txt"
            shutil.copyfile(path_a, blind_a)
            shutil.copyfile(path_b, blind_b)
            pairs.append(
                {
                    "pair_id": pair_id,
                    "model_alias": "Model A" if model.endswith("flash") else "Model B",
                    "case_id": case_id,
                    "variant_a_raw_output": blind_a.relative_to(run_dir).as_posix(),
                    "variant_b_raw_output": blind_b.relative_to(run_dir).as_posix(),
                    "variant_a_sha256": run_a["output_sha256"],
                    "variant_b_sha256": run_b["output_sha256"],
                    "review_instruction": "Select A or B using only visible quality and boundary evidence.",
                }
            )
            answers.append(
                {
                    "pair_id": pair_id,
                    "model": model,
                    "case_id": case_id,
                    "variant_a_role": role_a,
                    "variant_b_role": role_b,
                }
            )
    secrets.SystemRandom().shuffle(pairs)
    order = {pair["pair_id"]: index for index, pair in enumerate(pairs)}
    answers.sort(key=lambda item: order[item["pair_id"]])
    blind_pack = {"schema_version": "1.0", "summary": {"pair_count": len(pairs)}, "pairs": pairs}
    if len(pairs) != 20:
        raise ValueError(f"blind materials require 20 pairs, found {len(pairs)}")
    blind_pack_sha256 = canonical_sha256(blind_pack)
    answer_key = {
        "schema_version": "1.0",
        "summary": {"pair_count": len(answers)},
        "promotion": report["provider_matrix"]["promotion"],
        "blind_pack_sha256": blind_pack_sha256,
        "answers": answers,
    }
    templates = {
        reviewer: {
            "schema_version": "1.0",
            "reviewer": reviewer,
            "review_integrity": {"blind_pack_sha256": blind_pack_sha256},
            "reviewer_attestation": {
                "independent_blind_review_completed": False,
                "submitted_at": "",
                "controlled_submission_id": "",
            },
            "decisions": [
                {"pair_id": pair["pair_id"], "winner_variant": "", "critical_failure": False, "reason": ""}
                for pair in pairs
            ],
        }
        for reviewer in ("reviewer-a", "reviewer-b", "reviewer-c")
    }
    return blind_pack, answer_key, templates

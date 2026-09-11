#!/usr/bin/env python3
"""Deterministic intent clarification planning for skill authoring."""

import re
from typing import Any


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by intent reports and Yao CLI creation flows to plan bounded, bilingual clarification."


GENERIC_ENGLISH_TOKENS = {
    "a",
    "an",
    "and",
    "create",
    "do",
    "help",
    "handle",
    "it",
    "job",
    "make",
    "output",
    "package",
    "process",
    "repeated",
    "request",
    "requests",
    "reusable",
    "skill",
    "something",
    "stuff",
    "task",
    "tasks",
    "the",
    "things",
    "this",
    "turn",
    "workflow",
    "work",
}

GENERIC_PHRASES = {
    "turn a repeated workflow into a reusable skill",
    "a reusable skill package",
    "describe what the skill does and when to use it",
    "turn rough requests into a compact reusable demo skill",
    "帮我做一个skill",
    "帮我做个skill",
    "帮我做一个技能",
    "帮我做个技能",
    "做一个skill",
    "做个skill",
    "做一个技能",
    "做个技能",
    "优化一下",
    "处理这些内容",
}

ALTERNATIVE_MARKERS = (" either ", "还是", "二选一", "两个方向", "两种方向")
ENGLISH_DIRECTION_VERBS = ("choose", "create", "decide", "deliver", "generate", "pick", "produce", "return")
CHINESE_DIRECTION_VERBS = ("选择", "创建", "产出", "生成", "交付", "输出", "制作")
CORRECTION_CONFLICT_MARKERS = (
    "actually",
    "instead",
    "rather",
    "change to",
    "改成",
    "调整为",
    "以此为准",
)
OUTPUT_CORRECTION_MARKERS = (
    "deliverable",
    "format",
    "hand-back",
    "output",
    "result",
    "return",
    "交付物",
    "格式",
    "结果",
    "输出",
)
JOB_CORRECTION_MARKERS = ("direction", "job", "task", "workflow", "任务", "方向", "流程", "负责")
NON_CORE_CORRECTION_MARKERS = (
    "audit",
    "compatibility",
    "concise",
    "do not",
    "don't",
    "exclude",
    "naming",
    "privacy",
    "private",
    "quality",
    "tone",
    "不要",
    "不得",
    "不包含",
    "兼容",
    "命名",
    "审计",
    "排除",
    "简洁",
    "质量",
    "语气",
    "隐私",
)
CORE_OUTPUT_VALUE_MARKERS = (
    "csv",
    "dashboard",
    "docx",
    "html",
    "json",
    "markdown",
    "pdf",
    "report",
    "spreadsheet",
    "仪表盘",
    "文档",
    "报告",
    "表格",
)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def compact_excerpt(value: Any, limit: int = 96) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def detect_language(*values: Any) -> str:
    text = " ".join(normalize_text(value) for value in values if normalize_text(value))
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]+", text))
    return "zh-CN" if cjk_count and cjk_count >= latin_count else "en"


def is_generic_intent(value: Any) -> bool:
    text = normalize_text(value)
    if not text:
        return True
    compact = text.lower().rstrip("。.!！?？")
    if compact in GENERIC_PHRASES:
        return True
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    if cjk:
        reduced = compact
        for token in ("帮我", "请", "做一个", "做个", "创建一个", "创建", "优化一下", "处理一下", "skill", "技能", "这个"):
            reduced = reduced.replace(token, "")
        latin_tokens = [
            token
            for token in re.findall(r"[a-z][a-z0-9_-]*", reduced)
            if token not in GENERIC_ENGLISH_TOKENS
        ]
        specificity_units = len(re.findall(r"[\u3400-\u9fff]", reduced)) + len(latin_tokens)
        return specificity_units < 3
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", compact)
    content_tokens = [token for token in tokens if token not in GENERIC_ENGLISH_TOKENS]
    return not content_tokens


def classify_correction_target(value: Any) -> str:
    correction = normalize_text(value).lower()
    if not correction:
        return ""
    has_output_marker = any(marker in correction for marker in OUTPUT_CORRECTION_MARKERS)
    has_non_core_marker = any(marker in correction for marker in NON_CORE_CORRECTION_MARKERS)
    has_direction_change = any(marker in correction for marker in CORRECTION_CONFLICT_MARKERS)
    has_core_output_value = any(marker in correction for marker in CORE_OUTPUT_VALUE_MARKERS)
    if has_non_core_marker and not has_direction_change and not has_core_output_value:
        return "non_core"
    if has_output_marker:
        return "primary_output"
    if has_non_core_marker:
        return "non_core"
    if any(marker in correction for marker in JOB_CORRECTION_MARKERS + CORRECTION_CONFLICT_MARKERS):
        return "job"
    return "job"


def has_explicit_alternative(value: Any, *, output_slot: bool = False) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    lowered = f" {text.lower()} "
    if any(marker in lowered for marker in ALTERNATIVE_MARKERS):
        return True
    if " or " in lowered:
        if output_slot or any(mark in text for mark in ("?", "？")):
            return True
        if not any(mark in text for mark in (",", ";", "，", "；")):
            return any(re.search(rf"\b{re.escape(verb)}\b", lowered) for verb in ENGLISH_DIRECTION_VERBS)
    if "或" in text:
        if output_slot or any(mark in text for mark in ("?", "？")):
            return True
        if not any(mark in text for mark in (",", ";", "，", "；")):
            return any(verb in text for verb in CHINESE_DIRECTION_VERBS)
    return False


def direction_ambiguity_details(context: dict[str, Any]) -> tuple[str, str]:
    state = context.get("clarification_state", {}) if isinstance(context.get("clarification_state"), dict) else {}
    resolved = {str(item) for item in state.get("resolved_ambiguities", [])}
    correction = normalize_text(context.get("correction")).lower()
    correction_target = classify_correction_target(correction)
    correction_is_pending = bool(state.get("correction_pending"))
    correction_is_explicit_conflict = any(marker in correction for marker in CORRECTION_CONFLICT_MARKERS)
    if (
        "direction_conflict" not in resolved
        and correction
        and correction_target != "non_core"
        and (correction_is_pending or correction_is_explicit_conflict)
    ):
        return "direction_conflict", correction_target or "job"
    for slot, output_slot in (("job", False), ("description", False), ("primary_output", True)):
        if "multi_intent" not in resolved and has_explicit_alternative(context.get(slot), output_slot=output_slot):
            return "multi_intent", "primary_output" if slot == "primary_output" else "job"
    return "", ""


def detect_direction_ambiguity(context: dict[str, Any]) -> str:
    return direction_ambiguity_details(context)[0]


def split_explicit_alternatives(value: Any) -> list[str]:
    text = normalize_text(value).strip(" .。!?！？")
    if not text:
        return []
    text = re.sub(r"^(?:either|choose between)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:是选择|选择|要么)", "", text)
    if re.search(r"\s+or\s+", text, flags=re.IGNORECASE):
        parts = re.split(r"\s+or\s+", text, maxsplit=1, flags=re.IGNORECASE)
    elif "还是" in text:
        parts = text.split("还是", 1)
    elif "或" in text:
        parts = text.split("或", 1)
    else:
        return []
    return [normalize_text(part).strip(" .。!?！？") for part in parts if normalize_text(part)]


def _alternative_tokens(value: str) -> set[str]:
    english = {
        token
        for token in re.findall(r"[a-z][a-z0-9_-]*", value.lower())
        if token not in GENERIC_ENGLISH_TOKENS and len(token) > 2
    }
    cjk = "".join(re.findall(r"[\u3400-\u9fff]", value))
    chinese = {cjk[index : index + 2] for index in range(max(0, len(cjk) - 1))}
    return english | chinese


def choose_preferred_alternative(value: Any, anchor: Any) -> tuple[str, str]:
    alternatives = split_explicit_alternatives(value)
    if len(alternatives) != 2:
        return normalize_text(value), "low"
    anchor_tokens = _alternative_tokens(normalize_text(anchor))
    scores = [len(_alternative_tokens(item) & anchor_tokens) for item in alternatives]
    if scores[0] != scores[1] and max(scores) > 0:
        return alternatives[0 if scores[0] > scores[1] else 1], "medium"
    return alternatives[0], "low"


def extract_correction_value(value: Any, target_slot: str) -> str:
    text = normalize_text(value).strip(" .。")
    text = re.sub(r"^(?:actually|instead|please)\s*[:,，]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:其实|请|改成|调整为)\s*", "", text)
    if target_slot == "primary_output":
        english = re.search(
            r"(?:the\s+)?(?:output|deliverable|hand-?back|result|format)\s+"
            r"(?:should\s+|must\s+|needs?\s+to\s+)?(?:be|become|use|to)\s+(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if english:
            return english.group(1).strip(" .。")
        chinese = re.search(r"(?:输出|交付物|结果|格式)(?:要|应|需要|改成|调整为|为|：|:)*\s*(.+)$", text)
        if chinese:
            return chinese.group(1).strip(" .。")
    return text


def replace_inference_assumption(
    assumptions: list[dict[str, str]], slot: str, value: str, reason: str, quality: str
) -> None:
    assumptions[:] = [
        item
        for item in assumptions
        if not (str(item.get("slot", "")) == slot and str(item.get("source", "")) == "preferred-inference")
    ]
    assumptions.append(
        {
            "slot": slot,
            "value": value,
            "source": "preferred-inference",
            "reason": reason,
            "confidence": quality,
        }
    )


def build_non_core_assumptions(context: dict[str, Any], gap_keys: list[str], language: str) -> list[dict[str, str]]:
    copy = {
        "en": {
            "real_inputs": "Use user-supplied materials directly related to the confirmed job.",
            "exclusions": "Requests outside the confirmed recurring job remain out of scope.",
            "constraints": "No extra constraints were confirmed; keep the package's existing safety and compatibility rules.",
            "standards": "No extra quality standard was confirmed; use the declared output contract as the first evaluation target.",
        },
        "zh-CN": {
            "real_inputs": "使用与已确认任务直接相关的用户材料作为输入。",
            "exclusions": "已确认任务之外的相邻请求保持在范围外。",
            "constraints": "用户没有补充额外约束，继续遵守包体现有的安全与兼容规则。",
            "standards": "用户没有补充额外质量标准，先以已声明的输出契约作为评测目标。",
        },
    }[language]
    assumptions = []
    for slot in ("real_inputs", "exclusions", "constraints", "standards"):
        if slot not in gap_keys:
            continue
        assumptions.append(
            {
                "slot": slot,
                "value": copy[slot],
                "source": "inferred-default",
                "reason": "Non-core information is missing and does not change the current package boundary.",
                "confidence": "medium",
            }
        )
    return assumptions


def clarification_review_status(intent: dict[str, Any]) -> str:
    clarification = intent.get("clarification_plan", {}) if isinstance(intent, dict) else {}
    decision = str(clarification.get("decision", ""))
    authoring_ready = intent.get("authoring_ready")
    assumptions = intent.get("assumptions", []) if isinstance(intent, dict) else []
    if authoring_ready is False and decision == "ask":
        return "block"
    if decision == "infer" or assumptions:
        return "warn"
    if authoring_ready is True or intent.get("gate_passed"):
        return "pass"
    return "warn"


def apply_preferred_inference(context: dict[str, Any], skill_name: str = "") -> dict[str, Any]:
    inferred = dict(context)
    inferred["real_inputs"] = list(context.get("real_inputs", []) or [])
    inferred["exclusions"] = list(context.get("exclusions", []) or [])
    inferred["constraints"] = list(context.get("constraints", []) or [])
    inferred["standards"] = list(context.get("standards", []) or [])
    assumptions = [dict(item) for item in context.get("assumptions", []) if isinstance(item, dict)]
    job = normalize_text(context.get("job"))
    primary_output = normalize_text(context.get("primary_output"))
    correction = normalize_text(context.get("correction"))
    description = normalize_text(context.get("description"))
    language = detect_language(job, primary_output, correction, description)
    inferred_slots: list[tuple[str, str, str, str]] = []
    state = dict(context.get("clarification_state", {}) or {})
    direction_ambiguity, direction_slot = direction_ambiguity_details(context)

    if correction and direction_ambiguity == "direction_conflict":
        correction_value = extract_correction_value(correction, direction_slot)
        if direction_slot == "primary_output" and not is_generic_intent(correction_value):
            primary_output = correction_value
            inferred_slots.append(
                ("primary_output", primary_output, "The user's output correction is the strongest available signal.", "medium")
            )
        elif not is_generic_intent(correction_value):
            job = correction_value
            inferred_slots.append(("job", job, "The user's task correction is the strongest available signal.", "medium"))
            primary_output = ""
        else:
            retained_slot = "primary_output" if direction_slot == "primary_output" else "job"
            retained_value = primary_output if retained_slot == "primary_output" else job
            inferred_slots.append(
                (
                    retained_slot,
                    retained_value,
                    "The correction was not specific enough to replace the strongest confirmed direction.",
                    "medium",
                )
            )

    if direction_ambiguity == "multi_intent":
        source_value = primary_output if direction_slot == "primary_output" else job
        anchor = (
            f"{job} {description.replace(job, '')}"
            if direction_slot == "primary_output"
            else f"{primary_output} {description.replace(job, '')}"
        )
        selected, selection_quality = choose_preferred_alternative(source_value, anchor)
        if direction_slot == "primary_output":
            primary_output = selected
        else:
            job = selected
        inferred_slots.append(
            (
                direction_slot,
                selected,
                "The selected branch has the strongest overlap with confirmed context. The first branch wins when evidence is tied.",
                selection_quality,
            )
        )

    if is_generic_intent(job) and not is_generic_intent(primary_output):
        job = (
            f"围绕“{compact_excerpt(primary_output)}”稳定完成所需的重复任务"
            if language == "zh-CN"
            else f"Reliably complete the recurring work needed to produce {compact_excerpt(primary_output)}"
        )
        inferred_slots.append(("job", job, "A concrete hand-back is the strongest available anchor.", "medium"))

    if is_generic_intent(primary_output) and not is_generic_intent(job):
        primary_output = (
            f"一份可直接用于“{compact_excerpt(job)}”的首版交付物"
            if language == "zh-CN"
            else f"A first-pass deliverable that can be used directly for {compact_excerpt(job)}"
        )
        inferred_slots.append(
            ("primary_output", primary_output, "A concrete recurring job is the strongest available anchor.", "medium")
        )

    if is_generic_intent(job) and is_generic_intent(primary_output) and not is_generic_intent(description):
        job = description
        primary_output = (
            f"一份可直接用于“{compact_excerpt(job)}”的首版交付物"
            if language == "zh-CN"
            else f"A first-pass deliverable that can be used directly for {compact_excerpt(job)}"
        )
        inferred_slots.extend(
            [
                ("job", job, "The explicit description is the strongest remaining direction signal.", "medium"),
                (
                    "primary_output",
                    primary_output,
                    "The explicit description anchors the safest bounded hand-back.",
                    "medium",
                ),
            ]
        )

    if is_generic_intent(job) and is_generic_intent(primary_output):
        label = normalize_text(skill_name).replace("-", " ") or "current skill"
        if language == "zh-CN":
            job = f"围绕“{label}”把用户提供的材料整理成一个聚焦的首版可复用工作流"
            primary_output = "一个带明确任务边界、输入说明和使用方法的首版 Skill 包"
        else:
            job = f"Turn user-provided material for {label} into a focused reusable first-pass workflow"
            primary_output = "A first-pass skill package with a clear job boundary, input notes, and usage guidance"
        inferred_slots.extend(
            [
                ("job", job, "The skill name and original request are the only remaining direction signals.", "low"),
                ("primary_output", primary_output, "The first-pass package contract is the safest bounded hand-back.", "low"),
            ]
        )

    inference_quality = "low" if any(item[3] == "low" for item in inferred_slots) else "medium"
    for slot, value, reason, quality in inferred_slots:
        replace_inference_assumption(assumptions, slot, value, reason, quality)
    rounds_used = int(state.get("rounds_used", 0) or 0)
    max_rounds = int(state.get("max_rounds", 2) or 2)
    resolved_ambiguities = [str(item) for item in state.get("resolved_ambiguities", [])]
    if direction_ambiguity and direction_ambiguity not in resolved_ambiguities:
        resolved_ambiguities.append(direction_ambiguity)
    state.update(
        {
            "decision": "infer",
            "rounds_used": rounds_used,
            "max_rounds": max_rounds,
            "resolved_ambiguities": resolved_ambiguities,
            "correction_pending": False,
            "stop_reason": "round-limit" if rounds_used >= max_rounds else "user-skipped",
            "inference_quality": inference_quality,
        }
    )
    inferred.update(
        {
            "job": job,
            "primary_output": primary_output,
            "language": language,
            "assumptions": assumptions,
            "clarification_state": state,
        }
    )
    return inferred


def build_clarification_plan(context: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    job = normalize_text(context.get("job"))
    primary_output = normalize_text(context.get("primary_output"))
    description = normalize_text(context.get("description"))
    language = detect_language(job, primary_output, description, context.get("correction", ""))
    gap_keys = [str(gap.get("key", "")) for gap in gaps]
    direction_ambiguity, direction_slot = direction_ambiguity_details(context)
    blocking = []
    if "job_specificity" in gap_keys:
        blocking.append("task_missing" if not job else "task_too_broad")
    if "primary_output" in gap_keys:
        blocking.append("deliverable_missing" if not primary_output else "deliverable_too_broad")
    if direction_ambiguity:
        blocking.insert(0, direction_ambiguity)
    state = context.get("clarification_state", {}) if isinstance(context.get("clarification_state"), dict) else {}
    asked = {str(item) for item in state.get("asked_ambiguities", [])}
    unasked_blocking = [key for key in blocking if key not in asked]
    prioritized_blocking = unasked_blocking or blocking
    decision = "ask" if blocking else "proceed"
    stop_reason = "blocking-core-ambiguity" if blocking else ("non-core-only" if gaps else "clear")
    ambiguity_type = prioritized_blocking[0] if prioritized_blocking else ""
    target_slot = (
        "direction"
        if ambiguity_type in {"direction_conflict", "multi_intent"}
        else (
            "job"
            if ambiguity_type in {"task_missing", "task_too_broad"}
            else ("primary_output" if ambiguity_type in {"deliverable_missing", "deliverable_too_broad"} else "")
        )
    )
    question = ""
    rationale = ""
    decision_impact = ""
    if target_slot == "direction":
        direction_value = primary_output if direction_slot == "primary_output" else job
        direction_excerpt = compact_excerpt(direction_value)
        correction_excerpt = compact_excerpt(context.get("correction"))
        if language == "zh-CN":
            if correction_excerpt:
                prior_label = "交付物" if direction_slot == "primary_output" else "核心任务"
                question = f"你先前确认的{prior_label}是“{direction_excerpt}”，后面又补充了“{correction_excerpt}”。这会改变首版边界，以哪个方向为准？"
            else:
                question = f"“{direction_excerpt}”里包含多个明确方向，它们会形成不同的能力边界。首版最需要优先接住哪一个？"
            decision_impact = "这个选择会决定首版的核心任务、触发边界和交付物。"
        else:
            if correction_excerpt:
                prior_label = "hand-back" if direction_slot == "primary_output" else "core job"
                question = (
                    f'Your confirmed {prior_label} was “{direction_excerpt}”, and you later added “{correction_excerpt}”. '
                    "These lead to different capability boundaries. Which direction should the first version follow?"
                )
            else:
                question = (
                    f'The request “{direction_excerpt}” contains multiple explicit directions with different capability boundaries. '
                    "Which one should the first version own?"
                )
            decision_impact = "This choice determines the first version's core job, trigger boundary, and hand-back."
        rationale = "An explicit alternative or correction would materially change the package direction."
    elif target_slot == "job":
        output_excerpt = compact_excerpt(primary_output)
        if language == "zh-CN":
            question = (
                f"我已经知道你希望拿到“{output_excerpt}”。为了把能力边界定准，它每次最需要稳定接住的具体任务是什么？"
                if output_excerpt
                else "我们先锁定最关键的一点：这个 Skill 每次最需要稳定接住的具体任务是什么？"
            )
            decision_impact = "这个答案会决定 Skill 的触发边界和首版工作流。"
        else:
            question = (
                f'I know the desired hand-back is “{output_excerpt}”. What concrete recurring job should this skill reliably own?'
                if output_excerpt
                else "What concrete recurring job should this skill reliably own every time?"
            )
            decision_impact = "This answer determines the trigger boundary and first-pass workflow."
        rationale = "The recurring job is still missing or too generic to anchor the package."
    elif target_slot == "primary_output":
        job_excerpt = compact_excerpt(job)
        if language == "zh-CN":
            question = f"我理解它要负责“{job_excerpt}”。完成后，用户最需要直接拿走什么结果？"
            decision_impact = "这个答案会决定输出契约和第一项质量评测。"
        else:
            question = f'I understand this should handle “{job_excerpt}”. What finished result should the user be able to take away?'
            decision_impact = "This answer determines the output contract and first evaluation target."
        rationale = "The finished hand-back is still missing or too generic to guide package design."
    return {
        "decision": decision,
        "language": language,
        "ambiguity_type": ambiguity_type,
        "target_slot": target_slot,
        "direction_slot": direction_slot,
        "question": question,
        "rationale": rationale,
        "decision_impact": decision_impact,
        "blocking_ambiguities": blocking,
        "stop_reason": stop_reason,
        "inference_quality": "medium" if not blocking and gap_keys else ("high" if not gap_keys else ""),
    }

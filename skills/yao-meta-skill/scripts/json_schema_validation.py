#!/usr/bin/env python3
"""Small dependency-free validator for the JSON Schema keywords used by Yao."""

from __future__ import annotations

from datetime import date
import re
from typing import Any


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by manifest and Skill IR validation to enforce their committed JSON Schema contracts."


def _matches_type(value: Any, expected: str) -> bool:
    mapping = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return mapping.get(expected, lambda _item: True)(value)


def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    failures: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        return [f"{path}: expected {expected_type}"]
    if "const" in schema and value != schema["const"]:
        failures.append(f"{path}: expected constant {schema['const']!r}")
    if isinstance(schema.get("enum"), list) and value not in schema["enum"]:
        failures.append(f"{path}: value is outside the allowed enum")
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            failures.append(f"{path}: string is shorter than {schema['minLength']}")
        if isinstance(schema.get("pattern"), str) and re.fullmatch(schema["pattern"], value) is None:
            failures.append(f"{path}: string does not match the required pattern")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                failures.append(f"{path}: invalid ISO date")
    if isinstance(value, dict):
        properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required", []) if isinstance(schema.get("required"), list) else []
        for key in required:
            if key not in value:
                failures.append(f"{path}.{key}: required property is missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    failures.append(f"{path}.{key}: additional property is forbidden")
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, dict):
                failures.extend(validate_json_schema(child, child_schema, f"{path}.{key}"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            failures.extend(validate_json_schema(item, schema["items"], f"{path}[{index}]"))
    return failures

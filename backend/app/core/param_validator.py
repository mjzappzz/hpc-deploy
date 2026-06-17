import re
from typing import Any


FORBIDDEN_PATH_TOKENS = (";", "&&", "||", "`", "$(", ">", "<", "rm -rf", "reboot", "shutdown", "../")
ALLOWED_PATH_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789~/._-{}")
GPU_IDS_PATTERN = re.compile(r"^(all|\d+(,\d+)*)$")


def validate_script_params(
    params_schema: dict[str, Any] | None,
    params: dict[str, Any],
) -> list[str]:
    schema = params_schema or {}
    errors: list[str] = []

    for key in params:
        if key not in schema:
            errors.append(f"unknown parameter: {key}")

    for name, definition in schema.items():
        if not isinstance(definition, dict):
            errors.append(f"{name}: schema definition must be an object")
            continue

        required = bool(definition.get("required", False))
        param_type = definition.get("type")
        value = params.get(name, definition.get("default"))

        if required and _is_empty(value):
            errors.append(f"{name}: required parameter is missing")
            continue

        if _is_empty(value):
            continue

        if param_type == "select":
            options = definition.get("options", [])
            if value not in options:
                errors.append(f"{name}: value must be one of {options}")
        elif param_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"{name}: value must be a number")
            elif name == "duration" and value <= 0:
                errors.append(f"{name}: value must be greater than 0")
        elif param_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"{name}: value must be a boolean")
        elif param_type in {"string", "path"}:
            if not isinstance(value, str):
                errors.append(f"{name}: value must be a string")
                continue
            if name == "gpu_ids" and not GPU_IDS_PATTERN.fullmatch(value):
                errors.append(f"{name}: value must be all or look like 0 or 0,1,2,3")
            if param_type == "path":
                errors.extend(_validate_path_value(name, value))
        else:
            errors.append(f"{name}: unsupported parameter type {param_type!r}")

    return errors


def _validate_path_value(name: str, value: str) -> list[str]:
    lowered = value.lower()
    errors: list[str] = []
    for token in FORBIDDEN_PATH_TOKENS:
        if token in lowered:
            errors.append(f"{name}: forbidden path token {token!r}")

    invalid_chars = sorted({char for char in value if char not in ALLOWED_PATH_CHARS})
    if invalid_chars:
        errors.append(f"{name}: invalid path characters {''.join(invalid_chars)!r}")

    return errors


def _is_empty(value: Any) -> bool:
    return value is None or value == ""

from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

from .errors import ContractError


JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def require_json_value(value: Any, path: str = "$") -> JSONValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and not isinstance(value, bool):
        if value != value or value in (float("inf"), float("-inf")):
            raise ContractError(f"{path}: non-finite numbers are forbidden")
        return value
    if isinstance(value, list):
        return [require_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"{path}: object keys must be strings")
            result[key] = require_json_value(item, f"{path}.{key}")
        return result
    raise ContractError(f"{path}: {type(value).__name__} is not a JSON value")


def to_primitive(value: Any) -> JSONValue:
    if dataclasses.is_dataclass(value):
        return {
            field.name: to_primitive(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_primitive(item) for item in value]
    return require_json_value(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: str | Path) -> JSONValue:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON from {path}: {exc}") from exc
    return require_json_value(value)


def dump_json(value: Any) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"


def require_object(value: Any, path: str = "$") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path}: expected object")
    if not all(isinstance(key, str) for key in value):
        raise ContractError(f"{path}: object keys must be strings")
    return value


def strict_fields(value: Any, required: set[str], optional: set[str], path: str = "$") -> dict[str, Any]:
    obj = require_object(value, path)
    missing = required - obj.keys()
    unknown = obj.keys() - required - optional
    if missing:
        raise ContractError(f"{path}: missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ContractError(f"{path}: unknown fields: {', '.join(sorted(unknown))}")
    return obj


def require_string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ContractError(f"{path}: expected {'non-empty ' if nonempty else ''}string")
    return value


def require_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise ContractError(f"{path}: expected boolean")
    return value


def require_number(value: Any, path: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{path}: expected number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ContractError(f"{path}: expected finite number")
    if minimum is not None and result < minimum:
        raise ContractError(f"{path}: expected value >= {minimum}")
    return result


def require_sha256(value: Any, path: str) -> str:
    result = require_string(value, path)
    prefix, separator, digest = result.partition(":")
    if separator != ":" or prefix != "sha256" or len(digest) != 64:
        raise ContractError(f"{path}: expected sha256:<64 lowercase hex characters>")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ContractError(f"{path}: invalid sha256 digest") from exc
    if digest.lower() != digest:
        raise ContractError(f"{path}: sha256 digest must be lowercase")
    return result

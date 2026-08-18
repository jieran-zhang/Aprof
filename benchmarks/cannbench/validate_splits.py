#!/usr/bin/env python3
"""Validate the frozen CANNBench operator split and project readiness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
SPLIT_NAMES = ("train", "validation", "test")
REQUIRED_PROJECT_FILES = (
    "CMakeLists.txt",
    "run.sh",
    "scripts/cases.py",
    "scripts/gen_data.py",
    "scripts/verify_result.py",
    "results.json",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def pending_names(manifest: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in manifest.get("pending_operators", []):
        name = item.get("name") if isinstance(item, dict) else item
        if not isinstance(name, str) or not name:
            raise ValueError(f"invalid pending operator entry: {item!r}")
        names.append(name)
    return names


def membership_payload(manifests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        name: {
            "active_operators": manifests[name]["active_operators"],
            "pending_operators": pending_names(manifests[name]),
        }
        for name in SPLIT_NAMES
    }


def membership_digest(manifests: dict[str, dict[str, Any]]) -> str:
    encoded = json.dumps(
        membership_payload(manifests), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def result_passed_20(path: Path) -> tuple[bool, str]:
    data = load_json(path)
    total = data.get("total_cases")
    passed = data.get("passed_cases")
    all_passed = data.get("all_passed")
    if all_passed is None and isinstance(data.get("verification"), dict):
        all_passed = data["verification"].get("all_passed")
    ok = total == 20 and passed == 20 and all_passed is True
    return ok, f"total={total!r}, passed={passed!r}, all_passed={all_passed!r}"


def main() -> int:
    errors: list[str] = []
    index = load_json(ROOT / "split_index.json")
    manifests = {
        name: load_json(ROOT / name / "manifest.json") for name in SPLIT_NAMES
    }

    active: dict[str, set[str]] = {}
    pending: dict[str, set[str]] = {}
    for name, manifest in manifests.items():
        values = manifest.get("active_operators")
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            errors.append(f"{name}: active_operators must be a string list")
            values = []
        if values != sorted(values):
            errors.append(f"{name}: active_operators must be sorted")
        active[name] = set(values)
        try:
            pending[name] = set(pending_names(manifest))
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            pending[name] = set()

        text_path = ROOT / name / "operators.txt"
        text_names = [
            line.strip()
            for line in text_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if text_names != values:
            errors.append(f"{name}: operators.txt differs from manifest.json")

    for left_index, left in enumerate(SPLIT_NAMES):
        for right in SPLIT_NAMES[left_index + 1 :]:
            overlap = active[left] & active[right]
            if overlap:
                errors.append(f"active overlap {left}/{right}: {sorted(overlap)}")

    operators_root = ROOT / "operators"
    ready_dirs = {path.name for path in operators_root.iterdir() if path.is_dir()}
    active_union = set().union(*active.values())
    if active_union != ready_dirs:
        errors.append(
            "active split coverage differs from materialized operators: "
            f"missing={sorted(ready_dirs - active_union)}, "
            f"unexpected={sorted(active_union - ready_dirs)}"
        )

    catalog: dict[str, str] = {}
    catalog_root = REPO_ROOT / "third_party/cann-bench/tasks"
    for path in catalog_root.glob("level*/*"):
        if path.is_dir():
            catalog[path.name] = path.parent.name
    pending_union = set().union(*pending.values())
    catalog_missing = set(catalog) - ready_dirs
    if pending_union != catalog_missing:
        errors.append(
            "pending coverage differs from unmaterialized catalog tasks: "
            f"missing={sorted(catalog_missing - pending_union)}, "
            f"unexpected={sorted(pending_union - catalog_missing)}"
        )
    non_level4 = {name for name in pending_union if catalog.get(name) != "level4"}
    if non_level4:
        errors.append(f"pending tasks are not all Level 4: {sorted(non_level4)}")

    for name in sorted(active_union):
        project = operators_root / name
        for relative in REQUIRED_PROJECT_FILES:
            if not (project / relative).is_file():
                errors.append(f"{name}: missing {relative}")
        if not list((project / "op_host").glob("*.asc")):
            errors.append(f"{name}: missing op_host/*.asc")
        if not list((project / "op_kernel").glob("*.asc")):
            errors.append(f"{name}: missing op_kernel/*.asc")
        try:
            passed, detail = result_passed_20(project / "results.json")
            if not passed:
                errors.append(f"{name}: correctness is not 20/20 ({detail})")
        except ValueError as exc:
            errors.append(f"{name}: {exc}")

    digest = membership_digest(manifests)
    if digest != index.get("membership_sha256"):
        errors.append(
            "split membership digest mismatch: "
            f"expected={index.get('membership_sha256')}, actual={digest}"
        )

    expected_counts = {
        "development_train": len(active["train"]),
        "validation": len(active["validation"]),
        "sealed_test": len(active["test"]),
    }
    for role, count in expected_counts.items():
        recorded = index.get("splits", {}).get(role, {}).get("active_count")
        if recorded != count:
            errors.append(f"index count mismatch for {role}: {recorded!r} != {count}")

    if errors:
        print("CANNBench split validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "CANNBench split v0001 valid: "
        f"train={len(active['train'])} ready+{len(pending['train'])} pending, "
        f"validation={len(active['validation'])}, test={len(active['test'])}, "
        f"sha256={digest}"
    )
    official = index["inventory"]["official_summary_completed"]
    if official != len(ready_dirs):
        print(
            "note: benchmark_results.json records "
            f"{official} completed operators; filesystem readiness is {len(ready_dirs)}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

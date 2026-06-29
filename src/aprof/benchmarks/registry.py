from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aprof.benchmarks.models import BenchmarkCase, BenchmarkManifest
from aprof.core.errors import BenchmarkNotFoundError
from aprof.core.paths import benchmarks_dir


def load_json_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "cases" in payload:
        return payload["cases"]
    raise BenchmarkNotFoundError(f"unsupported manifest format: {path}")


def load_injected_ops_manifest(root: Path | None = None) -> BenchmarkManifest:
    root = root or benchmarks_dir() / "aprof_injected_ops"
    manifest_path = root / "manifest.json"
    entries = load_json_manifest(manifest_path)
    cases: list[BenchmarkCase] = []
    for entry in entries:
        op = str(entry.get("op", ""))
        variant = str(entry.get("variant", ""))
        case_path = root / op / variant
        cases.append(
            BenchmarkCase(
                name=f"{op}/{variant}",
                source="aprof_injected_ops",
                path=case_path,
                op=op,
                variant=variant,
                injected_label=str(entry.get("injected_label", "")),
                metadata=entry,
            )
        )
    return BenchmarkManifest(
        name="aprof_injected_ops",
        description="Injected AscendC vector-kernel benchmark cases with controlled anti-patterns.",
        cases=cases,
        adapter="local",
    )


def load_reference_ops(root: Path | None = None) -> BenchmarkManifest:
    root = root or benchmarks_dir() / "reference_ops"
    cases: list[BenchmarkCase] = []
    for case_dir in sorted(root.glob("*")):
        if not case_dir.is_dir():
            continue
        metadata_path = case_dir / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        cases.append(
            BenchmarkCase(
                name=case_dir.name,
                source="reference_ops",
                path=case_dir,
                op=case_dir.name,
                variant="reference",
                injected_label=str(metadata.get("injected_label", "reference")),
                metadata=metadata,
            )
        )
    return BenchmarkManifest(
        name="reference_ops",
        description="Reference AscendC workloads used as AProf benchmark seeds.",
        cases=cases,
        adapter="local",
    )


def list_manifests() -> list[BenchmarkManifest]:
    return [load_injected_ops_manifest(), load_reference_ops()]


def get_case(manifest_name: str, case_name: str) -> BenchmarkCase:
    for manifest in list_manifests():
        if manifest.name != manifest_name:
            continue
        for case in manifest.cases:
            if case.name == case_name or case.path.name == case_name:
                return case
    raise BenchmarkNotFoundError(f"case not found: {manifest_name}/{case_name}")

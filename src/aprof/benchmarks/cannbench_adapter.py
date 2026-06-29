from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from aprof.benchmarks.models import BenchmarkCase, BenchmarkManifest
from aprof.core.errors import BenchmarkNotFoundError
from aprof.core.paths import benchmarks_dir


class CannBenchAdapter:
    """Adapter skeleton for importing CANNBench reference operators."""

    def __init__(self, manifest_path: Path | None = None) -> None:
        self.manifest_path = manifest_path or benchmarks_dir() / "cannbench" / "manifest.yaml"

    def load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "name": "cannbench",
                "description": "Placeholder manifest for future CANNBench references.",
                "source_repo": "",
                "cases": [],
            }
        return yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))

    def list_cases(self) -> list[BenchmarkCase]:
        payload = self.load_manifest()
        cases: list[BenchmarkCase] = []
        for entry in payload.get("cases", []):
            case_path = benchmarks_dir() / "cannbench" / str(entry.get("path", ""))
            cases.append(
                BenchmarkCase(
                    name=str(entry.get("name", case_path.name)),
                    source="cannbench",
                    path=case_path,
                    op=str(entry.get("op", "")),
                    variant=str(entry.get("variant", "")),
                    injected_label=str(entry.get("label", "")),
                    metadata=entry,
                )
            )
        return cases

    def to_manifest(self) -> BenchmarkManifest:
        payload = self.load_manifest()
        return BenchmarkManifest(
            name=str(payload.get("name", "cannbench")),
            description=str(payload.get("description", "")),
            source_repo=str(payload.get("source_repo", "")),
            cases=self.list_cases(),
            adapter="cannbench",
        )

    def import_reference(self, source: str, name: str, target_subdir: str | None = None) -> BenchmarkCase:
        """Record a future CANNBench import without fetching external repos."""

        target = benchmarks_dir() / "cannbench" / (target_subdir or name)
        target.mkdir(parents=True, exist_ok=True)
        metadata = {
            "name": name,
            "source": source,
            "status": "pending_import",
            "path": str(target.relative_to(benchmarks_dir() / "cannbench")),
        }
        (target / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._append_manifest_entry(metadata)
        return BenchmarkCase(
            name=name,
            source="cannbench",
            path=target,
            metadata=metadata,
        )

    def _append_manifest_entry(self, entry: dict[str, Any]) -> None:
        payload = self.load_manifest()
        cases = list(payload.get("cases", []))
        if any(item.get("name") == entry.get("name") for item in cases):
            return
        cases.append(entry)
        payload["cases"] = cases
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def verify_case(self, case: BenchmarkCase) -> dict[str, Any]:
        required = ["run.sh"]
        missing = [name for name in required if not (case.path / name).exists()]
        return {
            "case": case.name,
            "path": str(case.path),
            "exists": case.path.exists(),
            "missing": missing,
            "ready": case.path.exists() and not missing,
        }

    def verify(self, name: str | None = None) -> list[dict[str, Any]]:
        cases = self.list_cases()
        if name is not None:
            cases = [case for case in cases if case.name == name]
            if not cases:
                raise BenchmarkNotFoundError(f"cannbench case not found: {name}")
        return [self.verify_case(case) for case in cases]

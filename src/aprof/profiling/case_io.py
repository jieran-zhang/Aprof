from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_case_metadata(case: Path, profile: Path | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    candidates = [case / "metadata.json", case / "build_sim" / "metadata.json"]
    if profile is not None:
        candidates.append(profile / "metadata.json")
    for path in candidates:
        if path.exists():
            merged.update(json.loads(path.read_text(encoding="utf-8")))
    return merged


def latest_profile(case: Path) -> Path:
    roots = sorted((case / "msprof_sim_output").glob("OPPROF_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not roots:
        return case / "msprof_sim_output"
    return roots[0]


def find_case_root(path: Path) -> Path | None:
    for parent in [path, *path.parents]:
        if (parent / "run.sh").exists() and (parent / "op_kernel").exists():
            return parent
    return None


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

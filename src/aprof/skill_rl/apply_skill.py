"""Apply executable skill edits to a direct-invoke operator case tree."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from aprof.skill_rl.models import Skill

PatchFn = Callable[[Path, int], list[str]]


@dataclass(frozen=True)
class Applicator:
    name: str
    min_value: int
    max_value: int
    apply: PatchFn
    alignment: int = 1

    def validate(self, value: int) -> None:
        if value < self.min_value or value > self.max_value:
            raise ValueError(f"{self.name} out of range: {value}")
        if value % self.alignment:
            raise ValueError(f"{self.name} must align to {self.alignment}: {value}")


def _patch_tile_length_in_text(text: str, new_tile: int) -> str:
    text = re.sub(
        r"(constexpr\s+uint32_t\s+kTileLength\s*=\s*)\d+(\s*U?)",
        rf"\g<1>{new_tile}\2",
        text,
    )
    text = re.sub(
        r'("tile_length"\s*:\s*)\d+',
        rf"\g<1>{new_tile}",
        text,
    )
    return text


def apply_tile_length(case_dir: Path, new_tile: int) -> list[str]:
    """Rewrite tile_length knobs in a case directory. Returns changed relative paths."""
    changed: list[str] = []
    targets = [
        case_dir / "case_metadata.json",
        case_dir / "op_host" / "main.asc",
        case_dir / "scripts" / "gen_data.py",
    ]
    for path in targets:
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        new = _patch_tile_length_in_text(old, new_tile)
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(case_dir)).replace("\\", "/"))
    # Keep case_id distinct if present.
    meta = case_dir / "case_metadata.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["tile_length"] = int(new_tile)
        if str(data.get("case_id", "")).startswith("op_"):
            data["case_id"] = case_dir.name
        meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        if "case_metadata.json" not in changed:
            changed.append("case_metadata.json")
    return changed


def _patch_integer_knob(
    case_dir: Path,
    *,
    metadata_key: str,
    constant_name: str,
    value: int,
) -> list[str]:
    changed: list[str] = []
    targets = [
        case_dir / "case_metadata.json",
        case_dir / "op_host" / "main.asc",
        case_dir / "scripts" / "gen_data.py",
    ]
    constant = re.compile(
        rf"(constexpr\s+uint32_t\s+{re.escape(constant_name)}\s*=\s*)\d+(\s*U?)"
    )
    json_key = re.compile(rf'("{re.escape(metadata_key)}"\s*:\s*)\d+')
    for path in targets:
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        new = constant.sub(rf"\g<1>{value}\2", old)
        new = json_key.sub(rf"\g<1>{value}", new)
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(case_dir)).replace("\\", "/"))
    meta = case_dir / "case_metadata.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        data[metadata_key] = value
        data["case_id"] = case_dir.name
        meta.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        if "case_metadata.json" not in changed:
            changed.append("case_metadata.json")
    return changed


def apply_blockdim(case_dir: Path, value: int) -> list[str]:
    return _patch_integer_knob(
        case_dir,
        metadata_key="blockdim",
        constant_name="kBlockDim",
        value=value,
    )


def apply_tile_num(case_dir: Path, value: int) -> list[str]:
    return _patch_integer_knob(
        case_dir,
        metadata_key="tile_num_mul",
        constant_name="kTileNumMul",
        value=value,
    )


APPLICATORS: dict[str, Applicator] = {
    "tile_length": Applicator("tile_length", 8, 65536, apply_tile_length, alignment=8),
    "blockdim": Applicator("blockdim", 1, 64, apply_blockdim),
    "tile_num": Applicator("tile_num", 1, 4096, apply_tile_num),
    "tile_num_mul": Applicator("tile_num_mul", 1, 4096, apply_tile_num),
}


def _rename_cmake_target(case_dir: Path, op_name: str, case_id: str) -> None:
    cmake = case_dir / "CMakeLists.txt"
    if not cmake.is_file():
        return
    old = cmake.read_text(encoding="utf-8")
    new_name = f"{op_name}_{case_id}"
    # Replace any previous op_* target tokens.
    text = re.sub(rf"{re.escape(op_name)}_op_\d{{4}}", new_name, old)
    if text != old:
        cmake.write_text(text, encoding="utf-8", newline="\n")


def materialize_optimized_case(
    src_case: Path,
    dst_case: Path,
    *,
    skill: Skill,
    target_tile_length: int | None = None,
    parameters: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Copy a case and apply registered, validated skill parameters."""
    if dst_case.exists():
        shutil.rmtree(dst_case)
    shutil.copytree(
        src_case,
        dst_case,
        ignore=shutil.ignore_patterns(
            "build",
            "build_sim",
            "data",
            "msprof_*",
            "__pycache__",
            ".ground_truth",
        ),
    )
    values = dict(parameters or {})
    if target_tile_length is not None:
        values.setdefault("tile_length", int(target_tile_length))
    applied: list[dict[str, Any]] = []
    for edit in skill.actionable_edits:
        if not isinstance(edit, dict):
            continue
        knob = str(edit.get("adjust") or "")
        if knob in APPLICATORS and knob in values:
            applicator = APPLICATORS[knob]
            value = int(values[knob])
            applicator.validate(value)
            files = applicator.apply(dst_case, value)
            applied.append(
                {
                    "skill_id": skill.id,
                    "adjust": knob,
                    "to": value,
                    "files": files,
                    "notes": edit.get("notes"),
                }
            )
        elif edit.get("from_trajectory") and "tile_length" in values:
            applicator = APPLICATORS["tile_length"]
            value = int(values["tile_length"])
            applicator.validate(value)
            files = applicator.apply(dst_case, value)
            applied.append(
                {
                    "skill_id": skill.id,
                    "adjust": "tile_length",
                    "to": value,
                    "files": files,
                    "notes": "from_trajectory_fallback",
                    "code_changes": edit.get("code_changes"),
                }
            )
    op_name = dst_case.parent.parent.name
    case_id = dst_case.name
    _rename_cmake_target(dst_case, op_name, case_id)
    run_sh = dst_case / "run.sh"
    if run_sh.is_file():
        text = run_sh.read_text(encoding="utf-8")
        text2 = re.sub(
            r'TARGET_NAME="[^"]+"',
            f'TARGET_NAME="{op_name}_{case_id}"',
            text,
            count=1,
        )
        if text2 != text:
            run_sh.write_text(text2, encoding="utf-8", newline="\n")
    return {
        "src": str(src_case),
        "dst": str(dst_case),
        "skill_id": skill.id,
        "applied": applied,
        "parameters": values,
        "target_tile_length": values.get("tile_length"),
        "rollback": {"strategy": "discard_materialized_case", "source": str(src_case)},
    }

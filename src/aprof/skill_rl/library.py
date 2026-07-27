"""Versioned skill library load/commit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aprof.skill_rl import simple_yaml as yaml
from aprof.skill_rl.models import Skill, SkillEdit, SkillLibrarySnapshot

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "skills" / "aprof" / "skill_library"
FAMILIES = (
    "tiling",
    "data_movement",
    "pipeline_parallel",
    "onchip_memory",
    "ai_core_utilization",
    "api_algorithm",
)


def _skill_from_dict(d: dict[str, Any]) -> Skill:
    return Skill(
        id=str(d["id"]),
        family=str(d.get("family") or "unknown"),
        version=int(d.get("version") or 1),
        scope=d.get("scope") or "production_safe",  # type: ignore[arg-type]
        preconditions=list(d.get("preconditions") or []),
        actionable_edits=list(d.get("actionable_edits") or []),
        expected_metric_delta=dict(d.get("expected_metric_delta") or {}),
        measurement_policy=dict(d.get("measurement_policy") or {}),
        linked_hypotheses=list(d.get("linked_hypotheses") or []),
        contraindications=list(d.get("contraindications") or []),
        notes=str(d.get("notes") or ""),
    )


def _skill_to_dict(s: Skill) -> dict[str, Any]:
    return {
        "id": s.id,
        "family": s.family,
        "version": s.version,
        "scope": s.scope,
        "preconditions": s.preconditions,
        "actionable_edits": s.actionable_edits,
        "expected_metric_delta": s.expected_metric_delta,
        "measurement_policy": s.measurement_policy,
        "linked_hypotheses": s.linked_hypotheses,
        "contraindications": s.contraindications,
        "notes": s.notes,
    }


def content_hash(skills: dict[str, Skill]) -> str:
    blob = json.dumps(
        {k: _skill_to_dict(v) for k, v in sorted(skills.items())},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class SkillLibrary:
    def __init__(self, root: Path | None = None, version_label: str = "v0"):
        self.root = Path(root) if root else DEFAULT_ROOT
        self.version_label = version_label
        self.skills: dict[str, Skill] = {}

    @property
    def version_dir(self) -> Path:
        return self.root / self.version_label

    def load(self) -> SkillLibrarySnapshot:
        skills: dict[str, Skill] = {}
        vdir = self.version_dir
        if not vdir.exists():
            self.skills = {}
            return SkillLibrarySnapshot(version_label=self.version_label, skills={}, content_hash="")
        for path in sorted(vdir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, list):
                for item in data:
                    sk = _skill_from_dict(item)
                    skills[sk.id] = sk
            elif isinstance(data, dict) and "id" in data:
                sk = _skill_from_dict(data)
                skills[sk.id] = sk
            elif isinstance(data, dict) and "skills" in data:
                for item in data["skills"]:
                    sk = _skill_from_dict(item)
                    skills[sk.id] = sk
        self.skills = skills
        return SkillLibrarySnapshot(
            version_label=self.version_label,
            skills=dict(skills),
            content_hash=content_hash(skills),
        )

    def apply_edits(self, edits: list[SkillEdit]) -> list[SkillEdit]:
        """Apply edits in-memory; return applied list."""
        applied: list[SkillEdit] = []
        for edit in edits:
            if edit.scope == "benchmark_specialized":
                # Do not write specialized into primary library.
                continue
            if edit.op == "ADD" or edit.op == "UPDATE":
                payload = dict(edit.payload)
                payload.setdefault("id", edit.skill_id)
                if edit.skill_id in self.skills:
                    old = self.skills[edit.skill_id]
                    payload.setdefault("family", old.family)
                    payload["version"] = int(old.version) + 1
                    # Merge contraindications.
                    cons = list(dict.fromkeys(list(old.contraindications) + list(payload.get("contraindications") or [])))
                    payload["contraindications"] = cons
                    if not payload.get("actionable_edits"):
                        payload["actionable_edits"] = list(old.actionable_edits)
                    if not payload.get("expected_metric_delta"):
                        payload["expected_metric_delta"] = dict(old.expected_metric_delta)
                sk = _skill_from_dict(payload)
                if not sk.is_actionable() and edit.op == "ADD":
                    continue
                self.skills[edit.skill_id] = sk
                applied.append(edit)
            elif edit.op == "DEPRECATE":
                if edit.skill_id in self.skills:
                    sk = self.skills[edit.skill_id]
                    tip = str(edit.payload.get("contraindication") or edit.rationale or "deprecated_by_curator")
                    if tip not in sk.contraindications:
                        sk.contraindications.append(tip)
                    sk.version += 1
                    applied.append(edit)
                else:
                    # Record floating contraindication skill stub.
                    sk = Skill(
                        id=edit.skill_id,
                        family=str(edit.payload.get("family") or "unknown"),
                        actionable_edits=[{"note": "deprecated_without_body"}],
                        expected_metric_delta={"primary": "TaskDuration_median_us", "direction": "decrease", "min_effect_pct": 3.0},
                        contraindications=[str(edit.payload.get("contraindication") or edit.rationale or "failed_candidate")],
                        notes="deprecate_stub",
                    )
                    self.skills[edit.skill_id] = sk
                    applied.append(edit)
        return applied

    def commit(self, new_version_label: str) -> SkillLibrarySnapshot:
        out = self.root / new_version_label
        out.mkdir(parents=True, exist_ok=True)
        by_family: dict[str, list[dict[str, Any]]] = {f: [] for f in FAMILIES}
        for sk in self.skills.values():
            fam = sk.family if sk.family in by_family else "tiling"
            by_family.setdefault(fam, []).append(_skill_to_dict(sk))
        for fam, items in by_family.items():
            path = out / f"{fam}.yaml"
            path.write_text(
                yaml.safe_dump({"skills": items}, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
        snap = SkillLibrarySnapshot(
            version_label=new_version_label,
            skills=dict(self.skills),
            content_hash=content_hash(self.skills),
        )
        manifest = {
            "version_label": new_version_label,
            "content_hash": snap.content_hash,
            "skill_ids": sorted(self.skills.keys()),
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.version_label = new_version_label
        return snap

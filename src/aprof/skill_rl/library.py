"""Versioned skill library load/commit."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
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


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


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
        hardware_scope=list(d.get("hardware_scope") or []),
        workload_scope=list(d.get("workload_scope") or []),
        operator_scope=list(d.get("operator_scope") or []),
        evidence_episode_ids=list(d.get("evidence_episode_ids") or []),
        success_count=int(d.get("success_count") or 0),
        failure_count=int(d.get("failure_count") or 0),
        last_used_at=str(d.get("last_used_at") or ""),
        confidence=float(d.get("confidence") or 0.0),
        tombstone=bool(d.get("tombstone") or False),
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
        "hardware_scope": s.hardware_scope,
        "workload_scope": s.workload_scope,
        "operator_scope": s.operator_scope,
        "evidence_episode_ids": s.evidence_episode_ids,
        "success_count": s.success_count,
        "failure_count": s.failure_count,
        "last_used_at": s.last_used_at,
        "confidence": s.confidence,
        "tombstone": s.tombstone,
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
        self.audit_log: list[dict[str, Any]] = []
        self.parent_hash: str = ""
        self.training_run_id: str = ""
        self.base_content_hash: str = ""

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
        manifest_path = vdir / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.parent_hash = str(manifest.get("parent_hash") or "")
            self.training_run_id = str(manifest.get("training_run_id") or "")
        audit_path = vdir / "edit_audit.jsonl"
        if audit_path.is_file():
            self.audit_log = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        self.skills = skills
        self.base_content_hash = content_hash(skills)
        return SkillLibrarySnapshot(
            version_label=self.version_label,
            skills=dict(skills),
            content_hash=content_hash(skills),
            parent_hash=self.parent_hash,
            training_run_id=self.training_run_id,
            audit_log=list(self.audit_log),
        )

    def clone(self) -> "SkillLibrary":
        trial = SkillLibrary(root=self.root, version_label=self.version_label)
        trial.skills = deepcopy(self.skills)
        trial.audit_log = deepcopy(self.audit_log)
        trial.parent_hash = self.parent_hash
        trial.training_run_id = self.training_run_id
        trial.base_content_hash = self.base_content_hash or content_hash(self.skills)
        return trial

    def apply_edits(
        self,
        edits: list[SkillEdit],
        *,
        library_budget: int | None = None,
        transaction_id: str = "",
    ) -> list[SkillEdit]:
        """Atomically apply edits in-memory and append an audit trail."""
        before = deepcopy(self.skills)
        before_audit = list(self.audit_log)
        applied: list[SkillEdit] = []
        try:
            for edit in edits:
                target_id = edit.target_skill_id or edit.skill_id
                if edit.scope == "benchmark_specialized":
                    continue
                if edit.op == "NOOP":
                    applied.append(edit)
                elif edit.op in ("ADD", "UPDATE"):
                    payload = dict(edit.payload)
                    payload.setdefault("id", target_id)
                    if target_id in self.skills:
                        old = self.skills[target_id]
                        payload.setdefault("family", old.family)
                        payload["version"] = int(old.version) + 1
                        payload.setdefault("preconditions", list(old.preconditions))
                        payload.setdefault("measurement_policy", dict(old.measurement_policy))
                        payload.setdefault("linked_hypotheses", list(old.linked_hypotheses))
                        payload.setdefault("hardware_scope", list(old.hardware_scope))
                        payload.setdefault("workload_scope", list(old.workload_scope))
                        payload.setdefault("operator_scope", list(old.operator_scope))
                        payload["success_count"] = old.success_count + int(
                            payload.get("success_count") or 0
                        )
                        payload["failure_count"] = old.failure_count + int(
                            payload.get("failure_count") or 0
                        )
                        payload["confidence"] = max(
                            old.confidence,
                            float(payload.get("confidence") or 0.0),
                        )
                        payload["tombstone"] = False
                        cons = list(
                            dict.fromkeys(
                                list(old.contraindications)
                                + list(payload.get("contraindications") or [])
                            )
                        )
                        payload["contraindications"] = cons
                        evidence = list(
                            dict.fromkeys(
                                list(old.evidence_episode_ids)
                                + list(edit.evidence_episode_ids)
                                + list(payload.get("evidence_episode_ids") or [])
                            )
                        )
                        payload["evidence_episode_ids"] = evidence
                        if not payload.get("actionable_edits"):
                            payload["actionable_edits"] = list(old.actionable_edits)
                        if not payload.get("expected_metric_delta"):
                            payload["expected_metric_delta"] = dict(old.expected_metric_delta)
                    else:
                        payload.setdefault("evidence_episode_ids", list(edit.evidence_episode_ids))
                    sk = _skill_from_dict(payload)
                    if not sk.is_actionable() and edit.op == "ADD":
                        continue
                    self.skills[target_id] = sk
                    applied.append(edit)
                elif edit.op == "DELETE":
                    if target_id not in self.skills:
                        continue
                    sk = self.skills[target_id]
                    sk.tombstone = True
                    sk.version += 1
                    sk.failure_count += 1
                    applied.append(edit)
                elif edit.op == "DEPRECATE":
                    if target_id not in self.skills:
                        continue
                    sk = self.skills[target_id]
                    tip = str(edit.payload.get("contraindication") or edit.rationale or "deprecated_by_curator")
                    if tip not in sk.contraindications:
                        sk.contraindications.append(tip)
                    sk.version += 1
                    sk.failure_count += 1
                    applied.append(edit)
                if edit in applied:
                    self.audit_log.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "transaction_id": transaction_id,
                            "op": edit.op,
                            "skill_id": target_id,
                            "evidence_episode_ids": list(edit.evidence_episode_ids),
                            "policy_name": edit.policy_name,
                            "candidate_group_id": edit.candidate_group_id,
                            "rationale": edit.rationale,
                        }
                    )
            live_count = sum(1 for skill in self.skills.values() if not skill.tombstone)
            if library_budget is not None and live_count > library_budget:
                raise ValueError(f"library budget exceeded: {live_count}>{library_budget}")
        except Exception:
            self.skills = before
            self.audit_log = before_audit
            raise
        return applied

    def commit(
        self,
        new_version_label: str,
        *,
        training_run_id: str = "",
    ) -> SkillLibrarySnapshot:
        out = self.root / new_version_label
        out.mkdir(parents=True, exist_ok=True)
        by_family: dict[str, list[dict[str, Any]]] = {f: [] for f in FAMILIES}
        for sk in self.skills.values():
            fam = sk.family if sk.family in by_family else "tiling"
            by_family.setdefault(fam, []).append(_skill_to_dict(sk))
        for fam, items in by_family.items():
            path = out / f"{fam}.yaml"
            _atomic_write(
                path,
                yaml.safe_dump({"skills": items}, sort_keys=False, allow_unicode=True),
            )
        snap = SkillLibrarySnapshot(
            version_label=new_version_label,
            skills=dict(self.skills),
            content_hash=content_hash(self.skills),
            parent_hash=self.base_content_hash,
            training_run_id=training_run_id or self.training_run_id,
            audit_log=list(self.audit_log),
        )
        manifest = {
            "version_label": new_version_label,
            "content_hash": snap.content_hash,
            "parent_hash": snap.parent_hash,
            "training_run_id": snap.training_run_id,
            "skill_ids": sorted(self.skills.keys()),
        }
        _atomic_write(out / "manifest.json", json.dumps(manifest, indent=2))
        _atomic_write(
            out / "edit_audit.jsonl",
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in self.audit_log),
        )
        self.version_label = new_version_label
        self.parent_hash = snap.content_hash
        self.base_content_hash = snap.content_hash
        self.training_run_id = snap.training_run_id
        return snap

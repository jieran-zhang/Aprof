"""Central configuration for the SAGE × Memory-R1 demo."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SkillRlConfig:
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.25
    allow_cross_operator: bool = True
    allow_cross_hardware: bool = False
    merge_threshold: float = 0.8
    chain_length: int = 2
    candidate_group_size: int = 4
    min_warmup: int = 10
    min_repeat: int = 5
    max_cv: float = 0.05
    min_effect_pct: float = 3.0
    library_budget: int = 128
    reuse_bonus: float = 0.25
    edit_bonus_scale: float = 0.5
    measurement_cost: float = 0.01
    candidate_cost: float = 0.005
    duplicate_penalty: float = 0.05
    conflict_penalty: float = 0.10
    specialized_penalty: float = 0.10

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SkillRlConfig":
        raw = raw or {}
        known = {key: value for key, value in raw.items() if key in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, path: Path) -> "SkillRlConfig":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

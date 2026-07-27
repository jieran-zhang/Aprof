"""Train/Dev/Test split helpers for Skill-RL fixtures / inject lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class SplitSpec:
    train: list[str] = field(default_factory=list)
    dev: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {"train": list(self.train), "dev": list(self.dev), "test": list(self.test)}


def split_case_ids(case_ids: Iterable[str], *, seed: int = 0) -> SplitSpec:
    """Deterministic round-robin split for small demo sets."""
    ids = sorted(case_ids)
    if seed:
        # Simple rotate for reproducibility without random module dependency surprises.
        k = seed % max(len(ids), 1)
        ids = ids[k:] + ids[:k]
    train, dev, test = [], [], []
    for i, cid in enumerate(ids):
        bucket = i % 3
        if bucket == 0:
            train.append(cid)
        elif bucket == 1:
            dev.append(cid)
        else:
            test.append(cid)
    # Ensure non-empty train/dev when possible.
    if not train and ids:
        train.append(ids[0])
    if not dev and len(ids) > 1:
        dev.append(ids[1])
    return SplitSpec(train=train, dev=dev, test=test)


def demo_dual_fixture_split() -> SplitSpec:
    """Canonical demo split for Fixture A/B."""
    return SplitSpec(
        train=["fast_gelu_large_weak_start"],
        dev=["fast_gelu_2048_strong_baseline"],
        test=["fast_gelu_2048_strong_baseline"],
    )


def stratified_keys(rows: list[dict[str, Any]], key_fields: tuple[str, ...] = ("op", "family")) -> list[str]:
    keys = []
    for r in rows:
        parts = [str(r.get(k) or "unknown") for k in key_fields]
        keys.append("|".join(parts) + "|" + str(r.get("case_id") or r.get("id") or len(keys)))
    return keys

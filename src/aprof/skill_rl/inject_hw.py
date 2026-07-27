"""Load 910B inject-restore Skill-RL episodes from fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from aprof.skill_rl.episode_adapter import adapt_fixture_b, FIXTURE_DIR
from aprof.skill_rl.models import Episode


def _adapt_inject_dict(data: dict) -> Episode:
    """Reuse Fixture B adapter shape (strong baseline / production best)."""
    # Temporarily write-compatible: adapt_fixture_b already understands this schema.
    return adapt_fixture_b(data)


def load_inject_hw_train(limit: int = 0) -> list[Episode]:
    index_path = FIXTURE_DIR / "inject_hw_train" / "index.json"
    if not index_path.is_file():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    eps: list[Episode] = []
    for item in index.get("episodes") or []:
        rel = item.get("path")
        if not rel:
            continue
        path = Path(__file__).resolve().parents[3] / rel
        if not path.is_file():
            # fallback relative to fixture dir
            path = FIXTURE_DIR / "inject_hw_train" / Path(rel).name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ep = _adapt_inject_dict(data)
        # Prefer offline GT correctness when baseline verified.
        gt = data.get("ground_truth_offline") or {}
        ep.metadata["inject_gt"] = gt
        ep.metadata["source_910b"] = True
        eps.append(ep)
        if limit and len(eps) >= limit:
            break
    return eps

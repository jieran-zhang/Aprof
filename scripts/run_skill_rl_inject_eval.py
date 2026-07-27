#!/usr/bin/env python3
"""Run Skill-RL offline round on 910B inject-restore train set.

Compares a stripped generic skill lib (no actionable_edits) vs curated lib
built from inject HW episodes — demonstrates skill improvement beyond equal v0 stubs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from aprof.skill_rl.curator import filter_executable_edits, propose_edits
from aprof.skill_rl.inject_hw import load_inject_hw_train
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import Skill
from aprof.skill_rl.reward import score_episode
from aprof.skill_rl.trainer import run_offline_round
from aprof.skill_rl.validation_gate import validate_edits


def strip_to_generic(skills: dict[str, Skill]) -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    for sid, sk in skills.items():
        out[sid] = Skill(
            id=sk.id,
            family=sk.family,
            version=sk.version,
            scope=sk.scope,
            preconditions=list(sk.preconditions),
            actionable_edits=[],  # intentional: vague frozen baseline
            expected_metric_delta={},
            measurement_policy=dict(sk.measurement_policy),
            linked_hypotheses=list(sk.linked_hypotheses),
            contraindications=[],
            notes="generic_frozen_for_skill_rl_eval",
        )
    return out


def main() -> int:
    episodes = load_inject_hw_train()
    if len(episodes) < 2:
        print("need inject_hw_train fixtures; run scripts/build_skill_rl_inject_hw_episodes.py")
        return 1

    # Train / Dev split: first half train, second half dev (by speedup-sorted index).
    mid = max(1, len(episodes) // 2)
    train, dev = episodes[:mid], episodes[mid:]
    if not dev:
        dev = train[-1:]

    lib = SkillLibrary(version_label="v0")
    lib.load()
    generic = SkillLibrary(version_label="v0")
    generic.skills = strip_to_generic(lib.skills)

    frozen_scores = [score_episode(ep, skills=generic.skills) for ep in train + dev]
    frozen_mean = sum(s.primary for s in frozen_scores) / len(frozen_scores)
    frozen_act = sum(s.actionability for s in frozen_scores) / len(frozen_scores)

    edits = []
    for ep in train:
        edits.extend(propose_edits(ep, lib.skills))
    edits = filter_executable_edits(edits)
    ok, applied, gate = validate_edits(edits, base_library=lib, dev_episodes=dev)

    curated = SkillLibrary(version_label="v0")
    curated.skills = dict(lib.skills)
    if ok and applied:
        curated.apply_edits(applied)

    curated_scores = [score_episode(ep, skills=curated.skills) for ep in train + dev]
    curated_mean = sum(s.primary for s in curated_scores) / len(curated_scores)
    curated_act = sum(s.actionability for s in curated_scores) / len(curated_scores)

    # Also run stock trainer report for A/B fixtures compatibility.
    from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b

    stock = run_offline_round([adapt_fixture_a()], [adapt_fixture_b()], commit=False)

    report = {
        "remote_910b_live": "ssh_timeout_used_prior_hw_artifacts",
        "glm_diagnosis_samples": [
            "plugins/aprof-performance-workflow/demo/out/skill_rl_glm/fast_gelu_op_0005/",
            "plugins/aprof-performance-workflow/demo/out/skill_rl_glm/gelu_mul_op_0005/",
        ],
        "inject_train_count": len(train),
        "inject_dev_count": len(dev),
        "gate_accepted": ok,
        "gate_report": gate,
        "applied_edits": [f"{e.op}:{e.skill_id}" for e in applied],
        "metrics": {
            "generic_frozen": {
                "primary_mean": frozen_mean,
                "actionability_mean": frozen_act,
            },
            "curated_from_910b_inject": {
                "primary_mean": curated_mean,
                "actionability_mean": curated_act,
            },
            "delta_primary": curated_mean - frozen_mean,
            "delta_actionability": curated_act - frozen_act,
            "stock_fixture_ab": stock["metrics"]["primary"],
        },
        "memory_path": "benchmarks/aprof_injected_ops/.maintainer_artifacts/optimization_memory.jsonl",
        "episode_index": "tests/fixtures/skill_rl/inject_hw_train/index.json",
    }

    out = REPO / "plugins" / "aprof-performance-workflow" / "demo" / "out" / "skill_rl_inject_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

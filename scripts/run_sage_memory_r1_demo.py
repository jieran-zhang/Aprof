#!/usr/bin/env python3
"""Run the dependency-free SAGE × Memory-R1 replay demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from aprof.skill_rl.config import SkillRlConfig  # noqa: E402
from aprof.skill_rl.inject_hw import load_inject_hw_train  # noqa: E402
from aprof.skill_rl.library import SkillLibrary  # noqa: E402
from aprof.skill_rl.memory_manager import FrozenPolicy, RulePolicy, SampledPolicy  # noqa: E402
from aprof.skill_rl.sequential_rollout import (  # noqa: E402
    build_task_chains,
    run_managed_rollout,
)
from aprof.skill_rl.splits import (  # noqa: E402
    assert_no_group_leakage,
    group_stratified_split,
)
from aprof.skill_rl.transition_dataset import (  # noqa: E402
    build_transition_dataset,
    write_jsonl,
)
from aprof.skill_rl.trainer import run_group_relative_round  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "tests" / "fixtures" / "skill_rl" / "sage_memory_r1_demo_report.json",
    )
    parser.add_argument(
        "--transitions",
        type=Path,
        default=REPO / "tests" / "fixtures" / "skill_rl" / "transition_dataset.jsonl",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO / "configs" / "skill_rl_sage_memory_r1_mvp.json",
    )
    parser.add_argument("--chain-length", type=int, default=2)
    parser.add_argument(
        "--verl-output",
        type=Path,
        default=REPO / "tests" / "fixtures" / "skill_rl" / "verl_trajectories.jsonl",
    )
    return parser.parse_args()


def summarize(trace) -> dict:
    steps = trace.steps
    return {
        "scenario_id": trace.scenario_id,
        "steps": [
            {
                "episode_id": step.episode_id,
                "retrieved": step.retrieved_skill_ids,
                "used": step.used_skill_ids,
                "generated": step.generated_skill_ids,
                "edits": step.edit_actions,
                "outcome_reward": step.outcome_reward,
                "reuse_reward": step.reuse_reward,
                "edit_reward": step.edit_reward,
                "training_reward": step.training_reward,
                "bank_hash_before": step.bank_hash_before,
                "bank_hash_after": step.bank_hash_after,
            }
            for step in steps
        ],
        "mean_training_reward": (
            sum(step.training_reward for step in steps) / len(steps) if steps else 0.0
        ),
        "success_skill_usage_rate": (
            sum(bool(set(step.retrieved_skill_ids) & set(step.used_skill_ids)) for step in steps)
            / len(steps)
            if steps
            else 0.0
        ),
        "library_size": sum(not skill.tombstone for skill in trace.final_skills.values()),
    }


def main() -> int:
    args = parse_args()
    episodes = load_inject_hw_train()
    if not episodes:
        raise SystemExit("no inject_hw_train fixtures")
    library = SkillLibrary(version_label="v0")
    library.load()
    base_config = SkillRlConfig.from_json(args.config)

    rows = []
    for episode in episodes:
        strategy = episode.actionable_strategy_ids[0] if episode.actionable_strategy_ids else "unknown"
        problem = str(episode.metadata.get("problem_id") or strategy)
        rows.append(
            {
                "case_id": episode.case_id,
                "op": episode.op_name,
                "problem_family": problem,
                "shape_family": episode.workload.workload_class,
            }
        )
    split = group_stratified_split(rows, seed=7)
    assert_no_group_leakage(rows, split)

    for episode in episodes:
        episode.metadata.setdefault("frozen_outcome", 0.0)
        episode.metadata.setdefault(
            "edited_outcome",
            min(1.0, float(episode.combined_speedup or 1.0) / 5.0),
        )
        episode.metadata.setdefault("hardware", "Ascend910B")

    ablations: dict[str, list[dict]] = {
        "frozen_outcome_only": [],
        "current_rule_curator": [],
        "memory_manager_without_reuse": [],
        "sage_reuse_without_edit_credit": [],
        "combined": [],
    }
    chains = build_task_chains(episodes, chain_length=args.chain_length)
    for selected in chains:

        replay_kwargs = {
            "chain_length": args.chain_length,
            "min_warmup": 3,
            "min_repeat": 1,
            "max_cv": 1.0,
            "retrieval_top_k": base_config.retrieval_top_k,
            "retrieval_min_score": base_config.retrieval_min_score,
            "candidate_group_size": base_config.candidate_group_size,
            "library_budget": base_config.library_budget,
            "edit_bonus_scale": base_config.edit_bonus_scale,
        }
        frozen_cfg = SkillRlConfig(**replay_kwargs, reuse_bonus=0.0)
        rule_cfg = SkillRlConfig(
            **{**replay_kwargs, "edit_bonus_scale": 0.0},
            reuse_bonus=0.0,
        )
        no_reuse_cfg = SkillRlConfig(**replay_kwargs, reuse_bonus=0.0)
        sage_cfg = SkillRlConfig(
            **{**replay_kwargs, "edit_bonus_scale": 0.0},
            reuse_bonus=base_config.reuse_bonus,
        )
        combined_cfg = SkillRlConfig(**replay_kwargs, reuse_bonus=base_config.reuse_bonus)
        ablations["frozen_outcome_only"].append(
            summarize(
                run_managed_rollout(
                    selected,
                    initial_skills=library.skills,
                    manager_policy=FrozenPolicy(),
                    config=frozen_cfg,
                )
            )
        )
        ablations["memory_manager_without_reuse"].append(
            summarize(
                run_managed_rollout(
                    selected,
                    initial_skills=library.skills,
                    manager_policy=RulePolicy(),
                    config=no_reuse_cfg,
                )
            )
        )
        ablations["current_rule_curator"].append(
            summarize(
                run_managed_rollout(
                    selected,
                    initial_skills=library.skills,
                    manager_policy=RulePolicy(),
                    config=rule_cfg,
                )
            )
        )
        ablations["sage_reuse_without_edit_credit"].append(
            summarize(
                run_managed_rollout(
                    selected,
                    initial_skills=library.skills,
                    manager_policy=RulePolicy(),
                    config=sage_cfg,
                )
            )
        )
        ablations["combined"].append(
            summarize(
                run_managed_rollout(
                    selected,
                    initial_skills=library.skills,
                    manager_policy=RulePolicy(),
                    config=combined_cfg,
                )
            )
        )

    report_paths = [
        REPO / "tests" / "fixtures" / "skill_rl" / "msprof_live_score_report.json",
        REPO / "tests" / "fixtures" / "skill_rl" / "closed_loop_hw_report.json",
    ]
    transitions = build_transition_dataset(report_paths)
    write_jsonl(transitions, args.transitions)

    def sampled_actions(prompt: dict, group_size: int):
        episode = prompt["episode"]
        strategy = (episode.get("actionable_strategy_ids") or ["tiling.generated"])[0]
        current = prompt.get("skills", {}).get(strategy) or {}
        payload = {
            "family": strategy.split(".", 1)[0],
            "actionable_edits": current.get("actionable_edits")
            or [{"from_trajectory": True}],
            "expected_metric_delta": current.get("expected_metric_delta")
            or {"primary": "TaskDuration_median_us", "direction": "decrease"},
        }
        candidates = [
            {"op": "NOOP", "candidate_id": "noop"},
            {
                "op": "UPDATE",
                "skill_id": strategy,
                "payload": payload,
                "candidate_id": "update",
            },
            {"op": "DELETE", "skill_id": strategy, "candidate_id": "delete"},
            {
                "op": "ADD",
                "skill_id": strategy + ".candidate",
                "payload": payload,
                "candidate_id": "add",
            },
        ]
        return candidates[:group_size]

    if args.verl_output.exists():
        args.verl_output.unlink()
    replay_config = SkillRlConfig(
        retrieval_top_k=base_config.retrieval_top_k,
        retrieval_min_score=base_config.retrieval_min_score,
        candidate_group_size=base_config.candidate_group_size,
        min_warmup=3,
        min_repeat=1,
        max_cv=1.0,
    )
    training = run_group_relative_round(
        episodes[:4],
        policy=SampledPolicy(sampled_actions),
        base_library=library,
        config=replay_config,
        verl_output=args.verl_output,
    )
    selected_actions = [
        group["selected"].split(":", 1)[0] for group in training["groups"]
    ]
    action_distribution = {
        op: selected_actions.count(op) for op in ("ADD", "UPDATE", "DELETE", "NOOP")
    }
    beneficial = 0
    for group in training["groups"]:
        selected = next(
            candidate
            for candidate in group["candidates"]
            if candidate["edit"] == group["selected"]
        )
        beneficial += selected["reward"] > 0
    report = {
        "schema_version": 1,
        "method": "SAGE sequential reuse + Memory-R1 structured edits",
        "data_split": split.to_dict(),
        "ablations": ablations,
        "transition_dataset": str(args.transitions),
        "transition_count": len(transitions),
        "light_training": {
            "groups": training["groups"],
            "selector_weights": training["selector_weights"],
            "verl_output": str(args.verl_output),
            "trajectory_count": len(
                args.verl_output.read_text(encoding="utf-8").splitlines()
            ),
            "selected_action_distribution": action_distribution,
            "beneficial_edit_precision": (
                beneficial / len(training["groups"]) if training["groups"] else 0.0
            ),
        },
        "replay_measurement_policy": {
            "min_warmup": 3,
            "min_repeat": 1,
            "purpose": "historical candidate ranking only; live gate remains warmup=10/repeat=5/CV<=5%",
        },
        "caveat": (
            "Replay rewards are counterfactual labels from existing episodes; "
            "only closed_loop_hw_report entries are live 910B skill-apply measurements."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "transition_count": len(transitions)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

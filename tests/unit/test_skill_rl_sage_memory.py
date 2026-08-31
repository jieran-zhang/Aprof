import json
import tempfile
import unittest
from pathlib import Path

from aprof.skill_rl.apply_skill import materialize_optimized_case
from aprof.skill_rl.config import SkillRlConfig
from aprof.skill_rl.group_relative import group_relative_advantages
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.memory_manager import FrozenPolicy, RulePolicy, SampledPolicy
from aprof.skill_rl.models import (
    Candidate,
    Episode,
    Measurement,
    Round,
    Skill,
    SkillEdit,
    WorkloadModel,
)
from aprof.skill_rl.sequential_rollout import build_task_chains, run_managed_rollout
from aprof.skill_rl.splits import assert_no_group_leakage, group_stratified_split
from aprof.skill_rl.trainer import run_group_relative_round
from aprof.skill_rl.transition_dataset import build_transition_dataset


def episode(case_id: str) -> Episode:
    skill_id = "tiling.increase_tile_length"
    return Episode(
        case_id=case_id,
        op_name=case_id,
        scenario_id="tile-small|elementwise|910B",
        baseline_kind="strong",
        source="test",
        original_median_us=10.0,
        final_median_us=5.0,
        combined_speedup=2.0,
        workload=WorkloadModel(
            total_elements=2048,
            workload_class="small",
            operator_family="elementwise",
        ),
        diagnosis_type="true_bottleneck",
        measurement=Measurement(
            warm_up=10,
            repeat=5,
            samples_us=[5.0] * 5,
            median_us=5.0,
            cv=0.0,
        ),
        rounds=[
            Round(
                round_index=1,
                label="restore",
                selected=Candidate(
                    id="candidate",
                    strategy_id=skill_id,
                    code_changes=["increase tile length"],
                    median_us=5.0,
                    samples_us=[5.0] * 5,
                    cv=0.0,
                    accepted=True,
                    correctness_checked=2048,
                ),
                measurement=Measurement(
                    warm_up=10,
                    repeat=5,
                    samples_us=[5.0] * 5,
                    median_us=5.0,
                    cv=0.0,
                ),
            )
        ],
        actionable_strategy_ids=[skill_id],
        metadata={
            "correctness": {"checked": 2048, "bad": 0},
            "problem_id": "tile_length_too_small",
            "hardware": "910B",
            "frozen_outcome": 0.4,
            "edited_outcome": 0.8,
        },
    )


class TestSageMemoryR1(unittest.TestCase):
    def test_four_memory_operations_and_budget_rollback(self):
        lib = SkillLibrary(version_label="test")
        add = SkillEdit(
            op="ADD",
            skill_id="tiling.x",
            payload={
                "family": "tiling",
                "actionable_edits": [{"adjust": "tile_length"}],
                "expected_metric_delta": {"direction": "decrease"},
            },
        )
        self.assertEqual(len(lib.apply_edits([add], library_budget=1)), 1)
        self.assertTrue(lib.skills["tiling.x"].is_actionable())
        lib.apply_edits([SkillEdit(op="NOOP", skill_id="", rationale="nothing")])
        lib.apply_edits([SkillEdit(op="DELETE", skill_id="tiling.x")])
        self.assertTrue(lib.skills["tiling.x"].tombstone)

        with self.assertRaises(ValueError):
            lib.apply_edits(
                [
                    SkillEdit(
                        op="ADD",
                        skill_id="tiling.y",
                        payload={
                            "family": "tiling",
                            "actionable_edits": [{"adjust": "tile_length"}],
                            "expected_metric_delta": {"direction": "decrease"},
                        },
                    ),
                    SkillEdit(
                        op="ADD",
                        skill_id="tiling.z",
                        payload={
                            "family": "tiling",
                            "actionable_edits": [{"adjust": "tile_length"}],
                            "expected_metric_delta": {"direction": "decrease"},
                        },
                    ),
                ],
                library_budget=1,
            )
        self.assertNotIn("tiling.y", lib.skills)

    def test_managed_rollout_reuses_generated_skill(self):
        trace = run_managed_rollout(
            [episode("fast_gelu"), episode("gelu_mul")],
            manager_policy=RulePolicy(),
            config=SkillRlConfig(chain_length=2, retrieval_min_score=0.1),
        )
        self.assertEqual(len(trace.steps), 2)
        self.assertIn("tiling.increase_tile_length", trace.steps[0].generated_skill_ids)
        self.assertIn("tiling.increase_tile_length", trace.steps[1].retrieved_skill_ids)
        self.assertGreater(trace.steps[1].reuse_reward, 0.0)

    def test_task_chains_do_not_pair_same_operator(self):
        first = episode("fast_gelu")
        variant = episode("fast_gelu")
        variant.case_id = "fast_gelu_variant"
        second = episode("gelu_mul")
        chains = build_task_chains([first, variant, second], chain_length=2)
        self.assertEqual(len(chains), 1)
        self.assertNotEqual(chains[0][0].op_name, chains[0][1].op_name)

    def test_frozen_policy_does_not_grow_bank(self):
        trace = run_managed_rollout(
            [episode("fast_gelu")],
            manager_policy=FrozenPolicy(),
        )
        self.assertFalse(trace.final_skills)

    def test_group_split_has_no_leakage(self):
        rows = [
            {"case_id": "a1", "op": "a", "problem_family": "tile", "shape_family": "small"},
            {"case_id": "a2", "op": "a", "problem_family": "tile", "shape_family": "small"},
            {"case_id": "b1", "op": "b", "problem_family": "tile", "shape_family": "small"},
            {"case_id": "c1", "op": "c", "problem_family": "block", "shape_family": "large"},
        ]
        split = group_stratified_split(rows)
        assert_no_group_leakage(rows, split)
        buckets = split.to_dict()
        self.assertEqual(
            len([bucket for bucket, ids in buckets.items() if "a1" in ids or "a2" in ids]),
            1,
        )

    def test_registered_applicators_patch_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "op" / "operators" / "op_0001"
            dst = root / "op" / "operators" / "op_9001"
            (src / "op_host").mkdir(parents=True)
            (src / "scripts").mkdir()
            (src / "case_metadata.json").write_text(
                json.dumps({"case_id": "op_0001", "blockdim": 1, "tile_num_mul": 1}),
                encoding="utf-8",
            )
            (src / "op_host" / "main.asc").write_text(
                "constexpr uint32_t kBlockDim = 1U;\n"
                "constexpr uint32_t kTileNumMul = 1U;\n",
                encoding="utf-8",
            )
            skill = Skill(
                id="tiling.combo",
                family="tiling",
                actionable_edits=[
                    {"adjust": "blockdim"},
                    {"adjust": "tile_num"},
                ],
                expected_metric_delta={"direction": "decrease"},
            )
            report = materialize_optimized_case(
                src,
                dst,
                skill=skill,
                parameters={"blockdim": 8, "tile_num": 2},
            )
            self.assertEqual(len(report["applied"]), 2)
            text = (dst / "op_host" / "main.asc").read_text(encoding="utf-8")
            self.assertIn("kBlockDim = 8U", text)
            self.assertIn("kTileNumMul = 2U", text)

    def test_group_relative_advantages(self):
        values = group_relative_advantages([0.0, 1.0, 2.0])
        self.assertAlmostEqual(sum(values), 0.0)
        self.assertGreater(values[-1], values[0])

    def test_group_relative_round_exports_verl(self):
        def sampler(_prompt, _group_size):
            return [
                {"op": "NOOP", "candidate_id": "n"},
                {
                    "op": "ADD",
                    "skill_id": "tiling.sampled",
                    "candidate_id": "a",
                    "payload": {
                        "family": "tiling",
                        "actionable_edits": [{"adjust": "tile_length"}],
                        "expected_metric_delta": {"direction": "decrease"},
                    },
                },
            ]

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "verl.jsonl"
            report = run_group_relative_round(
                [episode("fast_gelu")],
                policy=SampledPolicy(sampler),
                base_library=SkillLibrary(version_label="empty"),
                verl_output=path,
            )
            self.assertEqual(len(report["groups"]), 1)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_transition_reports_share_schema(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "op": "fast_gelu",
                                "problem_id": "tile_small",
                                "before_median_us": 10,
                                "after_median_us": 5,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rows = build_transition_dataset([path])
            self.assertEqual(rows[0]["op"], "fast_gelu")
            self.assertEqual(rows[0]["outcome"]["after_median_us"], 5)


if __name__ == "__main__":
    unittest.main()

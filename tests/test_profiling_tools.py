from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "skills/aprof/profiling/scripts"


def load_tool(name: str):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compress_msprof = load_tool("compress_msprof")
run_profile_stages = load_tool("run_profile_stages")
paired_timing = load_tool("paired_timing")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ProfilingToolsTest(unittest.TestCase):
    def test_compressor_reads_timestamped_standard_msprof_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_csv(
                root / "op_summary_20260811084940.csv",
                [{
                    "Op Name": "apply_adam_w_kernel",
                    "Task Duration(us)": 38.919,
                    "Block Num": 40,
                    "aiv_vec_ratio": 0.21,
                    "aiv_scalar_ratio": 0.44,
                    "aiv_mte2_ratio": 0.35,
                }],
            )
            args = compress_msprof.build_parser().parse_args([
                "--input", str(root),
                "--output", str(root / "symptoms.json"),
                "--op-name", "apply_adam_w_kernel",
                "--available-cores", "40",
            ])
            result = compress_msprof.compress(args)
            self.assertEqual(38.919, result["features"]["task_duration_us"])
            self.assertEqual(1.0, result["features"]["core_coverage"])
            self.assertEqual(0.44, result["features"]["pipe_ratios"]["aiv_scalar"])
            self.assertEqual("aiv_scalar", result["features"]["dominant_pipe"])
            self.assertTrue(result["predicate_states"]["predicate.profile.scalar_hot"])
            self.assertIn(
                "resource_conflict_ratio_not_found",
                result["unresolved_reasons"]["predicate.profile.ub_conflict_high"],
            )

    def test_compressor_preserves_repeat_samples_and_uses_median(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            durations = [37.839, 37.799, 37.419, 37.18, 38.419]
            for index, duration in enumerate(durations):
                write_csv(
                    root / f"repeat_{index}" / f"op_summary_2026081108494{index}.csv",
                    [{
                        "Op Name": "apply_adam_w_kernel",
                        "Task Duration(us)": duration,
                        "Block Num": 40,
                        "aiv_time(us)": duration,
                        "aiv_vec_ratio": 0.40,
                        "aiv_scalar_ratio": 0.20,
                    }],
                )
            args = compress_msprof.build_parser().parse_args([
                "--input", str(root),
                "--output", str(root / "symptoms.json"),
                "--op-name", "apply_adam_w_kernel",
                "--available-cores", "40",
            ])
            result = compress_msprof.compress(args)
            self.assertEqual(sorted(durations), sorted(result["features"]["task_duration_samples_us"]))
            self.assertEqual(37.799, result["features"]["task_duration_us"])
            self.assertEqual(5, result["features"]["task_duration_statistics"]["count"])
            self.assertEqual("median_us", result["features"]["task_duration_statistics"]["selected"])
            self.assertAlmostEqual(
                0.012505615605645698,
                result["features"]["task_duration_statistics"]["cv"],
            )
            self.assertEqual(
                "stable_full_profile_metric",
                result["features"]["task_duration_measurement_status"],
            )
            self.assertFalse(result["features"]["production_gain_eligible"])
            self.assertEqual([], result["features"]["per_core_time"])
            self.assertEqual(
                "unknown",
                result["predicate_states"]["predicate.profile.per_core_time_imbalanced"],
            )

    def test_compressor_preserves_raw_features_unknowns_and_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_csv(
                root / "op_summary_PipeUtilization.csv",
                [{
                    "Op Name": "demo_kernel",
                    "Task Duration(us)": 20.0,
                    "Block Num": 8,
                    "aiv_time(us)": 18.0,
                    "aiv_vec_ratio": 0.10,
                    "aiv_scalar_ratio": 0.35,
                    "aiv_mte2_ratio": 0.55,
                    "aiv_mte3_ratio": 0.20,
                }],
            )
            write_csv(
                root / "op_summary_Memory.csv",
                [{
                    "Op Name": "demo_kernel",
                    "GM_to_UB_datas(KB)": 64,
                    "aiv_mte2_instructions": 16,
                    "GM_to_UB_bw_usage_rate(%)": 30,
                    "read_main_memory_datas(KB)": 128,
                    "write_main_memory_datas(KB)": 128,
                }],
            )
            write_csv(
                root / "op_summary_ResourceConflictRatio.csv",
                [{"Op Name": "demo_kernel", "aiv_vec_total_cflt_ratio": 0.10}],
            )
            write_csv(
                root / "per_core_cycles.csv",
                [{"coreid": 0, "task_cycles": 100}, {"coreid": 1, "task_cycles": 200}],
            )
            parser = compress_msprof.build_parser()
            args = parser.parse_args([
                "--input", str(root),
                "--output", str(root / "symptoms.json"),
                "--op-name", "demo_kernel",
                "--available-cores", "40",
                "--theoretical-gm-bytes", str(128 * 1024),
            ])
            result = compress_msprof.compress(args)
            self.assertEqual("demo_kernel", result["operator"])
            self.assertEqual(8, result["features"]["block_dim"])
            self.assertEqual(0.2, result["features"]["core_coverage"])
            self.assertEqual(0.5, result["features"]["per_core_imbalance"])
            self.assertTrue(result["predicate_states"]["predicate.profile.scalar_hot"])
            self.assertTrue(result["predicate_states"]["predicate.profile.mte_setup_dominated"])
            self.assertTrue(result["predicate_states"]["predicate.profile.ub_conflict_high"])
            self.assertTrue(result["predicate_states"]["predicate.profile.gm_traffic_amplified"])
            self.assertEqual("unknown", result["predicate_states"]["predicate.profile.overlap_low"])
            scalar = next(
                item for item in result["symptoms"]
                if item["id"] == "symptom.profile.scalar_share_high"
            )
            self.assertGreaterEqual(len(scalar["candidate_problem_ids"]), 2)
            self.assertTrue(all(item["sha256"].startswith("sha256:") for item in result["artifacts"]))

    def test_stage_runner_dry_run_and_stop_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "schema_version": "1.0.0",
                "op_dir": str(root),
                "output_dir": ".aprof/dry-run",
                "stages": [
                    {
                        "name": "build",
                        "commands": [[sys.executable, "-c", "raise SystemExit(3)"]],
                        "timeout_seconds": 10,
                        "required": True,
                    },
                    {
                        "name": "correctness",
                        "commands": [[sys.executable, "-c", "raise SystemExit(0)"]],
                        "timeout_seconds": 10,
                        "required": True,
                    },
                ],
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            loaded = run_profile_stages._load_config(config_path)
            planned = run_profile_stages.execute(loaded, dry_run=True)
            self.assertEqual("planned", planned["terminal_status"])
            config["output_dir"] = ".aprof/actual"
            failed = run_profile_stages.execute(config)
            self.assertEqual("build_failed", failed["terminal_status"])
            self.assertEqual(1, len(failed["stages"]))
            self.assertTrue(Path(failed["stages"][0]["commands"][0]["log"]).is_file())

    def test_stage_runner_continues_after_optional_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "schema_version": "1.0.0",
                "op_dir": str(root),
                "output_dir": ".aprof/optional",
                "stages": [
                    {
                        "name": "preflight",
                        "commands": [[sys.executable, "-c", "raise SystemExit(3)"]],
                        "timeout_seconds": 10,
                        "required": False,
                    },
                    {
                        "name": "build",
                        "commands": [[sys.executable, "-c", "raise SystemExit(0)"]],
                        "timeout_seconds": 10,
                        "required": True,
                    },
                ],
            }
            result = run_profile_stages.execute(config)
            self.assertEqual("passed", result["terminal_status"])
            self.assertEqual(["preflight"], result["optional_failures"])
            self.assertEqual(["failed", "passed"], [stage["status"] for stage in result["stages"]])

    def test_stage_runner_rejects_optional_correctness_before_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "schema_version": "1.0.0",
                "op_dir": str(root),
                "output_dir": ".aprof/invalid",
                "stages": [
                    {
                        "name": "build",
                        "commands": [[sys.executable, "-c", "pass"]],
                        "required": True,
                    },
                    {
                        "name": "correctness",
                        "commands": [[sys.executable, "-c", "pass"]],
                        "required": False,
                    },
                    {
                        "name": "profile",
                        "commands": [[sys.executable, "-c", "pass"]],
                        "required": True,
                    },
                ],
            }
            path = root / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "correctness stage cannot be optional"):
                run_profile_stages._load_config(path)

    def test_paired_timer_marks_small_runs_exploratory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, "-c", "pass"]
            config = {
                "schema_version": "1.0.0",
                "baseline": {"cwd": directory, "command": command},
                "candidate": {"cwd": directory, "command": command},
                "pairs": 2,
                "warmup": 0,
                "timeout_seconds": 10,
            }
            result = paired_timing.collect(config)
            self.assertEqual(["AB", "BA"], result["order"])
            self.assertEqual(2, len(result["baseline_samples_ns"]))
            self.assertFalse(result["production_minimum_met"])
            self.assertEqual("draft_only; aprofctl candidate gate recomputes stability and LCB", result["authority"])


if __name__ == "__main__":
    unittest.main()

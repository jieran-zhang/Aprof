#!/usr/bin/env python3
"""回放两份统一测量证据并展示比较；正式结论由 runtime 收尾入口给出。"""

import argparse
import json
from pathlib import Path
import sys

RELEASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RELEASE / "runtime/src"))

PROTOCOL = "single_role_l2_clean_task_v1"
METRIC = "msprof.Task_Duration.complete_call"
COMMON = ("workload_ref", "input_ref", "hardware_ref", "toolchain_ref", "collector_ref")


def compare(baseline_path, candidate_path):
    from aprof_runtime.unified_timing import replay_capture
    a, b = replay_capture(baseline_path), replay_capture(candidate_path)
    baseline, candidate = a["capture"], b["capture"]
    for key in ("operator", "case_id", "cache_policy", "metric", "declaration_ref"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"A/B {key} differs")
    for key in COMMON:
        if baseline["identity"][key] != candidate["identity"][key]:
            raise ValueError(f"A/B {key} differs")
    return {
        "protocol": PROTOCOL, "metric": METRIC, "operator": baseline["operator"],
        "case_id": baseline["case_id"], "baseline_manifest_ref": a["capture_ref"],
        "candidate_manifest_ref": b["capture_ref"], "baseline_median_us": a["median_us"],
        "candidate_median_us": b["median_us"],
        "apparent_speedup": a["median_us"] / b["median_us"],
        "baseline_within_process_cv": a["within_process_cv"],
        "candidate_within_process_cv": b["within_process_cv"],
        "formal_admission": "not_evaluated",
        "reason": "此命令只展示单 case 原始回放结果；正式收尾另行检查完整 case、正确性与复用策略",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="本次比较的父实现测量，可复用上一轮 B")
    parser.add_argument("--candidate", type=Path, required=True, help="本次候选实现测量")
    parser.add_argument("--output", type=Path, required=True, help="尚不存在的比较结果 JSON")
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

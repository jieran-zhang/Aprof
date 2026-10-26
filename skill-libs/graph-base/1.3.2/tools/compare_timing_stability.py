#!/usr/bin/env python3
"""既有 Task CSV 的离线敏感性分析；不执行 collector、oracle 或 NPU。"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/src"))
from aprof_runtime.median_timing import compare_windows, sample_statistics
from aprof_runtime.task_statistics import bounded_statistics
from aprof_runtime.unified_task_samples import complete_calls


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def extract(path):
    docs, captures, rounds = {}, {}, []

    def document(p, expected=None):
        p = Path(p).resolve(); raw = p.read_bytes(); key = digest(raw)
        if expected is not None and key != expected:
            raise ValueError(f"来源 hash 不符：{p}")
        docs.setdefault(key, {"original_path": str(p), "sha256": key, "text": raw.decode("utf-8")})
        return key

    def capture(p, expected=None):
        key = document(p, expected)
        if key in captures:
            return key
        cap = json.loads(docs[key]["text"])
        ref = cap["artifacts"]["task_csv"]
        csv = (Path(p).parent / ref["path"]).resolve()
        csv_key = document(csv, ref["sha256"])
        decl = cap["artifacts"]["declaration"]
        document(Path(p).parent / decl["path"], decl["sha256"])
        captures[key] = {"capture_document": key, "csv_document": csv_key}
        return key

    input_key = document(path)
    original = json.loads(docs[input_key]["text"])
    for item in original["rounds"]:
        result_key = document(item["result_vs_parent_ref"])
        result = json.loads(docs[result_key]["text"])
        request_path = Path(result["request"]["path"])
        request_key = document(request_path, result["request"]["sha256"])
        request = json.loads(docs[request_key]["text"])
        selection_path = Path(item["authority_selection_ref"])
        selection_key = document(selection_path)
        parent = selection_path.parent
        window_map, selected, first = {}, {}, {}
        for role, label in (("baseline", "A"), ("candidate", "B")):
            by_case = {}
            for collection_path in sorted(parent.glob(f"*-{label}-collection.json")):
                collection_key = document(collection_path)
                collection = json.loads(docs[collection_key]["text"])
                for ref in collection["captures"]:
                    key = capture(collection_path.parent / ref["path"], ref["sha256"])
                    cap = json.loads(docs[key]["text"])
                    by_case.setdefault(cap["case_id"], set()).add(key)
            first_path = parent / f"first-{label}-collection.json"
            first_collection = json.loads(docs[document(first_path)]["text"])
            first[role] = {}
            for ref in first_collection["captures"]:
                key = capture(first_path.parent / ref["path"], ref["sha256"])
                first[role][str(json.loads(docs[key]["text"])["case_id"])] = key
            selected[role] = {}
            for ref in request[role + "_captures"]:
                key = capture(request_path.parent / ref["path"], ref["sha256"])
                case = json.loads(docs[key]["text"])["case_id"]
                selected[role][str(case)] = key
                by_case.setdefault(case, set()).add(key)
            window_map[role] = {str(case): sorted(keys, key=lambda k: json.loads(docs[k]["text"])["captured_at"])
                                for case, keys in by_case.items()}
        rounds.append({"operator": item["operator"], "round": item["round"],
            "candidate": item["candidate"], "actual_parent": item["actual_parent"],
            "historical_verdict": result["verdict"], "historical_speedup": result["speedup"],
            "historical_max_case_regression": result["max_case_regression"],
            "historical_formal_chain": item["full_formal_chain_status"],
            "historical_HAP_qualified": item["HAP_qualified"], "historical_HAP_valid": item["HAP_valid"],
            "result_document": result_key, "request_document": request_key,
            "selection_document": selection_key, "selected": selected, "first": first, "windows": window_map})
    return {"schema": "aprof.offline-timing-evidence/v1", "input_document": input_key,
            "documents": docs, "captures": captures, "rounds": rounds,
            "scope": "仅核对归档/hash/Task计数与统计；未重新认证正确性、硬件或完整交接"}


def analyze(frozen):
    docs, captures = frozen["documents"], frozen["captures"]
    for key, value in docs.items():
        if digest(value["text"].encode("utf-8")) != key or value["sha256"] != key:
            raise ValueError("冻结文本 hash 不符")
    parsed = {}
    with tempfile.TemporaryDirectory(prefix="aprof-offline-task-csv-") as temp:
        for key, record in captures.items():
            cap = json.loads(docs[record["capture_document"]]["text"])
            csv_record = docs[record["csv_document"]]
            if cap["artifacts"]["task_csv"]["sha256"] != csv_record["sha256"]:
                raise ValueError("capture 与原始CSV绑定不符")
            csv = Path(temp) / "tasks.csv"; csv.write_bytes(csv_record["text"].encode("utf-8"))
            values = complete_calls(csv if cap["task_table"] == "kernel_details" else None,
                                   csv if cap["task_table"] == "op_summary" else None,
                                   cap["kernel_names"], eviction_type=cap["cache_policy"]["eviction_kernel"])["values_us"]
            parsed[key] = {"capture": cap, "values": values}
    variants = [(2, .05), (3, .10), (4, .10), (4, .15)]
    rows, sensitivity, invalid_drift = [], {}, {}
    for old in frozen["rounds"]:
        cases = sorted(old["selected"]["baseline"], key=int)
        if set(cases) != set(old["selected"]["candidate"]) or len(cases) != 20:
            raise ValueError("原始比较不包含双方完整20 case")
        operator = old["operator"]
        for limit, cv in variants:
            stats = {role: [sample_statistics(parsed[old["selected"][role][case]]["values"], max_excluded=limit, max_cv=cv)
                            for case in cases] for role in ("baseline", "candidate")}
            counts = {r: sum(s["quality_status"] != "within_window_acceptable" for s in samples) for r, samples in stats.items()}
            bucket = sensitivity.setdefault(operator, {}).setdefault(f"{limit}/20_cv{cv:g}", {"baseline_invalid": 0, "candidate_invalid": 0, "both20_within_rule_rounds": 0})
            bucket["baseline_invalid"] += counts["baseline"]; bucket["candidate_invalid"] += counts["candidate"]
            bucket["both20_within_rule_rounds"] += int(not any(counts.values()))
        final_cases, all_cases, cells, incomparable = [], [], [], []
        for case in cases:
            final_case = {"case_id": int(case)}; all_case = {"case_id": int(case)}
            for role in ("baseline", "candidate"):
                key = old["selected"][role][case]; final = parsed[key]
                first_key = old["first"][role][case]; first = parsed[first_key]
                original = bounded_statistics(final["values"]); new = sample_statistics(final["values"])
                all_keys = old["windows"][role][case]
                identity = first["capture"]["identity"]
                comparable = all(parsed[k]["capture"]["identity"] == identity
                                 and parsed[k]["capture"]["cache_policy"] == first["capture"]["cache_policy"]
                                 and parsed[k]["capture"]["kernel_names"] == first["capture"]["kernel_names"] for k in all_keys)
                if comparable and (all_keys[0] != first_key or all_keys[-1] != key):
                    raise ValueError("历史最终窗口并非登记的最后窗口，不能静默择优")
                if not comparable:
                    incomparable.append({"case_id": int(case), "role": role})
                old_invalid = original["exclusion_limit_exceeded"] or original["cv"] > .05
                drift = abs(statistics.median(final["values"]) - statistics.median(first["values"])) / statistics.median(first["values"]) if comparable and key != first_key else None
                if old_invalid and drift is not None:
                    invalid_drift.setdefault(operator, {}).setdefault(role, []).append(drift)
                cells.append({"case_id": int(case), "role": role, "selected_capture": key,
                    "first_capture": first_key, "all_capture_refs": all_keys, "comparable": comparable,
                    "raw_drift_first_to_final": drift, "old_within_window_valid": not old_invalid,
                    "new_within_window_valid": new["quality_status"] == "within_window_acceptable",
                    "old_statistics": original, "new_statistics": new})
                final_case[role] = [final["values"]]
                all_case[role] = [parsed[k]["values"] for k in all_keys] if comparable else [final["values"]]
            final_cases.append(final_case); all_cases.append(all_case)
        final_review = compare_windows(final_cases); all_review = compare_windows(all_cases)
        if incomparable:
            all_review.update(verdict="inconclusive", timing_quality="uncertain")
            all_review["quality_reasons"].append("存在不可比较身份；不能由数值相似推断跨窗口稳定")
        rows.append({**{k: v for k, v in old.items() if k not in ("windows", "selected", "first")},
            "cells": cells, "final_window_counterfactual": final_review,
            "all_windows_counterfactual": all_review, "incomparable_windows": incomparable,
            "new_protocol_admitted": False})
    drift_summary = {op: {r: {"compared": len(v), "at_most_3pct": sum(x <= .03 for x in v),
                         "at_most_5pct": sum(x <= .05 for x in v), "median_abs_drift": statistics.median(v)}
                         for r, v in roles.items()} for op, roles in invalid_drift.items()}
    return {"schema": "aprof.offline-timing-comparison/v1", "hardware_executed": False,
            "historical_results_modified": False, "historical_candidates_readmitted": False,
            "sensitivity": sensitivity, "old_invalid_group_drift": drift_summary, "rounds": rows,
            "limitations": ["这是同一既有数据集的阈值敏感性与条件分析，不是新协议独立验证。",
                            "旧声明未选择新协议，旧正确性、工程、HAP和正式交接结论保持原义。"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--round-results", type=Path)
    inputs.add_argument("--frozen", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.frozen:
        raw = gzip.decompress(args.frozen.read_bytes()); frozen = json.loads(raw)
    else:
        frozen = extract(args.round_results)
        raw = json.dumps(frozen, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    archive = args.output / "raw-evidence.json.gz"
    archive.write_bytes(gzip.compress(raw, mtime=0))
    result = analyze(frozen)
    write(args.output / "comparison.json", result)
    write(args.output / "evidence-identity.json", {"archive": archive.name, "sha256": digest(archive.read_bytes()),
        "decoded_sha256": digest(raw), "captures": len(frozen["captures"]), "documents": len(frozen["documents"])})
    print(json.dumps({"rounds": len(result["rounds"]), "sensitivity": result["sensitivity"],
                      "old_invalid_group_drift": result["old_invalid_group_drift"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

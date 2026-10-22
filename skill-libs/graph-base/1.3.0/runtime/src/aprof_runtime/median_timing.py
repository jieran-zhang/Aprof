"""显式预声明的中位数探索协议；采集口径仍为 5/20 完整 Task 调用。"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import statistics

from .errors import ContractError
from .jsonio import content_hash
from .task_statistics import NORMAL_MAD_SCALE

STABILITY_PROTOCOL = "median_stability_exploration_v2"
STABILITY_POLICY = "bounded_outlier_v2"
MAX_EXCLUDED = 4
MAX_CV = .10


def sample_statistics(values, *, max_excluded=MAX_EXCLUDED, max_cv=MAX_CV):
    """只从完整原始值检测一次；超限不剔除，不把波动解释成收益失败。"""
    if len(values) != 20 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in values):
        raise ContractError("中位数协议需要完整的 20 个正有限 Task 时长")
    values = list(values)
    center = statistics.median(values)
    mad = statistics.median(abs(x - center) for x in values)
    threshold = max(.10 * center, 3 * NORMAL_MAD_SCALE * mad)
    outliers = [i for i, x in enumerate(values, 1) if abs(x - center) > threshold]
    exceeded = len(outliers) > max_excluded
    excluded = [] if exceeded else outliers
    retained = [x for i, x in enumerate(values, 1) if i not in excluded]
    median = statistics.median(retained)
    cv = statistics.stdev(retained) / statistics.fmean(retained)
    return {
        "policy": STABILITY_POLICY if (max_excluded, max_cv) == (MAX_EXCLUDED, MAX_CV) else "offline_threshold_sensitivity",
        "max_excluded": max_excluded, "max_cv": max_cv, "raw_values_us": values,
        "raw_median_us": center, "median_us": median,
        "raw_cv": statistics.stdev(values) / statistics.fmean(values), "cv": cv,
        "mad_us": mad, "outlier_threshold_us": threshold,
        "outlier_indices": outliers, "outlier_count": len(outliers),
        "excluded_indices": excluded, "retained_count": len(retained),
        "exclusion_limit_exceeded": exceeded,
        "median_shift_fraction": abs(median - center) / center,
        "quality_status": "variable_review_required" if exceeded or cv > max_cv else "within_window_acceptable",
    }


def window_stability(windows):
    """windows 按时间包含首测和全部已执行复验；使用原始中位数。"""
    if not windows:
        raise ContractError("缺少首测窗口")
    medians = [w["raw_median_us"] for w in windows]
    drift = [abs(m - medians[0]) / medians[0] for m in medians[1:]]
    maximum = max(drift) if drift else None
    status = ("not_measured" if maximum is None else "stable_evidence" if maximum <= .03 + 1e-12
              else "caution" if maximum <= .05 + 1e-12 else "uncertain")
    return {"status": status, "raw_medians_us": medians, "drift_fractions_from_first": drift,
            "max_drift_fraction": maximum, "threshold_scope": "exploration_trial_only"}


def engineering_assessment(baseline, candidate):
    ratios = [a / b for a, b in zip(baseline, candidate, strict=True)]
    speedup = math.exp(statistics.fmean(math.log(x) for x in ratios))
    worst = max(b / a - 1 for a, b in zip(baseline, candidate, strict=True))
    reasons = ([] if speedup >= 1.03 else ["等权几何中位数比未达到 1.03"]) + ([] if worst <= .03 else ["至少一个 case 回归超过 3%"])
    return {"speedup": speedup, "max_case_regression": worst, "reasons": reasons,
            "verdict": "accepted" if not reasons else "rejected"}


def compare_windows(cases):
    """只评估统计/收益：不证明原始证据、正确性、HAP或完整交接。"""
    reasons, reviews, rows = [], [], []
    for case in cases:
        sides = {}
        for role in ("baseline", "candidate"):
            stats = [sample_statistics(v) for v in case[role]]
            stability = window_stability(stats)
            variable = any(s["quality_status"] != "within_window_acceptable" for s in stats)
            if variable:
                reviews.append(f"{role}/case {case['case_id']} 波动较大／需复核；不能仅凭稳定中位数自动通过")
            if stability["status"] == "uncertain":
                reasons.append(f"{role}/case {case['case_id']} 原始中位数跨窗口漂移超过 5%")
            sides[role] = {"windows": stats, "median_stability": stability,
                           "further_benefit_review_possible": variable and stability["status"] == "stable_evidence"}
        a, b = (sides[r]["windows"] for r in ("baseline", "candidate"))
        # 最后已执行窗口固定作点估计；所有先前窗口仍参加漂移/敏感性分析。
        rows.append({"case_id": case["case_id"], **sides,
                     "speedup": a[-1]["median_us"] / b[-1]["median_us"],
                     "regression": b[-1]["median_us"] / a[-1]["median_us"] - 1,
                     "raw_speedup": a[-1]["raw_median_us"] / b[-1]["raw_median_us"]})
    a = [r["baseline"]["windows"][-1]["median_us"] for r in rows]
    b = [r["candidate"]["windows"][-1]["median_us"] for r in rows]
    raw_a = [r["baseline"]["windows"][-1]["raw_median_us"] for r in rows]
    raw_b = [r["candidate"]["windows"][-1]["raw_median_us"] for r in rows]
    processed, raw = engineering_assessment(a, b), engineering_assessment(raw_a, raw_b)
    changed = raw["verdict"] != processed["verdict"] or any(
        (rb / ra - 1 > .03) != (pb / pa - 1 > .03)
        for ra, rb, pa, pb in zip(raw_a, raw_b, a, b, strict=True))
    if changed:
        reviews.append("剔除改变工程门槛结论；需解释原始与处理后差异")
    # 这是观测窗口范围的敏感性，不是置信区间，也不虚构配对样本。
    lower_a, upper_a, lower_b, upper_b = [], [], [], []
    for row in rows:
        vals = {r: [s[k] for s in row[r]["windows"] for k in ("raw_median_us", "median_us")]
                for r in ("baseline", "candidate")}
        lower_a.append(min(vals["baseline"])); upper_a.append(max(vals["baseline"]))
        lower_b.append(min(vals["candidate"])); upper_b.append(max(vals["candidate"]))
    conservative = engineering_assessment(lower_a, upper_b)
    optimistic = engineering_assessment(upper_a, lower_b)
    if conservative["verdict"] != optimistic["verdict"]:
        reviews.append("已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化")
    if (processed["verdict"] == "accepted" and processed["speedup"] <= 1.03 + 1e-12
            and any(row[r]["median_stability"]["status"] != "stable_evidence"
                    for row in rows for r in ("baseline", "candidate"))):
        reviews.append("约 3% 的门槛附近收益缺少双方跨窗口稳定依据")
    quality = "uncertain" if reasons else "review_required" if reviews else "within_trial_rule"
    return {"cases": rows, "engineering_assessment": processed,
            "raw_engineering_assessment": raw, "exclusion_changes_conclusion": changed,
            "observed_window_sensitivity": {"conservative": conservative, "optimistic": optimistic,
                                            "is_confidence_interval": False},
            "timing_quality": quality, "quality_reasons": reasons + reviews,
            "verdict": processed["verdict"] if quality == "within_trial_rule" else "inconclusive"}


def validate_schema(root, kind, value):
    """新旧 schema 显式分派；旧 JSON schema 文件保持原字节。"""
    from .knowledge import validate_schema as checked
    suffix = "-v2" if isinstance(value, dict) and value.get("schema_version") == 2 else ""
    return checked(Path(root), f"unified-timing-{kind}{suffix}", value)


def evaluate_request(path, *, evaluated_at=None):
    from . import unified_timing as u
    path = Path(path).resolve()
    req = u.read_json(path)
    required = {"schema_version", "protocol", "operator", "candidate_id", "baseline_source_sha256",
                "candidate_source_sha256", "declaration", "baseline_captures", "candidate_captures",
                "baseline_correctness", "candidate_correctness", "stability_protocol", "replications"}
    u.fields(req, required, "中位数探索请求")
    u.require(req["schema_version"] == 2 and req["protocol"] == u.PROTOCOL
              and req["stability_protocol"] == STABILITY_PROTOCOL
              and isinstance(req["candidate_id"], str) and req["candidate_id"], "探索协议身份无效")
    decl = u.declaration(path.parent, req["declaration"])
    u.require(decl["schema_version"] == 3 and decl["operator"] == req["operator"], "新协议需要测前 v3 声明")
    declared_ref = req["declaration"]["sha256"]
    when = evaluated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    now, verified, roles, integrity_reasons = u.timestamp(when), set(), {}, []
    u.fields(req["replications"], {"baseline", "candidate"}, "全部复验引用")
    for role in ("baseline", "candidate"):
        source = req[role + "_source_sha256"]
        assumed = role == "baseline" and req["baseline_correctness"] is None
        if assumed:
            u.check_baseline_trust(decl, {"source_sha256": source, "binary_sha256": decl["baseline_trust"]["binary_sha256"]})
            correct = None
        else:
            correct = u.replay_correctness(u.reference(path.parent, req[role + "_correctness"]),
                source=source, operator=req["operator"], declaration_ref=declared_ref,
                case_ids=decl["correctness_case_ids"], verified=verified)
        by_case, seen, native_ids = {}, set(), set()
        for is_retest, refs in ((False, req[role + "_captures"]), (True, req["replications"][role])):
            u.require(isinstance(refs, list) and (is_retest or refs), "计时窗口列表无效")
            for ref in refs:
                capture_path = u.reference(path.parent, ref)
                replay = u.replay_capture(capture_path, verified=verified)
                cap = replay["capture"]; case = cap["case_id"]
                native = u.read_json(u.reference(capture_path.parent, cap["artifacts"]["native_receipt"]))
                native_id = native.get("capture_id")
                u.require(isinstance(native_id, str) and native_id and native_id not in native_ids,
                          "复验必须来自独立采集，不能重包装同一 native 窗口")
                native_ids.add(native_id)
                execution = u.read_json(u.reference(capture_path.parent, cap["artifacts"]["execution_receipt"]))
                replay["native_window"] = execution["stages"]["native"]
                u.require(cap["operator"] == req["operator"] and cap["identity"]["source_sha256"] == source
                          and cap["declaration_ref"] == declared_ref, "窗口 source/operator/declaration 不符")
                if assumed:
                    u.check_baseline_trust(decl, cap["identity"])
                else:
                    for k in ("source_sha256", "binary_sha256", "input_ref", "workload_ref"):
                        u.require(cap["identity"][k] == correct["cases"][case][k], f"窗口正确性 {k} 不符")
                    u.require(replay["oracle_signature"] == correct["oracle_signatures"][case], "窗口 oracle/golden 不符")
                u.require(replay["capture_ref"] not in seen, "重复窗口不能作为复验")
                seen.add(replay["capture_ref"])
                if is_retest:
                    u.require(case in by_case, "复验缺少原始首测")
                    previous = by_case[case][-1]["capture"]
                    u.require(cap["identity"] == previous["identity"] and cap["cache_policy"] == previous["cache_policy"]
                              and cap["kernel_names"] == previous["kernel_names"], "复验实现/workload/测量口径改变")
                    u.require(u.timestamp(cap["captured_at"]) > u.timestamp(previous["captured_at"]), "复验必须按时间排列")
                    u.require(u.timestamp(replay["native_window"]["started_at"]) >= u.timestamp(by_case[case][-1]["native_window"]["finished_at"]),
                              "同一实现的复验 native 窗口不能重叠")
                    u.require(len(by_case[case]) <= decl["replication_policy"]["max_retests"], "超过预声明复验次数")
                else:
                    u.require(case not in by_case, "首测 case 重复")
                    by_case[case] = []
                by_case[case].append(replay)
                age = now - u.timestamp(cap["captured_at"])
                u.require(age >= 0, "窗口来自未来")
                if age > decl["reuse_policy"]["max_age_seconds"]:
                    integrity_reasons.append(f"{role}/case {case} 超出预声明复用时限")
        u.require(set(by_case) == set(decl["case_ids"]), "计时 case 覆盖不符")
        roles[role] = by_case
    stats_cases, bindings = [], []
    for case in decl["case_ids"]:
        a, b = (roles[r][case] for r in ("baseline", "candidate"))
        for x in a:
            for y in b:
                for key in ("workload_ref", "input_ref", "hardware_ref", "toolchain_ref", "collector_ref"):
                    u.require(x["capture"]["identity"][key] == y["capture"]["identity"][key], f"A/B {key} 不符")
                u.require(x["capture"]["cache_policy"] == y["capture"]["cache_policy"], "A/B 清L2口径不同")
                if abs(u.timestamp(x["captured_at"]) - u.timestamp(y["captured_at"])) > decl["reuse_policy"]["max_ab_gap_seconds"]:
                    integrity_reasons.append(f"case {case} A/B 窗口间隔超限")
        stats_cases.append({"case_id": case, **{r: [w["values_us"] for w in roles[r][case]] for r in roles}})
        bindings.append({r: [w["capture_ref"] for w in roles[r][case]] for r in roles})
    report = compare_windows(stats_cases)
    for row, bound in zip(report["cases"], bindings, strict=True):
        row["capture_refs"] = bound
        case = row["case_id"]
        for role in ("baseline", "candidate"):
            last = roles[role][case][-1]
            stats = row[role]["windows"][-1]
            row[role + "_capture_ref"] = last["capture_ref"]
            row[role + "_median_us"] = stats["median_us"]
            row[role + "_within_process_cv"] = stats["cv"]
        row["ab_gap_seconds"] = abs(u.timestamp(roles["baseline"][case][-1]["captured_at"])
                                   - u.timestamp(roles["candidate"][case][-1]["captured_at"]))
    if integrity_reasons:
        report.update(verdict="inconclusive", timing_quality="uncertain")
        report["quality_reasons"].extend(integrity_reasons)
    performance = report["engineering_assessment"]
    result = {"schema_version": 2, "kind": "unified_timing_result", "protocol": u.PROTOCOL,
        "stability_protocol": STABILITY_PROTOCOL, "stability_policy": STABILITY_POLICY,
        "metric": u.METRIC, "operator": req["operator"], "candidate_id": req["candidate_id"],
        "request": {"path": str(path), "sha256": u.file_hash(path)}, "evaluated_at": when,
        **report, "speedup": performance["speedup"], "max_case_regression": performance["max_case_regression"],
        "reasons": report["quality_reasons"] + performance["reasons"], "authority": "performance_engineering_only",
        "baseline_correctness_status": "assumed" if req["baseline_correctness"] is None else "verified",
        "thresholds": {"min_speedup": 1.03, "max_case_regression": .03, "max_within_process_cv": MAX_CV,
                       "max_excluded": MAX_EXCLUDED, "stable_drift": .03, "caution_drift": .05},
        # 不因所有单窗口都缺漂移数据就建议全量再采，也不反复采到通过。
        "replication_recommended": decl["replication_policy"]["max_retests"] > 0 and any(
            len(r[s]["windows"]) == 1 and (r[s]["windows"][0]["quality_status"] != "within_window_acceptable"
                or math.isclose(performance["speedup"], 1.03)
                or math.isclose(performance["max_case_regression"], .03))
            for r in report["cases"] for s in ("baseline", "candidate")),
        "uncertainty": "试用阈值；轮内质量、观测窗口敏感性与工程收益分开；不证明置信度、HAP或Action—P/O准入"}
    return {**result, "decision_hash": content_hash(result)}

"""统一 L2-clean Task 计时：原始证据回放与独立的性能工程验收。

20 轮只表示单进程内重复；本模块不构造配对样本、置信下界或生产 episode。
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import statistics
import struct

from .errors import ContractError
from .jsonio import content_hash
from .unified_task_samples import complete_calls
from .task_statistics import BOUNDED_OUTLIER_POLICY, bounded_statistics

PROTOCOL = "single_role_l2_clean_task_v1"
CORRECTNESS_PROTOCOL = "single_role_correctness_case_v1"
METRIC = "msprof.Task_Duration.complete_call"
IDENTITY = {"source_sha256", "binary_sha256", "workload_ref", "input_ref", "hardware_ref", "toolchain_ref", "collector_ref"}
CAPTURE_FIELDS = {"schema_version", "protocol", "operator", "case_id", "captured_at", "identity", "declaration_ref", "cache_policy", "metric", "warmup_calls", "formal_calls", "kernel_names", "task_table", "artifacts"}
ARTIFACTS = {"source", "binary", "workload", "input", "hardware", "toolchain", "collector", "task_csv", "output", "native_receipt", "oracle_receipt", "execution_receipt", "declaration"}
FORMATS = {"float16": "e", "float32": "f", "float64": "d", "int8": "b", "uint8": "B", "int16": "h", "uint16": "H", "int32": "i", "uint32": "I", "int64": "q", "uint64": "Q", "bool": "?"}


def require(condition, message):
    if not condition:
        raise ContractError(message)


def fields(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names), f"{label} 字段不匹配")
    return value


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f"JSON 无效：{path}") from exc


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "时间戳必须包含时区")
        return parsed.timestamp()
    except (AttributeError, ValueError) as exc:
        raise ContractError("时间戳无效") from exc


def positive(value, label):
    require(type(value) in (float, int) and math.isfinite(value) and value > 0, f"{label} 必须是正有限数")
    return value


def reference(root, ref):
    fields(ref, {"path", "sha256"}, "文件引用")
    require(isinstance(ref["path"], str) and ref["path"] and not Path(ref["path"]).is_absolute(), "文件引用必须为相对路径")
    path = (Path(root) / ref["path"]).resolve()
    require(path.is_relative_to(Path(root).resolve()), "文件引用超出证据目录")
    require(path.is_file() and file_hash(path) == ref["sha256"], f"文件缺失或 SHA256 不符：{ref['path']}")
    return path


def inventory(root, ref):
    value = read_json(reference(root, ref))
    require(isinstance(value, dict) and isinstance(value.get("files"), list) and value["files"], "快照必须列出非空 files")
    seen = set()
    for entry in value["files"]:
        # 清单可附 dtype/shape 等元数据；引用本身只有 path 和 sha256。
        require(isinstance(entry, dict) and {"path", "sha256"} <= set(entry), "快照文件引用无效")
        bound = {key: entry[key] for key in ("path", "sha256")}
        actual = reference(root, bound)
        require(actual not in seen, "快照包含重复文件")
        seen.add(actual)
    return value


def declaration(root, ref):
    value = read_json(reference(root, ref))
    names = {"schema_version", "operator", "created_at", "case_ids", "correctness_case_ids", "reuse_policy"}
    if isinstance(value, dict) and "stability_policy" in value:
        names.add("stability_policy")
        require(value["stability_policy"] == BOUNDED_OUTLIER_POLICY, "未知 stability_policy")
    fields(value, names, "预声明")
    require(value["schema_version"] == 1 and isinstance(value["operator"], str) and value["operator"], "预声明身份无效")
    for key in ("case_ids", "correctness_case_ids"):
        ids = value[key]
        require(isinstance(ids, list) and ids and all(type(item) is int and item > 0 for item in ids) and len(ids) == len(set(ids)), f"{key} 必须为不重复正整数")
    require(set(value["case_ids"]) <= set(value["correctness_case_ids"]), "正确性集合必须覆盖全部计时 case")
    timestamp(value["created_at"])
    fields(value["reuse_policy"], {"max_age_seconds", "max_ab_gap_seconds"}, "复用策略")
    for key, number in value["reuse_policy"].items():
        positive(number, key)
    return value


def replay_oracle(root, receipt, output_ref, limits, *, deadline=None, logs=None, verified=None):
    """重算冻结 golden 与实际输出的差异，不信任 passed 标签。"""
    require(receipt.get("status") == "passed", "oracle 未通过")
    output = inventory(root, output_ref)
    require(receipt.get("output_sha256") == output_ref["sha256"], "oracle 输出绑定不符")
    reference(root, receipt["oracle_source"])
    checks = receipt.get("checks")
    require(isinstance(checks, list) and checks, "oracle 缺少逐输出检查")
    if isinstance(limits, dict) and limits.get("mode") == "original_python_v1":
        from .original_oracle import execute
        actuals = [check["actual"] for check in checks]
        expected_outputs = [{key: entry[key] for key in ("path", "sha256")} for entry in output["files"]]
        require(len(actuals) == len(expected_outputs) and sorted(actuals, key=lambda x: x["path"]) == sorted(expected_outputs, key=lambda x: x["path"]), "oracle 未完整覆盖输出清单")
        execute(root, receipt, limits, deadline=deadline, logs=logs, verified=verified, reuse=True)
        return
    require("replay" not in receipt, "原 oracle 回放缺少 workload 契约绑定")
    fields(limits, {"atol", "rtol", "equal_nan"}, "预注册精度限制")
    for key in ("atol", "rtol"):
        require(type(limits[key]) in (int, float) and math.isfinite(limits[key]) and limits[key] >= 0, "精度限制无效")
    require(type(limits["equal_nan"]) is bool, "equal_nan 必须为布尔值")
    actuals = []
    for check in checks:
        fields(check, {"actual", "expected", "dtype", "atol", "rtol", "equal_nan"}, "oracle check")
        require(check["dtype"] in FORMATS, "不支持的 oracle dtype")
        for key in ("atol", "rtol"):
            require(type(check[key]) in (int, float) and math.isfinite(check[key]) and 0 <= check[key] <= limits[key], "oracle 放宽了预注册精度限制")
        require(type(check["equal_nan"]) is bool and (not check["equal_nan"] or limits["equal_nan"]), "oracle 放宽了 NaN 规则")
        actual = reference(root, check["actual"]).read_bytes()
        expected = reference(root, check["expected"]).read_bytes()
        fmt = "<" + FORMATS[check["dtype"]]
        width = struct.calcsize(fmt)
        require(len(actual) == len(expected) and len(actual) > 0 and len(actual) % width == 0, "oracle 输出长度或 dtype 不匹配")
        for index, ((got,), (want,)) in enumerate(zip(struct.iter_unpack(fmt, actual), struct.iter_unpack(fmt, expected), strict=True)):
            if math.isnan(got) or math.isnan(want):
                valid = check["equal_nan"] and math.isnan(got) and math.isnan(want)
            elif math.isinf(got) or math.isinf(want):
                valid = got == want
            else:
                valid = abs(got - want) <= check["atol"] + check["rtol"] * abs(want)
            require(valid, f"oracle 原始输出不匹配，元素 {index}")
        actuals.append(check["actual"])
    expected_outputs = [{key: entry[key] for key in ("path", "sha256")} for entry in output["files"]]
    require(len(actuals) == len(expected_outputs) and sorted(actuals, key=lambda x: x["path"]) == sorted(expected_outputs, key=lambda x: x["path"]), "oracle 未完整覆盖输出清单")


def replay_stages(root, execution, names):
    require(execution.get("status") == "passed" and execution.get("returncode") == 0, "执行回执未通过")
    stages = execution.get("stages")
    fields(stages, names, "执行阶段")
    for name, stage in stages.items():
        fields(stage, {"argv", "cwd", "returncode", "pid", "started_at", "finished_at", "elapsed_seconds", "stdout", "stderr"}, f"{name} 阶段")
        require(stage["returncode"] == 0 and type(stage["pid"]) is int and stage["pid"] > 0, f"{name} 执行失败")
        require(isinstance(stage["argv"], list) and stage["argv"] and all(isinstance(x, str) for x in stage["argv"]), "执行 argv 无效")
        require(isinstance(stage["cwd"], str) and stage["cwd"], "执行 cwd 无效")
        started, finished = timestamp(stage["started_at"]), timestamp(stage["finished_at"])
        require(finished >= started and type(stage["elapsed_seconds"]) in (int, float) and math.isfinite(stage["elapsed_seconds"]) and stage["elapsed_seconds"] >= 0, "执行时序无效")
        reference(root, stage["stdout"])
        reference(root, stage["stderr"])
    return stages


def _base(path, *, deadline=None, verified=None):
    path = Path(path).resolve()
    capture = read_json(path)
    require(isinstance(capture, dict), "采集记录必须为对象")
    root, artifacts = path.parent, capture.get("artifacts")
    require(isinstance(artifacts, dict), "缺少 artifacts")
    for ref in artifacts.values():
        reference(root, ref)
    identity = capture.get("identity")
    require(isinstance(identity, dict), "缺少 identity")
    for name in ("source", "binary", "input", "workload"):
        key = name + ("_sha256" if name in ("source", "binary") else "_ref")
        require(identity.get(key) == artifacts[name]["sha256"], f"{name} 身份与快照不符")
    inventory(root, artifacts["source"])
    inventory(root, artifacts["input"])
    workload = read_json(reference(root, artifacts["workload"]))
    require(isinstance(workload, dict), "workload 必须为对象")
    decl = declaration(root, artifacts["declaration"])
    require(capture.get("schema_version") == 1 and capture.get("declaration_ref") == artifacts["declaration"]["sha256"] and capture.get("operator") == decl["operator"], "采集与声明身份不符")
    require(type(capture.get("case_id")) is int and capture["case_id"] in decl["correctness_case_ids"], "采集 case 不在声明中")
    require(timestamp(decl["created_at"]) <= timestamp(capture["captured_at"]), "声明晚于采集")
    receipt = read_json(reference(root, artifacts["oracle_receipt"]))
    execution = read_json(reference(root, artifacts["execution_receipt"]))
    for record in (receipt, execution):
        require(isinstance(record, dict), "回执必须为对象")
        for key in ("source_sha256", "binary_sha256", "input_ref"):
            require(record.get(key) == identity[key], f"回执 {key} 绑定不符")
        require(record.get("case_id") == capture["case_id"], "回执 case 绑定不符")
    require(execution.get("oracle_receipt_sha256") == artifacts["oracle_receipt"]["sha256"], "执行与 oracle 回执绑定不符")
    replay_oracle(root, receipt, artifacts["output"], workload.get("oracle_limits"), deadline=deadline, verified=verified)
    return root, capture, decl, execution


def receipt_signature(receipt):
    if "replay" in receipt:
        from .original_oracle import contract
        return {"oracle_source_sha256": receipt["oracle_source"]["sha256"],
                "original_oracle_contract": contract(receipt["replay"])}
    checks = sorted(receipt["checks"], key=lambda check: check["actual"]["path"])
    return {"oracle_source_sha256": receipt["oracle_source"]["sha256"], "checks": [
        {"actual_path": check["actual"]["path"], "expected_sha256": check["expected"]["sha256"],
         **{key: check[key] for key in ("dtype", "atol", "rtol", "equal_nan")}} for check in checks]}


def oracle_signature(root, capture):
    return receipt_signature(read_json(reference(root, capture["artifacts"]["oracle_receipt"])))


def replay_capture(path, *, deadline=None, verified=None):
    """核验无 A/B 角色的快照，逐完整调用重建 20 个原始 Task 样本。"""
    try:
        root, capture, decl, execution = _base(path, deadline=deadline, verified=verified)
        fields(capture, CAPTURE_FIELDS, "采集记录")
        fields(capture["identity"], IDENTITY, "采集 identity")
        artifacts, identity = capture["artifacts"], capture["identity"]
        fields(artifacts, ARTIFACTS, "采集 artifacts")
        require(capture["protocol"] == PROTOCOL and capture["metric"] == METRIC and capture["warmup_calls"] == 5 and capture["formal_calls"] == 20, "必须使用统一 5/20 计时协议")
        require(capture["case_id"] in decl["case_ids"], "计时 case 不在声明中")
        for name in ("hardware", "toolchain", "collector"):
            require(identity[name + "_ref"] == artifacts[name]["sha256"], f"{name} 身份不符")
        for name in ("toolchain", "collector"):
            inventory(root, artifacts[name])
        policy = capture["cache_policy"]
        fields(policy, {"eviction_kernel", "eviction_bytes", "l2_bytes", "address_policy"}, "清 L2 策略")
        require(policy["eviction_kernel"] == "CannBenchCacheClean" and type(policy["eviction_bytes"]) is int and type(policy["l2_bytes"]) is int and policy["eviction_bytes"] > policy["l2_bytes"] > 0 and isinstance(policy["address_policy"], str) and policy["address_policy"], "清 L2 策略无效")
        stages = replay_stages(root, execution, {"native", "export", "oracle", "hardware_before", "hardware_after"})
        require(timestamp(decl["created_at"]) <= timestamp(capture["captured_at"]) <= min(timestamp(s["started_at"]) for s in stages.values()), "声明或采集时间晚于执行")
        require(execution.get("task_csv_sha256") == artifacts["task_csv"]["sha256"] and execution.get("native_receipt_sha256") == artifacts["native_receipt"]["sha256"], "执行与 Task/native 回执绑定不符")
        profile_files = execution.get("profile_files")
        require(isinstance(profile_files, list) and profile_files, "缺少原始 PROF 文件清单")
        listed = {reference(root, ref) for ref in profile_files}
        require(len(listed) == len(profile_files), "原始 PROF 文件清单重复")
        profile_root = root / "profile"
        require(profile_root.is_dir() and listed == {p.resolve() for p in profile_root.rglob("*") if p.is_file()}, "原始 PROF 文件缺失或未完整登记")
        require(reference(root, artifacts["task_csv"]) in listed, "Task CSV 未绑定原始 PROF 目录")
        prefixes = execution.get("profile_log_prefixes", [])
        require(isinstance(prefixes, list), "原始日志前缀清单无效")
        for prefix in prefixes:
            fields(prefix, {"profile_path", "prefix"}, "原始日志前缀")
            profile = (root / prefix["profile_path"]).resolve()
            require(profile in listed and re.fullmatch(r"collection_(host|device_[0-9]+)\.log", profile.name) is not None, "只允许 profiler 收集日志追加")
            require(profile.read_bytes().startswith(reference(root, prefix["prefix"]).read_bytes()), "profiler 日志改写了原始前缀")
        native = read_json(reference(root, artifacts["native_receipt"]))
        require(isinstance(native, dict), "native 回执无效")
        for key in ("protocol", "operator", "case_id", "warmup_calls", "formal_calls"):
            require(native.get(key) == capture[key], f"native {key} 不匹配")
        require(native.get("pid") == stages["native"]["pid"] and native.get("input_bytes_unchanged") is True and native.get("l2_bytes") == policy["l2_bytes"] and native.get("eviction_bytes") == policy["eviction_bytes"], "native 进程/输入/清 L2 绑定不符")
        native_log = reference(root, stages["native"]["stdout"]).read_text()
        messages = [line.split("APROF_SINGLE_ROLE_TASK_JSON:", 1)[1] for line in native_log.splitlines() if line.startswith("APROF_SINGLE_ROLE_TASK_JSON:")]
        require(len(messages) == 1 and json.loads(messages[0]) == native, "native 原始日志不匹配")
        hardware = read_json(reference(root, artifacts["hardware"]))
        require(isinstance(hardware, dict) and type(hardware.get("device")) is int and native.get("device") == hardware["device"] and all(isinstance(hardware.get(key), str) and hardware[key] for key in ("physical_device", "soc_version")), "硬件身份不完整")
        for name in ("hardware_before", "hardware_after"):
            require(read_json(reference(root, stages[name]["stdout"])) == hardware, "前后硬件身份变化")
        require(capture["task_table"] in ("kernel_details", "op_summary"), "Task 表类型无效")
        csv = reference(root, artifacts["task_csv"])
        parsed = complete_calls(csv if capture["task_table"] == "kernel_details" else None, csv if capture["task_table"] == "op_summary" else None, capture["kernel_names"], eviction_type=policy["eviction_kernel"])
        cv = statistics.stdev(parsed["values_us"]) / statistics.fmean(parsed["values_us"])
        result = {"capture": capture, "capture_ref": file_hash(path), "captured_at": capture["captured_at"], "values_us": parsed["values_us"], "median_us": parsed["median_us"], "within_process_cv": cv, "oracle_signature": oracle_signature(root, capture)}
        if decl.get("stability_policy") == BOUNDED_OUTLIER_POLICY:
            stats = bounded_statistics(parsed["values_us"])
            result.update(sample_statistics=stats, median_us=stats["median_us"], within_process_cv=stats["cv"])
        return result
    except (KeyError, TypeError, ValueError) as exc:
        if hasattr(exc, "reason"):
            raise
        raise ContractError(f"统一计时证据无效：{exc}") from exc


def _replay_correctness(path, *, source, operator, declaration_ref, case_ids, deadline=None, verified=None):
    """完整正确性独立于计时；可复用逐 case 原始输出，但不可只提交 passed。"""
    path = Path(path).resolve()
    value = read_json(path)
    fields(value, {"schema_version", "operator", "source_sha256", "declaration_ref", "cases"}, "完整正确性")
    require(value["schema_version"] == 1 and value["operator"] == operator and value["source_sha256"] == source and value["declaration_ref"] == declaration_ref, "完整正确性身份不符")
    require(isinstance(value["cases"], list) and value["cases"], "完整正确性缺少 cases")
    seen = set()
    identities = {}
    oracles = {}
    for ref in value["cases"]:
        case_path = reference(path.parent, ref)
        root, case, decl, execution = _base(case_path, deadline=deadline, verified=verified)
        require(case["protocol"] in (CORRECTNESS_PROTOCOL, PROTOCOL), "正确性证据协议无效")
        require(case["identity"]["source_sha256"] == source and case["operator"] == operator and case["declaration_ref"] == declaration_ref, "正确性 case 身份不符")
        require(case["case_id"] not in seen, "正确性 case 重复")
        seen.add(case["case_id"])
        identities[case["case_id"]] = case["identity"]
        oracles[case["case_id"]] = oracle_signature(root, case)
        names = {"native", "export", "oracle", "hardware_before", "hardware_after"} if case["protocol"] == PROTOCOL else {"execute", "oracle"}
        stages = replay_stages(root, execution, names)
        require(timestamp(decl["created_at"]) <= timestamp(case["captured_at"]) <= min(timestamp(s["started_at"]) for s in stages.values()), "声明或采集时间晚于正确性执行")
    require(seen == set(case_ids), "完整正确性 case 覆盖不符")
    return {"manifest_ref": file_hash(path), "cases": identities, "oracle_signatures": oracles}


def replay_correctness(path, *, source, operator, declaration_ref, case_ids, deadline=None, verified=None):
    try:
        return _replay_correctness(path, source=source, operator=operator, declaration_ref=declaration_ref, case_ids=case_ids, deadline=deadline, verified=verified)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if hasattr(exc, "reason"):
            raise
        raise ContractError(f"完整正确性证据无效：{exc}") from exc


def _evaluate_request(path, *, evaluated_at=None):
    path = Path(path).resolve()
    request = read_json(path)
    fields(request, {"schema_version", "protocol", "operator", "candidate_id", "baseline_source_sha256", "candidate_source_sha256", "declaration", "baseline_captures", "candidate_captures", "baseline_correctness", "candidate_correctness"}, "性能验收请求")
    require(request["schema_version"] == 1 and request["protocol"] == PROTOCOL and isinstance(request["candidate_id"], str) and request["candidate_id"], "性能验收请求身份无效")
    decl = declaration(path.parent, request["declaration"])
    require(decl["operator"] == request["operator"], "operator 与声明不符")
    declared_ref = request["declaration"]["sha256"]
    when = evaluated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    now = timestamp(when)
    roles = {}
    reasons = []
    verified = set()
    for role in ("baseline", "candidate"):
        source = request[role + "_source_sha256"]
        correctness = reference(path.parent, request[role + "_correctness"])
        correct = replay_correctness(correctness, source=source, operator=request["operator"], declaration_ref=declared_ref, case_ids=decl["correctness_case_ids"], verified=verified)
        captures = request[role + "_captures"]
        require(isinstance(captures, list) and captures, "采集列表为空")
        by_case = {}
        for ref in captures:
            replay = replay_capture(reference(path.parent, ref), verified=verified)
            capture = replay["capture"]
            require(capture["operator"] == request["operator"] and capture["identity"]["source_sha256"] == source and capture["declaration_ref"] == declared_ref, f"{role} source/operator/declaration 绑定不符")
            case = capture["case_id"]
            for key in ("source_sha256", "binary_sha256", "input_ref", "workload_ref"):
                require(capture["identity"][key] == correct["cases"][case][key], f"{role}/case {case} 正确性与计时 {key} 不同")
            require(replay["oracle_signature"] == correct["oracle_signatures"][case], f"{role}/case {case} 原 oracle 或 golden 绑定不同")
            require(case not in by_case, "计时 case 重复")
            by_case[case] = replay
            age = now - timestamp(capture["captured_at"])
            require(age >= 0, "采集记录来自未来")
            if age > decl["reuse_policy"]["max_age_seconds"]:
                reasons.append(f"{role}/case {case} 超出预声明复用时限")
            if replay.get("sample_statistics", {}).get("exclusion_limit_exceeded"):
                reasons.append(f"{role}/case {case} 异常值超过预声明的 2/20 上限")
            if replay["within_process_cv"] > 0.05:
                reasons.append(f"{role}/case {case} 轮内 CV 超过 5%")
        require(set(by_case) == set(decl["case_ids"]), f"{role} 计时 case 覆盖不全或超出声明")
        roles[role] = by_case
    results = []
    for case in decl["case_ids"]:
        a, b = (roles[role][case] for role in ("baseline", "candidate"))
        for key in ("workload_ref", "input_ref", "hardware_ref", "toolchain_ref", "collector_ref"):
            require(a["capture"]["identity"][key] == b["capture"]["identity"][key], f"case {case} 的 A/B {key} 不同")
        require(a["capture"]["cache_policy"] == b["capture"]["cache_policy"], "A/B 清 L2 策略不同")
        gap = abs(timestamp(a["captured_at"]) - timestamp(b["captured_at"]))
        if gap > decl["reuse_policy"]["max_ab_gap_seconds"]:
            reasons.append(f"case {case} A/B 间隔超出预声明范围")
        results.append({"case_id": case, "baseline_capture_ref": a["capture_ref"], "candidate_capture_ref": b["capture_ref"], "baseline_median_us": a["median_us"], "candidate_median_us": b["median_us"], "speedup": a["median_us"] / b["median_us"], "regression": b["median_us"] / a["median_us"] - 1, "baseline_within_process_cv": a["within_process_cv"], "candidate_within_process_cv": b["within_process_cv"], "ab_gap_seconds": gap})
        if "stability_policy" in decl:
            results[-1].update(baseline_statistics=a["sample_statistics"], candidate_statistics=b["sample_statistics"])
    speedup = math.exp(statistics.fmean(math.log(item["speedup"]) for item in results))
    regression = max(item["regression"] for item in results)
    if reasons:
        verdict = "inconclusive"
    elif speedup < 1.03 or regression > 0.03:
        verdict = "rejected"
        if speedup < 1.03:
            reasons.append("等权几何中位数比未达到 1.03")
        if regression > 0.03:
            reasons.append("至少一个 case 回归超过 3%")
    else:
        verdict = "accepted"
    result = {"schema_version": 1, "kind": "unified_timing_result", "protocol": PROTOCOL, "metric": METRIC, "operator": request["operator"], "candidate_id": request["candidate_id"], "request": {"path": str(path), "sha256": file_hash(path)}, "evaluated_at": when, "verdict": verdict, "speedup": speedup, "max_case_regression": regression, "thresholds": {"min_speedup": 1.03, "max_case_regression": 0.03, "max_within_process_cv": 0.05}, "cases": results, "reasons": reasons, "authority": "performance_engineering_only", "replication_recommended": math.isclose(speedup, 1.03) or math.isclose(regression, 0.03), "uncertainty": "单进程轮内 CV；不证明跨进程置信度、硬件资格或路由/语义正确性"}
    if "stability_policy" in decl:
        result.update(stability_policy=decl["stability_policy"], uncertainty="预声明异常值剔除后的中位数与轮内 CV；原始样本和剔除索引保留；不证明跨进程置信度、硬件资格或路由/语义正确性")
    return {**result, "decision_hash": content_hash(result)}


def evaluate_request(path, *, evaluated_at=None):
    try:
        return _evaluate_request(path, evaluated_at=evaluated_at)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if hasattr(exc, "reason"):
            raise
        raise ContractError(f"性能验收请求无效：{exc}") from exc


def finalize_timing(request, output):
    result = evaluate_request(request)
    with Path(output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return result


def verify_timing(result_path):
    result = read_json(result_path)
    require(isinstance(result, dict) and isinstance(result.get("request"), dict), "性能结果缺少请求绑定")
    request = result["request"]
    require(file_hash(request["path"]) == request["sha256"], "性能请求已更改")
    replayed = evaluate_request(request["path"], evaluated_at=result["evaluated_at"])
    require(replayed == result, "性能结果与原始证据回放不符")
    return {"valid": True, "verdict": result["verdict"], "decision_hash": result["decision_hash"]}

"""只校验观测算术和口径，不判定 Problem、Action 或真实硬件瓶颈。

输入中的 window/durations/counters 都属于同一个 scope。字节计数必须声明
layer；逻辑 GM 请求和 HBM 事务分开推导。synthetic 输入始终保持假设身份。
返回 unknown 表示资料不足；invalid 表示格式、自洽性或已存派生副本冲突。
派生量只依赖明确列出的原始字段，不能作为新的独立支持证据。
"""
from __future__ import annotations

import math

from .errors import ContractError
from .jsonio import content_hash, require_json_value

_SECONDS = {"s": 1, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
_BYTES = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}
_RATES = {"B/s": 1, "GB/s": 1e9, "GiB/s": 1024 ** 3}


def validate_and_derive(observation: dict) -> dict:
    """校验一个明确窗口；不修改输入，也不回填任何旧 fact/派生记录。

    durations: [{id,value,unit,window_ref:"/window"}]
    duration_partitions: [{parent_id,member_ids,complete:bool}]
    counters: [{id,kind:read_bytes|write_bytes|read_calls|write_calls,
                value,unit,layer,window_ref:"/window"}]
    throughput_duration_id 指向本窗口内的时间量；references 中的 layer、
    duration_id、bytes_basis 必须与比较量相同。可选 derived_claims 用于检查
    已存副本；每项带 quantity_id/value/unit/layer/dependency_hash。
    """
    result = {"status": "valid", "errors": [], "unknowns": [], "derived": {},
              "input_sha256": None, "evidence_status": None}
    errors, unknowns, derived = result["errors"], result["unknowns"], result["derived"]

    def error(path, reason):
        errors.append({"path": path, "reason": reason})

    def unknown(path, reason):
        unknowns.append({"path": path, "reason": reason})

    try:
        require_json_value(observation)
        if not isinstance(observation, dict):
            raise ContractError("observation must be an object")
        result["input_sha256"] = content_hash(observation)
    except (ContractError, ValueError, TypeError) as exc:
        error("/", str(exc))
        result["status"] = "invalid"
        return result
    result["evidence_status"] = observation.get("evidence_status", "unknown")
    if not isinstance(observation.get("scope"), dict) or not observation["scope"]:
        unknown("/scope", "缺少实现、workload、对象和阶段的绑定；不可跨 scope 合并。")

    def number(value, path, *, integer=False, positive=False):
        if value is None:
            unknown(path, '数值未提供，保持 unknown。')
            return None
        try:
            valid = (not isinstance(value, bool) and isinstance(value, (int, float))
                     and math.isfinite(value) and value >= 0
                     and not (positive and value == 0)
                     and not (integer and not float(value).is_integer()))
        except (OverflowError, TypeError, ValueError):
            valid = False
        if not valid:
            error(path, "要求有限非负数；计数须为整数，时间分母须大于0；bool 不是数值。")
            return None
        return value

    def entries(name):
        value = observation.get(name, [])
        if not isinstance(value, list):
            error('/' + name, '必须为数组。')
            return []
        return value

    def dep(pointer, value):
        return {"pointer": pointer, "value_sha256": content_hash(value)}

    def finite(value, path, *, positive=False):
        try:
            valid = math.isfinite(value) and not (positive and value <= 0)
        except (OverflowError, TypeError, ValueError):
            valid = False
        if not valid:
            error(path, "派生运算溢出、非有限或正数下溢为0。")
            return None
        return value

    def emit(key, value, unit, layer, formula, deps, *, positive=False):
        value = finite(value, key, positive=positive)
        if value is None:
            return
        dependencies = sorted(deps, key=lambda item: item["pointer"])
        derived[key] = {"value": value, "unit": unit, "layer": layer,
                        "formula": formula, "dependencies": dependencies,
                        "dependency_hash": content_hash(dependencies),
                        "input_sha256": result["input_sha256"],
                        "evidence_status": result["evidence_status"],
                        "independent_support": False}

    window = observation.get("window")
    window_s = None
    if window is None:
        unknown("/window", "缺少明确观测窗口，不能推导吞吐。")
    elif not isinstance(window, dict):
        error("/window", "窗口必须为对象。")
    else:
        start = number(window.get("start"), "/window/start")
        end = number(window.get("end"), "/window/end")
        unit = window.get("unit")
        if unit is None:
            unknown('/window/unit', '缺少时间单位，保持 unknown。')
        elif not isinstance(unit, str) or unit not in _SECONDS:
            error("/window/unit", "时间单位必须为 s/ms/us/ns。")
        elif start is not None and end is not None:
            if end <= start:
                error("/window", "窗口 end 必须大于 start。")
            else:
                window_s = finite((end - start) * _SECONDS[unit], "/window", positive=True)
                if window_s is not None:
                    emit("window.duration", window_s, "s", "time", "(end-start)*unit_seconds",
                         [dep("/window", window)])

    durations = {}
    for i, item in enumerate(entries("durations")):
        path = f"/durations/{i}"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            error(path, "时间计数需要对象及字符串 id。")
            continue
        key = item["id"]
        value = number(item.get("value"), path + "/value")
        if key in durations:
            error(path + "/id", "重复时间 id。")
            continue
        if item.get('unit') is None or item.get('window_ref') is None:
            unknown(path, '时间计数缺少单位或观测窗口绑定。')
            continue
        if (not isinstance(item['unit'], str) or item.get("unit") not in _SECONDS
                or item.get("window_ref") != "/window"):
            error(path, "时间计数须声明合法单位并绑定 /window。")
            continue
        if value is not None:
            seconds = finite(value * _SECONDS[item["unit"]], path + "/value", positive=value > 0)
            if seconds is None:
                continue
            if window_s is not None and seconds - window_s > max(1e-15, window_s * 1e-12):
                error(path, "时间计数超过其观测窗口。")
            durations[key] = (seconds, path, item)
    for i, partition in enumerate(entries("duration_partitions")):
        path = f"/duration_partitions/{i}"
        if not isinstance(partition, dict) or type(partition.get("complete")) is not bool:
            error(path, "时间分解需要 complete 布尔值。")
            continue
        members = partition.get("member_ids", [])
        if (not isinstance(members, list) or not all(isinstance(x, str) for x in members)
                or not isinstance(partition.get('parent_id'), str)):
            error(path, "member_ids 必须为 id 列表。")
            continue
        if len(set(members)) != len(members) or partition.get("parent_id") in members:
            error(path, "时间分解不能重复成员或包含父计数。")
            continue
        names = [partition.get("parent_id"), *members]
        if not all(name in durations for name in names):
            unknown(path, "时间分解缺少父计数或成员。")
            continue
        parent = durations[names[0]][0]
        total = finite(sum(durations[name][0] for name in members), path)
        if total is None:
            continue
        tolerance = max(1e-15, parent * 1e-12)
        if total - parent > tolerance or (partition["complete"] and abs(total - parent) > tolerance):
            error(path, "互斥时间成员之和与父时间不一致。")

    counters, groups = {}, {}
    for i, item in enumerate(entries("counters")):
        path = f"/counters/{i}"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            error(path, "计数需要对象及字符串 id。")
            continue
        key, kind, layer = item["id"], item.get("kind"), item.get("layer")
        if key in counters:
            error(path + "/id", "重复计数 id。")
            continue
        if not isinstance(kind, str) or kind not in {"read_bytes", "write_bytes", "read_calls", "write_calls"}:
            error(path + "/kind", "未识别的计数维度。")
            continue
        if not isinstance(layer, str) or not layer:
            unknown(path + "/layer", "缺少 logical_gm/hbm 等明确存储层级。")
            continue
        if item.get('window_ref') is None:
            unknown(path, '计数缺少观测窗口绑定。')
            continue
        if item.get("window_ref") != "/window":
            error(path, "计数必须绑定同一 /window。")
            continue
        is_bytes = kind.endswith("_bytes")
        units = _BYTES if is_bytes else {"calls": 1}
        if item.get('unit') is None:
            unknown(path + '/unit', '计数缺少单位，保持 unknown。')
            continue
        if not isinstance(item['unit'], str) or item.get("unit") not in units:
            error(path + "/unit", "字节和调用次数单位不可混用；B 为字节。")
            continue
        value = number(item.get("value"), path + "/value", integer=True)
        if value is None:
            continue
        group = groups.setdefault(layer, {})
        if kind in group:
            error(path, "同一窗口/层级/方向的重复计数，不能自动累加独立性不明的数据。")
            continue
        normalized = finite(value * units[item["unit"]], path + "/value")
        if normalized is None:
            continue
        counter = (normalized, path, item)
        counters[key] = counter
        group[kind] = counter

    # 一个显式求和请求不得把逻辑请求字节和 HBM 事务字节混成总流量。
    for i, aggregate in enumerate(entries("aggregates")):
        ids = aggregate.get("counter_ids", []) if isinstance(aggregate, dict) else []
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            error(f"/aggregates/{i}", "counter_ids 必须为字符串数组。")
            continue
        if len(set(ids)) != len(ids):
            error(f"/aggregates/{i}", '同一原始计数不能重复求和。')
            continue
        selected = [counters[x][2] for x in ids if x in counters]
        if len(selected) != len(ids) or not ids:
            unknown(f"/aggregates/{i}", "求和缺少明确计数。")
        elif len({x["layer"] for x in selected}) != 1 or any(not x["kind"].endswith("_bytes") for x in selected):
            error(f"/aggregates/{i}", "禁止混合 logical_gm/HBM 等层级或字节/调用口径。")

    duration_id = observation.get("throughput_duration_id")
    if duration_id is not None and not isinstance(duration_id, str):
        error('/throughput_duration_id', '时间引用须为字符串 id。')
        duration_id = None
    duration = durations.get(duration_id)
    if duration is None:
        unknown("/throughput_duration_id", "缺少吞吐分母时间，保持 unknown。")
    elif duration[0] <= 0:
        error("/throughput_duration_id", "吞吐时间分母必须大于0。")
        duration = None
    for layer, group in groups.items():
        for direction in ("read", "write"):
            b, c = group.get(direction + "_bytes"), group.get(direction + "_calls")
            if b and c:
                if c[0] == 0:
                    if b[0] > 0:
                        error(c[1], "字节非零但调用数为0。")
                    else:
                        unknown(c[1], "0/0 的平均请求大小未知。")
                else:
                    emit(f"{layer}.{direction}_mean_payload", b[0] / c[0], "B/call", layer,
                         "bytes/calls", [dep(b[1], b[2]), dep(c[1], c[2])])
            elif b and layer == "logical_gm":
                unknown(f"{layer}.{direction}_mean_payload", "缺少调用次数，不能推导平均请求大小。")
        pair = [group.get("read_bytes"), group.get("write_bytes")]
        if not all(pair):
            unknown(layer + ".bandwidth", "读写混合带宽必须具有同窗口、同层级的读和写字节。")
            continue
        deps = [dep(x[1], x[2]) for x in pair]
        total = finite(sum(x[0] for x in pair), layer + ".total_bytes")
        if total is None:
            continue
        emit(layer + ".total_bytes", total, "B", layer, "read_bytes+write_bytes", deps)
        if duration and window_s is not None:
            deps += [dep(duration[1], duration[2]), dep("/window", window),
                     dep("/throughput_duration_id", duration_id)]
            bytes_per_second = finite(total / duration[0], layer + ".bandwidth", positive=total > 0)
            if bytes_per_second is not None:
                emit(layer + ".bandwidth", bytes_per_second / 1e9, "GB/s", layer,
                     "(read_bytes+write_bytes)/duration_seconds/1e9", deps, positive=total > 0)
    reference_keys = set()
    for i, reference in enumerate(entries("references")):
        path = f"/references/{i}"
        if not isinstance(reference, dict):
            error(path, "带宽参照必须为对象。")
            continue
        layer = reference.get("layer")
        if not isinstance(layer, str) or not layer:
            error(path + "/layer", "参照须声明明确存储层级。")
            continue
        key = layer + ".bandwidth"
        unit = reference.get("unit")
        if (reference.get("duration_id") != duration_id
                or reference.get("bytes_basis") != ["read_bytes", "write_bytes"]):
            error(path, "参照必须使用同层级、同时间分母和相同读写求和口径。")
            continue
        if key in reference_keys:
            error(path, "同一窗口/层级/时间分母/读写口径的重复参照，不能自动选择。")
            derived.pop(layer + ".reference_ratio", None)
            continue
        reference_keys.add(key)
        if not isinstance(unit, str) or unit not in _RATES:
            error(path + "/unit", "参照必须声明 B/s、GB/s 或 GiB/s。")
            continue
        value = number(reference.get("value"), path + "/value", positive=True)
        reference_bps = (finite(value * _RATES[unit], path + "/value", positive=True)
                         if value is not None else None)
        if key not in derived:
            unknown(path, "缺少同层级带宽派生量，不能借用另一存储层。")
        elif reference_bps is not None:
            base = derived[key]
            bandwidth_bps = finite(base["value"] * 1e9, layer + ".reference_ratio",
                                   positive=base["value"] > 0)
            if bandwidth_bps is not None:
                emit(layer + ".reference_ratio", bandwidth_bps / reference_bps,
                     "ratio", layer, "same_layer_bandwidth/reference_bandwidth",
                     base["dependencies"] + [dep(path, reference)], positive=bandwidth_bps > 0)
    for i, claim in enumerate(entries("derived_claims")):
        path = f"/derived_claims/{i}"
        if (not isinstance(claim, dict) or not isinstance(claim.get('quantity_id'), str)
                or claim.get("quantity_id") not in derived):
            unknown(path, "已存派生副本没有可复算的原始依赖。")
            continue
        actual = derived[claim["quantity_id"]]
        value = number(claim.get("value"), path + "/value")
        if claim.get("unit") != actual["unit"] or claim.get("layer") != actual["layer"]:
            error(path, "派生副本单位或存储层不匹配。")
        if claim.get("dependency_hash") != actual["dependency_hash"]:
            error(path, "派生副本依赖 hash 已失效。")
        if value is not None and not math.isclose(value, actual["value"], rel_tol=1e-12, abs_tol=1e-12):
            error(path, "派生副本数值与当前原始量重算不一致。")
    result["status"] = "invalid" if errors else ("unknown" if unknowns else "valid")
    if errors:
        # 错误输入的局部算术可供定位，不能作为可用证据导出。
        for quantity in derived.values():
            quantity["usable_as_evidence"] = False
    else:
        for quantity in derived.values():
            quantity["usable_as_evidence"] = True
    return result

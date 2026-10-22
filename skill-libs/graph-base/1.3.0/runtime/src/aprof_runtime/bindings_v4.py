"""完整方案的共同计划与逐实例路由；核验声明身份，不证明任意源码语义。

v4 不把计划保证写入 Context facts。保证仅能在最终候选上补足同实例的
未知实施条件；已知相反证据仍须通过新的不可变推理记录处理。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from . import bindings as b
from .errors import GraphError
from .jsonio import content_hash, file_hash
from .knowledge import validate_schema

SCHEMA = "aprof.handoff/v4"
JOINT_DIMENSIONS = {"ownership", "data_path", "layout", "synchronization", "workspace_ownership", "numeric_semantics", "resource_lifetimes"}


def _part(root, name, value):
    schema = b._json_file(Path(root) / "schemas/knowledge-handoff-v4.schema.json")
    errors = list(Draft202012Validator({"$ref": "#/$defs/" + name, "$defs": schema["$defs"]}).iter_errors(value))
    if errors:
        raise GraphError(f"{name}: {errors[0].json_path}: {errors[0].message}")


def _members(values, *, key):
    result = {value[key]: value for value in values}
    if len(result) != len(values):
        raise GraphError("方案成员不能重复或用重复实例覆盖另一成员")
    return result


def _scope(scope, common):
    from .diagnosis_reasoning import validate_scope
    validate_scope(scope, common)


def _plan(root, plan, reasoning, members, *, hard):
    """共同计划覆盖所有成员；各成员仍只取得自己范围的事实。"""
    scope = plan["scope"]
    _scope(scope, reasoning["current"]["scope"])
    targets = set()
    for member in members:
        _scope(member["instance"]["scope"], scope)
        targets.update(member["instance"]["scope"]["target_ids"])
    # 完整有效父计划可以覆盖本轮未修改的目标；复用它不会扩大成员变更授权。
    if not targets <= set(scope["target_ids"]):
        raise GraphError("共同计划 scope 必须完整覆盖全部成员")
    return b._plan(root, plan, scope, hard=hard)


def compatibility_configuration(selection, *, execution=None):
    """共同兼容审查的规范身份；排序只规范成员身份，不改变步骤依赖。"""
    actual = {} if execution is None else _members(execution["members"], key="instance_id")
    if execution is not None and set(actual) != {m["instance"]["instance_id"] for m in selection["members"]}:
        raise GraphError("共同兼容配置必须包含全部且仅所选成员")
    members = []
    for member in selection["members"]:
        instance = member["instance"]
        parameters = instance["parameters"] if execution is None else actual[instance["instance_id"]]["actual_parameters"]
        members.append({"instance_id": instance["instance_id"], "instance_hash": content_hash(instance),
                        "parameters_hash": content_hash(parameters)})
    return {"plan_hash": content_hash(selection["confirmed_plan"]),
            "implementation_hash": (selection["confirmed_plan"]["scope"]["parent_implementation_hash"]
                                    if execution is None else execution["implementation_source_ref"]["sha256"]),
            "members": sorted(members, key=lambda item: item["instance_id"])}


def configuration_hash(selection, *, execution=None):
    return content_hash(compatibility_configuration(selection, execution=execution))


def routing_context(root, reasoning, instance, *, task_root=None, artifact=None):
    """显式实例绑定先消解同范围多证据；没有消解时不任选 true 事实。"""
    from .diagnosis_reasoning import fact_state
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    artifact = artifact if artifact is not None else b._artifacts(root)["diagnosis"]
    b._reasoning(root, reasoning, task_root, artifact)
    if not b._same(instance, b._instance(reasoning, instance["instance_id"])):
        raise GraphError("Action 实例快照被替换")
    grouped = {}
    for key, fact in reasoning["facts"].items():
        if b._same(fact["scope"], instance["scope"]):
            grouped.setdefault(fact.get("predicate", key), []).append(key)
    bindings = {}
    for predicate, keys in grouped.items():
        explicit = instance["evidence_bindings"].get(predicate)
        if explicit is not None:
            if explicit not in keys:
                raise GraphError("显式路由证据必须绑定同 predicate 及完整实例范围")
            bindings[predicate] = explicit
        elif len(keys) == 1:
            bindings[predicate] = keys[0]
        else:
            raise GraphError("同范围路由谓词有多份证据，各实例须显式消解绑定")
    for predicate, key in instance["evidence_bindings"].items():
        fact = reasoning["facts"].get(key)
        if fact is None or fact.get("predicate", key) != predicate or not b._same(fact["scope"], instance["scope"]):
            raise GraphError("路由绑定不能借用其他谓词、实例范围或子目标的证据")
    def ancestor(key):
        fact = reasoning["facts"][key]
        if fact["kind"] == "raw" and fact["ref"] is not None:
            return fact["ref"]
        for dependency in fact["derived_from"]:
            found = ancestor(dependency)
            if found is not None:
                return found
        return None
    facts = {}
    for predicate, key in bindings.items():
        fact = reasoning["facts"][key]
        state = fact_state(reasoning, key)
        item = {"state": state, "kind": fact["kind"], "evidence_id": fact["evidence_id"], "ref": deepcopy(fact["ref"])}
        if state != "unknown" and item["ref"] is None:
            ref = ancestor(key)
            if ref is None:
                raise GraphError("已知派生路由事实缺少真实原始来源")
            item.update(evidence_id=key, ref=deepcopy(ref))
        facts[predicate] = item
    return {"schema_version": "aprof.evidence/v1", "task_id": reasoning["task_id"],
            "source_context_ref": deepcopy(reasoning["source_context_ref"]),
            "attributes": deepcopy(reasoning["context_snapshot"]["attributes"]), "facts": facts}


def route_parallel(root, reasoning, instance_id, hint, *, task_root=None, artifacts=None, routing_config=None):
    root = Path(root)
    artifacts, config = b._routing_inputs(root, artifacts=artifacts, routing_config=routing_config)
    instance = b._instance(reasoning, instance_id)
    b._hint(config, instance, hint)
    context = routing_context(root, reasoning, instance, task_root=task_root, artifact=artifacts["diagnosis"])
    return b.route_candidates(artifacts["parallel-planning"], context, hint["parallel-planning"])


def _context(root, reasoning, instance, selection, task_root, artifact):
    # 当前事实来自原始 reasoning；共同计划只产生明确的 plan_freedom 声明。
    context = routing_context(root, reasoning, instance, task_root=task_root, artifact=artifact)
    plan = selection["confirmed_plan"]
    if not b._same(b._json_file(b._file(task_root, selection["confirmed_plan_ref"])), plan):
        raise GraphError("confirmed_plan_ref 必须指向共同计划的实际完整文件")
    platform = context["attributes"].get("platform")
    arch = plan["architecture_profile"]["npu_arch"]
    if arch is not None and platform != f"dav-{arch}":
        raise GraphError("共同计划架构与 Context platform 不一致或未知")
    freedom = plan["implementation_freedom"]
    context["facts"]["constraint.plan_freedom"] = {
        "state": bool(freedom["dimensions"] or freedom["parameter_domains"]),
        "kind": "confirmed_plan", "evidence_id": "confirmed-plan-freedom",
        "ref": {**deepcopy(selection["confirmed_plan_ref"]), "locator": "implementation_freedom"}}
    return context


def route_optimization(root: Path, reasoning: dict, selection: dict, *, task_root=None,
                       artifacts=None, routing_config=None) -> dict:
    """逐成员真实路由，不合并 hint，不把前置步骤的期望效果变成事实。"""
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    _part(root, "selection", selection)
    artifacts, config = b._routing_inputs(root, artifacts=artifacts, routing_config=routing_config)
    if selection["routing_config_hash"] != content_hash(config):
        raise GraphError("共同计划的 routing config 身份不匹配")
    _plan(root, selection["confirmed_plan"], reasoning, selection["members"], hard=False)
    routes = []
    for member in selection["members"]:
        instance = b._instance(reasoning, member["instance"]["instance_id"])
        if not b._same(instance, member["instance"]) or member["instance_hash"] != content_hash(instance):
            raise GraphError("成员实例或参数/目标被替换")
        b._hint(config, instance, member["routing_hint"])
        context = _context(root, reasoning, instance, selection, task_root, artifacts["diagnosis"])
        routes.append({"instance_id": instance["instance_id"], "instance_hash": content_hash(instance),
                       "route": b.route_candidates(artifacts["optimization"], context, member["routing_hint"]["optimization"])})
    return {"schema_version": "aprof.scheme-optimization-routes/v1", "scheme_id": selection["scheme_id"],
            "selection_hash": content_hash(selection), "members": routes}


def _joint(reasoning, rows, selection, ids, *, hard, execution=None):
    plan = selection["confirmed_plan"]
    dimensions = {row["dimension"] for row in rows}
    if not JOINT_DIMENSIONS <= dimensions or len(rows) != len(dimensions):
        raise GraphError("共同兼容性须分别比较 owner、通路、布局、同步、workspace、数值及生命周期资源")
    missing = []
    for row in rows:
        if row["plan_hash"] != content_hash(plan) or row["configuration_hash"] != configuration_hash(selection, execution=execution):
            raise GraphError("共同兼容性未绑定本次实例、实际参数、源码和共同计划配置")
        if set(row["member_instance_ids"]) != set(ids):
            raise GraphError("共同兼容性必须覆盖所有成员，不能只拼接各自合法性")
        missing += b._compatibility(reasoning, row, plan["scope"], hard=hard)
    return missing


def _resources(root, selection, task_root):
    """半开生命周期 [start,end) 按 group/memory 计算峰值。

    group 是现有 dispatch 的互斥 workload 域（select_dispatch 唯一选组），
    不能用不同 group 表示同次 launch 的并发阶段来绕开容量。一个域内
    全部成员/阶段统一登记，物理共享 allocation 只登记一次。
    """
    plan = selection["confirmed_plan"]
    ids = {m["instance"]["instance_id"] for m in selection["members"]}
    groups = {g["group_id"]: g for g in plan["parallel_plan"]["groups"]}
    allocation_ids, intervals = set(), {}
    for row in selection["resource_lifetimes"]:
        if row["allocation_id"] in allocation_ids:
            raise GraphError("同一物理 allocation 只登记一次；共享成员在一条记录内列出")
        allocation_ids.add(row["allocation_id"])
        if not set(row["member_instance_ids"]) <= ids or row["group_id"] not in groups:
            raise GraphError("资源生命周期引用未知成员或 group")
        if row["start"] >= row["end"]:
            raise GraphError("资源生命周期必须是非空半开区间")
        b._file(task_root, row["evidence_ref"])
        memory = row["memory"]
        if memory != "workspace" and memory not in plan["architecture_profile"]["memory_bytes"]:
            raise GraphError("资源生命周期引用当前架构未声明的存储")
        intervals.setdefault((row["group_id"], memory), []).append(row)
    peaks = []
    for group_id, group in groups.items():
        declared = {**group["memory_requirements"], "workspace": group["workspace_bytes"]}
        for memory in set(declared) | {m for g, m in intervals if g == group_id}:
            rows = intervals.get((group_id, memory), [])
            times = sorted({t for r in rows for t in (r["start"], r["end"])})
            peak = max((sum(r["bytes"] for r in rows if r["start"] <= t < r["end"]) for t in times), default=0)
            budget = declared.get(memory, 0)
            if peak != budget:
                raise GraphError(f"共同生命周期峰值与计划预算不一致: {group_id}/{memory} peak={peak}, budget={budget}")
            capacity = budget if memory == "workspace" else plan["architecture_profile"]["memory_bytes"][memory]
            if capacity is not None and peak > capacity:
                raise GraphError(f"共同资源同时存活超出容量: {memory}")
            if rows or budget:
                peaks.append({"group_id": group_id, "memory": memory, "peak_bytes": peak,
                              "allocation_ids": sorted(r["allocation_id"] for r in rows)})
    return peaks


def _locator(path, locator):
    match = re.fullmatch(r"lines:([1-9][0-9]*)(?:-([1-9][0-9]*))?", locator)
    try:
        count = len(path.read_text().splitlines())
    except UnicodeError as exc:
        raise GraphError("实施核实必须引用可读源码") from exc
    if match is None or not 1 <= int(match[1]) <= int(match[2] or match[1]) <= count:
        raise GraphError("实际变更/保证核实需要有效源码 lines:N 或 lines:N-M")


def _guarantees(scheme):
    result = {}
    for step in scheme["steps"]:
        for guarantee in step["guarantees"]:
            for target in guarantee["target_instance_ids"]:
                key = (guarantee["id"], target)
                if key in result:
                    raise GraphError("保证 ID 与目标组合不能重复")
                result[key] = (step, guarantee)
    return result


def _checks(task_root, scheme, selection, execution, members):
    """核验最终源码上的保证声明身份，不宣称任意 C++ 推导已由机器证明。"""
    expected, seen, fulfilled = _guarantees(scheme), set(), {}
    source = execution["implementation_source_ref"]
    path = b._file(task_root, source)
    for check in execution["guarantee_checks"]:
        key = (check["guarantee_id"], check["target_instance_id"])
        if key not in expected or key in seen:
            raise GraphError("保证核实必须引用唯一已计划的保证及精确目标实例")
        seen.add(key)
        step, guarantee = expected[key]
        instance = members[check["target_instance_id"]]["instance"]
        actual = next(m for m in execution["members"] if m["instance_id"] == instance["instance_id"])
        if (check["step_id"] != step["id"] or check["predicate"] != guarantee["predicate"] or
            check["expected_state"] is not guarantee["expected_state"] or
            check["instance_hash"] != content_hash(instance) or check["template_hash"] != instance["template_hash"] or
            not b._same(check["scope"], instance["scope"]) or check["parameters_hash"] != content_hash(actual["actual_parameters"]) or
            check["configuration_hash"] != configuration_hash(selection, execution=execution) or
            check["plan_hash"] != content_hash(selection["confirmed_plan"]) or not b._same(check["implementation_ref"], source)):
            raise GraphError("保证核实串用了实例、目标、参数、计划或候选源码身份")
        if check["actual_state"] is not check["expected_state"]:
            raise GraphError("最终源码未核实计划保证（包括 expected=false 的条件）")
        _locator(path, check["source_locator"])
        fulfilled.setdefault(instance["instance_id"], {})[check["predicate"]] = check["expected_state"]
    if seen != set(expected):
        raise GraphError("所有计划保证都必须在最终候选上核实，不能只记录期望效果")
    return fulfilled


def _pending(values, guarantees):
    # 只能用 exact predicate 的已核实保证补 unknown；不把 true/false 反向状态忽略。
    return [value for value in values if value not in guarantees]


def _decision(root, c1, instances, task_root, artifacts, config):
    from .action_decision import validate_handoff_decision
    decision = b._json_file(b._file(task_root, c1["decision_ref"]))
    if decision.get("schema_version") != "aprof.action-decision/v3":
        raise GraphError("handoff/v4 只接受显式 action-decision/v3；禁止混装历史版本")
    from .action_decision_v3 import selected_scheme
    scheme = selected_scheme(decision)
    if scheme is None or scheme["id"] != c1["scheme_id"] or content_hash(scheme) != c1["scheme_hash"]:
        raise GraphError("C1 未精确绑定所选完整方案")
    result = validate_handoff_decision(root, c1, instances, task_root=task_root,
        artifact=artifacts["diagnosis"], implementation=False, artifacts=artifacts, routing_config=config)
    return scheme, result


def validate_chain(root: Path, c1: dict, c2: dict, c3: dict | None = None, *, task_root=None,
                   artifacts=None, routing_config=None) -> dict:
    """沿用交接校验入口；C2 可条件分析，C3 逐实例及共同计划核验。"""
    from .diagnosis_reasoning import action_status
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    chain = [c1, c2] + ([c3] if c3 is not None else [])
    for index, handoff in enumerate(chain):
        validate_schema(root, "knowledge-handoff-v4", handoff)
        if handoff["stage"] != f"C{index + 1}" or handoff["task_id"] != c1["task_id"]:
            raise GraphError("handoff stage/task 不一致")
        if handoff["parent_hash"] != (None if index == 0 else content_hash(chain[index - 1])):
            raise GraphError("handoff parent_hash 不匹配")
        for ref in handoff["artifacts"]:
            b._file(task_root, ref)
    if c1["candidate_id"] is not None or c2["candidate_id"] is not None:
        raise GraphError("C1/C2 为分析与计划，不能预先声明候选")
    artifacts, config = b._routing_inputs(root, artifacts=artifacts, routing_config=routing_config)
    reasoning, selection = c1["reasoning"], c2["selection"]
    members = _members(selection["members"], key="instance_hash")
    members = {m["instance"]["instance_id"]: m for m in members.values()}
    if len(members) != len(selection["members"]):
        raise GraphError("方案成员实例 ID 重复")
    scheme, decision = _decision(root, c1, list(members), task_root, artifacts, config)
    scheme_ids = [m["action_instance_id"] for m in scheme["members"]]
    if set(scheme_ids) != set(members) or len(scheme_ids) != len(members):
        raise GraphError("C2 成员必须精确覆盖方案，不能少选或额外拼接 Action")
    if (selection["scheme_id"] != c1["scheme_id"] or selection["scheme_hash"] != c1["scheme_hash"] or
            selection["routing_config_hash"] != content_hash(config)):
        raise GraphError("共同计划替换了方案或 routing 身份")
    statuses, p_routes, missing = {}, {}, []
    p_nodes = {r["id"]: r for r in artifacts["parallel-planning"]["records"]}
    p_mode = selection["parallel"]["mode"]
    for identifier, member in members.items():
        instance = b._instance(reasoning, identifier)
        if not b._same(instance, member["instance"]) or member["instance_hash"] != content_hash(instance):
            raise GraphError("C2 串实例、目标、参数或模板身份")
        b._hint(config, instance, member["routing_hint"])
        context = routing_context(root, reasoning, instance, task_root=task_root, artifact=artifacts["diagnosis"])
        status = statuses[identifier] = action_status(root, reasoning, instance, artifact=artifacts["diagnosis"])
        if status["failed"]:
            raise GraphError("Action 已知硬前提相反，不能用计划保证覆盖: " + ", ".join(status["failed"]))
        missing.extend(status["missing"])
        trace = p_routes[identifier] = b.route_candidates(artifacts["parallel-planning"], context, member["routing_hint"]["parallel-planning"])
        if not b._same(trace, member["parallel_route"]):
            raise GraphError("成员 P route 不是自身作用域上的真实内部路由")
        choice = member["parallel"]
        if p_mode == "KEEP" and choice["mode"] != "KEEP":
            raise GraphError("共同 P_KEEP 不能藏有成员 P_CHANGE")
        missing += b._chosen(trace, [] if choice["entry_id"] is None else [choice["entry_id"]], choice["mode"], p_nodes, hard=False)
        if (member["compatibility"]["instance_hash"] != content_hash(instance) or
                member["compatibility"]["plan_hash"] != content_hash(selection["confirmed_plan"]) or
                member["compatibility"]["parameters_hash"] != content_hash(instance["parameters"]) or
                member["compatibility"]["implementation_hash"] != instance["scope"]["parent_implementation_hash"]):
            raise GraphError("成员兼容性未绑定精确实例和共同计划")
        missing += b._compatibility(reasoning, member["compatibility"], instance["scope"], hard=c3 is not None)
    if p_mode == "CHANGE" and not any(m["parallel"]["mode"] == "CHANGE" for m in members.values()):
        raise GraphError("共同 P_CHANGE 须记录至少一个实际规划选择")
    parent = selection["parent_plan"]
    if parent is None:
        if p_mode == "KEEP" or any(m["instance"]["parent_plan_hash"] is not None for m in members.values()):
            raise GraphError("P_KEEP 需要覆盖全体成员的完整有效父计划")
    else:
        _plan(root, parent, reasoning, selection["members"], hard=p_mode == "KEEP")
        if any(m["instance"]["parent_plan_hash"] != content_hash(parent) for m in members.values()):
            raise GraphError("成员必须绑定同一完整父计划")
    missing += _plan(root, selection["confirmed_plan"], reasoning, selection["members"], hard=p_mode == "KEEP" or c3 is not None)
    if not b._same(b._json_file(b._file(task_root, selection["confirmed_plan_ref"])), selection["confirmed_plan"]):
        raise GraphError("共同 confirmed_plan_ref 内容不符")
    if p_mode == "KEEP" and not b._same(parent, selection["confirmed_plan"]):
        raise GraphError("P_KEEP 必须保留全域计划及其许可自由度")
    missing += _joint(reasoning, selection["joint_compatibility"], selection, members, hard=c3 is not None)
    peaks = _resources(root, selection, task_root)
    if decision:
        missing += (decision.get("missing_safety", []) + decision.get("failed_safety", []) +
                    decision.get("pending_required_evidence", []) + decision.get("missing_workload_mapping", []))
        if decision["selection_mode"] != "experiment":
            missing.append("action_decision." + decision["selection_mode"])
    result = {"schema_version": "aprof.handoff-chain-validation/v2", "task_id": c1["task_id"],
        "scheme_id": c1["scheme_id"], "scheme_hash": c1["scheme_hash"], "member_instance_ids": list(members),
        "status": "conditional" if missing else "ready", "missing": sorted(set(missing)),
        "handoff_hashes": [content_hash(h) for h in chain], "resource_peaks": peaks,
        "causal_claim": False, "legacy_episode_eligible": False}
    if c3 is None:
        return result
    if decision is None or decision["selection_mode"] != "experiment":
        raise GraphError("C3 需要明确选择可实施试验，条件分析不能自动授权候选")
    if decision.get("missing_workload_mapping"):
        raise GraphError("C3 缺少测前冻结的完整 workload case payload 映射；计划保证不能补填首次选择身份")
    execution = c3["execution"]
    if (execution["scheme_id"] != c1["scheme_id"] or execution["scheme_hash"] != c1["scheme_hash"] or
            execution["selection_hash"] != content_hash(selection)):
        raise GraphError("C3 替换了方案或共同计划")
    actual_members = _members(execution["members"], key="instance_id")
    if set(actual_members) != set(members):
        raise GraphError("C3 必须报告全部且仅所选方案成员")
    fulfilled = _checks(task_root, scheme, selection, execution, members)
    readiness = {row["instance_id"]: row for row in (decision or {}).get("member_readiness", [])}
    routes = {m["instance_id"]: m["route"] for m in route_optimization(root, reasoning, selection,
        task_root=task_root, artifacts=artifacts, routing_config=config)["members"]}
    o_nodes = {r["id"]: r for r in artifacts["optimization"]["records"]}
    source_ref = execution["implementation_source_ref"]
    source_path = b._file(task_root, source_ref)
    any_change = p_mode == "CHANGE"
    plan = selection["confirmed_plan"]
    domains = {d["name"]: d for d in plan["implementation_freedom"]["parameter_domains"]}
    snapshots = []
    actually_executed = set()
    from .action_decision import condition_policy
    _, policies = condition_policy(root, artifacts["diagnosis"])
    for identifier, actual in actual_members.items():
        member, guaranteed = members[identifier], fulfilled.get(identifier, {})
        instance = member["instance"]
        if actual["instance_hash"] != member["instance_hash"]:
            raise GraphError("C3 借用了其他 Action 实例的就绪证据")
        required = list(statuses[identifier]["missing"])
        row = readiness.get(identifier, {})
        if row.get("failed_safety"):
            raise GraphError("C3 Action 实施条件存在已知反证")
        required += row.get("missing_safety", []) + row.get("pending_required_evidence", [])
        template = next(r for r in artifacts["diagnosis"]["records"] if r["id"] == instance["action_id"])
        expected_conditions = {condition["fact"]: condition["state"] for condition in template["preconditions"]}
        expected_conditions.update({condition["fact"]: condition["state"] for condition in policies[instance["action_id"]]["safety_conditions"]})
        if any(predicate in guaranteed and predicate in expected_conditions and guaranteed[predicate] is not expected_conditions[predicate]
               for predicate in required):
            raise GraphError("最终保证与 Action 硬前提的期望 bool 不一致")
        if _pending(required, guaranteed):
            raise GraphError("C3 原始硬前提或必需实施证据仍未知: " + ", ".join(_pending(required, guaranteed)))
        trace = routes[identifier]
        if not b._same(trace, actual["optimization_route"]):
            raise GraphError("成员 O route 被伪造或借用了其他实例/计划")
        mode, entries = actual["optimization"]["mode"], actual["optimization"]["entry_ids"]
        unknown = b._chosen(trace, entries, mode, o_nodes, hard=False)
        if _pending(unknown, {p: state for p, state in guaranteed.items() if state is True}):
            raise GraphError("实际 O 的路由前提未满足，计划保证不能替代核实")
        choice = member["parallel"]
        p_unknown = b._chosen(p_routes[identifier], [] if choice["entry_id"] is None else [choice["entry_id"]], choice["mode"], p_nodes, hard=False)
        if _pending(p_unknown, {p: state for p, state in guaranteed.items() if state is True}):
            raise GraphError("实际 P 的路由前提未满足")
        if (actual["compatibility"]["instance_hash"] != content_hash(instance) or
                actual["compatibility"]["plan_hash"] != content_hash(plan) or
                actual["compatibility"]["parameters_hash"] != content_hash(actual["actual_parameters"]) or
                actual["compatibility"]["implementation_hash"] != execution["implementation_source_ref"]["sha256"]):
            raise GraphError("实际成员兼容性串用了其他实例或计划")
        b._compatibility(reasoning, actual["compatibility"], instance["scope"], hard=True)
        params = actual["actual_parameters"]
        if set(params) != set(instance["parameters"]):
            raise GraphError("replanning_required: 成员实际参数缺失或增项")
        for key, value in params.items():
            domain = domains.get(f"{identifier}.{key}", domains.get(key))
            if not b._same(value, instance["parameters"][key]) and (domain is None or not b._domain(value, domain)):
                raise GraphError("replanning_required: 成员参数超出共同计划许可")
        for change in actual["actual_changes"]:
            if change["target_id"] not in instance["scope"]["target_ids"]:
                raise GraphError("成员实际变化作用于其他目标")
            _locator(source_path, change["source_locator"])
        member_change = mode == "CHANGE" or choice["mode"] == "CHANGE"
        if member_change and not actual["actual_changes"]:
            raise GraphError("非 KEEP 成员须记录最终源码中的实际实施变化")
        if member_change or (p_mode == "CHANGE" and actual["actual_changes"]):
            actually_executed.add(identifier)
        any_change |= member_change
        snapshots.append({"instance_id": identifier, "instance_hash": member["instance_hash"],
            "action_id": instance["action_id"], "template_hash": instance["template_hash"],
            "scope": deepcopy(instance["scope"]), "targets": deepcopy(instance["targets"]),
            "parallel": deepcopy(choice), "optimization": deepcopy(actual["optimization"]),
            "actual_parameters": deepcopy(params), "actual_changes": deepcopy(actual["actual_changes"]),
            "parallel_snapshot": deepcopy(next(m["snapshot"] for m in p_routes[identifier]["matches"] if m["id"] == choice["entry_id"])) if choice["mode"] == "CHANGE" else deepcopy(plan),
            "optimization_snapshots": [deepcopy(next(m["snapshot"] for m in trace["matches"] if m["id"] == entry)) for entry in entries]})
    _joint(reasoning, execution["joint_compatibility"], selection, members, hard=True, execution=execution)
    _actual_plan(execution, selection, source_ref["sha256"])
    noop = not any_change
    if noop:
        if (execution["result"] != "NOOP" or execution["executed_instances"] or c3["candidate_id"] is not None or
            source_ref["sha256"] != plan["scope"]["parent_implementation_hash"] or execution["changes"] or
            any(a["actual_changes"] or not b._same(a["actual_parameters"], members[i]["instance"]["parameters"]) for i, a in actual_members.items())):
            raise GraphError("全 KEEP 才是 NOOP，不能伪造新候选或实际变更")
    else:
        if (execution["result"] != "implemented" or set(execution["executed_instances"]) != actually_executed or
                not c3["candidate_id"]):
            raise GraphError("实际实施须绑定完整方案成员与统一候选身份")
        if source_ref["sha256"] == plan["scope"]["parent_implementation_hash"]:
            metadata = {"source_hash", "implementation_source_hash", "plan_basis_source_hash",
                        "architecture_profile_ref", "parallel_plan_ref"}
            baseline = selection["parent_plan"] or plan
            before_dispatch = {k: v for k, v in baseline["dispatch_plan"].items() if k not in metadata}
            after_dispatch = {k: v for k, v in execution["dispatch_plan"].items() if k not in metadata}
            if (b._same(before_dispatch, after_dispatch) and
                    all(b._same(a["actual_parameters"], members[i]["instance"]["parameters"]) for i, a in actual_members.items())):
                raise GraphError("未发生源码、分发或参数变化，不能申报 implemented")
    result.update(status="NOOP" if noop else "implemented", missing=[], candidate_id=c3["candidate_id"],
        actual_combination={"scheme_id": c1["scheme_id"], "scheme_hash": c1["scheme_hash"],
            "confirmed_plan_hash": content_hash(plan), "source_hash": source_ref["sha256"], "members": snapshots,
            "joint_compatibility": deepcopy(execution["joint_compatibility"]), "guarantee_checks": deepcopy(execution["guarantee_checks"])})
    return result


def _actual_plan(execution, selection, source):
    from .planning import validate_planning_contract
    plan, dispatch = selection["confirmed_plan"], execution["dispatch_plan"]
    validate_planning_contract("dispatch_plan", dispatch)
    expected = deepcopy(plan["dispatch_plan"])
    expected.update(source_hash=source, implementation_source_hash=source,
                    plan_basis_source_hash=plan["scope"]["parent_implementation_hash"])
    if (dispatch.get("implementation_source_hash") != source or dispatch.get("source_hash") != source or
            dispatch.get("plan_basis_source_hash") != plan["scope"]["parent_implementation_hash"] or
            dispatch.get("architecture_profile_ref") != content_hash(plan["architecture_profile"]) or
            dispatch.get("parallel_plan_ref") != content_hash(plan["parallel_plan"])):
        raise GraphError("实际源码/dispatch/共同计划身份不匹配")
    freedom = plan["implementation_freedom"]
    if not b._same(dispatch, expected) and "dispatch_domain" not in freedom["dimensions"]:
        raise GraphError("replanning_required: dispatch 域超出共同计划许可")
    groups = {g["group_id"] for g in plan["parallel_plan"]["groups"]}
    entries = dispatch.get("declared_workloads") if dispatch.get("mode") == "unkeyed_complete_call" else [*dispatch["entries"], dispatch["fallback"]]
    if dispatch["operator"] != plan["parallel_plan"]["operator"] or any(e["group_id"] not in groups for e in entries):
        raise GraphError("实际 dispatch 引入了未确认 operator/group")
    if any(plan["architecture_profile"]["capabilities"].get(c, {}).get("status") != "supported" for e in entries for c in e.get("required_capabilities", [])):
        raise GraphError("实际 dispatch 引入了未知或不支持 capability")
    before, after = plan["contracts"], execution["actual_contracts"]
    if set(before) != set(after):
        raise GraphError("实际实现必须完整报告共同计划边界")
    changed = {key for key in before if not b._same(before[key], after[key])}
    reported = {row["dimension"]: row for row in execution["changes"]}
    if len(reported) != len(execution["changes"]) or set(reported) != changed:
        raise GraphError("共同计划边界变化须逐项准确申报")
    for key in changed:
        if key not in freedom["dimensions"] or not b._same(reported[key]["before"], before[key]) or not b._same(reported[key]["after"], after[key]):
            raise GraphError(f"replanning_required: {key} 超出共同计划许可")


def link_result_v4(c1, c2, c3, timing, *, task_root=None, timing_ref=None, root=None,
                   artifacts=None, routing_config=None):
    """timing 是 {path,sha256,candidate_id,protocol}；timing_ref 可指定该引用文件路径。

    与已核验完整方案关联统一计时；不产生机制因果结论或旧 episode 奖励。
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    task_root = Path(task_root) if task_root is not None else root
    validation = validate_chain(root, c1, c2, c3, task_root=task_root, artifacts=artifacts, routing_config=routing_config)
    if validation["status"] != "implemented":
        raise GraphError("NOOP 不能关联为新候选的计时结果")
    if (set(timing) != {"path", "sha256", "candidate_id", "protocol"} or timing["candidate_id"] != c3["candidate_id"] or
            timing["protocol"] != "single_role_l2_clean_task_v1"):
        raise GraphError("需要相同方案候选的统一计时引用")
    timing_base = Path(timing_ref).resolve().parent if timing_ref is not None else task_root
    measured_path = Path(timing["path"])
    if not measured_path.is_absolute():
        measured_path = timing_base / measured_path
    if not measured_path.is_file() or file_hash(measured_path) != timing["sha256"]:
        raise GraphError("计时结果引用 hash 不匹配")
    measured = b._json_file(measured_path)
    validate_schema(root, "unified-timing-result", measured)
    if measured["decision_hash"] != content_hash({k: v for k, v in measured.items() if k != "decision_hash"}):
        raise GraphError("统一计时结果 decision_hash 不匹配")
    if (measured.get("kind") != "unified_timing_result" or measured.get("candidate_id") != timing["candidate_id"] or
            measured.get("protocol") != timing["protocol"] or measured.get("task_id", c1["task_id"]) != c1["task_id"]):
        raise GraphError("计时结果与任务、候选或协议不一致")
    request_ref = measured.get("request")
    if not isinstance(request_ref, dict) or set(request_ref) != {"path", "sha256"}:
        raise GraphError("计时结果须绑定真实统一计时请求")
    request_path = Path(request_ref["path"])
    if not request_path.is_absolute():
        request_path = measured_path.parent / request_path
    if not request_path.is_file() or file_hash(request_path) != request_ref["sha256"]:
        raise GraphError("计时请求 hash 不匹配")
    request = b._json_file(request_path)
    validate_schema(root, "unified-timing-request", request)
    if (request.get("candidate_id") != c3["candidate_id"] or request.get("protocol") != timing["protocol"] or
            request["operator"] != measured["operator"] or request["operator"] != c2["selection"]["confirmed_plan"]["parallel_plan"]["operator"] or
            request.get("candidate_source_sha256") != c3["execution"]["implementation_source_ref"]["sha256"] or
            request.get("baseline_source_sha256") != c1["reasoning"]["current"]["implementation_ref"]["sha256"]):
        raise GraphError("计时请求与实际方案源码、父本或候选不匹配")
    return {"schema_version": "aprof.knowledge-outcome/v3", "task_id": c1["task_id"],
        "candidate_id": c3["candidate_id"], "scheme_id": c1["scheme_id"], "scheme_hash": c1["scheme_hash"],
        "context_hash": c1["reasoning"]["context_hash"], "knowledge_hash": c1["reasoning"]["knowledge_hash"],
        "workload_ref": deepcopy(c1["reasoning"]["current"]["workload_ref"]),
        "routing_config_hash": c2["selection"]["routing_config_hash"],
        "handoff_hashes": validation["handoff_hashes"],
        "recommended_actions": sorted({instance["action_id"] for instance in c1["reasoning"]["action_instances"]}),
        "selected_instances": [m["instance"]["instance_id"] for m in c2["selection"]["members"]],
        "selected_actions": [m["instance"]["action_id"] for m in c2["selection"]["members"]],
        "executed_instances": deepcopy(c3["execution"]["executed_instances"]),
        "executed_actions": [m["instance"]["action_id"] for m in c2["selection"]["members"]
                             if m["instance"]["instance_id"] in c3["execution"]["executed_instances"]],
        "actual_combination": validation["actual_combination"], "timing_result": deepcopy(timing),
        "attribution": "scheme_level", "causal_claim": False, "legacy_episode_eligible": False}

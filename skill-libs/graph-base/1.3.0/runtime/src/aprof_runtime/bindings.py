"""作用域 Action → P 路由 → 已确认计划 → O 路由；只验证声明与来源。"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .errors import GraphError
from .jsonio import canonical_json, content_hash, file_hash
from .knowledge import REGIONS, artifact_path as tree_artifact_path, digest, local, route_tree, validate_artifact as validate_tree_artifact, validate_schema, verify as verify_tree

CONFIG = "workflows/references/action-routing.json"
OWNERS = ("parallel-planning", "optimization")
ROUTING_SNAPSHOTS = "workflows/references/action-routing-snapshots"
CONTRACTS = {"algorithm", "task_partition", "ownership", "reduction", "synchronization",
             "workspace_ownership", "fusion_boundary", "data_path", "dispatch_domain"}


def _artifacts(root):
    from .diagnosis import verify
    return {"diagnosis": verify(root), **{owner: verify_tree(root, owner) for owner in OWNERS}}


def _same(left, right):
    """JSON快照身份保留bool/int/float类型，不使用Python的True == 1。"""
    return canonical_json(left) == canonical_json(right)


def _json_file(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise GraphError(f"无法读取JSON: {path}") from exc


def _base_path(owner, version):
    filename = "graph.json" if owner == "diagnosis" else "index.json"
    return f"{REGIONS[owner]}/versions/{version}/{filename}"


def _immutable_bytes(root, name, raw):
    path = local(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise GraphError(f"不可变快照不能覆盖不同字节: {name}")
    return path


def routing_snapshot_ref(root: Path, config: dict) -> dict:
    """配置规范JSON内容hash决定文件名；ref.sha256始终为实际文件SHA。"""
    root = Path(root)
    name = f"{ROUTING_SNAPSHOTS}/{content_hash(config).removeprefix('sha256:')}.json"
    path = local(root, name)
    if not path.is_file() or not _same(_json_file(path), config):
        raise GraphError("routing配置尚未冻结或快照内容不同")
    return {"path": name, "sha256": file_hash(path)}


def freeze_bases(root: Path) -> dict:
    """显式归档当前三棵知识与配置；已有版本/内容地址绝不覆盖不同字节。"""
    from .diagnosis import artifact_path as diagnosis_artifact_path
    root = Path(root)
    config = _json_file(root / CONFIG)
    artifacts = _artifacts(root)
    bases = {}
    for owner, artifact in artifacts.items():
        name = _base_path(owner, artifact["version"])
        source = diagnosis_artifact_path(root) if owner == "diagnosis" else tree_artifact_path(root, owner)
        path = _immutable_bytes(root, name, source.read_bytes())
        bases[owner] = {"version": artifact["version"], "sha256": content_hash(artifact),
                        "path": name, "file_sha256": file_hash(path)}
    config["bases"] = bases
    load_routing(root, artifacts=artifacts, routing_config=config)
    raw = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode()
    name = f"{ROUTING_SNAPSHOTS}/{content_hash(config).removeprefix('sha256:')}.json"
    _immutable_bytes(root, name, raw)
    (root / CONFIG).write_bytes(raw)
    return config


def _frozen_artifacts(root, config):
    from .diagnosis import verify_snapshot
    artifacts = {}
    for owner, base in config["bases"].items():
        if base["path"] != _base_path(owner, base["version"]):
            raise GraphError("routing base必须引用owner/version对应的不可变文件")
        path = _file(root, {"path": base["path"], "sha256": base["file_sha256"]})
        artifact = verify_snapshot(root, path) if owner == "diagnosis" else validate_tree_artifact(_json_file(path))
        if artifact["owner"] != owner:
            raise GraphError("routing frozen base owner不匹配")
        artifacts[owner] = artifact
    return artifacts


def load_frozen_bundle(root: Path, routing_ref: dict) -> tuple[dict, dict]:
    """回放包内冻结配置及历史三知识快照，不读取latest REGION或重新编译。"""
    root = Path(root)
    config = _json_file(_file(root, routing_ref))
    expected = f"{ROUTING_SNAPSHOTS}/{content_hash(config).removeprefix('sha256:')}.json"
    if routing_ref["path"] != expected:
        raise GraphError("历史routing_ref必须引用内容地址的不可变配置快照")
    return _routing_inputs(root, routing_config=config)


def load_routing(root: Path, *, artifacts=None, routing_config=None) -> dict:
    """默认校验当前知识；显式bundle只校验该冻结版本，绝不改绑latest。"""
    return _routing_inputs(Path(root), artifacts=artifacts, routing_config=routing_config)[1]


def _validate_frozen_sources(root, artifact):
    """只回放固定raw来源，不读取可能已换版的活跃Markdown/REGION。"""
    checked = set()
    for record in artifact["records"]:
        for source in record["sources"]:
            identity = (source["path"], source["sha256"], tuple(source["lines"]), source["excerpt_sha256"])
            if identity in checked:
                continue
            raw = _file(root, {"path": source["path"], "sha256": source["sha256"]}).read_bytes()
            try:
                lines = raw.decode().splitlines(keepends=True)
            except UnicodeError as exc:
                raise GraphError(f"冻结来源不是可读UTF-8: {source['path']}") from exc
            start, end = source["lines"]
            if not 1 <= start <= end <= len(lines):
                raise GraphError(f"冻结来源lines越界: {source['path']}")
            if digest("".join(lines[start - 1:end]).encode()) != source["excerpt_sha256"]:
                raise GraphError(f"冻结来源摘录hash不匹配: {source['path']}")
            checked.add(identity)


def _routing_inputs(root, *, artifacts=None, routing_config=None):
    config = _json_file(root / CONFIG) if routing_config is None else deepcopy(routing_config)
    validate_schema(root, "action-routing", config)
    if artifacts is None:
        artifacts = _artifacts(root) if routing_config is None else _frozen_artifacts(root, config)
    if set(artifacts) != {"diagnosis", *OWNERS}:
        raise GraphError("routing bundle必须包含三个owner的确切快照")
    from .diagnosis import validate_artifact
    validate_artifact(artifacts["diagnosis"], root)
    for owner in OWNERS:
        validate_tree_artifact(artifacts[owner])
        _validate_frozen_sources(root, artifacts[owner])
    for owner, artifact in artifacts.items():
        base = config["bases"][owner]
        if base["path"] != _base_path(owner, base["version"]):
            raise GraphError("routing base必须引用owner/version对应的不可变文件")
        stored = _json_file(_file(root, {"path": base["path"], "sha256": base["file_sha256"]}))
        if (artifact["owner"] != owner or artifact["version"] != base["version"] or
                base["sha256"] != content_hash(artifact) or not _same(stored, artifact)):
            raise GraphError(f"action-routing 的 {owner} 精确快照不匹配")
    actions = {n["id"]: n for n in artifacts["diagnosis"]["records"] if n["kind"] == "action"}
    rows = config["actions"]
    if len({r["action_id"] for r in rows}) != len(rows) or {r["action_id"] for r in rows} != set(actions):
        raise GraphError("action-routing 必须逐项覆盖全部已注册 A，不能注册临时新 A")
    for row in rows:
        for owner, field in (("parallel-planning", "planning_subtrees"), ("optimization", "optimization_subtrees")):
            nodes = {n["id"]: n for n in artifacts[owner]["records"]}
            for ref in row[field]:
                if ref not in nodes or nodes[ref]["status"] != "active" or _fallback(nodes[ref], nodes):
                    raise GraphError(f"无效路由子树: {ref}")
    reviews = config["variant_reviews"]
    if len({r["variant_id"] for r in reviews}) != len(reviews) or any(r["action_id"] not in actions for r in reviews):
        raise GraphError("变体复核缺少唯一身份或引用未注册 A")
    if any(p["proposed_id"] in actions for p in config["proposals"]):
        raise GraphError("pending proposal 不能冒充已注册 A")
    o_nodes = {n["id"]: n for n in artifacts["optimization"]["records"]}
    if any(ref not in o_nodes or o_nodes[ref]["status"] != "active" or o_nodes[ref]["kind"] != "recipe" for ref in config["support_entries"]):
        raise GraphError("support_entries必须引用active配方，不能作为主执行选择")
    for proposal in config["proposals"]:
        if any(ref not in o_nodes or o_nodes[ref]["status"] != "active" for ref in proposal["routing_subtrees"]):
            raise GraphError("pending proposal 的来源路由范围不存在或已失效")
    return artifacts, config


def coverage(root: Path) -> dict:
    artifacts = _artifacts(Path(root))
    config = load_routing(root, artifacts=artifacts)
    reverse = {}
    for owner in OWNERS:
        nodes = {r["id"]: r for r in artifacts[owner]["records"]}
        field = "planning_subtrees" if owner == OWNERS[0] else "optimization_subtrees"
        for identifier, node in nodes.items():
            if node["kind"] == "router":
                continue
            users = [r["action_id"] for r in config["actions"]
                     if _under(identifier, r[field], nodes) and not _fallback(node, nodes)]
            support = identifier in config["support_entries"]
            reverse[identifier] = {"actions": users, "role": "support_only" if support else "candidate_scope" if users else "retrieval_only",
                                   "reason": "精度/边界支持材料不能单独兑现Action。" if support else "范围覆盖仍需真实路由与实例证据；不是执行承诺。" if users else "示例、fallback或尚无已审阅Action意图；不自动绑定。"}
    return {"schema_version": "aprof.action-routing-coverage/v1", "config_hash": content_hash(config),
            "reviewed_actions": len(config["actions"]), "actions": deepcopy(config["actions"]),
            "variant_reviews": deepcopy(config["variant_reviews"]), "proposals": deepcopy(config["proposals"]),
            "entries": reverse, "execution_coverage_claim": False}


def _under(identifier, refs, nodes):
    while identifier is not None:
        if identifier in refs:
            return True
        identifier = nodes[identifier].get("parent")
    return False


def _fallback(node, nodes):
    parent = node.get("parent")
    return parent is not None and any(r["target"] == node["id"] and r["fallback"]
                                      for r in nodes[parent].get("routes", []))


def route_candidates(artifact: dict, context: dict, subtree_refs: list[str]) -> dict:
    """先真实 route_tree 再取子树交集；空 matches 是 unsupported，不能自动转 KEEP。"""
    nodes = {r["id"]: r for r in artifact["records"]}
    if not isinstance(subtree_refs, list) or not subtree_refs or any(not isinstance(ref, str) or ref not in nodes for ref in subtree_refs):
        raise GraphError("路由提示引用不存在的稳定子树")
    trace = route_tree(artifact, context)
    trace["matches"] = [m for m in trace["matches"] if _under(m["id"], subtree_refs, nodes)]
    return trace


def _file(task_root, ref):
    path = local(task_root, ref["path"])
    if not path.is_file() or file_hash(path) != ref["sha256"]:
        raise GraphError(f"任务证据文件 hash 不匹配: {ref['path']}")
    return path


def _instance(reasoning, instance_id):
    values = [i for i in reasoning["action_instances"] if i["instance_id"] == instance_id]
    if len(values) != 1:
        raise GraphError("需要唯一且属于 C1 的 action instance_id")
    return values[0]


def _reasoning(root, reasoning, task_root, artifact):
    from .diagnosis_reasoning import validate_reasoning
    validate_reasoning(root, reasoning, artifact=artifact)
    origin = _json_file(_file(task_root, reasoning["source_context_ref"]))
    if origin.get("task_id") != reasoning["task_id"]:
        raise GraphError("source Context 属于其他任务")
    if origin.get("schema_version") == "aprof.evidence/v1":
        from .knowledge import _evidence
        _evidence(origin)
        attrs = origin.get("attributes")
    elif origin.get("schema_version") == "1.0.0":
        from .contracts import Context
        validate_schema(root, "context", origin)
        Context.from_dict(origin)
        attrs = origin.get("evidence", {}).get("routing_attributes")
    else:
        raise GraphError("source Context authority schema未知；只接受evidence/v1或Context1.0.0")
    if not isinstance(attrs, dict) or not _same(attrs, reasoning["context_snapshot"]["attributes"]):
        raise GraphError("routing attributes 必须来自已绑定 Context 的显式投影，不能伪造属性")
    for ref in (reasoning["current"]["implementation_ref"], reasoning["current"]["workload_ref"]):
        _file(task_root, ref)
    for fact in reasoning["facts"].values():
        if fact["kind"] == "raw" and fact["ref"] is not None:
            _file(task_root, fact["ref"])
    if reasoning.get("predecessor_ref") is not None:
        predecessor = json.loads(_file(task_root, reasoning["predecessor_ref"]).read_text())
        validate_reasoning(root, predecessor, artifact=artifact)
        if (predecessor["task_id"] != reasoning["task_id"] or not _same(predecessor["current"], reasoning["current"])):
            raise GraphError("reasoning 后继必须保持任务、实现、workload、对象与范围身份")


def routing_context(root: Path, reasoning: dict, instance: dict, *, task_root=None,
                    confirmed_plan=None, confirmed_plan_ref=None, artifact=None) -> dict:
    """仅投影同一实例范围的已校验证据；计划自由度是明确C2声明。"""
    from .diagnosis_reasoning import fact_state
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    if artifact is None:
        artifact = _artifacts(root)["diagnosis"]
    _reasoning(root, reasoning, task_root, artifact)
    if not _same(instance, _instance(reasoning, instance["instance_id"])):
        raise GraphError("action 实例快照被替换（targets/scope/parameters/parent plan 必须一致）")
    facts = {}
    bindings = {}
    for key, fact in reasoning["facts"].items():
        if not _same(fact["scope"], instance["scope"]):
            continue
        predicate = fact.get("predicate", key)
        if predicate in bindings:
            raise GraphError("同范围路由谓词重复，必须显式消解证据")
        bindings[predicate] = key
    for predicate, identifier in instance["evidence_bindings"].items():
        fact = reasoning["facts"].get(identifier)
        if fact is None or fact.get("predicate", identifier) != predicate:
            raise GraphError("evidence binding 的 predicate 不匹配，不能借任意 true 事实")
        bindings[predicate] = identifier
    for key, identifier in bindings.items():
        fact = reasoning["facts"].get(identifier)
        if fact is None or not _same(fact["scope"], instance["scope"]):
            continue
        state = fact_state(reasoning, identifier)
        item = {"state": state, "kind": fact["kind"], "evidence_id": fact["evidence_id"], "ref": deepcopy(fact["ref"])}
        if state != "unknown" and item["ref"] is None:
            # 保留一个真实原始祖先引用；全部依赖及推导声明仍在冻结的C1中。
            def ancestor(key):
                source = reasoning["facts"][key]
                if source["kind"] == "raw" and source["ref"] is not None:
                    return source["ref"]
                for dependency in source["derived_from"]:
                    found = ancestor(dependency)
                    if found is not None:
                        return found
                return None
            ref = ancestor(identifier)
            if ref is None:
                raise GraphError("已知派生事实没有真实原始证据祖先")
            item.update(evidence_id=identifier, ref=deepcopy(ref))
        facts[key] = item
    if confirmed_plan is not None:
        _plan(root, confirmed_plan, instance["scope"], hard=False)
        if confirmed_plan_ref is None or not _same(_json_file(_file(task_root, confirmed_plan_ref)), confirmed_plan):
            raise GraphError("confirmed_plan_ref必须绑定真实文件且内容等于C2确认计划")
        platform = reasoning["context_snapshot"]["attributes"].get("platform")
        if confirmed_plan["architecture_profile"]["npu_arch"] is not None and platform != f"dav-{confirmed_plan['architecture_profile']['npu_arch']}":
            raise GraphError("confirmed plan 架构与已绑定 Context platform 不一致或未知")
        freedom = confirmed_plan["implementation_freedom"]
        facts["constraint.plan_freedom"] = {"state": bool(freedom["dimensions"] or freedom["parameter_domains"]),
            "kind": "confirmed_plan", "evidence_id": "confirmed-plan-freedom",
            "ref": {**deepcopy(confirmed_plan_ref), "locator": "implementation_freedom"}}
    return {"schema_version": "aprof.evidence/v1", "task_id": reasoning["task_id"],
            "source_context_ref": deepcopy(reasoning["source_context_ref"]),
            "attributes": deepcopy(reasoning["context_snapshot"]["attributes"]), "facts": facts}


def _hint(config, instance, hint):
    validate_schema_hint = {"parallel-planning", "optimization"}
    if not isinstance(hint, dict) or set(hint) != validate_schema_hint:
        raise GraphError("hint 只能含两个 owner 的稳定子树引用；不能含 facts 或 attributes")
    row = next((r for r in config["actions"] if r["action_id"] == instance["action_id"]), None)
    if row is None:
        raise GraphError("临时Problem只能复用已注册A；临时新A不能路由")
    for owner, field in (("parallel-planning", "planning_subtrees"), ("optimization", "optimization_subtrees")):
        if not isinstance(hint[owner], list) or not hint[owner] or any(not isinstance(ref, str) for ref in hint[owner]) or len(set(hint[owner])) != len(hint[owner]):
            raise GraphError("hint 需要非空唯一子树数组")
        if not set(hint[owner]) <= set(row[field]):
            raise GraphError("hint 越出该 A 已审阅的路由范围")


def default_hint(root: Path, action_id: str) -> dict:
    config = load_routing(root)
    row = next((r for r in config["actions"] if r["action_id"] == action_id), None)
    if row is None:
        raise GraphError("未注册 A 不能获得路由提示")
    return {"parallel-planning": deepcopy(row["planning_subtrees"]), "optimization": deepcopy(row["optimization_subtrees"])}


def route_parallel(root: Path, reasoning: dict, instance_id: str, hint: dict, *, task_root=None) -> dict:
    root = Path(root)
    artifacts = _artifacts(root)
    config = load_routing(root, artifacts=artifacts)
    instance = _instance(reasoning, instance_id)
    _hint(config, instance, hint)
    context = routing_context(root, reasoning, instance, task_root=task_root, artifact=artifacts["diagnosis"])
    return route_candidates(artifacts["parallel-planning"], context, hint["parallel-planning"])


def route_optimization(root: Path, reasoning: dict, selection: dict, *, task_root=None,
                       artifacts=None, routing_config=None) -> dict:
    """C3按已确认P检索O；新技术域须形成有依据的Context/reasoning后继。

    已有机制与P正文可复用；这里不能把计划期望写成当前观测属性。
    """
    root = Path(root)
    _part(root, "selection", selection)
    artifacts, config = _routing_inputs(root, artifacts=artifacts, routing_config=routing_config)
    _hint(config, selection["instance"], selection["routing_hint"])
    if selection["routing_config_hash"] != content_hash(config):
        raise GraphError("C2 routing config hash 不匹配")
    context = routing_context(root, reasoning, selection["instance"], task_root=task_root,
                              confirmed_plan=selection["confirmed_plan"], confirmed_plan_ref=selection["confirmed_plan_ref"], artifact=artifacts["diagnosis"])
    return route_candidates(artifacts["optimization"], context, selection["routing_hint"]["optimization"])


def _part(root, key, value):
    schema = json.loads((root / "schemas/knowledge-handoff-v3.schema.json").read_text())
    part = {"$ref": "#/$defs/" + key, "$defs": schema["$defs"]}
    errors = list(Draft202012Validator(part).iter_errors(value))
    if errors:
        raise GraphError(f"{key}: {errors[0].json_path}: {errors[0].message}")


def _plan(root, plan, scope, *, hard=True):
    from .planning import validate_planning_contract
    _part(root, "plan_bundle", plan)
    if not _same(plan["scope"], scope):
        raise GraphError("计划 scope 与 action 实例不一致")
    architecture, parallel, dispatch = (plan[k] for k in ("architecture_profile", "parallel_plan", "dispatch_plan"))
    for kind, value in (("architecture-profile", architecture), ("parallel-plan", parallel), ("dispatch-plan", dispatch)):
        validate_planning_contract(kind.replace("-", "_"), value)
    missing = []
    if architecture["architecture_id"] == "unknown" or architecture["npu_arch"] is None or not any(architecture["core_counts"].values()):
        missing.append("architecture_profile.target_capabilities")
    for group in parallel["groups"]:
        for capability in group["required_capabilities"]:
            if architecture["capabilities"].get(capability, {}).get("status") != "supported":
                status = architecture["capabilities"].get(capability, {}).get("status", "unknown")
                if status == "unsupported":
                    raise GraphError("parallel plan 需要已知不支持 capability")
                missing.append("capability." + capability)
        for memory, amount in group["memory_requirements"].items():
            capacity = architecture["memory_bytes"][memory]
            if amount and capacity is None:
                missing.append("capacity." + memory)
            elif amount and amount > capacity:
                raise GraphError("parallel plan 超出已知 memory capacity")
    if (parallel["source_hash"] != scope["parent_implementation_hash"] or
        parallel["architecture_profile_ref"] != content_hash(architecture) or
        dispatch["architecture_profile_ref"] != content_hash(architecture) or
        dispatch["parallel_plan_ref"] != content_hash(parallel) or
        dispatch["operator"] != parallel["operator"] or dispatch["source_hash"] != parallel["source_hash"]):
        raise GraphError("architecture/parallel/dispatch 的 source 或 plan hash 不匹配")
    groups = {g["group_id"] for g in parallel["groups"]}
    if len(groups) != len(parallel["groups"]):
        raise GraphError("parallel plan group_id 重复")
    entries = dispatch.get("declared_workloads") if dispatch.get("mode") == "unkeyed_complete_call" else [*dispatch["entries"], dispatch["fallback"]]
    for entry in entries:
        for capability in entry.get("required_capabilities", []):
            status = architecture["capabilities"].get(capability, {}).get("status", "unknown")
            if status == "unsupported":
                raise GraphError("dispatch 需要已知不支持 capability")
            if status != "supported":
                missing.append("capability." + capability)
    if not entries or any(e["group_id"] not in groups for e in entries):
        raise GraphError("dispatch 引用未知 group 或空计划")
    if not CONTRACTS <= set(plan["contracts"]):
        raise GraphError("计划必须冻结全部算法/owner/同步/数据通路边界")
    domains = plan["implementation_freedom"]["parameter_domains"]
    if len({d["name"] for d in domains}) != len(domains):
        raise GraphError("参数自由度重名")
    for domain in domains:
        if len(domain) == 1 or ("minimum" in domain and "maximum" in domain and domain["minimum"] > domain["maximum"]):
            raise GraphError("参数自由度必须有有效范围")
    if hard and missing:
        raise GraphError("有效计划硬门禁尚缺: " + ", ".join(sorted(set(missing))))
    return missing


def _chosen(trace, identifiers, mode, nodes, *, hard):
    if mode == "KEEP":
        if identifiers:
            raise GraphError("KEEP 不能借用非空/fallback条目作为 identity")
        return []
    if not identifiers:
        raise GraphError("空匹配/unsupported 不能冒充 KEEP 或 CHANGE")
    entries = {m["id"]: m for m in trace["matches"]}
    missing = []
    for identifier in identifiers:
        match = entries.get(identifier)
        if (match is None or nodes[identifier]["status"] != "active" or
            nodes[identifier]["kind"] not in {"template", "strategy", "recipe"} or _fallback(nodes[identifier], nodes)):
            raise GraphError("实际选择不是合法已路由的变换，或试图把 fallback 当 KEEP")
        missing.extend(match["missing"])
    if hard and missing:
        raise GraphError("C3 recipe/plan 所需证据未知: " + ", ".join(sorted(set(missing))))
    return missing


def _compatibility(reasoning, binding, scope, *, hard):
    from .diagnosis_reasoning import fact_state
    missing = []
    if not binding["fact_bindings"]:
        missing.append("explicit_action_plan_compatibility")
    for identifier in binding["fact_bindings"]:
        fact = reasoning["facts"].get(identifier)
        if fact is None or not _same(fact["scope"], scope):
            raise GraphError("兼容性证据不存在或跨作用域")
        state = fact_state(reasoning, identifier)
        if state is False:
            raise GraphError("实际组合的兼容性证据为 false")
        if state is not True:
            missing.append(identifier)
    if hard and missing:
        raise GraphError("C3 缺少组合兼容性证据: " + ", ".join(missing))
    return missing


def _domain(value, domain):
    if "values" in domain and not any(_same(value, option) for option in domain["values"]):
        return False
    if "minimum" in domain or "maximum" in domain:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if "minimum" in domain and value < domain["minimum"] or "maximum" in domain and value > domain["maximum"]:
            return False
    return True


def validate_chain(root: Path, c1: dict, c2: dict, c3: dict | None = None, *, task_root=None,
                   artifacts=None, routing_config=None) -> dict:
    """实施前/交接时同一门禁，不需要 timing；C2 不选 O 配方。"""
    from .diagnosis_reasoning import action_status
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    chain = [c1, c2] + ([c3] if c3 is not None else [])
    for index, item in enumerate(chain):
        validate_schema(root, "knowledge-handoff-v3", item)
        if item["stage"] != f"C{index + 1}" or item["task_id"] != c1["task_id"]:
            raise GraphError("handoff stage 或 task 身份不一致")
        if item["parent_hash"] != (None if index == 0 else content_hash(chain[index - 1])):
            raise GraphError("handoff parent_hash 不匹配")
        for ref in item["artifacts"]:
            _file(task_root, ref)
    artifacts, config = _routing_inputs(root, artifacts=artifacts, routing_config=routing_config)
    reasoning, selection = c1["reasoning"], c2["selection"]
    instance = _instance(reasoning, selection["instance"]["instance_id"])
    if (not _same(selection["instance"], instance) or selection["instance_hash"] != content_hash(instance) or
            selection["routing_config_hash"] != content_hash(config) or reasoning["task_id"] != c1["task_id"]):
        raise GraphError("C2 串实例或配置身份不匹配")
    _hint(config, instance, selection["routing_hint"])
    context = routing_context(root, reasoning, instance, task_root=task_root, artifact=artifacts["diagnosis"])
    status = action_status(root, reasoning, instance, artifact=artifacts["diagnosis"])
    if status["status"] == "blocked":
        raise GraphError("A 原始硬前提不满足: " + ", ".join(status["failed"]))
    if c2["candidate_id"] is not None or c1["candidate_id"] is not None:
        raise GraphError("C1/C2 是分析/计划，candidate_id 必须为 null")
    p_mode, p_entry = selection["parallel"]["mode"], selection["parallel"]["entry_id"]
    parent_plan = selection["parent_plan"]
    if parent_plan is None:
        if instance["parent_plan_hash"] is not None or p_mode == "KEEP":
            raise GraphError("P_KEEP 需要完整有效父计划，首次规划必须 P_CHANGE")
    else:
        _plan(root, parent_plan, instance["scope"], hard=p_mode == "KEEP")
        if instance["parent_plan_hash"] != content_hash(parent_plan):
            raise GraphError("action 实例绑定了其他 parent plan")
    plan_missing = _plan(root, selection["confirmed_plan"], instance["scope"], hard=p_mode == "KEEP" or c3 is not None)
    if not _same(_json_file(_file(task_root, selection["confirmed_plan_ref"])), selection["confirmed_plan"]):
        raise GraphError("confirmed_plan_ref真实JSON与C2确认计划不同")
    if p_mode == "KEEP" and not _same(selection["parent_plan"], selection["confirmed_plan"]):
        raise GraphError("P_KEEP 必须保持完整有效计划及原有自由度")
    actual_p = route_candidates(artifacts["parallel-planning"], context, selection["routing_hint"]["parallel-planning"])
    if not _same(selection["parallel_route"], actual_p):
        raise GraphError("P route 不是同一作用域权威事实上的真实路由")
    p_nodes = {r["id"]: r for r in artifacts["parallel-planning"]["records"]}
    missing = status["missing"] + plan_missing + _chosen(actual_p, [] if p_entry is None else [p_entry], p_mode, p_nodes, hard=c3 is not None)
    missing += _compatibility(reasoning, selection["compatibility"], instance["scope"], hard=c3 is not None)
    result = {"schema_version": "aprof.handoff-chain-validation/v1", "task_id": c1["task_id"],
              "instance_id": instance["instance_id"], "status": "conditional" if missing else "ready",
              "missing": sorted(set(missing)), "handoff_hashes": [content_hash(c) for c in chain],
              "causal_claim": False, "legacy_episode_eligible": False}
    if c3 is None:
        return result
    if status["status"] != "ready":
        raise GraphError("C3 实施前 A 原始硬前提必须全部满足；请形成后继 reasoning/C1/C2")
    execution = c3["execution"]
    if execution["instance_hash"] != selection["instance_hash"] or execution["selection_hash"] != content_hash(selection):
        raise GraphError("C3 串实例或私换 C2 P selection")
    actual_o = route_optimization(root, reasoning, selection, task_root=task_root,
                                  artifacts=artifacts, routing_config=config)
    if not _same(execution["optimization_route"], actual_o):
        raise GraphError("O route 被伪造或借用了不同计划/属性")
    o_mode, o_entries = execution["optimization"]["mode"], execution["optimization"]["entry_ids"]
    o_nodes = {r["id"]: r for r in artifacts["optimization"]["records"]}
    _chosen(actual_o, o_entries, o_mode, o_nodes, hard=True)
    _compatibility(reasoning, execution["compatibility"], instance["scope"], hard=True)
    source = execution["implementation_source_ref"]["sha256"]
    source_path = _file(task_root, execution["implementation_source_ref"])
    source_lines = source_path.read_text().splitlines()
    for change in execution["actual_changes"]:
        if change["target_id"] not in instance["scope"]["target_ids"]:
            raise GraphError("实际局部变更不能作用于其他实例目标")
        match = re.fullmatch(r"lines:([1-9][0-9]*)(?:-([1-9][0-9]*))?", change["source_locator"])
        if match is None or not 1 <= int(match[1]) <= int(match[2] or match[1]) <= len(source_lines):
            raise GraphError("实际变更 source_locator 需要可读源码的有效 lines:N 或 lines:N-M")
    plan = selection["confirmed_plan"]
    dispatch = execution["dispatch_plan"]
    from .planning import validate_planning_contract
    validate_planning_contract("dispatch_plan", dispatch)
    if (dispatch.get("implementation_source_hash") != source or
        dispatch.get("plan_basis_source_hash") != instance["scope"]["parent_implementation_hash"] or
        dispatch["source_hash"] != source or
        dispatch["architecture_profile_ref"] != content_hash(plan["architecture_profile"]) or
        dispatch["parallel_plan_ref"] != content_hash(plan["parallel_plan"])):
        raise GraphError("实际 source/dispatch/plan basis 身份不匹配")
    expected_dispatch = deepcopy(plan["dispatch_plan"])
    expected_dispatch.update(source_hash=source, implementation_source_hash=source,
                             plan_basis_source_hash=instance["scope"]["parent_implementation_hash"])
    groups = {g["group_id"] for g in plan["parallel_plan"]["groups"]}
    actual_entries = dispatch.get("declared_workloads") if dispatch.get("mode") == "unkeyed_complete_call" else [*dispatch["entries"], dispatch["fallback"]]
    if dispatch["operator"] != plan["parallel_plan"]["operator"] or any(e["group_id"] not in groups for e in actual_entries):
        raise GraphError("实际dispatch不能引入其他operator/未确认group")
    if any(plan["architecture_profile"]["capabilities"].get(c, {}).get("status") != "supported"
           for e in actual_entries for c in e.get("required_capabilities", [])):
        raise GraphError("实际dispatch要求未知/未支持capability")
    freedom = plan["implementation_freedom"]
    if not _same(dispatch, expected_dispatch) and "dispatch_domain" not in freedom["dimensions"]:
        raise GraphError("replanning_required: dispatch 域变化超出 C2 自由度")
    contracts = plan["contracts"]
    actual_contracts = execution["actual_contracts"]
    if set(actual_contracts) != set(contracts):
        raise GraphError("actual_contracts 必须完整报告计划边界")
    changed = {k for k in contracts if not _same(contracts[k], actual_contracts[k])}
    reported = {x["dimension"]: x for x in execution["changes"]}
    if set(reported) != changed or len(reported) != len(execution["changes"]):
        raise GraphError("实际边界变化须逐项准确申报")
    for key in changed:
        if key not in freedom["dimensions"] or not _same(reported[key]["before"], contracts[key]) or not _same(reported[key]["after"], actual_contracts[key]):
            raise GraphError(f"replanning_required: {key} 超出 C2 自由度")
    params = execution["actual_parameters"]
    original = instance["parameters"]
    if set(params) != set(original):
        raise GraphError("replanning_required: 实际参数身份缺失或增项")
    domains = {d["name"]: d for d in freedom["parameter_domains"]}
    if any(k not in domains or not _domain(params[k], domains[k]) for k in params if not _same(params[k], original[k])):
        raise GraphError("replanning_required: 参数变化超出 C2 自由度")
    noop = p_mode == o_mode == "KEEP"
    if noop:
        if (execution["result"] != "NOOP" or execution["executed_instances"] or c3["candidate_id"] is not None or
                source != instance["scope"]["parent_implementation_hash"] or changed or not _same(params, original) or execution["actual_changes"] or not _same(dispatch, expected_dispatch)):
            raise GraphError("双 KEEP 必须是 NOOP，不能伪造执行或新候选")
    elif (execution["result"] != "implemented" or not _same(execution["executed_instances"], [instance["instance_id"]]) or not c3["candidate_id"] or not execution["actual_changes"]):
        raise GraphError("实际实施须绑定唯一 action instance 与新候选")
    else:
        # 谱系/plan引用重绑不是执行变化；比较实际分发内容和参数。
        metadata = {"source_hash", "implementation_source_hash", "plan_basis_source_hash",
                    "architecture_profile_ref", "parallel_plan_ref"}
        baseline_plan = selection["parent_plan"] or selection["confirmed_plan"]
        before_dispatch = {k: v for k, v in baseline_plan["dispatch_plan"].items() if k not in metadata}
        after_dispatch = {k: v for k, v in dispatch.items() if k not in metadata}
        if (source == instance["scope"]["parent_implementation_hash"] and
                _same(before_dispatch, after_dispatch) and _same(params, original)):
            raise GraphError("未发生源码、实际分发或参数变化，不能申报implemented；保留NOOP或补充实施")
    result.update(status="NOOP" if noop else "implemented", missing=[], candidate_id=c3["candidate_id"],
                  actual_combination={"instance_hash": content_hash(instance), "parallel": deepcopy(selection["parallel"]),
                                      "optimization": deepcopy(execution["optimization"]),
                                      "confirmed_plan_hash": content_hash(plan), "source_hash": source,
                                      "compatibility": deepcopy(execution["compatibility"]),
                                      "actual_changes": deepcopy(execution["actual_changes"]),
                                      "parallel_snapshot": (deepcopy(next(m["snapshot"] for m in actual_p["matches"] if m["id"] == p_entry)) if p_mode == "CHANGE" else deepcopy(plan)),
                                      "optimization_snapshots": [deepcopy(next(m["snapshot"] for m in actual_o["matches"] if m["id"] == identifier)) for identifier in o_entries]})
    return result

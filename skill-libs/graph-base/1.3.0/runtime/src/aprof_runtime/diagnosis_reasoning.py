"""任务内推理的结构与来源边界校验，不自动形成机制结论或注册新模板。"""
from __future__ import annotations

from pathlib import Path
from contextvars import ContextVar
import json
import math

from .errors import GraphError
from .jsonio import content_hash
from .knowledge import digest, local, validate_schema
from . import diagnosis


def validate_scope(scope: dict, current_scope: dict) -> dict:
    for key in ("task_id", "parent_implementation_hash", "workload_hash", "stage"):
        if scope[key] != current_scope[key]:
            raise GraphError(f"scope 的 {key} 不一致")
    if not scope["target_ids"] or not set(scope["target_ids"]) <= set(current_scope["target_ids"]):
        raise GraphError("scope 必须绑定当前目标，不能跨目标借用")
    return scope


def profile_time_known(fact: dict) -> bool:
    """Whether one fact explicitly identifies a whole artifact or a finite time interval."""
    if not isinstance(fact, dict):
        return False
    span = fact.get("time_range")
    if not isinstance(span, dict):
        return False
    if span.get("kind") == "full_artifact":
        return set(span) == {"kind", "aggregation"} and span["aggregation"] == "all_recorded_samples"
    if span.get("kind") != "interval" or set(span) != {"kind", "start", "end", "unit", "origin"}:
        return False
    return (all(type(span[key]) is int or (type(span[key]) is float and math.isfinite(span[key])) for key in ("start", "end"))
            and span["start"] <= span["end"] and isinstance(span["unit"], str) and span["unit"] in {"ns", "us", "ms", "s", "cycles", "ticks"}
            and isinstance(span["origin"], str) and bool(span["origin"].strip()))


def _profile_fact(key, fact):
    predicate = fact.get("predicate", key)
    return fact.get("view") == "profile" or (isinstance(predicate, str) and predicate.startswith("symptom.profile."))


def fact_state(reasoning: dict, fact_id: str):
    fact = reasoning["facts"].get(fact_id)
    if fact is None or fact["kind"] == "proxy":
        return "unknown"
    if fact["kind"] == "raw" and _profile_fact(fact_id, fact) and not profile_time_known(fact):
        return "unknown"
    if fact.get("components"):
        states = [fact_state(reasoning, key) for key in fact["components"]]
        return False if any(s is False for s in states) else True if all(s is True for s in states) else "unknown"
    return fact["state"]


def _raw_roots(facts, key, active=None):
    active = set() if active is None else active
    if key not in facts or key in active:
        raise GraphError(f"事实依赖不存在或成环: {key}")
    fact = facts[key]
    if fact["kind"] in {"raw", "proxy"}:
        ref = fact["ref"]
        return {(ref["sha256"], ref["locator"])} if ref else set()
    result = set()
    for dependency in fact["derived_from"]:
        result |= _raw_roots(facts, dependency, active | {key})
    return result


def _same_targets(left, right):
    return set(left["target_ids"]) == set(right["target_ids"])


def action_status(root: Path, reasoning: dict, instance: dict, artifact=None) -> dict:
    artifact = artifact if artifact is not None else diagnosis.verify(root)
    action = next((r for r in artifact["records"] if r["id"] == instance["action_id"] and r["kind"] == "action"), None)
    if action is None:
        raise GraphError("动作必须引用已注册 A 模板；临时 Problem 不能创建临时 A")
    if instance["template_hash"] != content_hash(action):
        raise GraphError("Action template_hash 不匹配精确内容快照")
    validate_scope(instance["scope"], reasoning["current"]["scope"])
    missing, failed = [], []
    for condition in action["preconditions"]:
        key = condition["fact"]
        bound = instance["evidence_bindings"].get(key)
        fact = reasoning["facts"].get(bound)
        state = fact_state(reasoning, bound) if bound else "unknown"
        if fact:
            if (bound != key and fact.get("predicate") != key) or ("predicate" in fact and fact["predicate"] != key):
                raise GraphError("动作硬前提 evidence binding 的 predicate 不匹配")
            validate_scope(fact["scope"], instance["scope"])
            if not _same_targets(fact["scope"], instance["scope"]):
                raise GraphError("动作前提证据必须覆盖同一完整目标作用域")
        if state == "unknown":
            missing.append(key)
        elif state is not condition["state"]:
            failed.append(key)
    return {"status": "blocked" if failed else "conditional" if missing else "ready", "missing": sorted(set(missing)), "failed": sorted(set(failed))}


def validate_reasoning(root: Path, reasoning: dict, artifact=None) -> dict:
    root = Path(root)
    validate_schema(root, "diagnosis-reasoning", reasoning)
    artifact = artifact if artifact is not None else diagnosis.verify(root)
    diagnosis.validate_artifact(artifact, root)
    if reasoning["knowledge_hash"] != content_hash(artifact):
        raise GraphError("推理知识快照 hash 不匹配")
    context = reasoning["context_snapshot"]
    if context["task_id"] != reasoning["task_id"] or reasoning["context_hash"] != content_hash(context) or reasoning["source_context_ref"] != context["source_context_ref"]:
        raise GraphError("推理任务/context身份不一致")
    current = reasoning["current"]
    scope = current["scope"]
    if scope["task_id"] != reasoning["task_id"] or scope["parent_implementation_hash"] != current["implementation_ref"]["sha256"] or scope["workload_hash"] != current["workload_ref"]["sha256"]:
        raise GraphError("当前实现/workload 身份必须绑定 scope")
    objects = {o["object_id"]: o for o in current["objects"]}
    if len(objects) != len(current["objects"]) or not scope["target_ids"] or not set(scope["target_ids"]) <= set(objects):
        raise GraphError("当前对象重复或 scope 目标未注册")
    nodes = {r["id"]: r for r in artifact["records"]}
    component_views = {c["id"]: r["view"] for r in artifact["records"] if r["kind"] == "symptom" for c in r["observation"]["required_components"]}
    def declared_view(predicate):
        return nodes.get(predicate, {}).get("view", component_views.get(predicate))
    facts, identities = reasoning["facts"], {}
    for key, fact in facts.items():
        validate_scope(fact["scope"], scope)
        predicate = fact.get("predicate", key)
        expected_view = declared_view(predicate)
        if expected_view is not None and "view" in fact and fact["view"] != expected_view:
            raise GraphError("事实 view 必须与注册 Symptom predicate 一致")
        if fact.get("time_range") is not None and not profile_time_known(fact):
            raise GraphError("事实time_range必须是完整artifact聚合或合法有限非倒置interval")
        is_profile = expected_view == "profile" or _profile_fact(key, fact)
        if fact["kind"] == "raw" and is_profile:
            if expected_view == "profile" and not _profile_fact(key, fact):
                raise GraphError("非标准ID的profile原始事实必须显式声明view=profile")
            if fact["state"] != "unknown" and not profile_time_known(fact):
                raise GraphError("已知profile raw事实缺少时间口径；请将state标unknown或建立补证据后继")
        if fact["kind"] in {"raw", "proxy"}:
            if fact["derived_from"] or fact.get("components"):
                raise GraphError("原始/代理事实不能伪装派生依赖")
            if fact["state"] != "unknown" and (fact["ref"] is None or not fact["evidence_id"]):
                raise GraphError("已知事实必须有 evidence_id 与原始引用")
        else:
            if not fact["derived_from"] or fact["ref"] is not None:
                raise GraphError("派生事实必须引用原始依赖，不能伪装新原始证据")
            if fact.get("components") and not set(fact["components"]) <= set(fact["derived_from"]):
                raise GraphError("复合观察各组件必须属于 derived_from")
            for dependency in fact["derived_from"]:
                if dependency not in facts:
                    raise GraphError(f"派生依赖不存在: {dependency}")
                validate_scope(facts[dependency]["scope"], fact["scope"])
                if not _same_targets(facts[dependency]["scope"], fact["scope"]):
                    raise GraphError("派生事实不能跨目标合并证据")
        if fact["evidence_id"] and fact["ref"]:
            identity = tuple(fact["ref"][k] for k in ("path", "sha256", "locator"))
            if fact["evidence_id"] in identities and identities[fact["evidence_id"]] != identity:
                raise GraphError("同一 evidence_id 绑定了不同原始来源")
            identities[fact["evidence_id"]] = identity
        _raw_roots(facts, key)
    for key, fact in facts.items():
        predicate = fact.get("predicate", key)
        template = nodes.get(predicate, {})
        if template.get("kind") == "symptom" and template["observation"]["required_components"] and fact_state(reasoning, key) != "unknown":
            expected = {c["id"] for c in template["observation"]["required_components"]}
            actual = [facts[c].get("predicate", c) for c in fact.get("components", [])]
            if fact["kind"] != "derived" or len(actual) != len(expected) or set(actual) != expected:
                raise GraphError("已知Symptom必须按模板全部required_components派生，不能raw断言或缺组件")
        view = fact.get("view", declared_view(predicate))
        if fact["kind"] == "derived" and fact["state"] != "unknown" and not fact.get("components"):
            if any(fact_state(reasoning, dependency) == "unknown" for dependency in fact["derived_from"]):
                raise GraphError("已知派生事实不能由未知/代理依赖伪造")
        if fact["kind"] == "derived" and view in {"source", "profile"} and fact_state(reasoning, key) != "unknown":
            def raw_views(dependency):
                item = facts[dependency]
                if item["kind"] != "derived":
                    return {item.get("view", declared_view(item.get("predicate", dependency)))}
                return set().union(*(raw_views(d) for d in item["derived_from"]))
            if view not in set().union(*(raw_views(d) for d in fact["derived_from"])):
                raise GraphError("source 与 profile 不能互相自动推断")
        if fact.get("components") and fact_state(reasoning, key) != fact["state"]:
            raise GraphError("复合观察须遵循 all-of: false优先，否则全true才true，其余unknown")
    candidates = {c["hypothesis_id"]: c for c in reasoning["candidates"]}
    if len(candidates) != len(reasoning["candidates"]):
        raise GraphError("候选 hypothesis_id 重复")
    for candidate in candidates.values():
        validate_scope(candidate["scope"], scope)
        if set(candidate["targets"]) != set(candidate["scope"]["target_ids"]):
            raise GraphError("候选 targets 与 scope 不一致")
        if candidate["problem_id"] is not None and nodes.get(candidate["problem_id"], {}).get("kind") != "problem":
            raise GraphError("候选引用未注册 Problem；临时机制应使用 problem_id=null")
        for field in ("support", "counter", "unknown", "excluded_by"):
            for key in candidate[field]:
                if key not in facts:
                    raise GraphError(f"候选引用不存在的事实: {key}")
                validate_scope(facts[key]["scope"], candidate["scope"])
                if not _same_targets(facts[key]["scope"], candidate["scope"]):
                    raise GraphError("候选不能跨目标借证据")
                state = fact_state(reasoning, key)
                if field == "unknown" and state != "unknown":
                    raise GraphError("已知事实不能标注为 unknown")
                if field != "unknown" and state == "unknown":
                    raise GraphError("支持、反证和排除必须绑定已知事实")
        if candidate["status"] == "supported" and not candidate["support"]:
            raise GraphError("supported 候选必须有支持证据")
        if candidate["status"] == "rejected" and not (candidate["excluded_by"] or candidate["counter"]):
            raise GraphError("排除候选必须有反证或排除证据")
        roots_seen = set()
        for group in candidate["independent_evidence_groups"]:
            if not group or not set(group) <= set(candidate["support"] + candidate["counter"] + candidate["excluded_by"]):
                raise GraphError("独立证据组只能引用候选的已知证据")
            roots = set().union(*(_raw_roots(facts, key) for key in group))
            if not roots or roots & roots_seen:
                raise GraphError("同一原始证据及其派生量不能伪装为独立证据组")
            roots_seen |= roots
        if any(a not in candidates and nodes.get(a, {}).get("kind") != "problem" for a in candidate["alternatives"]):
            raise GraphError("替代解释必须引用任务候选或注册 Problem")
    instances = set()
    for instance in reasoning["action_instances"]:
        if instance["instance_id"] in instances:
            raise GraphError("Action instance_id 重复")
        instances.add(instance["instance_id"])
        if instance["hypothesis_id"] not in candidates:
            raise GraphError("动作实例必须引用当前候选，包括显式临时 Problem")
        candidate = candidates[instance["hypothesis_id"]]
        validate_scope(instance["scope"], candidate["scope"])
        if not _same_targets(instance["scope"], candidate["scope"]):
            raise GraphError("动作实例与候选必须作用于相同目标")
        action = nodes.get(instance["action_id"], {})
        if action.get("kind") != "action" or action.get("status") != "active":
            raise GraphError("动作实例必须引用 active 注册模板")
        slots = {s["name"]: s for s in action["slots"]}
        required_bindings = {s["name"] for s in slots.values() if s["required"]} | set(action["instantiation"]["required_bindings"])
        if set(instance["targets"]) - set(slots) or not required_bindings <= set(instance["targets"]):
            raise GraphError("动作实例缺少必需 slot 或绑定未知 slot")
        for name, object_id in instance["targets"].items():
            if object_id not in objects:
                raise GraphError("动作绑定的对象不存在")
            if slots[name]["kind"] != "object" and objects[object_id]["kind"] != slots[name]["kind"]:
                raise GraphError(f"动作 slot 对象类型不匹配: {name}")
        target_ids = {object_id for name, object_id in instance["targets"].items() if slots[name]["kind"] not in {"stage", "workload", "implementation"}}
        if target_ids != set(instance["scope"]["target_ids"]):
            raise GraphError("Action 目标绑定与 scope 不一致")
        if any(k not in facts for k in instance["evidence_bindings"].values()):
            raise GraphError("动作 evidence_bindings 引用了不存在事实")
        for fact_id in instance["evidence_bindings"].values():
            validate_scope(facts[fact_id]["scope"], instance["scope"])
        status = action_status(root, reasoning, instance, artifact)
        if status["failed"]:
            raise GraphError("动作原硬前提已知不满足，不能登记可推进实例")
        if instance["status"] == "ready" and status["status"] != "ready":
            raise GraphError("unknown 硬前提只允许 C2 conditional 分析，不能标记 ready")
        if not set(status["missing"]) <= set(instance["unknowns"]):
            raise GraphError("动作实例必须列出所有缺失硬前提")
    return reasoning


def _validate_sources(root, sources):
    manifest = json.loads((root / "workflows/references/knowledge-sources-1.3.0.json").read_text())
    revisions = {r["repo"]: r["revision"] for r in manifest["repositories"]}
    parent = json.loads((root / diagnosis.REGION / "versions/v0003/graph.json").read_text())
    historical = {(s["path"], s["revision"], s["sha256"]) for r in parent["records"] for s in r["sources"]}
    for source in sources:
        diagnosis._source(root, source, revisions, historical)


def _validate_claims(root, record, *, task_root=None, visited=None):
    task_root = Path(task_root) if task_root is not None else Path(root)
    visited = set() if visited is None else visited
    for claim in record["claims"]:
        if any(i >= len(record["sources"]) for i in claim["source_indexes"]):
            raise GraphError("claim 来源索引越界")
        if claim["basis"] in {"source_statement", "code_fact"} and not claim["source_indexes"]:
            raise GraphError("来源事实必须绑定 source_indexes")
        if claim["basis"] == "case_support" and not claim.get("case_refs"):
            raise GraphError("case_support 必须绑定非空且可验证的 claim.case_refs")
        for ref in claim.get("case_refs", []):
            path = _checked_reference(task_root, ref)
            identity = str(path.resolve())
            if identity in visited:
                raise GraphError("case_refs 不能循环自证")
            case = validate_case(root, json.loads(path.read_text()), task_root=task_root, _visited=visited | {identity})
            if claim["basis"] == "case_support" and (case["evidence_status"] != "validated_case" or case.get("execution_kind") != "hardware"):
                raise GraphError("paper/source_review/proxy/synthetic 不能作为 case_support")


def _validate_case_identity(root, record, task_root):
    """Check persisted record identities; this does not prove causality or hardware authenticity."""
    outcome = record["outcome"]
    context = json.loads(_checked_reference(task_root, record["context_ref"]).read_text())
    reasoning = json.loads(_checked_reference(task_root, record["reasoning_ref"]).read_text())
    validate_schema(root, "diagnosis-reasoning", reasoning)
    if not all(record.get(key) for key in ("routing_config_ref", "handoff_refs", "review_ref")):
        raise GraphError("validated_case必须绑定冻结routing bundle、C1/C2/C3交接与独立review")
    from .bindings import load_frozen_bundle, validate_chain
    artifacts, routing_config = load_frozen_bundle(root, record["routing_config_ref"])
    artifact = artifacts["diagnosis"]
    validate_reasoning(root, reasoning, artifact)
    chain = [json.loads(_checked_reference(task_root, record["handoff_refs"][stage]).read_text()) for stage in ("C1", "C2", "C3")]
    c1, c2, c3 = chain
    selected = record["selected_action_instances"]
    if not selected or not set(selected) <= {i["instance_id"] for i in reasoning["action_instances"]}:
        raise GraphError("案例selected_action_instances引用不存在的reasoning实例")
    result = validate_chain(root, c1, c2, c3, task_root=task_root, artifacts=artifacts, routing_config=routing_config)
    if content_hash(c1["reasoning"]) != content_hash(reasoning):
        raise GraphError("案例reasoning与C1真实快照不一致")
    if result["status"] != "implemented" or selected != c3["execution"]["executed_instances"]:
        raise GraphError("案例selected_action_instances必须对应C3实际实施的当前实例")
    _case_review(root, record, task_root)
    component_views = {c["id"]: r["view"] for r in artifact["records"] if r["kind"] == "symptom" for c in r["observation"]["required_components"]}
    views = {r["id"]: r["view"] for r in artifact["records"] if r["kind"] == "symptom"}
    views.update(component_views)
    if context.get("task_id") != record["task_id"] or reasoning["task_id"] != record["task_id"] or reasoning["current"]["scope"] != record["scope"]:
        raise GraphError("案例 Context/reasoning 与 task/scope 不一致")
    if reasoning["source_context_ref"] != record["context_ref"] or reasoning["context_hash"] != content_hash(reasoning["context_snapshot"]):
        raise GraphError("案例 reasoning 的 Context 来源身份不一致")
    for ref in (reasoning["current"]["implementation_ref"], reasoning["current"]["workload_ref"]):
        _checked_reference(task_root, ref)
    profiles = set()
    for key, fact in reasoning["facts"].items():
        if fact["kind"] == "raw" and fact["ref"] is not None:
            _checked_reference(task_root, fact["ref"])
            view = fact.get("view", views.get(fact.get("predicate", key)))
            if fact["state"] != "unknown" and view == "profile" and fact["scope"] == record["scope"]:
                profiles.add(fact["ref"]["sha256"])
    timing = json.loads(_checked_reference(task_root, outcome["timing_ref"]).read_text())
    correctness = json.loads(_checked_reference(task_root, outcome["correctness_ref"]).read_text())
    validate_schema(root, "unified-timing-result", timing)
    validate_schema(root, "unified-correctness", correctness)
    if timing["verdict"] != outcome["status"] or timing["operator"] != correctness["operator"] or timing["decision_hash"] != content_hash({k: v for k, v in timing.items() if k != "decision_hash"}):
        raise GraphError("案例性能/正确性记录身份或decision_hash不一致")
    request_ref = dict(timing["request"])
    request_path = Path(request_ref["path"])
    if request_path.is_absolute():
        if not request_path.resolve().is_relative_to(task_root.resolve()):
            raise GraphError("案例timing request越出任务根")
        request_ref["path"] = request_path.resolve().relative_to(task_root.resolve()).as_posix()
    request = json.loads(_checked_reference(task_root, request_ref).read_text())
    validate_schema(root, "unified-timing-request", request)
    if request["candidate_id"] != timing["candidate_id"] or request["baseline_source_sha256"] != record["scope"]["parent_implementation_hash"] or request["candidate_source_sha256"] != correctness["source_sha256"] or request["candidate_correctness"]["sha256"] != outcome["correctness_ref"]["sha256"]:
        raise GraphError("案例父实现、候选或正确性引用不一致")
    operator = context.get("operator")
    if not operator or any(value != operator for value in (request["operator"], timing["operator"], correctness["operator"], c2["selection"]["confirmed_plan"]["parallel_plan"]["operator"], c3["execution"]["dispatch_plan"]["operator"])):
        raise GraphError("案例Context、请求、timing、correctness与计划operator不一致")
    if c3["candidate_id"] != request["candidate_id"] or c3["execution"]["implementation_source_ref"]["sha256"] != request["candidate_source_sha256"]:
        raise GraphError("案例真实C3候选/source与计时请求不一致")
    # Runtime results contain an absolute request path; preserve it for the existing raw replay API.
    if not request_path.is_absolute():
        raise GraphError("validated_case必须使用runtime生成并绑定真实绝对request路径的timing结果")
    from .unified_timing import verify_timing
    from .errors import ContractError
    try:
        verify_timing(_checked_reference(task_root, outcome["timing_ref"]))
    except (ContractError, OSError, ValueError) as exc:
        raise GraphError(f"案例统一计时/完整正确性原始链回放失败: {exc}") from exc
    for role in ("baseline", "candidate"):
        for ref in request[role + "_captures"]:
            capture = json.loads(_checked_reference(request_path.parent, ref).read_text())
            if capture["identity"]["workload_ref"] != record["scope"]["workload_hash"]:
                raise GraphError("案例真实capture与reasoning/C3 workload身份不一致")
    for ref in outcome["mechanism_refs"]:
        mechanism = json.loads(_checked_reference(task_root, ref).read_text())
        validate_schema(root, "mechanism-report", mechanism)
        if mechanism["candidate_id"] != timing["candidate_id"] or mechanism["hypothesis_basis"] != "measured":
            raise GraphError("案例机制报告不能用paper/proxy/heuristic冒充实测")
        if any(m[side + "_profile_hash"] not in profiles for m in mechanism["metrics"] for side in ("baseline", "candidate")):
            raise GraphError("案例机制指标必须绑定同scope已核hash的原始profile事实")


_CASE_BASIS_FIELDS = ("case_id", "evidence_status", "execution_kind", "task_id", "scope", "context_ref", "reasoning_ref", "sources", "observations", "candidate_explanations", "selected_action_instances", "outcome", "claims", "handoff_refs", "routing_config_ref")


def case_basis_hash(record: dict) -> str:
    return content_hash({key: record.get(key) for key in _CASE_BASIS_FIELDS})


def _case_review(root, record, task_root):
    if not record.get("review_ref"):
        raise GraphError("validated_case需要结构化独立review_ref")
    review = json.loads(_checked_reference(task_root, record["review_ref"]).read_text())
    validate_schema(root, "diagnosis-case-review", review)
    if review["case_id"] != record["case_id"] or review["case_basis_hash"] != case_basis_hash(record):
        raise GraphError("案例review未绑定本案例的完整证据内容")
    if any(review[key] != record["review"][key] for key in ("reviewer", "independent", "decision")):
        raise GraphError("案例独立review正文与外层声明不一致")
    if not review["independent"] or review["decision"] != "reviewed" or review["blocking_findings"]:
        raise GraphError("validated_case独立review必须reviewed且无blocking findings")


_ACTIVE_CASES = ContextVar("aprof_active_diagnosis_cases", default=frozenset())


def validate_case(root: Path, record: dict, *, task_root=None, _visited=None) -> dict:
    task_root = Path(task_root) if task_root is not None else Path(root)
    identity = (str(task_root.resolve()), content_hash(record))
    active = _ACTIVE_CASES.get()
    if identity in active:
        raise GraphError("case/routing bundle不能循环自证")
    token = _ACTIVE_CASES.set(active | {identity})
    try:
        return _validate_case(root, record, task_root=task_root, _visited=_visited)
    finally:
        _ACTIVE_CASES.reset(token)


def _validate_case(root: Path, record: dict, *, task_root=None, _visited=None) -> dict:
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    validate_schema(root, "diagnosis-case", record)
    if record["scope"]["task_id"] != record["task_id"]:
        raise GraphError("案例 task/scope 不一致")
    _validate_sources(root, record["sources"])
    _validate_claims(root, record, task_root=task_root, visited=_visited)
    outcome = record["outcome"]
    for ref in (record["context_ref"], record["reasoning_ref"], record.get("review_ref"), outcome["timing_ref"], outcome["correctness_ref"], *outcome["mechanism_refs"], *record.get("handoff_refs", {}).values()):
        if ref is not None:
            _checked_reference(task_root, ref)
    if record.get("routing_config_ref") is not None:
        _checked_reference(root, record["routing_config_ref"])
    if record["evidence_status"] in {"paper", "source_review"}:
        if record.get("execution_kind", "not_run") != "not_run":
            raise GraphError("paper/source_review不能声明hardware或synthetic执行")
        if outcome["status"] != "not_run" or outcome["timing_ref"] is not None or outcome["correctness_ref"] is not None or outcome["mechanism_refs"]:
            raise GraphError("纸面/来源审阅案例不能冒充真实运行或性能结果")
        if any(c["basis"] == "case_support" for c in record["claims"]):
            raise GraphError("paper/source_review 不能生成 case_support")
    else:
        if record.get("execution_kind") not in {"hardware", "synthetic"}:
            raise GraphError("validated_case必须明确声明execution_kind=hardware或synthetic；标签不证明硬件真实性")
        if not all((record["context_ref"], record["reasoning_ref"], outcome["timing_ref"], outcome["correctness_ref"], outcome["mechanism_refs"])) or outcome["status"] == "not_run":
            raise GraphError("validated_case 必须保留真实上下文、推理、正确性、计时和机制引用")
        if not record["review"]["independent"] or record["review"]["decision"] != "reviewed":
            raise GraphError("validated_case 需要独立审阅")
        _validate_case_identity(root, record, task_root)
    return record


def _checked_reference(root, ref):
    path = local(root, ref["path"])
    if not path.is_file() or digest(path.read_bytes()) != ref["sha256"]:
        raise GraphError(f"产物文件 hash 不匹配: {ref['path']}")
    return path


_PROPOSAL_BASIS_FIELDS = ("proposal_id", "kind", "title", "rationale", "scope", "sources", "claims", "case_refs", "semantic_dedup", "proposed_record", "proposed_relations")


def proposal_basis_hash(record: dict) -> str:
    """Bind review to substantive content without circular review/control references."""
    return content_hash({key: record[key] for key in _PROPOSAL_BASIS_FIELDS})


def _proposal_attestations(root, record, task_root, artifact):
    target = record["promotion"]["target_version"]
    if not isinstance(target, str) or len(target) != 5 or target[0] != "v" or not target[1:].isdigit() or int(target[1:]) <= int(artifact["version"][1:]):
        raise GraphError("提案 target_version 必须高于当前诊断图版本")
    expected = {"proposal_id": record["proposal_id"], "proposal_basis_hash": proposal_basis_hash(record), "base_knowledge_hash": content_hash(artifact), "target_version": target}
    review = None
    if record["review_ref"] is not None:
        review = json.loads(_checked_reference(task_root, record["review_ref"]).read_text())
        validate_schema(root, "diagnosis-proposal-review", review)
        if any(review[key] != value for key, value in expected.items()):
            raise GraphError("独立review绑定了其他提案内容、base或目标版本")
        if any(review[key] != record["review"][key] for key in ("reviewer", "independent", "decision")):
            raise GraphError("独立review正文与外层review声明不一致")
    validations = []
    for ref in record["validation_refs"]:
        value = json.loads(_checked_reference(task_root, ref).read_text())
        validate_schema(root, "diagnosis-proposal-validation", value)
        if any(value[key] != expected_value for key, expected_value in expected.items()):
            raise GraphError("validation绑定了其他提案内容、base或目标版本")
        validations.append(value)
    if record["promotion"]["eligible"]:
        if review is None or not review["independent"] or review["decision"] != "approved" or review["blocking_findings"]:
            raise GraphError("晋升必须有独立approved且无blocking findings的结构化review")
        if not validations or any(v["blocking_findings"] or any(state != "passed" for state in v["checks"].values()) for v in validations):
            raise GraphError("晋升validation必须contract/source/dedup全部passed且无blocking findings")


def validate_proposal(root: Path, record: dict, *, task_root=None) -> dict:
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    validate_schema(root, "diagnosis-proposal", record)
    _validate_sources(root, record["sources"])
    _validate_claims(root, record, task_root=task_root)
    for ref in record["case_refs"]:
        validate_case(root, json.loads(_checked_reference(task_root, ref).read_text()), task_root=task_root)
    draft = record["proposed_record"]
    if draft is not None:
        if draft["kind"] != record["kind"]:
            raise GraphError("提案类型与 proposed_record 不一致")
        _validate_sources(root, draft["sources"])
        _validate_claims(root, draft, task_root=task_root)
    for relation in record["proposed_relations"]:
        _validate_sources(root, relation["sources"])
        _validate_claims(root, relation, task_root=task_root)
    if record["promotion"]["eligible"] and (draft is None or not record["validation_refs"] or record["review_ref"] is None):
        raise GraphError("晋升需完整模板草稿、验证记录和独立复核文件引用")
    artifact = None
    if record["validation_refs"] or record["review_ref"] is not None or record["promotion"]["eligible"]:
        artifact = diagnosis.verify(root)
        _proposal_attestations(root, record, task_root, artifact)
    if record["promotion"]["eligible"]:
        ids = {r["id"] for r in artifact["records"]}
        if draft["id"] in ids or any(r["id"] in ids for r in record["proposed_relations"]):
            raise GraphError("提案 ID 与现模板重复")
        if not set(record["semantic_dedup"]["compared_ids"]) <= ids:
            raise GraphError("语义去重引用了不存在模板")
        diagnosis._validate_records(artifact["records"] + [draft] + record["proposed_relations"])

        if not (record["status"] == "reviewed" and record["review"]["independent"] and record["review"]["decision"] == "approved" and record["contract_check"]["status"] == "passed" and record["semantic_dedup"]["distinct_from_existing"] and record["semantic_dedup"]["compared_ids"] and record["promotion"]["target_version"] and record["sources"]):
            raise GraphError("模板晋升需要来源、契约、语义去重与独立审阅；禁止自动入图")
    return record

"""轻量机制目录与当前观察邻接；不计算机制分数或锁定Action。"""
from __future__ import annotations
from copy import deepcopy

from .diagnosis import _root, validate_artifact
from .errors import GraphError
from .jsonio import content_hash
from .knowledge import _evidence, digest, validate_schema


def _scope_status(scope, attributes):
    unknown = False
    for name, key in (("platform", "platforms"), ("dtype", "dtypes"), ("family", "workloads")):
        allowed = scope[key]
        if "all" in allowed:
            continue
        observed = attributes.get(name)
        if observed is None:
            unknown = True
            continue
        values = observed if isinstance(observed, list) else [observed]
        if any(not isinstance(value, str) for value in values):
            raise GraphError(f"检索属性 {name} 必须为字符串或字符串数组")
        if not set(values) & set(allowed):
            return "mismatch"
    return "unknown" if unknown else "match"


def retrieve(artifact: dict, context: dict, root=None) -> dict:
    from .diagnosis_reasoning import profile_time_known
    validate_artifact(artifact, root)
    facts = _evidence(context)
    for name in ("platform", "dtype", "family"):
        value = context["attributes"].get(name)
        if value is not None and not (isinstance(value, str) or
                isinstance(value, list) and all(isinstance(item, str) for item in value)):
            raise GraphError(f"检索属性 {name} 必须为字符串或字符串数组")
    problems = []
    for record in artifact["records"]:
        if record["kind"] != "problem":
            continue
        analysis = record["analysis"]
        problems.append({"id": record["id"], "title": record["title"], "mechanism": record["mechanism"],
            "mechanism_summary": " → ".join(analysis["mechanism_chain"]),
            "alternatives": deepcopy(analysis["alternatives"]),
            "discriminating_checks": analysis["supporting_checks"][:1] + analysis["counter_checks"][:1],
            "scope_status": _scope_status(record["scope"], context["attributes"]),
            "scope": deepcopy(record["scope"]), "slots": deepcopy(record["slots"]),
            "source_path": record["source_path"], "source_hash": record["source_hash"],
            "review": deepcopy(record["review"])})
    observations, adjacency = [], []
    def observation_state(key, view):
        fact = facts.get(key, {})
        if fact.get("kind") == "proxy" or view == "profile" and not profile_time_known(fact):
            return "unknown"
        return fact.get("state", "unknown")
    for record in artifact["records"]:
        if record["kind"] != "symptom":
            continue
        required = [component["id"] for component in record["observation"]["required_components"]]
        states = [observation_state(key, record["view"]) for key in required]
        if required:
            state = False if any(s is False for s in states) else True if all(s is True for s in states) else "unknown"
        else:
            state = observation_state(record["id"], record["view"])
        observations.append({"id": record["id"], "state": state, "view": record["view"],
            "required_components": required, "scope_status": "unbound",
            "interpretation_boundary": record["observation"]["interpretation_boundary"]})
        if state == "unknown" or _scope_status(record["scope"], context["attributes"]) == "mismatch":
            continue
        for edge in artifact["records"]:
            if edge["kind"] != "edge" or edge["from"] != record["id"]:
                continue
            adjacency.append({"symptom_id": record["id"], "problem_id": edge["to"], "relation": edge["relation"],
                "edge_id": edge["id"], "observation_state": state, "condition_state": "not_evaluated",
                "binding": deepcopy(edge["binding"]), "claim_basis": sorted({c["basis"] for c in edge["claims"]}),
                "source_path": edge["source_path"], "source_hash": edge["source_hash"],
                "legacy_prior": {"weight": edge["learning"]["weight"], "role": "uncalibrated_auxiliary_only"}})
    result = {"schema_version": "aprof.diagnosis-retrieval/v1", "task_id": context["task_id"],
        "context_hash": content_hash(context), "knowledge_hash": content_hash(artifact), "graph_version": artifact["graph_version"],
        "source_context_ref": deepcopy(context["source_context_ref"]), "problem_directory": problems,
        "observations": observations, "symptom_adjacency": adjacency,
        "limitations": ["目录完整；仅展开当前已知观察的邻接，未加载机制正文或全部来源。", "profiling缺少明确时间范围或整份采集聚合口径时保持unknown。", "观察和边条件尚未绑定当前目标/阶段；scope match只是检索范围，不授权平台能力。", "历史先验只辅助阅读，不计算机制总分、概率或自动选择动作。"]}
    validate_schema(_root(root), "diagnosis-retrieval", result)
    return result


def expand(artifact: dict, context: dict, request: dict, root=None) -> dict:
    """只展开调用者显式选择的注册 Problem；不据目录生成判断或 Action。"""
    root = _root(root)
    validate_schema(root, "diagnosis-problem-expansion-request", request)
    retrieval = retrieve(artifact, context, root)
    identity = {key: retrieval[key] for key in (
        "task_id", "context_hash", "knowledge_hash", "graph_version", "source_context_ref")}
    identity["retrieval_hash"] = content_hash(retrieval)
    if any(request[key] != value for key, value in identity.items()):
        raise GraphError("Problem 展开请求与 Context、知识或检索身份不一致")
    records = {record["id"]: record for record in artifact["records"] if record["kind"] == "problem"}
    selected = [selection["problem_id"] for selection in request["selections"]]
    if len(selected) != len(set(selected)):
        raise GraphError("同一展开请求不能重复选择 Problem")
    entries = []
    for selection in request["selections"]:
        identifier = selection["problem_id"]
        if identifier not in records:
            raise GraphError(f"只能展开已注册 Problem，临时机制没有模板正文: {identifier}")
        if any(other not in records for other in selection["related_problem_ids"]):
            raise GraphError("关联机制必须为已注册 Problem；临时解释保存在任务推理中")
        record = records[identifier]
        if not record["body"].strip():
            raise GraphError(f"Problem 缺少正文: {identifier}")
        entry = deepcopy(selection)
        entry.update({key: deepcopy(record[key]) for key in (
            "title", "mechanism", "scope", "slots", "analysis", "claims", "review", "sources",
            "body", "source_path", "source_hash")})
        entry.update(template_hash=content_hash(record), body_sha256=digest(record["body"].encode("utf-8")),
                     scope_status=_scope_status(record["scope"], context["attributes"]))
        entries.append(entry)
    result = {"schema_version": "aprof.diagnosis-problem-expansion/v1", **identity,
              "request_hash": content_hash(request), "request": deepcopy(request), "entries": entries,
              "limitations": ["正文由调用者按阅读理由选择；展开不表示机制成立、被排除或 Action 已就绪。",
                              "scope match 仅用于检索，不授权平台能力；原始证据及未知项仍由任务推理核验。",
                              "正文 hash 证明交付内容可回放；不能据此证明 Agent 已理解或采用该内容。"]}
    validate_schema(root, "diagnosis-problem-expansion", result)
    return result


def validate_expansion(artifact: dict, context: dict, result: dict, root=None) -> dict:
    """用原请求和同身份知识/Context 回放，校验全部正文、来源和理由。"""
    root = _root(root)
    validate_schema(root, "diagnosis-problem-expansion", result)
    expected = expand(artifact, context, result["request"], root)
    if result != expected:
        raise GraphError("Problem 展开正文、来源、阅读理由或身份已改变")
    return {"valid": True, "schema_version": result["schema_version"],
            "knowledge_hash": result["knowledge_hash"], "context_hash": result["context_hash"],
            "expansion_hash": content_hash(result),
            "problem_ids": [entry["problem_id"] for entry in result["entries"]]}

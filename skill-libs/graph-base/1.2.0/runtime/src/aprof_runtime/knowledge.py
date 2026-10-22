"""可训练 Markdown 知识的确定性构建、校验和路由；不改变历史图语义。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .errors import GraphError
from .jsonio import content_hash
from .measurement_admission import _release_root

SCHEMA = "aprof.knowledge/v1"
ROUTE_SCHEMA = "aprof.knowledge-route/v1"
REGIONS = {
    "diagnosis": "skills/ascendc-aprof-diagnosis/graph",
    "parallel-planning": "skills/ascendc-aprof-parallel-planning/knowledge",
    "optimization": "skills/ascendc-aprof-optimization/knowledge",
}
GRAPH_KINDS = {"symptom", "problem", "action", "edge"}
TREE_KINDS = {"router", "strategy", "template", "recipe", "example"}


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key, value in node.value:
        key = loader.construct_object(key, deep=deep)
        if not isinstance(key, str) or key in result:
            raise GraphError(f"YAML 字段非字符串或重复: {key!r}")
        result[key] = loader.construct_object(value, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def local(root: Path, name: str) -> Path:
    rel = Path(name)
    path = root / rel
    if rel.is_absolute() or ".." in rel.parts or not path.resolve().is_relative_to(root.resolve()):
        raise GraphError(f"路径越出知识包: {name}")
    if any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
        raise GraphError(f"知识源不能通过符号链接读取: {name}")
    return path


def validate_schema(root: Path, name: str, value: Any) -> None:
    schema = json.loads((root / f"schemas/{name}.schema.json").read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise GraphError(f"{name}: {errors[0].json_path}: {errors[0].message}")


def _finite(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GraphError(f"{label}: 需要有限数值")
    if minimum is not None and value < minimum:
        raise GraphError(f"{label}: 小于 {minimum}")


def read_record(path: Path, root: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise GraphError(f"缺少 YAML frontmatter: {path}")
    header, body = text[4:].split("\n---\n", 1)
    try:
        record = yaml.load(header, Loader=UniqueSafeLoader)
    except yaml.YAMLError as exc:
        raise GraphError(f"无法安全解析 {path}: {exc}") from exc
    validate_schema(root, "knowledge-record", record)
    if not body.strip():
        raise GraphError(f"正文为空: {path}")
    for source in record["sources"]:
        raw = local(root, source["path"]).read_bytes()
        if digest(raw) != source["sha256"]:
            raise GraphError(f"来源 hash 不符: {source['path']}")
        lines = raw.decode().splitlines(keepends=True)
        start, end = source["lines"]
        if not (1 <= start <= end <= len(lines)):
            raise GraphError(f"来源行号无效: {source['path']}")
        if digest("".join(lines[start - 1:end]).encode()) != source["excerpt_sha256"]:
            raise GraphError(f"来源片段 hash 不符: {source['path']}")
    record.update(body=body.strip(), source_path=path.relative_to(root).as_posix(),
                  source_hash=digest(path.read_bytes()))
    return record


def _condition_valid(condition):
    if set(condition) != {"field", "op", "value"} or condition["op"] not in {"eq", "contains", "in"}:
        raise GraphError(f"非法条件: {condition}")
    if condition["op"] == "in" and not isinstance(condition["value"], list):
        raise GraphError("in 条件必须给数组")


def validate_records(records: list[dict], owner: str) -> None:
    nodes = {}
    for r in records:
        identifier, kind = r["id"], r["kind"]
        if identifier in nodes:
            raise GraphError(f"重复 ID: {identifier}")
        nodes[identifier] = r
        if kind not in (GRAPH_KINDS if owner == "diagnosis" else TREE_KINDS):
            raise GraphError(f"知识类型不属于 {owner}: {kind}")
        for key, value in r["learning"].items():
            _finite(value, f"{identifier}.{key}")
        expected = {"symptom": {"gain": 1}, "problem": {"bias": 0}, "action": {"bias": 0}}
        if kind in expected and r["learning"] != expected[kind]:
            raise GraphError(f"初值必须是 {expected[kind]}: {identifier}；训练值使用覆盖文件")
        for condition in r.get("conditions", []):
            _condition_valid(condition)
    if owner == "diagnosis":
        relations = set()
        for r in records:
            kind = r["kind"]
            if kind == "symptom" and r["view"] not in {"source", "profile", "workload"}:
                raise GraphError("symptom.view 非法")
            if kind == "edge":
                relation = r["relation"]
                endpoints = ("problem", "action") if relation == "mitigated_by" else ("symptom", "problem")
                if relation not in {"supports", "refutes", "mitigated_by"}:
                    raise GraphError(f"非法边类型: {relation}")
                if any(nodes.get(r[k], {}).get("kind") != t for k, t in zip(("from", "to"), endpoints)):
                    raise GraphError(f"悬空或错误类型的边: {r['id']}")
                signature = (r["from"], r["to"], relation, json.dumps(r["conditions"], sort_keys=True))
                if signature in relations:
                    raise GraphError(f"重复关系: {r['id']}")
                relations.add(signature)
                if set(r["learning"]) != {"weight"} or r["learning"]["weight"] not in (1, 2, 3):
                    raise GraphError("边的专家初值必须是 1/2/3")
        return
    roots = [r for r in records if r["parent"] is None]
    if len(roots) != 1 or roots[0]["kind"] != "router":
        raise GraphError("知识树必须恰有一个根 router")
    owned = set()
    for r in records:
        if r["kind"] != "router" and r.get("routes"):
            raise GraphError("只有 router 可以维护子路由")
        fallbacks = 0
        for route in r.get("routes", []):
            target = route["target"]
            if target not in nodes or nodes[target]["parent"] != r["id"] or target in owned:
                raise GraphError(f"树路由悬空或主归属重复: {target}")
            owned.add(target)
            score = route["prior_score"]
            _finite(score, target)
            if score not in (1, 2, 3) and not (score == 0 and route["fallback"]):
                raise GraphError("路由初值必须为 1/2/3；fallback 为 0")
            if route["fallback"]:
                fallbacks += 1
                if score != 0:
                    raise GraphError("fallback 分数必须为 0")
            for c in route["match"] + route["exclude"]:
                _condition_valid(c)
        if r["kind"] == "router" and fallbacks != 1:
            raise GraphError(f"每个 router 需要一个 fallback: {r['id']}")
        if any(ref not in nodes for ref in r.get("references", [])):
            raise GraphError(f"悬空跨分支引用: {r['id']}")
        visited = set()
        current = r
        while current["parent"] is not None:
            if current["id"] in visited or current["parent"] not in nodes:
                raise GraphError(f"树环或不存在的父节点: {r['id']}")
            visited.add(current["id"])
            current = nodes[current["parent"]]
    if owned != set(nodes) - {roots[0]["id"]}:
        raise GraphError("存在无路由可达的条目")


def compile_region(root: Path, owner: str) -> dict:
    root = root.resolve()
    region = root / REGIONS[owner]
    identity = json.loads((region / "REGION.json").read_text())
    if (set(identity) != {"schema_version", "owner", "version"}
            or identity["schema_version"] != "aprof.knowledge-region/v1"
            or identity["owner"] != owner or not re.fullmatch(r"v[0-9]{4}", identity["version"])):
        raise GraphError("知识区身份/版本无效")
    records = []
    for path in sorted(region.rglob("*.md")):
        rel = path.relative_to(region)
        if set(rel.parts) & {"history", "sources", "versions"} or path.name in {"README.md", "FORMAT.md", "GRAPH.md", "INITIALIZATION.md", "NOTICE.md"}:
            continue
        records.append(read_record(path, root))
    if not records:
        raise GraphError(f"知识区为空: {owner}")
    validate_records(records, owner)
    records.sort(key=lambda r: r["id"])
    artifact = {"schema_version": SCHEMA, "owner": owner,
                "version": identity["version"],
                "generator": {"id": "aprof_runtime.knowledge/v1", "sha256": digest(Path(__file__).read_bytes()),
                              "schema_hash": digest((root / 'schemas/knowledge-record.schema.json').read_bytes())},
                "source_hashes": {r["source_path"]: r["source_hash"] for r in records}, "records": records}
    if owner == "diagnosis":
        artifact["graph_version"] = identity["version"]
    artifact["source_hashes"][(region / "REGION.json").relative_to(root).as_posix()] = digest((region / "REGION.json").read_bytes())
    validate_schema(root, "knowledge-index", artifact)
    return artifact


def artifact_path(root: Path, owner: str) -> Path:
    region = root / REGIONS[owner]
    version = json.loads((region / "REGION.json").read_text())["version"]
    return local(region, f"versions/{version}/graph.json" if owner == "diagnosis" else "index.json")


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build(root: Path, owner: str) -> dict:
    if (root / "release.json").exists():
        raise GraphError("不能重建已发布包；先建立新的版本目录")
    artifact = compile_region(root, owner)
    path = artifact_path(root, owner)
    write_json(path, artifact)
    region = root / REGIONS[owner]
    lines = ["# 初始化清单（自动生成）", "", "初值是未校准的专家排序分数，不表示概率或预期收益。修改各条目 Markdown 后重新构建。", "", "| ID | 类型 | 初始参数 | 来源 | 赋值理由 |", "| --- | --- | --- | --- | --- |"]
    for r in artifact["records"]:
        relative = Path(r["source_path"]).relative_to(REGIONS[owner]).as_posix()
        source = "; ".join(f"{s['original_path']}:{s['lines'][0]}-{s['lines'][1]} @ {s['revision']} ({s['excerpt_sha256']})" for s in r["sources"])
        reason = r.get("seed_reason", "匹配增益为 1；机制与动作偏置为 0" if owner == "diagnosis" else "子路由逐项给出 3/2/1 初值，通用 fallback 为 0")
        lines.append(f"| [{r['id']}]({relative}) | {r['kind']} | `{json.dumps(r['learning'])}` | {source} | {reason} |")
        for route in r.get("routes", []):
            lines.append(f"| {r['id']} → {route['target']} | route | {route['prior_score']} | 同所属 router | {route['seed_reason']} |")
    (region / "INITIALIZATION.md").write_text("\n".join(lines) + "\n")
    if owner == "diagnosis":
        write_json(path.parent / "lineage.json", {"parent_graph_version": "v0002", "migration": "../../../../../workflows/migration/migration.json", "scoring": "ordinal_support_refute_v1"})
        manifest = {"graph_version": artifact["version"], "immutable": True, "graph_sha256": digest(path.read_bytes()).removeprefix("sha256:"), "files": {"graph": "graph.json", "lineage": "lineage.json", "checksums": "checksums.json"}}
        write_json(path.parent / "manifest.json", manifest)
        write_json(path.parent / "checksums.json", {"algorithm": "sha256", "files": {p.name: digest(p.read_bytes()).removeprefix("sha256:") for p in (path, path.parent / "lineage.json", path.parent / "manifest.json")}})
        lines = [f"# {artifact['version']} 诊断图（自动生成）", "", "按观测匹配 symptom，再沿 supports/refutes 评估 problem，沿 mitigated_by 找 action。每条边的唯一来源是 edges 中的 Markdown。", "", "| Symptom / Problem | 关系 | Problem / Action | 初值 | 条件 |", "| --- | --- | --- | --- | --- |"]
        lookup = {r["id"]: Path(r["source_path"]).relative_to(REGIONS[owner]).as_posix() for r in artifact["records"]}
        for r in artifact["records"]:
            if r["kind"] == "edge":
                lines.append(f"| [{r['from']}]({lookup[r['from']]}) | [{r['relation']}]({lookup[r['id']]}) | [{r['to']}]({lookup[r['to']]}) | {r['learning']['weight']} | 见边的适用域与条件 |")
        (region / "GRAPH.md").write_text("\n".join(lines) + "\n")
    return artifact


def validate_artifact(artifact: dict) -> dict:
    if artifact.get("schema_version") != SCHEMA or artifact.get("owner") not in REGIONS:
        raise GraphError("知识格式/角色不匹配")
    package = _release_root()
    validate_schema(package, "knowledge-index", artifact)
    for record in artifact["records"]:
        raw = {k: v for k, v in record.items() if k not in {"body", "source_path", "source_hash"}}
        validate_schema(package, "knowledge-record", raw)
        if not record.get("body") or artifact["source_hashes"].get(record.get("source_path")) != record.get("source_hash"):
            raise GraphError("条目快照缺少正文或源文件 hash")
    validate_records(artifact["records"], artifact["owner"])
    if artifact["owner"] == "diagnosis" and (artifact.get("graph_version") != artifact["version"] or artifact["version"] in {"v0001", "v0002"}):
        raise GraphError("新知识格式不能冒充历史图")
    return artifact


def verify(root: Path, owner: str) -> dict:
    artifact = json.loads(artifact_path(root, owner).read_text())
    if artifact != compile_region(root, owner):
        raise GraphError(f"{owner}: 构建产物已过期或被修改")
    return artifact


def apply_override(artifact: dict, override: dict | None) -> dict:
    result = deepcopy(artifact)
    if override is None:
        return result
    if (set(override) != {"schema_version", "base_hash", "version", "parameters"}
            or override["schema_version"] != "aprof.knowledge-override/v1"
            or override["base_hash"] != content_hash(artifact) or override["version"] != artifact["version"]):
        raise GraphError("训练参数必须绑定知识的确切版本和 hash；不能使用旧 policy")
    nodes = {r["id"]: r for r in result["records"]}
    for identifier, update in override["parameters"].items():
        if identifier not in nodes or not isinstance(update, dict):
            raise GraphError(f"覆盖了未知条目: {identifier}")
        node = nodes[identifier]
        if node["kind"] == "router":
            routes = {r["target"]: r for r in node["routes"]}
            for target, value in update.items():
                if target not in routes or routes[target]["fallback"]:
                    raise GraphError("不能覆盖不存在的 route 或 fallback")
                _finite(value, target, 0)
                routes[target]["prior_score"] = value
        else:
            if set(update) - set(node["learning"]):
                raise GraphError("学习参数名称不匹配")
            for name, value in update.items():
                _finite(value, identifier, None if name == "bias" else 0)
                node["learning"][name] = value
    return result


def _evidence(context):
    if context.get("schema_version") != "aprof.evidence/v1" or not context.get("task_id"):
        raise GraphError("需要 aprof.evidence/v1 及 task_id；旧 context 不自动转换")
    origin = context.get("source_context_ref")
    if not isinstance(origin, dict) or set(origin) != {"path", "sha256"} or not origin["path"] or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(origin["sha256"])):
        raise GraphError("evidence 必须关联 C0/Context 的文件引用 source_context_ref")
    facts = context.get("facts", {})
    if not isinstance(facts, dict) or not isinstance(context.get("attributes", {}), dict):
        raise GraphError("facts/attributes 必须为对象")
    for key, item in facts.items():
        if not isinstance(item, dict) or (item.get("state") != "unknown" and type(item.get("state")) is not bool):
            raise GraphError(f"{key}: state 必须是 true/false/unknown")
        if item["state"] != "unknown":
            if not item.get("evidence_id") or not isinstance(item.get("ref"), dict) or not all(item["ref"].get(k) for k in ("path", "sha256", "locator")):
                raise GraphError(f"{key}: 已知事实必须绑定 evidence_id 和原始证据引用")
    return facts


def _state(facts, key):
    item = facts.get(key, {})
    return "unknown" if item.get("kind") == "proxy" else item.get("state", "unknown")


def _matches(attributes, condition):
    value = attributes.get(condition["field"])
    if value is None:
        return None
    op, expected = condition["op"], condition["value"]
    if op == "eq":
        return value == expected
    if op == "contains":
        return expected in value if isinstance(value, (list, str, dict)) else False
    return value in expected


def _in_scope(record, attributes):
    for key, attribute in (("platforms", "platform"), ("workloads", "family"), ("dtypes", "dtype")):
        wanted = record["scope"][key]
        if "all" not in wanted:
            actual = attributes.get(attribute)
            if actual is None:
                return False
            actual = actual if isinstance(actual, list) else [actual]
            if not set(wanted) & set(actual):
                return False
    return True


def _trace(artifact, context, override):
    return {"schema_version": ROUTE_SCHEMA, "owner": artifact["owner"], "version": artifact["version"],
            "knowledge_hash": content_hash(artifact), "context_hash": content_hash(context),
            "task_id": context["task_id"], "override_hash": content_hash(override) if override else None,
            "selection_mode": "deterministic", "evidence": deepcopy(context.get("facts", {})),
            "context_snapshot": deepcopy(context)}


def route_diagnosis(artifact: dict, context: dict, override=None) -> dict:
    validate_artifact(artifact)
    if artifact["owner"] != "diagnosis":
        raise GraphError("知识树不能当诊断图路由")
    facts = _evidence(context)
    effective = apply_override(artifact, override)
    nodes = {r["id"]: r for r in effective["records"]}
    attrs = context.get("attributes", {})
    applicable = {i for i, r in nodes.items() if r["status"] == "active" and _in_scope(r, attrs)}
    contributions = {}
    ignored = []
    for edge in effective["records"]:
        if edge["kind"] != "edge" or edge["relation"] == "mitigated_by" or edge["id"] not in applicable:
            continue
        if edge["from"] not in applicable or edge["to"] not in applicable or _state(facts, edge["from"]) is not True:
            continue
        if any(_matches(attrs, c) is not True for c in edge["conditions"]):
            continue
        evidence_id = facts[edge["from"]]["evidence_id"]
        key = (edge["to"], evidence_id)
        score = edge["learning"]["weight"] * nodes[edge["from"]]["learning"]["gain"] * (-1 if edge["relation"] == "refutes" else 1)
        item = {"edge_id": edge["id"], "evidence_id": evidence_id, "symptom_id": edge["from"], "score": score}
        old = contributions.get(key)
        if old is None or (-abs(score), score, edge["id"]) < (-abs(old["score"]), old["score"], old["edge_id"]):
            if old:
                ignored.append(old)
            contributions[key] = item
        else:
            ignored.append(item)
    problems = []
    for r in nodes.values():
        if r["kind"] == "problem" and r["id"] in applicable:
            evidence = [v for (problem, _), v in contributions.items() if problem == r["id"]]
            problems.append({"id": r["id"], "score": r["learning"]["bias"] + sum(v["score"] for v in evidence), "contributions": evidence})
    problems.sort(key=lambda r: (-r["score"], r["id"]))
    scores = {r["id"]: r["score"] for r in problems}
    actions = {}
    for edge in effective["records"]:
        if edge["kind"] != "edge" or edge["relation"] != "mitigated_by" or edge["id"] not in applicable or scores.get(edge["from"], 0) <= 0 or edge["to"] not in applicable:
            continue
        action = nodes[edge["to"]]
        missing, failed = [], []
        for condition in action["preconditions"]:
            state = _state(facts, condition["fact"])
            if state == "unknown":
                missing.append(condition["fact"])
            elif state != condition["state"]:
                failed.append(condition["fact"])
        for c in edge["conditions"]:
            matched = _matches(attrs, c)
            if matched is None:
                missing.append(c["field"])
            elif not matched:
                failed.append(c["field"])
        score = scores[edge["from"]] * edge["learning"]["weight"] + action["learning"]["bias"]
        item = {"id": action["id"], "score": score, "problem_id": edge["from"], "edge_id": edge["id"],
                "status": "blocked" if failed else "needs_evidence" if missing else "executable",
                "missing": sorted(set(missing)), "failed": sorted(set(failed)), "snapshot": action}
        previous = actions.get(action["id"])
        if previous is None or (-score, edge["id"]) < (-previous["score"], previous["edge_id"]):
            actions[action["id"]] = item
    ranked = sorted(actions.values(), key=lambda r: (-r["score"], r["id"]))
    status = "resolved" if ranked else "unknown"
    if _state(facts, "symptom.workload.tiny_or_overhead_limited") is True:
        status = "workload_limited"
    elif not any(_state(facts, i) != "unknown" for i in nodes if i.startswith("symptom.profile.")):
        status = "measurement_limited"
    trace = _trace(artifact, context, override)
    trace.update(diagnostic_state=status, problems=problems, actions=ranked, deduplicated=ignored,
                 missing=[i for i, r in nodes.items() if r["kind"] == "symptom" and _state(facts, i) == "unknown"],
                 selected_action=next((r["id"] for r in ranked if r["status"] == "executable"), None))
    return trace


def route_tree(artifact: dict, context: dict, override=None) -> dict:
    validate_artifact(artifact)
    if artifact["owner"] == "diagnosis":
        raise GraphError("诊断图不能当知识树路由")
    facts = _evidence(context)
    effective = apply_override(artifact, override)
    nodes = {r["id"]: r for r in effective["records"]}
    root = next(r for r in nodes.values() if r["parent"] is None)
    results = []
    considered = []

    def visit(node, path, score, inherited_missing):
        if node["kind"] != "router":
            results.append({"id": node["id"], "version": node["version"], "path": path,
                            "score": score, "missing": sorted(set(inherited_missing)),
                            "status": "needs_evidence" if inherited_missing else "reference_ready", "snapshot": node})
            return
        matched = []
        for route in node["routes"]:
            if route["fallback"]:
                continue
            target = nodes[route["target"]]
            attrs = context.get("attributes", {})
            ok = (target["status"] == "active" and _in_scope(target, attrs)
                  and all(_matches(attrs, c) is True for c in route["match"])
                  and not any(_matches(attrs, c) is True for c in route["exclude"]))
            considered.append({"router": node["id"], "target": target["id"], "matched": ok, "prior_score": route["prior_score"]})
            if ok:
                matched.append(route)
        if not matched:
            matched = [r for r in node["routes"] if r["fallback"]]
        for route in sorted(matched, key=lambda r: (-r["prior_score"], r["target"])):
            missing = inherited_missing + [k for k in route["required_evidence"] if _state(facts, k) is not True]
            visit(nodes[route["target"]], path + [route["target"]], score + route["prior_score"], missing)

    visit(root, [root["id"]], 0, [])
    trace = _trace(artifact, context, override)
    trace.update(matches=sorted(results, key=lambda r: (-r["score"], r["id"])), considered=considered)
    return trace


def link_result(c1: dict, c2: dict, c3: dict, timing: dict) -> dict:
    """关联角色选择与统一计时，不把相关性生成旧 episode 奖励。"""
    chain = [c1, c2, c3]
    package = _release_root()
    for index, item in enumerate(chain, 1):
        validate_schema(package, "knowledge-handoff", item)
        if item.get("schema_version") != "aprof.handoff/v2" or item.get("stage") != f"C{index}":
            raise GraphError("需要独立版本的 C1/C2/C3 handoff")
        if item.get("task_id") != c1.get("task_id") or item.get("candidate_id") not in (None, c3.get("candidate_id")):
            raise GraphError("handoff 的任务或候选不一致")
        if index > 1 and item.get("parent_hash") != content_hash(chain[index - 2]):
            raise GraphError("handoff 父记录 hash 不匹配")
        owner = ["diagnosis", "parallel-planning", "optimization"][index - 1]
        if item.get("route", {}).get("owner") != owner or item["route"].get("schema_version") != ROUTE_SCHEMA:
            raise GraphError("handoff route 的角色或版本不匹配")
        if item["route"].get("task_id") != item["task_id"]:
            raise GraphError("route 属于其他任务")
        trace = item["route"]
        _evidence(trace["context_snapshot"])
        if trace["context_hash"] != content_hash(trace["context_snapshot"]) or trace["evidence"] != trace["context_snapshot"]["facts"]:
            raise GraphError("route 的证据快照或 context hash 不匹配")
    recommended = {a["id"] for a in c1["route"]["actions"]}
    chosen, executed = c2["selected_actions"], c3["executed_actions"]
    if not set(chosen) <= recommended or not set(executed) <= set(chosen):
        raise GraphError("实际执行必须属于规划选择；规划选择必须引用诊断快照")
    executable = {a["id"] for a in c1["route"]["actions"] if a["status"] == "executable"}
    if not set(executed) <= executable or c3["plan_compliance"] != "compliant":
        raise GraphError("硬前提未满足或需重规划的动作不能标记为已执行")
    for item in (c2, c3):
        ready = {m["id"] for m in item["route"]["matches"] if m["status"] == "reference_ready"}
        if not item["selected_entries"] or not set(item["selected_entries"]) <= ready:
            raise GraphError("实际采用条目必须来自满足证据要求的路由路径")
    if not all(timing.get(key) for key in ("path", "sha256", "candidate_id", "protocol")) or timing["candidate_id"] != c3["candidate_id"] or timing["protocol"] != "single_role_l2_clean_task_v1":
        raise GraphError("需要相同候选的统一计时结果引用")
    return {"schema_version": "aprof.knowledge-outcome/v1", "task_id": c1["task_id"],
            "candidate_id": c3["candidate_id"], "handoff_hashes": [content_hash(c) for c in chain],
            "recommended_actions": sorted(recommended), "selected_actions": chosen,
            "executed_actions": executed, "timing_result": timing, "causal_claim": False,
            "legacy_episode_eligible": False}

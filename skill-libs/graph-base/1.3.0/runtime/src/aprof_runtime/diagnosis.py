"""独立的诊断知识编译与检索；旧图和旧知识树仍由原运行时回放。"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

import yaml

from .errors import GraphError
from .jsonio import content_hash
from .knowledge import UniqueSafeLoader, digest, local, validate_schema, write_json, _evidence
from .measurement_admission import _release_root

REGION = "skills/ascendc-aprof-diagnosis/graph"
SCHEMA = "aprof.diagnosis-graph/v1"
SCHEMA_NAMES = ("diagnosis-record", "diagnosis-region", "diagnosis-graph")


def _root(root=None):
    return Path(root).resolve() if root is not None else _release_root()


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise GraphError(f"无法读取诊断JSON: {path}: {exc}") from exc


def _source(root, source, allowed_revisions, historical):
    path = local(root, source["path"])
    raw = path.read_bytes()
    if digest(raw) != source["sha256"]:
        raise GraphError(f"来源 hash 不符: {source['path']}")
    lines = raw.decode().splitlines(keepends=True)
    start, end = source["lines"]
    if not 1 <= start <= end <= len(lines):
        raise GraphError(f"来源行号无效: {source['path']}")
    if digest("".join(lines[start - 1:end]).encode()) != source["excerpt_sha256"]:
        raise GraphError(f"来源片段 hash 不符: {source['path']}")
    identity = (source["path"], source["revision"], source["sha256"])
    if identity not in historical:
        parts = Path(source["path"]).parts
        matches = [i for i, part in enumerate(parts) if part == "sources" and i + 2 < len(parts)]
        if not matches:
            raise GraphError(f"新增来源缺少 repo/revision 固定身份: {source['path']}")
        offset = matches[-1]
        repo, revision = parts[offset + 1:offset + 3]
        if allowed_revisions.get(repo) != revision or source["revision"] != revision:
            raise GraphError(f"新增来源未绑定声明的固定 revision: {source['path']}")
        license_path = Path(*parts[:offset + 3]) / "LICENSE"
        license_file = local(root, license_path.as_posix())
        if not license_file.is_file():
            raise GraphError(f"新增来源缺少完整 LICENSE: {repo}")
        declared = _read(root / "workflows/references/knowledge-sources-1.3.0.json")
        suffix = f"/sources/{repo}/{revision}/{source['original_path']}"
        expected = {item["sha256"] for item in declared["archived_files"] if item["path"].endswith(suffix)}
        license_suffix = f"/sources/{repo}/{revision}/LICENSE"
        licenses = {item["sha256"] for item in declared["archived_files"] if item["path"].endswith(license_suffix)}
        if source["sha256"] not in expected or digest(license_file.read_bytes()) not in licenses:
            raise GraphError(f"新增来源/许可与固定来源清单不符: {source['path']}")
    return source["path"], digest(raw)


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"v[0-9]{4}", value):
        raise GraphError("诊断图版本必须为 vNNNN")
    return int(value[1:])


def _check_parent(child, parent):
    if _version(child) < 4 or (child == "v0004" and parent != "v0003") or (child != "v0004" and not 4 <= _version(parent) < _version(child)):
        raise GraphError("v0004 必须绑定父 v0003；后续诊断图必须显式绑定较低版本的新快照")


def _lineage(artifact):
    return {"parent_graph_version": artifact["parent"]["graph_version"], "parent_graph_ref": artifact["parent"]["graph_ref"], "semantics": "agent_reasoning_no_automatic_score_v1"}


def _manifest(version, graph_path):
    return {"graph_version": version, "immutable": True, "graph_sha256": digest(graph_path.read_bytes()).removeprefix("sha256:"), "files": {"graph": "graph.json", "lineage": "lineage.json", "checksums": "checksums.json"}}


def _parent(root, snapshot):
    snapshot = Path(snapshot)
    if not snapshot.is_absolute():
        snapshot = local(root, snapshot.as_posix())
    graph_path = snapshot / "graph.json" if snapshot.is_dir() else snapshot
    if not graph_path.resolve().is_relative_to(root.resolve()):
        raise GraphError("父快照必须位于包内")
    local(root, graph_path.relative_to(root).as_posix())
    graph = _read(graph_path)
    version = graph.get("version")
    if graph.get("graph_version") != version or _version(version) < 3:
        raise GraphError("父快照版本/身份无效")
    if version == "v0003":
        if graph.get("schema_version") != "aprof.knowledge/v1" or graph.get("owner") != "diagnosis":
            raise GraphError("父 v0003 必须为冻结的历史诊断图")
    else:
        validate_artifact(graph, root)
    checksums = _read(graph_path.parent / "checksums.json")
    if set(checksums) != {"algorithm", "files"} or checksums["algorithm"] != "sha256" or set(checksums["files"]) != {"graph.json", "lineage.json", "manifest.json"}:
        raise GraphError("父快照 checksums 不完整")
    if checksums.get("files", {}).get("graph.json") != digest(graph_path.read_bytes()).removeprefix("sha256:"):
        raise GraphError("父 v0003 graph.json 文件 hash 不匹配")
    for name, expected in checksums.get("files", {}).items():
        file = local(graph_path.parent, name)
        if digest(file.read_bytes()).removeprefix("sha256:") != expected:
            raise GraphError(f"父快照校验失败: {name}")
    manifest = _read(graph_path.parent / "manifest.json")
    if manifest != _manifest(version, graph_path):
        raise GraphError("父快照 manifest 不匹配")
    if version != "v0003" and _read(graph_path.parent / "lineage.json") != _lineage(graph):
        raise GraphError("父快照 lineage 不匹配")
    return graph, {"graph_version": version, "graph_ref": {"path": graph_path.relative_to(root).as_posix(), "sha256": digest(graph_path.read_bytes())}}


def _validate_records(records, parent=None):
    nodes = {r["id"]: r for r in records}
    if len(nodes) != len(records):
        raise GraphError("诊断知识 ID 重复")
    signatures = set()
    component_ids = set()
    for record in records:
        identifier = record["id"]
        slots = [s["name"] for s in record["slots"]]
        if len(set(slots)) != len(slots):
            raise GraphError(f"重复 slot: {identifier}")
        claims = [c["id"] for c in record["claims"]]
        if len(claims) != len(set(claims)):
            raise GraphError(f"重复 claim: {identifier}")
        for claim in record["claims"]:
            if any(i >= len(record["sources"]) for i in claim["source_indexes"]):
                raise GraphError(f"claim 来源索引越界: {identifier}")
            if claim["basis"] == "case_support" and not claim.get("case_refs"):
                raise GraphError("case_support 必须绑定非空且可验证的 claim.case_refs")
            if claim["basis"] in {"source_statement", "code_fact"} and not claim["source_indexes"]:
                raise GraphError(f"来源事实必须有来源索引: {identifier}")
        if record["kind"] == "problem":
            for alternative in record["analysis"]["alternatives"]:
                if alternative["problem_id"] is not None and nodes.get(alternative["problem_id"], {}).get("kind") != "problem":
                    raise GraphError(f"替代机制引用不存在: {identifier}")
            if any(nodes.get(a["action_id"], {}).get("kind") != "action" for a in record["analysis"]["actions"]):
                raise GraphError(f"机制引用未注册动作: {identifier}")
        if record["kind"] == "symptom":
            if not set(record["observation"]["object_slots"]) <= set(slots):
                raise GraphError(f"观察引用未知 slot: {identifier}")
            required_ids = [c["id"] for c in record["observation"]["required_components"]]
            if len(required_ids) != len(set(required_ids)) or component_ids & set(required_ids) or set(required_ids) & set(nodes):
                raise GraphError(f"复合观察组件ID必须全局唯一且独立于模板ID: {identifier}")
            component_ids.update(required_ids)
        if record["kind"] == "action" and not set(record["instantiation"]["target_slots"] + record["instantiation"]["required_bindings"]) <= set(slots):
            raise GraphError(f"动作引用未知 slot: {identifier}")
        if record["kind"] != "edge":
            continue
        relation = record["relation"]
        kinds = ("problem", "action") if relation == "mitigated_by" else ("symptom", "problem") if relation in {"supports", "refutes"} else ("problem", "problem")
        if any(nodes.get(record[key], {}).get("kind") != kind for key, kind in zip(("from", "to"), kinds)):
            raise GraphError(f"悬空或错误类型的边: {identifier}")
        sig = (record["from"], record["to"], relation, json.dumps(record["conditions"], sort_keys=True))
        if sig in signatures:
            raise GraphError(f"重复关系: {identifier}")
        signatures.add(sig)
        for binding in record["binding"]["object_bindings"]:
            if binding["from_slot"] not in {s["name"] for s in nodes[record["from"]]["slots"]} or binding["to_slot"] not in {s["name"] for s in nodes[record["to"]]["slots"]}:
                raise GraphError(f"边绑定引用未知 slot: {identifier}")
        if kinds == ("problem", "problem") and not any(c["basis"] == "mechanism_inference" for c in record["claims"]):
            raise GraphError("额外机制关系必须标记 mechanism_inference")
    if parent is not None:
        for old in parent["records"]:
            new = nodes.get(old["id"])
            if new is None or new["kind"] != old["kind"] or new["learning"] != old["learning"]:
                raise GraphError(f"迁移丢失历史 ID/类型/初值: {old['id']}")
            for key in (("preconditions", "invariants") if old["kind"] == "action" else ("relation", "from", "to") if old["kind"] == "edge" else ()):
                if new[key] != old[key]:
                    raise GraphError(f"迁移改变历史 {key}: {old['id']}")


def compile_region(root: Path, parent_snapshot: Path) -> dict:
    root = _root(root)
    parent, parent_ref = _parent(root, parent_snapshot)
    region = root / REGION
    identity = _read(region / "REGION.json")
    validate_schema(root, "diagnosis-region", identity)
    _check_parent(identity["version"], parent_ref["graph_version"])
    declared = _read(root / "workflows/references/knowledge-sources-1.3.0.json")
    revisions = {r["repo"]: r["revision"] for r in declared["repositories"]}
    historical = {(s["path"], s["revision"], s["sha256"]) for r in parent["records"] for s in r["sources"]}
    records, hashes = [], {}
    for folder in ("symptoms", "problems", "actions", "edges"):
        for path in sorted((region / folder).rglob("*.md")):
            local(root, path.relative_to(root).as_posix())
            text = path.read_text()
            if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                raise GraphError(f"缺少 YAML frontmatter: {path}")
            header, body = text[4:].split("\n---\n", 1)
            try:
                record = yaml.load(header, Loader=UniqueSafeLoader)
            except yaml.YAMLError as exc:
                raise GraphError(f"无法解析诊断知识: {path}") from exc
            validate_schema(root, "diagnosis-record", record)
            from .diagnosis_reasoning import _validate_claims
            _validate_claims(root, record)
            if not body.strip():
                raise GraphError(f"诊断知识正文为空: {path}")
            for source in record["sources"]:
                name, value = _source(root, source, revisions, historical)
                hashes[name] = value
            record.update(body=body.strip(), source_path=path.relative_to(root).as_posix(), source_hash=digest(path.read_bytes()))
            hashes[record["source_path"]] = record["source_hash"]
            records.append(record)
    if not records:
        raise GraphError("诊断知识区为空")
    _validate_records(records, parent)
    # Include unreferenced source files too: changing a license or copied source invalidates the build.
    for source_directory in (region / "sources", region.parent / "sources"):
        for path in sorted(source_directory.rglob("*")):
            if path.is_file():
                name = path.relative_to(root).as_posix()
                hashes[name] = digest(local(root, name).read_bytes())
    for name in (f"{REGION}/REGION.json", "workflows/references/knowledge-sources-1.3.0.json"):
        hashes[name] = digest(local(root, name).read_bytes())
    artifact = {"schema_version": SCHEMA, "owner": "diagnosis", "version": identity["version"], "graph_version": identity["version"], "parent": parent_ref,
                "generator": {"id": "aprof_runtime.diagnosis/v1", "sha256": digest(Path(__file__).read_bytes()), "schema_hashes": {n: digest((root / f"schemas/{n}.schema.json").read_bytes()) for n in SCHEMA_NAMES}},
                "source_hashes": dict(sorted(hashes.items())), "records": sorted(records, key=lambda r: r["id"])}
    validate_schema(root, "diagnosis-graph", artifact)
    return artifact


def artifact_path(root):
    root = _root(root)
    identity = _read(root / REGION / "REGION.json")
    validate_schema(root, "diagnosis-region", identity)
    return root / REGION / f"versions/{identity['version']}/graph.json"


def build(root: Path, parent_snapshot: Path) -> dict:
    root = _root(root)
    if (root / "release.json").exists():
        raise GraphError("不能重建已发布包")
    artifact = compile_region(root, parent_snapshot)
    directory = artifact_path(root).parent
    if directory.exists():
        raise GraphError("诊断快照不可覆盖；必须使用未存在的新版本")
    directory.mkdir(parents=True)
    write_json(directory / "graph.json", artifact)
    write_json(directory / "lineage.json", _lineage(artifact))
    write_json(directory / "manifest.json", _manifest(artifact["version"], directory / "graph.json"))
    write_json(directory / "checksums.json", {"algorithm": "sha256", "files": {name: digest((directory / name).read_bytes()).removeprefix("sha256:") for name in ("graph.json", "lineage.json", "manifest.json")}})
    return artifact


def validate_artifact(artifact: dict, root=None) -> dict:
    root = _root(root)
    validate_schema(root, "diagnosis-graph", artifact)
    if artifact["version"] != artifact["graph_version"]:
        raise GraphError("诊断图 version/graph_version 不一致")
    _check_parent(artifact["version"], artifact["parent"]["graph_version"])
    _validate_records(artifact["records"])
    from .diagnosis_reasoning import _validate_claims
    for record in artifact["records"]:
        _validate_claims(root, record)
        if artifact["source_hashes"].get(record["source_path"]) != record["source_hash"]:
            raise GraphError("诊断记录源 hash 与清单不一致")
    return artifact


def verify_snapshot(root: Path, snapshot: Path) -> dict:
    root = _root(root)
    snapshot = Path(snapshot)
    directory = (root / snapshot if not snapshot.is_absolute() else snapshot)
    if directory.is_file():
        directory = directory.parent
    if not directory.resolve().is_relative_to(root):
        raise GraphError("诊断快照路径越出知识包")
    local(root, directory.relative_to(root).as_posix())
    artifact = validate_artifact(_read(directory / "graph.json"), root)
    checksums = _read(directory / "checksums.json")
    if set(checksums) != {"algorithm", "files"} or checksums["algorithm"] != "sha256" or set(checksums["files"]) != {"graph.json", "lineage.json", "manifest.json"}:
        raise GraphError("诊断快照 checksums 不完整")
    for name, expected in checksums["files"].items():
        if digest(local(directory, name).read_bytes()).removeprefix("sha256:") != expected:
            raise GraphError(f"诊断快照 hash 不匹配: {name}")
    manifest = _read(directory / "manifest.json")
    if manifest != _manifest(artifact["version"], directory / "graph.json"):
        raise GraphError("诊断快照 manifest 不匹配")
    parent, parent_ref = _parent(root, artifact["parent"]["graph_ref"]["path"])
    if parent_ref != artifact["parent"]:
        raise GraphError("诊断快照父引用不匹配")
    lineage = _read(directory / "lineage.json")
    if lineage != _lineage(artifact):
        raise GraphError("诊断 lineage 父引用不匹配")
    _validate_records(artifact["records"], parent)
    live_metadata = {r["source_path"] for r in artifact["records"]} | {f"{REGION}/REGION.json"}
    for name, expected in artifact["source_hashes"].items():
        if name not in live_metadata and digest(local(root, name).read_bytes()) != expected:
            raise GraphError(f"诊断来源已改变: {name}")
    return artifact


def verify(root: Path) -> dict:
    root = _root(root)
    artifact = verify_snapshot(root, artifact_path(root))
    if compile_region(root, artifact["parent"]["graph_ref"]["path"]) != artifact:
        raise GraphError("诊断构建产物已过期或被修改")
    return artifact


def retrieve(artifact: dict, context: dict, root=None) -> dict:
    """检索实现独立于模板编译器，检索调整不改变知识生成器身份。"""
    from .diagnosis_retrieval import retrieve as retrieve_candidates
    return retrieve_candidates(artifact, context, root)

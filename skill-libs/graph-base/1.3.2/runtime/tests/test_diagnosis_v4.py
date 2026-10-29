from aprof_runtime.documentation_sources import original_path as evidence_original
"""CPU-only boundary checks for the independently versioned diagnosis runtime."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
import yaml

from aprof_runtime import diagnosis
from aprof_runtime.diagnosis_reasoning import (
    action_status, fact_state, profile_time_known, proposal_basis_hash, validate_case, validate_proposal, validate_reasoning,
)
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash
from aprof_runtime.knowledge import digest

ROOT = Path(__file__).resolve().parents[2]
PARENT = Path(diagnosis.REGION) / "versions/v0003"
HASH = digest(b"fixture")


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    """Use the frozen parent as an independent migration fixture, never rewrite the package."""
    root = tmp_path_factory.mktemp("diagnosis-package")
    (root / "schemas").mkdir()
    for name in diagnosis.SCHEMA_NAMES + ("diagnosis-retrieval", "diagnosis-reasoning", "diagnosis-case", "diagnosis-proposal", "diagnosis-proposal-review", "diagnosis-proposal-validation", "diagnosis-case-review"):
        shutil.copy(ROOT / f"schemas/{name}.schema.json", root / "schemas")
    shutil.copytree(ROOT / PARENT, root / PARENT)
    manifest = Path("workflows/references/knowledge-sources-1.3.0.json")
    (root / manifest).parent.mkdir(parents=True)
    shutil.copy(ROOT / manifest, root / manifest)
    parent = json.loads((root / PARENT / "graph.json").read_text())
    region = root / diagnosis.REGION
    (region / "REGION.json").write_text(json.dumps({"schema_version": "aprof.diagnosis-region/v1", "owner": "diagnosis", "version": "v0004"}))
    for old in parent["records"]:
        record = {k: deepcopy(v) for k, v in old.items() if k not in {"body", "source_path", "source_hash"}}
        record["schema_version"] = "aprof.diagnosis-record/v1"
        record["slots"] = [{"name": "target", "kind": "object", "description": "当前目标", "required": True}]
        record["claims"] = [{"id": "historical", "text": "历史来源只用于可核验线索", "basis": "legacy_seed", "source_indexes": [0], "review_status": "gap", "limitations": ["本测试无硬件运行"]}]
        record["review"] = {"state": "gap", "source_credibility": "历史来源", "discriminating_power": "unknown", "observed_frequency": "unknown", "gaps": ["待当前任务验证"]}
        if record["kind"] == "symptom":
            record["observation"] = {"object_slots": ["target"], "rule": record["title"], "comparison_basis": "同目标比较", "unknown_when": ["缺数据"], "interpretation_boundary": "不能自动推断机制", "required_components": []}
        elif record["kind"] == "problem":
            record["analysis"] = {k: ["待验证"] for k in ["mechanism_chain", "objects_and_stages", "predictions", "supporting_checks", "counter_checks", "limits"]}
            record["analysis"].update(alternatives=[], actions=[])
        elif record["kind"] == "action":
            record["instantiation"] = {"target_slots": ["target"], "required_bindings": ["target"], "effect": "待验证变换", "costs": ["新增资源"], "unknown_policy": "C2条件分析", "replan_triggers": ["所有权改变"]}
        else:
            record["binding"] = {"object_bindings": [{"from_slot": "target", "to_slot": "target", "rule": "同对象"}], "joint_requirements": [], "exceptions": [], "rationale": "待证据判别", "discriminating_checks": ["对照机制"]}
        for source in record["sources"]:
            target = root / source["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(evidence_original(ROOT, source["path"]), target)
        target = root / old["source_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n\n" + old["body"] + "\n")
    loose = region / "sources/unused.txt"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text("未被摘录的来源仍须进入hash清单\n")
    artifact = diagnosis.build(root, PARENT)
    return root, artifact


def evidence(facts=None):
    return {"schema_version": "aprof.evidence/v1", "task_id": "task", "source_context_ref": {"path": "context.json", "sha256": HASH}, "attributes": {}, "facts": facts or {}}


def reasoning_fixture(artifact):
    action = next(r for r in artifact["records"] if r["kind"] == "action")
    scope = {"task_id": "task", "parent_implementation_hash": HASH, "workload_hash": HASH, "target_ids": ["tensor.x"], "stage": "kernel.main"}
    facts = {p["fact"]: {"state": p["state"], "kind": "raw", "evidence_id": p["fact"], "ref": {"path": "raw.json", "sha256": HASH, "locator": p["fact"]}, "derived_from": [], "scope": deepcopy(scope)} for p in action["preconditions"]}
    context = evidence()
    instance = {"instance_id": "instance.one", "action_id": action["id"], "template_hash": content_hash(action), "hypothesis_id": "hypothesis.one", "targets": {"target": "tensor.x"}, "scope": deepcopy(scope), "parameters": {}, "evidence_bindings": {key: key for key in facts}, "unknowns": [], "status": "ready", "reason": "全部原硬前提有绑定证据", "parent_plan_hash": None}
    candidate = {"hypothesis_id": "hypothesis.one", "problem_id": None, "mechanism": "临时机制可复用已注册A", "targets": ["tensor.x"], "scope": deepcopy(scope), "support": list(facts), "counter": [], "unknown": [], "alternatives": [], "checks": ["后续真实profile区分"], "status": "plausible", "reason": "任务内临时Problem", "excluded_by": [], "independent_evidence_groups": []}
    reasoning = {"schema_version": "aprof.diagnosis-reasoning/v1", "task_id": "task", "context_hash": content_hash(context), "knowledge_hash": content_hash(artifact), "source_context_ref": context["source_context_ref"], "context_snapshot": context, "current": {"implementation_ref": {"path": "parent.cpp", "sha256": HASH}, "workload_ref": {"path": "workload.json", "sha256": HASH}, "objects": [{"object_id": "tensor.x", "kind": "tensor", "description": "输入目标"}], "scope": scope}, "facts": facts, "candidates": [candidate], "action_instances": [instance], "predecessor_ref": None}
    return reasoning


def test_compile_verify_and_history_cannot_be_overwritten(package):
    root, artifact = package
    assert diagnosis.compile_region(root, PARENT) == artifact
    assert diagnosis.verify(root) == artifact
    assert diagnosis.verify_snapshot(root, diagnosis.artifact_path(root)) == artifact
    assert len(artifact["records"]) == 195
    assert artifact["parent"]["graph_ref"]["sha256"] == digest((root / PARENT / "graph.json").read_bytes())
    with pytest.raises(GraphError, match="不可覆盖"):
        diagnosis.build(root, PARENT)


def test_full_directory_and_no_automatic_decision(package):
    root, artifact = package
    result = diagnosis.retrieve(artifact, evidence(), root)
    assert len(result["problem_directory"]) == 28
    assert len(result["observations"]) == 55
    assert result["symptom_adjacency"] == []
    assert all(row["mechanism_summary"] and "alternatives" in row for row in result["problem_directory"])
    matched = diagnosis.retrieve(artifact, evidence({"symptom.source.inner_loop_copy": {
        "state": True, "kind": "source_review", "evidence_id": "copy", "ref": {"path": "source.cpp", "sha256": HASH, "locator": "copy"}}}), root)
    assert matched["symptom_adjacency"] and all(edge["symptom_id"] == "symptom.source.inner_loop_copy" for edge in matched["symptom_adjacency"])
    assert all("claims" not in edge and edge["condition_state"] == "not_evaluated" for edge in matched["symptom_adjacency"])
    assert "selected_action" not in result and "score" not in result
    assert all(o["state"] == "unknown" for o in result["observations"])
    assert all(e["legacy_prior"]["role"] == "uncalibrated_auxiliary_only" for e in result["symptom_adjacency"])


def test_retrieval_rejects_malformed_scope_attributes(package):
    root, artifact = package
    context = evidence()
    context["attributes"]["family"] = {"pretend": "matmul"}
    with pytest.raises(GraphError, match="字符串"):
        diagnosis.retrieve(artifact, context, root)


def test_all_source_files_are_bound_and_parent_hash_is_checked(package):
    root, artifact = package
    path = root / diagnosis.REGION / "sources/unused.txt"
    previous = path.read_bytes()
    try:
        path.write_text("篡改未引用source")
        with pytest.raises(GraphError, match="来源已改变"):
            diagnosis.verify(root)
    finally:
        path.write_bytes(previous)
    altered = deepcopy(artifact)
    altered["parent"]["graph_ref"]["sha256"] = digest(b"different parent")
    assert altered != artifact


def test_strict_nested_record_and_reasoning_fields(package):
    root, artifact = package
    altered = deepcopy(artifact)
    altered["records"][0]["claims"][0]["confidence"] = 0.99
    with pytest.raises(GraphError, match="Additional properties"):
        diagnosis.validate_artifact(altered, root)
    reasoning = reasoning_fixture(artifact)
    reasoning["action_instances"][0]["targets"]["unknown_slot"] = "tensor.x"
    with pytest.raises(GraphError, match="slot"):
        validate_reasoning(root, reasoning, artifact)


def test_temporary_problem_reuses_registered_action_and_false_preconditions(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    assert validate_reasoning(root, reasoning, artifact) is reasoning
    altered = deepcopy(artifact)
    action = next(r for r in altered["records"] if r["id"] == reasoning["action_instances"][0]["action_id"])
    action["preconditions"][0]["state"] = False
    condition = action["preconditions"][0]["fact"]
    reasoning["facts"][condition]["state"] = False
    reasoning["knowledge_hash"] = content_hash(altered)
    reasoning["action_instances"][0]["template_hash"] = content_hash(action)
    assert action_status(root, reasoning, reasoning["action_instances"][0], altered)["status"] == "ready"
    validate_reasoning(root, reasoning, altered)
    reasoning["facts"][condition]["state"] = True
    assert action_status(root, reasoning, reasoning["action_instances"][0], altered)["failed"] == [condition]
    with pytest.raises(GraphError, match="硬前提"):
        validate_reasoning(root, reasoning, altered)


def test_unknown_and_proxy_only_allow_conditional_analysis(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    key = next(iter(reasoning["facts"]))
    reasoning["facts"][key]["kind"] = "proxy"
    reasoning["candidates"][0]["support"].remove(key)
    reasoning["candidates"][0]["unknown"].append(key)
    instance = reasoning["action_instances"][0]
    with pytest.raises(GraphError, match="unknown"):
        validate_reasoning(root, reasoning, artifact)
    instance["status"], instance["unknowns"] = "conditional", [key]
    validate_reasoning(root, reasoning, artifact)
    assert action_status(root, reasoning, instance, artifact)["status"] == "conditional"


def test_scope_binding_and_tampered_template_are_rejected(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    reasoning["action_instances"][0]["template_hash"] = digest(b"tampered")
    with pytest.raises(GraphError, match="template_hash"):
        validate_reasoning(root, reasoning, artifact)
    reasoning = reasoning_fixture(artifact)
    next(iter(reasoning["facts"].values()))["scope"]["target_ids"] = ["other.tensor"]
    with pytest.raises(GraphError, match="目标"):
        validate_reasoning(root, reasoning, artifact)


def test_duplicate_raw_evidence_cannot_claim_independence(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    a, b = list(reasoning["facts"])[:2]
    reasoning["facts"][b]["ref"] = deepcopy(reasoning["facts"][a]["ref"])
    reasoning["candidates"][0]["independent_evidence_groups"] = [[a], [b]]
    with pytest.raises(GraphError, match="独立证据"):
        validate_reasoning(root, reasoning, artifact)
    reasoning["candidates"][0]["independent_evidence_groups"] = [[a, b]]
    validate_reasoning(root, reasoning, artifact)


def test_derived_cycles_and_all_of_unknown_false_semantics(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    keys = list(reasoning["facts"])[:2]
    fact = {"state": True, "kind": "derived", "evidence_id": None, "ref": None, "derived_from": keys, "components": keys, "scope": deepcopy(reasoning["current"]["scope"])}
    reasoning["facts"]["joint"] = fact
    validate_reasoning(root, reasoning, artifact)
    reasoning["facts"][keys[0]]["state"] = "unknown"
    assert fact_state(reasoning, "joint") == "unknown"
    reasoning["facts"][keys[1]]["state"] = False
    assert fact_state(reasoning, "joint") is False
    fact["derived_from"] = ["joint"]
    fact["components"] = ["joint"]
    with pytest.raises(GraphError, match="成环"):
        validate_reasoning(root, reasoning, artifact)


def test_paper_case_cannot_produce_case_support(package):
    root, artifact = package
    source = next(r["sources"][0] for r in artifact["records"])
    record = {"schema_version": "aprof.diagnosis-case/v1", "case_id": "paper.case", "evidence_status": "paper", "task_id": "task", "scope": reasoning_fixture(artifact)["current"]["scope"], "context_ref": None, "reasoning_ref": None, "sources": [source], "observations": ["纸面观察"], "candidate_explanations": ["候选机制"], "selected_action_instances": [], "outcome": {"status": "not_run", "timing_ref": None, "correctness_ref": None, "mechanism_refs": [], "limitations": ["本轮未运行"]}, "claims": [], "review": {"reviewer": "fixture", "independent": False, "decision": "pending", "notes": []}}
    validate_case(root, record)
    record["claims"] = [{"id": "fake", "text": "合成记录不是已验证案例", "basis": "case_support", "source_indexes": [0], "review_status": "gap", "limitations": []}]
    with pytest.raises(GraphError, match="case_support"):
        validate_case(root, record)


def test_source_only_evidence_cannot_become_profile_fact(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    key = next(iter(reasoning["facts"]))
    reasoning["facts"][key]["view"] = "source"
    reasoning["facts"]["profile.story"] = {"state": True, "kind": "derived", "view": "profile", "evidence_id": None, "ref": None, "derived_from": [key], "scope": deepcopy(reasoning["current"]["scope"])}
    with pytest.raises(GraphError, match="source 与 profile"):
        validate_reasoning(root, reasoning, artifact)


def test_parent_snapshot_tamper_and_unpinned_revision_are_rejected(package):
    root, artifact = package
    parent_file = root / PARENT / "graph.json"
    original = parent_file.read_bytes()
    try:
        parent_file.write_bytes(original + b"\n")
        with pytest.raises(GraphError, match="父 v0003"):
            diagnosis.verify(root)
    finally:
        parent_file.write_bytes(original)
    path = root / artifact["records"][0]["source_path"]
    original = path.read_bytes()
    text = original.decode()
    header, body = text[4:].split("\n---\n", 1)
    record = yaml.safe_load(header)
    record["sources"][0]["revision"] = "master"
    try:
        path.write_text("---\n" + yaml.safe_dump(record, allow_unicode=True) + "---\n" + body)
        with pytest.raises(GraphError, match="固定"):
            diagnosis.compile_region(root, PARENT)
    finally:
        path.write_bytes(original)


def test_pending_proposal_is_not_automatically_promoted(package, tmp_path):
    root, artifact = package
    source = deepcopy(artifact["records"][0]["sources"][0])
    proposal = {"schema_version": "aprof.diagnosis-proposal/v1", "proposal_id": "proposal.one", "kind": "problem", "status": "pending", "title": "待独立审阅机制", "rationale": "只登记缺口", "scope": artifact["records"][0]["scope"], "sources": [source], "claims": [], "case_refs": [], "semantic_dedup": {"compared_ids": [], "distinct_from_existing": False, "reason": "待比较"}, "contract_check": {"status": "pending", "notes": []}, "review": {"reviewer": "unassigned", "independent": False, "decision": "pending", "notes": []}, "promotion": {"eligible": False, "automatic": False, "target_version": None}, "proposed_record": None, "proposed_relations": [], "validation_refs": [], "review_ref": None}
    assert validate_proposal(root, proposal, task_root=tmp_path) is proposal
    proposal["promotion"]["automatic"] = True
    with pytest.raises(GraphError, match="False was expected"):
        validate_proposal(root, proposal)
    proposal["promotion"]["automatic"] = False
    proposal["promotion"]["eligible"] = True
    with pytest.raises(GraphError, match="完整模板草稿"):
        validate_proposal(root, proposal)


def test_case_task_artifacts_are_relative_to_task_root(package, tmp_path):
    root, artifact = package
    source = artifact["records"][0]["sources"][0]
    (tmp_path / "context.json").write_text('{"task_id":"task"}')
    ref = {"path": "context.json", "sha256": digest((tmp_path / "context.json").read_bytes())}
    record = {"schema_version": "aprof.diagnosis-case/v1", "case_id": "paper.task", "evidence_status": "paper", "task_id": "task", "scope": reasoning_fixture(artifact)["current"]["scope"], "context_ref": ref, "reasoning_ref": None, "sources": [source], "observations": [], "candidate_explanations": [], "selected_action_instances": [], "outcome": {"status": "not_run", "timing_ref": None, "correctness_ref": None, "mechanism_refs": [], "limitations": []}, "claims": [], "review": {"reviewer": "fixture", "independent": False, "decision": "pending", "notes": []}}
    validate_case(root, record, task_root=tmp_path)
    record["context_ref"]["sha256"] = HASH
    with pytest.raises(GraphError, match="hash"):
        validate_case(root, record, task_root=tmp_path)


def test_action_preconditions_cannot_borrow_unrelated_true_fact(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    first, second = list(reasoning["facts"])[:2]
    instance = reasoning["action_instances"][0]
    instance["evidence_bindings"][first] = second
    with pytest.raises(GraphError, match="predicate"):
        validate_reasoning(root, reasoning, artifact)
    alias = "observed.for.this.target"
    reasoning["facts"][alias] = deepcopy(reasoning["facts"][first])
    instance["evidence_bindings"][first] = alias
    with pytest.raises(GraphError, match="predicate"):
        validate_reasoning(root, reasoning, artifact)
    reasoning["facts"][alias]["predicate"] = first
    validate_reasoning(root, reasoning, artifact)


def copy_condition_policy(future, artifact):
    v4 = Path(diagnosis.REGION) / "versions/v0004"
    # 后继版本须显式声明条件去向；本例仅变正文，全部前提仍保持安全分类。
    policy = json.loads((ROOT / "workflows/references/action-condition-policies/v0001.json").read_text())
    policy["legacy_graph_ref"].update(path=str(v4 / "graph.json"),
        file_sha256=digest((future / v4 / "graph.json").read_bytes()), graph_sha256=content_hash(artifact))
    actions = {r["id"]: r for r in artifact["records"] if r["kind"] == "action"}
    for row in policy["actions"]:
        original = actions[row["action_id"]]["preconditions"]
        row["legacy_preconditions"] = deepcopy(original)
        row["safety_conditions"] = [dict(c, kind="structural_applicability", reason="本测试保持原义") for c in original]
        row["performance_hypotheses"] = [h for h in row["performance_hypotheses"] if h["legacy_condition"] is None]
        row["added_safety_predicates"] = []
        row["legacy_dispositions"] = [dict(c, destination="safety_conditions", reason="本测试保持原义") for c in original]
    raw = json.dumps(policy, ensure_ascii=False)
    policy_path = future / "workflows/references/action-condition-policy.json"
    policy_path.write_text(raw)
    frozen = future / "workflows/references/action-condition-policies/v0001.json"
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_text(raw)
    shutil.copy(ROOT / "schemas/action-condition-policy.schema.json", future / "schemas")


def test_future_version_uses_explicit_lower_parent_and_replays_v4(package, tmp_path):
    root, artifact = package
    future = tmp_path / "future"
    shutil.copytree(root, future)
    region = future / diagnosis.REGION
    identity = {"schema_version": "aprof.diagnosis-region/v1", "owner": "diagnosis", "version": "v0005"}
    (region / "REGION.json").write_text(json.dumps(identity))
    source = future / artifact["records"][0]["source_path"]
    source.write_text(source.read_text() + "\n后继版本新增说明；旧快照保留原正文。\n")
    v4 = Path(diagnosis.REGION) / "versions/v0004"
    assert diagnosis.verify_snapshot(future, v4) == artifact
    copy_condition_policy(future, artifact)
    result = diagnosis.build(future, v4)
    assert result["version"] == "v0005"
    assert result["parent"]["graph_version"] == "v0004"
    assert result["parent"]["graph_ref"]["sha256"] == digest((future / v4 / "graph.json").read_bytes())
    assert diagnosis.verify(future) == result
    with pytest.raises(GraphError, match="较低版本"):
        diagnosis.compile_region(future, Path(diagnosis.REGION) / "versions/v0005")


def test_new_source_and_license_are_pinned_to_declared_repo_revision(tmp_path):
    manifest_path = Path("workflows/references/knowledge-sources-1.3.0.json")
    manifest = json.loads((ROOT / manifest_path).read_text())
    revision_map = {r["repo"]: r["revision"] for r in manifest["repositories"]}
    entry = next(i for i in manifest["archived_files"] if "/sources/asc-devkit/" in i["path"] and not i["path"].endswith("/LICENSE"))
    repo, revision = "asc-devkit", revision_map["asc-devkit"]
    original_path = entry["path"].split(f"/sources/{repo}/{revision}/", 1)[1]
    relative = Path("skills/ascendc-aprof-diagnosis/sources") / repo / revision / original_path
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    shutil.copy(evidence_original(ROOT, entry["path"]), target)
    license_entry = next(i for i in manifest["archived_files"] if i["path"].endswith(f"/sources/{repo}/{revision}/LICENSE"))
    license_path = tmp_path / f"skills/ascendc-aprof-diagnosis/sources/{repo}/{revision}/LICENSE"
    shutil.copy(ROOT / license_entry["path"], license_path)
    (tmp_path / manifest_path).parent.mkdir(parents=True)
    shutil.copy(ROOT / manifest_path, tmp_path / manifest_path)
    first = target.read_text().splitlines(keepends=True)[0]
    source = {"path": relative.as_posix(), "original_path": original_path, "revision": revision, "lines": [1, 1], "sha256": digest(target.read_bytes()), "excerpt_sha256": digest(first.encode())}
    assert diagnosis._source(tmp_path, source, revision_map, set())[1] == source["sha256"]
    license_path.write_text("不能用截断许可证冒充原始归档")
    with pytest.raises(GraphError, match="许可与固定来源清单"):
        diagnosis._source(tmp_path, source, revision_map, set())


def test_registered_symptom_cannot_bypass_template_components(package):
    root, original = package
    artifact = deepcopy(original)
    reasoning = reasoning_fixture(artifact)
    key = next(k for k in reasoning["facts"] if k.startswith("symptom."))
    template = next(r for r in artifact["records"] if r["id"] == key)
    components = [key + ".component_one", key + ".component_two"]
    template["observation"]["required_components"] = [{"id": c, "description": "当前目标必要组成观察"} for c in components]
    reasoning["knowledge_hash"] = content_hash(artifact)
    with pytest.raises(GraphError, match="全部required_components"):
        validate_reasoning(root, reasoning, artifact)
    for component in components:
        reasoning["facts"][component] = {"state": True, "kind": "raw", "evidence_id": component, "ref": {"path": "components.json", "sha256": HASH, "locator": component}, "derived_from": [], "scope": deepcopy(reasoning["current"]["scope"])}
    fact = reasoning["facts"][key]
    fact.update(kind="derived", evidence_id=None, ref=None, derived_from=components, components=components)
    validate_reasoning(root, reasoning, artifact)
    assert action_status(root, reasoning, reasoning["action_instances"][0], artifact)["status"] == "ready"
    fact["components"] = components[:1]
    with pytest.raises(GraphError, match="全部required_components"):
        validate_reasoning(root, reasoning, artifact)
    fact["components"] = components
    # Component instances can use local IDs if their canonical predicate is explicit.
    alias = "local.second.component"
    reasoning["facts"][alias] = reasoning["facts"].pop(components[1])
    reasoning["facts"][alias]["predicate"] = components[1]
    fact["components"] = [components[0], alias]
    fact["derived_from"] = [components[0], alias]
    validate_reasoning(root, reasoning, artifact)
    reasoning["facts"][components[0]]["state"] = "unknown"
    fact["state"] = "unknown"
    reasoning["candidates"][0]["support"].remove(key)
    reasoning["candidates"][0]["unknown"] = [key]
    instance = reasoning["action_instances"][0]
    instance.update(status="conditional", unknowns=[key])
    validate_reasoning(root, reasoning, artifact)
    assert action_status(root, reasoning, instance, artifact)["status"] == "conditional"
    reasoning["facts"][alias]["state"] = False
    fact["state"] = False
    reasoning["candidates"][0]["unknown"] = []
    reasoning["candidates"][0]["counter"] = [key]
    assert fact_state(reasoning, key) is False
    assert action_status(root, reasoning, instance, artifact)["status"] == "blocked"
    reasoning["action_instances"] = []
    validate_reasoning(root, reasoning, artifact)


def test_case_support_requires_real_hashed_case_not_paper(package, tmp_path):
    root, artifact = package
    source = artifact["records"][0]["sources"][0]
    record = {"schema_version": "aprof.diagnosis-case/v1", "case_id": "paper.claim", "evidence_status": "paper", "task_id": "task", "scope": reasoning_fixture(artifact)["current"]["scope"], "context_ref": None, "reasoning_ref": None, "sources": [source], "observations": [], "candidate_explanations": [], "selected_action_instances": [], "outcome": {"status": "not_run", "timing_ref": None, "correctness_ref": None, "mechanism_refs": [], "limitations": []}, "claims": [], "review": {"reviewer": "fixture", "independent": False, "decision": "pending", "notes": []}}
    (tmp_path / "paper.json").write_text(json.dumps(record))
    claim = {"id": "claim.support", "text": "纸面案例不构成真实案例支持", "basis": "case_support", "source_indexes": [], "review_status": "gap", "limitations": []}
    record["claims"] = [claim]
    with pytest.raises(GraphError, match="claim.case_refs"):
        validate_case(root, record, task_root=tmp_path)
    claim["case_refs"] = [{"path": "paper.json", "sha256": digest((tmp_path / "paper.json").read_bytes())}]
    with pytest.raises(GraphError, match="不能作为 case_support"):
        validate_case(root, record, task_root=tmp_path)


def source_proposal_fixture(package, tmp_path):
    root, artifact = package
    old = next(r for r in artifact["records"] if r["kind"] == "problem")
    draft = {k: deepcopy(v) for k, v in old.items() if k not in {"body", "source_path", "source_hash"}}
    draft["id"] = "problem.proposal_fixture"
    draft["title"] = "仅在独立测试内登记的来源型提案"
    claim = {"id": "source.checked", "text": "来源声明及适用边界已核对", "basis": "source_statement", "source_indexes": [0], "review_status": "reviewed", "limitations": ["没有实测机制收益"]}
    draft["claims"] = [claim]
    draft["review"].update(state="reviewed_with_limits", gaps=["需未来实际任务判别"])
    action = next(r for r in artifact["records"] if r["kind"] == "action")
    draft["analysis"]["actions"] = [{"action_id": action["id"], "intervention": "借注册A检验此来源假设", "requirements": ["原硬前提全部成立"], "costs": ["待实际计时"]}]
    edge = {k: deepcopy(v) for k, v in next(r for r in artifact["records"] if r["kind"] == "edge" and r["relation"] == "mitigated_by").items() if k not in {"body", "source_path", "source_hash"}}
    edge.update(id="edge.proposal_fixture", **{"from": draft["id"], "to": action["id"]})
    (tmp_path / "review.json").write_text('{"reviewer":"independent-fixture","decision":"approved"}')
    (tmp_path / "validation.txt").write_text("CPU fixture: schema/source/link checks only")
    review_ref = {"path": "review.json", "sha256": digest((tmp_path / "review.json").read_bytes())}
    validation_ref = {"path": "validation.txt", "sha256": digest((tmp_path / "validation.txt").read_bytes())}
    record = {"schema_version": "aprof.diagnosis-proposal/v1", "proposal_id": "proposal.source_fixture", "kind": "problem", "status": "reviewed", "title": draft["title"], "rationale": "检验晋升申报门禁而非注册知识", "scope": draft["scope"], "sources": draft["sources"], "claims": [claim], "case_refs": [], "semantic_dedup": {"compared_ids": [old["id"]], "distinct_from_existing": True, "reason": "测试中的显式差异审阅声明"}, "contract_check": {"status": "passed", "notes": ["仅结构校验"]}, "review": {"reviewer": "independent-fixture", "independent": True, "decision": "approved", "notes": ["不作实测支持"]}, "promotion": {"eligible": True, "automatic": False, "target_version": "v0005"}, "proposed_record": draft, "proposed_relations": [edge], "validation_refs": [validation_ref], "review_ref": review_ref}
    attestation = {"proposal_id": record["proposal_id"], "proposal_basis_hash": proposal_basis_hash(record), "base_knowledge_hash": content_hash(artifact), "target_version": "v0005"}
    review = {"schema_version": "aprof.diagnosis-proposal-review/v1", **attestation, "reviewer": "independent-fixture", "independent": True, "decision": "approved", "blocking_findings": [], "notes": ["CPU test review only"]}
    validation = {"schema_version": "aprof.diagnosis-proposal-validation/v1", **attestation, "checks": {k: "passed" for k in ("contract", "source", "dedup")}, "blocking_findings": [], "notes": ["CPU test records only"]}
    (tmp_path / "review.json").write_text(json.dumps(review))
    (tmp_path / "validation.txt").write_text(json.dumps(validation))
    record["review_ref"]["sha256"] = digest((tmp_path / "review.json").read_bytes())
    record["validation_refs"][0]["sha256"] = digest((tmp_path / "validation.txt").read_bytes())
    return root, artifact, record, review, validation


def test_source_based_proposal_requires_review_files_and_remains_unregistered(package, tmp_path):
    root, artifact, record, review, validation = source_proposal_fixture(package, tmp_path)
    assert validate_proposal(root, record, task_root=tmp_path) is record
    assert all(r["id"] != record["proposed_record"]["id"] for r in diagnosis.verify(root)["records"])
    record["review_ref"]["sha256"] = HASH
    with pytest.raises(GraphError, match="hash"):
        validate_proposal(root, record, task_root=tmp_path)


@pytest.mark.parametrize("mutation", ["other_proposal", "rejected", "nonindependent", "blocking", "base", "basis", "backwards", "validation_failed", "validation_other", "stale_draft"])
def test_proposal_review_and_validation_are_bound_to_content(package, tmp_path, mutation):
    root, artifact, record, review, validation = source_proposal_fixture(package, tmp_path)
    if mutation == "other_proposal":
        review["proposal_id"] = "proposal.someone_else"
    elif mutation == "rejected":
        review["decision"] = "rejected"
    elif mutation == "nonindependent":
        review["independent"] = False
    elif mutation == "blocking":
        review["blocking_findings"] = ["fix before promotion"]
    elif mutation == "base":
        review["base_knowledge_hash"] = HASH
    elif mutation == "basis":
        review["proposal_basis_hash"] = HASH
    elif mutation == "backwards":
        record["promotion"]["target_version"] = review["target_version"] = validation["target_version"] = "v0003"
    elif mutation == "validation_failed":
        validation["checks"]["source"] = "failed"
    elif mutation == "validation_other":
        validation["proposal_id"] = "proposal.someone_else"
    else:
        record["proposed_record"]["title"] = "unreviewed replacement"
    (tmp_path / "review.json").write_text(json.dumps(review))
    (tmp_path / "validation.txt").write_text(json.dumps(validation))
    record["review_ref"]["sha256"] = digest((tmp_path / "review.json").read_bytes())
    record["validation_refs"][0]["sha256"] = digest((tmp_path / "validation.txt").read_bytes())
    with pytest.raises(GraphError):
        validate_proposal(root, record, task_root=tmp_path)


# Shared CPU capture fixtures produce complete raw receipts and numeric oracle output.
from test_action_handoff_v3 import package as handoff_package


@pytest.fixture(scope="module")
def measured_case(handoff_package, tmp_path_factory, request):
    from aprof_runtime import bindings
    from aprof_runtime.diagnosis_reasoning import case_basis_hash
    from aprof_runtime.unified_timing import finalize_timing
    from test_action_handoff_v3 import chain_fixture, rebind, write_json
    from test_unified_timing import campaign

    root, artifact = handoff_package
    for name in ("diagnosis-case-review", "unified-timing-result", "unified-timing-request", "unified-correctness", "mechanism-report"):
        shutil.copy(ROOT / f"schemas/{name}.schema.json", root / "schemas")
    import tempfile
    ram_root = Path(tempfile.mkdtemp(prefix="aprof-validated-case-", dir="/dev/shm"))
    request.addfinalizer(lambda: shutil.rmtree(ram_root))
    task = ram_root / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    measurement = task / "measurement"
    measurement.mkdir()
    request_path, _ = campaign(measurement)
    request = json.loads(request_path.read_text())
    captures = {role: (measurement / request[role + "_captures"][0]["path"]) for role in ("baseline", "candidate")}
    capture_values = {role: json.loads(path.read_text()) for role, path in captures.items()}
    reasoning, selection, execution = c1["reasoning"], c2["selection"], c3["execution"]
    scope = reasoning["current"]["scope"]
    # Timing source identities refer to complete source inventories, not a single C++ file.
    for role, filename in (("baseline", "parent.cpp"), ("candidate", "candidate.cpp")):
        source = capture_values[role]["artifacts"]["source"]
        shutil.copyfile(captures[role].parent / source["path"], task / filename)
    workload = capture_values["baseline"]["artifacts"]["workload"]
    shutil.copyfile(captures["baseline"].parent / workload["path"], task / "workload.json")
    scope.update(parent_implementation_hash=request["baseline_source_sha256"], workload_hash=workload["sha256"])
    reasoning["current"]["implementation_ref"]["sha256"] = scope["parent_implementation_hash"]
    reasoning["current"]["workload_ref"]["sha256"] = scope["workload_hash"]
    origin = json.loads((task / "context.json").read_text())
    origin["operator"] = request["operator"]
    origin_ref = write_json(task / "context.json", origin)
    reasoning["source_context_ref"] = origin_ref
    reasoning["context_snapshot"]["source_context_ref"] = deepcopy(origin_ref)
    reasoning["context_hash"] = content_hash(reasoning["context_snapshot"])
    for fact in reasoning["facts"].values():
        fact["scope"] = deepcopy(scope)
    for candidate in reasoning["candidates"]:
        candidate["scope"] = deepcopy(scope)
    instance = reasoning["action_instances"][0]
    instance["scope"] = deepcopy(scope)
    for plan in (selection["parent_plan"], selection["confirmed_plan"]):
        plan["scope"] = deepcopy(scope)
        plan["parallel_plan"].update(operator=request["operator"], source_hash=scope["parent_implementation_hash"])
        plan["dispatch_plan"].update(operator=request["operator"], source_hash=scope["parent_implementation_hash"], parallel_plan_ref=content_hash(plan["parallel_plan"]))
    instance["parent_plan_hash"] = content_hash(selection["parent_plan"])
    selection["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", selection["confirmed_plan"])
    execution["implementation_source_ref"]["sha256"] = request["candidate_source_sha256"]
    execution["dispatch_plan"] = deepcopy(selection["confirmed_plan"]["dispatch_plan"])
    execution["dispatch_plan"].update(source_hash=request["candidate_source_sha256"], implementation_source_hash=request["candidate_source_sha256"], plan_basis_source_hash=scope["parent_implementation_hash"])
    c3["candidate_id"] = request["candidate_id"]
    profile_hashes = {}
    for role in ("baseline", "candidate"):
        ref = deepcopy(capture_values[role]["artifacts"]["task_csv"])
        ref["path"] = (captures[role].parent / ref["path"]).relative_to(task).as_posix()
        profile_hashes[role] = ref["sha256"]
        reasoning["facts"]["case.profile." + role] = {"state": True, "kind": "raw", "view": "profile", "time_range": {"kind": "full_artifact", "aggregation": "all_recorded_samples"}, "evidence_id": "case-profile-" + role, "ref": {**ref, "locator": "all complete calls"}, "derived_from": [], "scope": deepcopy(scope)}
    rebind(c1, c2, c3)
    selection["parallel_route"] = bindings.route_parallel(root, reasoning, instance["instance_id"], selection["routing_hint"], task_root=task)
    execution["optimization_route"] = bindings.route_optimization(root, reasoning, selection, task_root=task)
    rebind(c1, c2, c3)
    assert bindings.validate_chain(root, c1, c2, c3, task_root=task)["status"] == "implemented"
    routing_ref = bindings.routing_snapshot_ref(root, bindings.load_routing(root))
    handoff_refs = {stage: write_json(task / (stage + ".json"), item) for stage, item in zip(("C1", "C2", "C3"), (c1, c2, c3))}
    reasoning_ref = write_json(task / "reasoning.json", reasoning)
    timing_path = measurement / "result.json"
    finalize_timing(request_path, timing_path)
    def task_ref(path):
        return {"path": path.relative_to(task).as_posix(), "sha256": digest(path.read_bytes())}
    correctness_ref = task_ref(measurement / request["candidate_correctness"]["path"])
    mechanism = {"schema_version": "1.0.0", "candidate_id": request["candidate_id"], "hypothesis_basis": "measured", "metrics": [{"name": "Task_Duration", "baseline": 100.0, "candidate": 80.0, "expected_direction": "decrease", "unit": "us", "baseline_profile_hash": profile_hashes["baseline"], "candidate_profile_hash": profile_hashes["candidate"]}]}
    mechanism_ref = write_json(task / "mechanism.json", mechanism)
    record = {"schema_version": "aprof.diagnosis-case/v1", "case_id": "cpu.synthetic.validated", "evidence_status": "validated_case", "execution_kind": "synthetic", "task_id": reasoning["task_id"], "scope": deepcopy(scope), "context_ref": origin_ref, "reasoning_ref": reasoning_ref, "sources": [deepcopy(artifact["records"][0]["sources"][0])], "observations": ["CPU synthetic raw receipts; no hardware claim"], "candidate_explanations": ["Fixture only"], "selected_action_instances": [instance["instance_id"]], "outcome": {"status": "accepted", "timing_ref": task_ref(timing_path), "correctness_ref": correctness_ref, "mechanism_refs": [mechanism_ref], "limitations": ["Synthetic CPU fixture; never included in package knowledge"]}, "claims": [], "review": {"reviewer": "independent-cpu-fixture", "independent": True, "decision": "reviewed", "notes": ["Structure/raw replay only"]}, "routing_config_ref": routing_ref, "handoff_refs": handoff_refs}
    review = {"schema_version": "aprof.diagnosis-case-review/v1", "case_id": record["case_id"], "case_basis_hash": case_basis_hash(record), "reviewer": record["review"]["reviewer"], "independent": True, "decision": "reviewed", "blocking_findings": [], "notes": ["CPU synthetic fixture; no causal or hardware claim"]}
    record["review_ref"] = write_json(task / "case-review.json", review)
    return root, task, record


def test_validated_case_replays_full_synthetic_cpu_chain(measured_case):
    root, task, record = measured_case
    assert validate_case(root, record, task_root=task) is record


@pytest.mark.parametrize("mutation", ["selected_instance", "request_operator", "missing_raw", "review_rejected"])
def test_validated_case_rejects_fabricated_identity_and_raw_chain(measured_case, mutation):
    from aprof_runtime.diagnosis_reasoning import case_basis_hash
    root, task, original = measured_case
    record = deepcopy(original)
    changed = {}
    def replace(path, raw):
        if path not in changed:
            changed[path] = path.read_bytes()
        path.write_bytes(raw)
    try:
        if mutation == "selected_instance":
            record["selected_action_instances"] = ["instance.DOES_NOT_EXIST"]
        elif mutation in {"request_operator", "missing_raw"}:
            timing_path = task / record["outcome"]["timing_ref"]["path"]
            timing = json.loads(timing_path.read_text())
            request_path = Path(timing["request"]["path"])
            request = json.loads(request_path.read_text())
            if mutation == "request_operator":
                request["operator"] = "OTHER_OPERATOR"
            else:
                request["candidate_captures"][0] = {"path": "NONEXISTENT-raw-capture.json", "sha256": HASH}
            replace(request_path, json.dumps(request).encode())
            timing["request"]["sha256"] = digest(request_path.read_bytes())
            timing["decision_hash"] = content_hash({k: v for k, v in timing.items() if k != "decision_hash"})
            replace(timing_path, json.dumps(timing).encode())
            record["outcome"]["timing_ref"]["sha256"] = digest(timing_path.read_bytes())
        review_path = task / record["review_ref"]["path"]
        review = json.loads(review_path.read_text())
        review["case_basis_hash"] = case_basis_hash(record)
        if mutation == "review_rejected":
            review["decision"] = "rejected"
        replace(review_path, json.dumps(review).encode())
        record["review_ref"]["sha256"] = digest(review_path.read_bytes())
        with pytest.raises(GraphError):
            validate_case(root, record, task_root=task)
    finally:
        for path, raw in changed.items():
            path.write_bytes(raw)


def test_validated_case_replays_correctness_outputs(measured_case):
    root, task, record = measured_case
    correctness = json.loads((task / record["outcome"]["correctness_ref"]["path"]).read_text())
    case_root = (task / record["outcome"]["correctness_ref"]["path"]).parent
    case_path = case_root / correctness["cases"][0]["path"]
    case = json.loads(case_path.read_text())
    output_inventory = case_path.parent / case["artifacts"]["output"]["path"]
    output = json.loads(output_inventory.read_text())["files"][0]
    output_path = case_path.parent / output["path"]
    raw = output_path.read_bytes()
    try:
        output_path.write_bytes(b"tampered numerical output")
        with pytest.raises(GraphError, match="原始链回放失败"):
            validate_case(root, record, task_root=task)
    finally:
        output_path.write_bytes(raw)


def test_synthetic_replayed_case_cannot_become_case_support(measured_case):
    root, task, record = measured_case
    case_path = task / "synthetic-case.json"
    case_path.write_text(json.dumps(record))
    paper = deepcopy(record)
    for key in ("review_ref", "handoff_refs", "routing_config_ref"):
        paper.pop(key, None)
    paper.update(case_id="paper.cannot.promote.synthetic", evidence_status="source_review", execution_kind="not_run", context_ref=None, reasoning_ref=None, selected_action_instances=[])
    paper["outcome"] = {"status": "not_run", "timing_ref": None, "correctness_ref": None, "mechanism_refs": [], "limitations": []}
    paper["claims"] = [{"id": "synthetic.support", "text": "Explicit synthetic evidence cannot become knowledge support", "basis": "case_support", "source_indexes": [], "review_status": "reviewed", "limitations": [], "case_refs": [{"path": case_path.name, "sha256": digest(case_path.read_bytes())}]}]
    with pytest.raises(GraphError, match="synthetic.*不能作为 case_support"):
        validate_case(root, paper, task_root=task)


def test_known_profile_raw_requires_explicit_time_without_mutating_record(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    profile = deepcopy(next(iter(reasoning["facts"].values())))
    profile.update(view="profile", evidence_id="profile-window")
    profile["ref"]["locator"] = "metrics/bandwidth"
    reasoning["facts"]["current.profile"] = profile
    candidate = reasoning["candidates"][0]
    candidate["support"].append("current.profile")
    assert fact_state(reasoning, "current.profile") == "unknown"
    unchanged = deepcopy(reasoning)
    with pytest.raises(GraphError, match="时间口径.*unknown.*后继"):
        validate_reasoning(root, reasoning, artifact)
    assert reasoning == unchanged
    profile["state"] = "unknown"
    candidate["support"].remove("current.profile")
    candidate["unknown"].append("current.profile")
    assert validate_reasoning(root, reasoning, artifact) is reasoning
    profile["time_range"] = None
    assert validate_reasoning(root, reasoning, artifact) is reasoning
    profile.update(state=True, time_range={"kind": "full_artifact", "aggregation": "all_recorded_samples"})
    candidate["unknown"].remove("current.profile")
    candidate["support"].append("current.profile")
    assert profile_time_known(profile) and fact_state(reasoning, "current.profile") is True
    validate_reasoning(root, reasoning, artifact)
    profile.update(state=False, time_range={"kind": "interval", "start": 0, "end": 1.25, "unit": "ms", "origin": "capture_start"})
    candidate["support"].remove("current.profile")
    candidate["counter"].append("current.profile")
    assert profile_time_known(profile) and fact_state(reasoning, "current.profile") is False
    validate_reasoning(root, reasoning, artifact)
    profile["kind"] = "proxy"
    candidate["counter"].remove("current.profile")
    candidate["unknown"].append("current.profile")
    assert fact_state(reasoning, "current.profile") == "unknown"
    validate_reasoning(root, reasoning, artifact)


@pytest.mark.parametrize("span", [None, {}, {"kind": "interval", "start": 2, "end": 1, "unit": "us", "origin": "capture_start"}, {"kind": "interval", "start": True, "end": 1, "unit": "us", "origin": "capture_start"}, {"kind": "interval", "start": 0, "end": float("inf"), "unit": "us", "origin": "capture_start"}, {"kind": "interval", "start": float("nan"), "end": 1, "unit": "us", "origin": "capture_start"}, {"kind": "interval", "start": 0, "end": 1, "unit": "us", "origin": " "}, {"kind": "full_artifact", "aggregation": "all_recorded_samples", "invented": True}])
def test_profile_time_scope_rejects_invalid_or_incomplete_boundaries(package, span):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    profile = deepcopy(next(iter(reasoning["facts"].values())))
    profile.update(view="profile", evidence_id="invalid-profile-window", time_range=span)
    reasoning["facts"]["invalid.profile"] = profile
    assert profile_time_known(profile) is False
    with pytest.raises(GraphError):
        validate_reasoning(root, reasoning, artifact)


def test_source_workload_and_constraint_facts_need_no_profile_time(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    for index, view in enumerate(("source", "workload", "constraint")):
        fact = deepcopy(next(iter(reasoning["facts"].values())))
        fact.update(view=view, evidence_id="nonprofile-" + view)
        fact["ref"]["locator"] = "nonprofile/" + view
        reasoning["facts"]["nonprofile." + str(index)] = fact
    validate_reasoning(root, reasoning, artifact)
    assert all("time_range" not in fact for fact in reasoning["facts"].values())


def test_profile_windows_and_aliases_cannot_claim_independent_support(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    raw = deepcopy(next(iter(reasoning["facts"].values())))
    raw.update(view="profile", evidence_id="same-measurement", time_range={"kind": "interval", "start": 0, "end": 10, "unit": "us", "origin": "capture_start"})
    raw["ref"]["locator"] = "metrics/profile-row"
    reasoning["facts"]["profile.first"] = raw
    alias = deepcopy(raw)
    alias.update(evidence_id="renamed-measurement", time_range={"kind": "interval", "start": 10, "end": 20, "unit": "us", "origin": "capture_start"})
    reasoning["facts"]["profile.renamed"] = alias
    candidate = reasoning["candidates"][0]
    candidate["support"].extend(["profile.first", "profile.renamed"])
    candidate["independent_evidence_groups"] = [["profile.first"], ["profile.renamed"]]
    with pytest.raises(GraphError, match="独立证据"):
        validate_reasoning(root, reasoning, artifact)
    for name, start, end in (("derived.window_one", 0, 4), ("derived.window_two", 4, 8)):
        reasoning["facts"][name] = {"state": True, "kind": "derived", "view": "profile", "evidence_id": None, "ref": None, "derived_from": ["profile.first"], "scope": deepcopy(raw["scope"]), "time_range": {"kind": "interval", "start": start, "end": end, "unit": "us", "origin": "capture_start"}}
        candidate["support"].append(name)
    candidate["independent_evidence_groups"] = [["derived.window_one"], ["derived.window_two"]]
    with pytest.raises(GraphError, match="独立证据"):
        validate_reasoning(root, reasoning, artifact)
    candidate["independent_evidence_groups"] = [["profile.first", "profile.renamed", "derived.window_one", "derived.window_two"]]
    validate_reasoning(root, reasoning, artifact)


def test_registered_profile_and_predicate_alias_require_time_even_without_view(package):
    root, artifact = package
    reasoning = reasoning_fixture(artifact)
    predicate = next(r["id"] for r in artifact["records"] if r["kind"] == "symptom" and r["view"] == "profile")
    fact = deepcopy(next(iter(reasoning["facts"].values())))
    fact.update(predicate=predicate, evidence_id="canonical-profile")
    reasoning["facts"]["local.profile.instance"] = fact
    assert "view" not in fact
    assert fact_state(reasoning, "local.profile.instance") == "unknown"
    with pytest.raises(GraphError, match="时间口径"):
        validate_reasoning(root, reasoning, artifact)
    fact["time_range"] = {"kind": "interval", "start": -2.5, "end": 3, "unit": "cycles", "origin": "kernel_entry"}
    assert profile_time_known(fact)
    assert fact_state(reasoning, "local.profile.instance") is True
    validate_reasoning(root, reasoning, artifact)
    assert not profile_time_known({"time_range": {"kind": "interval", "start": 0, "end": 1, "unit": [], "origin": "capture_start"}})

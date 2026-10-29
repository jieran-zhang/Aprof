from aprof_runtime.documentation_sources import original_path as evidence_original
"""知识迁移、路由边界与五类 C1→C2→C3 纸面演练；不访问 NPU。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aprof_runtime.errors import ContractError, GraphError
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import content_hash
from aprof_runtime.knowledge import (
    REGIONS, apply_override, artifact_path, build, compile_region, digest,
    link_result, read_record, route_diagnosis, route_tree, validate_records,
    validate_schema, verify,
)

ROOT = Path(__file__).resolve().parents[2]
DEVELOPMENT = ROOT.parents[2] / 'scaffolding/curation/graph-base-1.3.2-development/materials'


@pytest.fixture(scope="module")
def artifacts():
    # 冻结v0003按原评分器回放；当前模板MD已迁移，不能重编成旧格式。
    return {owner: (load_snapshot(ROOT / REGIONS[owner] / "versions/v0003")[0]
                    if owner == "diagnosis" else verify(ROOT, owner))
            for owner in REGIONS}


def fact(value=True, evidence_id="fixture-observation", kind="source_review"):
    return {"state": value, "evidence_id": evidence_id, "kind": kind,
            "ref": {"path": "exercise-only.txt", "sha256": digest(b"paper exercise"), "locator": evidence_id}}


def context(facts=None, **attributes):
    return {"schema_version": "aprof.evidence/v1", "task_id": "paper-exercise",
            "source_context_ref": {"path": "C0-context.json", "sha256": digest(b"paper C0")},
            "attributes": attributes, "facts": facts or {}}


def test_all_regions_rebuild_deterministically_and_history_is_frozen(artifacts, tmp_path):
    legacy = tmp_path / "legacy-seed"
    shutil.copytree(ROOT, legacy, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", ".runtime-env"))
    graph = legacy / REGIONS["diagnosis"]
    seed = DEVELOPMENT / REGIONS["diagnosis"] / "history/seed-v0003"
    (graph / "PROBLEMS.md").unlink(missing_ok=True)  # 旧编译器不识别新目录视图。
    for section in ("symptoms", "problems", "actions", "edges"):
        shutil.rmtree(graph / section)
        shutil.copytree(seed / section, graph / section)
    shutil.copy2(seed / "REGION.json", graph / "REGION.json")
    for owner, artifact in artifacts.items():
        assert compile_region(legacy if owner == "diagnosis" else ROOT, owner) == artifact
    manifest = json.loads((ROOT / "workflows/migration/migration.json").read_text())
    for file in manifest["files"]:
        if file["disposition"].startswith("frozen"):
            assert digest(evidence_original(ROOT, file["path"]).read_bytes()) == file["original_hash"]
    assert len({item["id"] for item in manifest["items"]}) == len(manifest["items"])
    assert all(item["targets"] and item["reason"] for item in manifest["items"])


def test_tiny_workload_refutes_unexposed_parallelism(artifacts):
    facts = {"symptom.profile.tasks_below_available_cores": fact(evidence_id="tasks"),
             "symptom.source.fixed_or_undersubscribed_tasking": fact(evidence_id="source"),
             "symptom.workload.tiny_or_overhead_limited": fact(evidence_id="workload")}
    result = route_diagnosis(artifacts["diagnosis"], context(facts))
    p = next(p for p in result["problems"] if p["id"] == "problem.underused_task_parallelism")
    assert p["score"] <= 0
    assert result["diagnostic_state"] == "workload_limited"
    assert "action.decompose_tasks_dynamically" not in {a["id"] for a in result["actions"]}


def test_bandwidth_and_small_transfer_are_distinguished(artifacts):
    r = route_diagnosis(artifacts["diagnosis"], context({
        "symptom.source.inner_loop_copy": fact(evidence_id="copy-source"),
        "symptom.profile.memory_bandwidth_saturation": fact(evidence_id="measured-bandwidth")}))
    scores = {p["id"]: p["score"] for p in r["problems"]}
    assert scores["problem.tiny_transfer_setup_amplification"] < 0
    assert scores["problem.memory_bandwidth_saturation"] == 3
    r = route_diagnosis(artifacts["diagnosis"], context({
        "symptom.profile.mte_setup_dominated": fact(evidence_id="small-transfer")}))
    assert next(p["score"] for p in r["problems"] if p["id"] == "problem.tiny_transfer_setup_amplification") == 3


def test_missing_false_proxy_and_duplicate_evidence_are_not_confused(artifacts):
    graph = artifacts["diagnosis"]
    r = route_diagnosis(graph, context())
    assert r["selected_action"] is None and all(p["score"] == 0 for p in r["problems"])
    r = route_diagnosis(graph, context({"symptom.profile.ub_conflict_high": fact(kind="proxy")}))
    assert all(p["score"] == 0 for p in r["problems"])
    r = route_diagnosis(graph, context({
        "symptom.profile.per_core_time_imbalanced": fact(evidence_id="same-observation"),
        "symptom.source.tail_concentrated": fact(evidence_id="same-observation")}))
    score = next(p["score"] for p in r["problems"] if p["id"] == "problem.core_tail_imbalance")
    assert score == 3 and r["deduplicated"]
    assert next(a["status"] for a in r["actions"] if a["id"] == "action.balance_tail_assignment") == "needs_evidence"


def test_hard_prerequisite_failure_never_becomes_executable(artifacts):
    graph = artifacts["diagnosis"]
    action = next(n for n in graph["records"] if n["id"] == "action.coalesce_contiguous_transfers")
    facts = {p["fact"]: fact(p["state"], evidence_id=p["fact"]) for p in action["preconditions"]}
    facts["constraint.capacity"] = fact(False, evidence_id="capacity")
    r = route_diagnosis(graph, context(facts))
    a = next(a for a in r["actions"] if a["id"] == action["id"])
    assert a["status"] == "blocked" and a["failed"] == ["constraint.capacity"]


def test_platform_specific_missing_fields_do_not_match(artifacts):
    graph = deepcopy(artifacts["diagnosis"])
    n = next(n for n in graph["records"] if n["id"] == "symptom.profile.ub_conflict_high")
    n["scope"]["platforms"] = ["dav-2201"]
    r = route_diagnosis(graph, context({n["id"]: fact()}, platform="dav-3510"))
    assert next(p["score"] for p in r["problems"] if p["id"] == "problem.ub_bank_conflict") == 0


def test_tree_multibranch_missing_prerequisites_and_fallback(artifacts):
    r = route_tree(artifacts["parallel-planning"], context(family=["elementwise", "under-fusion"]))
    assert {"planning.elementwise.continuous", "planning.under-fusion.chain"} <= {m["id"] for m in r["matches"]}
    assert all(m["status"] == "needs_evidence" for m in r["matches"])
    r = route_tree(artifacts["parallel-planning"], context(family=["uncovered"]))
    assert [m["id"] for m in r["matches"]] == ["planning.fallback"]
    assert r["matches"][0]["score"] == 0


@pytest.mark.parametrize("damage", ["duplicate", "relation", "dangling", "weight", "nan", "cycle", "parent"])
def test_bad_records_are_rejected(artifacts, damage):
    owner = "parallel-planning" if damage in {"cycle", "parent"} else "diagnosis"
    records = deepcopy(artifacts[owner]["records"])
    if damage == "duplicate":
        records.append(deepcopy(records[0]))
    elif owner == "diagnosis":
        edge = next(r for r in records if r["kind"] == "edge")
        if damage == "relation": edge["relation"] = "invented"
        if damage == "dangling": edge["to"] = "missing"
        if damage == "weight": edge["learning"]["weight"] = 4
        if damage == "nan": edge["learning"]["weight"] = float("nan")
    else:
        item = next(r for r in records if r["parent"] is not None)
        item["parent"] = item["id"] if damage == "cycle" else "missing"
    with pytest.raises(GraphError):
        validate_records(records, owner)


@pytest.mark.parametrize("damage", ["hash", "missing_source", "yaml_duplicate", "unsafe_yaml"])
def test_source_and_yaml_trust_boundary(tmp_path, damage):
    path = DEVELOPMENT / "skills/ascendc-aprof-diagnosis/graph/history/seed-v0003/symptoms/symptom.profile.gm_traffic_amplified.md"
    copy = tmp_path / "record.md"
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    header = path.read_text()
    original = next(record for record in load_snapshot(ROOT / REGIONS["diagnosis"] / "versions/v0003")[0]["records"]
                    if record["id"] == path.stem)
    for source in original["sources"]:
        dest = tmp_path / source["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source["path"], dest)
    if damage == "hash":
        (tmp_path / original["sources"][0]["path"]).write_text("changed source\n")
    elif damage == "missing_source":
        header = header[:header.index("sources:")] + "sources: []\n" + header[header.index("learning:"):]
    elif damage == "yaml_duplicate":
        header = header.replace("---\n", "---\nkind: symptom\n", 1)
    else:
        header = header.replace("title:", "title: !!python/object/apply:os.system ['false']\nunused:", 1)
    copy.write_text(header)
    with pytest.raises(GraphError):
        read_record(copy, tmp_path)


def test_override_is_version_bound_and_deterministic(artifacts):
    graph = artifacts["diagnosis"]
    edge = next(n for n in graph["records"] if n["kind"] == "edge")
    override = {"schema_version": "aprof.knowledge-override/v1", "version": graph["version"],
                "base_hash": content_hash(graph), "parameters": {edge["id"]: {"weight": 1.25}}}
    assert apply_override(graph, override) != graph
    ctx = context({"symptom.source.inner_loop_copy": fact()})
    assert route_diagnosis(graph, ctx, override) == route_diagnosis(graph, ctx, override)
    override["version"] = "v0002"
    with pytest.raises(GraphError, match="确切版本"):
        apply_override(graph, override)
    with pytest.raises(GraphError, match="旧 policy"):
        route_graph(graph, ctx, policy={})


def test_published_package_and_old_policy_training_are_not_mutated(artifacts, tmp_path):
    from aprof_runtime.policy import train_fixed_graph_policy
    (tmp_path / "release.json").write_text("{}")
    with pytest.raises(GraphError, match="不能重建已发布包"):
        build(tmp_path, "diagnosis")
    with pytest.raises(ContractError, match="不使用旧 fixed-graph policy"):
        train_fixed_graph_policy(artifacts["diagnosis"], [], policy_version="invalid-cross-version")


@pytest.mark.parametrize("family,action_id,template,features", [
    ("elementwise", "coalesce_contiguous_transfers", "planning.elementwise.continuous", ["tiling-tail", "memory-transfer"]),
    ("reduction", "restructure_reduction", "planning.reduction.split", ["tiling-tail", "precision-boundaries"]),
    ("matmul", "decompose_tasks_dynamically", "planning.matmul.mn", ["tiling-tail", "pipeline-sync"]),
    ("under-fusion", "fuse_kernel_chain", "planning.under-fusion.chain", ["buffer-lifetime", "vector-api"]),
    ("flash-attention", "decompose_tasks_dynamically", "planning.flash-attention.splitkv", ["kv_underparallel", "pipeline-sync", "precision-boundaries"]),
])
def test_five_family_handoffs_use_snapshots_and_separate_recommended_selected_executed(
        artifacts, tmp_path, family, action_id, template, features):
    graph = artifacts["diagnosis"]
    action = next(r for r in graph["records"] if r["id"] == "action." + action_id)
    facts = {p["fact"]: fact(p["state"], p["fact"]) for p in action["preconditions"]}
    for owner in ("parallel-planning", "optimization"):
        for r in artifacts[owner]["records"]:
            for route in r.get("routes", []):
                for key in route["required_evidence"]:
                    facts[key] = fact(True, key)
    ctx = context(facts, family=[family], features=features)
    c1 = {"schema_version": "aprof.handoff/v2", "stage": "C1", "task_id": ctx["task_id"],
          "candidate_id": None, "parent_hash": None, "route": route_diagnosis(graph, ctx), "artifacts": []}
    chosen = "action." + action_id
    assert next(a for a in c1["route"]["actions"] if a["id"] == chosen)["status"] == "executable"
    # Planning receives C1 snapshots, never the graph's source directory.
    c2 = {"schema_version": "aprof.handoff/v2", "stage": "C2", "task_id": ctx["task_id"],
          "candidate_id": None, "parent_hash": content_hash(c1),
          "route": route_tree(artifacts["parallel-planning"], ctx), "selected_actions": [chosen],
          "selected_entries": [template], "parameters": {"capacity_bytes": 65536},
          "alternatives": [{"name": "baseline", "reason": "paper comparison only"}],
          "implementation_freedom": ["tile within declared capacity"], "artifacts": []}
    matched_template = next(m for m in c2["route"]["matches"] if m["id"] == template)
    assert "snapshot" in matched_template and "body" in matched_template["snapshot"]
    r3 = route_tree(artifacts["optimization"], ctx)
    c3 = {"schema_version": "aprof.handoff/v2", "stage": "C3", "task_id": ctx["task_id"],
          "candidate_id": "candidate-001", "parent_hash": content_hash(c2), "route": r3,
          "executed_actions": [chosen], "selected_entries": [r3["matches"][0]["id"]],
          "implementation_source_hash": digest(b"paper implementation"),
          "parameters": {"tile": 128}, "parameter_adjustments": [], "plan_compliance": "compliant", "artifacts": []}
    timing = {"path": "timing.json", "sha256": digest(b"not measured; reference-only fixture"),
              "candidate_id": c3["candidate_id"], "protocol": "single_role_l2_clean_task_v1"}
    linked = link_result(c1, c2, c3, timing)
    assert linked["selected_actions"] == linked["executed_actions"] == [chosen]
    assert not linked["causal_claim"] and not linked["legacy_episode_eligible"]
    for index, item in enumerate((c1, c2, c3), 1):
        validate_schema(ROOT, "knowledge-handoff", item)
        (tmp_path / f"C{index}.json").write_text(json.dumps(item))
    damaged = deepcopy(c3)
    damaged["executed_actions"] = ["action.not_selected"]
    with pytest.raises(GraphError):
        link_result(c1, c2, damaged, timing)
    if family == "elementwise":
        # 关联真实 CPU 协议回放产物；采集使用 FakeRunner，不访问 NPU。
        from aprof_runtime.cli import main
        from aprof_runtime.unified_timing import finalize_timing
        from test_unified_timing import campaign
        measured = tmp_path / "cpu-capture"
        measured.mkdir()
        request_path, _ = campaign(measured)
        request = json.loads(request_path.read_text())
        request["candidate_id"] = c3["candidate_id"]
        request_path.write_text(json.dumps(request))
        c3["implementation_source_hash"] = request["candidate_source_sha256"]
        (tmp_path / "C3.json").write_text(json.dumps(c3))
        result_path = measured / "result.json"
        finalize_timing(request_path, result_path)
        timing.update(path=str(result_path), sha256=digest(result_path.read_bytes()))
        timing_path = tmp_path / "timing-ref.json"
        timing_path.write_text(json.dumps(timing))
        command = ["knowledge", "link-result", "--root", str(ROOT),
                   "--c1", str(tmp_path / "C1.json"), "--c2", str(tmp_path / "C2.json"),
                   "--c3", str(tmp_path / "C3.json"), "--timing-ref", str(timing_path)]
        assert main(command) == 0
        c3["implementation_source_hash"] = digest(b"different implementation")
        (tmp_path / "C3.json").write_text(json.dumps(c3))
        assert main(command) == 2
        timing["sha256"] = digest(b"different timing result")
        timing_path.write_text(json.dumps(timing))
        assert main(command) == 2
    damaged = deepcopy(c3)
    damaged["parent_hash"] = digest(b"different plan")
    with pytest.raises(GraphError):
        link_result(c1, c2, damaged, timing)


def test_history_versions_load_without_reinterpretation():
    base = ROOT / REGIONS["diagnosis"] / "history/versions"
    for version in ("v0001", "v0002"):
        graph, manifest = load_snapshot(base / version)
        assert graph["graph_version"] == version and manifest["immutable"]
        assert "records" not in graph
        assert any(e.get("prior_logit") == 2.8 for e in graph["edges"])


def test_frozen_old_routes_and_policies_replay_identically():
    from aprof_runtime.contracts import Context
    from aprof_runtime.jsonio import to_primitive
    fixture = json.loads((Path(__file__).parent / 'fixtures/historical-routes.json').read_text())
    base = ROOT / REGIONS['diagnosis'] / 'history/versions'
    for case in fixture['cases']:
        graph, _ = load_snapshot(base / case['graph_version'])
        policy = fixture['policies'][case['graph_version']] if case['policy'] else None
        route = route_graph(graph, Context.from_dict(case['context']), policy=policy)
        assert content_hash(to_primitive(route)) == case['expected_route_hash']

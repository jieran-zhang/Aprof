"""新 memory 的真实信任边界；fixture 全部为 CPU 合成材料，无性能资格。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import ValidationError

TOOL = Path(__file__).resolve().parents[1] / "tools/validate_learning_records.py"
spec = importlib.util.spec_from_file_location("learning_records", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_bundle(root):
    def put(name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
        return {"path": name, "sha256": module.file_hash(path)}

    source = put("baseline.txt", "CPU synthetic baseline")
    candidate = put("candidate.txt", "CPU synthetic candidate")
    source_hash, candidate_hash = source["sha256"], candidate["sha256"]
    note = put("evidence.txt", "CPU synthetic evidence; not hardware evidence")
    knowledge = {owner: put(f"{owner}.json", {"schema_version": "aprof.knowledge/v1",
                 "owner": owner, "version": "v0003" if owner == "diagnosis" else "v0001",
                 "records": []}) for owner in module.OWNERS}
    batch = {"schema_version": "aprof.optimization-batch/v1", "batch_id": "batch-1",
             "skill_lib_ref": put("package.json", {"synthetic": True}), "knowledge_refs": knowledge,
             "override_refs": dict.fromkeys(module.OWNERS), "model": "cpu-fixture",
             "prompt_ref": note, "timing_protocol": module.PROTOCOL,
             "split_refs": {s: put(f"split-{s}.json", {"active_operators": ops})
                            for s, ops in (("train", ["exp"]), ("validation", ["softmax"]), ("test", ["matmul"]))},
             "tasks": [{"task_id": "task-exp", "operator": "exp", "group_id": "exp-lineage",
                        "split": "train", "source_ref": source, "source_hash": source_hash,
                        "workload_ref": note, "optimizer_id": "optimizer-1", "budget_seconds": 600,
                        "max_attempts": 2}]}
    batch_ref = put("batch.json", batch)
    chain, handoffs = [], {}
    for number, owner in enumerate(module.OWNERS, 1):
        artifact = module.strict_json((root / knowledge[owner]["path"]).read_text())
        handoff = {"schema_version": "aprof.handoff/v2", "stage": f"C{number}",
                   "task_id": "task-exp", "candidate_id": "a1" if number == 3 else None,
                   "parent_hash": module.content_hash(chain[-1]) if chain else None,
                   "route": {"owner": owner, "version": artifact["version"],
                             "knowledge_hash": module.content_hash(artifact), "override_hash": None}}
        if number == 2:
            handoff["selected_actions"] = ["action.example"]
        if number == 3:
            handoff.update(executed_actions=["action.example"], implementation_source_hash=candidate_hash)
        chain.append(handoff)
        handoffs[f"C{number}"] = put(f"C{number}.json", handoff)
    timing = put("timing.json", {"kind": "unified_timing_result", "protocol": module.PROTOCOL,
                                 "candidate_id": "a1", "synthetic": True})
    outcome = put("outcome.json", {"schema_version": "aprof.knowledge-outcome/v1", "task_id": "task-exp",
                   "candidate_id": "a1", "handoff_hashes": [module.content_hash(c) for c in chain],
                   "selected_actions": ["action.example"], "executed_actions": ["action.example"],
                   "timing_result": timing, "causal_claim": False, "legacy_episode_eligible": False})
    journal = put("attempts.jsonl", "\n".join(json.dumps({"seq": seq, "event": event,
                   "task_id": "task-exp", "attempt_id": "a1", "ref": note})
                   for seq, event in ((1, "registered"), (2, "closed"))) + "\n")
    result = {"schema_version": "aprof.task-result/v1", "batch_id": "batch-1", "task_id": "task-exp",
              "optimizer_id": "optimizer-1", "journal_ref": journal, "status": "completed",
              "attempts": [{"attempt_id": "a1", "status": "completed", "terminal_ref": note}],
              "selected_attempt_id": "a1", "optimization_seconds": 10, "stop_reason": None}
    result_ref = put("task-result.json", result)
    memory = {"schema_version": "aprof.optimization-memory/v3", "memory_id": "memory-exp", "revision": 1,
              "previous_ref": None, "batch_ref": batch_ref, "task_result_ref": result_ref,
              "task_id": "task-exp", "C0_ref": note,
              "recorder": {"agent_id": "recorder-1", "model": "cpu-fixture", "producer_ref": note},
              "attempts": [{"attempt_id": "a1", "parent_attempt_id": None,
                            "parent_source_ref": source, "parent_source_hash": source_hash,
                            "candidate_source_ref": candidate, "candidate_source_hash": candidate_hash,
                            "patch_ref": note, "handoffs": handoffs, "C4_ref": note, "C5_ref": note,
                            "execution_refs": [note], "timing_ref": timing, "outcome_ref": outcome,
                            "status": "completed", "failure": None, "missing": [],
                            "observations": [{"claim_id": "claim-1", "owner": "diagnosis",
                              "target_id": "edge.example", "statement": "CPU fixture only",
                              "basis_kind": "retrospective", "status": "inconclusive",
                              "evidence_refs": [note], "limitation": "未实测"}],
                            "optimization_seconds": 10, "tokens": None}],
              "memory_seconds": 1, "limitations": ["CPU fixture; incomplete runtime handoff; no learning admission"]}
    memory_ref = put("memory.json", memory)
    base_graph = module.strict_json((root / knowledge["diagnosis"]["path"]).read_text())
    override = put("override.json", {"schema_version": "aprof.knowledge-override/v1",
                   "base_hash": module.content_hash(base_graph), "version": base_graph["version"],
                   "parameters": {"edge.example": {"weight": 2}}})
    policy = put("policy.json", module.strict_json((TOOL.parents[1] /
                 "skills/aprof-train-knowledge/references/admission-policy.json").read_text()))
    proposal = {"schema_version": "aprof.knowledge-update/v1", "proposal_id": "proposal-1",
                "base_skill_lib_ref": batch["skill_lib_ref"], "owner": "diagnosis", "change_type": "parameters",
                "base_knowledge_ref": knowledge["diagnosis"], "candidate_artifact_ref": override,
                "policy_ref": policy, "training_memory_refs": [memory_ref], "validation_memory_refs": [],
                "changes": [{"target_id": "edge.example", "operation": "reweight", "before_refs": [note],
                             "after_refs": [note], "reason": "仅验证 metadata",
                             "signals": [{"memory_id": "memory-exp", "attempt_id": "a1", "claim_ids": ["claim-1"]}]}],
                "evaluation_ref": None, "status": "candidate", "previous_proposal_ref": None,
                "limitations": ["不可晋升"]}
    return put, batch, result, memory, proposal


def test_metadata_validation_never_grants_promotion(tmp_path):
    put, batch, result, memory, proposal = make_bundle(tmp_path)
    validator = module.Validator(tmp_path)
    validator.memory(memory)
    assert validator.update(proposal) == {"train_operator_groups": 1, "validation_operator_groups": 0}
    completed = subprocess.run([sys.executable, str(TOOL), "--root", str(tmp_path), "--kind", "memory",
                                "--input", "memory.json"], capture_output=True, text=True, check=True)
    report = json.loads(completed.stdout)
    assert report["integrity_valid"] and not report["promotion_authorized"] and not report["runtime_replay_performed"]


@pytest.mark.parametrize("mutation,match", [
    (lambda m: m["recorder"].update(agent_id="optimizer-1"), "recorder"),
    (lambda m: m.update(attempts=[]), "全部候选"),
    (lambda m: m["attempts"][0].update(parent_attempt_id="a1"), "父候选"),
    (lambda m: m["attempts"][0].update(status="failed"), "闭合结果"),
    (lambda m: m.update(revision=2), "revision"),
    (lambda m: m["attempts"][0]["handoffs"].update(C1=None), "missing"),
    (lambda m: m["attempts"][0].update(candidate_source_hash="sha256:" + "0" * 64), "C3"),
])
def test_memory_rejects_bad_bindings(tmp_path, mutation, match):
    _, _, _, memory, _ = make_bundle(tmp_path)
    mutation(memory)
    with pytest.raises(ValueError, match=match):
        module.Validator(tmp_path).memory(memory)


def test_partial_failure_is_retained(tmp_path):
    put, _, result, memory, _ = make_bundle(tmp_path)
    result.update(status="failed", selected_attempt_id=None, stop_reason="构建失败")
    result["attempts"][0]["status"] = "failed"
    memory["task_result_ref"] = put("task-result.json", result)
    attempt = memory["attempts"][0]
    attempt.update(status="failed", failure={"stage": "build", "category": "implementation", "reason": "编译错误"},
                   timing_ref=None, outcome_ref=None, C4_ref=None, missing=["构建失败，未计时"])
    module.Validator(tmp_path).memory(memory)


def test_revision_and_all_attempts_preserved(tmp_path):
    put, _, _, memory, _ = make_bundle(tmp_path)
    original = put("memory-r1.json", memory)
    memory.update(revision=2, previous_ref=original, limitations=["增加审读说明"])
    module.Validator(tmp_path).memory(memory)
    memory["previous_ref"]["sha256"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="hash"):
        module.Validator(tmp_path).memory(memory)


def test_revision_cannot_replace_closed_task_result(tmp_path):
    put, _, result, memory, _ = make_bundle(tmp_path)
    original = put("memory-r1.json", memory)
    result["optimization_seconds"] = 0
    memory.update(revision=2, previous_ref=original, task_result_ref=put("replacement.json", result))
    with pytest.raises(ValueError, match="revision 链"):
        module.Validator(tmp_path).memory(memory)


def test_journal_catches_omitted_attempt_and_order(tmp_path):
    put, _, result, _, _ = make_bundle(tmp_path)
    result["attempts"] = []
    result["selected_attempt_id"] = None
    with pytest.raises(ValueError, match="journal"):
        module.Validator(tmp_path).task_result(result)


def test_bytes_and_path_boundary(tmp_path):
    _, _, _, memory, _ = make_bundle(tmp_path)
    (tmp_path / "candidate.txt").write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        module.Validator(tmp_path).memory(memory)
    for path in ("../escape", str(tmp_path / "baseline.txt")):
        with pytest.raises(ValueError, match="归档根"):
            module.Validator(tmp_path).path(path)
    (tmp_path / "alias").symlink_to(tmp_path / "baseline.txt")
    with pytest.raises(ValueError, match="symlink"):
        module.Validator(tmp_path).path("alias")


def test_split_leakage_and_duplicate_sources(tmp_path):
    _, batch, _, _, _ = make_bundle(tmp_path)
    task = deepcopy(batch["tasks"][0])
    task.update(task_id="task-other", operator="softmax", split="validation", group_id="exp-lineage")
    batch["tasks"].append(task)
    with pytest.raises(ValueError, match="跨 split"):
        module.Validator(tmp_path).batch(batch)
    task["group_id"] = "new-name"
    with pytest.raises(ValueError, match="同源 baseline"):
        module.Validator(tmp_path).batch(batch)


def test_cross_version_route_rejected(tmp_path):
    put, _, _, memory, _ = make_bundle(tmp_path)
    c1 = module.strict_json((tmp_path / "C1.json").read_text())
    c1["route"]["version"] = "v0002"
    memory["attempts"][0]["handoffs"]["C1"] = put("C1.json", c1)
    with pytest.raises(ValueError, match="知识版本"):
        module.Validator(tmp_path).memory(memory)


def test_teacher_cannot_fit_validation_or_unknown_claim(tmp_path):
    put, batch, _, memory, proposal = make_bundle(tmp_path)
    proposal["changes"][0]["signals"][0]["claim_ids"] = ["invented"]
    with pytest.raises(ValueError, match="claim"):
        module.Validator(tmp_path).update(proposal)
    proposal["changes"][0]["signals"][0]["claim_ids"] = ["claim-1"]
    batch["tasks"][0].update(operator="softmax", split="validation")
    memory["batch_ref"] = put("batch.json", batch)
    proposal["training_memory_refs"] = [put("memory.json", memory)]
    with pytest.raises(ValueError, match="不能用 validation"):
        module.Validator(tmp_path).update(proposal)


def test_schema_rejects_unversioned_extensions_and_nonfinite_json(tmp_path):
    _, _, _, memory, _ = make_bundle(tmp_path)
    memory["production_safe_gain"] = True
    with pytest.raises(ValidationError):
        module.Validator(tmp_path).memory(memory)
    for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'):
        with pytest.raises(ValueError):
            module.strict_json(raw)


def test_parameter_candidate_cannot_use_old_policy_or_wrong_base(tmp_path):
    put, _, _, _, proposal = make_bundle(tmp_path)
    proposal["candidate_artifact_ref"] = put("wrong-override.json", {"schema_version": "legacy-policy/v1"})
    with pytest.raises(ValueError, match="override"):
        module.Validator(tmp_path).update(proposal)


def test_json_ref_error_names_artifact(tmp_path):
    _, _, _, _, proposal = make_bundle(tmp_path)
    proposal["candidate_artifact_ref"] = proposal["changes"][0]["before_refs"][0]
    with pytest.raises(ValueError, match="evidence.txt"):
        module.Validator(tmp_path).update(proposal)


def test_blocked_task_with_zero_candidates_can_be_archived(tmp_path):
    put, _, result, memory, _ = make_bundle(tmp_path)
    result.update(status="blocked", selected_attempt_id=None, attempts=[],
                  optimization_seconds=0, stop_reason="C0 缺 oracle adapter", journal_ref=put("empty.jsonl", ""))
    memory.update(attempts=[], task_result_ref=put("blocked-result.json", result), limitations=["准备阶段阻塞"])
    module.Validator(tmp_path).memory(memory)


def test_snapshot_inventory_bytes_are_checked(tmp_path):
    put, batch, _, _, _ = make_bundle(tmp_path)
    batch["skill_lib_ref"] = put("snapshot.json", {"schema_version": "aprof.skill-lib-snapshot/v1",
                 "files": {"baseline.txt": batch["tasks"][0]["source_ref"]["sha256"]}})
    module.Validator(tmp_path).batch(batch)
    (tmp_path / "baseline.txt").write_text("modified after snapshot")
    with pytest.raises(ValueError, match="hash"):
        module.Validator(tmp_path).batch(batch)

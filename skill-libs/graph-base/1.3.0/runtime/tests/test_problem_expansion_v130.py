"""Explicit, replayable Problem reading without choosing a diagnosis or Action."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime import cli, diagnosis
from aprof_runtime.diagnosis_retrieval import expand, retrieve, validate_expansion
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash
from aprof_runtime.knowledge import digest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def artifact():
    return json.loads((ROOT / diagnosis.REGION / "versions/v0004/graph.json").read_text())


@pytest.fixture
def context():
    return {"schema_version": "aprof.evidence/v1", "task_id": "reading-test",
            "source_context_ref": {"path": "context.json", "sha256": digest(b"synthetic-context")},
            "attributes": {"platform": "dav-2201", "family": "elementwise", "dtype": "float32"},
            "facts": {}}


def request_for(artifact, context, identifiers):
    result = retrieve(artifact, context, ROOT)
    return {"schema_version": "aprof.diagnosis-problem-expansion-request/v1",
            **{key: deepcopy(result[key]) for key in (
                "task_id", "context_hash", "knowledge_hash", "graph_version", "source_context_ref")},
            "retrieval_hash": content_hash(result), "selections": [
                {"problem_id": identifier, "reason": "需要结合当前观测比较此机制及其边界",
                 "trigger": "unexplained_observation", "related_problem_ids": [],
                 "unexplained_observations": ["task.observation.unexplained"]}
                for identifier in identifiers]}


def test_directory_remains_light_and_reading_is_explicit_not_top_k(artifact, context):
    directory = retrieve(artifact, context, ROOT)
    assert len(directory["problem_directory"]) == 28
    assert directory["symptom_adjacency"] == []
    assert all("body" not in item for item in directory["problem_directory"])
    identifiers = [item["id"] for item in directory["problem_directory"]]
    chosen = [identifiers[-1], identifiers[3], identifiers[8], identifiers[0]]
    for selected in (chosen[:1], chosen):
        result = expand(artifact, context, request_for(artifact, context, selected), ROOT)
        assert [item["problem_id"] for item in result["entries"]] == selected
        assert len(result["entries"]) == len(selected)
        assert "selected_action" not in result and "score" not in result
        records = {record["id"]: record for record in artifact["records"]}
        for item in result["entries"]:
            record = records[item["problem_id"]]
            for key in ("body", "analysis", "sources", "claims", "review", "slots", "scope"):
                assert item[key] == record[key]
            assert item["body_sha256"] == digest(record["body"].encode("utf-8"))
            assert item["template_hash"] == content_hash(record)
        assert validate_expansion(artifact, context, result, ROOT)["problem_ids"] == selected


@pytest.mark.parametrize("key", ["task_id", "context_hash", "knowledge_hash", "retrieval_hash", "graph_version"])
def test_wrong_request_identity_is_rejected(artifact, context, key):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    request = request_for(artifact, context, [identifier])
    request[key] = "v9999" if key == "graph_version" else "other-task" if key == "task_id" else digest(b"wrong")
    with pytest.raises(GraphError, match="身份不一致"):
        expand(artifact, context, request, ROOT)


def test_changed_context_and_knowledge_cannot_reuse_request(artifact, context):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    request = request_for(artifact, context, [identifier])
    changed_context = deepcopy(context)
    changed_context["attributes"]["platform"] = "dav-3510"
    with pytest.raises(GraphError, match="身份不一致"):
        expand(artifact, changed_context, request, ROOT)
    changed = deepcopy(artifact)
    next(record for record in changed["records"] if record["id"] == identifier)["body"] += "\n另一份知识内容"
    with pytest.raises(GraphError, match="身份不一致"):
        expand(changed, context, request, ROOT)


@pytest.mark.parametrize("invalid_id", ["problem.task-local", "action.reuse_input_tiles", "../source.md"])
def test_unregistered_or_nonproblem_cannot_claim_template_reading(artifact, context, invalid_id):
    request = request_for(artifact, context, [invalid_id])
    with pytest.raises(GraphError, match="已注册 Problem"):
        expand(artifact, context, request, ROOT)


def test_duplicate_selection_invalid_related_id_and_empty_reason_are_rejected(artifact, context):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    request = request_for(artifact, context, [identifier, identifier])
    with pytest.raises(GraphError, match="重复"):
        expand(artifact, context, request, ROOT)
    request["selections"].pop()
    request["selections"][0]["related_problem_ids"] = ["problem.task-local"]
    with pytest.raises(GraphError, match="关联机制"):
        expand(artifact, context, request, ROOT)
    request["selections"][0]["related_problem_ids"] = []
    request["selections"][0]["reason"] = "   "
    with pytest.raises(GraphError, match="reason"):
        expand(artifact, context, request, ROOT)


def test_missing_body_is_not_a_successful_expansion(artifact, context):
    changed = deepcopy(artifact)
    record = next(record for record in changed["records"] if record["kind"] == "problem")
    record["body"] = "   "
    request = request_for(changed, context, [record["id"]])
    with pytest.raises(GraphError, match="缺少正文"):
        expand(changed, context, request, ROOT)


def test_scope_unknown_or_mismatch_is_reported_without_choosing_or_excluding(artifact, context):
    changed = deepcopy(artifact)
    record = next(record for record in changed["records"] if record["kind"] == "problem")
    record["scope"]["platforms"] = ["dav-2201"]
    for platform, expected in ((None, "unknown"), ("dav-3510", "mismatch")):
        observed = deepcopy(context)
        if platform is None:
            observed["attributes"].pop("platform")
        else:
            observed["attributes"]["platform"] = platform
        request = request_for(changed, observed, [record["id"]])
        result = expand(changed, observed, request, ROOT)
        assert result["entries"][0]["scope_status"] == expected
        assert not any(key in result["entries"][0] for key in ("status", "selected_action", "score"))


def test_new_contract_rejects_undeclared_request_and_result_fields(artifact, context):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    request = request_for(artifact, context, [identifier])
    forged = deepcopy(request)
    forged["selected_action"] = "action.reuse_input_tiles"
    with pytest.raises(GraphError, match="Additional properties"):
        expand(artifact, context, forged, ROOT)
    result = expand(artifact, context, request, ROOT)
    result["entries"][0]["causal_probability"] = 1
    with pytest.raises(GraphError, match="Additional properties"):
        validate_expansion(artifact, context, result, ROOT)


@pytest.mark.parametrize("field", ["body", "body_sha256", "analysis", "sources", "reason", "scope_status"])
def test_replay_detects_content_source_reason_and_applicability_tampering(artifact, context, field):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    result = expand(artifact, context, request_for(artifact, context, [identifier]), ROOT)
    entry = result["entries"][0]
    if field == "analysis":
        entry[field]["mechanism_chain"].append("未在知识中出现的机制")
    elif field == "sources":
        entry[field][0]["sha256"] = digest(b"wrong-source")
    elif field == "body_sha256":
        entry[field] = digest(b"wrong-body")
    elif field == "scope_status":
        entry[field] = "mismatch" if entry[field] != "mismatch" else "match"
    else:
        entry[field] += "被修改"
    with pytest.raises(GraphError, match="已改变"):
        validate_expansion(artifact, context, result, ROOT)


def test_cli_can_write_once_and_replay_without_altering_retrieve(artifact, context, tmp_path, monkeypatch):
    identifier = next(record["id"] for record in artifact["records"] if record["kind"] == "problem")
    request = request_for(artifact, context, [identifier])
    context_path, request_path, output_path = (tmp_path / name for name in ("context.json", "request.json", "read.json"))
    context_path.write_text(json.dumps(context))
    request_path.write_text(json.dumps(request))
    monkeypatch.setattr(diagnosis, "verify", lambda root: artifact)
    arguments = ["diagnosis", "expand", "--root", str(ROOT), "--context", str(context_path),
                 "--request", str(request_path), "--output", str(output_path)]
    result = cli.run(cli._parser().parse_args(arguments))
    assert json.loads(output_path.read_text()) == result
    with pytest.raises(FileExistsError):
        cli.run(cli._parser().parse_args(arguments))
    replay = cli.run(cli._parser().parse_args([
        "diagnosis", "verify-expansion", "--root", str(ROOT), "--context", str(context_path),
        "--input", str(output_path)]))
    assert replay["valid"] is True
    plain = cli.run(cli._parser().parse_args([
        "diagnosis", "retrieve", "--root", str(ROOT), "--context", str(context_path)]))
    assert plain == retrieve(artifact, context, ROOT)

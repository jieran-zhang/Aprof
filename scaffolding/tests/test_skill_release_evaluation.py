import importlib.util
import asyncio
import json
from pathlib import Path
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "collection/scripts"
sys.path.insert(0, str(SCRIPTS))
import evaluate_skill_release as evaluation


def test_matrix_has_all_45_predetermined_pairs():
    plan = {"seeds": [4101, 4102, 4103], "operators": ["a", "b", "c", "d", "e"]}
    rows = evaluation.matrix(plan)
    assert len(rows) == len({row["run_id"] for row in rows}) == 45
    assert rows == evaluation.matrix(plan)
    assert {row["arm"] for row in rows} == set(evaluation.ARMS)
    with pytest.raises(ValueError, match="unique"):
        evaluation.matrix({"seeds": [4101, 4102, 4103], "operators": ["gelu"] * 5})


@pytest.mark.parametrize("proposer,reviewer,total", [
    (56000, 8000, 64001), (56000, 8000, 56000), (True, 0, 1), (-1, 0, -1),
])
def test_model_cost_must_be_exact_nonnegative_integers(proposer, reviewer, total):
    assert not evaluation.valid_model_cost(proposer, reviewer, total)


def test_model_tokens_are_cost_only_without_old_role_or_total_limits():
    for values in ((56000, 8000, 64000), (56001, 0, 56001), (0, 8001, 8001),
                   (56001, 8000, 64001), (120000, 25000, 145000)):
        assert evaluation.valid_model_cost(*values)
    assert evaluation.MODEL_BUDGETS == {"proposer": None, "reviewer": None}


@pytest.mark.parametrize("operators", [["gelu"] * 5, ["a", "b", "c", "d", "e"]])
def test_freeze_refuses_wrong_validation_inventory(tmp_path, operators):
    plan = tmp_path / "plan.json"
    evaluation.dump(plan, {"equal_budget_evaluation": {"seeds": [4101, 4102, 4103], "operators": operators}})
    with pytest.raises(ValueError, match="predetermined"):
        evaluation.validate_freeze({"state": "frozen_for_validation", "schema_version": 1,
                                   "plan": {"path": str(plan), "sha256": evaluation.sha(plan)}})


@pytest.mark.parametrize("entrypoint", ["prepare", "execute", "publication", "worker"])
def test_unenforced_worker_build_budget_blocks_launch_and_publication(tmp_path, entrypoint):
    plan = tmp_path / "plan.json"
    evaluation.dump(plan, {"equal_budget_evaluation": {"seeds": [4101, 4102, 4103],
        "operators": list(evaluation.VALIDATION_OPERATORS), "candidate_limit": 1,
        "build_limit": 1, "timing_limit": 1, "full_profile_limit": 1,
        "wall_time_limit_seconds": 3600, "model_token_limit": None, "budget_policy": evaluation.BUDGET_POLICY,
        "model_budgets": evaluation.MODEL_BUDGETS}})
    manifest = {"state": "frozen_for_validation", "schema_version": 1,
        "budget_policy": evaluation.BUDGET_POLICY,
        "plan": {"path": str(plan), "sha256": evaluation.sha(plan)},
        # A self-report cannot replace captured tool-inventory qualification.
        "worker_build_budget_attestation": {"accepted": True, "worker_builds": 0}}
    evaluation.dump(tmp_path / "freeze.json", manifest)
    with pytest.raises(ValueError, match="authoritative tool-capture qualification"):
        if entrypoint == "prepare":
            evaluation.prepare(tmp_path / "freeze.json", tmp_path / "output")
        elif entrypoint == "execute":
            evaluation.execute(tmp_path, "any-run")
        elif entrypoint == "publication":
            evaluation.verify_publication(tmp_path, release=tmp_path)
        else:
            asyncio.run(evaluation.run_worker(tmp_path, tmp_path / "output", "model", "effort", None, 3600))
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "runs").exists()


def test_baseline_identity_rejects_changed_payload_with_same_release_label(tmp_path, monkeypatch):
    original = tmp_path / "skill-libs/graph-base/0.5.0"
    altered = tmp_path / "altered"
    original.mkdir(parents=True)
    altered.mkdir()
    metadata = {"status": "stable", "release_id": "graph-base/0.5.0"}
    for where, contents in ((original, "original"), (altered, "changed")):
        evaluation.dump(where / "release.json", metadata)
        (where / "skill.md").write_text(contents)
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    import aprof_layout

    class Module:
        def verify(self, root):
            assert root == original
            return metadata

    monkeypatch.setattr(aprof_layout, "release_module", lambda _: Module())
    with pytest.raises(ValueError, match="canonical"):
        evaluation.verify_baseline_library(altered)
    assert evaluation.verify_baseline_library(original) == metadata


def test_primary_bootstrap_cannot_be_rescued_by_no_change():
    baseline = {"correct": True, "deployed_speedup": 1, "regression_cases": []}
    improved = {**baseline, "deployed_speedup": 1.1}
    result = evaluation.paired_comparison([(baseline, improved)] * 15)
    assert result["bootstrap_95_lower"] == pytest.approx(1.1)
    assert evaluation.paired_comparison([(baseline, baseline)] * 15)["bootstrap_95_lower"] == 1
    bad = {**improved, "correct": False}
    assert not evaluation.paired_comparison([(baseline, bad)] + [(baseline, improved)] * 14)["no_correctness_decline"]


def test_gate_refuses_unfrozen_or_no_evidence(tmp_path):
    with pytest.raises(ValueError, match="freeze"):
        evaluation.validate_freeze({"state": "not_run", "schema_version": 1})
    with pytest.raises(FileNotFoundError):
        evaluation.verify_publication(tmp_path, release=tmp_path)


def test_library_payload_hash_survives_sealing_but_detects_skill_edits(tmp_path):
    (tmp_path / "skill.md").write_text("frozen skill")
    frozen = evaluation.library_sha(tmp_path)
    (tmp_path / "release.json").write_text('{"status":"stable"}')
    assert evaluation.library_sha(tmp_path) == frozen
    assert evaluation.tree_sha(tmp_path) != frozen
    evaluation.checked({"path": str(tmp_path), "sha256": frozen}, library=True)
    (tmp_path / "skill.md").write_text("changed skill")
    assert evaluation.library_sha(tmp_path) != frozen


def test_existing_worker_without_usage_cannot_be_scored_as_fallback(tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    output = tmp_path / "evaluation"
    output.mkdir()
    plan = {"seeds": [4101, 4102, 4103], "operators": list(evaluation.VALIDATION_OPERATORS)}
    manifest = {"libraries": {"candidate": {"path": str(library), "sha256": evaluation.library_sha(library)}}}
    evaluation.dump(output / "freeze.json", manifest)
    roster = evaluation.matrix(plan)
    evaluation.dump(output / "matrix.json", {"freeze_sha256": evaluation.sha(output / "freeze.json"), "runs": roster})
    monkeypatch.setattr(evaluation, "validate_freeze", lambda _: plan)
    directory = output / "runs" / roster[0]["run_id"]
    worker = {"status": "missing_usage_receipt", "usage": None}
    evaluation.dump(directory / "result.json", {**roster[0], "worker": worker, "status": "missing_usage_receipt"})
    evaluation.dump(directory / "worker/worker.json", worker)
    (directory / "worker/events.jsonl").write_text("")
    with pytest.raises(ValueError, match="authoritative model usage"):
        evaluation.verify_publication(output, release=library)


def test_candidate_cannot_change_oracle_or_symlink(tmp_path):
    before, after = tmp_path / "baseline", tmp_path / "candidate"
    before.mkdir()
    after.mkdir()
    (before / "kernel.asc").write_text("old")
    (after / "kernel.asc").write_text("new")
    assert evaluation.validate_candidate(before, after) == ["kernel.asc"]
    (after / "oracle.py").write_text("tampered")
    with pytest.raises(ValueError, match="protected"):
        evaluation.validate_candidate(before, after)
    (after / "oracle.py").unlink()
    (after / "external").symlink_to(before, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        evaluation.validate_candidate(before, after)


def test_score_checks_hashes_and_reports_regressions(tmp_path):
    raw = tmp_path / "timing.json"
    raw.write_text("{}")
    receipt = {"counts": {"candidates": 1, "builds": 1, "timing_groups": 1, "profile_groups": 1},
               "full_declared_correctness": True, "evidence": [{"path": str(raw), "sha256": evaluation.sha(raw)}],
               "cases": [{"case_id": 1, "correct": True, "baseline_us": 2, "candidate_us": 1},
                         {"case_id": 2, "correct": True, "baseline_us": 1, "candidate_us": 2}]}
    assert evaluation.score(receipt)["regression_cases"] == [2]
    raw.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        evaluation.score(receipt)


def test_current_profiler_json_bundle_binds_clean_sources_and_all_cas_files(tmp_path):
    profiler_path = evaluation.ROOT / "skill-libs/graph-base/1.0.0/skills/ascendc-aprof-profiling/scripts/profile_capture.py"
    spec = importlib.util.spec_from_file_location("eval_profile_test", profiler_path)
    profiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profiler)
    tree = tmp_path / "source"
    tree.mkdir()
    kernel = tree / "kernel.asc"
    kernel.write_text("kernel-v1")
    original = tmp_path / "original.asc"
    original.write_text(kernel.read_text())
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"schema_version": "1.0.0", "files": profiler.source_inventory(tree)}))
    objects = {evaluation.sha(original): original, evaluation.sha(bundle): bundle}

    class Store:
        def verify_artifact(self, reference):
            path = objects[reference]
            assert evaluation.sha(path) == reference
            return path

    evaluation.validate_source_bundle(Store(), evaluation.sha(bundle), tree, profiler.source_inventory)
    kernel.write_text("kernel-v2")
    with pytest.raises(ValueError, match="differs"):
        evaluation.validate_source_bundle(Store(), evaluation.sha(bundle), tree, profiler.source_inventory)
    kernel.write_text("kernel-v1")
    del objects[evaluation.sha(original)]
    with pytest.raises(KeyError):
        evaluation.validate_source_bundle(Store(), evaluation.sha(bundle), tree, profiler.source_inventory)


def test_controller_builds_copy_and_owns_device_lock(tmp_path, monkeypatch):
    directory = tmp_path / "trial"
    work = directory / "worker/root/work"
    for role in ("baseline", "candidate"):
        (work / role).mkdir(parents=True)
        (work / role / "kernel.asc").write_text(role)
    (work / "candidate_plan.json").write_text("{}")
    recorded = []

    def job(value):
        recorded.append(value)
        copied = Path(value["argv"][1])
        (copied / "candidate/kernel.asc").write_text("controller changed its own copy")
        return {"status": "failed"}

    monkeypatch.setattr(evaluation, "run_job", job)
    manifest = {"evaluator": {"argv": ["controller", "{workspace}"], "physical_device": 3}}
    result = {"worker": {"status": "completed"}}
    evaluation.evaluate_candidate(manifest, {"wall_time_limit_seconds": 3600},
        {"run_id": "trial", "operator": "gelu", "seed": 4101}, directory, work, time.monotonic(), result)
    assert "physical_device" not in recorded[0]
    assert recorded[0]["environment"]["ASCEND_RT_VISIBLE_DEVICES"] == "3"
    assert recorded[0]["environment"]["APROF_LOGICAL_DEVICE"] == "0"
    assert (work / "candidate/kernel.asc").read_text() == "candidate"


def test_candidate_error_is_terminal_record_without_fake_gate(tmp_path, monkeypatch):
    plan = {"seeds": [4101], "operators": ["gelu"], "model_token_limit": 64000, "wall_time_limit_seconds": 3600}
    manifest = {"model": {"name": "model", "reasoning_effort": "effort"}, "target_speedup": 1.03,
        "worker_qualification": {}, "tasks": {"gelu": {"route_registry": {}}}, "libraries": {"candidate": {"path": str(tmp_path)}}}
    evaluation.dump(tmp_path / "freeze.json", manifest)
    evaluation.dump(tmp_path / "matrix.json", {"freeze_sha256": evaluation.sha(tmp_path / "freeze.json"), "runs": evaluation.matrix(plan)})
    monkeypatch.setattr(evaluation, "validate_freeze", lambda _: plan)
    monkeypatch.setattr(evaluation, "stage", lambda *_: None)

    async def worker(_workspace, output, *_, **kwargs):
        evaluation.dump(output / "root/work/candidate_plan.json", {"transformation_id": "transformation.test"})
        return {"status": "completed", "usage": {"totalTokens": 100}}

    def fail(*_):
        raise ValueError("protected oracle changed")

    monkeypatch.setattr(evaluation, "run_worker", worker)
    monkeypatch.setattr(evaluation, "review_candidate", lambda *_: None)
    monkeypatch.setattr(evaluation, "evaluate_candidate", fail)
    result = evaluation.execute(tmp_path, evaluation.matrix(plan)[0]["run_id"])
    assert result["status"] == "candidate_or_controller_error"
    assert result["deployed_speedup"] == 1
    assert "controller" not in result
    assert list((tmp_path / "runs").glob("*/result.json"))


@pytest.mark.parametrize("available,staging,remaining", [(10, 7, 3), (10, 12, None), (.6, .2, .4)])
def test_controller_staging_consumes_shared_deadline(tmp_path, monkeypatch, available, staging, remaining):
    directory = tmp_path / "trial"
    work = directory / "worker/root/work"
    for role in ("baseline", "candidate"):
        (work / role).mkdir(parents=True)
        (work / role / "kernel.asc").write_text(role)
    (work / "candidate_plan.json").write_text("{}")
    clock, jobs = [3600 - available], []
    monkeypatch.setattr(evaluation.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(evaluation, "run_job", lambda job: jobs.append(job) or {"status": "failed"})
    # Simulate time spent materializing the controller workspace.
    monkeypatch.setattr(evaluation.shutil, "copytree", lambda *args, **kwargs: clock.__setitem__(0, clock[0] + staging))
    result = {"worker": {"status": "completed"}}
    evaluation.evaluate_candidate({"evaluator": {"argv": ["controller", "{seconds}"], "physical_device": 0}},
        {"wall_time_limit_seconds": 3600}, {"run_id": "trial", "operator": "gelu", "seed": 4101},
        directory, work, 0, result)
    if remaining is None:
        assert jobs == []
        assert result["status"] == "over_wall_time_budget"
    else:
        assert len(jobs) == 1
        assert jobs[0]["timeout_seconds"] == pytest.approx(remaining)
        assert float(jobs[0]["argv"][1]) == pytest.approx(remaining)


def test_late_online_result_cannot_claim_deployment_or_time_to_target(tmp_path, monkeypatch):
    plan = {"seeds": [4101], "operators": ["gelu"], "wall_time_limit_seconds": 3600}
    manifest = {"model": {"name": "model", "reasoning_effort": "effort"}, "target_speedup": 1.03,
        "worker_qualification": {}, "tasks": {"gelu": {"route_registry": {}}},
        "libraries": {"candidate": {"path": str(tmp_path)}}}
    evaluation.dump(tmp_path / "freeze.json", manifest)
    evaluation.dump(tmp_path / "matrix.json", {"freeze_sha256": evaluation.sha(tmp_path / "freeze.json"),
        "runs": evaluation.matrix(plan)})
    clock = [0.0]
    monkeypatch.setattr(evaluation.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(evaluation, "validate_freeze", lambda _: plan)
    monkeypatch.setattr(evaluation, "stage", lambda *_: None)

    async def worker(_workspace, output, *_, **kwargs):
        evaluation.dump(output / "root/work/candidate_plan.json", {"transformation_id": "transformation.test"})
        return {"status": "completed", "usage": {"totalTokens": 100000}}

    def late(_manifest, _plan, _row, _directory, _workspace, _started, result):
        result.update(status="passed", deployed_speedup=1.2)
        clock[0] = 3600.1

    monkeypatch.setattr(evaluation, "run_worker", worker)
    monkeypatch.setattr(evaluation, "review_candidate", lambda *_: None)
    monkeypatch.setattr(evaluation, "evaluate_candidate", late)
    result = evaluation.execute(tmp_path, evaluation.matrix(plan)[0]["run_id"])
    assert result["status"] == "over_wall_time_budget"
    assert result["deployed_speedup"] == 1.0
    assert result["time_to_target_seconds"] is None
    assert result["tokens_to_target"] is None
    assert result["total_model_tokens"] == 100000


@pytest.mark.parametrize("phase", ["stage", "worker"])
def test_worker_lifecycle_failure_preserves_unknown_usage_and_elapsed_cost(tmp_path, monkeypatch, phase):
    plan = {"seeds": [4101], "operators": ["gelu"], "model_token_limit": 64000, "wall_time_limit_seconds": 3600}
    manifest = {"model": {"name": "model", "reasoning_effort": "effort"}, "target_speedup": 1.03,
        "worker_qualification": {}, "tasks": {"gelu": {"route_registry": {}}}, "libraries": {"candidate": {"path": str(tmp_path)}}}
    evaluation.dump(tmp_path / "freeze.json", manifest)
    evaluation.dump(tmp_path / "matrix.json", {"freeze_sha256": evaluation.sha(tmp_path / "freeze.json"), "runs": evaluation.matrix(plan)})
    monkeypatch.setattr(evaluation, "validate_freeze", lambda _: plan)

    def stage(*_):
        if phase == "stage":
            raise OSError("source staging failed")

    async def worker(_workspace, output, *_args, **kwargs):
        output.mkdir()
        (output / "events.jsonl").write_text('{"method":"thread/started"}\n')
        raise RuntimeError("app-server transport closed before usage receipt")

    monkeypatch.setattr(evaluation, "stage", stage)
    monkeypatch.setattr(evaluation, "run_worker", worker)
    result = evaluation.execute(tmp_path, evaluation.matrix(plan)[0]["run_id"])
    assert result["status"] == phase + "_error"
    assert result["worker"] is None
    assert result["model_usage_status"].startswith("unavailable")
    assert result["duration_seconds"] > 0
    assert result["deployed_speedup"] == 1
    assert result["tokens_to_target"] is None
    assert "controller" not in result
    if phase == "worker":
        assert len(result["partial_worker_evidence"]) == 1
        evaluation.checked(result["partial_worker_evidence"][0])
    assert list((tmp_path / "runs").glob("*/result.json"))


def test_worker_startup_exception_cleans_staged_credentials(tmp_path, monkeypatch):
    import isolated_eval_worker as worker
    output = tmp_path / "output"
    monkeypatch.setenv("CODEX_HOME", "/evaluation-auth")

    async def fail(*_, **kwargs):
        auth = output / "root/evaluation-auth"
        auth.mkdir(parents=True)
        (auth / "auth.json").write_text("test-only-placeholder")
        raise OSError("subprocess startup failed")

    monkeypatch.setattr(worker, "_run", fail)
    with pytest.raises(OSError, match="startup"):
        asyncio.run(worker.run(tmp_path, output, "model", "effort", 64000, 3600, probe=True))
    assert not (output / "root/evaluation-auth").exists()

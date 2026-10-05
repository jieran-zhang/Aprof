"""CPU-only evidence/ledger fixtures; no collectors or runtime stores."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import builtins
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import msprof_exploration_campaign as campaign
import shared_context_campaign as old


def h(number):
    return "sha256:" + f"{number:064x}"


def save(path, data):
    path.write_text(json.dumps(data))


def tree(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@pytest.fixture
def prior(tmp_path):
    baselines = {name: h(i + 1) for i, name in enumerate(old.WORKLOADS)}
    inherited = {"candidate_id": "exp001", "source_hash": h(100), "patch_hash": h(101),
                 "source_parent": {"candidate_id": None, "source_hash": baselines["exp"]},
                 "probes": [{"case_id": 3, "reason": "BF16 boundary"}, {"case_id": 9, "reason": "tail"}],
                 "origin": {"run_id": "original-run"}}
    ledger = old.prepare_ledger(tmp_path / "prior-ledger", old.make_config("previous-run", baselines, inherited, h(900)))
    ledger.resume(event_id="resume", reason="fixture")
    for kind, plan in (("build", {"source_hash": h(100)}), ("profile", {"case_ids": [1], "capture_window": {"count": 5}})):
        ledger.start_stage(event_id="start-" + kind, workload="exp", candidate_id="exp001", stage_id=kind, kind=kind, plan=plan)
        ledger.finish_stage(event_id="finish-" + kind, workload="exp", stage_id=kind, outcome="failed", reason="fixture failure",
                            evidence={"log_ref": h(901)})
    ledger.observation(event_id="observe", workload="exp", candidate_id="exp001", observation_id="old-exp-observation",
                       stage_ids=["build", "profile"], feedback={"reason": "retained failure"})
    ledger.checkpoint(event_id="checkpoint", checkpoint_id="prior-checkpoint", reason="paused", next_action="plan", resources_released=True)
    status = ledger.status()
    remaining = {name: task["remaining"] for name, task in status["tasks"].items()}
    delivery = tmp_path / "delivery.json"
    save(delivery, {"remaining_budgets": remaining})
    closure_refs = {}
    for name, task in status["tasks"].items():
        path = tmp_path / (name + "-closure.json")
        save(path, {"operator": name, "split": task["split"], "used": task["used"], "remaining": task["remaining"]})
        closure_refs[name] = {"closure": str(path)}
    path = tmp_path / "checkpoint-final.json"
    save(path, {"schema_version": "shared_context_checkpoint_pointer_v1", "status": "paused", "resources_released": True,
                "ledger": str(ledger.directory), "ledger_head": status["head_hash"], "ledger_config_hash": status["config_hash"],
                "remaining_budgets": remaining, "qualification": closure_refs,
                "delivery": {"path": str(delivery), "sha256": campaign._file_hash(delivery)}})
    return path


@pytest.fixture
def ledger(tmp_path, prior):
    return campaign.create(tmp_path / "new-ledger", campaign_id="new-run", prior_checkpoint=prior)


def register(ledger, cid="mish001", source=200, basis=None, parent=None, workload="mish"):
    if not campaign._safe_source(ledger.state["tasks"][workload], None):
        baseline = ledger.config["tasks"][workload]["baseline_source_hash"]
        for kind in ("build", "correctness", "runtime"):
            sid = workload + "-baseline-" + kind
            start(ledger, sid, kind, {"source_hash": baseline, "case_ids": campaign.ALL_CASES}, cid=None, workload=workload)
            finish(ledger, sid, native=kind != "build", workload=workload, prepared=kind == "correctness")
    return ledger.register(event_id="register-" + cid, workload=workload, candidate_id=cid, source_hash=h(source), patch_hash=h(source + 1000),
        source_parent=parent or {"candidate_id": None, "source_hash": ledger.config["tasks"][workload]["baseline_source_hash"]}, decision_basis=basis or [])


def start(ledger, sid, kind, plan=None, cid="mish001", workload="mish", event_id=None):
    return ledger.start(event_id=event_id or "start-" + sid, workload=workload, stage_id=sid, kind=kind,
                        candidate_id=cid, plan=plan or {"command_manifest_ref": h(500)})


def finish(ledger, sid, outcome="success", samples=0, native=False, workload="mish", event_id=None, costs=None, prepared=False):
    return ledger.finish(event_id=event_id or "finish-" + sid, workload=workload, stage_id=sid, outcome=outcome,
                         native_started=native, formal_samples=samples, actual_costs=costs,
                         evidence={"record_ref": h(501), "prepared_output_checked": prepared},
                         reason="recorded failure" if outcome != "success" else None)


def ready(ledger, cid="mish001", workload="mish", suffix=""):
    stages = []
    for kind in ("build", "correctness", "runtime"):
        sid = f"{cid}-{kind}{suffix}"
        plan = {"case_ids": campaign.ALL_CASES} if kind == "correctness" else {"manifest_ref": h(500)}
        start(ledger, sid, kind, plan, cid=cid, workload=workload)
        finish(ledger, sid, native=kind != "build", workload=workload, prepared=kind == "correctness")
        stages.append(sid)
    return stages


def plan(ledger, cid="mish001", purpose="search", finals=None, workload="mish"):
    return campaign.timing_plan(ledger.state["tasks"][workload]["candidates"][cid],
                                ledger.config["tasks"][workload]["baseline_source_hash"], purpose=purpose,
                                manifest_ref=h(700), final_candidate_ids=finals)


def timed(ledger, sid, cid="mish001", finals=None, purpose="search", workload="mish"):
    value = plan(ledger, cid, purpose, finals, workload)
    start(ledger, sid, "timing", value, cid=cid, workload=workload)
    finish(ledger, sid, samples=campaign.expected_samples(value), native=True, workload=workload,
           costs={"timed_complete_calls": campaign.expected_complete_calls(value)})
    return sid


def observe(ledger, oid, stages, cid="mish001", workload="mish", quality=None):
    return ledger.observe(event_id="observe-" + oid, workload=workload, candidate_id=cid, observation_id=oid,
                          stage_ids=stages, feedback={"action": "continue with uncertainty"}, report_ref=h(710), quality=quality)


def test_import_all_budget_dimensions_stable_identity_and_split_isolation(ledger, prior, tmp_path):
    status = ledger.status()
    assert set(status["tasks"]) == set(campaign.TRAIN_WORKLOADS)
    exp = status["tasks"]["exp"]
    assert exp["used"] == dict(source=1, build=1, timing_groups=0, profile_groups=1)
    assert exp["remaining"] == dict(source=5, build=5, timing_groups=6, profile_groups=2)
    assert exp["candidates"]["exp001"]["stable_id"] == "original-run/train/exp001"
    assert exp["new_source_attempts"] == exp["new_rounds_started"] == 0
    assert [p["case_id"] for p in exp["candidates"]["exp001"]["probes"]] == [3, 9]
    assert ledger.config["policy"]["repeat"] == 10
    assert old.PROTOCOL == "shared_context_paired_v1"
    validation = campaign.create(tmp_path / "validation-ledger", campaign_id="validation-run", prior_checkpoint=prior, workloads=["gelu"])
    assert set(validation.status()["tasks"]) == {"gelu"}
    assert not validation.status(split="train")["tasks"]
    assert b'"exp001"' not in (validation.directory / "config.json").read_bytes()


@pytest.mark.parametrize("fault", ["remaining", "delivery", "closure", "head", "baseline"])
def test_predecessor_tampering_fails_before_new_directory(prior, tmp_path, fault):
    value = json.loads(prior.read_text())
    kwargs = {}
    if fault == "remaining":
        value["remaining_budgets"]["exp"]["build"] = 6
        save(prior, value)
    elif fault == "delivery":
        Path(value["delivery"]["path"]).write_text("{}")
    elif fault == "closure":
        path = Path(value["qualification"]["exp"]["closure"])
        closure = json.loads(path.read_text()); closure["used"]["profile_groups"] = 0; save(path, closure)
    elif fault == "head":
        value["ledger_head"] = h(123); save(prior, value)
    else:
        kwargs["baselines"] = {name: h(666) for name in campaign.TRAIN_WORKLOADS}
    out = tmp_path / "rejected"
    with pytest.raises(ValueError):
        campaign.create(out, campaign_id="new", prior_checkpoint=prior, **kwargs)
    assert not out.exists()


def test_same_source_multiple_observations_failure_is_feedback_and_no_extra_round(ledger):
    register(ledger)
    stages = ready(ledger)
    stages.append(timed(ledger, "search-1"))
    observe(ledger, "o1", stages, quality={"calibration": "insufficient_precision", "performance": "inconclusive"})
    stages = [timed(ledger, "search-2")]
    with pytest.raises(ValueError, match="close source feedback"):
        register(ledger, "mish002", 201, basis=["o1"])
    observe(ledger, "o2", stages, quality={"performance": "regression"})
    task = ledger.status()["tasks"]["mish"]
    assert task["used"]["source"] == task["new_source_attempts"] == task["new_rounds_started"] == 1
    assert task["used"]["timing_groups"] == 2
    assert list(task["observations"]) == ["o1", "o2"]
    with pytest.raises(ValueError, match="same source"):
        register(ledger, "renamed", 200, basis=["o2"])
    register(ledger, "mish002", 201, basis=["o2"], parent={"candidate_id": "mish001", "source_hash": h(200)})
    assert len(plan(ledger, "mish002")["comparisons"]) == 2


def test_three_new_source_attempts_including_repairs_and_custom_exp_limit(ledger, prior, tmp_path):
    basis = []
    for i in range(3):
        cid = f"mish{i}"
        register(ledger, cid, 200 + i, basis=basis)
        start(ledger, "build-" + cid, "build", cid=cid)
        finish(ledger, "build-" + cid, "build_failed")
        observe(ledger, "o" + cid, ["build-" + cid], cid)
        basis = ["o" + cid]
    with pytest.raises(ValueError, match="round limit"):
        register(ledger, "mish4", 204, basis=basis)
    assert ledger.status()["tasks"]["mish"]["new_rounds_started"] == 3
    limited = campaign.create(tmp_path / "limited", campaign_id="limited", prior_checkpoint=prior, max_new_rounds={"exp": 2})
    assert limited.status()["tasks"]["exp"]["remaining_new_source_rounds"] == 2
    assert limited.status()["tasks"]["mish"]["remaining_new_source_rounds"] == 3


def test_three_search_candidates_reserve_all_three_full_groups(ledger):
    cids = []
    for i in range(3):
        cid = f"mish{i}"
        register(ledger, cid, 200 + i, basis=[] if i == 0 else ["o" + cids[-1]])
        cids.append(cid)
        stages = ready(ledger, cid)
        stages.append(timed(ledger, "search-" + cid, cid, finals=list(cids)))
        observe(ledger, "o" + cid, stages, cid)
    before = tree(ledger.directory)
    with pytest.raises(ValueError, match="reserved full"):
        start(ledger, "extra-search", "timing", plan(ledger, cids[-1], finals=cids), cid=cids[-1])
    assert before == tree(ledger.directory)
    final_plans = {cid: plan(ledger, cid, purpose="final") for cid in cids}
    ledger.freeze(event_id="freeze", workload="mish", candidate_ids=cids, final_plans=final_plans, reason="stop search")
    frozen = deepcopy(ledger.state["tasks"]["mish"]["frozen_roster"])
    for cid in cids:
        timed(ledger, "final-" + cid, cid, purpose="final")
        observe(ledger, "final-o" + cid, ["final-" + cid], cid)
    assert ledger.status()["tasks"]["mish"]["remaining"]["timing_groups"] == 0
    assert ledger.state["tasks"]["mish"]["frozen_roster"] == frozen
    with pytest.raises(ValueError, match="frozen"):
        register(ledger, "mish4", 204, basis=["final-o" + cids[-1]])


def test_frozen_final_plan_cannot_change_or_be_repeated(ledger):
    register(ledger)
    observe(ledger, "ready", ready(ledger))
    final = plan(ledger, purpose="final")
    ledger.freeze(event_id="freeze", workload="mish", candidate_ids=["mish001"], final_plans={"mish001": final}, reason="selected")
    wrong = deepcopy(final); wrong["manifest_ref"] = h(711)
    with pytest.raises(ValueError, match="exact frozen"):
        start(ledger, "wrong", "timing", wrong)
    timed(ledger, "final", purpose="final")
    with pytest.raises(ValueError, match="already has a stage"):
        timed(ledger, "another-final", purpose="final")


def test_six_processes_both_configurations_and_complete_call_accounting(ledger):
    register(ledger)
    ready(ledger)
    value = plan(ledger)
    assert campaign.expected_samples(value) == 4 * 6 * 2 * 30 * 2
    assert campaign.expected_complete_calls(value) == 4 * 7200
    assert value["repeat"] == 10 and value["profiler_mode"] == campaign.PROFILER_MODE
    for key, bad in (("repeat", 100), ("processes", 5), ("configurations", ["normal"]), ("case_ids", [1])):
        altered = deepcopy(value); altered[key] = bad
        with pytest.raises(ValueError, match="differs"):
            start(ledger, "bad-" + key, "timing", altered)
    start(ledger, "timing", "timing", value)
    with pytest.raises(ValueError, match="both configurations"):
        finish(ledger, "timing", samples=campaign.expected_samples(value) // 2, native=True)
    finish(ledger, "timing", "incomplete", samples=10, native=True)
    assert ledger.state["tasks"]["mish"]["used"]["timing_groups"] == 1


def test_prestart_evidence_only_once_same_plan_and_nonrefund(ledger):
    register(ledger); ready(ledger)
    value = plan(ledger)
    start(ledger, "group", "timing", value)
    with pytest.raises(ValueError, match="native_started=False"):
        finish(ledger, "group", "prestart_failure", native=True)
    finish(ledger, "group", "prestart_failure")
    altered = deepcopy(value); altered["manifest_ref"] = h(777)
    with pytest.raises(ValueError, match="immutable"):
        start(ledger, "group", "timing", altered, event_id="changed-recovery")
    start(ledger, "group", "timing", value, event_id="recover")
    finish(ledger, "group", "prestart_failure", event_id="recover-failed")
    with pytest.raises(ValueError, match="one prestart"):
        start(ledger, "group", "timing", value, event_id="third")
    assert ledger.state["tasks"]["mish"]["used"]["timing_groups"] == 1
    start(ledger, "warmup-failure", "timing", value)
    finish(ledger, "warmup-failure", "failed", native=True)
    with pytest.raises(ValueError, match="native-not-started"):
        start(ledger, "warmup-failure", "timing", value, event_id="retry-warmup")


def test_build_recovery_charges_every_launch_and_failed_feedback_cannot_disappear(ledger):
    register(ledger)
    start(ledger, "build", "build")
    finish(ledger, "build", "prestart_failure")
    start(ledger, "build", "build", event_id="recover-build")
    finish(ledger, "build", "build_failed", event_id="recovered-build-failed")
    assert ledger.state["tasks"]["mish"]["used"]["build"] == 2
    with pytest.raises(ValueError, match="every newly completed"):
        observe(ledger, "missing", [])
    observe(ledger, "failed", ["build"])
    with pytest.raises(ValueError, match="current build"):
        register(ledger, "child", 201, basis=["failed"], parent={"candidate_id": "mish001", "source_hash": h(200)})


def test_prepared_correctness_runtime_and_current_build_are_required(ledger):
    register(ledger)
    start(ledger, "build", "build"); finish(ledger, "build")
    with pytest.raises(ValueError, match="all 20"):
        start(ledger, "partial-correctness", "correctness", {"case_ids": [1]})
    start(ledger, "correctness", "correctness", {"case_ids": campaign.ALL_CASES})
    with pytest.raises(ValueError, match="prepared output"):
        finish(ledger, "correctness", native=True)
    finish(ledger, "correctness", native=True, prepared=True)
    with pytest.raises(ValueError, match="runtime"):
        start(ledger, "timing-before-runtime", "timing", plan(ledger))
    start(ledger, "runtime", "runtime"); finish(ledger, "runtime", native=True)
    start(ledger, "rebuild", "build"); finish(ledger, "rebuild")
    with pytest.raises(ValueError, match="current build"):
        start(ledger, "timing-after-rebuild", "timing", plan(ledger))


def test_fixed_costs_and_task_only_not_mechanism_profile(ledger):
    register(ledger)
    with pytest.raises(ValueError, match="not mechanism"):
        start(ledger, "wrong-profile", "profile", {"case_ids": [1], "capture_window": {"repeat": 5}, "profiler_mode": campaign.PROFILER_MODE})
    with pytest.raises(ValueError, match="cannot hide"):
        start(ledger, "wrong-control", "control", {"case_ids": [1], "source_hash": h(200), "control_type": "aa", "manifest_ref": h(400)})
    baseline = ledger.config["tasks"]["mish"]["baseline_source_hash"]
    start(ledger, "baseline-build", "build", {"source_hash": baseline}, cid=None)
    finish(ledger, "baseline-build", costs={"build_commands": 3})
    start(ledger, "aa", "control", {"source_hash": baseline, "case_ids": campaign.ALL_CASES, "control_type": "aa", "manifest_ref": h(400)}, cid=None)
    finish(ledger, "aa", native=True, costs={"native_processes": 6})
    task = ledger.status()["tasks"]["mish"]
    assert task["used"] == dict(source=1, build=0, timing_groups=0, profile_groups=0)
    assert task["fixed_costs"] == dict(build_starts=2, correctness_starts=1, runtime_starts=1, control_starts=1, build_commands=3, native_processes=6)


def test_idempotent_concurrent_start_and_collision(ledger):
    register(ledger)
    def commit(_):
        return start(campaign.Campaign(ledger.directory), "build", "build")
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(commit, range(8)))
    assert all(record == records[0] for record in records)
    assert ledger.status()["tasks"]["mish"]["used"]["build"] == 1
    with pytest.raises(ValueError, match="idempotency key"):
        start(ledger, "other-build", "build", event_id="start-build")


def test_checkpoint_resume_new_run_inheritance_and_pure_read_verification(ledger, tmp_path, monkeypatch):
    register(ledger); start(ledger, "build", "build")
    with pytest.raises(ValueError, match="finished stages"):
        ledger.checkpoint(event_id="early", checkpoint_id="cp", reason="pause", next_action="inspect", resources_released=True)
    finish(ledger, "build", "interrupted"); observe(ledger, "failure", ["build"])
    event = ledger.checkpoint(event_id="cp", checkpoint_id="cp", reason="pause", next_action="inspect", resources_released=True)
    seal = next((ledger.directory / "checkpoints").glob("*.json"))
    next_run = campaign.create(tmp_path / "next-run", campaign_id="next", prior_checkpoint=seal)
    assert next_run.state["tasks"]["mish"]["used"]["build"] == 1
    assert next_run.state["tasks"]["mish"]["candidates"]["mish001"]["stable_id"] == "new-run/train/mish001"
    with pytest.raises(ValueError, match="latest paused"):
        ledger.resume(event_id="wrong", checkpoint_id="wrong", reason="continue")
    ledger.resume(event_id="resume", checkpoint_id="cp", reason="continue")
    assert ledger.checkpoint(event_id="cp", checkpoint_id="cp", reason="pause", next_action="inspect", resources_released=True) == event
    assert ledger.status()["status"] == "active"
    before = tree(ledger.directory)
    real_open, real_path_open = builtins.open, Path.open
    def readonly_open(path, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+")
        return real_open(path, mode, *args, **kwargs)
    def readonly_path_open(path, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+")
        return real_path_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", readonly_open); monkeypatch.setattr(Path, "open", readonly_path_open)
    assert campaign.Campaign(ledger.directory).verify(expected_head=ledger.events[-1]["hash"])["read_only"]
    assert before == tree(ledger.directory)


@pytest.mark.parametrize("fault", ["event", "partial", "config", "truncated_checkpoint", "duplicate_key"])
def test_verify_rejects_corruption_without_repair(ledger, fault):
    ledger.checkpoint(event_id="cp", checkpoint_id="cp", reason="pause", next_action="inspect", resources_released=True)
    path = ledger.directory / "events.jsonl"
    data = path.read_bytes()
    if fault == "event":
        path.write_bytes(data.replace(b'"reason":"pause"', b'"reason":"other"'))
    elif fault == "partial":
        path.write_bytes(data[:-1])
    elif fault == "config":
        config = json.loads((ledger.directory / "config.json").read_text()); config["policy"]["repeat"] = 100
        save(ledger.directory / "config.json", config)
    elif fault == "truncated_checkpoint":
        path.write_bytes(data.splitlines()[0] + b"\n")
    else:
        path.write_bytes(data.replace(b'"sequence":0', b'"sequence":3,"sequence":0'))
    before = tree(ledger.directory)
    with pytest.raises(ValueError):
        campaign.Campaign(ledger.directory).verify()
    assert before == tree(ledger.directory)


def test_interrupted_checkpoint_seal_only_original_key_can_recover(ledger, monkeypatch):
    original = campaign.Campaign._seal
    def fail(self, event):
        raise OSError("crash after event commit")
    monkeypatch.setattr(campaign.Campaign, "_seal", fail)
    arguments = dict(event_id="cp", checkpoint_id="cp", reason="pause", next_action="inspect", resources_released=True)
    with pytest.raises(OSError):
        ledger.checkpoint(**arguments)
    restored = campaign.Campaign(ledger.directory)
    with pytest.raises(ValueError, match="unsealed checkpoint"):
        restored.verify()
    with pytest.raises(ValueError, match="seal committed"):
        restored.resume(event_id="resume", checkpoint_id="cp", reason="continue")
    monkeypatch.setattr(campaign.Campaign, "_seal", original)
    restored.checkpoint(**arguments)
    assert restored.verify()["valid"]


def test_quality_is_observation_not_execution_failure_and_cross_task_basis_rejected(ledger):
    register(ledger); start(ledger, "build", "build")
    with pytest.raises(ValueError, match="independent of measurement quality"):
        finish(ledger, "build", "quality_failed")
    finish(ledger, "build", "build_failed"); observe(ledger, "failed", ["build"])
    with pytest.raises(ValueError, match="same-task"):
        register(ledger, "exp002", 210, workload="exp", basis=["failed"])


def test_cli_status_verify_are_read_only(ledger, capsys):
    before = tree(ledger.directory)
    assert campaign.main(["status", "--ledger", str(ledger.directory)]) == 0
    assert json.loads(capsys.readouterr().out)["hardware_executed"] is False
    assert campaign.main(["verify", "--ledger", str(ledger.directory)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    assert before == tree(ledger.directory)


def test_baseline_parent_must_be_current_and_runtime_can_use_actual_prior_native_evidence(ledger):
    baseline = ledger.config["tasks"]["mish"]["baseline_source_hash"]
    with pytest.raises(ValueError, match="baseline parent"):
        ledger.register(event_id="unverified", workload="mish", candidate_id="unverified", source_hash=h(200), patch_hash=h(500),
                        source_parent={"candidate_id": None, "source_hash": baseline}, decision_basis=[])
    for kind in ("build", "correctness"):
        start(ledger, kind, kind, {"source_hash": baseline, "case_ids": campaign.ALL_CASES}, cid=None)
        finish(ledger, kind, native=kind != "build", prepared=kind == "correctness")
    start(ledger, "derived-runtime", "runtime", {"source_hash": baseline}, cid=None)
    with pytest.raises(ValueError, match="lifecycle evidence"):
        finish(ledger, "derived-runtime")
    ledger.finish(event_id="derived-runtime-finish", workload="mish", stage_id="derived-runtime", outcome="success", native_started=False,
                  evidence={"runtime": {"path": "/frozen/runtime.json", "sha256": h(777)}})
    register(ledger)
    assert ledger.state["tasks"]["mish"]["stages"]["derived-runtime"]["attempts"][-1]["native_started"] is False


def test_budget_caps_profile_and_source_are_independent_of_runtime(ledger):
    register(ledger)
    for index in range(3):
        sid = f"profile-{index}"
        start(ledger, sid, "profile", {"case_ids": [1], "capture_window": {"repeat": 5}, "profiler_mode": "mechanism"})
        finish(ledger, sid, "failed", native=True)
    with pytest.raises(ValueError, match="profile_groups budget"):
        start(ledger, "profile-4", "profile", {"case_ids": [1], "capture_window": {"repeat": 5}})
    assert ledger.state["tasks"]["mish"]["used"]["timing_groups"] == 0


def test_recovery_order_invalidates_correctness_after_same_build_stage_recovery(ledger):
    register(ledger)
    start(ledger, "old-build", "build"); finish(ledger, "old-build", "prestart_failure")
    ready(ledger)
    start(ledger, "old-build", "build", event_id="recovered-earlier-build")
    finish(ledger, "old-build", event_id="recovered-earlier-build-finish")
    with pytest.raises(ValueError, match="current build"):
        start(ledger, "timing", "timing", plan(ledger))


def test_validate_start_is_pure_and_atomic_start_rechecks_after_preflight(ledger):
    register(ledger)
    args = dict(event_id="start-a", workload="mish", stage_id="a", kind="build", candidate_id="mish001", plan={"manifest_ref": h(900)})
    before = tree(ledger.directory)
    state = deepcopy(ledger.state)
    assert ledger.validate_start(**args)["already_committed"] is False
    assert before == tree(ledger.directory) and state == ledger.state
    start(ledger, "competing", "build")
    with pytest.raises(ValueError, match="active"):
        ledger.start(**args)
    finish(ledger, "competing", "build_failed")
    ledger.start(**args)
    before = tree(ledger.directory)
    assert ledger.validate_start(**args)["already_committed"] is True
    assert before == tree(ledger.directory)
    with pytest.raises(ValueError, match="idempotency key"):
        ledger.validate_start(**{**args, "kind": "static"})

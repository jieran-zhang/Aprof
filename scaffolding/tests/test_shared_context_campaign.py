"""Real filesystem ledger tests. No executor, SDK, gate or device is loaded."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("shared_context_campaign", ROOT / "scaffolding/collection/scripts/shared_context_campaign.py")
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)


def h(number):
    return "sha256:" + f"{number:064x}"


def config():
    baselines = {name: h(index + 1) for index, name in enumerate(campaign.WORKLOADS)}
    inherited = dict(candidate_id="exp001", source_hash=h(101), patch_hash=h(201),
                     source_parent={"candidate_id": None, "source_hash": baselines["exp"]},
                     origin={"kind": "inherited_unbuilt", "manifest_ref": h(301)})
    return campaign.make_config("new-level1", baselines, inherited, h(500))


@pytest.fixture
def ledger(tmp_path):
    result = campaign.prepare_ledger(tmp_path / "ledger", config())
    result.resume(event_id="resume-initial", reason="authorized execution")
    return result


def register(ledger, *, name="mish", cid="mish001", source=102, probes=None, basis=None, parent=None):
    return ledger.register(event_id="register-" + cid, workload=name, candidate_id=cid, source_hash=h(source), patch_hash=h(source + 100),
                           source_parent=parent or {"candidate_id": None, "source_hash": ledger.config["tasks"][name]["baseline_source_hash"]},
                           decision_basis=basis or [], probes=probes or [], artifacts={"snapshot_ref": h(source + 200)})


def start(ledger, sid, kind, *, name="mish", cid="mish001", plan=None, event_id=None):
    return ledger.start_stage(event_id=event_id or "start-" + sid, workload=name, candidate_id=cid, stage_id=sid,
                              kind=kind, plan=plan or {"argv": ["build"]})


def finish(ledger, sid, *, name="mish", outcome="success", samples=0, event_id=None):
    return ledger.finish_stage(event_id=event_id or "finish-" + sid, workload=name, stage_id=sid, outcome=outcome,
                               formal_samples=samples, evidence={"execution_ref": h(700)}, reason="fixture result" if outcome != "success" else "")


def ready(ledger, *, name="mish", cid="mish001"):
    start(ledger, cid + "-build", "build", name=name, cid=cid)
    finish(ledger, cid + "-build", name=name)
    start(ledger, cid + "-correct", "correctness", name=name, cid=cid, plan={"case_ids": list(range(1, 21))})
    finish(ledger, cid + "-correct", name=name)
    return [cid + "-build", cid + "-correct"]


def plan(ledger, *, name="mish", cid="mish001", purpose="search"):
    return campaign.timing_plan(ledger.state["tasks"][name]["candidates"][cid], ledger.config["tasks"][name]["baseline_source_hash"],
                                purpose=purpose, manifest_ref=h(600))


def timed(ledger, sid, *, name="mish", cid="mish001", purpose="search", outcome="success"):
    declared = plan(ledger, name=name, cid=cid, purpose=purpose)
    start(ledger, sid, "timing", name=name, cid=cid, plan=declared)
    samples = len(declared["case_ids"]) * len(declared["comparisons"]) * 6 * 30 * 2
    finish(ledger, sid, name=name, outcome=outcome, samples=samples)
    return sid


def observe(ledger, oid, *, name="mish", cid="mish001", stages=None, qualified=False):
    return ledger.observation(event_id="observe-" + oid, workload=name, observation_id=oid, candidate_id=cid,
                              stage_ids=stages or [], feedback={"finding": "recorded actual outcome", "next": "inspect mechanism"},
                              quality={key: qualified for key in ("correctness", "runtime", "stable", "protocol_qualified")},
                              evidence_ref=h(701), close_feedback=True)


def bytes_tree(directory):
    return {str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.rglob("*") if path.is_file()}


def test_exact_scope_inherited_costs_and_readonly_verification(ledger):
    before = bytes_tree(ledger.directory)
    status = campaign.Ledger(ledger.directory).status()
    assert status["tasks"]["exp"]["used"] == dict(source=1, build=0, timing_groups=0, profile_groups=0)
    assert status["tasks"]["exp"]["remaining"]["source"] == 5
    assert set(status["tasks"]["exp"]["candidates"]) == {"exp001"}
    for name in campaign.WORKLOADS[1:]:
        assert status["tasks"][name]["remaining"] == campaign.BUDGETS
    assert status["historical_queue"] == "prior_only_not_queued"
    assert set(ledger.status(split="validation")["tasks"]) == {"gelu"}
    assert "gelu" not in ledger.status(split="train")["tasks"]
    assert ledger.verify(expected_head=status["head_hash"])["valid"]
    assert before == bytes_tree(ledger.directory)


def test_candidate_feedback_order_and_same_source_multiple_observations(ledger):
    register(ledger)
    with pytest.raises(ValueError, match="close candidate feedback"):
        register(ledger, cid="mish002", source=103)
    stages = ready(ledger)
    stages.append(timed(ledger, "search-1"))
    observe(ledger, "mish-o1", stages=stages, qualified=True)
    stages.append(timed(ledger, "search-2"))
    with pytest.raises(ValueError, match="close candidate feedback"):
        register(ledger, cid="mish002", source=103, basis=["mish-o1"])
    observe(ledger, "mish-o2", stages=stages, qualified=True)
    assert ledger.status()["tasks"]["mish"]["used"]["source"] == 1
    parent = {"candidate_id": "mish001", "source_hash": h(102)}
    register(ledger, cid="mish002", source=103, basis=["mish-o2"], parent=parent)
    expected = campaign.comparison_identities(ledger.state["tasks"]["mish"]["candidates"]["mish002"], h(4))
    assert len(expected) == 2
    assert [row["control_source_hash"] for row in expected] == [h(102), h(4)]


def test_failures_charge_at_start_and_cannot_be_hidden_from_feedback(ledger):
    register(ledger)
    start(ledger, "bad-build", "build")
    assert ledger.status()["tasks"]["mish"]["used"]["build"] == 1
    finish(ledger, "bad-build", outcome="build_failed")
    with pytest.raises(ValueError, match="every newly completed"):
        observe(ledger, "bad-observation")
    observe(ledger, "build-failure", stages=["bad-build"])
    with pytest.raises(ValueError, match="successful current build"):
        start(ledger, "invalid-timing", "timing", plan=plan(ledger))
    assert ledger.status()["tasks"]["mish"]["used"]["build"] == 1


def test_five_searches_reserve_final_group_and_frozen_roster_is_immutable(ledger):
    register(ledger)
    stages = ready(ledger)
    for i in range(5):
        stages.append(timed(ledger, f"search-{i}", outcome="quality_failed" if i == 1 else "success"))
    before = bytes_tree(ledger.directory)
    with pytest.raises(ValueError, match="final evaluation is reserved"):
        start(ledger, "sixth-search", "timing", plan=plan(ledger))
    assert before == bytes_tree(ledger.directory)
    observe(ledger, "search-result", stages=stages)
    final = plan(ledger, purpose="final")
    ledger.freeze(event_id="freeze-mish", workload="mish", candidate_ids=["mish001"], final_plans={"mish001": final}, reason="search stopped")
    frozen = deepcopy(ledger.state["tasks"]["mish"]["frozen_roster"])
    with pytest.raises(ValueError, match="roster is frozen"):
        register(ledger, cid="mish002", source=103, basis=["search-result"])
    changed = deepcopy(final)
    changed["manifest_ref"] = h(888)
    with pytest.raises(ValueError, match="exact frozen plan"):
        start(ledger, "changed-final", "timing", plan=changed)
    timed(ledger, "final", purpose="final")
    observe(ledger, "final-result", stages=["final"])
    assert ledger.status()["tasks"]["mish"]["remaining"]["timing_groups"] == 0
    assert ledger.state["tasks"]["mish"]["frozen_roster"] == frozen


def test_prestart_recovery_is_per_stage_same_plan_once_and_never_quality_retry(ledger):
    register(ledger)
    ready(ledger)
    frozen = plan(ledger)
    start(ledger, "g1", "timing", plan=frozen)
    finish(ledger, "g1", outcome="prestart_failure")
    start(ledger, "g1", "timing", plan=frozen, event_id="recover-g1")
    finish(ledger, "g1", outcome="prestart_failure", event_id="recovery-failed-g1")
    with pytest.raises(ValueError, match="one prestart recovery"):
        start(ledger, "g1", "timing", plan=frozen, event_id="third-g1")
    assert ledger.status()["tasks"]["mish"]["used"]["timing_groups"] == 1
    start(ledger, "g2", "timing", plan=frozen)
    finish(ledger, "g2", outcome="prestart_failure")
    altered = deepcopy(frozen)
    altered["manifest_ref"] = h(12345)
    with pytest.raises(ValueError, match="immutable"):
        start(ledger, "g2", "timing", plan=altered, event_id="changed-recovery")
    start(ledger, "g2", "timing", plan=frozen, event_id="recover-g2")
    finish(ledger, "g2", outcome="quality_failed", samples=1, event_id="quality-g2")
    with pytest.raises(ValueError, match="zero-sample prestart"):
        start(ledger, "g2", "timing", plan=frozen, event_id="retry-quality")
    assert ledger.status()["tasks"]["mish"]["stages"]["g2"]["recoveries"] == 1


def test_prestart_cannot_hide_partial_samples_and_rebuilds_charge_again(ledger):
    register(ledger)
    start(ledger, "build", "build")
    before = bytes_tree(ledger.directory)
    with pytest.raises(ValueError, match="any formal sample"):
        finish(ledger, "build", outcome="prestart_failure", samples=1)
    assert before == bytes_tree(ledger.directory)
    finish(ledger, "build", outcome="prestart_failure")
    start(ledger, "build", "build", event_id="build-recovery")
    finish(ledger, "build", event_id="build-recovery-finish")
    assert ledger.status()["tasks"]["mish"]["used"]["build"] == 2


def test_idempotency_concurrent_retries_and_key_collision(ledger):
    payload = dict(event_id="same-register", workload="mish", candidate_id="mish001", source_hash=h(102), patch_hash=h(202),
                   source_parent={"candidate_id": None, "source_hash": h(4)})
    def action(_):
        return campaign.Ledger(ledger.directory).register(**payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(action, range(2)))
    assert results[0] == results[1]
    assert ledger.status()["tasks"]["mish"]["used"]["source"] == 1
    with pytest.raises(ValueError, match="idempotency key"):
        ledger.register(**{**payload, "source_hash": h(103)})


@pytest.mark.parametrize("probes", [[{"case_id": 2, "reason": "x"}, {"case_id": 3, "reason": "y"}, {"case_id": 4, "reason": "z"}],
                                   [{"case_id": 2, "reason": ""}], [{"case_id": True, "reason": "x"}],
                                   [{"case_id": 1, "reason": "sentinel"}], [{"case_id": 2, "reason": "x"}] * 2])
def test_candidate_probe_contract(ledger, probes):
    with pytest.raises(ValueError):
        register(ledger, probes=probes)


def test_probe_and_comparison_plan_cannot_change_after_registration(ledger):
    register(ledger, probes=[{"case_id": 3, "reason": "BF16 branch"}])
    ready(ledger)
    frozen = plan(ledger)
    assert frozen["case_ids"] == [1, 8, 14, 20, 3]
    for field, value in [("case_ids", [1, 8, 14, 20, 2]), ("pairs_per_case", 31), ("repeat", 99),
                         ("comparisons", [{"control_source_hash": h(666), "candidate_source_hash": h(102)}])]:
        with pytest.raises(ValueError):
            start(ledger, "bad-" + field, "timing", plan={**frozen, field: value})


def test_checkpoint_resume_preserves_failure_budget_and_requires_latest_pin(ledger):
    register(ledger)
    start(ledger, "b", "build")
    with pytest.raises(ValueError, match="close every running"):
        ledger.checkpoint(event_id="too-early", checkpoint_id="cp", reason="interrupted", next_action="inspect", resources_released=True)
    finish(ledger, "b", outcome="interrupted")
    observe(ledger, "interrupted-build", stages=["b"])
    event = ledger.checkpoint(event_id="checkpoint", checkpoint_id="cp", reason="blocked", next_action="diagnose", resources_released=True)
    assert ledger.status()["status"] == "paused"
    with pytest.raises(ValueError, match="resume campaign"):
        start(ledger, "b2", "build")
    with pytest.raises(ValueError, match="latest checkpoint"):
        ledger.resume(event_id="wrong-resume", reason="continue")
    ledger.resume(event_id="resume-cp", checkpoint_id="cp", reason="authorized continuation")
    assert ledger.status()["tasks"]["mish"]["used"]["build"] == 1
    assert ledger.checkpoint(event_id="checkpoint", checkpoint_id="cp", reason="blocked", next_action="diagnose", resources_released=True) == event
    assert ledger.status()["status"] == "active"


@pytest.mark.parametrize("fault", ["config", "event", "partial_tail", "sealed_truncation", "duplicate_json_key"])
def test_readonly_verifier_rejects_corruption_without_repair(ledger, fault):
    ledger.checkpoint(event_id="checkpoint", checkpoint_id="cp", reason="pause", next_action="continue", resources_released=True)
    log = ledger.directory / "events.jsonl"
    if fault == "config":
        value = json.loads((ledger.directory / "config.json").read_text())
        value["tasks"]["mish"]["budgets"]["source"] = 60
        (ledger.directory / "config.json").write_text(json.dumps(value))
    elif fault == "event":
        log.write_bytes(log.read_bytes().replace(b'"authorized execution"', b'"edited execution"'))
    elif fault == "partial_tail":
        log.write_bytes(log.read_bytes()[:-1])
    elif fault == "sealed_truncation":
        log.write_bytes(b"\n".join(log.read_bytes().splitlines()[:-1]) + b"\n")
    else:
        log.write_bytes(log.read_bytes().replace(b'"sequence":0', b'"sequence":999,"sequence":0'))
    before = bytes_tree(ledger.directory)
    with pytest.raises(ValueError):
        campaign.Ledger(ledger.directory).verify()
    assert before == bytes_tree(ledger.directory)


def test_no_cross_split_feedback_or_method_cost_bypass(ledger):
    register(ledger, name="gelu", cid="gelu001", source=105)
    observe(ledger, "validation-observation", name="gelu", cid="gelu001")
    with pytest.raises(ValueError, match="same-workload"):
        register(ledger, basis=["validation-observation"])
    register(ledger)
    with pytest.raises(ValueError, match="hide candidate work"):
        start(ledger, "fake-aa", "control", plan={"case_ids": [1], "control_type": "aa", "source_hash": h(102)})
    with pytest.raises(ValueError, match="original baseline"):
        start(ledger, "fake-baseline-build", "build", cid=None, plan={"source_hash": h(102)})
    start(ledger, "real-aa", "control", cid=None, plan={"case_ids": [1], "control_type": "aa", "source_hash": h(4)})
    finish(ledger, "real-aa", outcome="quality_failed")
    assert ledger.status()["tasks"]["mish"]["used"]["timing_groups"] == 0
    assert ledger.state["tasks"]["mish"]["stage_starts"]["control"] == 1


def test_quality_cannot_be_invented_from_failed_or_missing_stages(ledger):
    register(ledger)
    with pytest.raises(ValueError, match="successful referenced correctness"):
        observe(ledger, "invented-quality", qualified=True)
    stages = ready(ledger)
    stages.append(timed(ledger, "bad-timing", outcome="quality_failed"))
    with pytest.raises(ValueError, match="successful referenced stable"):
        observe(ledger, "contradictory-quality", stages=stages, qualified=True)
    observe(ledger, "failed-parent", stages=stages)
    with pytest.raises(ValueError, match="protocol-qualified"):
        register(ledger, cid="mish002", source=103, basis=["failed-parent"], parent={"candidate_id": "mish001", "source_hash": h(102)})


def test_cli_status_verify_and_nonfinite_payload_rejection(ledger, capsys, tmp_path):
    assert campaign.main(["status", "--ledger", str(ledger.directory), "--split", "validation"]) == 0
    assert set(json.loads(capsys.readouterr().out)["tasks"]) == {"gelu"}
    assert campaign.main(["verify", "--ledger", str(ledger.directory)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    payload = tmp_path / "payload.json"
    payload.write_text('{"event_id":"x","reason":NaN}')
    with pytest.raises(ValueError, match="nonfinite JSON"):
        campaign.main(["resume", "--ledger", str(ledger.directory), "--payload", str(payload)])


def test_source_build_profile_caps_and_actual_costs_are_independent(ledger):
    register(ledger)
    for index in range(6):
        sid = f"build-{index}"
        start(ledger, sid, "build")
        finish(ledger, sid, outcome="build_failed")
    with pytest.raises(ValueError, match="build budget"):
        start(ledger, "build-7", "build")
    for index in range(3):
        sid = f"profile-{index}"
        start(ledger, sid, "profile", plan={"case_ids": [1], "capture_window": {"skip": 10, "count": 5}})
        ledger.finish_stage(event_id="finish-" + sid, workload="mish", stage_id=sid, outcome="failed", reason="capture failed",
                            evidence={"log_ref": h(777)}, actual_costs={"process_starts": 1, "profile_launches": 2})
    with pytest.raises(ValueError, match="profile_groups budget"):
        start(ledger, "profile-4", "profile", plan={"case_ids": [1], "capture_window": {"count": 5}})
    stages = [f"build-{i}" for i in range(6)] + [f"profile-{i}" for i in range(3)]
    observe(ledger, "source-1", stages=stages)
    for index in range(2, 7):
        register(ledger, cid=f"mish{index:03d}", source=110 + index, basis=[f"source-{index - 1}"])
        observe(ledger, f"source-{index}", cid=f"mish{index:03d}")
    with pytest.raises(ValueError, match="source budget"):
        register(ledger, cid="mish007", source=117, basis=["source-6"])
    task = ledger.status()["tasks"]["mish"]
    assert task["used"] == dict(source=6, build=6, timing_groups=0, profile_groups=3)
    assert task["actual_costs"] == dict(process_starts=3, profile_launches=6)


def test_inherited_exp_allows_only_five_additional_sources(ledger):
    observe(ledger, "exp-inherited", name="exp", cid="exp001")
    previous = "exp-inherited"
    for index in range(2, 7):
        cid = f"exp{index:03d}"
        register(ledger, name="exp", cid=cid, source=400 + index, basis=[previous])
        previous = f"exp-observation-{index}"
        observe(ledger, previous, name="exp", cid=cid)
    with pytest.raises(ValueError, match="source budget"):
        register(ledger, name="exp", cid="exp007", source=407, basis=[previous])
    assert ledger.status()["tasks"]["exp"]["remaining"]["source"] == 0


def test_checkpoint_crash_after_journal_commit_needs_idempotent_seal_recovery(ledger, monkeypatch):
    original = ledger._seal_checkpoint
    def interrupted(event):
        raise OSError("simulated power failure after journal fsync")
    monkeypatch.setattr(ledger, "_seal_checkpoint", interrupted)
    arguments = dict(event_id="cp-event", checkpoint_id="cp-id", reason="pause", next_action="resume", resources_released=True)
    with pytest.raises(OSError):
        ledger.checkpoint(**arguments)
    restored = campaign.Ledger(ledger.directory)
    assert restored.status()["unsealed_checkpoints"] == ["cp-id"]
    with pytest.raises(ValueError, match="unsealed checkpoint"):
        restored.verify()
    with pytest.raises(ValueError, match="seal the committed"):
        restored.resume(event_id="resume-cp", checkpoint_id="cp-id", reason="continue")
    monkeypatch.setattr(ledger, "_seal_checkpoint", original)
    restored.checkpoint(**arguments)
    assert restored.verify()["valid"]
    restored.resume(event_id="resume-cp", checkpoint_id="cp-id", reason="continue")
    assert restored.status()["status"] == "active"


def test_stage_dependency_and_incomplete_success_fail_closed(ledger):
    register(ledger)
    ready(ledger)
    start(ledger, "partial", "timing", plan=plan(ledger))
    with pytest.raises(ValueError, match="every planned formal sample"):
        finish(ledger, "partial", samples=1)
    finish(ledger, "partial", outcome="incomplete", samples=1)
    with pytest.raises(ValueError, match="dependency has not succeeded"):
        start(ledger, "dependent", "profile", plan={"case_ids": [1], "capture_window": {"count": 1}, "depends_on": ["partial"]})
    assert ledger.status()["tasks"]["mish"]["used"]["timing_groups"] == 1

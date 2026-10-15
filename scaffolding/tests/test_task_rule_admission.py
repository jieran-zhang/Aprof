"""Structural negatives for the Task rule envelope, using the real local reader."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))
from aprof_layout import skill_lib
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
from aprof_runtime.local_evidence import LocalEvidence
from task_rule_admission import PROTOCOL, TASK_PROTOCOL, STAGES, verify_task_attempt_roster


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def fixture(tmp_path, change=None):
    store = LocalEvidence(tmp_path / "records")
    save = store.register_json
    file = tmp_path / "stdout.log"
    file.write_text("job output\n")
    log = {"path": str(file), "sha256": store.register_artifact(file)}
    identity = dict(run_id="round3", candidate_id="exp-8192", operator="exp",
                    source_hashes={"baseline": save({"source": "baseline"}),
                                   "candidate": save({"source": "candidate"})})
    job = dict(job_id="exp-rule", argv=["python3", "controller.py"], cwd=str(tmp_path),
               output_dir=str(tmp_path / "outer"), timeout_seconds=3600)
    anchor = dict(schema_version=1, protocol=PROTOCOL, task_protocol=TASK_PROTOCOL,
                  purpose="promotion", **identity, created_at=99, job_ref=save(job),
                  budget_seconds=3600, history_refs=[save({"old_attempt": "failed"})])
    for key in ("input_inventory_ref", "boundary_plan_ref", "screen_plan_ref",
                "profile_plan_ref", "source_review_ref"):
        anchor[key] = save({"kind": key})
    protocol = {**anchor, "created_at": 101}
    registration = dict(schema_version=1, run_id=identity["run_id"],
                        candidate_id=identity["candidate_id"], created_at=102,
                        max_attempts=1, stop_on_failure=True, resampling="none", stages=list(STAGES))
    execution = dict(schema_version="1.0.0", kind="aprof_execution_report", job=job,
                     status="passed", exit_code=0, started_at=iso(100), finished_at=iso(120),
                     duration_seconds=20, stdout=log, stderr=log)
    evidence = {stage: [save({"stage": stage, "payload": "not an admission"})] for stage in STAGES}
    events = [dict(sequence=i, stage=stage, state=state, at=103 + i,
                   evidence_refs=[] if state == "started" else evidence[stage],
                   **({"exit_status": 0} if state == "completed" else {}))
              for i, (stage, state) in enumerate((s, t) for s in STAGES for t in ("started", "completed"))]
    values = dict(anchor=anchor, protocol=protocol, registration=registration,
                  execution=execution, evidence=evidence, events=events)
    if change:
        change(values)
    anchor_ref = save(values["anchor"])
    values["protocol"]["anchor_ref"] = anchor_ref
    protocol_ref = save(values["protocol"])
    values["registration"].update(anchor_ref=anchor_ref, protocol_ref=protocol_ref)
    registration_ref = save(values["registration"])
    chain, previous = [], registration_ref
    for event in values["events"]:
        event = {**event, "previous_ref": previous, "registration_ref": registration_ref}
        previous = save(event)
        chain.append(previous)
    roster_ref = save(dict(schema_version=1, registration_ref=registration_ref, events=chain))
    execution_path = tmp_path / "outer/execution.json"
    execution_path.parent.mkdir()
    execution_path.write_text(json.dumps(values["execution"]) + "\n")
    expected = {**identity, "anchor_ref": anchor_ref, "protocol_ref": protocol_ref,
                "qualification_registration_ref": registration_ref,
                "execution_ref": store.register_artifact(execution_path)}
    report = dict(schema_version=1, protocol=PROTOCOL, **expected,
                  attempt_roster_ref=roster_ref, stage_evidence=values["evidence"])
    return store, report, expected


def verify(tmp_path, change=None):
    store, report, expected = fixture(tmp_path, change)
    return verify_task_attempt_roster(store, store.register_json(report), expected=expected)


def test_valid_structure_has_no_admission_authority(tmp_path):
    result = verify(tmp_path)
    assert result["valid"] and result["admission_authority"] is False
    assert list(result["stage_windows"]) == list(STAGES)
    assert result["actual_duration_seconds"] == 20


def test_adjustable_job_budget_requires_a_frozen_parent_campaign(tmp_path):
    def extend(values):
        values["anchor"]["budget_seconds"] = 7200
        values["protocol"]["budget_seconds"] = 7200
    with pytest.raises(ValueError, match="requires a frozen parent campaign"):
        verify(tmp_path, extend)


@pytest.mark.parametrize("mutation", [
    lambda x: x["execution"].update(status="timeout", exit_code=143),
    lambda x: x["execution"].update(exit_code=1),
    lambda x: x["execution"].update(error={"type": "TimeoutError"}),
    lambda x: x["execution"].update(duration_seconds=3600.01),
    lambda x: x["execution"].update(finished_at=iso(3700.01)),
    lambda x: x["execution"].update(finished_at=iso(112)),
    lambda x: x["execution"].update(started_at="1970-01-01T00:01:40"),
    lambda x: x["execution"].update(job={**x["execution"]["job"], "timeout_seconds": 7200}),
    lambda x: x["anchor"].update(created_at=100.1),
    lambda x: x["protocol"].update(created_at=99),
    lambda x: x["protocol"].update(task_protocol="device_event_v2"),
    lambda x: x["protocol"].update(budget_seconds=7200),
    lambda x: x["protocol"].update(history_refs=[]),
    lambda x: x["registration"].update(max_attempts=2),
    lambda x: x["registration"].update(stop_on_failure=False),
    lambda x: x["registration"].update(stages=["correctness", "aa_before", "formal", "aa_after", "profile"]),
    lambda x: x["events"].pop(),
    lambda x: x["events"][3].update(exit_status=1),
    lambda x: x["events"][5].update(evidence_refs=[]),
    lambda x: x["events"][6].update(at=102),
    lambda x: x["events"][7].update(sequence=3),
    lambda x: x["events"][0].update(evidence_refs=x["evidence"]["correctness"]),
    lambda x: x["evidence"].update(aa_before=["sha256:" + "0" * 64]),
])
def test_rejects_failed_late_reordered_or_altered_attempt(tmp_path, mutation):
    with pytest.raises(ValueError):
        verify(tmp_path, mutation)


def test_rejects_changed_log_bytes(tmp_path):
    store, report, expected = fixture(tmp_path)
    (tmp_path / "stdout.log").write_text("changed bytes\n")
    with pytest.raises(Exception, match="changed"):
        verify_task_attempt_roster(store, store.register_json(report), expected=expected)


def test_rejects_untrusted_registration(tmp_path):
    store, report, expected = fixture(tmp_path)
    expected["qualification_registration_ref"] = store.register_json({"unrelated": True})
    with pytest.raises(ValueError, match="qualification_registration_ref"):
        verify_task_attempt_roster(store, store.register_json(report), expected=expected)


def test_rejects_report_substituting_success_for_dispatcher_failure(tmp_path):
    store, report, expected = fixture(tmp_path, lambda x: x["execution"].update(status="failed", exit_code=1))
    fake = json.loads(store.verify_artifact(expected["execution_ref"]).read_text())
    fake.update(status="passed", exit_code=0)
    report["execution_ref"] = store.register_json(fake)
    with pytest.raises(ValueError, match="execution_ref differs"):
        verify_task_attempt_roster(store, store.register_json(report), expected=expected)


def test_rejects_success_pointer_when_actual_dispatcher_file_is_failed(tmp_path):
    store, report, expected = fixture(tmp_path)
    fake = json.loads(store.verify_artifact(expected["execution_ref"]).read_text())
    report["execution_ref"] = expected["execution_ref"] = store.register_json(fake)
    fake.update(status="failed", exit_code=1)
    (tmp_path / "outer/execution.json").write_text(json.dumps(fake) + "\n")
    with pytest.raises(ValueError, match="external file changed"):
        verify_task_attempt_roster(store, store.register_json(report), expected=expected)

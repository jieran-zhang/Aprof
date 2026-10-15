"""Campaign accounting and narrow amendment tests; no hardware claims."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from test_teacher_wiki import MODULE
import timing_admission


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir()

    def put(self, value):
        data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
        ref = MODULE.digest(data)
        (self.root / ref[7:]).write_bytes(data)
        return ref

    def verify_artifact(self, ref):
        path = self.root / ref[7:]
        assert MODULE.digest(path.read_bytes()) == ref
        return path


def json_file(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))
    return path


def campaign_fixture(tmp_path, monkeypatch):
    kinds = ["legacy-diagnostic", "v2-diagnostic", "v2-confirmation", "candidate-qualification"]
    operators = ["sigmoid", "exp"]
    stores, manifest_refs, attempts = {}, {}, {}
    anchor_path = tmp_path / "repo/scaffolding/curation/graph-base-1.0.0-round2-plan.json"
    round_plan = json_file(tmp_path / "campaign/round-plan.json", {
        "operators": operators, "attempt_order": kinds, "max_attempts_per_kind": 1})
    old_driver = b"# synthetic driver, never executed\nresult = report['speedup']>=1.0\n"
    new_driver = tmp_path / "campaign/round2-screen-fix.py"
    new_driver.write_bytes(old_driver.replace(b"report['speedup']>=1.0",
        b"math.exp(statistics.fmean(math.log(r['speedup']) for r in report['per_case']))>=1.0"))
    old_path = tmp_path / "campaign/round2.py"
    old_path.write_bytes(old_driver)
    selected = None
    for operator_index, operator in enumerate(operators):
        root = tmp_path / "campaign" / operator
        root.mkdir()
        archive = stores[root / "evidence.sqlite"] = Store(root / "cas")
        driver_ref = archive.put(old_driver)
        archive.put(new_driver.read_bytes())
        source_hashes = {role: archive.put({"source": role, "operator": operator}) for role in ("baseline", "candidate")}
        binary_hashes = {role: archive.put(("binary " + role + operator).encode()) for role in ("baseline", "candidate")}
        manifest = {"schema_version": 1, "operator": operator, "round_plan_ref": MODULE.digest(round_plan.read_bytes()),
                    "driver_ref": driver_ref, "attempts": {}, "source_hashes": source_hashes, "binary_hashes": binary_hashes}
        entries = attempts[operator] = {}
        for kind_index, kind in enumerate(kinds):
            candidate = kind == "candidate-qualification"
            protocol = {"schema_version": 1, "operator": operator, "run_id": operator + kind,
                "candidate_id": operator + "-candidate-" + kind, "created_at": 1,
                "purpose": "promotion" if candidate else "baseline_qualification" if kind == "v2-confirmation" else "protocol_diagnostic",
                "source_hashes": {role: source_hashes[role if candidate else "baseline"] for role in ("baseline", "candidate")},
                "binary_hashes": {role: binary_hashes[role if candidate else "baseline"] for role in ("baseline", "candidate")},
                "round_plan_ref": manifest["round_plan_ref"], "driver_ref": driver_ref,
                "history_refs": [archive.put({"prior_failed_qualification": operator})], "phases": {}}
            protocol_ref = archive.put(protocol)
            registration = {"schema_version": 1, "protocol_ref": protocol_ref, "run_id": protocol["run_id"],
                "candidate_id": protocol["candidate_id"], "created_at": 2, "max_attempts": 1,
                "stop_on_failure": True, "resampling": "none", "stages": ["correctness"]}
            registration_ref = archive.put(registration)
            if operator == "sigmoid" and candidate:
                selected = registration_ref
            manifest["attempts"][kind] = {"protocol_ref": protocol_ref, "registration_ref": registration_ref}
            status = "failed" if kind == "legacy-diagnostic" or operator == "exp" and kind == "v2-diagnostic" else "passed"
            if operator == "exp" and kind_index >= 2:
                status = "not_run"
            start = 200 + operator_index * 1000 + kind_index * 10
            events, prior = [], registration_ref
            if status != "not_run":
                for index, state in enumerate(("started", "completed")):
                    event = {"sequence": index, "previous_ref": prior, "registration_ref": registration_ref,
                        "stage": "correctness", "state": state, "at": start + .1 + index / 10,
                        "evidence_refs": [archive.put({"test_only_execution": operator, "kind": kind})] if index else []}
                    if index:
                        event["exit_status"] = 0 if status == "passed" else 1
                    prior = archive.put(event)
                    events.append(prior)
            roster = {"schema_version": 1, "registration_ref": registration_ref, "events": events}
            roster_ref = archive.put(roster)
            closure = {"schema_version": 1, "operator": operator, "kind": kind, "status": status,
                "protocol_ref": protocol_ref, "registration_ref": registration_ref, "attempt_roster_ref": roster_ref,
                "finished_at": start + 1, "resampling": "none", "collected": {}}
            item = {}
            if status == "not_run":
                closure["prerequisite_ref"] = entries[kinds[kind_index - 1]]["closure_ref"]
            else:
                iso = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
                execution = {"job": {"argv": ["/python", str(new_driver if candidate else old_path), "execute", operator, kind]},
                    "started_at": iso(start), "finished_at": iso(start + 2), "status": "passed" if status == "passed" else "failed",
                    "exit_code": 0 if status == "passed" else 1,
                    "stdout": {"path": str(root / kind / "job/stdout.log"), "sha256": archive.put(b"test stdout")},
                    "stderr": {"path": str(root / kind / "job/stderr.log"), "sha256": archive.put(b"test stderr")}}
                item["execution_ref"] = archive.put(execution)
            if status == "passed":
                item["control_report_ref"] = archive.put({"protocol_ref": protocol_ref, "attempt_roster_ref": roster_ref,
                    "test_only_control_wiring": True})
            item["closure_ref"] = archive.put(closure)
            entries[kind] = item
        manifest_path = json_file(root / "frozen-round.json", manifest)
        manifest_refs[operator] = MODULE.source(manifest_path, tmp_path)
    anchor = {"schema_version": 1, "operators": operators, "attempt_order": kinds, "max_attempts_per_kind": 1,
        "round_plan": MODULE.source(round_plan, tmp_path), "attempt_manifests": manifest_refs, "inventory_anchored_at": 100}
    json_file(anchor_path, anchor)
    formula = json_file(tmp_path / "formula.json", {"legacy": "formula provenance"})
    patch = json_file(tmp_path / "patch.json", {"test": "byte-diff is independently checked"})
    amendment = {"schema_version": 1, "kind": "explore_screen_aggregate_api_fix",
        "campaign_anchor_ref": MODULE.digest(anchor_path.read_bytes()), "registered_at": 150,
        "old_driver_ref": MODULE.digest(old_driver), "new_driver": MODULE.source(new_driver, tmp_path),
        "applies_to": ["candidate-qualification"], "formula_source": MODULE.source(formula, tmp_path), "diff": MODULE.source(patch, tmp_path)}
    amendment_path = anchor_path.with_name("graph-base-1.0.0-round2-amendment-screen.json")
    json_file(amendment_path, amendment)
    report = {"schema_version": 1, "anchor_ref": MODULE.digest(anchor_path.read_bytes()),
              "amendment_ref": MODULE.digest(amendment_path.read_bytes()), "attempts": attempts}

    @contextmanager
    def archives(path):
        yield stores[path]

    monkeypatch.setattr(MODULE, "campaign_store", archives)
    # The shared admission tests cover raw replay; this fixture isolates campaign
    # accounting and its call to that verifier, not a forged hardware proof.
    def control_replay(store, ref, *, expected):
        assert json.loads(store.verify_artifact(ref).read_text())["test_only_control_wiring"] is True
        assert expected["registration_ref"]
        return {"passed": True}
    monkeypatch.setattr(timing_admission, "verify_timing_admission", control_replay)
    return stores, report, anchor_path, amendment_path, selected


def test_campaign_keeps_failures_and_predeclared_blocked_attempts(tmp_path, monkeypatch):
    stores, report, anchor, _, selected = campaign_fixture(tmp_path, monkeypatch)
    store = next(iter(stores.values()))
    assert MODULE.verify_campaign(store, store.put(report), anchor_path=anchor, workspace=tmp_path,
                                  selected_registration_ref=selected)["attempts"] == 8


@pytest.mark.parametrize("fault", ["omitted_attempt", "unregistered_run", "late_amendment", "broad_driver_edit",
                                   "missing_control", "wrong_prerequisite", "executed_not_run", "old_candidate_driver"])
def test_campaign_rejects_selection_and_amendment_bypasses(tmp_path, monkeypatch, fault):
    stores, report, anchor, amendment_path, selected = campaign_fixture(tmp_path, monkeypatch)
    store = next(iter(stores.values()))
    if fault == "omitted_attempt":
        del report["attempts"]["sigmoid"]["legacy-diagnostic"]
    elif fault == "unregistered_run":
        selected = store.put({"an_unregistered_replacement": True})
    elif fault in {"late_amendment", "broad_driver_edit"}:
        amendment = json.loads(amendment_path.read_text())
        if fault == "late_amendment":
            amendment["registered_at"] = 10000
        else:
            path = tmp_path / amendment["new_driver"]["path"]
            path.write_bytes(path.read_bytes() + b"# unapproved source edit\n")
            amendment["new_driver"] = MODULE.source(path, tmp_path)
        json_file(amendment_path, amendment)
        report["amendment_ref"] = MODULE.digest(amendment_path.read_bytes())
    elif fault == "missing_control":
        del report["attempts"]["sigmoid"]["v2-confirmation"]["control_report_ref"]
    elif fault == "old_candidate_driver":
        item = report["attempts"]["sigmoid"]["candidate-qualification"]
        execution = json.loads(store.verify_artifact(item["execution_ref"]).read_text())
        execution["job"]["argv"][1] = str(tmp_path / "campaign/round2.py")
        item["execution_ref"] = store.put(execution)
    else:
        archive = stores[tmp_path / "campaign/exp/evidence.sqlite"]
        item = report["attempts"]["exp"]["v2-confirmation"]
        closure = json.loads(archive.verify_artifact(item["closure_ref"]).read_text())
        if fault == "wrong_prerequisite":
            closure["prerequisite_ref"] = report["attempts"]["exp"]["legacy-diagnostic"]["closure_ref"]
        else:
            item["execution_ref"] = report["attempts"]["exp"]["v2-diagnostic"]["execution_ref"]
        item["closure_ref"] = archive.put(closure)
    with pytest.raises((ValueError, KeyError)):
        MODULE.verify_campaign(store, store.put(report), anchor_path=anchor, workspace=tmp_path,
                               selected_registration_ref=selected)

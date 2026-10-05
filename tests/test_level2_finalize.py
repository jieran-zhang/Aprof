"""Real append-only ledger and source snapshots; all native work is synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import level2_finalize as final
import msprof_exploration_campaign as campaign
import msprof_raw_storage as raw_storage
from msprof_exploration_execute import load, save, sha, pointer
from prepare_trace_pilot import create_source_snapshot


def rewrite(path, value):
    path.write_text(json.dumps(value))


class Fixture:
    def __init__(self, run, monkeypatch, *, failed=(), count=3, blocked=(), error_type="RuntimeError", parent_chain=False,
                 omit_classification=False):
        self.run, self.task = run, run / "train/tasks/maximum"
        self.ids, self.calls, self.actual_reports = [], [], {}
        save(self.task / "manifest.json", {"version": "msprof_task_time_exploration_v2"})
        self.make_source(self.task, "baseline", "baseline-source.tar", "original")
        self.ledger = campaign.create_fresh(run / "train/ledger", campaign_id="fixture", workloads={"maximum": {
            "baseline_source_hash": sha(self.task / "baseline-source.tar"), "source_split": "train",
            "repeat_by_case": {str(c): 1 if c == 20 else 10 for c in campaign.ALL_CASES}, "pilot_ref": "sha256:" + "a" * 64}})
        self.baseline = self.ledger.config["tasks"]["maximum"]["baseline_source_hash"]
        script = self.task / "agent/boundary_guard.py";script.parent.mkdir();script.write_text("# fixture guard\n")
        for kind in ("build", "correctness", "runtime"):
            self.complete("baseline", kind, kind)
        save(self.task / "stages/aa-initial/cohort/report.json", {"baseline_calibration": True})
        comparisons = {}
        basis = []
        for i in range(1, count + 1):
            cid = f"maximum{i:03}";self.ids.append(cid)
            parent = self.task / "candidates" / cid
            self.make_source(parent, "op", "source.tar", cid)
            source_parent = ({"candidate_id": self.ids[-2], "source_hash": sha(self.task / "candidates" / self.ids[-2] / "source.tar")}
                             if parent_chain and i > 1 else {"candidate_id": None, "source_hash": self.baseline})
            self.ledger.register(event_id=cid + "-register", workload="maximum", candidate_id=cid,
                source_hash=sha(parent / "source.tar"), patch_hash="sha256:" + f"{i:064x}",
                source_parent=source_parent, decision_basis=basis)
            refs, stages = {}, []
            for kind in (("build",) if i in failed else ("build", "correctness", "runtime")):
                value = self.complete(cid, kind, kind, failed=(i in failed), error_type=error_type)
                path = parent / "stages" / kind / "result.json"
                stages.append({k: value[k] for k in ("stage_id", "kind", "status", "error")} | {"result": pointer(path)})
                refs[value["stage_id"]] = value
            guard_ref = None
            if i not in failed:
                self.guard(cid)
                guard_ref = pointer(parent / "boundary-validation/completion.json")
                search = self.ledger.timing_plan("maximum", cid, purpose="search", manifest_ref="sha256:" + "b" * 64,
                                                final_candidate_ids=list(self.ids))
                save(parent / "plans/search/stage-plan.json", {**search, "cohorts": []})
                value = self.complete(cid, "timing", "search", plan=search)
                stages.append({k: value[k] for k in ("stage_id", "kind", "status", "error")} |
                              {"result": pointer(parent / "stages/search/result.json")})
                refs[value["stage_id"]] = value
            comparisons[cid] = [{"speedup": 0.5, "limitations": ["unfavorable performance is still eligible"]}] if i not in failed else []
            feedback = {"operator": "maximum", "candidate_id": cid, "source_hash": sha(parent / "source.tar"),
                "source_parent": source_parent, "status": "infrastructure_blocked" if i in blocked else
                "source_attempt_failed" if i in failed else "measured", "measurement_error": None,
                "stages": stages, "semantic_guards": guard_ref, "comparisons": comparisons[cid]}
            if i in failed and not omit_classification:
                feedback['failure_classification'] = final.failure_classification.classify_failure(
                    self.task,parent,stage=value)
            path = self.task / "feedback" / (cid + ".json");save(path, feedback)
            oid = cid + "-feedback"
            self.ledger.observe(event_id=oid, workload="maximum", candidate_id=cid, observation_id=oid,
                stage_ids=list(refs), feedback=feedback, close_feedback=True, report_ref=sha(path),
                quality={"infrastructure_blocked": i in blocked})
            basis = [oid]
        monkeypatch.setattr(final.iteration, "comparison_reports", lambda task, parent, op, item, baseline, **kw: comparisons[item["candidate_id"]])
        monkeypatch.setattr(final, "preflight_cohort", lambda plan: None)
        monkeypatch.setattr(final.stage_module, "prepare_timing", self.prepare)
        monkeypatch.setattr(final.iteration, "run_stage", self.execute)
        monkeypatch.setattr(final.report, "analyze_task_cohort", self.replay)

    def make_source(self, parent, folder, tar, content):
        source = parent / folder
        for sub in ("op_host", "op_kernel"):
            directory = source / sub;directory.mkdir(parents=True)
            (directory / "maximum.asc").write_text(content + sub)
        create_source_snapshot(source, parent / tar, root_label="maximum")

    def complete(self, cid, kind, group, *, failed=False, error_type="RuntimeError", plan=None):
        self.ledger = campaign.Campaign(self.run / "train/ledger")
        candidate_id = None if cid == "baseline" else cid
        parent = self.task if candidate_id is None else self.task / "candidates" / cid
        source = self.baseline if candidate_id is None else sha(parent / "source.tar")
        sid = cid + "-" + group
        plan = deepcopy(plan) if plan is not None else {"case_ids": campaign.ALL_CASES, "source_hash": source}
        if kind == "runtime":
            plan.update(final.stage_module.successful_correctness_binding(self.ledger, "maximum", candidate_id, parent, source))
        directory = parent / "stages" / group
        save(directory / "stage-plan.json", plan)
        self.ledger.start(event_id=sid + "-start", workload="maximum", candidate_id=candidate_id,
                          stage_id=sid, kind=kind, plan=plan)
        value = {"stage_id": sid, "candidate_id": candidate_id, "kind": kind,
                 "status": "failed" if failed else "passed", "native_started": kind != "build",
                 "error": {"type": error_type, "message": "process failed (2): cmake"} if failed else None}
        save(directory / "result.json", value)
        if failed and kind=='build':
            from test_level2_failure_classification import execution
            build=parent/'build'
            save(build/'configure-execution/execution.json',execution(['cmake','-S',build,'-B',build/'build']))
            save(build/'build-execution/execution.json',execution(['cmake','--build',build/'build','-j2'],2,value['error']['message']))
            (build/'build-execution/stdout.log').write_text('')
            (build/'build-execution/stderr.log').write_text(
                f"{parent/'op/op_kernel/maximum.asc'}:1:1: error: use of undeclared identifier 'bad_api'\n")
        evidence = {"result": pointer(directory / "result.json")}
        if kind == "correctness":evidence["prepared_output_checked"] = not failed
        if kind == "runtime":
            correctness = Path(plan["correctness_directory"])
            save(correctness / "completion.json", {"status": "passed", "completed": [{"case_id": c} for c in campaign.ALL_CASES]})
            natives = []
            for case in campaign.ALL_CASES:
                path = correctness / f"case_{case:02d}/native.json"
                save(path, {"exit_code": 0, "stream_destroyed": True, "context_destroyed": True, "finalized": True})
                natives.append(pointer(path))
            path = correctness.parent / "standalone/completion.json";save(path, {"status": "passed", "passed_count": 20})
            save(directory / "runtime.json", {"status": "passed", "native_results": [*natives, pointer(path)],
                 "correctness": pointer(correctness / "completion.json"), "correctness_stage_result": plan["correctness_result"]})
            evidence["runtime"] = pointer(directory / "runtime.json")
        samples = campaign.expected_samples(plan) if kind == "timing" and not failed else 0
        self.ledger.finish(event_id=sid + "-finish", workload="maximum", stage_id=sid,
            outcome="build_failed" if failed and kind == "build" else "failed" if failed else "success",
            evidence=evidence, native_started=kind != "build", formal_samples=samples,
            reason="actual recorded failure" if failed else None)
        return value

    def guard(self, cid):
        parent = self.task / "candidates" / cid
        binary = parent / "build/standalone";binary.parent.mkdir();binary.write_bytes(b"fixture binary")
        save(parent / "build/build_manifest.json", {"standalone": pointer(binary)})
        save(parent / "dispatch_plan.json", {"source": cid})
        directory = parent / "boundary-validation"
        save(directory / "request.json", {"operator": "maximum", "candidate": cid,
             "script": pointer(self.task / "agent/boundary_guard.py"), "binary": pointer(binary),
             "dispatch_plan": pointer(parent / "dispatch_plan.json")})
        save(directory / "completion.json", {"operator": "maximum", "candidate": cid,
             "request": pointer(directory / "request.json"), "status": "passed", "error": None,
             "verification_error": None, "cases": [{"expected_process_passed": True, "dispatch_log_passed": True, "error": None}]})

    def prepare(self, run, operator, cid, group, **kwargs):
        assert kwargs["purpose"] == "final"
        self.calls.append(("prepare", cid))
        self.ledger = campaign.Campaign(self.run / "train/ledger")
        item = self.ledger.state["tasks"]["maximum"]["candidates"][cid]
        parent = self.task / "candidates" / cid
        directory = parent / "plans" / group
        controls = [("direct_parent", item["source_parent"]["candidate_id"] or "baseline")]
        if item["source_parent"]["source_hash"] != self.baseline:controls.append(("original_baseline", "baseline"))
        cohorts = []
        for relation, control in controls:
            build = directory / (relation + "-roles.json")
            control_source = self.task / "baseline" if control == "baseline" else self.task / "candidates" / control / "op"
            save(build, {"operator": "maximum", "roles": {"A": {"source_sha256": final.source_hash(control_source)},
                                                           "B": {"source_sha256": final.source_hash(parent / "op")}}})
            cohort_path = directory / (relation + "-cohort.json")
            storage=kwargs.get('capture_storage')
            storage_ref=pointer(raw_storage.__file__) if storage==raw_storage.LOCAL else None
            request={'version':'msprof_kernel_time_study_v2',
                     **({'capture_storage':storage} if storage is not None else {}),
                     **({'capture_storage_producer':storage_ref} if storage_ref else {})}
            scope={"epoch": kwargs.get("epoch", "epoch-01"),
                   **({'capture_storage':storage} if storage is not None else {}),
                   **({'capture_storage_producer_hash':storage_ref['sha256']} if storage_ref else {})}
            save(cohort_path, {"case_ids": campaign.ALL_CASES, "comparison_kind": "ab",
                 "protocol":final.report.PROTOCOL_V2,"analysis_version":final.report.ANALYSIS_V2,
                 "identity_bindings": {"role_build": pointer(build)},
                 "calibration_scope": scope,
                 "schedule": [{"name": f"p{i}", "request": request} for i in range(6)]})
            cohorts.append({"relation": relation, "control_candidate_id": control, "plan": pointer(cohort_path)})
            if relation in kwargs.get("calibration_by_relation", {}):
                cohorts[-1]["calibration_report"] = pointer(kwargs["calibration_by_relation"][relation])
        manifest = directory / "comparisons.json"
        save(manifest, {"candidate_id": cid, "cohorts": cohorts, "case_ids": campaign.ALL_CASES})
        plan = self.ledger.timing_plan("maximum", cid, purpose="final", manifest_ref=sha(manifest), cohorts=cohorts)
        plan["calibration_report"] = pointer(kwargs["calibration_path"])
        path = directory / "stage-plan.json";save(path, plan)
        return path

    def execute(self, run, operator, cid, kind, group, **kwargs):
        assert kind == "timing" and group == "final"
        self.calls.append(("execute", cid))
        assert campaign.Campaign(self.run / "train/ledger").state["tasks"]["maximum"]["frozen"]
        plan = load(kwargs["plan_path"])
        value = self.complete(cid, kind, group, plan=plan)
        for cohort in plan["cohorts"]:
            directory = self.task / "candidates" / cid / "stages/final" / cohort["relation"]
            frozen = load(cohort["plan"]["path"])
            save(directory / "plan.json", frozen)
            paths = [str(directory / r["name"]) for r in frozen["schedule"]]
            save(directory / "group-completion.json", {"status": "passed", "error": None, "completed_sessions": paths})
            actual = {"case_ids": [str(c) for c in campaign.ALL_CASES], "evidence_status": "verified_complete",
                      "speedup": 0.5, "limitations": ["descriptive, not admitted"]}
            self.actual_reports[paths[0]] = deepcopy(actual)
            save(directory / "report.json", actual)
        return value

    def replay(self, directories, plan, calibration):
        assert len(directories) == 6 and plan["case_ids"] == campaign.ALL_CASES
        return deepcopy(self.actual_reports[directories[0]])


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    return Fixture(tmp_path, monkeypatch)


def test_all_qualified_even_slow_candidates_freeze_full20_and_resume_without_calls(fixture):
    f = fixture
    prepared = final.finalize(f.run, "maximum", prepare_only=True)
    assert prepared["status"] == "prepared", prepared
    assert prepared["evaluation_candidate_ids"] == f.ids and prepared["selected_candidate_id"] is None
    assert not any(c[0] == "execute" for c in f.calls)
    state = campaign.Campaign(f.run / "train/ledger").state["tasks"]["maximum"]
    assert state["frozen"] and state["used"]["timing_groups"] == 3
    assert all(p["case_ids"] == campaign.ALL_CASES for p in state["final_plans"].values())
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "final_evaluations_completed", result
    assert [c for c in f.calls if c[0] == "execute"] == [("execute", cid) for cid in f.ids]
    head = campaign.Campaign(f.run / "train/ledger").events[-1]["hash"]
    calls = list(f.calls)
    assert final.finalize(f.run, "maximum") == result
    assert f.calls == calls and campaign.Campaign(f.run / "train/ledger").events[-1]["hash"] == head
    assert result["formal_admission"] == "not_evaluated" and result["episode_ref"] is None


def test_three_failed_sources_close_without_fake_candidate_or_success(tmp_path, monkeypatch):
    f = Fixture(tmp_path, monkeypatch, failed=(1, 2, 3))
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "closed_no_qualified_candidates", result
    assert result["evaluation_candidate_ids"] == [] and result["selected_candidate_id"] is None and not f.calls
    assert campaign.Campaign(f.run / "train/ledger").state["tasks"]["maximum"]["frozen"]
    assert final.finalize(f.run, "maximum") == result
    assert final.main(["--run", str(f.run), "--operator", "maximum"]) == 2


@pytest.mark.parametrize("fault", ["two_rounds", "infrastructure_feedback", "build_timeout"])
def test_unfinished_never_freezes_or_prepares(tmp_path, monkeypatch, fault):
    options = {"count": 2} if fault == "two_rounds" else {"blocked": (3,)} if fault == "infrastructure_feedback" else {"failed": (3,), "error_type": "TimeoutExpired"}
    f = Fixture(tmp_path, monkeypatch, **options)
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished"
    assert not f.calls and not (f.task / "finalization").exists()
    assert not campaign.Campaign(f.run / "train/ledger").state["tasks"]["maximum"]["frozen"]


@pytest.mark.parametrize("fault", ["feedback", "source", "stage_result", "guard", "missing_guard", "source_members"])
def test_evidence_tampering_blocks_before_freeze(fixture, fault):
    f = fixture;parent = f.task / "candidates/maximum002"
    if fault == "feedback":rewrite(f.task / "feedback/maximum002.json", {})
    elif fault == "source":(parent / "source.tar").write_bytes(b"tampered")
    elif fault == "stage_result":rewrite(parent / "stages/correctness/result.json", {"status": "passed"})
    elif fault == "guard":rewrite(parent / "boundary-validation/completion.json", {"status": "passed"})
    elif fault == "missing_guard":(parent / "boundary-validation/completion.json").unlink()
    else:(parent / "op/op_kernel/maximum.asc").write_text("new source not measured")
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert not f.calls


def test_budget_exhaustion_cannot_drop_qualified_candidates(fixture):
    f = fixture
    # Fault injection at the read boundary: even inconsistent prior budget
    # pressure must not make the coordinator prune the evaluation roster.
    original = final.campaign.Campaign
    def loaded(path):
        value = original(path);value.state["tasks"]["maximum"]["used"]["timing_groups"] = 4
        return value
    from unittest.mock import patch
    with patch.object(final.campaign, "Campaign", loaded):
        result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished" and "budget" in result["error"]["message"]
    assert not f.calls


@pytest.mark.parametrize("fault", ["request", "plan", "cohort", "calibration", "completion", "report"])
def test_frozen_resume_rejects_changed_plan_or_result(fixture, fault):
    f = fixture
    assert final.finalize(f.run, "maximum", prepare_only=fault not in ("completion", "report"))["status"] != "unfinished"
    parent = f.task / "candidates/maximum001"
    paths = {"request": f.task / "finalization/request.json", "plan": parent / "plans/final/stage-plan.json",
             "cohort": parent / "plans/final/direct_parent-cohort.json", "calibration": f.task / "stages/aa-initial/cohort/report.json",
             "completion": f.task / "finalization/completion.json", "report": parent / "stages/final/direct_parent/report.json"}
    rewrite(paths[fault], {})
    calls = list(f.calls)
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert f.calls == calls


def test_partial_planning_never_overwrites_or_restarts(fixture):
    f = fixture
    path = f.task / "candidates/maximum001/plans/final/partial.json";save(path, {"partial": True})
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert load(path) == {"partial": True} and not f.calls


def test_plan_scope_validation_rejects_missing_twentieth_case(fixture, monkeypatch):
    f = fixture;prepare = f.prepare
    def narrow(*args, **kwargs):
        path = prepare(*args, **kwargs);plan = load(path);plan["case_ids"] = list(range(1, 20));rewrite(path, plan)
        return path
    monkeypatch.setattr(final.stage_module, "prepare_timing", narrow)
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished" and "frozen cases" in result["error"]["message"]
    assert not any(c[0] == "execute" for c in f.calls)


def test_parent_and_original_are_both_frozen_for_later_sources(tmp_path, monkeypatch):
    f = Fixture(tmp_path, monkeypatch, parent_chain=True)
    result = final.finalize(f.run, "maximum", prepare_only=True)
    assert result["status"] == "prepared", result
    plan = load(f.task / "candidates/maximum003/plans/final/stage-plan.json")
    assert [(r["relation"], r["control_candidate_id"]) for r in plan["cohorts"]] == [
        ("direct_parent", "maximum002"), ("original_baseline", "baseline")]


def test_final_failure_is_retained_not_retried_or_marked_complete(fixture, monkeypatch):
    f = fixture
    def fail(run, operator, cid, kind, group, **kwargs):
        f.calls.append(("failed_execution", cid))
        return f.complete(cid, kind, group, failed=True, plan=load(kwargs["plan_path"]))
    monkeypatch.setattr(final.iteration, "run_stage", fail)
    first = final.finalize(f.run, "maximum")
    assert first["status"] == "unfinished" and "retained without retry" in first["error"]["message"]
    calls = list(f.calls)
    assert final.finalize(f.run, "maximum")["status"] == "unfinished" and f.calls == calls
    assert not (f.task / "finalization/completion.json").exists()
    assert campaign.Campaign(f.run / "train/ledger").state["tasks"]["maximum"]["used"]["timing_groups"] == 4


def test_missing_actual_final_report_never_completes(fixture, monkeypatch):
    f = fixture;execute = f.execute
    def omit(*args, **kwargs):
        value = execute(*args, **kwargs)
        (f.task / "candidates" / args[2] / "stages/final/direct_parent/report.json").unlink()
        return value
    monkeypatch.setattr(final.iteration, "run_stage", omit)
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert not (f.task / "finalization/completion.json").exists()


@pytest.mark.parametrize("path", ["stages/runtime/runtime.json", "stages/correctness/evidence/completion.json",
                                  "stages/correctness/evidence/case_20/native.json", "stages/correctness/standalone/completion.json"])
def test_passed_stage_summary_cannot_hide_changed_native_safety_evidence(fixture, path):
    f = fixture
    rewrite(f.task / "candidates/maximum002" / path, {"status": "passed"})
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished" and not f.calls


def test_new_epoch_storage_calibration_are_frozen_and_inherited_on_resume(fixture):
    f = fixture
    scope={'epoch':'local-raw-01','capture_storage':dict(raw_storage.LOCAL),'capture_storage_producer_hash':sha(raw_storage.__file__)}
    calibration={'protocol':final.report.PROTOCOL_V2,'analysis_version':final.report.ANALYSIS_V2,
        'comparison_kind':'aa','evidence_status':'verified_complete','formal_admission':'not_evaluated',
        'calibration_scope':scope,'environment_binding':{'capture_storage':dict(raw_storage.LOCAL),'capture_storage_producer_hash':sha(raw_storage.__file__)}}
    aa = f.task / "local-aa.json";save(aa, calibration)
    parent_aa = f.task / "parent-aa.json";save(parent_aa, calibration)
    options = {"epoch": "local-raw-01", "capture_storage": dict(raw_storage.LOCAL),
               "calibration_path": aa, "calibration_by_relation": {"direct_parent": parent_aa}}
    prepared = final.finalize(f.run, "maximum", prepare_only=True, timing_options=options)
    assert prepared["status"] == "prepared", prepared
    req = load(prepared["request"]["path"])
    assert req["timing_options"]["epoch"] == "local-raw-01"
    assert req["timing_options"]["calibration_report"] == pointer(aa)
    plan = load(f.task / "candidates/maximum001/plans/final/stage-plan.json")
    assert plan["cohorts"][0]["calibration_report"] == pointer(parent_aa)
    frozen = load(plan["cohorts"][0]["plan"]["path"])
    assert frozen["schedule"][0]["request"]["capture_storage"] == options["capture_storage"]
    assert final.finalize(f.run, "maximum")["status"] == "final_evaluations_completed"
    calls = list(f.calls)
    assert final.finalize(f.run, "maximum", timing_options={**options, "epoch": "different"})["status"] == "unfinished"
    assert f.calls == calls


def test_resume_after_request_written_before_ledger_freeze(fixture, monkeypatch):
    f = fixture;freeze = campaign.Campaign.freeze
    def interrupted(*args, **kwargs):raise OSError("interrupted before ledger commit")
    monkeypatch.setattr(campaign.Campaign, "freeze", interrupted)
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert (f.task / "finalization/request.json").is_file()
    assert not campaign.Campaign(f.run / "train/ledger").state["tasks"]["maximum"]["frozen"]
    monkeypatch.setattr(campaign.Campaign, "freeze", freeze)
    assert final.finalize(f.run, "maximum")["status"] == "final_evaluations_completed"
    assert [c for c in f.calls if c[0] == "prepare"] == [("prepare", cid) for cid in f.ids]


def test_resume_between_final_candidates_never_reexecutes_completed_one(fixture, monkeypatch):
    f = fixture;execute = f.execute
    def interrupted(run, operator, cid, *args, **kwargs):
        if cid == "maximum002":raise OSError("interruption before next stage")
        return execute(run, operator, cid, *args, **kwargs)
    monkeypatch.setattr(final.iteration, "run_stage", interrupted)
    assert final.finalize(f.run, "maximum")["status"] == "unfinished"
    assert (f.task / "candidates/maximum001/stages/final/result.json").is_file()
    monkeypatch.setattr(final.iteration, "run_stage", execute)
    assert final.finalize(f.run, "maximum")["status"] == "final_evaluations_completed"
    assert [c for c in f.calls if c[0] == "execute"] == [("execute", cid) for cid in f.ids]


def test_final_stage_result_tampering_rejected_by_ledger_resume(fixture):
    f = fixture
    assert final.finalize(f.run, "maximum")["status"] == "final_evaluations_completed"
    path = f.task / "candidates/maximum001/stages/final/result.json"
    value = load(path);value["error"] = {"type": "modified"};rewrite(path, value)
    calls = list(f.calls)
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished" and "result differs" in result["error"]["message"]
    assert f.calls == calls


def test_changed_cohort_scope_cannot_hide_inside_full20_stage_plan(fixture):
    f = fixture
    assert final.finalize(f.run, "maximum", prepare_only=True)["status"] == "prepared"
    parent = f.task / "candidates/maximum001/plans/final"
    cohort = load(parent / "direct_parent-cohort.json");cohort["case_ids"] = [1, 8, 14, 20]
    rewrite(parent / "direct_parent-cohort.json", cohort)
    plan = load(parent / "stage-plan.json");plan["cohorts"][0]["plan"] = pointer(parent / "direct_parent-cohort.json")
    manifest = load(parent / "comparisons.json");manifest["cohorts"] = plan["cohorts"];rewrite(parent / "comparisons.json", manifest)
    plan["manifest_ref"] = sha(parent / "comparisons.json");rewrite(parent / "stage-plan.json", plan)
    result = final.finalize(f.run, "maximum")
    assert result["status"] == "unfinished" and "cohort coverage" in result["error"]["message"]
    assert not any(c[0] == "execute" for c in f.calls)


def test_source_failures_without_positive_classification_stay_unfinished(tmp_path,monkeypatch):
    f=Fixture(tmp_path,monkeypatch,failed=(1,2,3),omit_classification=True)
    result=final.finalize(f.run,'maximum')
    assert result['status']=='unfinished' and 'positive classification' in result['error']['message']
    assert not f.calls


@pytest.mark.parametrize('text', ["fatal error: 'kernel_operator.h' file not found\n", ''])
def test_classification_replay_rejects_changed_proof_even_same_positive_rule(tmp_path,monkeypatch,text):
    f=Fixture(tmp_path,monkeypatch,failed=(1,2,3))
    log=f.task/'candidates/maximum002/build/build-execution/stderr.log'
    # Both a new infrastructure diagnostic and a changed-but-still-semantic
    # witness differ from the complete classification frozen in feedback.
    log.write_text(log.read_text().replace('bad_api','another_bad_api')+text)
    result=final.finalize(f.run,'maximum')
    assert result['status']=='unfinished' and 'positive classification' in result['error']['message']
    assert not f.calls


def test_feedback_is_resolved_by_observation_hash_not_legacy_filename(fixture):
    f=fixture
    for cid in f.ids:
        path=f.task/'feedback'/f'{cid}.json'
        path.rename(path.with_name(cid+'-immutable-observation-02.json'))
    result=final.finalize(f.run,'maximum',prepare_only=True)
    assert result['status']=='prepared',result
    assert all('immutable-observation-02' in row['feedback']['path']
               for row in load(result['request']['path'])['source_attempts'])
    assert pointer(final.failure_classification.__file__) in load(result['request']['path'])['producers']


@pytest.mark.parametrize('options', [
    {'epoch':'../unsafe'}, {'capture_storage':{'mode':'unreviewed'},'epoch':'new'},
    {'capture_storage':dict(raw_storage.LOCAL)},
])
def test_unreviewed_timing_options_fail_before_any_final_plan(fixture,options):
    f=fixture;result=final.finalize(f.run,'maximum',prepare_only=True,timing_options=options)
    assert result['status']=='unfinished' and not f.calls


def test_prepare_only_rejects_old_direct_aa_for_new_local_epoch(fixture):
    f=fixture
    result=final.finalize(f.run,'maximum',prepare_only=True,timing_options={
        'capture_storage':dict(raw_storage.LOCAL),'epoch':'local-raw-01'})
    assert result['status']=='unfinished' and 'fresh A/A' in result['error']['message']
    assert not campaign.Campaign(f.run/'train/ledger').state['tasks']['maximum']['frozen']
    assert not any(row[0]=='execute' for row in f.calls)

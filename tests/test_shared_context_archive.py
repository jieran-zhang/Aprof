"""Archive integration uses real v2 stores and synthetic CPU-only evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import shared_context_archive as archive
import shared_context_campaign as campaign
import trace_v2_dataset as v2


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(v2.canonical(value))
    return path


def blob(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return path


def fixture(tmp_path):
    run = tmp_path / "new-run"
    old_task = tmp_path / "old-run" / "tasks" / "exp"
    baselines = {}
    for operator in campaign.WORKLOADS:
        path = blob(run / "tasks" / operator / "baseline-source.tar", (operator + " baseline").encode())
        baselines[operator] = archive.file_hash(path)
        save(path.parent / "baseline-binding.json", {"path": str(path), "sha256": baselines[operator]})
    directory = run / "tasks" / "exp" / "candidates" / "exp001"
    source = blob(directory / "source.tar", b"changed exp source")
    patch = blob(directory / "optimization.patch", b"tileElements = 4096 -> 8192")
    (old_task / "candidates" / "001").mkdir(parents=True)
    proposal = {"id": "exp-c01-coalesce-tile-8192", "cases": [1, 8, 14, 20, 3, 9],
                "intervention": {"intent": "Reduce tile setup with coalescing", "parameters": {"baseline_tile_elements": 4096, "candidate_tile_elements": 8192}},
                "rationale": "Fresh cases3/9 show MTE2 ratios 0.5170/0.5298 and 8036/8152 useful bytes per instruction at BF16 tiles.",
                "measurement_limitations": ["Startup-window limited profile"], "expected_counters": {"mte_instruction_density": "decrease"}}
    draft = save(old_task / "agent" / "next-experiment.json", proposal)
    save(directory / "inheritance.json", {"original_attempt_id": "old-run/train/exp001", "origin": str(old_task / "candidates" / "001"), "same_source_attempt": True})
    save(directory / "registration.json", {"session_id": "historical-session", "registered_at": "2026-09-08T13:00:00Z"})
    save(directory / "static-review.json", {"status": "static_review_passed_not_build_or_runtime_gate", "hardware_executed": False})
    inherited = {"candidate_id": "exp001", "source_hash": archive.file_hash(source), "patch_hash": archive.file_hash(patch),
                 "source_parent": {"candidate_id": None, "source_hash": baselines["exp"]},
                 "origin": {"run_id": "old-run", "registration": str(directory / "registration.json")},
                 "probes": [{"case_id": 3, "reason": "incorrect p/shape"}, {"case_id": 9, "reason": "incorrect drift"}]}
    cfg = campaign.make_config("new-run", baselines, inherited, "sha256:" + "1" * 64)
    ledger = campaign.prepare_ledger(run / "ledger", cfg)
    ledger.resume(event_id="start", reason="explicitly authorized")
    return run, ledger, draft


def add_build(run, ledger, *, outcome="failed"):
    directory = run / "tasks" / "exp" / "candidates" / "exp001" / "ab-build-execution"
    execution = save(directory / "execution.json", {"status": "failed" if outcome != "success" else "passed", "exit_status": 1 if outcome != "success" else 0,
                                                      "reason": "compiler failure" if outcome != "success" else None})
    blob(directory / "stderr.log", b"retained compiler diagnostic")
    ledger.start_stage(event_id="build-start", workload="exp", candidate_id="exp001", stage_id="build", kind="build", plan={"argv": ["actual-build"]})
    ledger.finish_stage(event_id="build-finish", workload="exp", stage_id="build", outcome=outcome, reason="compiler failure" if outcome != "success" else None,
                        evidence={str(execution): archive.file_hash(execution)})


def test_probe_correction_preserves_cpu_history_budgets_ids_and_old_bytes(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    add_build(run, ledger, outcome="success")
    prior = {p.name: p.read_bytes() for p in (run / "ledger").iterdir() if p.is_file()}
    status = ledger.status()
    result = archive.repair_bootstrap_probes(run, draft)
    audited = Path(result["old_ledger"])
    assert {p.name: p.read_bytes() for p in audited.iterdir() if p.is_file()} == prior
    current = campaign.Ledger(run / "ledger")
    assert current.status()["tasks"]["exp"]["used"] == status["tasks"]["exp"]["used"]
    assert current.state["tasks"]["exp"]["stages"] == status["tasks"]["exp"]["stages"]
    assert current.config["tasks"]["exp"]["inherited_candidates"][0]["source_hash"] == ledger.config["tasks"]["exp"]["inherited_candidates"][0]["source_hash"]
    assert "p/shape" not in json.dumps(current.config["tasks"]["exp"]["inherited_candidates"][0]["probes"])
    assert result["new_source_charge"] is False
    assert (run / "ledger" / ".lock").stat().st_ino == (audited / ".lock").stat().st_ino
    assert archive.repair_bootstrap_probes(run, draft) == result


def test_probe_correction_refuses_hardware_history_without_any_write(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    ledger.start_stage(event_id="aa-start", workload="exp", candidate_id=None, stage_id="aa", kind="control",
                        plan={"case_ids": [1], "control_type": "aa", "source_hash": ledger.config["tasks"]["exp"]["baseline_source_hash"]})
    before = (run / "ledger" / "events.jsonl").read_bytes()
    with pytest.raises(ValueError, match="hardware stage"):
        archive.repair_bootstrap_probes(run, draft)
    assert before == (run / "ledger" / "events.jsonl").read_bytes()
    assert not (run / "bootstrap" / "ledger-before-exp001-probe-correction").exists()


def test_zero_attempt_blockers_and_inherited_attempt_identity_are_split_isolated(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    marker = "VALIDATION_SECRET_MARKER"
    for operator in campaign.WORKLOADS:
        task = run / "tasks" / operator
        execution = save(task / "qualification-execution" / "execution.json", {"status": "failed", "error": marker if operator == "gelu" else "qualification launcher failed"})
        save(task / "qualification-result.json", {"status": "blocked", "error": marker if operator == "gelu" else "qualification launcher failed",
                                                   "evidence": {str(execution): archive.file_hash(execution)}})
        save(task / "closure.json", {"status": "blocked", "reason": marker if operator == "gelu" else "no qualified measurement method"})
    result = archive.Bridge(run).archive()
    train = Path(result["datasets"]["train"]["root"])
    validation = Path(result["datasets"]["validation"]["root"])
    assert result["datasets"]["train"]["optimization_attempts"] == 1
    assert result["datasets"]["train"]["new_source_attempts"] == 0
    assert result["datasets"]["train"]["inherited_source_attempts"] == 1
    assert result["datasets"]["validation"]["optimization_attempts"] == 0
    assert result["datasets"]["validation"]["task_checkpoints"] == 1
    memory = v2.previous_records(train)["old-run/train/exp001"]["body"]
    assert memory["identity"]["run_id"] == "old-run"
    assert memory["evaluations"][0]["measurement_quality"] == "not_measured_static_review_only"
    assert memory["machine_results"][0]["verdict"] == "not_recorded"
    assert memory["machine_results"][0]["episode_ref"] is None
    assert memory["knowledge"]["actual_reads"] == []
    assert not any(marker.encode() in p.read_bytes() for p in train.rglob("*") if p.is_file())
    assert any(marker.encode() in p.read_bytes() for p in validation.rglob("*") if p.is_file())
    assert archive.Bridge(run).archive() == result


def test_current_build_failure_preserved_without_fake_timing_or_new_source(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    add_build(run, ledger)
    result = archive.Bridge(run).archive()
    root = Path(result["datasets"]["train"]["root"])
    memory = v2.previous_records(root)["old-run/train/exp001"]["body"]
    assert len(memory["evaluations"]) == 2
    current = memory["evaluations"][-1]
    assert current["run_id"] == "new-run" and current["relation"] == "measurement_continuation"
    assert current["stages"][0]["status"] == "failed"
    assert current["stages"][0]["reason"] == "compiler failure"
    assert all(stage["name"] != "timing" for ev in memory["evaluations"] for stage in ev["stages"])
    assert any("timing" in text for text in memory["diagnosis"]["missing_evidence"])
    assert any(b"retained compiler diagnostic" in path.read_bytes() for path in root.rglob("*") if path.is_file())
    assert ledger.status()["tasks"]["exp"]["used"]["build"] == 1


def test_cross_split_explicit_evidence_is_rejected_before_publication(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    path = save(run / "tasks" / "gelu" / "private.json", {"result": "validation"})
    save(run / "tasks" / "mish" / "closure.json", {"status": "blocked", "evidence": [{"path": str(path)}]})
    with pytest.raises(ValueError, match="cross-split"):
        archive.Bridge(run).archive()
    assert not (run / "archive" / "train" / "v2" / "current.json").exists()


@pytest.mark.parametrize("relative,split,owner", [
    ("tasks/exp/qualification/exp-aa-qualification-qualification-6-BA/validation/9-swapped-B/metadata.json", "train", "exp"),
    ("method/foreach_norm/qualification/session/validation/1-normal-A/result.json", "train", "foreach_norm"),
    ("tasks/gelu/qualification/session/validation/20-swapped-A/result.json", "validation", "gelu"),
])
def test_oracle_validation_directory_inherits_resolved_task_owner(tmp_path, relative, split, owner):
    path = save(tmp_path / "run" / relative, {"oracle": "actual native directory shape"})
    assert archive._safe_path(path, split, owner=owner) == path.resolve()


@pytest.mark.parametrize("relative,split,owner", [
    ("validation/tasks/exp/qualification/validation/result.json", "train", "exp"),
    ("train/tasks/gelu/qualification/validation/result.json", "validation", "gelu"),
    ("validation/method/foreach_norm/qualification/validation/result.json", "train", "foreach_norm"),
    ("archive/validation/v2/result.json", "train", None),
    ("tasks/exp/archive/validation/v2/result.json", "train", "exp"),
    ("tasks/exp/revisions/r1/validation/result.json", "train", "exp"),
    ("tasks/gelu/qualification/validation/result.json", "train", None),
    ("tasks/exp/qualification/validation/result.json", "validation", None),
    ("tasks/exp/qualification/tasks/mish/result.json", "train", None),
    ("tasks/mish/qualification/validation/result.json", "train", "exp"),
])
def test_split_roots_and_foreign_tasks_cannot_be_hidden_by_oracle_directories(tmp_path, relative, split, owner):
    path = save(tmp_path / "run" / relative, {"foreign": True})
    with pytest.raises(ValueError, match="cross-(split|task)") as error:
        archive._safe_path(path, split, owner=owner)
    assert str(path.resolve()) in str(error.value)


@pytest.mark.parametrize("target_owner", ["gelu", "mish"])
def test_oracle_symlink_cannot_cross_task_or_split(tmp_path, target_owner):
    target = save(tmp_path / "run/tasks" / target_owner / "qualification/validation/result.json", {"foreign": True})
    link = tmp_path / "run/tasks/exp/qualification/session/validation/result.json"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    with pytest.raises(ValueError, match="cross-(split|task)") as error:
        archive._safe_path(link, "train")
    assert str(target.resolve()) in str(error.value) and str(link) in str(error.value)


def test_oracle_journals_archive_in_their_owner_split_without_new_attempts(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    markers = {"exp": "TRAIN_ORACLE_EXP", "foreach_norm": "TRAIN_ORACLE_NORM", "gelu": "VALIDATION_ORACLE_GELU"}
    for operator, marker in markers.items():
        owner = run / ("method" if operator == "foreach_norm" else "tasks") / operator
        for filename in ("metadata.json", "result.json"):
            save(owner / "qualification/session-6-BA/validation/9-swapped-B" / filename, {"marker": marker})
    output = archive.Bridge(run).archive()
    for split in ("train", "validation"):
        root = Path(output["datasets"][split]["root"])
        frozen = b"\n".join(path.read_bytes() for path in root.rglob("*") if path.is_file())
        assert (markers["exp"].encode() in frozen) is (split == "train")
        assert (markers["foreach_norm"].encode() in frozen) is (split == "train")
        assert (markers["gelu"].encode() in frozen) is (split == "validation")
    assert output["datasets"]["train"]["optimization_attempts"] == 1
    assert output["datasets"]["validation"]["optimization_attempts"] == 0


def test_same_split_foreign_task_closure_evidence_is_rejected(tmp_path):
    run, _, _ = fixture(tmp_path)
    path = save(run / "tasks/mish/qualification/session/validation/result.json", {"owner": "mish"})
    save(run / "tasks/exp/closure.json", {"status": "blocked", "evidence": [{"path": str(path)}]})
    with pytest.raises(ValueError, match="cross-task") as error:
        archive.Bridge(run).archive()
    assert str(path) in str(error.value)
    assert not (run / "archive/train/v2/current.json").exists()


def test_source_hash_mismatch_and_active_stage_fail_before_publication(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    ledger.start_stage(event_id="running", workload="exp", candidate_id="exp001", stage_id="build", kind="build", plan={"argv": ["build"]})
    with pytest.raises(ValueError, match="active stages"):
        archive.Bridge(run)
    ledger.finish_stage(event_id="finish", workload="exp", stage_id="build", outcome="interrupted", reason="stopped", evidence={"log_ref": "sha256:" + "2" * 64})
    (run / "tasks" / "exp" / "candidates" / "exp001" / "source.tar").write_bytes(b"mutated source")
    with pytest.raises(ValueError, match="identity mismatch"):
        archive.Bridge(run).archive()


def test_real_statistics_replay_creates_numeric_method_lesson_without_attempt(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    spec = importlib.util.spec_from_file_location("archive_statistics_fixture", ROOT / "tests" / "test_shared_context_report.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    manifest, sessions = fixtures.fixture(stages=("qualification",), case_ids=("3",))
    manifest.update(run_id="new-run", task_id="foreach_norm")
    for plan, session in zip(manifest["session_plan"], sessions):
        for sample in session["samples"]:
            if plan["load_order"] == "AB" and sample["role"] == "A":
                sample["ns_per_call"] *= 1.01
                sample["raw_duration"] *= 1.01
    report = archive.statistics.analyze(manifest, sessions)
    directory = run / "method" / "foreach_norm" / "qualification"
    for filename, data in (("manifest.json", manifest), ("sessions.json", sessions), ("report.json", report)):
        save(directory / filename, data)
    result = archive.Bridge(run).archive()
    records = v2.previous_records(Path(result["datasets"]["train"]["root"]))
    assert len([row for row in records.values() if row["record_kind"] == "optimization_memory"]) == 1
    lesson = records["new-run/train/method/foreach_norm"]["body"]
    assert lesson["kind"] == "measurement_method" and lesson["memory_refs"] == []
    symptom = lesson["diagnosis"]["symptoms"][0]
    values = symptom["attributes"]
    assert any(v["aa_ratio"] == pytest.approx(1.01) for v in values["key_abnormal_aa_conditions"].values())
    assert len(values["representative_aa_condition"]["ratio_ci95"]) == 2
    assert values["abnormal_factor_contrasts"]["load"]["full_log_contrast"] == pytest.approx(report["qualification"]["3"]["contrasts"]["load"]["mean_log"])
    assert values["maximum_role_cv"] == 0
    assert "role_cv_by_process_and_buffer" not in values and "block_log_effects" not in json.dumps(values)
    assert lesson["claims"][0]["status"] == "supported"
    before = (Path(result["datasets"]["train"]["root"]) / "current.json").read_bytes()
    altered = deepcopy(report)
    altered["measurement_quality"]["observed_checks_pass"] = True
    save(directory / "report.json", altered)
    with pytest.raises(ValueError, match="does not match"):
        archive.Bridge(run).archive()
    assert before == (Path(result["datasets"]["train"]["root"]) / "current.json").read_bytes()


def test_norm_positive_comparison_is_numeric_method_checkpoint_not_new_attempt_or_lesson(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    spec = importlib.util.spec_from_file_location('archive_positive_fixture', ROOT / 'tests/test_shared_context_report.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    manifest, sessions = fixtures.fixture(stages=('before', 'reverse', 'ab', 'after'), case_ids=('1', '3'))
    manifest.update(run_id='new-run', task_id='foreach_norm', attempt_id='historical-positive-control')
    manifest['qualification_scope'] = {'status': 'externally_qualified', 'report_hash': 'sha256:' + 'a' * 64}
    for session in sessions:
        for sample in session['samples']:
            if session['session_id'].startswith('ab-') and sample['case_id'] == '1' and sample['role'] == 'A':
                sample['ns_per_call'] *= 8
                sample['raw_duration'] *= 8
    report = archive.statistics.analyze(manifest, sessions)
    directory = run / 'method/foreach_norm/positive-comparison'
    for name, value in (('manifest.json', manifest), ('sessions.json', sessions), ('report.json', report)):
        save(directory / name, value)
    result = archive.Bridge(run).archive()
    recording = archive.load(result['recording_manifests']['train'])
    checkpoint = next(c for c in recording['task_checkpoints'] if c.get('kind') == 'standalone_method_positive_comparison')
    assert checkpoint['ab_cases']['1']['speedup'] == pytest.approx(8.8)
    assert checkpoint['ab_cases']['3']['speedup'] == pytest.approx(1.1)
    assert '95% CI' in checkpoint['observed_facts'][0]
    assert checkpoint['source_attempts_created'] == 0
    assert all('norm' not in row['id'] for row in recording['attempts'])
    assert recording['lessons'] == []
    validation = archive.load(result['recording_manifests']['validation'])
    assert all(c.get('operator') != 'foreach_norm' for c in validation['task_checkpoints'])
    report['phases']['ab']['cases']['1']['speedup'] = 100
    save(directory / 'report.json', report)
    with pytest.raises(ValueError, match='does not match'):
        archive.Bridge(run).archive()


def test_failed_candidate_comparison_keeps_partial_text_closure_and_stage_binding(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    add_build(run, ledger, outcome='success')
    ledger.start_stage(event_id='correct', workload='exp', candidate_id='exp001', stage_id='correct', kind='correctness',
                       plan={'case_ids': list(range(1, 21))})
    ledger.finish_stage(event_id='correct-finish', workload='exp', stage_id='correct', outcome='success', evidence={'ref': 'sha256:' + '1' * 64})
    candidate = ledger.state['tasks']['exp']['candidates']['exp001']
    plan = campaign.timing_plan(candidate, ledger.config['tasks']['exp']['baseline_source_hash'], purpose='search', manifest_ref='sha256:' + '2' * 64)
    ledger.start_stage(event_id='timing', workload='exp', candidate_id='exp001', stage_id='timing', kind='timing', plan=plan)
    directory = run / 'tasks/exp/candidates/exp001/comparisons/search'
    result = save(directory / 'group-result.json', {'schema_version': 'shared_context_comparison_group_v1',
        'operator': 'exp', 'candidate_id': 'exp001', 'run_id': 'new-run', 'stage_id': 'timing', 'formal_samples': 1,
        'evaluations': [{'control': 'original', 'status': 'execution_failed', 'error': {'message': 'device stopped'}}]})
    marker = b'{"type":"sample"}\n{"partial_native_marker"'
    blob(directory / 'original/ab-0/journal.jsonl', marker)
    ledger.finish_stage(event_id='timing-finish', workload='exp', stage_id='timing', outcome='failed', formal_samples=1,
                        evidence={str(result): archive.file_hash(result)}, reason='device stopped')
    output = archive.Bridge(run).archive()
    root = Path(output['datasets']['train']['root'])
    records = v2.previous_records(root)
    memory = records['old-run/train/exp001']['body']
    assert any(evaluation['summary'].get('formal_samples') == 1 for evaluation in memory['evaluations'])
    assert any(p.read_bytes() == marker for p in root.rglob('*') if p.is_file())


def prestart_result(run, *, producer=None):
    directory = run / 'tasks/exp/candidates/exp001'
    value = {'candidate_id': 'exp001', 'stage': 'correctness', 'status': 'failed',
        'ledger_stage_started': False, 'started_at': 100, 'ended_at': 101,
        'actual_costs': {'native_sessions_attempted': 0, 'native_sessions_completed': 0, 'native_complete_calls': 0, 'wall_seconds': 1},
        'case_ids': list(range(1, 21)), 'completed_cases': [],
        'error': {'type': 'ValueError', 'message': 'archive parser rejected APROF_SOURCE_SNAPSHOT.json'},
        'producers': producer or {}}
    path = save(directory / 'correctness-current-20/group-result.json', value)
    return directory, path


def test_prestart_failure_and_one_recovery_remain_on_original_source_without_ledger_stage(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    directory, failed = prestart_result(run)
    save(directory / 'correctness-prestart-recovery.json', {
        'attempt_id': 'exp001', 'failed_group': 'current-20', 'next_group': 'current-20-recovery1', 'recovery_number': 1,
        'source_hash': ledger.state['tasks']['exp']['candidates']['exp001']['source_hash'], 'source_change': False,
        'hardware_sessions_started': 0, 'failed_record': {'path': str(failed), 'sha256': archive.file_hash(failed)}})
    before = (run / 'ledger/events.jsonl').read_bytes()
    output = archive.Bridge(run).archive()
    records = v2.previous_records(Path(output['datasets']['train']['root']))
    memory = records['old-run/train/exp001']['body']
    observation = next(e for e in memory['evaluations'] if e['measurement_quality'] == 'not_measured_prestart')
    assert observation['stages'][0]['name'] == 'correctness_prestart'
    assert observation['stages'][0]['status'] == 'prestart_failure'
    assert observation['summary']['correctness_evaluated'] is False
    assert observation['summary']['recoveries'][0]['target_stage_id'] == 'exp001-correctness-current-20-recovery1'
    assert any(row['event_type'] == 'prestart_failure_observed' for row in memory['timeline'])
    assert not any(e['stages'][0]['status'] == 'correctness_failed' for e in memory['evaluations'])
    assert len([r for r in records.values() if r['record_kind'] == 'optimization_memory']) == 1
    assert before == (run / 'ledger/events.jsonl').read_bytes()
    assert ledger.state['tasks']['exp']['used']['source'] == 1


def test_qualification_preprepare_failure_is_method_checkpoint_without_source_attempt(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    save(run / 'tasks/mish/qualification-preflight-result-123.json', {
        'operator': 'mish', 'stage': 'baseline_method_qualification', 'status': 'execution_failed',
        'ledger_stage_started': False, 'actual_costs': {'native_sessions_attempted': 0, 'event_samples': 0},
        'formal_samples': 0, 'error': {'message': 'input preparation failed'}, 'producers': {}})
    output = archive.Bridge(run).archive()
    recording = archive.load(output['recording_manifests']['train'])
    checkpoint = next(c for c in recording['task_checkpoints'] if c.get('operator') == 'mish')
    assert checkpoint['status'] == 'prestart_blocked'
    assert checkpoint['source_attempt_count'] == 0
    assert checkpoint['method_qualification']['prestart_observations'][0]['qualification_evaluated'] is False
    assert not any(a['operator'] == 'mish' for a in recording['attempts'])


def test_old_wrapper_snapshot_survives_live_source_change_and_later_export(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    script = blob(tmp_path / 'scripts/diagnostic.py', b'old wrapper version\n')
    expected = archive.file_hash(script)
    directory, failed = prestart_result(run, producer={str(script): expected})
    snapshot = blob(failed.parent / 'producers/diagnostic.py', script.read_bytes())
    script.write_bytes(b'new wrapper version\n')
    output = archive.Bridge(run).archive()
    root = Path(output['datasets']['train']['root'])
    frozen = v2.object_path(root / 'external_evidence', expected)
    assert frozen.read_bytes() == b'old wrapper version\n'
    snapshot.unlink()
    second = archive.Bridge(run).archive()
    records = v2.previous_records(Path(second['datasets']['train']['root']))
    observation = next(e for e in records['old-run/train/exp001']['body']['evaluations'] if e['measurement_quality'] == 'not_measured_prestart')
    binding = observation['summary']['producer_binding']
    assert binding['producer_snapshot_unavailable'] == []
    assert binding['resolved'][0]['snapshot']['sha256'] == expected
    assert archive.Bridge(run).pointer(script, 'train', expected=expected)['sha256'] == expected
    metadata = archive.load(root / 'revisions' / archive.load(root / 'current.json')['revision'] / 'metadata.json')
    assert metadata['producer_source_ref']


def test_unavailable_old_producer_is_explicit_not_replaced_by_new_code(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    script = blob(tmp_path / 'scripts/diagnostic.py', b'new unrelated wrapper\n')
    directory, failed = prestart_result(run, producer={str(script): 'sha256:' + 'f' * 64})
    output = archive.Bridge(run).archive()
    records = v2.previous_records(Path(output['datasets']['train']['root']))
    observation = next(e for e in records['old-run/train/exp001']['body']['evaluations'] if e['measurement_quality'] == 'not_measured_prestart')
    binding = observation['summary']['producer_binding']
    assert binding['resolved'] == [] and len(binding['producer_snapshot_unavailable']) == 1


def test_renamed_bootstrap_producer_snapshot_keeps_retrospective_attribution(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    script = blob(tmp_path / 'scripts/shared_context_wrapper_evidence.py', b'old helper\n')
    expected = archive.file_hash(script)
    prestart_result(run, producer={str(script): expected})
    snapshot = blob(run / 'bootstrap/pre-wrapper-hardening/archive-helper-v3-before-format-fix.py', script.read_bytes())
    save(snapshot.parent / 'snapshot-format-v4.json', {'recorded_at': '2026-09-10T15:41:30Z',
        'files': {str(snapshot): expected}, 'old_helper_preservation': 'Retrospective producer preservation, not a preexecution freeze.'})
    script.write_bytes(b'new helper\n')
    output = archive.Bridge(run).archive()
    records = v2.previous_records(Path(output['datasets']['train']['root']))
    observation = next(e for e in records['old-run/train/exp001']['body']['evaluations'] if e['measurement_quality'] == 'not_measured_prestart')
    binding = observation['summary']['producer_binding']['resolved'][0]
    assert binding['snapshot']['sha256'] == expected
    assert binding['preexecution_freeze_established_by_archive'] is False
    assert 'Retrospective' in binding['preservation']['note']


def analysis_fixture(run, ledger):
    from datetime import datetime, timedelta
    directory = run / 'tasks/exp/candidates/exp001'
    profile = save(run / 'tasks/exp/current-profile-analysis.json', {'case3': {'baseline_mte2': 87, 'candidate_mte2': 44}})
    skill = blob(run / 'tasks/exp/knowledge/tile_setup/SKILL.md', b'recorded knowledge fixture')
    when = datetime.fromisoformat(ledger.events[0]['recorded_at']) + timedelta(seconds=1)
    initial = save(run / 'tasks/exp/agent-initial-review.json', {'kind': 'agent_initial_static_review', 'operator': 'exp', 'candidate_id': 'exp001',
        'created_at': when.isoformat(), 'actual_reads': [{'path': str(skill), 'sha256': archive.file_hash(skill)}]})
    feedback = save(run / 'tasks/exp/agent-feedback-decision.json', {'kind': 'agent_feedback_decision', 'operator': 'exp', 'candidate_id': 'exp001',
        'created_at': (when + timedelta(seconds=1)).isoformat(), 'actual_reads': [{'path': str(profile), 'sha256': archive.file_hash(profile)}]})
    refs = {name: {'path': str(path), 'sha256': archive.file_hash(path)} for name, path in (
        ('profile', profile), ('patch', directory / 'optimization.patch'), ('skill', skill), ('initial', initial), ('feedback', feedback))}
    fact = {'statement': 'case3 MTE2 instructions fell from 87 to 44.', 'basis': 'retrospective_current_evidence',
            'case_ids': [3], 'metrics': {'before': 87, 'after': 44}, 'evidence': ['profile'],
            'limitations': ['Descriptive profile comparison only; paired timing is unavailable.']}
    value = {'schema_version': archive.ANALYSIS_VERSION, 'candidate_id': 'exp001', 'source_hash': ledger.state['tasks']['exp']['candidates']['exp001']['source_hash'],
        'retrospective': True, 'evidence': refs, 'diagnosis': {'symptoms': [fact], 'hypotheses': [], 'missing_evidence': ['Qualified paired timing']},
        'intervention': {'statement': 'tileElements 4096 to 8192', 'basis': 'retrospective_current_evidence', 'evidence': ['patch']},
        'lessons': [{'id': 'case3-setup', 'kind': 'operator_optimization', 'title': 'Case3 setup instruction reduction',
                     'claims': [{**fact, 'status': 'supported'}], 'evidence': ['profile', 'patch']}],
        'read_audits': [{'record': 'initial', 'temporal_scope': 'current_pre_execution_review', 'used_for_current_judgment': ['skill']},
                        {'record': 'feedback', 'temporal_scope': 'post_execution_analysis', 'used_for_current_judgment': []}]}
    path = save(directory / 'analysis.json', value)
    return path, value


def test_retrospective_analysis_populates_memory_lessons_and_scoped_actual_read_audits(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    path, value = analysis_fixture(run, ledger)
    before = (run / 'ledger/events.jsonl').read_bytes()
    archive.validate_candidate_analysis(path, run, 'exp', 'exp001', max_evidence_bytes=1024 * 1024)
    output = archive.Bridge(run).archive()
    records = v2.previous_records(Path(output['datasets']['train']['root']))
    memory = records['old-run/train/exp001']['body']
    assert memory['diagnosis']['symptoms'][0]['attributes']['metrics'] == {'before': 87, 'after': 44}
    assert memory['diagnosis']['symptoms'][0]['basis'] == 'retrospective_current_evidence'
    assert memory['diagnosis']['hypotheses'][0]['basis'] == 'recorded_historical_agent_proposal'
    assert len(memory['knowledge']['actual_reads']) == 2
    assert memory['knowledge']['actual_reads'][0]['purpose'].startswith('current_pre_execution_review')
    assert 'tile_setup/SKILL.md' in memory['knowledge']['actual_reads'][0]['purpose']
    assert memory['knowledge']['actual_reads'][1]['purpose'].startswith('post_execution_analysis')
    lesson = records['new-run/train/operator/exp/exp001/case3-setup']['body']
    assert lesson['retrospective'] is True and lesson['claims'][0]['status'] == 'supported'
    assert lesson['memory_refs'][0]['id'] == 'old-run/train/exp001'
    assert len([r for r in records.values() if r['record_kind'] == 'optimization_memory']) == 1
    assert before == (run / 'ledger/events.jsonl').read_bytes()


@pytest.mark.parametrize('fault', ['prospective', 'unknown', 'source', 'hash', 'alias', 'claim', 'read_scope', 'unread_skill', 'historical_reads'])
def test_analysis_validator_refuses_unbound_or_relabelled_facts_without_archive(tmp_path, fault):
    run, ledger, _ = fixture(tmp_path)
    path, value = analysis_fixture(run, ledger)
    if fault == 'prospective': value['retrospective'] = False
    if fault == 'unknown': value['fabricated_predictions'] = []
    if fault == 'source': value['source_hash'] = 'sha256:' + '0' * 64
    if fault == 'hash': value['evidence']['profile']['sha256'] = 'sha256:' + '0' * 64
    if fault == 'alias': value['diagnosis']['symptoms'][0]['evidence'] = ['missing']
    if fault == 'claim': value['lessons'][0]['claims'][0]['status'] = 'proven'
    if fault == 'read_scope': value['read_audits'][0]['temporal_scope'] = 'original_optimizer_proposal'
    if fault == 'unread_skill': value['read_audits'][0]['used_for_current_judgment'] = ['profile']
    if fault == 'historical_reads':
        audit_path = Path(value['evidence']['initial']['path'])
        audit = archive.load(audit_path); audit['created_at'] = '2000-01-01T00:00:00+00:00'; save(audit_path, audit)
        value['evidence']['initial']['sha256'] = archive.file_hash(audit_path)
    save(path, value)
    with pytest.raises(ValueError):
        archive.validate_candidate_analysis(path, run, 'exp', 'exp001', max_evidence_bytes=1024 * 1024)
    assert not (run / 'archive').exists()


def test_raw_profile_csv_and_native_build_binaries_are_frozen_for_baseline_and_candidate(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    task = run / 'tasks/exp'; candidate = task / 'candidates/exp001'
    binary = blob(candidate / 'ab-build/B.so', b'tiny native DSO fixture')
    runner = blob(run / 'tools/diagnostic/runner', b'tiny diagnostic runner fixture')
    build_path = save(candidate / 'ab-build/build_manifest.json', {'roles': {'B': {'binary': str(binary), 'binary_sha256': archive.file_hash(binary)[7:]}}})
    runner_path = save(runner.parent / 'profile-build.json', {'runner': str(runner), 'runner_hash': archive.file_hash(runner)})
    markers = []
    for cid, parent, sid in ((None, task, 'baseline-profile'), ('exp001', candidate, 'candidate-profile')):
        csv = blob(parent / 'profile-case3/case_03/PROF/Memory.csv', (sid + ',mte2\n3,44\n').encode())
        markers.append(csv.read_bytes())
        result = save(parent / 'profile-case3/group-result.json', {'status': 'passed', 'stage': 'profile', 'candidate_id': cid, 'producers': {}})
        plan = {'case_ids': [3], 'capture_window': {'full_operator': True}, 'role_build': str(build_path), 'runner_build': str(runner_path),
                'source_hash': ledger.config['tasks']['exp']['baseline_source_hash'] if cid is None else ledger.state['tasks']['exp']['candidates'][cid]['source_hash']}
        ledger.start_stage(event_id=sid, workload='exp', candidate_id=cid, stage_id=sid, kind='profile', plan=plan)
        ledger.finish_stage(event_id=sid + '-finish', workload='exp', stage_id=sid, outcome='success', evidence={str(result): archive.file_hash(result)})
    output = archive.Bridge(run).archive()
    root = Path(output['datasets']['train']['root'])
    for content in [*markers, binary.read_bytes(), runner.read_bytes()]:
        assert v2.object_path(root / 'external_evidence', v2.digest_bytes(content)).read_bytes() == content


def test_compact_method_report_retains_low_cv_counterexample_and_factor_extremes(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    spec = importlib.util.spec_from_file_location('compact_method_fixture', ROOT / 'tests/test_shared_context_report.py')
    fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
    manifest, sessions = fixtures.fixture(stages=('qualification',), case_ids=('1',))
    manifest.update(run_id='new-run', task_id='masked_scale')
    ratios = [1.002, .998, 1.003, .999, .9419, 1.004]
    for plan, session in zip(manifest['session_plan'], sessions):
        for sample in session['samples']:
            if plan['load_order'] == 'AB' and sample['role'] == 'A':
                sample['ns_per_call'] *= ratios[plan['replicate_id'] - 1]
                sample['raw_duration'] *= ratios[plan['replicate_id'] - 1]
    report = archive.statistics.analyze(manifest, sessions)
    directory = run / 'tasks/masked_scale/qualification'
    for name, value in (('manifest.json', manifest), ('sessions.json', sessions), ('report.json', report)):
        save(directory / name, value)
    result = archive.Bridge(run).archive()
    records = v2.previous_records(Path(result['datasets']['train']['root']))
    lesson = records['new-run/train/method/masked_scale']['body']
    values = lesson['diagnosis']['symptoms'][0]['attributes']
    assert values['maximum_role_cv'] == 0 and values['low_cv_is_not_sufficient_counterexample'] is True
    assert values['abnormal_factor_contrasts']['load']['block_multiplier_range'][0] == pytest.approx(.9419)
    assert values['abnormal_factor_contrasts']['load']['mixed_block_directions'] is True
    assert 'block_log_effects' not in json.dumps(lesson) and 'role_cv_by_process' not in json.dumps(lesson)
    assert 'failures' not in lesson['claims'][0]['attributes']['failure_summary']
    recording = archive.load(result['recording_manifests']['train'])
    checkpoint = next(c for c in recording['task_checkpoints'] if c['operator'] == 'masked_scale')
    assert 'qualification' not in checkpoint['method_qualification'] and 'cv_by_cell' not in checkpoint['method_qualification']


def test_task_notes_and_minimal_closure_are_external_evidence_without_new_attempt(tmp_path):
    run, ledger, _ = fixture(tmp_path)
    task = run / 'tasks/masked_scale'
    for name in ('aa-failure-analysis.json', 'agent-initial-review.json', 'agent-feedback-decision.json', 'runtime-supplement-manifest.json'):
        save(task / name, {'recorded': name, 'marker': 'external-not-inline'})
    result_path = save(task / 'qualification-result.json', {'status': 'quality_failed', 'reason': 'fixture control failure'})
    closure = {'status': 'blocked_measurement_qualification', 'reason': 'actual method control failed', 'next_action': 'preserve and plan a separate method experiment',
               'paired_performance_evaluated': False, 'evidence': [{'path': str(result_path), 'sha256': archive.file_hash(result_path)}]}
    save(task / 'closure.json', closure)
    result = archive.Bridge(run).archive()
    recording = archive.load(result['recording_manifests']['train'])
    checkpoint = next(c for c in recording['task_checkpoints'] if c['operator'] == 'masked_scale')
    assert checkpoint['recorded_closure'] == closure and checkpoint['source_attempt_count'] == 0
    paths = {Path(p['path']).name for p in recording['artifact_index']}
    assert {'aa-failure-analysis.json', 'agent-initial-review.json', 'agent-feedback-decision.json', 'runtime-supplement-manifest.json'} <= paths


def test_current_analysis_preserves_compact_historical_predictions_and_intervention_evidence(tmp_path):
    run, ledger, draft = fixture(tmp_path)
    analysis_fixture(run, ledger)
    output = archive.Bridge(run).archive()
    root = Path(output['datasets']['train']['root'])
    memory = v2.previous_records(root)['old-run/train/exp001']['body']
    intervention = memory['intervention']
    assert intervention['basis'] == 'retrospective_current_evidence'
    previous = intervention['attributes']['recorded_historical_proposal']
    assert set(previous) == {'statement', 'basis', 'parameters', 'expected_counters', 'limitations'}
    assert previous['basis'] == 'recorded_historical_agent_proposal'
    assert previous['parameters'] == {'baseline_tile_elements': 4096, 'candidate_tile_elements': 8192}
    assert previous['expected_counters'] == {'mte_instruction_density': 'decrease'}
    assert previous['limitations'] == ['Startup-window limited profile']
    assert 'evidence' not in previous
    revision = archive.load(root / 'current.json')['revision']
    index = archive.load(root / 'revisions' / revision / 'evidence_index.json')
    bound = {index[ref]['sha256'] for ref in intervention['evidence_ids']}
    assert archive.file_hash(draft) in bound and memory['sources']['patch'] in bound

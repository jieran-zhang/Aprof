"""Real CPU dispatcher/child lifecycle; component payloads are explicit fixtures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))
import task_rule_recorder as recorder_module
from task_rule_recorder import TaskRuleRecorder
from task_rule_admission import PROTOCOL, TASK_PROTOCOL, STAGES, verify_task_attempt_roster
from aprof_runtime.local_evidence import LocalEvidence
from run_aprof_job import run
from timing_admission import read


def prepare(root, mode='passed'):
    local = LocalEvidence(root / 'records')
    launch = root / 'launch.json'
    job = dict(job_id='CPU-task-recorder-' + mode,
        argv=[sys.executable, str(Path(__file__).resolve()), '--child', str(launch)],
        cwd=str(REPO), output_dir=str(root / 'dispatcher'), timeout_seconds=30,
        environment={'APROF_SKILL_LIB': str(recorder_module.selected_runtime()), 'PYTHONDONTWRITEBYTECODE':'1'})
    identity = dict(operator='exp', run_id='CPU-rule', candidate_id='CPU-only',
        source_hashes={role:local.register_json({'CPU_source':role}) for role in ('baseline','candidate')})
    anchor = dict(schema_version=1, protocol=PROTOCOL, task_protocol=TASK_PROTOCOL, purpose='promotion',
        created_at=time.time(), budget_seconds=30, **identity,
        job_ref=local.register_json(job), history_refs=[local.register_json({'previous':'CPU fixture'})])
    for key in ('input_inventory_ref','boundary_plan_ref','screen_plan_ref','profile_plan_ref','source_review_ref'):
        anchor[key] = local.register_json({'CPU_reference':key})
    binary = local.register_json({'CPU_binary':True})
    post = dict(binary_hashes={r:binary for r in ('baseline','candidate')},
        oracle_files={'/CPU/original-oracle.py':local.register_json({'CPU_oracle':True})},
        task_config_ref=local.register_json({'CPU_Task_config':True}),
        profile_configs={r:local.register_json({'CPU_profile':r}) for r in ('baseline','candidate')})
    anchor_ref = local.register_json(anchor)
    post_ref = local.register_json(post)
    index = local.write_index(root / 'initial-index.json')
    deadline = time.monotonic() + 30
    launch.write_text(json.dumps(dict(index=str(index), anchor_ref=anchor_ref, post_ref=post_ref,
        deadline=deadline, mode=mode)))
    return local, anchor_ref, post, deadline, job


def complete_stage(recorder, stage):
    reference = recorder.store.register_json({'CPU_component':stage, 'admission_authority':False})
    recorder.start(stage)
    recorder.complete(stage, [reference], report_ref=None if stage=='online_admission' else reference)


def child(launch):
    value = json.loads(Path(launch).read_text())
    root = Path(launch).parent
    local = LocalEvidence.from_index(value['index'])
    recorder = TaskRuleRecorder(local, root / 'recorder', anchor_ref=value['anchor_ref'],
        post_build=read(local, value['post_ref']), deadline=value['deadline'])
    code = 0
    try:
        for stage in STAGES:
            if stage == 'boundary' and value['mode'] == 'failed':
                recorder.start(stage)
                raise RuntimeError('real CPU child stage failure')
            if stage == 'boundary' and value['mode'] == 'unfinished_exit_zero':
                recorder.finish()
            complete_stage(recorder, stage)
        reference = recorder.finish()
        if value['mode'] == 'finished_exit_nonzero': code = 7
    except Exception as error:
        recorder.fail_active(error)
        reference = recorder.partial_report()
        code = 0 if value['mode'] == 'unfinished_exit_zero' else 7
    report = read(local, reference)
    assert 'execution_ref' not in report and 'execution_ref' not in recorder.expected
    (root / 'child-handoff.json').write_text(json.dumps(dict(report_ref=reference, expected=recorder.expected)))
    local.write_index(root / 'child-index.json')
    return code


def dispatch(root, mode):
    _, _, _, _, job = prepare(root, mode)
    execution = run(job)  # Real supervisor, CPU child and actual exit receipt.
    local = LocalEvidence.from_index(root / 'child-index.json')
    handoff = json.loads((root / 'child-handoff.json').read_text())
    original = local.verify_artifact(handoff['report_ref']).read_bytes()
    report = read(local, handoff['report_ref'])
    for stream in ('stdout','stderr'):
        assert local.register_artifact(execution[stream]['path']) == execution[stream]['sha256']
    execution_ref = local.register_artifact(root / 'dispatcher/execution.json')
    expected = dict(handoff['expected'], execution_ref=execution_ref)
    report['execution_ref'] = execution_ref
    reference = local.register_json(report)  # New dispatcher report, no child-file overwrite.
    local.write_index(root / 'dispatcher-index.json')
    assert local.verify_artifact(handoff['report_ref']).read_bytes() == original
    return local, reference, expected, execution, handoff['report_ref']


def test_real_dispatcher_success_binds_exit_and_keeps_every_old_roster_hash(tmp_path):
    local, reference, expected, execution, child_ref = dispatch(tmp_path, 'passed')
    result = verify_task_attempt_roster(local, reference, expected=expected)
    assert result['valid'] and not result['admission_authority']
    assert result['actual_duration_seconds'] == execution['duration_seconds'] > 0
    assert list(result['stage_windows']) == list(STAGES)
    assert 'execution_ref' not in read(local, child_ref)
    for digest in local._paths: local.verify_artifact(digest)
    with pytest.raises(ValueError, match='execution_ref differs'):
        verify_task_attempt_roster(local, child_ref, expected=expected)
    fake = deepcopy(read(local, reference)); fake['execution_ref'] = local.register_json({'status':'passed'})
    with pytest.raises(ValueError, match='execution_ref differs'):
        verify_task_attempt_roster(local, local.register_json(fake), expected=expected)


@pytest.mark.parametrize('mode', ['failed','unfinished_exit_zero','finished_exit_nonzero'])
def test_partial_or_failed_real_child_cannot_be_admitted(tmp_path, mode):
    local, reference, expected, execution, child_ref = dispatch(tmp_path, mode)
    if mode == 'unfinished_exit_zero': assert execution['exit_code'] == 0
    else: assert execution['exit_code'] == 7
    report = read(local, child_ref)
    roster = read(local, report['attempt_roster_ref'])
    if mode == 'failed':
        assert len(roster['events']) == 3
        assert read(local, roster['events'][-1])['state'] == 'started'
    with pytest.raises(ValueError): verify_task_attempt_roster(local, reference, expected=expected)
    for digest in local._paths: local.verify_artifact(digest)


def recorder_fixture(tmp_path):
    local, anchor, post, deadline, _ = prepare(tmp_path)
    return TaskRuleRecorder(local, tmp_path/'recorder', anchor_ref=anchor, post_build=post, deadline=deadline)


def test_repeated_stage_stops_without_fabricating_completion(tmp_path):
    recorder = recorder_fixture(tmp_path); recorder.start('correctness')
    with pytest.raises(ValueError, match='repeated'): recorder.start('correctness')
    assert recorder.failed and len(recorder.events) == 1
    with pytest.raises(ValueError, match='terminal'): recorder.start('boundary')
    assert read(recorder.store, recorder.partial_report())['attempt_roster_ref'] == recorder.roster_ref


def test_expired_original_deadline_retains_started_partial(tmp_path, monkeypatch):
    recorder = recorder_fixture(tmp_path); recorder.start('correctness')
    evidence = recorder.store.register_json({'CPU_actual_partial':True})
    monkeypatch.setattr(recorder_module.time, 'monotonic', lambda:recorder.deadline+1)
    with pytest.raises(TimeoutError): recorder.complete('correctness', [evidence], report_ref=evidence)
    assert recorder.failed and len(recorder.events) == 1
    assert read(recorder.store, recorder.events[-1])['state'] == 'started'
    assert recorder.failure_ref and recorder.partial_report()
    with pytest.raises(ValueError, match='terminal'): recorder.start('boundary')


def test_failed_verdict_is_partial_and_never_completed(tmp_path):
    recorder = recorder_fixture(tmp_path); recorder.start('correctness')
    evidence = recorder.store.register_json({'passed':False})
    with pytest.raises(ValueError, match='stage failed'):
        recorder.complete('correctness', [evidence], report_ref=evidence, passed=False)
    assert len(recorder.events) == 1 and evidence in recorder.stage_evidence['correctness']


def test_recorder_cannot_accept_child_execution_or_second_registration(tmp_path):
    local, anchor, post, deadline, _ = prepare(tmp_path)
    with pytest.raises(ValueError, match='post-build'):
        TaskRuleRecorder(local, tmp_path/'bad', anchor_ref=anchor,
            post_build=dict(post, execution_ref='invented'), deadline=deadline)
    TaskRuleRecorder(local, tmp_path/'recorder', anchor_ref=anchor, post_build=post, deadline=deadline)
    with pytest.raises(FileExistsError):
        TaskRuleRecorder(local, tmp_path/'recorder', anchor_ref=anchor, post_build=post, deadline=deadline)
    with pytest.raises(ValueError, match='LocalEvidence'):
        TaskRuleRecorder(object(), tmp_path/'other', anchor_ref=anchor, post_build=post, deadline=deadline)


if __name__ == '__main__':
    assert sys.argv[1] == '--child'
    raise SystemExit(child(sys.argv[2]))

"""Qualification boundaries, without running a device or claiming admission."""
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
sys.path.insert(0, str(ROOT / 'skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts'))
import qualify_task_window_timing_v051 as qualification


def profile_fixture(tmp_path):
    raw = 'PROF_one/device_0/data/task.data'
    log = 'PROF_one/mindstudio_profiler_log/collection_device_0.log'
    for relative, contents in ((raw, b'original tasks'), (log, b'original log\n')):
        target = tmp_path / 'profile' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    captured = qualification.relative_profile_inventory(tmp_path / 'profile')
    original = tmp_path / 'capture-logs' / log
    original.parent.mkdir(parents=True)
    original.write_bytes(b'original log\n')
    (tmp_path / 'profile' / log).write_bytes(b'original log\nexport appended\n')
    receipt = {'capture_profile_files': captured,
               'capture_log_copies': {log: qualification.binding(original)},
               'profile_files': qualification.profile_inventory(tmp_path / 'profile')}
    return receipt, raw, log


def test_export_can_append_log_without_changing_task_data(tmp_path):
    receipt, _, _ = profile_fixture(tmp_path)
    qualification.replay_captured_profile(tmp_path, tmp_path / 'profile', receipt, qualification.Evidence())


def test_archived_profile_replays_after_local_scratch_is_removed(tmp_path):
    receipt, _, _ = profile_fixture(tmp_path)
    local = tmp_path / 'profile'; archived = tmp_path / 'persisted-profile'
    shutil.copytree(local, archived)
    shutil.rmtree(local)
    qualification.replay_captured_profile(tmp_path, archived, receipt, qualification.Evidence(), online_root=local)
    (archived / 'PROF_one/device_0/data/task.data').write_bytes(b'changed after archive')
    with pytest.raises(ValueError):
        qualification.replay_captured_profile(tmp_path, archived, receipt, qualification.Evidence(), online_root=local)


@pytest.mark.parametrize('mutation', ['raw', 'truncate_log', 'rewrite_log', 'missing_original_log'])
def test_export_cannot_hide_raw_or_original_log_changes(tmp_path, mutation):
    receipt, raw, log = profile_fixture(tmp_path)
    if mutation == 'missing_original_log':
        receipt['capture_log_copies'] = {}
    else:
        path = tmp_path / 'profile' / (raw if mutation == 'raw' else log)
        path.write_bytes({'raw': b'altered tasks', 'truncate_log': b'original',
                          'rewrite_log': b'rewritten log\n'}[mutation])
        receipt['profile_files'] = qualification.profile_inventory(tmp_path / 'profile')
    with pytest.raises(ValueError):
        qualification.replay_captured_profile(tmp_path, tmp_path / 'profile', receipt, qualification.Evidence())


def test_observation_uses_frozen_case_repeat_and_rejects_changed_calibration(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, 'local_confirmation_dir',
                        lambda _qualification, _operator: tmp_path / 'exp/confirmation')
    folder = tmp_path / 'exp/confirmation'
    folder.mkdir(parents=True)
    calibration = folder / 'calibration.json'
    qualification.save_new(calibration, {'cases': [{'case_id': 1, 'repeat': 7300}]})
    qualification.save_new(folder / 'registration.json', {
        'calibration_ref': qualification.digest(calibration), 'repeat_by_case': {'1': 7300}})
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    assert qualification.observation_repeat(directory, {'operator': 'exp'}) == 7300
    calibration.write_text('{"cases": [{"case_id": 1, "repeat": 100}]}')
    with pytest.raises(ValueError, match='calibration differs'):
        qualification.observation_repeat(directory, {'operator': 'exp'})


def test_post_task_observation_repeat_uses_complete_archive_after_local_cleanup(tmp_path):
    from aprof_runtime.store import EpisodeStore
    from aprof_runtime.traces import register_json_artifact
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    path = tmp_path / 'archive.sqlite'
    with EpisodeStore(path) as store:
        calibration = register_json_artifact(store, {'cases': [{'case_id': 1, 'repeat': 200}]})
        registration = register_json_artifact(store, {'calibration_ref': calibration,
            'repeat_by_case': {'1': 200}})
        proof = register_json_artifact(store, {'operator': 'exp', 'registration_ref': registration})
        completion = register_json_artifact(store, {'proof_ref': proof})
    assert qualification.observation_repeat(directory, {'operator': 'exp'},
        archived={'store': str(path), 'completion_ref': completion}) == 200


def test_confirmation_roster_uses_fresh_local_work_without_store(tmp_path):
    plan = {'interpreter': {'path': '/trusted/python'},
            'configs': {'exp': '/frozen/exp.json', 'sigmoid': '/frozen/sigmoid.json'}}
    slots = qualification.roster_slots(tmp_path / qualification.PLANNED_OUTPUT_NAME, plan)
    confirmations = [slot for slot in slots if slot['kind'] == 'confirmation']
    assert len(confirmations) == 2
    for slot in confirmations:
        argv = slot['job']['argv']
        assert '--store' not in argv
        assert argv[argv.index('--output') + 1] == slot['output_dir']
        assert slot['output_dir'].startswith('/tmp/aprof-task-window-')
        assert slot['job']['timeout_seconds'] == 3600


@pytest.mark.parametrize('completion_after_exit', [False, True])
def test_online_slot_finishes_without_charging_an_independent_replay(tmp_path, monkeypatch, completion_after_exit):
    root = tmp_path / 'repo'; curation = root / 'scaffolding/curation'; curation.mkdir(parents=True)
    output = tmp_path / qualification.PLANNED_OUTPUT_NAME; output.mkdir()
    local = tmp_path / 'local-work'; slot = {'slot_id': 'exp-confirmation', 'kind': 'confirmation',
        'operator': 'exp', 'case_id': None, 'prerequisite_slot': None, 'job': {'job_id': 'exp-confirmation'}}
    roster = {'qualification_dir': str(output), 'slots': [slot], 'created_at': time.time()}
    qualification.save_new(output / 'roster.json', roster)
    anchor = curation / 'anchor.json'
    qualification.save_new(anchor, {'schema_version': 1, 'purpose': qualification.PURPOSE,
        'roster': qualification.binding(output / 'roster.json'), 'max_attempts': 1,
        'resampling': 'none', 'recorded_at_utc': datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(qualification, 'ROOT', root)
    monkeypatch.setattr(qualification, 'checked_plan', lambda _output: ({}, {}))
    monkeypatch.setattr(qualification, 'roster_slots', lambda _output, _plan: [slot])
    monkeypatch.setattr(qualification, 'local_confirmation_dir', lambda _output, _op: local)
    monkeypatch.setattr(qualification, 'locks', lambda _names: contextlib.nullcontext())
    monkeypatch.setattr(qualification, 'clean_parent_environment', lambda: None)
    monkeypatch.setattr(qualification, 'slot_replay_job', lambda *_args: pytest.fail('replay job entered online budget'))

    def fake_job(_job):
        started = time.time()
        local.mkdir()
        time.sleep(0.01)
        completion_started = time.time()
        time.sleep(0.01)
        completion_finished = time.time()
        time.sleep(0.01)
        finished = time.time()
        qualification.save_new(local / 'local-result.json', {'status': 'passed', 'error': None,
            'started_at': completion_started,
            'finished_at': finished + 0.1 if completion_after_exit else completion_finished,
            'elapsed_seconds': 0.5, 'timeout_seconds': 3600})
        path = output / 'campaign/exp-confirmation/job/execution.json'
        path.parent.mkdir(parents=True)
        receipt = {'exit_code': 0, 'status': 'passed',
            'started_at': datetime.fromtimestamp(started, timezone.utc).isoformat(),
            'finished_at': datetime.fromtimestamp(finished, timezone.utc).isoformat()}
        qualification.save_new(path, receipt)
        return receipt

    monkeypatch.setattr(qualification, 'job_run', fake_job)
    result = qualification.run(output / 'roster.json', anchor)
    terminal = qualification.read(output / 'campaign/exp-confirmation/terminal.json')
    assert result['accepted'] is (not completion_after_exit)
    assert terminal['status'] == ('failed' if completion_after_exit else 'passed')
    assert 'replay_execution' not in terminal


def test_observation_profile_copy_is_explicitly_post_task(tmp_path, monkeypatch):
    from device_task_timing import copy_profile_tree
    root = tmp_path / 'qualification'; root.mkdir()
    folder = root / 'observations/exp-observation-01'; folder.mkdir(parents=True)
    mode = folder / 'profiled'; mode.mkdir()
    scratch = tmp_path / 'scratch'
    local = scratch / 'observations/exp-observation-01/profile'
    raw = local / 'PROF_one/device_0/data/task.data'; raw.parent.mkdir(parents=True)
    raw.write_bytes(b'complete raw profile')
    table = local / 'PROF_one/mindstudio_profiler_output/op_summary.csv'; table.parent.mkdir(parents=True)
    table.write_text('full task table')
    config = root / 'exp/config.json'; config.parent.mkdir()
    qualification.save_new(config, {'task_profile': {'scratch_root': str(scratch)}})
    qualification.save_new(folder / 'terminal.json', {'complete': True, 'finished_at': time.time() - 1})
    qualification.save_new(mode / 'receipt.json', {'status': 'passed', 'mode': 'profiled',
        'profile_files': qualification.profile_inventory(local)})
    monkeypatch.setattr(qualification, 'checked_plan', lambda _path: ({'configs': {'exp': str(config)}}, {}))
    monkeypatch.setattr(qualification, 'task_modules', lambda: (SimpleNamespace(copy_profile_tree=copy_profile_tree), None, None, None))
    ref = qualification.archive_observation(root, 'exp', 1)
    assert qualification.read(ref['path'])['cost_scope'] == 'post_task_archive'
    receipt = qualification.read(mode / 'receipt.json')
    assert 'profile_transfer' not in receipt
    assert qualification.replay_profile_transfer(mode, {'task_profile': {'scratch_root': str(scratch)}},
        receipt, qualification.read(folder / 'terminal.json')['finished_at'], qualification.Evidence()) == mode / 'profile'
    (mode / 'profile/PROF_one/device_0/data/task.data').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='post-task profile archive differs'):
        qualification.replay_profile_transfer(mode, {'task_profile': {'scratch_root': str(scratch)}},
            receipt, qualification.read(folder / 'terminal.json')['finished_at'], qualification.Evidence())

"""Offline orchestration contracts; no device evidence is manufactured."""
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import qualify_task_timing_v051 as task
from replay_timing_diagnosis import Evidence


def plan_for(tmp_path):
    return {'interpreter': {'path': '/frozen/python'},
            'configs': {op: str(tmp_path / op / 'config.json') for op in ('exp', 'sigmoid')}}


@pytest.mark.parametrize('operator', ['exp', 'sigmoid'])
def test_fixed_twenty_cases_preserve_original_binary_and_oracles(tmp_path, operator):
    old = task.read(task.PREDECESSOR / operator / 'config.json')
    actual = task.config_for(tmp_path, operator, Path('/frozen/msprof'))
    expected = deepcopy(old)
    expected.update(run_id=tmp_path.name, session_id=tmp_path.name + '-' + operator,
                    task_profile={'profiler': '/frozen/msprof',
                                  'scratch_root': f'/tmp/aprof-task-{tmp_path.name}-{operator}',
                                  'role_kernel_names': {
                        role: [operator + '_kernel'] for role in ('baseline', 'candidate')}})
    assert actual == expected
    assert actual['expected_case_ids'] == list(range(1, 21))
    assert not Path(actual['task_profile']['scratch_root']).exists()


def test_case_scope_or_rebuilt_binary_cannot_enter_fixed_confirmation(tmp_path, monkeypatch):
    original = task.read(task.PREDECESSOR / 'exp/config.json')
    for change in ('scope', 'binary'):
        value = deepcopy(original)
        if change == 'scope': value['expected_case_ids'].pop()
        else: value['build']['binary'] = '/newly-built/exp'
        monkeypatch.setattr(task, 'read', lambda _: value)
        with pytest.raises(ValueError, match='original full-case binary'):
            task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))


def test_six_slots_have_fixed_budgets_order_and_direct_dependencies(tmp_path):
    slots = task.roster_slots(tmp_path, plan_for(tmp_path))
    assert [s['slot_id'] for s in slots] == [
        'exp-confirmation', 'exp-observation-01', 'exp-observation-09',
        'sigmoid-confirmation', 'sigmoid-observation-01', 'sigmoid-observation-04']
    assert [s['prerequisite_slot'] for s in slots] == [None, slots[0]['slot_id'], slots[1]['slot_id'],
                                                     None, slots[3]['slot_id'], slots[4]['slot_id']]
    assert [s['job']['timeout_seconds'] for s in slots] == [3600, 1200, 1200, 3600, 1200, 1200]
    assert task.BUDGETS['campaign'] == 12600
    assert [s['order'] for s in slots if s['kind'] == 'observation'] == [
        ['unprofiled', 'profiled'], ['profiled', 'unprofiled'],
        ['profiled', 'unprofiled'], ['unprofiled', 'profiled']]
    assert all(s['job']['argv'][0] == '/frozen/python' for s in slots)


def test_observation_targets_original_native_and_fixed_command_file(tmp_path):
    output = tmp_path / 'observations/exp-observation-01/profiled'
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    case = config['cases'][0]
    profiled = task.observation_job(output, config, case, 'profiled')
    assert profiled['argv'][0] == '/frozen/msprof'
    assert profiled['argv'][1] == ('--output=/tmp/aprof-task-' + tmp_path.name +
                                   '-exp/observations/exp-observation-01/profile')
    assert profiled['argv'][2:-1] == task.FLAGS
    assert profiled['argv'][-1].startswith('--application=' + config['build']['binary'])
    assert profiled['environment']['APROF_SHARED_COMMANDS'] == str(tmp_path / 'commands.txt')
    assert profiled['environment']['APROF_SHARED_REPEAT'] == '100'
    unprofiled = task.observation_job(output.with_name('unprofiled'), config, case, 'unprofiled')
    assert unprofiled['argv'][0] == config['build']['binary']
    assert unprofiled['timeout_seconds'] == 120 and profiled['timeout_seconds'] == 600


def test_observation_rejects_replaced_or_nonprivate_scratch(tmp_path):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    scratch = tmp_path / 'scratch'; config['task_profile']['scratch_root'] = str(scratch)
    scratch.mkdir(mode=0o755)
    with pytest.raises(ValueError, match='scratch root'):
        task.checked_scratch_root(config)
    scratch.chmod(0o700)
    assert task.checked_scratch_root(config) == scratch
    real = tmp_path / 'real-scratch'; scratch.rename(real); scratch.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match='scratch root'):
        task.checked_scratch_root(config)


@pytest.mark.parametrize('bad', ['formal_role', 'cycle_cv', 'drift'])
def test_task_controls_reject_same_source_instability(bad):
    controls = {phase: {'role_bias': .01, 'baseline_cv': .01, 'candidate_cv': .01}
                for phase in ('aa_before', 'formal', 'aa_after')}
    controls['drift'] = {'baseline': .01, 'candidate': .01}
    task.check_controls(controls)
    if bad == 'formal_role': controls['formal']['role_bias'] = .02001
    elif bad == 'cycle_cv': controls['aa_after']['candidate_cv'] = .05001
    else: controls['drift']['baseline'] = .02001
    with pytest.raises(ValueError, match='Task A/A'):
        task.check_controls(controls)


def test_observation_failed_capture_keeps_receipt(tmp_path, monkeypatch):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    (tmp_path / 'scratch').mkdir(mode=0o700)
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    directory.parent.mkdir(parents=True)
    def fail(job):
        path = Path(job['output_dir']); path.mkdir()
        task.save_new(path / 'execution.json', {'job': job, 'exit_code': 9, 'actual_failure': True})
        return {'exit_code': 9}
    monkeypatch.setattr(task, 'job_run', fail)
    result = task.observation_mode(directory, config, config['cases'][0], 'profiled')
    assert result['status'] == 'failed' and result['verifications'] == {}
    assert result['execution'] == task.binding(directory / 'job/execution.json')
    assert task.read(directory / 'receipt.json') == result
    with pytest.raises(FileExistsError):
        task.observation_mode(directory, config, config['cases'][0], 'profiled')


def test_profiled_observation_rejects_preexisting_scratch_profile(tmp_path, monkeypatch):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    (tmp_path / 'scratch').mkdir(mode=0o700)
    directory = tmp_path / 'observations/exp-observation-01/profiled'; directory.parent.mkdir(parents=True)
    task.observation_profile_path(directory, config).mkdir(parents=True)
    monkeypatch.setattr(task, 'job_run', lambda job: pytest.fail('native capture must not start'))
    receipt = task.observation_mode(directory, config, config['cases'][0], 'profiled')
    assert receipt['status'] == 'failed' and 'not fresh' in receipt['error']['message']


def test_profiled_observation_transfers_local_tree_before_oracles(tmp_path, monkeypatch):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    (tmp_path / 'scratch').mkdir(mode=0o700)
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    directory.parent.mkdir(parents=True)
    jobs, calls = [], []

    def capture(job):
        jobs.append(job)
        output = Path(job['output_dir']); output.mkdir()
        task.save_new(output / 'execution.json', {'job': job, 'exit_code': 0})
        (output / 'stdout.log').write_text('native stdout')
        local = Path(job['argv'][1].removeprefix('--output='))
        table = local / 'PROF_01/mindstudio_profiler_output/op_summary.csv'
        table.parent.mkdir(parents=True); table.write_text('Task table')
        assert not (directory / 'profile').exists()
        return {'exit_code': 0}

    def transfer(source, destination, inventory, *, deadline):
        assert source == task.observation_profile_path(directory, config)
        assert destination == directory / 'profile' and deadline > time.monotonic()
        assert inventory == task.relative_profile_inventory(source)
        start = time.time(); shutil.copytree(source, destination); finish = time.time()
        actual = task.relative_profile_inventory(destination)
        return {'source_dir': str(source), 'destination_dir': str(destination),
                'started_at': start, 'finished_at': finish,
                'source_inventory': inventory, 'persisted_inventory': actual,
                'source_after_inventory': inventory}

    def verify(*args):
        assert (directory / 'profile/PROF_01/mindstudio_profiler_output/op_summary.csv').exists()
        calls.append(args[1])
        return {'status': 'passed'}

    monkeypatch.setattr(task, 'job_run', capture)
    monkeypatch.setattr(task, 'native_messages', lambda _: [])
    monkeypatch.setattr(task, 'timeline_protocol', lambda *args: None)
    monkeypatch.setattr(task, 'oracle', verify)
    monkeypatch.setattr(task, 'production_oracle', lambda *args: None)
    monkeypatch.setattr(task, 'check_controls', lambda *args: None)
    monkeypatch.setattr(task, 'task_modules', lambda: (SimpleNamespace(copy_profile_tree=transfer), None,
        lambda *args, **kwargs: {'values_ns_per_call': {}}, lambda values: {}))
    receipt = task.observation_mode(directory, config, config['cases'][0], 'profiled',
                                    deadline=time.monotonic() + 1200)
    assert receipt['status'] == 'passed' and receipt['profile_transfer'] == task.binding(directory / 'profile-transfer.json')
    assert jobs[0]['argv'][1] == '--output=' + str(task.observation_profile_path(directory, config))
    assert calls == ['baseline', 'candidate']


def test_failed_first_observation_stops_second_without_invented_execution(tmp_path, monkeypatch):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    (tmp_path / 'scratch').mkdir(mode=0o700)
    config_path = tmp_path / 'config.json'; task.save_new(config_path, config)
    monkeypatch.setattr(task, 'checked_plan', lambda _: ({'configs': {'exp': str(config_path)}}, {}))
    monkeypatch.setattr(task, 'locks', lambda _: nullcontext())
    called = []
    def fail(directory, *args, **kwargs):
        called.append(directory.name); directory.mkdir()
        result = {'status': 'failed'}; task.save_new(directory / 'receipt.json', result); return result
    monkeypatch.setattr(task, 'observation_mode', fail)
    with pytest.raises(ValueError, match='no retry'):
        task.observe(tmp_path, 'exp', 1)
    folder = tmp_path / 'observations/exp-observation-01'
    terminal = task.read(folder / 'terminal.json')
    assert called == ['unprofiled']
    assert terminal['modes']['profiled']['status'] == 'not_run'
    assert not (folder / 'profiled').exists()
    assert task.read(folder / 'profiled-not-run.json')['prerequisite'] == task.binding(folder / 'unprofiled/receipt.json')


@pytest.mark.parametrize('mutation', ['source_path', 'destination_path', 'missing_file', 'changed_hash', 'reversed_time'])
def test_observation_transfer_replay_rejects_broken_identity_or_time(tmp_path, mutation):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    profile = directory / 'profile'; profile.mkdir(parents=True)
    (profile / 'PROF_01').mkdir(); file = profile / 'PROF_01/op_summary.csv'; file.write_text('sample')
    files = task.relative_profile_inventory(profile)
    transfer = {'source_dir': str(task.observation_profile_path(directory, config)),
                'destination_dir': str(profile), 'started_at': 2.0, 'finished_at': 3.0,
                'source_inventory': files, 'persisted_inventory': files, 'source_after_inventory': files}
    if mutation == 'source_path': transfer['source_dir'] = '/tmp/unregistered/profile'
    elif mutation == 'destination_path': transfer['destination_dir'] = '/tmp/elsewhere'
    elif mutation == 'missing_file': transfer['source_inventory'] = {}
    elif mutation == 'changed_hash': transfer['persisted_inventory'] = {'PROF_01/op_summary.csv': 'sha256:' + '0' * 64}
    else: transfer['started_at'] = 0.5
    task.save_new(directory / 'profile-transfer.json', transfer)
    receipt = {'profile_transfer': task.binding(directory / 'profile-transfer.json'), 'finished_at': 4.0}
    if mutation == 'source_path':
        assert not Path(transfer['source_dir']).exists()  # Replay must use the frozen map, not live /tmp files.
    with pytest.raises(ValueError, match='transfer differs'):
        task.replay_profile_transfer(directory, config, receipt, 1.0, Evidence())


def test_observation_transfer_replay_uses_durable_copy_when_scratch_is_gone(tmp_path):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'absent-scratch')
    directory = tmp_path / 'observations/exp-observation-01/profiled'
    profile = directory / 'profile'; profile.mkdir(parents=True)
    (profile / 'PROF_01').mkdir(); (profile / 'PROF_01/op_summary.csv').write_text('sample')
    files = task.relative_profile_inventory(profile)
    task.save_new(directory / 'profile-transfer.json', {
        'source_dir': str(task.observation_profile_path(directory, config)),
        'destination_dir': str(profile), 'started_at': 2.0, 'finished_at': 3.0,
        'source_inventory': files, 'persisted_inventory': files, 'source_after_inventory': files})
    receipt = {'profile_transfer': task.binding(directory / 'profile-transfer.json'), 'finished_at': 4.0}
    assert task.replay_profile_transfer(directory, config, receipt, 1.0, Evidence()) == 3.0


def test_real_profile_copy_helper_replays_after_local_scratch_disappears(tmp_path):
    config = task.config_for(tmp_path, 'exp', Path('/frozen/msprof'))
    config['task_profile']['scratch_root'] = str(tmp_path / 'scratch')
    directory = tmp_path / 'observations/exp-observation-01/profiled'; directory.mkdir(parents=True)
    source = task.observation_profile_path(directory, config)
    sample = source / 'PROF_01/mindstudio_profiler_output/op_summary.csv'
    sample.parent.mkdir(parents=True); sample.write_bytes(b'exact task bytes')
    collector, _, _, _ = task.task_modules()
    transfer = collector.copy_profile_tree(source, directory / 'profile',
        task.relative_profile_inventory(source), deadline=time.monotonic() + 30)
    task.save_new(directory / 'profile-transfer.json', transfer)
    receipt = {'profile_transfer': task.binding(directory / 'profile-transfer.json'),
               'finished_at': transfer['finished_at'] + 1}
    shutil.rmtree(tmp_path / 'scratch')
    assert task.replay_profile_transfer(directory, config, receipt,
                                        transfer['started_at'] - 1, Evidence()) == transfer['finished_at']


def test_freeze_cannot_overwrite_expected_original_with_current_hash(tmp_path, monkeypatch):
    original = tmp_path / 'original'; original.write_bytes(b'frozen')
    expected = task.digest(original); original.write_bytes(b'changed')
    config_value = {'task_profile': {'scratch_root': str(tmp_path / 'scratch')}}
    config_path = tmp_path / 'config.json'; task.save_new(config_path, config_value)
    plan = {'operators': {}, 'budgets': task.BUDGETS, 'original_files': {str(original): expected},
            'history': task.binding(config_path), 'configs': {'exp': str(config_path)}, 'profiler': {'path': '/profiler'}}
    task.save_new(tmp_path / 'plan.json', plan)
    predecessor = tmp_path / 'prior'; predecessor.mkdir(); task.save_new(predecessor / 'plan.json', {'operators': {}})
    monkeypatch.setattr(task, 'PREDECESSOR', predecessor)
    monkeypatch.setattr(task, 'config_for', lambda *args: config_value)
    collector = SimpleNamespace(PROTOCOL=task.PROTOCOL, PROFILE_FLAGS=task.FLAGS, config_value=lambda x: x,
                                inventory=lambda x: {'files': {str(original): task.digest(original)}})
    monkeypatch.setattr(task, 'task_modules', lambda: (collector, None, None, None))
    with pytest.raises(ValueError, match='original native/input identity'):
        task.freeze(tmp_path)
    assert not (tmp_path / 'freeze.json').exists()


def test_frozen_candidate_payload_is_checked_before_hardware(tmp_path, monkeypatch):
    plan = {'purpose': task.PURPOSE, 'protocol': task.PROTOCOL, 'budgets': task.BUDGETS,
            'observations': task.OBSERVATIONS, 'max_attempts': 1, 'resampling': 'none',
            'frozen_files': {}, 'original_files': {}, 'configs': {}}
    task.save_new(tmp_path / 'plan.json', plan)
    candidate = tmp_path / 'candidate-inventory.json'
    task.save_new(candidate, {'schema_version': 1, 'root': str(task.RELEASE), 'files': {'one': 'old'}})
    task.save_new(tmp_path / 'freeze.json', {'plan': task.binding(tmp_path / 'plan.json'),
        'configs': {}, 'candidate_inventory': task.binding(candidate), 'frozen_files': {str(candidate): task.digest(candidate)}})
    monkeypatch.setattr(task, 'release_inventory', lambda: {'one': 'old'})
    task.checked_plan(tmp_path)
    monkeypatch.setattr(task, 'release_inventory', lambda: {'one': 'changed'})
    with pytest.raises(ValueError, match='candidate payload changed'):
        task.checked_plan(tmp_path)

from __future__ import annotations

import copy
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cannbench_device_timing as timing
import run_level1_serial as serial


LOCK_NAMES = ['host-serial.lock', *[f'device-{device}.lock' for device in range(16)]]


def occupied_locks(root):
    """Probe with independent process descriptors; never touch real device locks."""
    result = subprocess.run(
        [sys.executable, '-c', '''
import fcntl
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
occupied = []
for name in json.loads(sys.argv[2]):
    with (root / name).open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            occupied.append(name)
print(json.dumps(occupied))
''', str(root), json.dumps(LOCK_NAMES)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return json.loads(result.stdout)


def test_host_exclusive_blocks_every_legacy_device_and_releases_after_exception(tmp_path):
    with pytest.raises(RuntimeError, match='simulated controller failure'):
        with serial.exclusive_host(tmp_path):
            assert occupied_locks(tmp_path) == LOCK_NAMES
            raise RuntimeError('simulated controller failure')
    assert occupied_locks(tmp_path) == []
    with serial.exclusive_host(tmp_path):
        assert occupied_locks(tmp_path) == LOCK_NAMES
    assert occupied_locks(tmp_path) == []


@pytest.mark.parametrize('device', range(16))
def test_any_legacy_device_lock_blocks_serial_without_leaking_partial_locks(tmp_path, device):
    with timing.device_lock(device, lock_root=tmp_path):
        with pytest.raises(RuntimeError, match=f'device-{device}\\.lock is occupied'):
            with serial.exclusive_host(tmp_path):
                pytest.fail('serial execution entered while a legacy job held a chip')
        assert occupied_locks(tmp_path) == [f'device-{device}.lock']
    assert occupied_locks(tmp_path) == []


def control_report(*, baseline=100.0, candidate=100.0):
    return {
        'stable': True,
        'unit': 'ns',
        'case_ids': list(serial.CASES),
        'per_case': [
            {
                'case_id': case,
                'pair_count': 30,
                'baseline_samples_ns': [baseline] * 30,
                'candidate_samples_ns': [candidate] * 30,
                'baseline_median_ns': baseline,
                'candidate_median_ns': candidate,
                'baseline_cv': 0.0,
                'candidate_cv': 0.0,
                'speedup': baseline / candidate,
            }
            for case in serial.CASES
        ],
    }


def test_controls_accept_reproducible_low_cv_measurements():
    result = serial.compare_controls(control_report(), control_report(baseline=101, candidate=101))
    assert result['accepted']
    assert [row['case_id'] for row in result['per_case']] == serial.CASES
    assert all(row['passed'] for row in result['per_case'])


@pytest.mark.parametrize('biased_session', ['before', 'after'])
def test_controls_reject_low_cv_role_bias_in_either_session(biased_session):
    reports = {'before': control_report(), 'after': control_report()}
    reports[biased_session] = control_report(baseline=100, candidate=104)
    result = serial.compare_controls(reports['before'], reports['after'])
    assert not result['accepted']
    assert not result['per_case'][0]['passed']


def test_controls_reject_low_cv_session_drift_with_perfect_aa_balance():
    result = serial.compare_controls(control_report(), control_report(baseline=104, candidate=104))
    assert not result['accepted']
    assert result['per_case'][0]['shifts']['pooled'] > .02
    assert result['per_case'][0]['role_bias'] == [0.0, 0.0]


def test_controls_reject_role_drift_even_when_pooled_shift_and_aa_bias_pass():
    result = serial.compare_controls(
        control_report(baseline=100, candidate=101.9),
        control_report(baseline=103.8, candidate=101.9),
    )
    row = result['per_case'][0]
    assert row['shifts']['pooled'] < .02
    assert max(row['role_bias']) < .02
    assert row['shifts']['baseline'] > .02
    assert not result['accepted']


@pytest.mark.parametrize('missing_from', ['before', 'after', 'both'])
def test_controls_reject_missing_required_case(missing_from):
    reports = {'before': control_report(), 'after': control_report()}
    for label in ('before', 'after'):
        if missing_from in (label, 'both'):
            reports[label]['per_case'].pop()
            reports[label]['case_ids'].pop()
    assert not serial.compare_controls(reports['before'], reports['after'])['accepted']


def test_controls_reject_report_marked_unstable():
    before, after = control_report(), control_report()
    after['stable'] = False
    assert not serial.compare_controls(before, after)['accepted']


def test_controls_reject_missing_samples_without_raising():
    before, after = control_report(), control_report()
    after['stable'] = False
    row = after['per_case'][0]
    row.update(pair_count=0, baseline_samples_ns=[], candidate_samples_ns=[],
               baseline_median_ns=None, candidate_median_ns=None,
               baseline_cv=None, candidate_cv=None, speedup=None)
    assert not serial.compare_controls(before, after)['accepted']


def test_control_comparison_does_not_mutate_evidence():
    before, after = control_report(), control_report()
    snapshots = copy.deepcopy((before, after))
    serial.compare_controls(before, after)
    assert (before, after) == snapshots


def dump_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


@pytest.fixture
def continuation(tmp_path):
    """One operator, twenty tiny cases, and no real campaign or hardware paths."""
    parent, run = tmp_path / 'parent', tmp_path / 'continuation'
    prepared = parent / 'tasks/exp/prepared'
    entries = []
    for identifier in ('001', '002'):
        candidate_dir = parent / 'tasks/exp/candidates' / identifier
        baseline, candidate = parent / 'tasks/exp/baseline', candidate_dir / 'op'
        registration = {
            'candidate_id': f'exp-{identifier}',
            'source_hashes': {'baseline': 'sha256:baseline', 'candidate': f'sha256:{identifier}'},
        }
        registration_path = candidate_dir / 'registration.json'
        dump_json(registration_path, registration)
        for tree in (baseline, candidate):
            (tree / 'build').mkdir(parents=True, exist_ok=True)
            (tree / 'build/exp').write_bytes(b'non-executable fixture\n')
        entries.append({
            **registration, 'identifier': identifier,
            'prepared_root': str(prepared),
            'registration_path': str(registration_path),
            'registration_sha256': serial.sha(registration_path),
            'baseline': str(baseline), 'candidate': str(candidate),
            'baseline_executable_sha256': serial.sha(baseline / 'build/exp'),
            'candidate_executable_sha256': serial.sha(candidate / 'build/exp'),
        })
    roster_path = parent / 'tasks/exp/frozen-roster.json'
    dump_json(roster_path, {'candidates': [
        {key: entry[key] for key in ('candidate_id', 'source_hashes')} for entry in entries
    ]})
    for case in range(1, 21):
        directory = prepared / f'case_{case:02d}'
        directory.mkdir(parents=True)
        for name in ('input', 'golden'):
            (directory / f'{name}.bin').write_bytes(bytes([case]))
        dump_json(directory / 'metadata.json', {
            'case_id': case, 'input': str(directory / 'input.bin'),
            'golden': str(directory / 'golden.bin'),
        })
    dump_json(run / 'run-manifest.json', {
        'parent_run': str(parent), 'operators': ['exp'],
        'candidates': {'exp': entries}, 'physical_device': 0, 'cpu_affinity': [40],
    })
    producer = run / 'setup/cannbench_device_timing.py'
    producer.parent.mkdir(parents=True)
    producer.write_text('# A frozen dummy producer; it must never execute.\n')
    dump_json(run / 'setup/producers.json', {'cannbench_device_timing.py': serial.sha(producer)})
    return {'run': run, 'parent': parent, 'prepared': prepared, 'roster': roster_path}


def test_seal_inputs_binds_all_cases_and_golden_without_modifying_parent(continuation):
    parent, run = continuation['parent'], continuation['run']
    before = {str(path.relative_to(parent)): path.read_bytes() for path in parent.rglob('*') if path.is_file()}
    serial.seal_inputs(run)
    binding = serial.read(run / 'setup/input-bindings.json')
    cases = binding['inputs']['exp']
    assert set(cases) == {str(case) for case in range(1, 21)}
    for case, files in cases.items():
        directory = continuation['prepared'] / f'case_{int(case):02d}'
        assert set(files) == {str(directory / name) for name in ('metadata.json', 'input.bin', 'golden.bin')}
        assert all(serial.sha(path) == digest for path, digest in files.items())
    assert binding['parent_rosters']['exp'] == {
        'path': str(continuation['roster']), 'sha256': serial.sha(continuation['roster']),
    }
    after = {str(path.relative_to(parent)): path.read_bytes() for path in parent.rglob('*') if path.is_file()}
    assert after == before


@pytest.mark.parametrize('missing', ['metadata.json', 'input.bin', 'golden.bin'])
def test_seal_inputs_rejects_missing_metadata_input_or_oracle(continuation, missing):
    (continuation['prepared'] / 'case_20' / missing).unlink()
    with pytest.raises(FileNotFoundError):
        serial.seal_inputs(continuation['run'])
    assert not (continuation['run'] / 'setup/input-bindings.json').exists()
    assert not (continuation['run'] / 'setup/active-controller.json').exists()


@pytest.mark.parametrize('mismatch', ['missing_candidate', 'extra_candidate', 'source_identity'])
def test_seal_inputs_rejects_parent_roster_mismatch(continuation, mismatch):
    roster = serial.read(continuation['roster'])
    if mismatch == 'missing_candidate':
        roster['candidates'].pop()
    elif mismatch == 'extra_candidate':
        extra = copy.deepcopy(roster['candidates'][0])
        extra['candidate_id'] = 'exp-003'
        roster['candidates'].append(extra)
    else:
        roster['candidates'][0]['source_hashes']['candidate'] = 'sha256:changed'
    dump_json(continuation['roster'], roster)
    with pytest.raises(ValueError, match='differs from frozen parent'):
        serial.seal_inputs(continuation['run'])
    assert not (continuation['run'] / 'setup/input-bindings.json').exists()


def test_measure_preserves_failed_archive_status_without_executing_or_promoting_report(continuation, monkeypatch):
    run = continuation['run']
    serial.seal_inputs(run)
    relative = Path('tasks/exp/measurements/001')
    execution = {'status': 'failed', 'exit_status': 17, 'reason': 'verification failed'}
    dump_json(run / relative / 'execution.json', execution)
    dump_json(run / relative / 'measurement_report.json', {'stable': True, 'performance_eligible': True})

    def forbidden(*args, **kwargs):
        pytest.fail('a failed immutable archive must not be rerun or treated as passing evidence')

    monkeypatch.setattr(serial.subprocess, 'Popen', forbidden)
    monkeypatch.setattr(serial, 'summarize_multicase', forbidden)
    assert serial.measure(run, 'exp', '001', relative, list(range(1, 21))) == execution
    assert serial.read(run / relative / 'execution.json') == execution


@pytest.mark.parametrize('changed', ['metadata.json', 'input.bin', 'golden.bin', 'registration', 'producer'])
def test_measure_rechecks_frozen_inputs_and_producers_before_archive_reuse(continuation, monkeypatch, changed):
    run = continuation['run']
    serial.seal_inputs(run)
    relative = Path('tasks/exp/measurements/001')
    dump_json(run / relative / 'execution.json', {'status': 'failed', 'exit_status': 17})
    entry = serial.read(run / 'run-manifest.json')['candidates']['exp'][0]
    if changed == 'registration':
        target = Path(entry['registration_path'])
    elif changed == 'producer':
        target = run / 'setup/cannbench_device_timing.py'
    else:
        target = continuation['prepared'] / 'case_20' / changed
    target.write_bytes(target.read_bytes() + b'changed')
    monkeypatch.setattr(serial.subprocess, 'Popen', lambda *a, **kw: pytest.fail('hardware must not start'))
    with pytest.raises(ValueError, match='frozen'):
        serial.measure(run, 'exp', '001', relative, list(range(1, 21)))


def test_measure_interrupt_reaps_and_archives_before_host_locks_release(continuation, monkeypatch, tmp_path):
    run = continuation['run']
    serial.seal_inputs(run)
    lock_root = tmp_path / 'locks'
    local_scratch = tmp_path / 'scratch'
    relative = Path('tasks/exp/measurements/001')
    events = []

    def assert_locks_held():
        for name in LOCK_NAMES:
            with (lock_root / name).open('a+') as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

    class InterruptedChild:
        pid = 999999
        returncode = None

        def __init__(self, *args, **kwargs):
            assert kwargs['start_new_session']

        def wait(self, timeout=None):
            assert_locks_held()
            if not events:
                events.append('interrupted')
                raise KeyboardInterrupt('simulated SIGTERM handler')
            events.append('reaped')
            self.returncode = -signal.SIGTERM
            return self.returncode

    def killpg(pid, sig):
        assert pid == InterruptedChild.pid and sig == signal.SIGTERM
        assert_locks_held()
        events.append('terminated')

    copytree = serial.shutil.copytree

    def archive(source, destination, *args, **kwargs):
        assert_locks_held()
        events.append('archived')
        return copytree(source, destination, *args, **kwargs)

    monkeypatch.setattr(serial, 'Path', lambda *parts: local_scratch if parts == ('/tmp/aprof-serial',) else Path(*parts))
    monkeypatch.setattr(serial.subprocess, 'Popen', InterruptedChild)
    monkeypatch.setattr(serial.os, 'killpg', killpg)
    monkeypatch.setattr(serial.shutil, 'copytree', archive)
    with pytest.raises(KeyboardInterrupt, match='simulated SIGTERM handler'):
        with serial.exclusive_host(lock_root):
            serial.measure(run, 'exp', '001', relative, list(range(1, 21)))
    assert events == ['interrupted', 'terminated', 'reaped', 'archived']
    execution = serial.read(run / relative / 'execution.json')
    assert execution['status'] == 'failed'
    assert execution['exit_status'] == -signal.SIGTERM
    for name in LOCK_NAMES:
        with (lock_root / name).open('a+') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

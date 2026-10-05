"""CPU-only observer tests: no collector, exporter, or device work is launched."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import watch_level1_serial_export as observer_module


def put_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def proc_stat(root, pid, *, state='S', start_ticks=12345):
    directory = root / str(pid)
    directory.mkdir(parents=True, exist_ok=True)
    # Fields 3 through 22; the comm field may itself contain ')' and spaces.
    fields = [state, *(['0'] * 18), str(start_ticks)]
    (directory / 'stat').write_text(f'{pid} (python (worker) ) {" ".join(fields)}\n')


@pytest.mark.parametrize('state', ['R', 'S', 'D'])
def test_process_identity_uses_kernel_start_tick_and_parses_complex_comm(tmp_path, state):
    proc_stat(tmp_path, 321, state=state, start_ticks=987654321)
    assert observer_module.process_identity(321, tmp_path) == {
        'pid': 321, 'start_ticks': 987654321,
    }


def test_process_identity_rejects_zombie_and_missing_process(tmp_path):
    proc_stat(tmp_path, 321, state='Z')
    assert observer_module.process_identity(321, tmp_path) is None
    assert observer_module.process_identity(654, tmp_path) is None


@pytest.fixture
def environment(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    scripts = project / 'scripts'
    scripts.mkdir(parents=True)
    for name in (
        'finalize_level1_serial.py', 'finalize_level1_campaign.py',
        'cannbench_device_timing.py', 'run_level1_serial.py',
        'collect_level1_traces.py', 'prepare_trace_pilot.py', 'run_aprof_job.py',
    ):
        (scripts / name).write_text('# inert CPU-test producer\n')
    runtime = project / 'src/aprof_runtime/nested'
    runtime.mkdir(parents=True)
    (runtime / 'helper.py').write_text('# inert transitive runtime producer\n')
    run = tmp_path / 'run'
    operators = [f'op{index}' for index in range(7)]
    put_json(run / 'run-manifest.json', {'operators': operators})
    current_identity = [{'pid': 321, 'start_ticks': 12345}]
    monkeypatch.setattr(observer_module, 'ROOT', project)
    monkeypatch.setattr(observer_module, 'process_identity', lambda pid: current_identity[0])
    affinity = []
    monkeypatch.setattr(observer_module.os, 'sched_setaffinity', lambda pid, cpus: affinity.append((pid, cpus)))
    # An unmocked command is always an error, never an actual exporter launch.
    def forbidden_subprocess(*args, **kwargs):
        pytest.fail('test attempted to launch an unmocked subprocess')
    monkeypatch.setattr(observer_module.subprocess, 'run', forbidden_subprocess)
    monkeypatch.setattr(observer_module.subprocess, 'Popen', forbidden_subprocess)
    instance = observer_module.ExportObserver(run, 321, cpu=40)
    states = []
    original_state = instance.state
    def record_state(status, closed, **extra):
        states.append(status)
        original_state(status, closed, **extra)
    monkeypatch.setattr(instance, 'state', record_state)
    calls = []
    failures = {}
    original_command = instance.command
    def record_command(flags):
        calls.append(list(flags))
        if tuple(flags) in failures:
            raise failures[tuple(flags)]
    monkeypatch.setattr(instance, 'command', record_command)
    return SimpleNamespace(
        project=project, run=run, operators=operators, observer=instance,
        current_identity=current_identity, affinity=affinity, states=states,
        calls=calls, failures=failures, original_command=original_command,
    )


def close_operator(environment, index, *, accepted=True, health=True):
    task = environment.run / 'tasks' / environment.operators[index]
    put_json(task / 'calibration-decision.json', {'accepted': accepted})
    if health:
        put_json(task / 'health-after.json', {
            'exit_status': 0, 'finished_at': '2026-09-08T01:15:00Z',
        })
    return task


def final_state(environment):
    return observer_module.read(environment.observer.directory / 'state.json')


def test_alive_rejects_pid_reuse_and_zombie_and_cannot_attach_after_missing_start(environment):
    instance = environment.observer
    assert instance.alive()
    environment.current_identity[0] = {'pid': 321, 'start_ticks': 12346}
    assert not instance.alive()
    environment.current_identity[0] = None
    assert not instance.alive()
    missing = observer_module.ExportObserver(environment.run, 321)
    environment.current_identity[0] = {'pid': 321, 'start_ticks': 99999}
    assert not missing.alive()


def test_decision_before_health_is_pending_then_closed(environment):
    task = close_operator(environment, 0, health=False)
    assert observer_module.closed_operators(environment.run, environment.operators) == []
    put_json(task / 'health-after.json', {'exit_status': 0, 'finished_at': 'finished'})
    assert observer_module.closed_operators(environment.run, environment.operators) == ['op0']


@pytest.mark.parametrize('health', [
    {}, {'exit_status': 0}, {'exit_status': None, 'finished_at': 'finished'},
    {'exit_status': True, 'finished_at': 'finished'},
    {'exit_status': '0', 'finished_at': 'finished'},
    {'exit_status': 0, 'finished_at': ''},
])
def test_incomplete_health_never_closes_operator(environment, health):
    task = close_operator(environment, 0, health=False)
    put_json(task / 'health-after.json', health)
    assert observer_module.closed_operators(environment.run, environment.operators) == []


def test_rejected_calibration_is_terminal_but_exporter_still_gates_health(environment):
    task = close_operator(environment, 0, accepted=False)
    # Closure is only a notification; nonzero health is checked by the exporter.
    put_json(task / 'health-after.json', {'exit_status': 1, 'finished_at': 'finished'})
    assert observer_module.closed_operators(environment.run, environment.operators) == ['op0']


@pytest.mark.parametrize('accepted', [None, 0, 1, 'false'])
def test_calibration_requires_explicit_boolean_status(environment, accepted):
    close_operator(environment, 0, accepted=accepted)
    with pytest.raises(ValueError, match='invalid terminal calibration decision'):
        observer_module.closed_operators(environment.run, environment.operators)


def test_zero_closed_exports_once_and_polling_does_not_repeat(environment):
    previous, done = environment.observer.step(None)
    assert (previous, done) == ((), False)
    assert environment.calls == [['--ready-only']]
    for _ in range(3):
        previous, done = environment.observer.step(previous)
        assert not done
    assert environment.calls == [['--ready-only']]
    assert final_state(environment)['status'] == 'waiting_for_operator_closure'


def test_each_new_closure_exports_once_then_seventh_runs_full_and_verifies(environment):
    previous, _ = environment.observer.step(None)
    for index in range(6):
        close_operator(environment, index, accepted=index % 2 == 0)
        previous, done = environment.observer.step(previous)
        assert not done
        assert previous == tuple(environment.operators[:index + 1])
        environment.observer.step(previous)
        assert environment.calls == [['--ready-only']] * (index + 2)
    close_operator(environment, 6)
    previous, done = environment.observer.step(previous)
    assert done and previous == tuple(environment.operators)
    assert environment.calls == [['--ready-only']] * 7 + [[], ['--verify-only']]
    state = final_state(environment)
    assert state['status'] == 'complete'
    assert state['pending_operators'] == []
    assert state['hardware_commands_launched'] == 0


def test_dead_collector_with_pending_health_never_synthesizes_completion(environment):
    close_operator(environment, 0)
    unfinished = close_operator(environment, 1, health=False)
    environment.current_identity[0] = None
    before = {str(path.relative_to(environment.run)): path.read_bytes()
              for path in (environment.run / 'tasks').rglob('*') if path.is_file()}
    previous, done = environment.observer.step(None)
    assert done and previous == ('op0',)
    assert environment.calls == [['--ready-only']]
    state = final_state(environment)
    assert state['status'] == 'collector_stopped_with_pending_operators'
    assert state['pending_operators'] == environment.operators[1:]
    assert 'complete' not in environment.states
    assert not (unfinished / 'health-after.json').exists()
    after = {str(path.relative_to(environment.run)): path.read_bytes()
             for path in (environment.run / 'tasks').rglob('*') if path.is_file()}
    assert before == after


@pytest.mark.parametrize('failure_flags, expected_calls', [
    ((), [[]]), (('--verify-only',), [[], ['--verify-only']]),
])
def test_full_export_or_verification_failure_is_not_complete_and_releases_lock(
    environment, failure_flags, expected_calls,
):
    for index in range(7):
        close_operator(environment, index)
    environment.failures[failure_flags] = RuntimeError('simulated exporter failure')
    with pytest.raises(RuntimeError, match='simulated exporter failure'):
        environment.observer.watch(interval=1)
    assert environment.calls == expected_calls
    assert environment.affinity == [(0, {40})]
    assert final_state(environment)['status'] == 'export_observer_failed'
    assert 'complete' not in environment.states
    with (environment.observer.directory / 'observer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_second_observer_cannot_export_while_first_holds_lock(environment):
    path = environment.observer.directory / 'observer.lock'
    with path.open('a+') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            environment.observer.watch(interval=1)
        assert environment.calls == []
        assert not (environment.observer.directory / 'state.json').exists()
        assert list(environment.observer.directory.glob('producer-*.json')) == []


@pytest.mark.parametrize('relative', [
    'scripts/finalize_level1_serial.py', 'scripts/collect_level1_traces.py',
    'scripts/prepare_trace_pilot.py', 'scripts/run_aprof_job.py',
    'src/aprof_runtime/nested/helper.py',
])
def test_changed_direct_or_transitive_producer_is_rejected_before_launch(environment, relative):
    path = environment.project / relative
    assert str(path) in environment.observer.sources
    path.write_text('# changed after observer start\n')
    with pytest.raises(ValueError, match='export producer changed'):
        environment.original_command(['--ready-only'])
    assert not list(environment.observer.directory.glob('command-*'))


def test_deleted_producer_is_rejected_before_launch(environment):
    (environment.project / 'scripts/finalize_level1_serial.py').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        environment.original_command(['--ready-only'])
    assert not list(environment.observer.directory.glob('command-*'))


def fake_exporter(environment, monkeypatch, *, exit_status=0, mutation=None):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv[:4] == [sys.executable, str(environment.observer.exporter), '--run', str(environment.run)]
        assert kwargs['cwd'] == environment.project
        assert kwargs['check'] is False
        kwargs['stdout'].write('fixture exporter output\n')
        kwargs['stderr'].write('fixture diagnostic\n')
        if mutation:
            mutation()
        return SimpleNamespace(returncode=exit_status)
    monkeypatch.setattr(observer_module.subprocess, 'run', run)
    return calls


def command_execution(environment):
    paths = list(environment.observer.directory.glob('command-*/execution.json'))
    assert len(paths) == 1
    return observer_module.read(paths[0])


def test_command_records_exit_and_log_hashes_and_inherits_lock(environment, monkeypatch):
    calls = fake_exporter(environment, monkeypatch)
    with (environment.observer.directory / 'observer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        environment.observer.lock_fd = lock.fileno()
        environment.original_command(['--ready-only'])
        assert calls[0][1]['pass_fds'] == (lock.fileno(),)
        assert calls[0][1]['start_new_session'] is True
    execution = command_execution(environment)
    assert execution['argv'][-1] == '--ready-only'
    assert execution['cpu'] == 40
    assert execution['exit_status'] == 0
    assert execution['finished_at']
    assert execution['producer_changed_during_execution'] == []
    assert execution['source_hashes'] == environment.observer.sources
    for stream in ('stdout', 'stderr'):
        assert execution[stream]['sha256'] == observer_module.digest(execution[stream]['path'])


def test_failed_command_retains_execution_and_logs(environment, monkeypatch):
    fake_exporter(environment, monkeypatch, exit_status=7)
    with pytest.raises(RuntimeError, match='export failed with exit 7'):
        environment.original_command(['--ready-only'])
    execution = command_execution(environment)
    assert execution['exit_status'] == 7
    assert execution['finished_at']
    assert Path(execution['stderr']['path']).read_text() == 'fixture diagnostic\n'


@pytest.mark.parametrize('delete', [False, True])
def test_producer_change_during_successful_export_fails_and_is_recorded(environment, monkeypatch, delete):
    path = environment.project / 'scripts/prepare_trace_pilot.py'
    def mutation():
        if delete:
            path.unlink()
        else:
            path.write_text('# mutated while exporter was executing\n')
    fake_exporter(environment, monkeypatch, mutation=mutation)
    monkeypatch.setattr(environment.observer, 'command', environment.original_command)
    for index in range(7):
        close_operator(environment, index)
    with pytest.raises(ValueError, match='producer changed during execution'):
        environment.observer.watch(interval=1)
    assert final_state(environment)['status'] == 'export_observer_failed'
    assert 'complete' not in environment.states
    execution = command_execution(environment)
    assert execution['exit_status'] == 0
    assert execution['producer_changed_during_execution'] == [str(path)]


def wait_until(predicate, *, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail('CPU fixture did not reach expected state before timeout')


def test_exporter_inherited_lock_survives_parent_sigkill_until_child_exits(tmp_path):
    """Launch only an inert temporary Python exporter, never the real observer CLI."""
    project = tmp_path / 'project'
    scripts = project / 'scripts'
    scripts.mkdir(parents=True)
    run = tmp_path / 'run'
    put_json(run / 'run-manifest.json', {'operators': ['fixture']})
    (scripts / 'finalize_level1_serial.py').write_text('''
import os
from pathlib import Path
import sys
import time
run = Path(sys.argv[sys.argv.index('--run') + 1])
(run / 'child-started').write_text(str(os.getpid()))
deadline = time.monotonic() + 10
while not (run / 'release-child').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('CPU fixture timed out waiting for release')
    time.sleep(0.01)
''')
    parent_code = '''
import fcntl
import os
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import watch_level1_serial_export as module
module.ROOT = Path(sys.argv[2])
observer = module.ExportObserver(Path(sys.argv[3]), os.getpid(), cpu=40)
with (observer.directory / 'observer.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    observer.lock_fd = lock.fileno()
    observer.command(['--ready-only'])
'''
    child_identity = None
    parent = subprocess.Popen(
        [sys.executable, '-c', parent_code, str(ROOT / 'scripts'), str(project), str(run)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        wait_until(lambda: (run / 'child-started').exists())
        child_pid = int((run / 'child-started').read_text())
        child_identity = observer_module.process_identity(child_pid)
        assert child_identity is not None
        with (run / 'export-observer/observer.lock').open('a+') as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            parent.kill()
            assert parent.wait(timeout=5) == -signal.SIGKILL
            assert observer_module.process_identity(child_pid) == child_identity
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (run / 'release-child').write_text('release inert CPU fixture\n')
            def acquired_after_child_exit():
                try:
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except BlockingIOError:
                    return False
            wait_until(acquired_after_child_exit)
    finally:
        (run / 'release-child').write_text('cleanup\n')
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if child_identity and observer_module.process_identity(child_identity['pid']) == child_identity:
            os.kill(child_identity['pid'], signal.SIGKILL)

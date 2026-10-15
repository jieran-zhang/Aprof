"""Real Linux process cleanup; no devices or profiling programs are invoked."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'collection/scripts/run_aprof_job.py'
spec = importlib.util.spec_from_file_location('job_cleanup_test', SCRIPT)
job_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job_runner)

TREE = r'''
import json,os,signal,subprocess,sys,time
from pathlib import Path
role,mode,log=sys.argv[1:]
def note(**extra):
 fd=os.open(log,os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
 os.write(fd,(json.dumps(dict(pid=os.getpid(),role=role,**extra))+'\n').encode());os.close(fd)
note()
if role=='leaf':
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
else:
 subprocess.Popen([sys.executable,__file__,'branch' if role=='root' else 'leaf',mode,log],start_new_session=True)
 if role=='branch' and mode=='doublefork': os._exit(0)
 if role=='root':
  while not any(json.loads(line)['role']=='leaf' for line in Path(log).read_text().splitlines()): time.sleep(.01)
  for index in range(20): print('APROF_SHARED_TIMING_JSON:'+json.dumps({'index':index}),flush=True)
  note(ready=True)
  if mode=='normal_exit': sys.exit(0)
while True: time.sleep(.1)
'''


def plan(tmp_path, *, mode='sleep', timeout=2):
    tree = tmp_path / 'tree.py'; tree.write_text(TREE)
    return {'job_id': 'cpu-cleanup', 'argv': [sys.executable, str(tree), 'root', mode, str(tmp_path / 'pids.jsonl')],
            'cwd': str(tmp_path), 'output_dir': str(tmp_path / 'job'), 'timeout_seconds': timeout,
            'environment': {'APROF_CLEANUP_TEST': 'unchanged'}}


def ready(tmp_path):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        path = tmp_path / 'pids.jsonl'
        if path.exists() and any(row.get('ready') for row in map(json.loads, path.read_text().splitlines())):
            return
        time.sleep(.02)
    raise AssertionError('nested process fixture did not start')


def gone(tmp_path):
    rows = [json.loads(line) for line in (tmp_path / 'pids.jsonl').read_text().splitlines()]
    assert {row['role'] for row in rows} == {'root', 'branch', 'leaf'}
    assert all(not Path(f"/proc/{row['pid']}").exists() for row in rows)


@pytest.fixture(autouse=True)
def emergency_cleanup(tmp_path):
    yield
    path = tmp_path / 'pids.jsonl'
    if path.exists():
        for row in map(json.loads, path.read_text().splitlines()):
            try: os.kill(row['pid'], signal.SIGKILL)
            except ProcessLookupError: pass


@pytest.mark.parametrize('mode', ['sleep', 'doublefork'])
def test_timeout_reaps_nested_detached_children_and_preserves_logs(tmp_path, mode):
    job = plan(tmp_path, mode=mode)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        result = job_runner.run(job)
        assert result['status'] == 'timeout' and result['exit_code'] != 0
        assert result['job'] == job
        assert unrelated.poll() is None
        assert len([line for line in Path(result['stdout']['path']).read_text().splitlines()
                    if line.startswith('APROF_SHARED_TIMING_JSON:')]) == 20
        gone(tmp_path)
    finally:
        unrelated.terminate(); unrelated.wait()


def test_outer_sigterm_saves_failure_then_reaps_detached_children(tmp_path):
    job = plan(tmp_path, mode='doublefork', timeout=30)
    config = tmp_path / 'job.json'; config.write_text(json.dumps(job))
    process = subprocess.Popen([sys.executable, str(SCRIPT), '--job', str(config)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        ready(tmp_path); process.send_signal(signal.SIGTERM)
        process.communicate(timeout=10)
        assert process.returncode != 0
        receipt = json.loads((tmp_path / 'job/execution.json').read_text())
        assert receipt['status'] == 'failed' and receipt['error']['type'] == 'SystemExit'
        gone(tmp_path)
    finally:
        if process.poll() is None: process.kill(); process.wait()


def test_wait_exception_also_cleans_tree_and_records_failure(tmp_path, monkeypatch):
    job = plan(tmp_path, timeout=30)
    wait = subprocess.Popen.wait
    injected = False
    def broken_wait(process, timeout=None):
        nonlocal injected
        if not injected and timeout == 30:
            ready(tmp_path); injected = True
            raise RuntimeError('injected parent wait failure')
        return wait(process, timeout=timeout)
    monkeypatch.setattr(subprocess.Popen, 'wait', broken_wait)
    with pytest.raises(RuntimeError, match='injected parent wait failure'):
        job_runner.run(job)
    receipt = json.loads((tmp_path / 'job/execution.json').read_text())
    assert receipt['status'] == 'failed' and receipt['error']['type'] == 'RuntimeError'
    gone(tmp_path)


def test_successful_root_exit_reaps_leftover_children(tmp_path):
    result = job_runner.run(plan(tmp_path, mode='normal_exit', timeout=10))
    assert result['status'] == 'passed' and result['exit_code'] == 0 and 'error' not in result
    gone(tmp_path)


def test_normal_job_preserves_argv_environment_and_stdout(tmp_path):
    code = 'import json,os,sys; print(json.dumps([sys.argv[1:],os.environ["APROF_CLEANUP_TEST"]]))'
    job = {'job_id': 'normal', 'argv': [sys.executable, '-c', code, 'literal argument'],
           'cwd': str(tmp_path), 'output_dir': str(tmp_path / 'job'), 'timeout_seconds': 5,
           'environment': {'APROF_CLEANUP_TEST': 'unchanged'}}
    result = job_runner.run(job)
    assert result['status'] == 'passed' and result['exit_code'] == 0 and result['job'] == job
    assert json.loads(Path(result['stdout']['path']).read_text()) == [['literal argument'], 'unchanged']
    assert set(result) == {'schema_version', 'kind', 'job', 'host', 'physical_device', 'started_at',
                          'finished_at', 'duration_seconds', 'exit_code', 'status', 'stdout', 'stderr'}


def test_absolute_deadline_caps_relative_timeout_and_reaps_children(tmp_path):
    job = plan(tmp_path, mode='doublefork', timeout=30)
    job['deadline_monotonic'] = time.monotonic() + 2
    result = job_runner.run(job)
    assert result['status'] == 'timeout' and result['process_started'] is True
    assert result['duration_seconds'] < 6  # Includes the existing TERM/KILL cleanup.
    gone(tmp_path)


@pytest.mark.parametrize('deadline', [None, True, float('nan'), float('inf'), '3600'])
def test_absolute_deadline_must_be_a_finite_clock(tmp_path, deadline):
    job = plan(tmp_path); job['deadline_monotonic'] = deadline
    with pytest.raises(ValueError, match='finite clock'):
        job_runner.run(job)
    assert not (tmp_path / 'pids.jsonl').exists()

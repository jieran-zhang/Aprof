"""Real unchanged Python main() calls, with no device/native execution."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import msprof_exploration_oracle as oracle


SOURCE = '''import argparse, json
from pathlib import Path

def main():
    import os, time
    p = argparse.ArgumentParser()
    p.add_argument('--metadata', required=True)
    a = p.parse_args()
    metadata = json.loads(Path(a.metadata).read_text())
    proof = Path(metadata['proof'])
    count = int(proof.read_text()) if proof.exists() else 0
    proof.write_text(str(count + 1))
    print('original complete main invocation', count + 1, flush=True)
    if metadata.get('sleep'):
        time.sleep(metadata['sleep'])
    if metadata.get('raise'):
        raise ValueError('original oracle exception')
    if metadata.get('mutate_oracle'):
        Path(__file__).write_text('changed source')
    if metadata.get('check_env'):
        assert os.environ['ORACLE_FIXTURE'] == metadata['check_env']
    result = {'passed': not metadata.get('exit'), 'argv_metadata': a.metadata, 'cwd': str(Path.cwd())}
    Path(metadata['result']).write_text(json.dumps(result))
    if metadata.get('exit'):
        raise SystemExit(metadata['exit'])

if __name__ == '__main__': main()
'''


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path / "baseline/scripts/verify_result.py"
    path.parent.mkdir(parents=True)
    path.write_text(SOURCE)
    metadata = tmp_path / "metadata.json"
    data = {"proof": str(tmp_path / "proof.txt"), "result": str(tmp_path / "result.json")}
    metadata.write_text(json.dumps(data))
    delegated = []
    def delegate(*args, **kwargs):
        delegated.append((args, kwargs))
        return "delegated"
    runner = oracle.make_run_logged(delegate, verifier=path, expected_hash=oracle.sha(path), metadata_root=tmp_path)
    return path, metadata, data, runner, delegated


def invoke(fixture, name="call", **kwargs):
    path, metadata, _, runner, _ = fixture
    return runner([sys.executable, "-B", str(path), "--metadata", str(metadata)], metadata.parent / name,
                  kwargs.pop("env", dict(os.environ)), kwargs.pop("timeout", 3), cwd=metadata.parent, **kwargs)


def record(fixture, name="call"):
    return json.loads((fixture[1].parent / (name + ".execution.json")).read_text())


def change_metadata(fixture, **changes):
    fixture[1].write_text(json.dumps({**fixture[2], **changes}))


def test_exact_full_main_reused_with_original_bytes_and_true_zero_processes(fixture):
    original = fixture[0].read_bytes()
    previous_argv, previous_cwd = sys.argv, Path.cwd()
    first = invoke(fixture, "first")
    module = fixture[3].verifier
    second = invoke(fixture, "second")
    assert fixture[3].verifier is module
    assert first.returncode == second.returncode == 0
    assert Path(fixture[2]["proof"]).read_text() == "2"
    assert "original complete main invocation 2" in second.stdout
    assert fixture[0].read_bytes() == original
    assert sys.argv is previous_argv and Path.cwd() == previous_cwd
    assert not fixture[4]
    assert not list(fixture[0].parent.rglob("__pycache__"))
    for name in ("first", "second"):
        row = record(fixture, name)
        assert row["verifier_calls"] == 1 and row["verifier_processes_started"] == 0
        assert row["new_process_started"] is False and row["mode"] == oracle.MODE
        assert row["started_at"] <= row["ended_at"] and row["exit_code"] == 0
        assert row["verifier"]["sha256"] == oracle.sha(fixture[0])
        assert row["argv"][1] == "-B"
    assert record(fixture, "second")["module_reused"] is True


@pytest.mark.parametrize("data,exception,exit_code", [({"exit": 7}, RuntimeError, 7), ({"raise": True}, ValueError, 1)])
def test_main_failures_keep_original_stdout_and_truthful_exit(fixture, data, exception, exit_code):
    change_metadata(fixture, **data)
    with pytest.raises(exception):
        invoke(fixture)
    row = record(fixture)
    assert row["status"] == "failed" and row["exit_code"] == exit_code
    assert row["verifier_calls"] == 1 and row["new_process_started"] is False
    assert "original complete main" in (fixture[1].parent / "call.stdout.log").read_text()
    assert row["error"]
    assert fixture[0].read_text() == SOURCE


def test_timeout_preserves_partial_log_restores_state_and_disables_scope(fixture):
    change_metadata(fixture, sleep=0.3)
    handler, cwd, argv = signal.getsignal(signal.SIGALRM), Path.cwd(), sys.argv
    with pytest.raises(subprocess.TimeoutExpired):
        invoke(fixture, timeout=0.02)
    row = record(fixture)
    assert row["timed_out"] is True and row["exit_code"] is None
    assert row["status"] == "failed" and row["verifier_calls"] == 1
    assert "original complete main" in (fixture[1].parent / "call.stdout.log").read_text()
    assert signal.getsignal(signal.SIGALRM) == handler and not any(signal.getitimer(signal.ITIMER_REAL))
    assert sys.argv is argv and Path.cwd() == cwd
    with pytest.raises(RuntimeError, match="disabled"):
        invoke(fixture, "after-timeout")
    assert record(fixture, "after-timeout")["verifier_calls"] == 0


def test_hash_checked_before_every_call_and_after_main(fixture):
    invoke(fixture, "first")
    fixture[0].write_text("changed source")
    with pytest.raises(ValueError, match="hash differs"):
        invoke(fixture, "changed")
    assert record(fixture, "changed")["verifier_calls"] == 0
    assert Path(fixture[2]["proof"]).read_text() == "1"


def test_source_change_inside_oracle_cannot_be_success(fixture):
    change_metadata(fixture, mutate_oracle=True)
    with pytest.raises(ValueError, match="changed during"):
        invoke(fixture)
    assert record(fixture)["status"] == "failed"


def test_environment_and_affinity_are_scoped_and_restored(fixture):
    before, affinity = dict(os.environ), os.sched_getaffinity(0)
    fixture[3].cpu_affinity = {min(affinity)}
    change_metadata(fixture, check_env="set-for-oracle")
    invoke(fixture, env={**os.environ, "ORACLE_FIXTURE": "set-for-oracle"})
    assert dict(os.environ) == before and os.sched_getaffinity(0) == affinity
    assert record(fixture)["actual_cpu_affinity"] == [min(affinity)]


@pytest.mark.parametrize("argv", [["native", "--metadata", "ignored"], [sys.executable, "-c", "print(1)"],
                                  [sys.executable, "foreign.py", "--metadata", "ignored"]])
def test_nonoracle_native_and_other_python_commands_pass_through_unchanged(fixture, argv):
    env, out = {"X": "original"}, fixture[1].parent / "unused"
    assert fixture[3](argv, out, env, 20, cwd=fixture[1].parent) == "delegated"
    args, kwargs = fixture[4][0]
    assert args[0] is argv and args[1] is out and args[2] is env
    assert args[3] == 20 and kwargs == {"cwd": fixture[1].parent}
    assert not list(fixture[1].parent.glob("unused*"))


def test_existing_evidence_is_never_overwritten(fixture):
    invoke(fixture)
    before = (fixture[1].parent / "call.execution.json").read_bytes()
    with pytest.raises(FileExistsError):
        invoke(fixture)
    assert (fixture[1].parent / "call.execution.json").read_bytes() == before
    assert Path(fixture[2]["proof"]).read_text() == "1"


def test_non_main_thread_and_existing_timer_delegate_to_original_runner(fixture):
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(invoke, fixture, "thread").result() == "delegated"
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, lambda *args: None)
    signal.setitimer(signal.ITIMER_REAL, 10)
    try:
        assert invoke(fixture, "timer") == "delegated"
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    assert len(fixture[4]) == 2 and fixture[3].verifier is None


def test_metadata_scope_and_unsafe_imports_fail_closed(fixture):
    fixture[3].metadata_root = fixture[1].parent / "another-task"
    with pytest.raises(ValueError, match="outside"):
        invoke(fixture, "outside")
    assert record(fixture, "outside")["verifier_calls"] == 0
    fixture[3].metadata_root = fixture[1].parent
    fixture[0].write_text("import os\n" + SOURCE)
    fixture[3].expected_hash = oracle.sha(fixture[0])
    with pytest.raises(ValueError, match="not applicable"):
        invoke(fixture, "unsafe")
    assert record(fixture, "unsafe")["verifier_calls"] == 0


def test_new_execution_injects_only_diagnostic_logger_and_preserves_timing_and_passthrough(tmp_path, monkeypatch):
    import cannbench_shared_context_profile as diagnostic
    import cannbench_msprof_timing as timing
    import msprof_exploration_execute as execute
    task = tmp_path / "train/tasks/exp"
    verifier = task / "baseline/scripts/verify_result.py"
    verifier.parent.mkdir(parents=True); verifier.write_text(SOURCE)
    (task / "input-bindings.json").write_text(json.dumps({"cases": [{"verifier": {"path": str(verifier), "sha256": oracle.sha(verifier)}}]}))
    calls = []
    def native_logger(*args, **kwargs):
        calls.append((args, kwargs)); return "native passthrough"
    monkeypatch.setattr(diagnostic, "run_logged", native_logger)
    monkeypatch.setattr(diagnostic, "health", diagnostic.health)
    monkeypatch.setattr(timing, "health", timing.health)
    original_timing = timing.run_logged
    _, supplied, _ = execute.execution_modules(task)
    assert isinstance(supplied.run_logged, oracle.ScopedOracle)
    assert supplied.run_logged.delegate is native_logger
    assert timing.run_logged is original_timing
    args = (["taskset", "-c", "8", "native-runner"], tmp_path / "native", {"DEVICE": "0"}, 10)
    assert supplied.run_logged(*args, cwd=tmp_path) == "native passthrough"
    assert calls == [(args, {"cwd": tmp_path})]
    execute.execution_modules(task)
    assert diagnostic.run_logged.delegate is native_logger
    execute.execution_modules()
    assert diagnostic.run_logged is native_logger and timing.run_logged is original_timing

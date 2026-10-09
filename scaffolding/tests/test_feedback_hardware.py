"""No hardware is executed: all hardware/process boundaries are mocked."""
import contextlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import feedback_hardware as hw


def args(tmp_path, command='measure', extra=()):
    return hw.parse_args([command, '--output', str(tmp_path / 'out'), '--baseline', str(tmp_path / 'baseline'),
                          '--candidate', str(tmp_path / 'candidate'), '--opdir', str(tmp_path / 'candidate'),
                          '--input-root', str(tmp_path / 'input'), *extra])


def test_measure_protocol_and_reverse_control(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hw, 'run_process', lambda argv, *a, **kw: calls.append(list(map(str, argv))))
    a = args(tmp_path, 'control', ['--reverse', '--cases', '1,8'])
    hw.execute_stages(a, tmp_path / 'scratch')
    argv = calls[0]
    assert argv[argv.index('--candidate') + 1] == str(a.baseline)
    assert argv[argv.index('--repeat') + 1] == '100'
    assert argv[argv.index('--pairs') + 1] == '30'
    assert argv[argv.index('--precondition-samples') + 1] == '1'
    assert {'--reverse-startup', '--single-live-context', '--reuse-verifier', '--external-lock'} <= set(argv)
    assert '--capture-replay' not in argv


def test_first_build_failure_stops(tmp_path, monkeypatch):
    process = Mock(side_effect=RuntimeError('configure failed'))
    monkeypatch.setattr(hw, 'run_process', process)
    with pytest.raises(RuntimeError):
        hw.execute_stages(args(tmp_path, 'build'), tmp_path / 'scratch')
    assert process.call_count == 1
    assert process.call_args.kwargs['cpu'] == '40-43'


def test_archive_idempotency_integrity_and_lock(tmp_path, monkeypatch):
    held = []
    @contextlib.contextmanager
    def lock():
        held.append(True)
        try:
            yield
        finally:
            held.pop()
    monkeypatch.setattr(hw, 'exclusive_host', lock)
    monkeypatch.setattr(hw, 'request_binding', lambda a: {'frozen': 'binding'})
    monkeypatch.setattr(hw, 'health', lambda path: held or pytest.fail('health without lock'))
    def stages(a, scratch):
        assert held
        (scratch / 'result.txt').write_text('evidence')
    executor = Mock(side_effect=stages)
    monkeypatch.setattr(hw, 'execute_stages', executor)
    a = args(tmp_path)
    first = hw.run(a)
    assert first['status'] == 'passed'
    assert hw.run(a) == first
    assert executor.call_count == 1
    (a.output / 'result.txt').write_text('tampered')
    with pytest.raises(FileExistsError):
        hw.run(a)
    assert executor.call_count == 1


def test_failed_archive_never_reruns(tmp_path, monkeypatch):
    monkeypatch.setattr(hw, 'exclusive_host', contextlib.nullcontext)
    monkeypatch.setattr(hw, 'request_binding', lambda a: {})
    monkeypatch.setattr(hw, 'health', lambda p: None)
    executor = Mock(side_effect=RuntimeError('runtime failure'))
    monkeypatch.setattr(hw, 'execute_stages', executor)
    a = args(tmp_path)
    with pytest.raises(RuntimeError):
        hw.run(a)
    assert json.loads((a.output / 'completion.json').read_text())['status'] == 'failed'
    with pytest.raises(FileExistsError):
        hw.run(a)
    assert executor.call_count == 1


def test_timeout_kills_only_owned_process_group(tmp_path, monkeypatch):
    child = Mock(pid=123456, returncode=-15)
    child.wait.side_effect = [subprocess.TimeoutExpired('mock', 1), -15]
    child.poll.return_value = None
    popen = Mock(return_value=child)
    kill = Mock()
    monkeypatch.setattr(hw.subprocess, 'Popen', popen)
    monkeypatch.setattr(hw.os, 'killpg', kill)
    with pytest.raises(subprocess.TimeoutExpired):
        hw.run_process(['mock'], tmp_path, tmp_path / 'logs', timeout=1)
    kill.assert_called_once_with(child.pid, hw.signal.SIGTERM)
    assert popen.call_args.kwargs['start_new_session'] is True
    assert json.loads((tmp_path / 'logs/execution.json').read_text())['status'] == 'failed'


def test_profile_requires_one_case(tmp_path):
    with pytest.raises(SystemExit):
        args(tmp_path, 'profile')


def test_nonzero_exit_archives_and_cleans_owned_descendants(tmp_path, monkeypatch):
    child = Mock(pid=123456, returncode=3)
    child.wait.return_value = 3
    child.poll.return_value = 3
    monkeypatch.setattr(hw.subprocess, 'Popen', Mock(return_value=child))
    kill = Mock()
    monkeypatch.setattr(hw.os, 'killpg', kill)
    with pytest.raises(RuntimeError, match='process failed'):
        hw.run_process(['mock'], tmp_path, tmp_path / 'logs')
    kill.assert_called_once_with(child.pid, hw.signal.SIGTERM)
    assert json.loads((tmp_path / 'logs/execution.json').read_text())['exit_status'] == 3


def test_profile_full_operator_launch_budget(tmp_path, monkeypatch):
    tree = tmp_path / 'tree'
    (tree / 'op_host').mkdir(parents=True)
    (tree / 'op_host/foreach_addcdiv_scalar.asc').write_text('constexpr uint64_t kChunkElements = 2ULL * 4;')
    assert hw.launch_count(tree, {'lengths': [9, 16]}) == 4
    (tree / 'op_host/foreach_addcdiv_scalar.asc').write_text('changed launch contract')
    with pytest.raises(ValueError, match='unknown TensorList'):
        hw.launch_count(tree, {'lengths': [9, 16]})


def test_spawn_signals_deferred_without_inherited_blocked_mask(tmp_path, monkeypatch):
    child = Mock(pid=123456, returncode=-15)
    child.wait.return_value = -15
    observed = []
    def spawn(*a, **kw):
        observed.append(hw.signal.pthread_sigmask(hw.signal.SIG_BLOCK, set()))
        hw.signal.getsignal(hw.signal.SIGTERM)(hw.signal.SIGTERM, None)
        return child
    monkeypatch.setattr(hw.subprocess, 'Popen', spawn)
    monkeypatch.setattr(hw.os, 'killpg', Mock())
    with pytest.raises(KeyboardInterrupt, match='during process startup'):
        hw.run_process(['mock'], tmp_path, tmp_path / 'logs')
    assert hw.signal.SIGTERM not in observed[0]
    assert hw.signal.SIGINT not in observed[0]
    hw.os.killpg.assert_called_once_with(child.pid, hw.signal.SIGTERM)


def test_profile_uses_actual_native_launch_names(tmp_path):
    (tmp_path / 'op_host').mkdir()
    (tmp_path / 'op_host/foreach_norm.asc').write_text('norm_partial_kernel<<<1>>>(x); norm_finalize_kernel<<<1>>>(y); norm_partial_kernel<<<1>>>(z);')
    assert hw.profile_kernels(tmp_path) == ['norm_partial_kernel', 'norm_finalize_kernel']


def test_golden_is_bound(tmp_path):
    a = args(tmp_path, 'correctness', ['--cases', '1'])
    (a.opdir / 'op_host').mkdir(parents=True)
    (a.opdir / 'op_host/exp.asc').write_text('source')
    (a.opdir / 'build').mkdir()
    (a.opdir / 'build/exp').write_text('binary')
    case = a.input_root / 'case_01'
    case.mkdir(parents=True)
    golden = case / 'golden.bin'
    golden.write_bytes(b'expected')
    (case / 'metadata.json').write_text(json.dumps({'golden': str(golden)}))
    first = hw.request_binding(a)
    assert first['inputs']['files'][str(golden)] == hw.sha(golden)
    golden.write_bytes(b'changed')
    assert hw.request_binding(a) != first


def test_profile_skips_all_host_warmup_launches(tmp_path, monkeypatch):
    a = args(tmp_path, 'profile', ['--cases', '1'])
    (a.opdir / 'op_host').mkdir(parents=True)
    (a.opdir / 'op_host/foreach_norm.asc').write_text('partial<<<1>>>(x); finalize<<<1>>>(x);')
    case = a.input_root / 'case_01'
    case.mkdir(parents=True)
    (case / 'metadata.json').write_text(json.dumps({'lengths': [100, 200]}))
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(hw, 'command_from_metadata', lambda *a: ['native-op'])
    process = Mock()
    monkeypatch.setattr(hw, 'run_process', process)
    hw.execute_stages(a, scratch)
    argv = process.call_args_list[0].args[0]
    assert '--launch-skip-before-match=40' in argv
    assert '--launch-count=20' in argv
    assert '--warm-up=10' in argv
    protocol = json.loads((scratch / 'profile-protocol.json').read_text())
    assert protocol['version'] == '2.0.0'
    assert protocol['launch_skip_before_match'] == 10 * protocol['complete_operator_launches']
    assert protocol['artifact_path_mapping']['archive_root'] == str(a.output)


def test_profile_budget_rejected_before_health_or_process(tmp_path, monkeypatch):
    a = args(tmp_path, 'profile', ['--cases', '1'])
    (a.opdir / 'op_host').mkdir(parents=True)
    (a.opdir / 'op_host/foreach_norm.asc').write_text('partial<<<1>>>(x); finalize<<<1>>>(x);')
    (a.opdir / 'build').mkdir()
    (a.opdir / 'build/foreach_norm').write_text('binary')
    case = a.input_root / 'case_01'
    case.mkdir(parents=True)
    (case / 'metadata.json').write_text(json.dumps({'lengths': [1] * 51}))
    monkeypatch.setattr(hw, 'exclusive_host', contextlib.nullcontext)
    health = Mock()
    process = Mock()
    monkeypatch.setattr(hw, 'health', health)
    monkeypatch.setattr(hw, 'run_process', process)
    with pytest.raises(ValueError, match='skip=1020'):
        hw.run(a)
    health.assert_not_called()
    process.assert_not_called()
    assert not a.output.exists()

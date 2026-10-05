"""CPU-only: real process enumeration, signals, hardware queries and locks are forbidden."""
import contextlib
import copy
import json
from pathlib import Path
import signal
import subprocess
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_aprof_devices as release
import msprof_exploration_safety as safety


def proc(pid, ppid=1, pgid=None, sid=None, ticks=None, name='python3', server=False):
    pgid = pid if pgid is None else pgid
    return dict(pid=pid, ppid=ppid, pgid=pgid, session_id=pgid if sid is None else sid,
                start_ticks=str(ticks or pid * 10), name=name, is_server=server, command_hash='hash')


def topology(ids=(0, 1), chips=2, *, occupied=None):
    lines = ['| NPU   Name | Health | Power(W) |', '| Chip  Phy-ID | Bus-Id | AICore(%) |']
    physical = 0
    for npu in ids:
        for chip in range(chips):
            lines += [f'| {npu} Ascend910 | OK | 100 |', f'| {chip} {physical} | 0000:9D:00.0 | 0 |']
            physical += 1
    lines += ['| NPU Chip | Process id | Process name | Process memory(MB) |']
    for npu in ids:
        if npu == occupied:
            lines += [f'| {npu} 0 | 777 | python3 | 2048 |']
        else:
            lines += [f'| No running processes found in NPU {npu} |']
    return '\n'.join(lines)


@pytest.fixture(autouse=True)
def prohibit_real_operations(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('test crossed a real process/hardware boundary')
    monkeypatch.setattr(release, 'processes', forbidden)
    monkeypatch.setattr(release, 'process', forbidden)
    monkeypatch.setattr(release, 'exclusive_host', forbidden)
    monkeypatch.setattr(release.os, 'kill', forbidden)
    monkeypatch.setattr(release.os, 'killpg', forbidden)
    monkeypatch.setattr(release.os, 'pidfd_open', forbidden)
    monkeypatch.setattr(release.signal, 'pidfd_send_signal', forbidden)
    monkeypatch.setattr(safety.subprocess, 'run', forbidden)
    monkeypatch.setattr(safety.subprocess, 'Popen', forbidden)
    monkeypatch.setattr(release.time, 'sleep', forbidden)


@pytest.fixture
def world(monkeypatch, tmp_path):
    class World:
        def __init__(self):
            self.current = {100: proc(100, server=True), 101: proc(101, 100, 100)}
            self.clock = 0
            self.signals = []
            self.held = False
            self.on_signal = lambda row, sig: self.current.pop(row['pid'], None)
            self.on_sleep = lambda: None
            self.on_health = lambda: None

        @contextlib.contextmanager
        def lock(self, root):
            assert not self.held
            self.held = True
            try:
                yield
            finally:
                self.held = False

        def snapshot(self):
            assert self.held
            return copy.deepcopy(self.current)

        def send(self, row, sig):
            assert self.held
            assert release.identity(row) == release.identity(self.current[row['pid']])
            self.signals.append((row['pid'], sig))
            self.on_signal(row, sig)
            return 'sent'

        def sleep(self, interval):
            self.clock += interval
            self.on_sleep()

        def health(self):
            assert self.held
            self.on_health()
            return dict(status='passed', exit_code=0, no_device_processes=True)

        def run(self, **kwargs):
            return release.release_devices(tmp_path / 'release.json', authorized=True,
                                           term_timeout=2, kill_timeout=1, poll_interval=1, **kwargs)

    w = World()
    monkeypatch.setattr(release, 'exclusive_host', w.lock)
    monkeypatch.setattr(release, 'processes', w.snapshot)
    monkeypatch.setattr(release, 'send_signal', w.send)
    monkeypatch.setattr(release.time, 'sleep', w.sleep)
    monkeypatch.setattr(release.time, 'monotonic', lambda: w.clock)
    monkeypatch.setattr(release, 'query_health', w.health)
    return w


def test_term_success_releases_only_authorized_tree(world, tmp_path):
    world.current[500] = proc(500, name='unrelated')
    report = world.run()
    assert report['status'] == 'passed' and report['exit_status'] == 0
    assert world.signals == [(100, signal.SIGTERM), (101, signal.SIGTERM)]
    assert set(world.current) == {500} and not world.held
    assert json.loads((tmp_path / 'release.json').read_text()) == report


def test_confirmed_residue_gets_kill_after_grace(world):
    world.on_signal = lambda row, sig: world.current.pop(row['pid']) if sig == signal.SIGKILL else None
    report = world.run()
    assert report['status'] == 'passed'
    assert world.signals == [(100, signal.SIGTERM), (101, signal.SIGTERM),
                             (100, signal.SIGKILL), (101, signal.SIGKILL)]
    assert world.clock >= 2


def test_new_child_discovered_during_term_gets_term(world):
    def on_signal(row, sig):
        if row['pid'] == 100:
            world.current[102] = proc(102, 101, 100)
        world.current.pop(row['pid'])
    world.on_signal = on_signal
    report = world.run()
    assert report['status'] == 'passed'
    assert (102, signal.SIGTERM) in world.signals
    assert len(report['discovered_targets']) == 3


def test_orphan_in_original_independent_group_is_discovered(world):
    def on_signal(row, sig):
        if row['pid'] == 100:
            world.current[102] = proc(102, 1, 100, name='sglang::schedul')
        world.current.pop(row['pid'])
    world.on_signal = on_signal
    assert world.run()['status'] == 'passed'
    assert (102, signal.SIGTERM) in world.signals


def test_unproven_orphan_is_never_signalled_and_blocks(world):
    world.current[500] = proc(500, name='sglang::schedul')
    report = world.run()
    assert report['status'] == 'failed'
    assert [row['pid'] for row in report['unresolved_processes']] == [500]
    assert all(pid != 500 for pid, sig in world.signals)


def test_contaminated_group_is_not_a_provenance_shortcut(world):
    world.current[500] = proc(500, 1, 100, name='unrelated')
    report = world.run()
    assert report['status'] == 'failed'
    assert all(pid != 500 for pid, sig in world.signals)
    assert report['unresolved_processes'][0]['pid'] == 500


def test_pid_reuse_is_not_killed(world):
    def on_signal(row, sig):
        if row['pid'] == 100:
            world.current[100] = proc(100, ticks=99999, name='unrelated')
        else:
            world.current.pop(row['pid'])
    world.on_signal = on_signal
    report = world.run()
    assert report['status'] == 'failed'  # Same numerical group is now unproven.
    assert world.signals.count((100, signal.SIGTERM)) == 1
    assert (100, signal.SIGKILL) not in world.signals
    assert report['reused_identities'] == [dict(pid=100, start_ticks='99999')]


def test_reused_root_cannot_authorize_new_group_members():
    tree = release.AuthorizedTree({100: proc(100, server=True)})
    alive, unknown = tree.refresh({100: proc(100, ticks=99999), 102: proc(102, 100, 100)})
    assert alive == []
    assert {row['pid'] for row in unknown} == {100, 102}


def test_nonindependent_group_cannot_authorize_orphans():
    root = proc(100, pgid=5, sid=5, server=True)
    tree = release.AuthorizedTree({100: root})
    alive, unknown = tree.refresh({102: proc(102, 1, 5, name='sglang::schedul')})
    assert alive == [] and unknown[0]['pid'] == 102


def test_late_child_is_not_killed_without_its_own_grace(world):
    world.on_signal = lambda row, sig: world.current.pop(row['pid']) if sig == signal.SIGKILL else None
    def born_late():
        if world.clock == 2:
            world.current[102] = proc(102, 1, 100)
    world.on_sleep = born_late
    report = world.run()
    assert report['status'] == 'failed'
    assert (102, signal.SIGTERM) in world.signals
    assert (102, signal.SIGKILL) not in world.signals
    assert report['remaining_targets'] == [102]


def test_respawn_during_health_blocks(world):
    world.on_health = lambda: world.current.update({500: proc(500, server=True)})
    assert world.run()['status'] == 'failed'
    assert all(pid != 500 for pid, sig in world.signals)


def test_health_failure_propagates_into_release(world, monkeypatch):
    monkeypatch.setattr(release, 'query_health', lambda: dict(status='failed', exit_code=7, error='driver error'))
    report = world.run()
    assert report['exit_status'] == 1 and report['npu_smi']['exit_code'] == 7


def test_inventory_mode_never_signals(world, tmp_path):
    report = release.release_devices(tmp_path / 'release.json')
    assert report['exit_status'] == 1 and world.signals == []


def test_explicit_root_does_not_authorize_other_server(world):
    world.current[500] = proc(500, server=True)
    report = world.run(root_pids=[100])
    assert report['status'] == 'failed'
    assert all(pid != 500 for pid, sig in world.signals)


def test_output_reuse_stops_before_lock_or_health(world, monkeypatch, tmp_path):
    world.run()
    def forbidden(*args, **kwargs):
        pytest.fail('reused evidence must not acquire locks or query health')
    monkeypatch.setattr(release, 'exclusive_host', forbidden)
    monkeypatch.setattr(release, 'query_health', forbidden)
    with pytest.raises(FileExistsError):
        world.run()


def test_pidfd_rechecks_identity_and_closes(monkeypatch):
    close, sent = Mock(), Mock()
    monkeypatch.setattr(release.os, 'pidfd_open', lambda pid: 12345)
    monkeypatch.setattr(release.os, 'close', close)
    monkeypatch.setattr(release.signal, 'pidfd_send_signal', sent)
    monkeypatch.setattr(release, 'process', lambda pid: proc(pid, ticks=99999))
    assert release.send_signal(proc(100), signal.SIGKILL) == 'identity_changed'
    sent.assert_not_called()
    close.assert_called_once_with(12345)


def test_pidfd_sends_to_pinned_object(monkeypatch):
    close, sent = Mock(), Mock()
    monkeypatch.setattr(release.os, 'pidfd_open', lambda pid: 12345)
    monkeypatch.setattr(release.os, 'close', close)
    monkeypatch.setattr(release.signal, 'pidfd_send_signal', sent)
    monkeypatch.setattr(release, 'process', lambda pid: proc(pid))
    assert release.send_signal(proc(100), signal.SIGTERM) == 'sent'
    sent.assert_called_once_with(12345, signal.SIGTERM)
    close.assert_called_once_with(12345)


@pytest.mark.parametrize('ids,chips', [((0,), 1), ((2, 4, 8), 2), (tuple(range(8)), 2)])
def test_health_parses_actual_topology_not_eight_empty_strings(ids, chips):
    parsed = safety.parse_health(topology(ids, chips))
    assert parsed['no_device_processes']
    assert parsed['npu_ids'] == list(ids)
    assert len(parsed['devices']) == len(ids) * chips


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'unknown', 'unhealthy', 'truncated', 'malformed'])
def test_health_rejects_bad_or_incomplete_inventory(change):
    text = topology()
    if change == 'missing':
        text = text.replace('| No running processes found in NPU 1 |', '')
    elif change == 'duplicate':
        text += '\n| No running processes found in NPU 0 |'
    elif change == 'unknown':
        text += '\n| No running processes found in NPU 9 |'
    elif change == 'unhealthy':
        text = text.replace('| OK |', '| Warning |', 1)
    elif change == 'truncated':
        text = text.split('| NPU Chip')[0]
    else:
        text += '\n| unexpected row |'
    try:
        parsed = safety.parse_health(text)
    except ValueError:
        return
    assert not parsed['no_device_processes']


def test_occupied_health_retains_pid():
    parsed = safety.parse_health(topology(occupied=1))
    assert not parsed['no_device_processes']
    assert parsed['processes'] == [dict(npu_id=1, chip_id=0, pid=777)]


@pytest.mark.parametrize('failure', ['nonzero', 'timeout', 'parse', 'occupied'])
def test_health_records_failure_immutably(monkeypatch, tmp_path, failure):
    query = Mock()
    if failure == 'timeout':
        query.side_effect = subprocess.TimeoutExpired(['npu-smi'], 30, output=b'partial output')
    else:
        query.return_value = subprocess.CompletedProcess([], 7 if failure == 'nonzero' else 0,
            'invalid' if failure == 'parse' else topology(occupied=1 if failure == 'occupied' else None), 'error text')
    monkeypatch.setattr(safety.subprocess, 'run', query)
    path = tmp_path / 'health.json'
    with pytest.raises(RuntimeError):
        safety.health(path)
    record = json.loads(path.read_text())
    assert record['status'] == 'failed' and record['error']
    if failure == 'nonzero':
        assert record['exit_code'] == record['exit_status'] == 7
    if failure == 'timeout':
        assert record['stdout'] == 'partial output' and record['exit_status'] is None
    with pytest.raises(FileExistsError):
        safety.health(path)
    assert query.call_count == 1


def test_health_success_requires_no_lock_acquisition(monkeypatch, tmp_path):
    monkeypatch.setattr(safety.subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess([], 0, topology((3,), 2), ''))
    report = safety.health(tmp_path / 'health.json')
    assert report['status'] == 'passed' and report['npu_ids'] == [3]

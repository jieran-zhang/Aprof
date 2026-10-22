"""Small wiring checks; full publication replay is exercised only by sealing."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import seal_task_window_history_supplement as entry


@pytest.fixture
def wiring(monkeypatch, tmp_path):
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text('{}')
    plan = {'source_archive_ref': {'path': '/extra', 'sha256': 'extra'},
            'program_refs': {}, 'history_ref': {}, 'failed_publication_ref': {}}
    terminals = {}
    for index in range(4):
        terminal = tmp_path / ('terminal-' + str(index) + '.json')
        terminal.write_text(json.dumps({'slot': index}))
        terminals[str(index)] = entry.bound(terminal)
    plan['reference_format_repair'] = {'observation_terminals': terminals}
    history = {'source_archive_refs': [{'path': '/original', 'sha256': 'original'}]}
    monkeypatch.setattr(entry, 'plan_value', lambda *args: (plan, history))
    reader = importlib.import_module('replay_task_window_method_history')
    calls = []

    def original(refs, **kwargs):
        calls.append((refs, kwargs))
        return object()

    monkeypatch.setattr(reader, 'HistoricalEvidence', original)
    return plan_path, plan, history, reader, original, calls


def test_complete_publisher_receives_only_archive_supplement(monkeypatch, wiring):
    path, plan, history, reader, original, calls = wiring

    def full_publisher(root, report):
        reader.HistoricalEvidence(history['source_archive_refs'], logical_paths=True)
        for ref in plan['reference_format_repair']['observation_terminals'].values():
            assert entry.publisher.bound(ref['path']) == ref
        return {'accepted': True, 'all_original_checks': 'sentinel'}

    monkeypatch.setattr(entry.publisher, 'verify_in_process', full_publisher)
    result = entry.audit('/root', '/report', path, entry.digest(path))
    assert calls == [([*history['source_archive_refs'], plan['source_archive_ref']],
                      {'logical_paths': True})]
    assert result['all_original_checks'] == 'sentinel'
    assert result['historical_source_replay_supplement']['original_publisher_full_replay'] is True
    assert reader.HistoricalEvidence is original


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'changed'])
def test_terminal_representation_repair_preserves_full_checks(monkeypatch, wiring, failure):
    path, plan, history, reader, original, _ = wiring
    original_bound = entry.publisher.bound
    refs = list(plan['reference_format_repair']['observation_terminals'].values())

    def full_publisher(*args):
        reader.HistoricalEvidence(history['source_archive_refs'])
        if failure == 'changed':
            Path(refs[0]['path']).write_text('changed terminal bytes')
        for ref in refs[:-1] if failure == 'missing' else refs:
            entry.publisher.bound(ref['path'])
        if failure == 'duplicate':
            entry.publisher.bound(refs[0]['path'])
        # Unrelated references retain the original bare-hash helper contract.
        assert entry.publisher.bound(path) == original_bound(path)
        return {'accepted': True}

    monkeypatch.setattr(entry.publisher, 'verify_in_process', full_publisher)
    with pytest.raises(ValueError):
        entry.audit('/root', '/report', path, entry.digest(path))
    assert reader.HistoricalEvidence is original
    assert entry.publisher.bound is original_bound


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'wrong_scope', 'rejected', 'exception'])
def test_failed_or_incomplete_original_replay_rejected(monkeypatch, wiring, failure):
    path, _, history, reader, original, _ = wiring

    def full_publisher(*args):
        if failure == 'exception':
            raise ValueError('original replay failure')
        if failure != 'missing':
            reader.HistoricalEvidence([] if failure == 'wrong_scope' else history['source_archive_refs'])
        if failure == 'duplicate':
            reader.HistoricalEvidence(history['source_archive_refs'])
        return {'accepted': failure != 'rejected'}

    monkeypatch.setattr(entry.publisher, 'verify_in_process', full_publisher)
    with pytest.raises(ValueError):
        entry.audit('/root', '/report', path, entry.digest(path))
    assert reader.HistoricalEvidence is original


@pytest.mark.parametrize('exit_code,accepted', [(1, True), (0, False)])
def test_independent_child_failure_rejected(monkeypatch, wiring, exit_code, accepted):
    path, *_ = wiring

    def child(argv, **kwargs):
        assert argv[1] == '-I' and argv[3] == 'audit'
        assert kwargs['timeout'] == 1800
        return SimpleNamespace(returncode=exit_code, stderr='child failed',
                               stdout=json.dumps({'accepted': accepted}))

    monkeypatch.setattr(entry.subprocess, 'run', child)
    with pytest.raises(ValueError):
        entry.independent('/root', '/report', path, entry.digest(path))


def test_changed_supplement_rejected(tmp_path):
    path = tmp_path / 'plan.json'
    path.write_text('{}')
    ref = entry.bound(path)
    path.write_text('{"changed": true}')
    with pytest.raises(ValueError, match='changed'):
        entry.checked(ref)

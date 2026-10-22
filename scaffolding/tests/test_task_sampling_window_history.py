"""Only explicit historical replay can resolve archived producer identities."""
import json
from pathlib import Path

import pytest

import diagnose_task_sampling_window as window
import replay_task_sampling_window_history as bridge
from measurement_source_archive import HistoricalEvidence
from replay_timing_diagnosis import Evidence, digest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'path': str(path), 'sha256': digest(path)}


def test_run_remains_strict_while_history_resolves_exact_old_producer(tmp_path, monkeypatch):
    output = tmp_path / 'diagnostic'; output.mkdir()
    old = tmp_path / 'old.py'; old.write_bytes(b'exact archived diagnostic producer')
    original = str(Path(window.__file__).resolve())
    index = write(tmp_path / 'archive.json', {'schema_version': 1, 'not_a_release': True,
        'files': {original: {'path': str(old), 'sha256': digest(old)}}})
    plan = write(output / 'plan.json', {})
    freeze = write(output / 'freeze.json', {'purpose': window.PURPOSE, 'plan': plan,
        'matrix': window.matrix(), 'accepted': False, 'eligible_for_publication': False,
        'created_at': 1, 'frozen_files': {original: digest(old)}})
    monkeypatch.setattr(window, 'ROOT', tmp_path)
    monkeypatch.setattr(window, '_checked_plan', lambda _: ({}, {}))
    anchor = tmp_path / 'scaffolding/curation/anchor.json'
    write(anchor, {'schema_version': 1, 'purpose': window.PURPOSE, 'freeze': freeze,
        'max_attempts': 1, 'resampling': 'none', 'recorded_at_utc': '2020-01-01T00:00:00+00:00'})
    with pytest.raises(ValueError, match='frozen diagnostic file changed'):
        window._anchored(output, anchor)
    evidence = HistoricalEvidence([index], logical_paths=True)
    assert window._anchored(output, anchor, historical_evidence=evidence) == ({}, {})
    assert evidence.resolved_files[original]['path'] == str(old)


def test_history_must_execute_the_unchanged_current_pure_parser(tmp_path):
    parser = str(window.RELEASE / 'runtime/src/aprof_runtime/task_timing.py')
    reference = write(tmp_path / 'archive.json', {'schema_version': 1, 'not_a_release': True,
        'files': {parser: {'path': str(tmp_path / 'old.py'), 'sha256': 'sha256:' + '0' * 64}}})
    write(tmp_path / 'freeze.json', {'frozen_files': {parser: 'sha256:' + '0' * 64}})
    with pytest.raises(ValueError, match='changed evidence'):
        window.replay(tmp_path, tmp_path / 'anchor.json', source_archive_refs=[reference])


def test_archived_raw_workload_cannot_replace_original_file(tmp_path):
    raw = tmp_path / 'raw.csv'; raw.write_bytes(b'changed actual raw')
    old = tmp_path / 'old.csv'; old.write_bytes(b'previous raw')
    # The generic resolver rejects even registering a data path as a producer.
    index = write(tmp_path / 'archive.json', {'schema_version': 1, 'not_a_release': True,
        'files': {str(raw): {'path': str(old), 'sha256': digest(old)}}})
    with pytest.raises(ValueError, match='cannot substitute workload'):
        HistoricalEvidence([index], logical_paths=True)


def test_saved_diagnostic_result_cannot_be_promoted():
    saved = {'complete': True, 'accepted': True, 'eligible_for_publication': False, 'slots': 24}
    with pytest.raises(ValueError, match='cannot grant admission'):
        bridge._check_saved_replay(saved, {}, {}, {}, {}, Evidence())


def test_bridge_rejects_incomplete_source_chain_before_recursing(tmp_path):
    reference = write(tmp_path / 'history.json', {'schema_version': 1, 'purpose': bridge.PURPOSE,
        'not_a_release': True, 'eligible_for_publication': False,
        'previous_history_supplement': {}, 'window': {'directory': str(tmp_path)}})
    with pytest.raises(ValueError, match='missing or unknown sources'):
        bridge.replay_task_sampling_window_history(reference)

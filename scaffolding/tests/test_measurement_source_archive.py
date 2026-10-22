import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'collection/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('measurement_source_archive', SCRIPTS / 'measurement_source_archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def snapshot(tmp_path, monkeypatch, *, evidence=False):
    repo = tmp_path / 'repo'
    sources = repo / 'scaffolding/collection/scripts'
    sources.mkdir(parents=True)
    monkeypatch.setattr(archive, 'REPO', repo)
    monkeypatch.setattr(archive, 'SOURCE_ROOTS', (sources,))
    original = (tmp_path if evidence else sources) / 'producer.py'
    original.write_text('current bytes')
    old = tmp_path / 'old.py'
    old.write_text('frozen producer bytes')
    expected = archive.digest(old)
    index = tmp_path / 'index.json'
    index.write_text(json.dumps({'schema_version': 1, 'not_a_release': True,
        'files': {str(original): {'path': str(old), 'sha256': expected}}}))
    reference = {'path': str(index), 'sha256': archive.digest(index)}
    return original, old, expected, reference


def test_archive_only_resolves_exact_old_hash(tmp_path, monkeypatch):
    original, old, expected, reference = snapshot(tmp_path, monkeypatch)
    historical = archive.HistoricalEvidence([reference])
    assert historical.bind(original, expected)['path'] == str(old)
    assert historical.bind(original, archive.digest(original))['path'] == str(original)
    with pytest.raises(ValueError, match='changed evidence'):
        archive.Evidence().bind(original, expected)
    with pytest.raises(ValueError, match='changed evidence'):
        historical.bind(original, 'sha256:' + '0' * 64)


def test_archive_cannot_substitute_raw_evidence(tmp_path, monkeypatch):
    *_, reference = snapshot(tmp_path, monkeypatch, evidence=True)
    with pytest.raises(ValueError, match='cannot substitute'):
        archive.HistoricalEvidence([reference])


def test_archive_and_snapshot_tampering_rejected(tmp_path, monkeypatch):
    original, old, expected, reference = snapshot(tmp_path, monkeypatch)
    old.write_text('changed snapshot')
    with pytest.raises(ValueError, match='changed evidence'):
        archive.HistoricalEvidence([reference]).bind(original, expected)
    Path(reference['path']).write_text('{}')
    with pytest.raises(ValueError, match='index changed'):
        archive.HistoricalEvidence([reference])


def logical_snapshot(tmp_path, monkeypatch, *, name='producer.py'):
    repo = tmp_path / 'repo'
    scripts = repo / 'scaffolding/collection/scripts'
    scripts.mkdir(parents=True)
    monkeypatch.setattr(archive, 'REPO', repo)
    monkeypatch.setattr(archive, 'SOURCE_ROOTS', (repo / 'scaffolding',))
    original = scripts / name
    original.write_text('new source')
    saved = tmp_path / ('saved-' + name)
    saved.write_text('old source')
    expected = archive.digest(saved)
    index = tmp_path / 'archive.json'
    index.write_text(json.dumps({'schema_version': 1, 'not_a_release': True,
        'files': {str(original): {'path': str(saved), 'sha256': expected}}}))
    return original, saved, expected, {'path': str(index), 'sha256': archive.digest(index)}


def test_historical_code_preserves_logical_result_and_separate_resolution(tmp_path, monkeypatch):
    original, saved, expected, reference = logical_snapshot(tmp_path, monkeypatch)
    historical = archive.HistoricalEvidence([reference], logical_paths=True)
    assert historical.resolve_producer(original, expected) == saved
    assert historical.bind(original)['path'] == str(original)
    assert historical.semantic_files() == {str(original): expected}
    assert historical.resolved_files[str(original)]['path'] == str(saved)
    assert str(Path(reference['path'])) in historical.files
    with pytest.raises(ValueError, match='absent'):
        historical.resolve_producer(original, archive.digest(original))


def test_historical_producer_resolver_cannot_alias_a_receipt_under_source_root(tmp_path, monkeypatch):
    original, _, expected, reference = logical_snapshot(tmp_path, monkeypatch, name='receipt.json')
    historical = archive.HistoricalEvidence([reference], logical_paths=True)
    with pytest.raises(ValueError, match='only registered producer'):
        historical.resolve_producer(original, expected)
    with pytest.raises(ValueError, match='changed evidence'):
        historical.bind(original, expected)
    with pytest.raises(ValueError, match='changed evidence'):
        archive.HistoricalEvidence([reference]).bind(original, expected)
    original.write_bytes((tmp_path / 'saved-receipt.json').read_bytes())
    assert archive.HistoricalEvidence([reference], logical_paths=True).bind(original, expected)['path'] == str(original)


def test_historical_logical_mapping_still_checks_snapshot_bytes(tmp_path, monkeypatch):
    original, saved, expected, reference = logical_snapshot(tmp_path, monkeypatch)
    saved.write_text('tampered source')
    historical = archive.HistoricalEvidence([reference], logical_paths=True)
    with pytest.raises(ValueError, match='changed evidence'):
        historical.resolve_producer(original, expected)

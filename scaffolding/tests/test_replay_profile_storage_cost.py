"""Small trust-boundary tests; never replay the large historical profiles here."""
import hashlib
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from replay_profile_storage_cost import (Evidence, _cas_index, _close_seconds, _seconds,
    resolve_fixed_cost_source)


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def test_full_tree_rejects_added_missing_and_changed_files(tmp_path):
    root = tmp_path / 'profile'
    root.mkdir()
    source = root / 'one'
    source.write_bytes(b'original')
    manifest = {'one': {'bytes': 8, 'sha256': sha(b'original')}}
    Evidence().tree(root, manifest)
    (root / 'extra').write_bytes(b'new')
    with pytest.raises(ValueError, match='roster'):
        Evidence().tree(root, manifest)
    (root / 'extra').unlink()
    source.write_bytes(b'modified')
    with pytest.raises(ValueError, match='changed'):
        Evidence().tree(root, manifest)
    source.unlink()
    with pytest.raises(ValueError, match='roster'):
        Evidence().tree(root, manifest)


def test_cas_object_and_sqlite_locations_are_complete(tmp_path):
    content = b'profile'
    digest = sha(content)
    source = tmp_path / 'former-local-source'
    database = tmp_path / 'evidence.sqlite'
    obj = tmp_path / 'evidence.sqlite.objects/sha256' / digest[7:9] / digest[9:]
    obj.parent.mkdir(parents=True)
    obj.write_bytes(content)
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE artifacts(content_hash TEXT)')
        conn.execute('CREATE TABLE artifact_locations(content_hash TEXT,uri TEXT,size_bytes INTEGER)')
        conn.execute('INSERT INTO artifacts VALUES (?)', (digest,))
        for path in (source / 'one', obj):
            conn.execute('INSERT INTO artifact_locations VALUES (?,?,?)',
                         (digest, path.as_uri(), len(content)))
    expected = {'one': {'bytes': len(content), 'sha256': digest}}
    post = {'files': {'one': {'bytes': len(content), 'sha256': digest, 'object': str(obj)}},
            'unique_objects': 1, 'sqlite_locations_checked': True}
    receipt = {'sqlite_ref': {'path': str(database), 'sha256': Evidence().hash(database)},
               'postverify': post}
    _cas_index(Evidence(), database, source, expected, receipt)
    obj.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='CAS object'):
        _cas_index(Evidence(), database, source, expected, receipt)
    obj.write_bytes(content)
    with sqlite3.connect(database) as conn:
        conn.execute('DELETE FROM artifact_locations WHERE uri=?', ((source / 'one').as_uri(),))
    receipt['sqlite_ref']['sha256'] = Evidence().hash(database)
    with pytest.raises(ValueError, match='SQLite artifact'):
        _cas_index(Evidence(), database, source, expected, receipt)


def test_cost_report_rejects_nonfinite_negative_or_forged_wall():
    for value in (-1, float('nan'), float('inf'), True):
        with pytest.raises(ValueError, match='cost seconds'):
            _seconds(value)
    with pytest.raises(ValueError, match='wall cost'):
        _close_seconds(3.0, 10.0, 12.0)


def test_fixed_archive_resolves_only_exact_old_cost_producer(monkeypatch, tmp_path):
    import json
    from replay_profile_storage_cost import PACKAGE
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'curation/'
        'graph-base-0.5.1-profile-storage-cost-evidence.json').read_text())
    old = manifest['cas']['store_source']
    live = PACKAGE / 'runtime/src/aprof_runtime/store.py'
    assert Path(old['path']) == live and Evidence().hash(live) != old['sha256']
    archive = resolve_fixed_cost_source(old, Evidence())
    assert archive != live and Evidence().bind(old) == archive
    assert Evidence().hash(archive) == old['sha256']
    with pytest.raises(ValueError, match='absent or hash differs'):
        resolve_fixed_cost_source({**old, 'sha256': Evidence().hash(live)}, Evidence())
    raw = tmp_path / 'raw.json'
    raw.write_bytes(b'raw experiment evidence')
    raw_ref = {'path': str(raw), 'sha256': Evidence().hash(raw)}
    assert resolve_fixed_cost_source(raw_ref, Evidence()) == raw
    raw_ref['sha256'] = old['sha256']
    with pytest.raises(ValueError, match='evidence bytes changed'):
        Evidence().bind(raw_ref)
    monkeypatch.setattr('replay_profile_storage_cost.ARCHIVE_INDEX_SHA256', 'sha256:changed')
    with pytest.raises(ValueError, match='archive index changed'):
        resolve_fixed_cost_source(old, Evidence())

"""Compact evidence preserves original bytes and never consults retired paths."""
import json
from pathlib import Path
import shutil
import pytest
import compact_evidence as compact


def fixture(tmp_path):
    root = tmp_path / 'compact'; root.mkdir()
    data = b'{"original_path":"/missing/historical/path","status":"failed"}\n'
    (root / 'record.jsonl').write_bytes(data)
    value = {'kind': 'compact_optimization_evidence', 'offline_evidence_complete': False,
             'level1': {'memory_rows': 37, 'lesson_rows': 26},
             'level2': {'closed_attempts': 26, 'source_attempts_planned': 48, 'status': 'paused_partial_snapshot'},
             'files': {'source/record.jsonl': {'path': 'record.jsonl', 'sha256': compact.digest(data), 'size_bytes': len(data)}}}
    (root / 'index.json').write_text(json.dumps(value))
    return root, data


def test_local_read_without_original_archive_and_tamper_rejection(tmp_path):
    root, data = fixture(tmp_path)
    assert compact.read(root, 'source/record.jsonl') == data
    assert compact.verify(root)['level2']['closed_attempts'] == 26
    with pytest.raises(FileNotFoundError, match='external'):
        compact.read(root, 'raw/not-imported.bin')
    (root / 'record.jsonl').write_bytes(data + b'changed')
    with pytest.raises(ValueError, match='changed'):
        compact.read(root, 'source/record.jsonl')


@pytest.mark.parametrize('kind', ['escape', 'symlink'])
def test_untrusted_locator_cannot_escape(tmp_path, kind):
    root, data = fixture(tmp_path)
    if kind == 'escape':
        path = root / 'index.json'; value = json.loads(path.read_text())
        value['files']['source/record.jsonl']['path'] = '../outside'
        path.write_text(json.dumps(value))
    else:
        path = root / 'record.jsonl'; path.unlink(); path.symlink_to('/etc/hosts')
    with pytest.raises(ValueError, match='unsafe|symlink'):
        compact.read(root, 'source/record.jsonl')


def test_export_roster_is_explicit():
    assert compact.SOURCE_ARTIFACT.fullmatch('train/tasks/gather/candidates/gather001/source.tar')
    assert not compact.SOURCE_ARTIFACT.fullmatch('train/tasks/gather/candidates/gather001/stages/search/raw.bin')
    assert not compact.SOURCE_ARTIFACT.fullmatch('snapshot.tar')

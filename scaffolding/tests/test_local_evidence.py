import json
from pathlib import Path

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import content_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.traces import register_json_artifact


def test_raw_files_are_read_in_place_without_copy_or_database(tmp_path):
    source = tmp_path / 'raw'; source.write_bytes(b'raw bytes')
    index = LocalEvidence(tmp_path / 'records')
    references = index.register_artifacts([source, source])
    assert references[0] == references[1]
    assert index.verify_artifact(references[0]) == source
    assert list(index.directory.iterdir()) == []
    assert not hasattr(index, 'connection') and not hasattr(index, 'object_path')
    source.write_bytes(b'bad bytes')
    with pytest.raises(StoreError, match='changed'):
        index.verify_artifact(references[0])


def test_canonical_metadata_helper_and_optional_handoff(tmp_path):
    index = LocalEvidence(tmp_path / 'records')
    value = {'purpose': 'online measurement', 'passed': False}
    digest = register_json_artifact(index, value)
    assert digest == content_hash(value)
    assert json.loads(index.verify_artifact(digest).read_text()) == value
    destination = index.write_index(tmp_path / 'handoff.json')
    saved = json.loads(destination.read_text())
    assert saved['artifacts'] == {digest: str(index.verify_artifact(digest))}
    reopened = LocalEvidence.from_index(destination)
    assert reopened.verify_artifact(digest) == index.verify_artifact(digest)
    assert reopened.register_json({'new': 'record'}) != digest
    with pytest.raises(FileExistsError):
        index.write_index(destination)
    with pytest.raises(StoreError, match='task workspace'):
        index.write_index(tmp_path.parent / 'escaped.json')


def test_capture_log_snapshot_retains_pre_export_prefix(tmp_path):
    source = tmp_path / 'collection_host.log'; source.write_bytes(b'capture\n')
    index = LocalEvidence(tmp_path / 'records')
    before = index.snapshot_file(source)
    source.write_bytes(b'capture\nexport\n')
    after = index.register_artifact(source)
    assert index.verify_artifact(before).read_bytes() == b'capture\n'
    assert index.verify_artifact(after) == source
    assert before != after


@pytest.mark.parametrize('mutation', ['missing', 'symlink', 'parent_symlink'])
def test_local_reference_mutation_is_rejected(tmp_path, mutation):
    directory = tmp_path / 'inputs'; directory.mkdir()
    source = directory / 'file'; source.write_bytes(b'input')
    index = LocalEvidence(tmp_path / 'records'); digest = index.register_artifact(source)
    if mutation == 'missing':
        source.unlink()
    elif mutation == 'symlink':
        source.unlink(); replacement = tmp_path / 'replacement'; replacement.write_bytes(b'input')
        source.symlink_to(replacement)
    else:
        directory.rename(tmp_path / 'moved'); directory.symlink_to(tmp_path / 'moved', target_is_directory=True)
    with pytest.raises(StoreError):
        index.verify_artifact(digest)


def test_unknown_reference_and_archive_location_are_rejected(tmp_path):
    index = LocalEvidence(tmp_path / 'records')
    with pytest.raises(StoreError, match='not indexed'):
        index.verify_artifact('sha256:' + '0' * 64)
    source = tmp_path / 'file'; source.write_text('file')
    with pytest.raises(StoreError, match='archive locations'):
        index.register_artifact(source, uri=source.as_uri())


def test_post_task_archive_is_explicit_and_preserves_task_result(tmp_path):
    import importlib.util
    import time
    script = Path(__file__).parents[1] / 'collection/scripts/archive_local_evidence.py'
    spec = importlib.util.spec_from_file_location('archive_local_evidence', script)
    collector = importlib.util.module_from_spec(spec); spec.loader.exec_module(collector)
    task = tmp_path / 'task'; task.mkdir()
    index = LocalEvidence(task / 'records')
    raw = task / 'profile.csv'; raw.write_text('original measurement')
    raw_ref = index.register_artifact(raw)
    terminal = {'kind': 'local_measurement_completion', 'status': 'failed',
                'finished_at': time.time() - 1, 'error': 'control failure'}
    completion = task / 'local-result.json'; completion.write_text(json.dumps(terminal))
    ref = index.register_artifact(completion)
    handoff = index.write_index(task / 'local-index.json')
    assert not (tmp_path / 'archive.db').exists()
    result = collector.archive(handoff, completion, tmp_path / 'archive.db', tmp_path / 'receipt.json')
    assert result['cost_scope'] == 'post_task_archive' and result['admission_authority'] is False
    assert result['completion_ref'] == ref and result['started_at'] >= terminal['finished_at']
    assert json.loads(completion.read_text()) == terminal
    with collector.EpisodeStore(tmp_path / 'archive.db') as store:
        assert store.verify_artifact(raw_ref).read_bytes() == raw.read_bytes()
    raw.write_text('changed')
    with pytest.raises(StoreError, match='changed'):
        collector.archive(handoff, completion, tmp_path / 'bad.db', tmp_path / 'bad.json')

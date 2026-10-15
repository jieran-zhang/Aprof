"""CPU-only relocation, tamper and interruption checks for portable evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import trace_v2_dataset as v2
import trace_v2_portable as portable
from test_trace_v2_dataset import publication


def save(path, value):
    path.write_bytes(v2.canonical(value))


def test_moved_bundle_works_without_original_dataset_or_evidence(tmp_path, monkeypatch):
    root, evidence, body, _ = publication(tmp_path)
    # Include a historical record revision and verify its entire CAS chain.
    body['next_decision']['reason'] = 'second observation'
    v2.publish(root, {'attempt': body}, lambda _: {}, evidence, {'hardware_executed': False})
    source_revision = json.loads((root / 'current.json').read_text())['revision']
    original_rows = (root / 'revisions' / source_revision / 'train/optimization_traces.jsonl').read_bytes()
    target = tmp_path / 'bundle'
    portable.export(root, target)
    moved = tmp_path / 'moved'
    target.rename(moved)
    shutil.rmtree(root)
    for row in evidence.entries.values():
        Path(row['path']).unlink()
    before = {path: path.read_bytes() for path in moved.rglob('*') if path.is_file()}
    result = portable.verify(moved)
    assert result['valid'] and result['portable']
    assert not result['original_evidence_locations_accessed']
    assert (moved / 'dataset/revisions' / source_revision / 'train/optimization_traces.jsonl').read_bytes() == original_rows
    completed = subprocess.run([sys.executable, str(moved / 'verifier/trace_v2_portable.py'),
        'verify', '--bundle', str(moved)], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)['valid']
    assert before == {path: path.read_bytes() for path in moved.rglob('*') if path.is_file()}


@pytest.mark.parametrize('fault', ['missing', 'extra', 'evidence', 'cas', 'unsafe_map', 'partial_map',
                                  'self_consistent_wrong_evidence', 'symlink'])
def test_bundle_corruption_rejected(tmp_path, fault):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    portable.export(root, target)
    manifest = json.loads((target / 'bundle.json').read_text())
    evidence = next(iter(manifest['evidence_map'].values()))
    if fault == 'missing':
        (target / evidence).unlink()
    elif fault == 'extra':
        (target / 'unindexed.txt').write_text('extra')
    elif fault in ('evidence', 'self_consistent_wrong_evidence'):
        (target / evidence).write_text('changed')
        if fault == 'self_consistent_wrong_evidence':
            manifest['files'][evidence] = portable.fingerprint(target / evidence)
            save(target / 'bundle.json', manifest)
    elif fault == 'cas':
        next(p for p in (target / 'dataset/cas').rglob('*') if p.is_file()).write_text('changed')
    elif fault == 'unsafe_map':
        key = next(iter(manifest['evidence_map']))
        manifest['evidence_map'][key] = '../outside'
        save(target / 'bundle.json', manifest)
    elif fault == 'partial_map':
        manifest['evidence_map'].clear()
        save(target / 'bundle.json', manifest)
    elif fault == 'symlink':
        payload = target / evidence
        external = tmp_path / 'external'
        payload.rename(external)
        payload.symlink_to(external)
    with pytest.raises((ValueError, FileNotFoundError)):
        portable.verify(target)


def test_copy_failure_does_not_publish_or_overwrite(tmp_path, monkeypatch):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    def fail(*_):
        raise OSError('injected fsync failure')
    monkeypatch.setattr(portable.os, 'fsync', fail)
    with pytest.raises(OSError, match='fsync'):
        portable.export(root, target)
    assert not target.exists()
    assert list(tmp_path.glob('.bundle.staging-*'))
    assert v2.verify(root, deep=True)['valid']


def test_existing_destination_is_preserved(tmp_path):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    target.mkdir()
    keep = target / 'keep'
    keep.write_text('existing bytes')
    with pytest.raises(ValueError, match='exists'):
        portable.export(root, target)
    assert keep.read_text() == 'existing bytes'


def test_explicit_resolver_never_falls_back_to_existing_source(tmp_path):
    root, _, _, _ = publication(tmp_path)
    with pytest.raises(ValueError, match='exactly'):
        v2.verify(root, deep=True, evidence_paths={})


def test_selectors_use_relocated_bytes(tmp_path):
    root, evidence, body, _ = publication(tmp_path)
    extra = tmp_path / 'observations.json'
    extra.write_text('{"cases":[{"result":"passed"}]}')
    ref = evidence.file(extra, selector='/cases/0/result')
    body['intervention']['evidence_ids'].append(ref)
    v2.publish(root, {'attempt': body}, lambda _: {}, evidence, {})
    target = tmp_path / 'bundle'
    portable.export(root, target)
    extra.unlink()
    assert portable.verify(target)['valid']


def test_v2_graph_associations_are_resolved_inside_bundle(tmp_path):
    root, evidence, body, _ = publication(tmp_path)
    graph = tmp_path / 'graph.json'
    graph.write_bytes(v2.canonical({'graph_version': 'v0002', 'nodes': [{'id': 'test.node'}]}))
    ref = evidence.file(graph)
    metadata = {'graph_snapshots': {'v0002': [{
        'content_hash': v2.digest_bytes(graph.read_bytes()[:-1]), 'evidence_id': ref}]}}
    item = {'id': 'lesson', 'kind': 'operator_optimization', 'operator': 'op', 'split': 'train',
        'title': 'Synthetic association', 'intervention': {'statement': 'Synthetic', 'basis': 'test'},
        'graph_links': [{'graph_version': 'v0002', 'node_id': 'test.node', 'basis': 'test'}]}
    v2.publish(root, {'attempt': body},
               lambda memories: v2.normalize_lessons([item], memories, evidence), evidence, metadata)
    target = tmp_path / 'bundle'
    portable.export(root, target)
    graph.unlink()
    assert portable.verify(target)['lessons'] == 1


@pytest.mark.parametrize('value', ['../x', '/absolute', 'a/../b', './a', ''])
def test_paths_cannot_escape_bundle(tmp_path, value):
    with pytest.raises(ValueError, match='path'):
        portable.inside(tmp_path, value)


@pytest.mark.parametrize('revision', ['../outside', '/outside', 'a' * 63, 'G' * 64])
def test_invalid_revision_is_rejected_before_reading_revision_files(tmp_path, monkeypatch, revision):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    portable.export(root, target)
    manifest = json.loads((target / 'bundle.json').read_bytes())
    manifest['revision'] = revision
    save(target / 'dataset/current.json', {key: manifest[key] for key in ('revision', 'manifest_hash')})
    manifest['files']['dataset/current.json'] = portable.fingerprint(target / 'dataset/current.json')
    save(target / 'bundle.json', manifest)
    original = Path.read_bytes
    def guarded(path):
        if path.name in ('evidence_index.json', 'record_objects.json', 'contexts.json'):
            pytest.fail('invalid revision reached a revision file read')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    with pytest.raises(ValueError, match='revision pointer'):
        portable.verify(target)


def test_corrupt_retained_historical_cas_cannot_be_blessed_by_outer_inventory(tmp_path):
    root, evidence, _, _ = publication(tmp_path)
    # Publishing an empty current view retains its old record object map.
    v2.publish(root, {}, lambda _: {}, evidence, {})
    target = tmp_path / 'bundle'
    portable.export(root, target)
    pointer = json.loads((target / 'dataset/current.json').read_bytes())
    objects = json.loads((target / 'dataset/revisions' / pointer['revision'] / 'record_objects.json').read_bytes())
    digest = next(iter(objects.values()))
    path = v2.object_path(target / 'dataset', digest)
    path.write_bytes(b'corrupted retained historical record')
    manifest = json.loads((target / 'bundle.json').read_bytes())
    manifest['files'][path.relative_to(target).as_posix()] = portable.fingerprint(path)
    save(target / 'bundle.json', manifest)
    with pytest.raises(ValueError, match='CAS filename/content hash'):
        portable.verify(target)


def test_unreferenced_cas_is_rejected_even_when_outer_inventory_binds_it(tmp_path):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    portable.export(root, target)
    payload = b'extra unreferenced CAS object'
    path = v2.object_path(target / 'dataset', v2.digest_bytes(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    manifest = json.loads((target / 'bundle.json').read_bytes())
    manifest['files'][path.relative_to(target).as_posix()] = portable.fingerprint(path)
    save(target / 'bundle.json', manifest)
    with pytest.raises(ValueError, match='CAS closure'):
        portable.verify(target)


def test_corrupt_retained_source_cas_cannot_publish_destination(tmp_path):
    root, evidence, _, _ = publication(tmp_path)
    v2.publish(root, {}, lambda _: {}, evidence, {})
    pointer = json.loads((root / 'current.json').read_bytes())
    objects = json.loads((root / 'revisions' / pointer['revision'] / 'record_objects.json').read_bytes())
    v2.object_path(root, next(iter(objects.values()))).write_bytes(b'corrupt historical source')
    target = tmp_path / 'bundle'
    with pytest.raises(ValueError, match='CAS filename/content hash'):
        portable.export(root, target)
    assert not target.exists()


def test_moved_legacy_graph_associations_use_only_bundle_snapshot(tmp_path, monkeypatch):
    root, evidence, body, _ = publication(tmp_path)
    item = {'id': 'legacy-lesson', 'kind': 'operator_optimization', 'operator': 'op', 'split': 'train',
        'title': 'Legacy graph association', 'intervention': {'statement': 'Synthetic', 'basis': 'test'},
        'graph_links': [{'graph_version': 'v0001', 'node_id': 'anchor.ai_core_utilization', 'basis': 'test'}]}
    v2.publish(root, {'attempt': body},
               lambda memories: v2.normalize_lessons([item], memories, evidence), evidence, {})
    target = tmp_path / 'bundle'
    portable.export(root, target)
    monkeypatch.setattr(v2, 'ROOT', tmp_path / 'absent-historical-checkout')
    shutil.rmtree(root)
    for row in evidence.entries.values():
        Path(row['path']).unlink()
    assert portable.verify(target)['lessons'] == 1
    completed = subprocess.run([sys.executable, str(target / 'verifier/trace_v2_portable.py'),
        'verify', '--bundle', str(target)], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)['lessons'] == 1
    # Even a self-consistent outer file list cannot recover a missing graph node
    # from a historical checkout once the explicit graph resolver is supplied.
    manifest = json.loads((target / 'bundle.json').read_bytes())
    graph_name = 'skillgraph/versions/v0001/graph.json'
    (target / graph_name).unlink()
    del manifest['files'][graph_name]
    save(target / 'bundle.json', manifest)
    with pytest.raises(ValueError, match='unknown graph node'):
        portable.verify(target)


def test_publication_rename_failure_keeps_source_and_unpublished_staging(tmp_path, monkeypatch):
    root, _, _, _ = publication(tmp_path)
    target = tmp_path / 'bundle'
    def fail(*_):
        raise OSError('injected publication rename failure')
    monkeypatch.setattr(portable.os, 'rename', fail)
    with pytest.raises(OSError, match='publication rename'):
        portable.export(root, target)
    assert not target.exists()
    staging = list(tmp_path.glob('.bundle.staging-*'))
    assert len(staging) == 1 and portable.verify(staging[0])['valid']
    assert v2.verify(root, deep=True)['valid']

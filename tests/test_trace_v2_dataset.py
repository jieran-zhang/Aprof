import builtins
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import trace_v2_dataset as v2


def fixture_data(tmp_path):
    e = v2.Evidence()
    source = tmp_path / 'source.txt'; source.write_text('baseline\ncandidate\n')
    ref = e.file(source); h = e.entries[ref]['sha256']
    ctx = e.context({'workload': 'fixture'})
    body = {
        'identity': {'run_id': 'test', 'task_id': 'op', 'candidate_id': 'op-001', 'operator': 'op', 'split': 'train'},
        'sources': {'original_baseline': h, 'direct_parent': h, 'candidate': h, 'patch': h, 'parent_attempt_id': None, 'evidence_ids': [ref]},
        'context_ref': ctx, 'knowledge': {'catalog_ref': ctx, 'actual_reads': [], 'classification_note': 'fixture'},
        'diagnosis': {'symptoms': [], 'hypotheses': [], 'missing_evidence': ['unmeasured'], 'retrospective': True, 'evidence_ids': [ref]},
        'intervention': v2.fact('edit', 'fixture edit', [ref], 'source'),
        'evaluations': [{'id': 'ev1', 'run_id': 'test', 'session_id': 'session', 'relation': 'original_attempt',
                         'comparison': {'baseline': h, 'candidate': h}, 'stages': [], 'measurement_quality': 'not_admitted',
                         'summary': {}, 'cases': [], 'evidence_ids': [ref]}],
        'machine_results': [{'evaluation_id': 'ev1', 'verdict': 'measurement_unstable', 'first_failed_stage': 'timing',
                             'graph_policy_eligible': False, 'episode_ref': None, 'evidence_ids': [ref], 'metrics': {}}],
        'timeline': [], 'next_decision': {'action': 'paused', 'reason': 'fixture', 'evidence_ids': []},
        'provenance': {'retrospective': True, 'source_record_refs': [ref], 'importer_hash': h,
                       'knowledge_state': 'unresolved', 'null_reasons': {'sources.parent_attempt_id': 'original baseline'}}}
    return e, body


def publication(tmp_path):
    e, body = fixture_data(tmp_path)
    root = tmp_path/'dataset'
    result = v2.publish(root, {'attempt': body}, lambda rows: {}, e, {'hardware_executed': False})
    return root, e, body, result


def test_finite_and_duplicate_json():
    for raw in ('{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'):
        with pytest.raises(ValueError): v2.strict_loads(raw)
    with pytest.raises(ValueError): v2.canonical({'nested': [float('nan')]})
    assert v2.finite_tags(float('inf')) == {'special_value': '+Inf'}


def test_closed_structures_and_fact_basis(tmp_path):
    _, body = fixture_data(tmp_path)
    body['diagnosis']['invented'] = []
    with pytest.raises(ValidationError): v2.seal('optimization_memory', 'a', body)
    f = v2.fact('f', {'statement': 'less than 3% regression', 'basis': 'measured'})
    assert f['basis'] == 'measured' and 'statement' not in f['attributes']


def test_hash_tamper(tmp_path):
    _, body = fixture_data(tmp_path)
    r = v2.seal('optimization_memory', 'a', body)
    r['body']['next_decision']['reason'] = 'changed'
    with pytest.raises(ValueError, match='hash'): v2.validate_record(r)


def test_publish_idempotence_revision_cas_and_read_only_verify(tmp_path, monkeypatch):
    root, e, body, result = publication(tmp_path)
    original = (root/'current.json').read_bytes()
    assert v2.publish(root, {'attempt': body}, lambda rows: {}, e, {'hardware_executed': False}) == result
    assert (root/'current.json').read_bytes() == original
    body['next_decision']['reason'] = 'new observation'
    v2.publish(root, {'attempt': body}, lambda rows: {}, e, {'hardware_executed': False})
    row = v2.previous_records(root)['attempt']
    assert row['revision'] == 2 and row['previous_ref']
    original_open = builtins.open; original_path_open = Path.open
    def checked_open(path, mode='r', *a, **kw):
        assert not any(flag in mode for flag in ('w', 'a', 'x', '+'))
        return original_open(path, mode, *a, **kw)
    def checked_path_open(path, mode='r', *a, **kw):
        assert not any(flag in mode for flag in ('w', 'a', 'x', '+'))
        return original_path_open(path, mode, *a, **kw)
    monkeypatch.setattr(builtins, 'open', checked_open)
    monkeypatch.setattr(Path, 'open', checked_path_open)
    monkeypatch.setattr(v2.sqlite3, 'connect', lambda *a, **k: pytest.fail('verify opened SQLite'))
    assert v2.verify(root, deep=True)['valid']


@pytest.mark.parametrize('fault', ['baseline', 'source_ref', 'duplicate_outcome', 'parent'])
def test_invalid_projection_cannot_replace_current(tmp_path, fault):
    root, e, body, _ = publication(tmp_path)
    before = (root/'current.json').read_bytes()
    if fault == 'baseline': body['evaluations'][0]['comparison']['baseline'] = 'sha256:'+'f'*64
    if fault == 'source_ref': body['sources']['evidence_ids'] = []
    if fault == 'duplicate_outcome': body['machine_results'].append(deepcopy(body['machine_results'][0]))
    if fault == 'parent': body['sources']['parent_attempt_id'] = 'absent'
    with pytest.raises(ValueError): v2.publish(root, {'attempt': body}, lambda rows: {}, e, {'hardware_executed': False})
    assert (root/'current.json').read_bytes() == before
    assert v2.verify(root)['valid']


def test_interrupted_publication_stays_on_previous(tmp_path, monkeypatch):
    root, e, body, _ = publication(tmp_path)
    before = (root/'current.json').read_bytes()
    body['next_decision']['reason'] = 'next'
    def fail(*args): raise OSError('injected atomic commit interruption')
    monkeypatch.setattr(v2.os, 'replace', fail)
    with pytest.raises(OSError): v2.publish(root, {'attempt': body}, lambda rows: {}, e, {})
    assert (root/'current.json').read_bytes() == before
    assert v2.verify(root)['valid']


def test_selectors_and_external_mutation(tmp_path):
    p = tmp_path/'rows.jsonl'; p.write_text('{"cases":[{"p":2}]}\n')
    v2.validate_selector('line 1 /cases/0/p', p)
    with pytest.raises((ValueError, IndexError)): v2.validate_selector('line:2', p)
    with pytest.raises(KeyError): v2.validate_selector('line 1 /missing', p)
    root, e, _, _ = publication(tmp_path)
    Path(next(iter(e.entries.values()))['path']).write_text('changed')
    with pytest.raises(ValueError, match='external evidence'): v2.verify(root, deep=True)


def test_missing_revision_link(tmp_path):
    _, body = fixture_data(tmp_path)
    row = v2.seal('optimization_memory', 'one', body)
    with pytest.raises(ValueError): v2.seal('optimization_memory', 'other', body, row)


@pytest.mark.skipif(not (ROOT/'.aprof/runs/level1-serial-final-20260908T011500Z').exists(), reason='local historical fixture absent')
def test_real_import_identity_and_measurement_continuation():
    parent = ROOT/'.aprof/runs/level1-20260907T152600Z'
    serial = ROOT/'.aprof/runs/level1-serial-final-20260908T011500Z'
    evidence = v2.Evidence((parent, serial))
    rows = v2.import_memories(parent, serial, evidence)
    assert len(rows) == 24
    assert sum(len(r['evaluations']) == 2 for r in rows.values()) == 3
    assert all(r['evaluations'][0]['measurement_quality'] == 'not_admitted' for r in rows.values())
    norm = next(r for r in rows.values() if r['identity']['candidate_id'] == 'foreach_norm-002')
    assert len(norm['evaluations'][1]['cases']) == 20
    assert len([c for c in norm['evaluations'][1]['cases'] if c['regression'] > 0]) == 7
    assert norm['sources']['parent_attempt_id'] is None
    assert 0 < len(norm['knowledge']['actual_reads']) < 100

from __future__ import annotations

from collections import Counter
import inspect
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import archive_level1_method_study as archive
import aprof_runtime.store as store_module
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore
from cannbench_device_timing import summarize_multicase
from run_level1_serial import compare_controls


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


@pytest.fixture
def method_run(tmp_path):
    parent = tmp_path / 'immutable-parent'
    run = tmp_path / 'level1-capture-probe-20260908T005000Z'
    baseline = parent / 'tasks/exp/baseline'
    (baseline / 'build').mkdir(parents=True)
    (baseline / 'build/exp').write_bytes(b'CPU fixture executable identity')
    source = parent / 'source.tar'
    source.write_bytes(b'CPU fixture original exp source snapshot')
    with EpisodeStore(parent / 'train/episodes.sqlite') as store:
        source_ref = store.register_artifact(source)
    dump(run / 'run-manifest.json', {
        'parent_run': str(parent), 'candidates': {'exp': [{'source_hashes': {'baseline': source_ref}}]},
    })
    dump(run / 'method_study.json', {'kind': 'measurement_method_study', 'status': 'rejected',
        'candidate_measurements': 0, 'next_experiment': 'Investigate one live context.'})
    producer = run / 'setup/cannbench_device_timing.py'
    producer.parent.mkdir(parents=True)
    producer.write_text('from cannbench_device_timing import summarize_multicase\n')
    (run / 'setup/run_level1_serial.py').write_text(
        'import math\nimport statistics\nCASES = [1, 8, 14, 20]\n' + inspect.getsource(compare_controls))
    metadata = {}
    for case in archive.CASES:
        directory = parent / 'tasks/exp/prepared' / f'case_{case:02d}'
        directory.mkdir(parents=True)
        input_path = directory / 'input.bin'
        input_path.write_bytes(bytes([case]))
        metadata_path = directory / 'metadata.json'
        dump(metadata_path, {'case_id': case, 'input': str(input_path)})
        metadata[case] = (metadata_path, input_path)
    reports = []
    report_paths = []
    for name in ('normal', 'reverse'):
        directory = run / 'calibration' / name
        records = []
        for case in archive.CASES:
            for index in range(30):
                sample = {'unit': 'ns', 'source': 'acl_event', 'elapsed_ns': 100.0, 'device': 0,
                          'sample_index': index, 'warmup': 10, 'repeat': 100}
                records.append({'case_id': case, 'round': index, 'device': 0,
                    'order': ['baseline', 'candidate'] if index % 2 == 0 else ['candidate', 'baseline'],
                    'baseline': sample, 'candidate': {**sample, 'elapsed_ns': 104.0}})
        raw = {'operator': 'exp', 'case_ids': archive.CASES, 'complete': True,
            'source': 'acl_event', 'unit': 'ns', 'device': 0, 'pairs': 30, 'warmup': 10, 'repeat': 100,
            'baseline_executable_sha256': file_hash(baseline / 'build/exp'),
            'candidate_executable_sha256': file_hash(baseline / 'build/exp'),
            'producer_sha256': file_hash(producer), 'records': records,
            'case_executions': [{'case_id': case, 'metadata_path': str(paths[0]),
                'metadata_sha256': file_hash(paths[0]), 'input_hashes': {'input': file_hash(paths[1])}}
                for case, paths in metadata.items()]}
        report = summarize_multicase(raw, archive.CASES)
        assert report['stable']
        dump(directory / 'raw_measurements.json', raw)
        dump(directory / 'measurement_report.json', report)
        for label in ('stdout', 'stderr'):
            (directory / (label + '.log')).write_text('original ' + label)
        dump(directory / 'execution.json', {
            'argv': ['python', str(producer), 'measure', '--baseline', str(baseline), '--candidate', str(baseline)],
            'cwd': str(run), 'host': 'original-host', 'physical_device': 0, 'status': 'passed', 'exit_status': 0,
            'started_at': '2026-09-08T00:00:00Z', 'finished_at': '2026-09-08T00:00:10Z',
            'timing_producer_sha256': file_hash(producer),
            'stdout': {'path': '/tmp/retired/stdout.log', 'sha256': file_hash(directory / 'stdout.log')},
            'stderr': {'path': '/tmp/retired/stderr.log', 'sha256': file_hash(directory / 'stderr.log')},
        })
        reports.append(report)
        report_paths.append(str(directory / 'measurement_report.json'))
    dump(run / 'selection.json', {**compare_controls(*reports), 'artifact_paths': report_paths})
    heldout_input = parent / 'tasks/gelu/heldout-input.bin'
    heldout_input.parent.mkdir(parents=True)
    heldout_input.write_bytes(b'HELDOUT INPUT MUST NEVER BE IMPORTED')
    dump(run / 'setup/input-bindings.json', {'inputs': {'gelu': {'1': {str(heldout_input): file_hash(heldout_input)}}}})
    dump(run / 'setup/verifier-qualification/qualification.json', {
        'all_exact_result_and_exit_matches': True, 'old_sources_metadata_results_unchanged': True,
        'operator_count': 2, 'rows': [{'operator': 'gelu', 'precision_value': 123.456, 'input': str(heldout_input)}],
    })
    dump(run / 'setup/verifier-qualification/gelu/result.json', {'precision_value': 123.456})
    initial = run / 'setup/verifier-qualification-initial/foreach_norm'
    for mode in ('subprocess', 'reuse-1'):
        dump(initial / mode / 'result.json', {'passed': True})
        (initial / mode / 'verify.log').write_text(('redis/hiredis UserWarning\n' if mode == 'subprocess' else '') + 'passed\n')
    return run, parent, heldout_input


def test_method_archive_has_zero_attempts_real_execution_times_and_readonly_parent(method_run):
    run, parent, heldout_input = method_run
    parent_before = {str(path.relative_to(parent)): path.read_bytes() for path in parent.rglob('*') if path.is_file()}
    result = archive.archive(run)
    assert result['valid'] and result['attempt_count'] == result['episode_count'] == 0
    events = [json.loads(line) for line in (run / 'train/trace_events.jsonl').read_text().splitlines()]
    assert all(row['candidate_id'] is None and row['attempt_id'] is None for row in events)
    assert events[-1]['payload']['status'] == 'blocked'
    measured = [row for row in events if row['payload'].get('stage', '').startswith('aa/')]
    assert len(measured) == 2
    for row in measured:
        assert row['timestamp'] != row['payload']['execution']['started_at']
        assert row['payload']['execution']['started_at'] == '2026-09-08T00:00:00Z'
        assert row['payload']['execution']['finished_at'] == '2026-09-08T00:00:10Z'
    assert (run / 'train/optimization_traces.jsonl').read_bytes() == b''
    assert (run / 'train/episodes.jsonl').read_bytes() == b''
    assert parent_before == {str(path.relative_to(parent)): path.read_bytes() for path in parent.rglob('*') if path.is_file()}
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        assert not store.object_path(file_hash(heldout_input)).exists()
        assert not store.object_path(file_hash(run / 'setup/verifier-qualification/gelu/result.json')).exists()
        assert not store.object_path(file_hash(run / 'setup/verifier-qualification/qualification.json')).exists()
    with EpisodeStore(run / 'validation/episodes.sqlite') as store:
        store.verify_artifact(file_hash(run / 'setup/verifier-qualification/gelu/result.json'))
        assert not store.object_path(file_hash(heldout_input)).exists()
    assert archive.archive(run) == result


def test_verification_hashes_each_unique_cas_object_once_and_detects_tampering(method_run, monkeypatch):
    run, _, _ = method_run
    archive.archive(run)
    counts = Counter()
    original = store_module.file_hash

    def count_hash(path):
        path = Path(path)
        if '.sqlite.objects' in str(path):
            counts[str(path)] += 1
        return original(path)

    monkeypatch.setattr(store_module, 'file_hash', count_hash)
    monkeypatch.setattr(archive, 'file_hash', count_hash)
    result = archive.verify(run)
    assert len(counts) == result['unique_train_artifacts_verified'] + result['unique_validation_artifacts_verified']
    assert set(counts.values()) == {1}
    decision = archive.read(run / 'method_archive/decision.json')
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        path = store.object_path(decision['sessions'][0]['raw_ref'])
        path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(StoreError, match='CAS object content'):
        archive.verify(run)


def test_heldout_index_is_mandatory_and_anchored(method_run):
    run, _, _ = method_run
    archive.archive(run)
    index = run / 'validation/method_evidence_index.json'
    original = index.read_bytes()
    index.unlink()
    with pytest.raises(StoreError, match='required held-out'):
        archive.verify(run)
    index.write_bytes(original + b'\n')
    with pytest.raises(StoreError, match='differs from its train trace anchor'):
        archive.verify(run)


def test_archive_recovers_missing_report_and_uses_frozen_admission_code(method_run, monkeypatch):
    run, _, _ = method_run
    result = archive.archive(run)
    report = run / 'method_archive/report.md'
    original = report.read_bytes()
    report.unlink()
    monkeypatch.setattr(archive, 'compare_controls', lambda *args: pytest.fail('live admission code must not run'))
    monkeypatch.setattr(archive, 'CASES', [999])
    assert archive.archive(run) == result
    assert report.read_bytes() == original


@pytest.mark.parametrize('violation', ['accepted', 'candidate_execution', 'different_binary', 'different_baseline_path', 'changed_report'])
def test_method_archive_refuses_false_zero_candidate_or_aa_claims(method_run, violation):
    run, _, _ = method_run
    if violation == 'accepted':
        path = run / 'selection.json'
        value = archive.read(path)
        value['accepted'] = True
    elif violation == 'candidate_execution':
        path = run / 'tasks/exp/measurements/001/execution.json'
        value = {'status': 'passed'}
    elif violation == 'different_binary':
        path = run / 'calibration/normal/raw_measurements.json'
        value = archive.read(path)
        value['candidate_executable_sha256'] = 'sha256:' + 'f' * 64
    elif violation == 'different_baseline_path':
        path = run / 'calibration/normal/execution.json'
        value = archive.read(path)
        value['argv'][-1] = '/some/optimized/candidate'
    else:
        path = run / 'calibration/normal/measurement_report.json'
        value = archive.read(path)
        value['per_case'][0]['speedup'] = 2.0
    dump(path, value)
    with pytest.raises(StoreError):
        archive.archive(run)
    assert not (run / 'method_archive/verification.json').exists()

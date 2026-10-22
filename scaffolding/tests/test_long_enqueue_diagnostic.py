"""CPU trust-boundary checks for the one-cycle diagnostic; no device launch."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'collection/scripts'
sys.path.insert(0, str(SCRIPTS))
import diagnose_long_enqueue as diagnostic


def sample():
    def point(wall):
        return {'wall_ns': wall, 'thread_cpu_ns': wall,
                'rusage': {key: wall for key in diagnostic.USAGE}}

    boundaries = ((110, 150), (200, 900), (910, 930), (940, 960))
    segments = {name: {'before': point(a), 'after': point(b)}
                for name, (a, b) in zip(diagnostic.SEGMENTS, boundaries, strict=True)}
    checkpoints = [{'completed_launches': index * 100, 'wall_ns': 300 + index * 7,
                    'thread_cpu_ns': 300 + index * 7} for index in range(1, 74)]
    return {'implementation': 'baseline', 'launches_per_operator': 1,
            'elapsed_ms': 150.0, 'elapsed_ns': 150e6 / diagnostic.REPEAT,
            'started_monotonic_ns': 100, 'finished_monotonic_ns': 1000,
            'submission_diagnostic': {'schema_version': 1, 'checkpoint_interval': 100,
                                      'segments': segments, 'enqueue_checkpoints': checkpoints}}


def test_missing_checkpoint_and_reversed_counter_rejected():
    original = sample()
    assert len(diagnostic._sample(original, 'baseline')['checkpoint_intervals']) == 73
    missing_sample = copy.deepcopy(original)
    del missing_sample['submission_diagnostic']
    with pytest.raises(ValueError, match='missing diagnostic sample'):
        diagnostic._sample(missing_sample, 'baseline')
    missing = copy.deepcopy(original)
    missing['submission_diagnostic']['enqueue_checkpoints'].pop()
    with pytest.raises(ValueError, match='checkpoints'):
        diagnostic._sample(missing, 'baseline')
    late_cpu = copy.deepcopy(original)
    late_cpu['submission_diagnostic']['enqueue_checkpoints'][-1]['thread_cpu_ns'] = 901
    with pytest.raises(ValueError, match='last checkpoint'):
        diagnostic._sample(late_cpu, 'baseline')
    reversed_counter = copy.deepcopy(original)
    reversed_counter['submission_diagnostic']['segments']['enqueue']['after']['rusage']['nvcsw'] = 1
    with pytest.raises(ValueError, match='counters reversed'):
        diagnostic._sample(reversed_counter, 'baseline')


def test_changed_frozen_file_rejected(tmp_path):
    path = tmp_path / 'input.bin'
    path.write_bytes(b'original')
    frozen = diagnostic.file_bindings((path,))
    diagnostic.verify_bindings(frozen)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='frozen file changed'):
        diagnostic.verify_bindings(frozen)


def test_freeze_rejects_incomplete_failed_campaign(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, '_check_plan', lambda output, plan: None)
    output = tmp_path / 'diagnostic'
    output.mkdir()
    predecessor = tmp_path / 'predecessor'
    (predecessor / 'campaign').mkdir(parents=True)
    order = ['exp-confirmation', 'exp-timeline-01', 'exp-timeline-09',
             'sigmoid-confirmation', 'sigmoid-timeline-01', 'sigmoid-timeline-04']
    (predecessor / 'roster.json').write_text(json.dumps({'order': order}))
    (predecessor / 'campaign/campaign.json').write_text(json.dumps({
        'accepted': False, 'resampling': 'none', 'slots': {'exp-confirmation': {}}}))
    source = output / 'source'
    (source / 'build').mkdir(parents=True)
    binary = source / 'build/exp'
    binary.write_bytes(b'build output')
    (output / 'plan.json').write_text(json.dumps({
        'predecessor': str(predecessor), 'original_source_files': {}, 'source_files': {},
        'input_files': {}, 'producer_files': {}, 'source_dir': str(source)}))
    (output / 'build-started.json').write_text(json.dumps({
        'plan': diagnostic.binding(output / 'plan.json'), 'environment': {'ASCEND_HOME_PATH': '/synthetic'}}))
    for index in range(2):
        (output / f'build-{index}.log').write_text('synthetic receipt fixture')
    commands = [
        ['cmake', '-S', str(source), '-B', str(source / 'build'), '-DCMAKE_BUILD_TYPE=Release'],
        ['cmake', '--build', str(source / 'build'), '-j2']]
    (output / 'build-terminal.json').write_text(json.dumps({
        'status': 'passed', 'environment': {'ASCEND_HOME_PATH': '/synthetic'}, 'commands': [
            {'argv': argv, 'exit_status': 0, 'log': diagnostic.binding(output / f'build-{index}.log')}
            for index, argv in enumerate(commands)], 'binary': diagnostic.binding(binary)}))
    with pytest.raises(ValueError, match='failure campaign incomplete'):
        diagnostic.freeze(output)
    assert not (output / 'freeze.json').exists()


def test_duplicate_run_rejected_before_native_start(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, 'ROOT', tmp_path)
    monkeypatch.setattr(diagnostic, '_check_plan', lambda output, plan: None)
    output = tmp_path / 'diagnostic'
    output.mkdir()
    (output / 'plan.json').write_text('{}')
    (output / 'freeze.json').write_text(json.dumps({
        'created_at': 1, 'predecessor_campaign': {'path': 'historical', 'sha256': 'sha256:' + '0' * 64}}))
    (output / 'started.json').write_text('{}')
    anchor = tmp_path / 'scaffolding/curation/one-cycle-anchor.json'
    anchor.parent.mkdir(parents=True)
    anchor.write_text(json.dumps({'schema_version': 1, 'purpose': diagnostic.PURPOSE,
                                  'freeze': diagnostic.binding(output / 'freeze.json'),
                                  'predecessor_campaign': {'path': 'historical', 'sha256': 'sha256:' + '0' * 64},
                                  'max_attempts': 1, 'resampling': 'none',
                                  'recorded_at_utc': datetime.now(timezone.utc).isoformat()}))
    with pytest.raises(ValueError, match='already attempted'):
        diagnostic.run(output, anchor)


def test_diagnostic_summary_cannot_claim_publication():
    rows = [{'phase': phase, 'role': role, 'elapsed_ms': 150.0}
            for phase in diagnostic.PHASES for _ in range(5) for role in diagnostic.ROLES]
    summary = diagnostic._summary(rows)
    assert summary['event_count'] == 30
    assert summary['accepted'] is False
    assert summary['publication_acceptance'] is False
    assert summary['measurement_admission_eligible'] is False

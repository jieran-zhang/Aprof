"""Historical identities and complete descriptive windows cannot grant admission."""
from decimal import Decimal
import csv
import json
from pathlib import Path

import pytest

import diagnose_exp_case1_prewarm as prewarm
import replay_local_task_history_supplement as history
from measurement_source_archive import HistoricalEvidence
from replay_timing_diagnosis import Evidence, digest


def write(path, value):
    path.write_text(json.dumps(value))
    return {'path': str(path), 'sha256': digest(path)}


def test_old_producer_resolves_only_in_explicit_history_path(tmp_path, monkeypatch):
    binary = tmp_path / 'binary'; binary.write_bytes(b'binary')
    old = tmp_path / 'old.py'; old.write_bytes(b'old frozen producer')
    source = str(Path(prewarm.__file__).resolve())
    index = write(tmp_path / 'index.json', {'schema_version': 1, 'not_a_release': True,
                   'files': {source: {'path': str(old), 'sha256': digest(old)}}})
    plan_path = tmp_path / 'plan.json'; plan_ref = write(plan_path, {})
    frozen = {'purpose': prewarm.PURPOSE, 'plan': plan_ref, 'matrix': [], 'accepted': False,
              'publication_acceptance': False, 'frozen_files': {source: digest(old), str(binary): digest(binary)}}
    write(tmp_path / 'freeze.json', frozen)
    monkeypatch.setattr(prewarm, '_checked_plan', lambda _: ({'matrix': [], 'B_binary': str(binary)}, {}))
    with pytest.raises(ValueError, match='frozen diagnostic file changed'):
        prewarm._checked_freeze(tmp_path)
    resolver = HistoricalEvidence([index], logical_paths=True)
    assert prewarm._checked_freeze(tmp_path, historical_evidence=resolver)[2] == frozen
    assert resolver.resolved_files[source]['path'] == str(old)


def test_history_cannot_substitute_current_pure_parser(tmp_path):
    index = write(tmp_path / 'index.json', {'schema_version': 1, 'not_a_release': True,
        'files': {str(prewarm.RELEASE / 'runtime/src/aprof_runtime/task_timing.py'):
                  {'path': str(tmp_path / 'old.py'), 'sha256': 'sha256:' + '0' * 64}}})
    write(tmp_path / 'freeze.json', {'frozen_files': {
        str(prewarm.RELEASE / 'runtime/src/aprof_runtime/task_timing.py'): 'sha256:' + '0' * 64}})
    with pytest.raises(ValueError, match='changed evidence'):
        prewarm.replay(tmp_path, tmp_path / 'unused-anchor.json', source_archive_refs=[index])


def test_analysis_retains_tail_and_complete_boundary_grid():
    tasks = [{'start_us': Decimal(i * 10), 'end_us': Decimal(i * 10 + 4), 'duration_us': Decimal(4)}
             for i in range(4222)]
    blocks, windows, summary = history.analysis_rows('cycle-0-A', tasks, 0)
    assert len(blocks[100]) == 43 and blocks[100][-1]['task_count'] == 22
    assert len(blocks[400]) == 11 and blocks[400][-1]['task_count'] == 222
    assert [row['boundary_full_index'] for row in windows] == list(range(400, 3801, 100))
    assert all(row['delta_us'] == 0 for row in windows)
    assert summary['stage_means_us'] == {key: 4.0 for key in ('warmup', 'untimed_snapshot',
        'aa_before_prime', 'aa_before_pairs', 'formal_prime', 'formal_pairs', 'aa_after_prime', 'aa_after_pairs')}


@pytest.mark.parametrize('mutation', ['drop', 'duplicate', 'change'])
def test_descriptive_csv_rejects_selection_or_changed_mean(tmp_path, mutation):
    expected = [{'slot': 'B', 'scope': 'native', 'index': 0, 'mean': 4.0},
                {'slot': 'B', 'scope': 'native', 'index': 1, 'mean': 5.0}]
    rows = [dict(row) for row in expected]
    if mutation == 'drop': rows.pop()
    elif mutation == 'duplicate': rows.append(dict(rows[0]))
    else: rows[1]['mean'] = 4.9
    path = tmp_path / 'blocks.csv'
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(expected[0])); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError, match='omitted or duplicated|changed raw arithmetic'):
        history._check_csv(path, expected, ('slot', 'scope', 'index'), Evidence())


def test_supplement_cannot_be_relabelled_as_publication(tmp_path):
    reference = write(tmp_path / 'history.json', {'schema_version': 1, 'not_a_release': True,
        'eligible_for_publication': True, 'purpose': 'explicit_history_source_supplement_for_future_protocol_registration'})
    with pytest.raises(ValueError, match='historical-only'):
        history.replay_local_task_history_supplement(reference)


def test_floating_serialization_tolerance_is_not_a_relaxed_gate():
    assert history._same({'x': 6.00455 + 1e-15}, {'x': 6.00455})
    assert not history._same({'x': 6.00455 + 1e-4}, {'x': 6.00455})
    assert not history._same({'x': float('nan')}, {'x': 6.00455})

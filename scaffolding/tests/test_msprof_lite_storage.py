"""CPU-only versioned storage roundtrip, including repository-free portable replay."""
import contextlib
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import level2_raw_archive_storage as raw
import level2_storage as dedup
import level2_native_output_storage as native
import level2_verification_storage as verification
import msprof_raw_storage as transport
import msprof_exploration_report as report
import trace_v2_portable as portable
from msprof_storage_protocol import cohort_process_count
from msprof_search_protocol import LITE_PROTOCOL, LITE_ANALYSIS, LITE_PRODUCER, LITE_DESIGN
from msprof_exploration_execute import event
from test_msprof_search_lite import lite_cohort
from test_msprof_raw_storage import localize
from test_level2_raw_storage_integration import dataset_for
from verification_authority_fixture import anchor


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def declaration():
    plan = {'protocol': LITE_PROTOCOL, 'analysis_version': LITE_ANALYSIS, 'schedule': []}
    for number, design in enumerate(LITE_DESIGN):
        plan['schedule'].append({'name': f'p{number + 1:02d}', 'request': {
            'version': LITE_PRODUCER, **dict(zip(('load_order', 'first_order', 'buffer_configs'), design))}})
    result = {'protocol': LITE_PROTOCOL, 'analysis_version': LITE_ANALYSIS,
              'formal_admission': 'not_evaluated', 'graph_policy_eligible': False, 'episode_ref': None,
              'results': [{'qualified_performance_eligible': False, 'ci95': None}], 'suite': {}}
    return plan, result


def test_legacy_missing_declaration_still_requires_six():
    assert cohort_process_count(plan={}) == 6
    assert cohort_process_count(report={'protocol': 'msprof_task_time_exploration_v2'}) == 6
    plan, result = declaration()
    assert cohort_process_count(plan=plan, report=result) == 2


@pytest.mark.parametrize('change', ['mixed', 'unknown', 'analysis', 'third_process', 'producer',
                                   'order', 'pairs', 'formal', 'graph', 'qualified', 'confidence'])
def test_lite_storage_rejects_mixed_versions_and_promoted_claims(change):
    plan, result = declaration()
    if change == 'mixed': result['protocol'] = 'msprof_task_time_exploration_v2'
    elif change == 'unknown': result['protocol'] = 'invented_protocol'
    elif change == 'analysis': result['analysis_version'] = 'unknown'
    elif change == 'third_process': plan['schedule'].append(copy.deepcopy(plan['schedule'][0]))
    elif change == 'producer': plan['schedule'][0]['request']['version'] = 'msprof_kernel_time_study_v2'
    elif change == 'order': plan['schedule'][1]['request']['first_order'] = 'AB'
    elif change == 'pairs': plan['schedule'][0]['request']['pairs'] = 30
    elif change == 'formal': result['formal_admission'] = 'passed'
    elif change == 'graph': result['graph_policy_eligible'] = True
    elif change == 'qualified': result['results'][0]['qualified_performance_eligible'] = True
    else: result['results'][0]['ci95'] = [1.1, 1.2]
    with pytest.raises(ValueError): cohort_process_count(plan=plan, report=result)


@pytest.fixture
def closed_lite(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def lock(): yield
    monkeypatch.setattr(raw, 'host_lock', lock)
    monkeypatch.setattr(dedup, 'exclusive_host', lock)
    task = tmp_path / 'run/train/tasks/maximum'
    stage = task / 'candidates/maximum001/stages/search'
    cohort = stage / 'direct_parent'
    sessions, plan = lite_cohort(cohort)
    for session, entry in zip(sessions, plan['schedule']):
        entry['request'] = localize(session, entry['request'])
        for directory in (session / 'verification').iterdir():
            save(directory / 'result.json', {'passed': True})
    plan['calibration_scope'].update(capture_storage=transport.LOCAL,
        capture_storage_producer_hash=transport.sha(transport.__file__))
    result = report.analyze_task_cohort(sessions, plan)
    # Synthetic collector operator is exp; storage location deliberately uses a
    # supported unary Level2 output contract. No actual NPU outcome is asserted.
    result['operator'] = 'maximum'
    save(cohort / 'plan.json', plan)
    save(cohort / 'report.json', result)
    observations = [{'directory': str(s), 'completion': raw.pointer(s / 'completion.json'),
                     'samples': raw.pointer(s / 'samples.json'), 'journal': raw.pointer(s / 'native/journal.jsonl')}
                    for s in sessions]
    save(cohort / 'group-completion.json', {'status': 'passed', 'error': None, 'ended_at': 200,
         'completed_sessions': list(map(str, sessions)), 'sessions': observations})
    save(stage / 'stage-plan.json', {'cohorts': [{'relation': 'direct_parent', 'plan': raw.pointer(cohort / 'plan.json')}]})
    save(stage / 'result.json', {'kind': 'timing', 'status': 'passed', 'error': None, 'ended_at': 200})
    save(task / 'manifest.json', {'version': 'msprof_task_time_exploration_v2', 'operator': 'maximum'})
    event(task, 'stage_completed', {'result': raw.pointer(stage / 'result.json')})
    anchor(task, cohort, 'observe')
    return task, cohort, sessions


def test_lite_raw_roundtrip_portable_and_tamper(closed_lite, tmp_path):
    task, cohort, sessions = closed_lite
    session = sessions[0]
    before = report.verify_observation(session)
    raw.prepare(session, writers_closed=True, retire=True)
    seal = json.loads((session / 'raw-archive-storage/seal.json').read_text())
    assert seal['version'] == 'level2_closed_raw_storage_v4'
    assert report.verify_observation(session) == before
    # Use an exact inventory member, independent of fixture CSV path spelling.
    reader = raw.RawArchive(session, raw.pointer(session / 'raw-archive-storage/seal.json'))
    origin = next(p for p in reader.logical_files() if p.name.startswith('op_summary'))
    dataset = dataset_for(tmp_path, [origin]); bundle = tmp_path / 'portable'
    assert portable.export(dataset, bundle)['valid']
    shutil.rmtree(task.parents[2]); shutil.rmtree(dataset)
    assert portable.verify(bundle)['valid']
    replay = subprocess.run([sys.executable, '-B', str(bundle / 'verifier/trace_v2_portable.py'),
        'verify', '--bundle', str(bundle)], cwd='/tmp', capture_output=True, text=True)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['original_evidence_locations_accessed'] is False
    manifest = json.loads((bundle / 'bundle.json').read_text())
    archive_name = next(name for name, value in manifest['files'].items()
                        if value['sha256'] == seal['archive']['sha256'])
    with (bundle / archive_name).open('r+b') as stream:
        stream.seek(520); stream.write(b'changed')
    with pytest.raises(ValueError): portable.verify(bundle)


def test_lite_verification_and_native_storage_replay(closed_lite):
    task, cohort, sessions = closed_lite
    maintenance = dedup.deduplicate(task.parents[2], cohort, kind='cohort', writers_closed=True, apply=True)
    event(task, 'closed_outputs_deduplicated', {'manifest': raw.pointer(maintenance['manifest_path']),
        'reclaimed_bytes': maintenance['reclaimed_bytes'], 'evidence_bytes_deleted': 0})
    result = native.prepare(cohort, writers_closed=True, retire=True)
    assert result['logical_files'] == 2 * 2 * 2 * 2
    for session in sessions:
        verification.prepare(session, writers_closed=True, retire=True)
    with verification.reader_session():
        assert verification.read_bytes(sessions[0] / 'native/1_normal_A.bin')
        assert verification.read_bytes(sessions[0] / 'verification/1_normal_A/metadata.json')


def test_historical_capture_identity_is_readable_but_cannot_launch_new_capture(tmp_path):
    pointer = {'path': str(Path(transport.__file__).resolve()),
               'sha256': transport.LEGACY_CAPTURE_PRODUCER_SHA}
    request = {'version': 'msprof_kernel_time_study_v2', 'capture_storage': transport.LOCAL,
               'capture_storage_producer': pointer}
    assert transport.policy(request) == transport.LOCAL
    with pytest.raises(ValueError, match='current transport producer'):
        transport.allocate(request, tmp_path)
    with pytest.raises(ValueError, match='frozen'):
        transport.policy({**request, 'version': LITE_PRODUCER})
    with pytest.raises(ValueError):
        transport.policy({**request, 'capture_storage_producer': {**pointer, 'sha256': 'sha256:' + '0' * 64}})


from test_msprof_exploration_archive import run, cohort as archive_fixture, read_memory
import msprof_exploration_archive as archive


def test_lite_archive_projection_preserves_null_uncertainty_and_false_admission(run, monkeypatch):
    directory, saved, analyzer = archive_fixture(run, monkeypatch)
    plan = json.loads((directory / 'plan.json').read_text())
    plan.update(protocol=LITE_PROTOCOL, analysis_version=LITE_ANALYSIS)
    plan['schedule'] = plan['schedule'][:2]
    for row, design in zip(plan['schedule'], LITE_DESIGN):
        row['request'].update(version=LITE_PRODUCER,
            **dict(zip(('load_order', 'first_order', 'buffer_configs'), design)))
    save(directory / 'plan.json', plan)
    group = json.loads((directory / 'group-completion.json').read_text())
    group['completed_sessions'] = group['completed_sessions'][:2]
    save(directory / 'group-completion.json', group)
    saved.update(protocol=LITE_PROTOCOL, analysis_version=LITE_ANALYSIS, sessions=saved['sessions'][:2])
    for row in [*saved['results'], *saved['suite'].values()]:
        row.update(ci95=None, df=None, qualified_performance_eligible=False,
                   measurement_quality='descriptive_search_only')
    save(directory / 'report.json', saved)
    analyzer.return_value = copy.deepcopy(saved)
    archive.archive_split(run['root'], 'train')
    rows, _ = read_memory(run['root'])
    evaluation = rows[0]['body']['evaluations'][0]
    assert evaluation['cases'] == saved['results']
    assert evaluation['summary']['native_process_count'] == 2
    assert evaluation['summary']['suite'] == saved['suite']
    assert evaluation['summary']['formal_admission'] == 'not_evaluated'
    assert evaluation['summary']['graph_policy_eligible'] is False
    assert evaluation['summary']['episode_ref'] is None

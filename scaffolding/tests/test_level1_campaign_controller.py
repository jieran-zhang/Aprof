from pathlib import Path
import json
import subprocess
import sys
from unittest.mock import patch

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scaffolding/collection/scripts'))
from collect_level1_traces import Campaign
from aprof_runtime.jsonio import file_hash
from aprof_runtime.traces import execution_record, register_json_artifact, verify_trace


@pytest.fixture
def campaign(tmp_path):
    (tmp_path/'run-manifest.json').write_text(json.dumps({
        'operators':['exp','gelu'],'validation_operators':['gelu'],
        'budget':{'candidate_limit':6},'sentinel_case_ids':[1,8,14,20]}))
    c=Campaign(tmp_path)
    for op in ['exp','gelu']:
        base=c.task(op)/'baseline';base.mkdir(parents=True)
        (base/'kernel.asc').write_text('original\n')
    return c


def proposal(c,identifier='001'):
    directory=c.task('exp')/'candidates'/identifier
    (directory/'op').mkdir(parents=True)
    (directory/'op/kernel.asc').write_text('changed\n')
    (directory/'candidate_plan.json').write_text(json.dumps({
        'candidate_id':'exp-'+identifier,'mode':'exploration','intent':'test atomic change',
        'handler_id':'test.handler','parameters':{},'expected_effects':['less work'],
        'coverage_gap':'no graph transformation','alternatives':[{'intent':'keep baseline'}]}))
    return directory


def test_registered_source_changes_and_new_files_are_rejected(campaign):
    directory=proposal(campaign);campaign.register_candidate('exp','001')
    campaign.verify_source_identity('exp','001')
    (directory/'op/kernel.asc').write_text('late edit\n')
    with pytest.raises(ValueError,match='source changed'):campaign.freeze('exp')
    (directory/'op/kernel.asc').write_text('changed\n')
    (directory/'op/extra.asc').write_text('new file\n')
    with pytest.raises(ValueError,match='file set'):campaign.freeze('exp')


def test_sealed_task_search_feedback_and_roster_boundary(campaign):
    with pytest.raises(ValueError,match='outside'):campaign.task('swi_glu')
    with pytest.raises(ValueError,match='nonsentinel'):campaign.measure_case('exp','001',case=2)
    with pytest.raises(ValueError,match='frozen'):campaign.measure_case('exp','001',case=1,phase='final')
    proposal(campaign);campaign.register_candidate('exp','001');campaign.freeze('exp')
    with pytest.raises(ValueError,match='closed'):campaign.register_candidate('exp','001')
    with pytest.raises(ValueError,match='closed'):campaign.build_candidate('exp','001')
    assert campaign.store('exp').path != campaign.store('gelu').path


def test_task_budget_is_not_a_global_cross_operator_counter(campaign):
    for i in range(1,8):proposal(campaign,f'{i:03d}')
    with pytest.raises(ValueError,match='budget'):campaign.register_candidate('exp','001')
    assert not (campaign.task('exp')/'candidates/001/registration.json').exists()


def test_oracle_edits_cannot_hide_outside_the_optimization_patch(campaign):
    directory=proposal(campaign)
    (directory/'op/scripts').mkdir()
    (directory/'op/scripts/verify_result.py').write_text('raise SystemExit(0)\n')
    with pytest.raises(ValueError,match='protected oracle'):
        campaign.register_candidate('exp','001')


def test_remote_transport_failure_is_an_immediate_trace_event(campaign):
    result=subprocess.CompletedProcess(['ssh'],255,'','connection lost')
    with patch('collect_level1_traces.subprocess.run',return_value=result):
        with pytest.raises(RuntimeError,match='transport failed'):
            campaign.job('exp','probe',['python3','probe.py'],host='decode',device=0)
    path=campaign.task('exp')/'trace_events.jsonl'
    assert verify_trace(path,store=campaign.store('exp'))['valid']
    row=json.loads(path.read_text())
    assert row['event_type']=='execution_interrupted'
    assert row['payload']['execution']['exit_status']==255
    assert 'remote kernel verdict' in row['payload']['execution']['reason']


@pytest.mark.parametrize('log_bytes', [b'', b'identical stdout and stderr\n'])
def test_record_identical_logs_preserves_report_and_event_idempotence(campaign, log_bytes):
    directory = campaign.task('exp') / 'executions' / 'cpu-check'
    directory.mkdir(parents=True)
    stdout, stderr = directory / 'stdout.log', directory / 'stderr.log'
    for path in (stdout, stderr):
        path.write_bytes(log_bytes)
    report = {'schema_version': '1.0.0', 'kind': 'aprof_execution_report',
        'job': {'job_id': 'exp-cpu-check', 'argv': ['git', 'diff', '--check'],
            'cwd': str(campaign.task('exp') / 'baseline')},
        'status': 'passed', 'exit_code': 0, 'host': 'test-local', 'physical_device': None,
        'started_at': '2026-09-07T00:00:00Z', 'finished_at': '2026-09-07T00:00:01Z',
        'stdout': {'path': str(stdout), 'sha256': file_hash(stdout)},
        'stderr': {'path': str(stderr), 'sha256': file_hash(stderr)}}
    report_ref = campaign.record('exp', report, stage='cpu_check')
    events = campaign.task('exp') / 'trace_events.jsonl'
    before = events.read_bytes()
    event = json.loads(before)
    log_ref = file_hash(stdout)
    assert log_ref == file_hash(stderr)
    assert event['payload']['artifact_refs'] == [log_ref, report_ref]
    assert event['payload']['execution']['log_ref'] == log_ref
    assert event['payload']['status'] == 'passed'
    with campaign.store('exp') as store:
        assert json.loads(store.verify_artifact(report_ref).read_text()) == report
        assert store.verify_artifact(log_ref).read_bytes() == log_bytes
        assert verify_trace(events, store)['event_count'] == 1
    assert campaign.record('exp', report, stage='cpu_check') == report_ref
    assert events.read_bytes() == before
    with campaign.store('exp') as store:
        assert verify_trace(events, store)['event_count'] == 1


def test_record_retries_legacy_unsorted_event_without_rewriting(campaign):
    directory = campaign.task('exp') / 'executions' / 'legacy-check'
    directory.mkdir(parents=True)
    stdout, stderr = directory / 'stdout.log', directory / 'stderr.log'
    # These distinct contents deliberately produce descending SHA-256 order.
    stdout.write_bytes(b'')
    stderr.write_bytes(b'hello')
    assert file_hash(stdout) > file_hash(stderr)
    report = {'schema_version': '1.0.0', 'kind': 'aprof_execution_report',
        'job': {'job_id': 'exp-legacy-check', 'argv': ['legacy-cpu-check'],
            'cwd': str(campaign.task('exp') / 'baseline')},
        'status': 'passed', 'exit_code': 0, 'host': 'test-local', 'physical_device': None,
        'started_at': '2026-09-07T00:00:00Z', 'finished_at': '2026-09-07T00:00:01Z',
        'stdout': {'path': str(stdout), 'sha256': file_hash(stdout)},
        'stderr': {'path': str(stderr), 'sha256': file_hash(stderr)}}
    with campaign.store('exp') as store:
        refs = [store.register_artifact(report[key]['path']) for key in ('stdout', 'stderr')]
        report_ref = register_json_artifact(store, report)
        refs.append(report_ref)
        assert len(refs) == len(set(refs)) and refs != sorted(refs)
        # Reproduce the pre-fix successful event's original payload and order.
        campaign.writer('exp', store).append('stage_completed', {
            'stage': 'cpu_check', 'status': 'passed',
            'execution': execution_record(argv=report['job']['argv'], cwd=report['job']['cwd'],
                host=report['host'], device=report['physical_device'], started_at=report['started_at'],
                finished_at=report['finished_at'], exit_status=report['exit_code'], log_ref=refs[0]),
            'reason': None, 'artifact_refs': refs},
            attempt_id=None, candidate_id=None, event_id=report['job']['job_id'] + '-completed')
    events = campaign.task('exp') / 'trace_events.jsonl'
    before = events.read_bytes()
    assert campaign.record('exp', report, stage='cpu_check') == report_ref
    assert events.read_bytes() == before
    assert json.loads(before)['payload']['artifact_refs'] == refs
    with campaign.store('exp') as store:
        assert verify_trace(events, store)['event_count'] == 1


def test_later_worker_reads_append_without_rewriting_prior_attestations(campaign, monkeypatch):
    import hashlib
    import import_level1_worker_evidence as importer
    monkeypatch.setattr(importer, 'Campaign', lambda: campaign)
    task = campaign.task('exp')
    log = task / 'worker_knowledge_reads.jsonl'
    def add_read(name):
        path = task / name
        path.write_text(name)
        with log.open('a') as stream:
            stream.write(json.dumps({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'purpose': 'bounded source review', 'timestamp': '2026-09-07T00:00:00Z'}) + '\n')
    add_read('first.md'); importer.import_worker('exp')
    events = task / 'trace_events.jsonl'; original = events.read_bytes()
    add_read('later.md'); importer.import_worker('exp')
    assert events.read_bytes().startswith(original)
    rows = [json.loads(line) for line in events.read_text().splitlines()]
    assert len(rows) == 2 and all(len(row['payload']['entries']) == 1 for row in rows)
    before = events.read_bytes(); importer.import_worker('exp')
    assert events.read_bytes() == before
    assert verify_trace(events, store=campaign.store('exp'))['valid']

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_level1_traces import Campaign
from finalize_level1_campaign import Finalizer
from verify_level1_campaign import CampaignVerifier, OPERATORS, ReadOnlyStore, TIMING_ENVIRONMENT
from aprof_runtime.errors import StoreError
from aprof_runtime.traces import register_json_artifact, execution_record, utcnow


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def manifest(run):
    ops = ['foreach_norm', 'exp', 'masked_scale', 'foreach_addcdiv_scalar', 'mish', 'sigmoid', 'gelu']
    dump(run / 'run-manifest.json', {'run_id': run.name, 'operators': ops,
        'train_operators': [op for op in ops if op != 'gelu'], 'validation_operators': ['gelu'],
        'sentinel_case_ids': [1, 8, 14, 20], 'acceptance_case_ids': list(range(1, 21)), 'policy_updates': False,
        'budget': {'candidate_limit': 6, 'build_limit': 6, 'timing_limit': 6, 'full_profile_limit': 3}})


@pytest.fixture
def complete_run(tmp_path):
    run = tmp_path / 'campaign'
    manifest(run)
    campaign = Campaign(run)
    for op in campaign.manifest['operators']:
        task = campaign.task(op)
        baseline = task / 'baseline'
        baseline.mkdir(parents=True)
        (baseline / 'kernel.asc').write_text('original kernel\n')
        (baseline / 'scripts').mkdir()
        (baseline / 'scripts/verify_result.py').write_text('unchanged oracle\n')
        for number in range(1, 7 if op == 'exp' else 4):
            identifier = f'{number:03}'
            directory = task / 'candidates' / identifier
            shutil.copytree(baseline, directory / 'op')
            (directory / 'op/kernel.asc').write_text(f'{op} candidate {number}\n')
            dump(directory / 'candidate_plan.json', {'candidate_id': op + '-' + identifier, 'mode': 'exploration',
                'handler_id': op + '.test', 'handler_version': '1.0.0', 'intent': 'Test bounded source candidate',
                'parameters': {'variant': number}, 'expected_effects': ['Fewer operations'], 'coverage_gap': 'Uncovered test handler.',
                'static_review': ['Source bounds reviewed.']})
            campaign.register_candidate(op, identifier)
            dump(task / 'executions' / identifier / 'build/execution.json', {'status': 'failed', 'exit_code': 1})
            with campaign.store(op) as store:
                ref = register_json_artifact(store, {'build_log': 'Synthetic failed build fixture', 'candidate': identifier})
                campaign.writer(op, store).append('stage_completed', {'stage': 'build', 'status': 'failed',
                    'reason': 'Synthetic test failure; no command is executed.', 'execution': None, 'artifact_refs': [ref]},
                    candidate_id=op + '-' + identifier, attempt_id=op + '-' + identifier)
        campaign.freeze(op)
    finalizer = Finalizer(run)
    for op in campaign.manifest['operators']:
        finalizer.finalize_operator(op)
    finalizer.export()
    return run


def fingerprint(run):
    return {str(path.relative_to(run)): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        for path in run.rglob('*') if path.is_file()}


def checks(report, name):
    return [check for check in report['checks'] if check['name'] == name]


def test_complete_campaign_verifies_without_writes_or_repair(complete_run):
    before = fingerprint(complete_run)
    report = CampaignVerifier(complete_run).verify()
    assert report['valid'], [check for check in report['checks'] if check['status'] == 'failed']
    assert report['status'] == 'verified'
    assert report['campaign_complete']
    assert fingerprint(complete_run) == before
    assert checks(report, 'bounded_24_candidate_roster')[0]['detail']['candidate_count'] == 24
    assert all(check['detail']['episode_count'] == 0 for check in checks(report, 'exact_compatibility_exports'))


def test_missing_cas_object_is_reported_and_never_reinstalled(complete_run):
    with ReadOnlyStore(complete_run / 'train/episodes.sqlite') as store:
        outcome = json.loads((complete_run / 'tasks/exp/exploration_outcomes.json').read_text())[0]
        missing = store.object_path(outcome['request_hash'])
    missing.unlink()
    before = fingerprint(complete_run)
    report = CampaignVerifier(complete_run).verify()
    assert not report['valid']
    assert any('CAS object is missing' in check.get('reason', '') for check in report['checks'])
    assert not missing.exists()
    assert fingerprint(complete_run) == before


def test_delivered_and_registered_source_mutations_fail_independently(complete_run):
    (complete_run / 'tasks/exp/best_source/kernel.asc').write_text('unverified deliverable')
    (complete_run / 'tasks/gelu/candidates/001/op/scripts/verify_result.py').write_text('changed oracle')
    report = CampaignVerifier(complete_run).verify()
    assert not report['valid']
    assert next(check for check in checks(report, 'delivered_source_snapshot') if check['scope'] == 'exp')['status'] == 'failed'
    assert next(check for check in checks(report, 'frozen_roster_source_harness_boundary') if check['scope'] == 'gelu')['status'] == 'failed'


def test_split_export_and_worker_boundary_tampering_are_visible(complete_run):
    train = complete_run / 'train/optimization_traces.jsonl'
    train.write_bytes(train.read_bytes() + (complete_run / 'validation/optimization_traces.jsonl').read_bytes())
    dump(complete_run / 'tasks/exp/worker_knowledge_reads.jsonl', {'path': str(complete_run / 'tasks/gelu/optimization_traces.jsonl'), 'purpose': 'forbidden heldout result'})
    report = CampaignVerifier(complete_run).verify()
    assert not report['valid']
    assert any(check['status'] == 'failed' for check in checks(report, 'exact_compatibility_exports'))
    assert next(check for check in checks(report, 'split_and_recorded_sealed_task_boundary') if check['scope'] == 'exp')['status'] == 'failed'


def test_profile_budget_excludes_calibration_but_detects_four_candidate_profiles(complete_run):
    for identifier in ('001', '002', '003', '004'):
        dump(complete_run / 'tasks/exp/executions' / identifier / 'profile-01/execution.json', {'status': 'failed'})
    for number in range(20):
        dump(complete_run / 'calibration' / str(number) / 'execution.json', {'status': 'passed'})
    report = CampaignVerifier(complete_run).verify()
    assert next(check for check in checks(report, 'candidate_execution_budgets') if check['scope'] == 'exp')['status'] == 'failed'
    assert all(check['status'] == 'passed' for check in checks(report, 'candidate_execution_budgets') if check['scope'] != 'exp')


def test_explicit_blocked_closure_is_not_a_false_verified_completion(tmp_path):
    run = tmp_path / 'blocked'
    manifest(run)
    campaign = Campaign(run)
    for op in OPERATORS:
        with campaign.store(op) as store:
            ref = register_json_artifact(store, {'reason': 'No timing topology qualified.'})
            campaign.writer(op, store).append('task_finished', {'status': 'blocked', 'reason': 'No timing topology qualified.',
                'attempt_count': 0, 'summary_ref': ref})
    before = fingerprint(run)
    report = CampaignVerifier(run).verify()
    assert report['integrity_valid'], [check for check in report['checks'] if check['status'] == 'failed']
    assert not report['valid'] and report['status'] == 'blocked'
    assert len(report['blocked_tasks']) == 7
    assert fingerprint(run) == before


def test_missing_task_closure_is_failure_not_an_implicit_block(tmp_path):
    run = tmp_path / 'incomplete'
    manifest(run)
    campaign = Campaign(run)
    for split in ('train', 'validation'):
        from aprof_runtime.store import EpisodeStore
        with EpisodeStore(run / split / 'episodes.sqlite'):
            pass
    report = CampaignVerifier(run).verify()
    assert report['status'] == 'failed'
    assert len(checks(report, 'event_chains_and_closure')) == 7
    assert all(check['status'] == 'failed' for check in checks(report, 'event_chains_and_closure'))


def test_read_only_registration_requires_an_existing_digest(tmp_path):
    from aprof_runtime.store import EpisodeStore
    path = tmp_path / 'episodes.sqlite'
    with EpisodeStore(path):
        pass
    source = tmp_path / 'new.json'
    source.write_text('{}')
    before = fingerprint(tmp_path)
    with ReadOnlyStore(path) as store:
        with pytest.raises(StoreError, match='CAS object is missing'):
            store.register_artifact(source)
        with pytest.raises(sqlite3.OperationalError):
            store.connection.execute("INSERT INTO artifacts(content_hash) VALUES ('sha256:' || printf('%064d', 0))")
    assert fingerprint(tmp_path) == before


def test_unregistered_execution_cannot_escape_candidate_budget(tmp_path):
    verifier = CampaignVerifier(tmp_path)
    verifier.manifest = {'budget': {'candidate_limit': 6, 'build_limit': 6, 'timing_limit': 6, 'full_profile_limit': 3}}
    dump(tmp_path / 'tasks/exp/candidates/001/registration.json', {})
    dump(tmp_path / 'tasks/exp/executions/002/build/execution.json', {'status': 'failed'})
    with pytest.raises(StoreError, match='unregistered candidate'):
        verifier.budgets('exp')


def test_sqlite_foreign_key_corruption_is_visible(tmp_path):
    from aprof_runtime.store import EpisodeStore
    path = tmp_path / 'episodes.sqlite'
    with EpisodeStore(path):
        pass
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO artifact_locations(content_hash,uri,size_bytes) VALUES (?, ?, ?)", ('sha256:' + 'a' * 64, '/unregistered', 0))
    with ReadOnlyStore(path) as store:
        with pytest.raises(StoreError, match='orphan foreign-key'):
            CampaignVerifier(tmp_path).sqlite_integrity(store)


def test_exp006_missing_supplemental_evidence_blocks_a_safe_claim(tmp_path):
    run = tmp_path / 'run'
    verifier = CampaignVerifier(run)
    verifier.tasks['exp'] = {'summaries': [{'identity': {'candidate_id': 'exp-006'},
        'result': {'verdict': 'benchmark_specialized_gain'}}]}
    from aprof_runtime.store import EpisodeStore
    with EpisodeStore(run / 'train/episodes.sqlite'):
        pass
    with ReadOnlyStore(run / 'train/episodes.sqlite') as store:
        with pytest.raises(FileNotFoundError, match='hardware_validation.json'):
            verifier.supplemental_exp006(store)


@pytest.fixture
def supplemental_run(tmp_path):
    from aprof_runtime.store import EpisodeStore
    run = tmp_path / 'supplement'
    base = run / 'tasks/exp/qualification/zero_affine'
    events, cases, planned = [], [], []
    argv_prefix = ['/usr/bin/env'] + [token for name in TIMING_ENVIRONMENT for token in ('-u', name)]
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        artifact = lambda value: register_json_artifact(store, value)
        for dtype in ('float32', 'float16', 'bfloat16'):
            for size in (17, 4097, 196673):
                case_id = f'zero-affine-{dtype}-n{size}'
                case = {'case_id': case_id, 'status': 'passed', 'reason': None}
                plan = {'case_id': case_id}
                for stage in ('launch', 'verify'):
                    argv = argv_prefix + ['/test/' + stage, case_id]
                    execution_ref = artifact({'status': 'passed', 'exit_code': 0, 'job': {'argv': argv, 'environment': {}}})
                    event_id = case_id + '-' + stage
                    events.append({'event_id': event_id, 'candidate_id': 'exp-006',
                        'payload': {'status': 'passed', 'artifact_refs': [execution_ref], 'execution': {'argv': argv, 'exit_status': 0}}})
                    case[stage] = {'status': 'passed', 'exit_code': 0, 'execution_ref': execution_ref, 'event_id': event_id}
                    plan[stage + '_argv'] = argv
                output_ref = artifact({'synthetic_output': case_id})
                observation_ref = artifact({'case_id': case_id, 'candidate_id': 'exp-006', 'passed': True, 'mismatch_count': 0,
                    'output_sha256': output_ref.removeprefix('sha256:')})
                case.update(output_ref=output_ref, observation_ref=observation_ref,
                    artifact_refs=[case['launch']['execution_ref'], case['verify']['execution_ref'], output_ref, observation_ref])
                case['case_validation_ref'] = artifact(case)
                cases.append(case)
                planned.append(plan)
        manifest_ref = artifact({'candidate_id': 'exp-006', 'attempt': '001', 'case_count': 9,
            'purpose': 'correctness_only_no_performance_feedback', 'timing_environment_unset': TIMING_ENVIRONMENT,
            'cases': planned, 'sources': [], 'source_artifact_refs': []})
        report = {'candidate_id': 'exp-006', 'kind': 'supplemental_correctness_validation', 'status': 'passed',
            'case_count': 9, 'attempted_count': 9, 'passed_count': 9, 'cases': cases, 'first_failure': None,
            'attempt': '001', 'purpose': 'correctness_only_no_performance_feedback', 'timing_environment_unset': TIMING_ENVIRONMENT,
            'run_manifest_ref': manifest_ref, 'event_id': 'supplement-complete'}
        report['summary_ref'] = artifact(report)
        dump(base / 'hardware_validation.json', report)
        raw_ref = store.register_artifact(base / 'hardware_validation.json')
        dump(base / 'attempts/001/binding.json', {'artifact_ref': raw_ref})
        events.append({'event_id': report['event_id'], 'candidate_id': 'exp-006',
            'payload': {'evidence_refs': [raw_ref, report['summary_ref'], manifest_ref]}})
        fragment_ref = artifact({'events': events})
    verifier = CampaignVerifier(run)
    verifier.tasks['exp'] = {'events': events, 'summaries': [{'identity': {'candidate_id': 'exp-006'},
        'result': {'verdict': 'benchmark_specialized_gain', 'attempt_evidence_hash': fragment_ref},
        'lesson': {'evidence_refs': [raw_ref]}}]}
    return verifier, base


def test_exp006_actual_format_binds_all_nine_observations_and_sealed_events(supplemental_run):
    verifier, _ = supplemental_run
    before = fingerprint(verifier.run)
    with ReadOnlyStore(verifier.run / 'train/episodes.sqlite') as store:
        assert verifier.supplemental_exp006(store)['case_count'] == 9
    assert fingerprint(verifier.run) == before


@pytest.mark.parametrize('mutation,reason', [('environment', 'leaked timing'), ('event', 'completion event binding'),
    ('coverage', 'coverage differs'), ('late_evidence', 'not sealed')])
def test_exp006_rejects_unbound_or_incomplete_supplement(supplemental_run, mutation, reason):
    from aprof_runtime.store import EpisodeStore
    verifier, base = supplemental_run
    if mutation in ('environment', 'coverage'):
        report = json.loads((base / 'hardware_validation.json').read_text())
        if mutation == 'environment':
            report['timing_environment_unset'] = True
        else:
            report['cases'][-1]['case_id'] = report['cases'][0]['case_id']
        dump(base / 'hardware_validation.json', report)
    elif mutation == 'event':
        verifier.tasks['exp']['events'][0]['payload']['artifact_refs'] = []
    else:
        with EpisodeStore(verifier.run / 'train/episodes.sqlite') as store:
            ref = register_json_artifact(store, {'events': verifier.tasks['exp']['events'][:-1]})
        verifier.tasks['exp']['summaries'][0]['result']['attempt_evidence_hash'] = ref
    with ReadOnlyStore(verifier.run / 'train/episodes.sqlite') as store:
        with pytest.raises(StoreError, match=reason):
            verifier.supplemental_exp006(store)


def collect_synthetic_profiles(campaign, mode='passed'):
    """Exercise the real queue with CPU fixtures at the hardware boundary."""
    import run_level1_blocked_diagnostics as diagnostic
    from collect_level1_traces import WRITER_LOCK
    task = campaign.task('exp')
    def profile(op, identifier, *, case, host, device):
        started = utcnow()
        argv = ['msprof', 'op', 'synthetic-test-case', str(case)]
        job = {'job_id': f'exp-{identifier}-profile-{case:02d}', 'argv': argv}
        report = {'kind': 'aprof_execution_report', 'status': 'failed' if mode == 'failed' else 'passed',
            'exit_code': 7 if mode == 'failed' else 0, 'job': job, 'started_at': started,
            'finished_at': utcnow(), 'host': host, 'physical_device': device}
        dump(task / 'executions' / identifier / f'profile-{case:02d}/execution.json', report)
        with WRITER_LOCK, campaign.store(op) as store:
            ref = register_json_artifact(store, report)
            campaign.writer(op, store).append('stage_completed', {'stage': 'profile', 'status': report['status'],
                'reason': 'Synthetic CPU fixture; hardware execution is mocked.', 'artifact_refs': [ref],
                'execution': execution_record(argv=argv, cwd=task, host=host, device=device, started_at=started,
                    finished_at=report['finished_at'], exit_status=report['exit_code'], log_ref=ref)},
                candidate_id='exp-' + identifier, attempt_id='exp-' + identifier)
        if mode == 'compression_error':
            raise RuntimeError('Synthetic compression failure after successful msprof exit')
        return report
    campaign.profile_case = profile
    complete = diagnostic.execute_operator('exp', campaign=campaign)
    verifier = CampaignVerifier(campaign.run)
    verifier.manifest = campaign.manifest
    events = [json.loads(line) for line in (task / 'trace_events.jsonl').read_text().splitlines()]
    with campaign.store('exp') as store:
        from recover_level1_profile_preflight import load_verified_recovery
        recovered = load_verified_recovery(campaign, 'exp', store)
        summaries = []
        for identifier in complete['selected_profile_candidate_ids']:
            candidate = 'exp-' + identifier
            status = 'passed' if identifier in complete['full_profile_candidate_ids'] else 'interrupted'
            summaries.append({'identity': {'candidate_id': candidate}, 'validation': {'profile': {'status': status}},
                'result': {'attempt_evidence_hash': campaign.writer('exp', store).seal_attempt(candidate)},
                'lesson': {'evidence_refs': [recovered['manifest_ref']] if recovered['manifest_ref'] else [],
                    'limitations': recovered['warnings']}})
    verifier.tasks['exp'] = {'events': events, 'summaries': summaries}
    return verifier, complete


@pytest.mark.parametrize('mode', ['passed', 'failed', 'compression_error', 'preflight_missing'])
def test_profile_lists_reproduce_successful_dispatches_and_complete_case_coverage(tmp_path, mode):
    from test_level1_blocked_diagnostics import FakeCampaign
    campaign = FakeCampaign(tmp_path, identifiers=('001',))
    if mode == 'preflight_missing':
        (campaign.task('exp') / 'candidates/001/mechanism_plan.json').unlink()
    verifier, complete = collect_synthetic_profiles(campaign, mode)
    before = fingerprint(tmp_path)
    with ReadOnlyStore(tmp_path / 'train/episodes.sqlite') as store:
        result = verifier.profile_execution_summary('exp', store, complete, ['001'])
    assert fingerprint(tmp_path) == before
    assert result['selected_profile_candidate_ids'] == ['001']
    assert result['profiled_candidate_ids'] == result['full_profile_candidate_ids'] == (['001'] if mode == 'passed' else [])
    assert result['successful_profile_case_count'] == (4 if mode == 'passed' else 0)
    if mode == 'compression_error':
        reports = list((campaign.task('exp') / 'executions/001').glob('profile-*/execution.json'))
        assert reports and all(json.loads(path.read_text())['status'] == 'passed' for path in reports)
        assert result['failed_profile_candidate_ids'] == ['exp-001']


@pytest.mark.parametrize('mutation,reason', [('invent_success', 'profiled candidate list'),
    ('invent_full', 'full profile candidate list'), ('hide_failure', 'hides a non-recovered profiler failure'),
    ('missing_execution', 'actual execution report'), ('report_swapped', 'belongs to another job'),
    ('queue_case', 'omitted, duplicated or changed a selected case')])
def test_profile_completion_cannot_hide_skips_missing_reports_or_real_failures(tmp_path, mutation, reason):
    from test_level1_blocked_diagnostics import FakeCampaign
    campaign = FakeCampaign(tmp_path, identifiers=('001',))
    mode = 'passed' if mutation in ('missing_execution', 'report_swapped', 'queue_case') else 'failed'
    verifier, complete = collect_synthetic_profiles(campaign, mode)
    if mutation == 'invent_success':
        complete['profiled_candidate_ids'] = ['001']
    elif mutation == 'invent_full':
        complete['full_profile_candidate_ids'] = ['001']
    elif mutation == 'hide_failure':
        verifier.tasks['exp']['summaries'][0]['validation']['profile']['status'] = 'passed'
    elif mutation == 'missing_execution':
        (campaign.task('exp') / 'executions/001/profile-01/execution.json').unlink()
    elif mutation == 'report_swapped':
        directory = campaign.task('exp') / 'executions/001'
        (directory / 'profile-01/execution.json').write_bytes((directory / 'profile-08/execution.json').read_bytes())
    else:
        path = campaign.task('exp') / 'queue/profiles.json'
        rows = json.loads(path.read_text())
        rows[0]['item'][1] = 2
        dump(path, rows)
    with ReadOnlyStore(tmp_path / 'train/episodes.sqlite') as store:
        with pytest.raises(StoreError, match=reason):
            verifier.profile_execution_summary('exp', store, complete, ['001'])


# Import the real, source-frozen CPU recovery fixture; no hardware is launched.
from test_level1_profile_preflight_recovery import failed_preflight


@pytest.mark.parametrize('mode', ['passed', 'failed'])
def test_profile_verifier_loads_recovery_without_ignoring_later_real_msprof_failures(failed_preflight, mode):
    from recover_level1_profile_preflight import prepare_recovery
    campaign, old = failed_preflight
    recovered = prepare_recovery(campaign, 'exp', old)
    verifier, complete = collect_synthetic_profiles(campaign, mode)
    before = fingerprint(campaign.run)
    with ReadOnlyStore(campaign.run / 'train/episodes.sqlite') as store:
        result = verifier.profile_execution_summary('exp', store, complete, ['001', '002'])
        assert result['controller_recovery_ref'] == recovered['manifest_ref']
        assert result['failed_profile_candidate_ids'] == ([] if mode == 'passed' else ['exp-001', 'exp-002'])
        if mode == 'failed':
            verifier.tasks['exp']['summaries'][0]['validation']['profile']['status'] = 'passed'
            with pytest.raises(StoreError, match='hides a non-recovered profiler failure'):
                verifier.profile_execution_summary('exp', store, complete, ['001', '002'])
        else:
            verifier.tasks['exp']['summaries'][0]['lesson']['limitations'] = []
            with pytest.raises(StoreError, match='omitted its qualified recovery evidence or warning'):
                verifier.profile_execution_summary('exp', store, complete, ['001', '002'])
    assert fingerprint(campaign.run) == before


def test_profile_verifier_rejects_an_unbound_or_tampered_recovery(failed_preflight):
    from recover_level1_profile_preflight import prepare_recovery, RECOVERY_ID
    campaign, old = failed_preflight
    prepare_recovery(campaign, 'exp', old)
    verifier, complete = collect_synthetic_profiles(campaign)
    with ReadOnlyStore(campaign.run / 'train/episodes.sqlite') as store:
        missing = dict(complete)
        missing.pop('controller_recovery_ref')
        with pytest.raises(StoreError, match='recovery reference is missing or unverified'):
            verifier.profile_execution_summary('exp', store, missing, ['001', '002'])
        path = campaign.task('exp') / 'controller_recoveries' / RECOVERY_ID / 'queue/profiles.json'
        path.chmod(0o644)
        path.write_text('[]')
        with pytest.raises(StoreError, match='archive changed'):
            verifier.profile_execution_summary('exp', store, complete, ['001', '002'])

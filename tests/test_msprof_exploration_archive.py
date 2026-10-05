"""Synthetic CPU archive tests. No process runner, device or historical run is used."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import msprof_exploration_archive as archive
import feedback_trace_export as export
import trace_v2_dataset as v2


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(v2.canonical(value))
    return path


def source(path, tree, payload):
    files = {'op_host/exp.asc': payload.encode(), 'op_kernel/helper.h': b'header'}
    for name, data in files.items():
        p = tree / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    with tarfile.open(path, 'w') as stream:
        for name, data in files.items():
            info = tarfile.TarInfo('source/' + name)
            info.size = len(data)
            stream.addfile(info, io.BytesIO(data))
    return archive.sha(path)


@pytest.fixture
def run(tmp_path, monkeypatch):
    root = tmp_path / 'new-run'
    task = root / 'train/tasks/exp'
    candidate = task / 'candidates/exp001'
    candidate.mkdir(parents=True)
    baseline = source(task / 'baseline-source.tar', task / 'baseline', 'original source')
    current = source(candidate / 'source.tar', candidate / 'op', 'optimized source')
    (candidate / 'optimization.patch').write_text('actual synthetic source diff')
    save(task / 'manifest.json', dict(operator='exp', split='train'))
    save(task / 'knowledge-catalog.json', dict(catalog='declared, not read'))
    save(task / 'input-bindings.json', dict(inputs=[]))
    save(candidate / 'proposal.json', dict(intent='Remove redundant synthetic operation.'))
    item = dict(candidate_id='exp001', source_hash=current, patch_hash=archive.sha(candidate / 'optimization.patch'),
                source_parent=dict(candidate_id=None, source_hash=baseline), stable_id='new-run/train/exp001',
                inherited=False, observation_ids=[])
    state = dict(split='train', candidates={'exp001': item}, stages={}, observations={},
                 used=dict.fromkeys(archive.campaign.BUDGETS, 0), new_rounds_started=1)
    class Ledger:
        config_hash = 'sha256:' + '0' * 64
        config = {'tasks': {'exp': {'baseline_source_hash': baseline}}}
        events = [dict(hash='sha256:' + '1' * 64, arguments={}, operation='prepare', recorded_at='2026-09-11T00:00:00Z')]
        def __init__(self, directory):
            assert Path(directory) == root / 'train/ledger'
            self.state = {'tasks': {'exp': state}}
        def verify(self):
            return {'valid': True}
    monkeypatch.setattr(archive.campaign, 'Campaign', Ledger)
    def forbidden(*args, **kwargs):
        pytest.fail('unexpected observation or hardware execution')
    monkeypatch.setattr(archive.analysis, 'analyze_task_cohort', forbidden)
    return dict(root=root, task=task, candidate=candidate, state=state, item=item, baseline=baseline)


def stage(run, *, status='failed', kind='build', name='build'):
    cid = run.get('candidate_id', 'exp001')
    path = run['candidate'] / 'stages' / name / 'result.json'
    save(path, dict(stage_id=name, candidate_id=cid, kind=kind, status=status,
                    error={'type': 'RuntimeError', 'message': 'synthetic failure'} if status == 'failed' else None, **archive.POLICY))
    run['state']['stages'][name] = dict(kind=kind, candidate_id=cid,
        attempts=[dict(outcome='success' if status == 'passed' else 'failed', evidence={'result': {'path': str(path), 'sha256': archive.sha(path)}})])
    return path


def read_memory(root):
    out = root / 'archive/train/v2'
    pointer = archive.load(out / 'current.json')
    base = out / 'revisions' / pointer['revision']
    return v2.load_rows(base / 'train/optimization_traces.jsonl'), base


def test_failed_source_is_archived_without_machine_verdict(run):
    stage(run)
    result = archive.archive_split(run['root'], 'train')
    rows, base = read_memory(run['root'])
    assert result['new_source_attempts'] == 1 and result['verification']['valid']
    assert rows[0]['body']['evaluations'][0]['stages'][0]['status'] == 'failed'
    assert rows[0]['body']['machine_results'][0]['verdict'] == 'not_recorded'
    assert rows[0]['body']['machine_results'][0]['graph_policy_eligible'] is False
    assert rows[0]['body']['machine_results'][0]['episode_ref'] is None
    assert rows[0]['body']['knowledge']['actual_reads'] == []
    assert (base / 'validation/optimization_traces.jsonl').read_bytes() == b''


def test_explicit_proposal_statement_keeps_optimizer_attribution(run):
    statement = 'Overlap the next input tile transfer while retaining sequential arithmetic.'
    save(run['candidate'] / 'proposal.json', {'statement': statement, 'rationale': {'mechanism': 'double input buffering'}})
    archive.archive_split(run['root'], 'train')
    intervention = read_memory(run['root'])[0][0]['body']['intervention']
    assert intervention['statement'] == statement
    assert intervention['basis'] == 'recorded_optimizer_proposal'


@pytest.mark.parametrize('quality_feedback', [
    {'action': 'quality_update'},
    {'action': 'quality_update', 'reason': 'CPU isolation was not established.'},
    {'artifact': 'additional descriptive evidence without a new decision'},
])
def test_quality_observation_preserves_actual_stop_and_its_own_timeline(run, quality_feedback):
    observations = [
        ('stop', {'action': 'stop', 'reason': 'No supported next source intervention.'}),
        ('quality', quality_feedback),
    ]
    for index, (oid, feedback) in enumerate(observations):
        value = {'observation_id': oid, 'candidate_id': 'exp001', 'stage_ids': [],
                 'feedback': feedback, 'close_feedback': True}
        run['state']['observations'][oid] = value
        run['item']['observation_ids'].append(oid)
        archive.campaign.Campaign.events.append({
            'operation': 'observe', 'recorded_at': f'2026-09-11T12:0{index}:00Z',
            'hash': 'sha256:' + str(index + 2) * 64,
            'arguments': {'workload': 'exp', **value},
        })
    archive.archive_split(run['root'], 'train')
    body = read_memory(run['root'])[0][0]['body']
    assert body['next_decision']['action'] == 'stop'
    assert body['next_decision']['reason'] == observations[0][1]['reason']
    assert len(body['timeline']) == 2
    assert 'quality' in body['timeline'][-1]['summary']
    assert all(x['graph_policy_eligible'] is False and x['episode_ref'] is None
               for x in body['machine_results'])


def test_later_actual_decision_supersedes_previous_stop(run):
    run['item']['observation_ids'] = ['stop', 'continue']
    run['state']['observations'] = {
        'stop': {'feedback': {'action': 'stop', 'reason': 'Earlier stop.'}},
        'continue': {'feedback': {'action': 'continue', 'reason': 'Later explicitly authorized decision.'}},
    }
    archive.archive_split(run['root'], 'train')
    decision = read_memory(run['root'])[0][0]['body']['next_decision']
    assert decision['action'] == 'continue'
    assert decision['reason'] == 'Later explicitly authorized decision.'


@pytest.mark.parametrize('field', ['feedback', 'quality'])
def test_quality_only_observation_binds_its_evidence_without_a_lesson(run, field):
    note = save(run['task'] / 'analysis/resource-note.json', {'restriction': 'unmeasured CPU activity'})
    ref = {'path': str(note), 'sha256': archive.sha(note)}
    run['item']['observation_ids'] = ['quality']
    run['state']['observations']['quality'] = {
        'candidate_id': 'exp001', 'stage_ids': [], 'feedback': {'action': 'quality_update'},
        field: {'resource_note': ref},
    }
    archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    index = archive.load(base / 'evidence_index.json')
    assert any(entry['sha256'] == ref['sha256'] for entry in index.values())


@pytest.mark.parametrize('field', ['feedback', 'quality'])
def test_quality_only_observation_rejects_changed_evidence_before_publish(run, field):
    note = save(run['task'] / 'analysis/resource-note.json', {'restriction': 'original'})
    ref = {'path': str(note), 'sha256': archive.sha(note)}
    run['item']['observation_ids'] = ['quality']
    run['state']['observations']['quality'] = {
        'candidate_id': 'exp001', 'stage_ids': [], 'feedback': {'action': 'quality_update'},
        field: {'resource_note': ref},
    }
    save(note, {'restriction': 'changed after observation binding'})
    with pytest.raises(ValueError):
        archive.archive_split(run['root'], 'train')
    assert not (run['root'] / 'archive/train/v2/current.json').exists()


def manual_static(run):
    platform = save(run['root'] / 'bootstrap/platform-query.json', {'ub_bytes': 196608})
    review = save(run['candidate'] / 'static-review.json', {'status': 'passed_static_review',
        'platform': {'path': str(platform), 'sha256': archive.sha(platform)},
        'source': {'path': str(run['candidate'] / 'source.tar'), 'sha256': run['item']['source_hash']}})
    plan = {'source_hash': run['item']['source_hash'], 'manual_review': True}
    evidence = {'review': {'path': str(review), 'sha256': archive.sha(review)}}
    attempt = {'outcome': 'success', 'native_started': False, 'formal_samples': 0, 'evidence': evidence}
    run['state']['stages']['exp001-static'] = {'kind': 'static', 'candidate_id': 'exp001', 'plan': plan, 'attempts': [attempt]}
    for operation, timestamp, extra in [('start', '2026-09-11T12:00:00Z', {'candidate_id': 'exp001', 'kind': 'static', 'plan': plan}),
                                        ('finish', '2026-09-11T12:01:00Z', attempt)]:
        archive.campaign.Campaign.events.append({'operation': operation, 'recorded_at': timestamp,
            'hash': 'sha256:' + ('2' if operation == 'start' else '3') * 64,
            'arguments': {'workload': 'exp', 'stage_id': 'exp001-static', **extra}})
    return review, platform


def test_manual_static_stage_has_frozen_review_and_real_ledger_timeline(run):
    review, platform = manual_static(run)
    before = {p: p.read_bytes() for p in run['candidate'].rglob('*') if p.is_file()}
    result = archive.archive_split(run['root'], 'train')
    assert result['verification']['valid']
    rows, base = read_memory(run['root'])
    body = rows[0]['body']
    stage = body['evaluations'][0]['stages'][0]
    assert stage['name'] == 'static' and stage['status'] == 'passed'
    assert [(row['event_type'], row['timestamp']) for row in body['timeline']] == [
        ('start', '2026-09-11T12:00:00Z'), ('finish', '2026-09-11T12:01:00Z')]
    assert before == {p: p.read_bytes() for p in run['candidate'].rglob('*') if p.is_file()}
    assert not (run['candidate'] / 'stages/static/result.json').exists()
    index = archive.load(base / 'evidence_index.json')
    for path in (review, platform):
        assert any(entry['sha256'] == archive.sha(path) and '/external_evidence/' in entry['path'] for entry in index.values())
    assert body['machine_results'][0]['verdict'] == 'not_recorded'


@pytest.mark.parametrize('location', ['plan', 'attempt', 'review'])
def test_manual_stage_nested_wrong_hash_is_rejected(run, location):
    review, platform = manual_static(run)
    pointer = {'path': str(platform), 'sha256': 'sha256:' + 'f' * 64}
    stage = run['state']['stages']['exp001-static']
    if location == 'plan':
        stage['plan']['nested'] = {'evidence': [pointer]}
    elif location == 'attempt':
        stage['attempts'][0]['evidence']['nested'] = {'proof': pointer}
    else:
        save(review, {'status': 'passed_static_review', 'nested': {'proof': pointer}})
        stage['attempts'][0]['evidence']['review']['sha256'] = archive.sha(review)
    with pytest.raises(ValueError, match='evidence hash differs'):
        archive.archive_split(run['root'], 'train')
    assert not (run['root'] / 'archive/train/v2/current.json').exists()


def test_manual_stage_cross_split_nested_evidence_is_rejected(run):
    manual_static(run)
    other = save(run['root'] / 'validation/tasks/rsqrt/review.json', {'status': 'passed_static_review'})
    run['state']['stages']['exp001-static']['attempts'][0]['evidence']['nested'] = {
        'proof': {'path': str(other), 'sha256': archive.sha(other)}}
    with pytest.raises(ValueError, match='cross-split'):
        archive.archive_split(run['root'], 'train')


def test_repeated_archive_does_not_add_attempt_or_revision(run):
    stage(run)
    first = archive.archive_split(run['root'], 'train')
    second = archive.archive_split(run['root'], 'train')
    assert first['revision'] == second['revision']
    assert second['optimization_attempts'] == 1


def test_verify_is_a_pure_reader(run):
    stage(run)
    archive.archive_split(run['root'], 'train')
    files = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in run['root'].rglob('*') if p.is_file()}
    assert archive.verify_split(run['root'], 'train')['valid']
    assert files == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in run['root'].rglob('*') if p.is_file()}


def test_zero_source_task_has_only_checkpoint(run):
    run['state']['candidates'] = {}
    result = archive.archive_split(run['root'], 'train')
    assert result['optimization_attempts'] == 0 and result['task_checkpoints'] == 1
    assert result['lessons'] == 0


def test_stage_must_match_ledger_completion_hash(run):
    path = stage(run)
    save(path, {**archive.load(path), 'status': 'passed'})
    with pytest.raises(ValueError, match='evidence hash differs'):
        archive.archive_split(run['root'], 'train')
    assert not (run['root'] / 'archive/train/v2/current.json').exists()


def test_source_tar_and_patch_bind_full_bytes(run):
    (run['candidate'] / 'optimization.patch').write_text('changed after registration')
    with pytest.raises(ValueError, match='evidence hash differs'):
        archive.archive_split(run['root'], 'train')


def test_cross_split_reference_refused_before_read(run, tmp_path):
    hidden = run['root'] / 'validation/tasks/gelu/secret.json'
    save(hidden, {'validation': 'secret'})
    lesson = run['task'] / 'analysis/lessons.json'
    save(lesson, [dict(id='measurement', kind='measurement_method', operator='exp', split='train', title='Synthetic method fact',
        intervention={'statement': 'Observed failure.', 'basis': 'retrospective_current_evidence'},
        evidence=[dict(path=str(hidden))])])
    with pytest.raises(ValueError, match='cross-split'):
        archive.archive_split(run['root'], 'train')
    assert not (run['root'] / 'archive/train/v2/current.json').exists()


def test_native_tar_hash_checks_exact_source_members(run):
    tar = run['candidate'] / 'source.tar'
    expected = archive.native_tar_hash(tar, run['candidate'] / 'op')
    assert len(expected) == 64
    (run['candidate'] / 'op/op_host/exp.asc').write_text('tampered')
    with pytest.raises(ValueError, match='native members differ'):
        archive.native_tar_hash(tar, run['candidate'] / 'op')


def test_unsafe_tar_member_is_rejected(tmp_path):
    path = tmp_path / 'unsafe.tar'
    with tarfile.open(path, 'w') as out:
        member = tarfile.TarInfo('../op_host/exp.asc')
        member.size = 1
        out.addfile(member, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='unsafe source archive'):
        archive.native_tar_hash(path)


def cohort(run, monkeypatch, *, label='direct_parent', control_tar=None, control_tree=None):
    path = stage(run, status='passed', kind='timing', name='search')
    root = path.parent / label
    build = root / 'build/build_manifest.json'
    native_hashes = {'A': archive.native_tar_hash(control_tar or run['task'] / 'baseline-source.tar'),
                     'B': archive.native_tar_hash(run['candidate'] / 'source.tar')}
    save(build, {'roles': {role: {'source_dir': str(tree), 'source_sha256': native_hashes[role]}
                          for role, tree in [('A', control_tree or run['task'] / 'baseline'), ('B', run['candidate'] / 'op')]}})
    runner = save(root / 'runner/build.json', {'runner': 'synthetic fixture; never executed'})
    schedule, dirs = [], []
    for i in range(6):
        directory = root / ('session-' + str(i))
        save(directory / 'bindings.json', {})
        save(directory / 'completion.json', {'status': 'passed'})
        dirs.append(str(directory))
        schedule.append(dict(name=directory.name, request={'role_build': str(build), 'runner_build': str(runner)}))
    save(root / 'plan.json', {'schedule': schedule})
    save(root / 'group-completion.json', dict(status='passed', error=None, completed_sessions=dirs))
    report = dict(operator='exp', source_hashes=native_hashes, results=[dict(case_id='1', buffer_config='normal', speedup=1.1)],
                  suite={'normal': {'speedup': 1.1}}, calibration_cards={}, calibration_report_hash=None,
                  sessions=[dict(directory=d, artifacts={}, bound_artifacts={}) for d in dirs], **archive.POLICY)
    save(root / 'report.json', report)
    verify = Mock(return_value=deepcopy(report))
    monkeypatch.setattr(archive.analysis, 'analyze_task_cohort', verify)
    return root, report, verify


def test_new_comparison_is_reverified_and_keeps_results(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    archive.archive_split(run['root'], 'train')
    verify.assert_called_once()
    rows, _ = read_memory(run['root'])
    evaluation = rows[0]['body']['evaluations'][0]
    assert evaluation['cases'] == report['results']
    assert evaluation['summary']['suite'] == report['suite']
    assert evaluation['comparison']['baseline'] == run['baseline']
    assert evaluation['comparison']['candidate'] == run['item']['source_hash']
    assert evaluation['summary']['formal_admission'] == 'not_evaluated'


def test_saved_report_must_equal_fresh_analysis(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    save(root / 'report.json', {**report, 'suite': {'normal': {'speedup': 999}}})
    with pytest.raises(ValueError, match='saved report differs'):
        archive.archive_split(run['root'], 'train')


def test_attested_analyzer_upgrade_preserves_old_report_and_freezes_proof(run, monkeypatch):
    import msprof_exploration_provenance as provenance
    root, report, verify = cohort(run, monkeypatch)
    scripts = run['root'].parent / 'engineering/scripts'
    scripts.mkdir(parents=True)
    analyzer = scripts / 'msprof_exploration_report.py'
    analyzer.write_text('# historical analyzer\n')
    expected = archive.sha(analyzer)
    snapshot = run['root'] / 'bootstrap/source-cas' / expected[7:]
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(analyzer.read_bytes())
    freeze = save(run['root'] / 'bootstrap/frozen-engineering.json', {'files': [
        {'path': str(analyzer), 'sha256': expected, 'snapshot': str(snapshot)}]})
    analyzer.write_text('# current analyzer\n')
    monkeypatch.setattr(provenance, 'ENGINEERING_SCRIPTS', scripts)
    monkeypatch.setattr(provenance, 'campaign_root', lambda evidence_path: run['root'])
    monkeypatch.setattr(archive.analysis, '__file__', str(analyzer))
    report['analysis_producer_hash'] = expected
    save(root / 'report.json', report)
    raw = (root / 'report.json').read_bytes()
    verify.return_value = {**report, 'analysis_producer_hash': archive.sha(analyzer)}
    archive.archive_split(run['root'], 'train')
    rows, base = read_memory(run['root'])
    assert rows[0]['body']['evaluations'][0]['summary']['analysis_producer_hash'] == expected
    assert (root / 'report.json').read_bytes() == raw
    index = archive.load(base / 'evidence_index.json')
    for path in (snapshot, freeze):
        assert any(entry['sha256'] == archive.sha(path) for entry in index.values())


def inherited_run(run, tmp_path):
    path = stage(run, status='passed')
    prior_root = tmp_path / 'prior/archive/train/v2'
    prior_manifest = tmp_path / 'prior/recording.json'
    sources = dict(original_baseline={'path': str(run['task'] / 'baseline-source.tar')},
                   direct_parent={'path': str(run['task'] / 'baseline-source.tar')},
                   candidate={'path': str(run['candidate'] / 'source.tar')}, patch={'path': str(run['candidate'] / 'optimization.patch')}, parent_attempt_id=None)
    config = dict(run_id='old-run', task_id='exp', attempts=[dict(id='exp001', operator='exp', split='train', sources=sources,
        intervention=dict(statement='Historical intent stays intact.', basis='recorded_historical_proposal'),
        evaluations=[dict(id='historical-build', session_id='old-session', baseline='direct_parent', relation='original_attempt',
            stages=[dict(name='build', record={'path': str(path)})], measurement_quality='historical')])])
    save(prior_manifest, config)
    export.Recorder(prior_manifest, prior_root).export()
    config['attempts'][0]['next_decision'] = {'action': 'stop', 'reason': 'Original historical decision.'}
    save(prior_manifest, config)
    export.Recorder(prior_manifest, prior_root).export()
    pointer = archive.load(prior_root / 'current.json')
    old = v2.load_rows(prior_root / 'revisions' / pointer['revision'] / 'train/optimization_traces.jsonl')[0]
    assert old['revision'] == 2
    run['item'].update(inherited=True, stable_id=old['id'])
    save(run['task'] / 'inheritance-context.json', dict(inherited_attempt_id=old['id'],
        prior_dataset={'path': str(prior_root), 'current': {'path': str(prior_root / 'current.json'), 'sha256': archive.sha(prior_root / 'current.json')}}))
    return old


def test_inherited_record_preserves_history_in_new_revision(run, tmp_path):
    old = inherited_run(run, tmp_path)
    before = {p: p.read_bytes() for p in (tmp_path / 'prior').rglob('*') if p.is_file()}
    result = archive.archive_split(run['root'], 'train')
    current = read_memory(run['root'])[0][0]
    assert result['new_source_attempts'] == 0 and result['inherited_source_attempts'] == 1
    assert current['id'] == old['id'] and current['revision'] == 3 and current['previous_ref'] == old['record_hash']
    assert current['body']['evaluations'][:len(old['body']['evaluations'])] == old['body']['evaluations']
    assert current['body']['intervention'] == old['body']['intervention']
    assert current['body']['next_decision'] == old['body']['next_decision']
    assert before == {p: p.read_bytes() for p in (tmp_path / 'prior').rglob('*') if p.is_file()}
    assert archive.verify_split(run['root'], 'train')['valid']


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure_point', ['publish', 'verification'])
def test_inherited_publish_failure_never_changes_official_current(run, tmp_path, monkeypatch, existing, failure_point):
    inherited_run(run, tmp_path)
    current = run['root'] / 'archive/train/v2/current.json'
    if existing:
        archive.archive_split(run['root'], 'train')
    before = current.read_bytes() if existing else None
    real_publish = v2.publish
    calls = []
    def observed_publish(root, *args, **kwargs):
        assert Path(root) != current.parent
        assert (current.read_bytes() if current.exists() else None) == before
        assert (Path(root) / 'current.json').is_file()  # private inherited seed or prior revision
        calls.append(root)
        if failure_point == 'publish':
            raise RuntimeError('injected publication failure')
        return real_publish(root, *args, **kwargs)
    monkeypatch.setattr(v2, 'publish', observed_publish)
    if failure_point == 'verification':
        def failed_verification(*args, **kwargs):
            assert (current.read_bytes() if current.exists() else None) == before
            raise RuntimeError('injected verification failure')
        monkeypatch.setattr(archive, 'verify_dataset', failed_verification)
    with pytest.raises(RuntimeError, match='injected'):
        archive.archive_split(run['root'], 'train')
    assert len(calls) == 1
    assert (current.read_bytes() if current.exists() else None) == before


def test_inherited_success_has_one_public_commit_and_stable_evidence_paths(run, tmp_path, monkeypatch):
    inherited_run(run, tmp_path)
    current = run['root'] / 'archive/train/v2/current.json'
    replace = archive.os.replace
    commits = []
    def observe_replace(source, target):
        if Path(target) == current:
            assert not current.exists()
            commits.append((source, target))
        else:
            assert not current.exists()
        return replace(source, target)
    monkeypatch.setattr(archive.os, 'replace', observe_replace)
    result = archive.archive_split(run['root'], 'train')
    assert len(commits) == 1 and result['root'] == str(current.parent)
    _, base = read_memory(run['root'])
    index = archive.load(base / 'evidence_index.json')
    assert all(Path(row['path']).is_relative_to(current.parent / 'external_evidence') for row in index.values())
    before = {p: p.read_bytes() for p in current.parent.rglob('*') if p.is_file()}
    assert archive.verify_split(run['root'], 'train', deep=True)['valid']
    assert before == {p: p.read_bytes() for p in current.parent.rglob('*') if p.is_file()}


def test_recorded_knowledge_reads_use_frozen_snapshot_not_later_source(run):
    path = run['task'] / 'agent/read.txt'
    path.parent.mkdir()
    path.write_text('original knowledge content')
    snapshot = run['task'] / 'read-evidence/snapshot'
    snapshot.parent.mkdir()
    snapshot.write_bytes(path.read_bytes())
    save(run['task'] / 'knowledge-reads/1.json', dict(path=str(path), snapshot=str(snapshot), sha256=archive.sha(snapshot),
        purpose='Understand the selected mechanism.', classification='knowledge_read'))
    path.write_text('later changed source must not rewrite actual read evidence')
    archive.archive_split(run['root'], 'train')
    rows, _ = read_memory(run['root'])
    assert rows[0]['body']['knowledge']['actual_reads'][0]['purpose'] == 'Understand the selected mechanism.'


def test_source_read_is_timeline_not_knowledge_claim(run):
    from msprof_exploration_execute import event
    event(run['task'], 'actual_read', dict(path=str(run['candidate'] / 'proposal.json'), purpose='Read my proposal.',
        classification='source_or_feedback_read'))
    archive.archive_split(run['root'], 'train')
    rows, _ = read_memory(run['root'])
    assert rows[0]['body']['knowledge']['actual_reads'] == []
    assert rows[0]['body']['timeline'][0]['event_type'] == 'actual_read'


def test_registered_agent_proposal_pointer_supported(run):
    path = run['task'] / 'agent/proposal.json'
    path.parent.mkdir()
    (run['candidate'] / 'proposal.json').rename(path)
    run['item']['artifacts'] = {'proposal': {'path': str(path), 'sha256': archive.sha(path)}}
    assert archive.archive_split(run['root'], 'train')['optimization_attempts'] == 1


def fresh_planning_run(run, monkeypatch):
    from test_planning import context_example
    from aprof_runtime.jsonio import canonical_json
    import shutil
    old_task = run['task']; new_task = old_task.with_name('maximum'); old_task.rename(new_task)
    run['task'] = new_task; run['candidate'] = new_task / 'candidates/exp001'
    save(new_task / 'manifest.json', dict(operator='maximum', split='train', source_split='test'))
    declaration = dict(baseline_source_hash=run['baseline'], split='train', source_split='test')
    class Ledger:
        config_hash = 'sha256:' + '0' * 64
        config = {'schema_version': archive.campaign.FRESH_SCHEMA, 'tasks': {'maximum': declaration}}
        events = [dict(hash='sha256:' + '1' * 64, arguments={}, operation='prepare', recorded_at='2026-10-05T00:00:00Z')]
        def __init__(self, directory): self.state = {'tasks': {'maximum': run['state']}}
        def verify(self): return {'valid': True}
    monkeypatch.setattr(archive.campaign, 'Campaign', Ledger)
    values = context_example()['evidence']
    profile, plan, dispatch = (values[k] for k in ('architecture_profile', 'parallel_plan', 'dispatch_plan'))
    preflight = run['root'] / 'preflight'
    raw = dict(soc_name=profile['soc_name'], probe_kind=profile['probe_kind'], device_id=profile['device_id'],
               platform={k: profile[k] for k in ('npu_arch', 'core_counts', 'memory_bytes')})
    raw_path = preflight / 'raw.json'; raw_path.parent.mkdir(parents=True); raw_path.write_text(canonical_json(raw))
    source_proof = save(preflight / 'producer.json', {'test': 'synthetic source evidence'})
    for key in profile['provenance']: profile['provenance'][key] = archive.sha(source_proof)
    profile['provenance']['raw_probe_ref'] = archive.sha(raw_path)
    profile['capabilities']['vector']['evidence_refs'] = [archive.sha(raw_path)]
    plan.update(operator='maximum', source_hash=run['baseline'], architecture_profile_ref=archive.content_hash(profile))
    plan['groups'][0]['selection_evidence'] = [archive.sha(source_proof)]
    dispatch.update(operator='maximum', source_hash=run['item']['source_hash'], plan_basis_source_hash=run['baseline'],
        implementation_source_hash=run['item']['source_hash'], architecture_profile_ref=archive.content_hash(profile), parallel_plan_ref=archive.content_hash(plan))
    artifacts = {}
    proposal = dict(statement='Use a metadata-selected implementation.', optimization_stage='execution',
        plan_basis_source_hash=run['baseline'], implementation_source_hash=run['item']['source_hash'],
        dispatch_selections=[dict(metadata={'shape':[128], 'dtype':'float32','layout':'ND','attributes':{}},
                                  tiling_key=1,kernel_entry='small_entry',group_id='generic')])
    for kind, value in (('architecture_profile',profile),('parallel_plan',plan),('dispatch_plan',dispatch)):
        path = save(run['candidate'] / 'plans' / (kind + '.json'), value)
        artifacts[kind] = {'path':str(path),'sha256':archive.sha(path)}
        proposal[kind+'_ref'] = archive.content_hash(value)
    graph_root=run['root']/'graph/v0002'
    shutil.copytree(Path(archive.__file__).resolve().parents[1]/'skillgraph/versions/v0002',graph_root)
    artifacts['graph_snapshot']={'path':str(graph_root/'graph.json'),'sha256':archive.sha(graph_root/'graph.json')}
    artifacts['graph_bundle']=[{'path':str(path),'sha256':archive.sha(path)} for path in sorted(graph_root.iterdir()) if path.is_file()]
    proposal['graph_hash']=archive.content_hash(archive.load(graph_root/'graph.json'))
    save(run['candidate']/'proposal.json',proposal)
    run['item']['artifacts']=artifacts
    return run


def test_fresh_test_origin_is_research_train_with_bound_planning_and_real_memory_refs(run, monkeypatch):
    fresh_planning_run(run, monkeypatch); stage(run)
    proposal = archive.load(run['candidate']/'proposal.json')
    proposal['optimization_stage'] = 'algorithm_parallel'
    save(run['candidate']/'proposal.json', proposal)
    save(run['task']/'analysis/lessons.json', [dict(id='dispatch-lesson',kind='operator_optimization',operator='maximum',
        title='Workload dispatch observation',source_attempt_ids=['exp001'],
        graph_links=[{'graph_version':'v0002','node_id':'transformation.select_parallel_algorithm','basis':'Retrospective association, not a route'}],
        intervention={'statement':'Use shape-conditioned entry.', 'basis':'retrospective'},
        evidence=[{'path':str(run['candidate']/'proposal.json')}])])
    result=archive.archive_split(run['root'],'train')
    rows,base=read_memory(run['root']);body=rows[0]['body']
    assert body['intervention']['attributes']['optimization_stage']=='algorithm_parallel'
    assert body['intervention']['attributes']['source_split']=='test'
    assert body['intervention']['attributes']['implementation_source_hash']==run['item']['source_hash']
    lessons=v2.load_rows(base/'train/lessons.jsonl')
    assert lessons[0]['body']['memory_refs']==[{'id':rows[0]['id'],'record_hash':rows[0]['record_hash']}]
    assert result['verification']['valid'] and body['machine_results'][0]['episode_ref'] is None


@pytest.mark.parametrize('fault',['implementation','profile_ref','key','proof'])
def test_fresh_planning_mismatch_fails_before_publication(run,monkeypatch,fault):
    fresh_planning_run(run,monkeypatch)
    path=run['candidate']/'proposal.json';value=archive.load(path)
    if fault=='implementation':value['implementation_source_hash']='sha256:'+'f'*64
    elif fault=='profile_ref':value['architecture_profile_ref']='sha256:'+'f'*64
    elif fault=='key':value['dispatch_selections'][0]['tiling_key']=999
    else:(run['root']/'preflight/raw.json').write_text('{}')
    save(path,value)
    with pytest.raises(ValueError):archive.archive_split(run['root'],'train')
    assert not (run['root']/'archive/train/v2/current.json').exists()


def test_fresh_operator_lesson_requires_its_actual_source_attempt(run,monkeypatch):
    fresh_planning_run(run,monkeypatch)
    save(run['task']/'analysis/lessons.json',[dict(id='missing-links',kind='operator_optimization',operator='maximum',
        title='Unbound',intervention={'statement':'No source binding','basis':'retrospective'},evidence=[])])
    with pytest.raises(ValueError,match='source_attempt_ids'):archive.archive_split(run['root'],'train')


def test_fresh_archive_rejects_historical_feature_checkout_before_read(run,monkeypatch,tmp_path):
    fresh_planning_run(run,monkeypatch)
    old=tmp_path/'aprof-feat-aprofgraph'/'payload.json';save(old,{'old':'forbidden'})
    with pytest.raises(ValueError,match='historical feature checkout'):archive.Archive(run['root'],'train').pointer(old,'maximum')


def test_method_lesson_without_source_attempt(run):
    run['state']['candidates'] = {}
    path = run['task'] / 'analysis/lessons.json'
    save(path, [dict(id='method-one', kind='measurement_method', operator='exp', title='Recorded method checkpoint',
        intervention={'statement': 'Stop before hardware until a source proposal exists.', 'basis': 'retrospective_current_evidence'},
        evidence=[{'path': str(run['task'] / 'manifest.json')}])])
    result = archive.archive_split(run['root'], 'train')
    assert result['lessons'] == 1 and result['optimization_attempts'] == 0


@pytest.mark.parametrize('payload', [
    {'evidence': {'native_started': False, 'changed_fields': ['final_candidate_ids']}},
    {'evidence': 'Recorded explanatory text, not a file pointer'},
    {'nested': [{'evidence': [{'path': '/nonexistent/opaque-description.json'}]}]},
])
def test_opaque_lesson_attributes_roundtrip_without_evidence_key_loss(run, payload):
    path = run['task'] / 'analysis/lessons.json'
    save(path, [dict(id='opaque-one', kind='measurement_method', operator='exp',
        title='Preserve recorded repair payload', source_attempt_ids=['exp001'],
        intervention={'statement': 'Repair only prestart reservations.',
                      'basis': 'recorded_evidence', 'attributes': payload},
        evidence=[{'path': str(run['task'] / 'manifest.json'),
                   'sha256': archive.sha(run['task'] / 'manifest.json')}])])
    original = path.read_bytes()
    result = archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    lesson = v2.load_rows(base / 'train/lessons.jsonl')[0]['body']
    assert lesson['intervention']['attributes']['attributes'] == payload
    assert lesson['intervention']['evidence_ids'] and lesson['memory_refs']
    assert path.read_bytes() == original
    assert result['verification']['valid']
    assert '/nonexistent/opaque-description.json' not in str(archive.load(base / 'evidence_index.json'))


@pytest.mark.parametrize('bad_evidence', [
    {'native_started': False}, 'not a pointer list', [{'path': 7}],
])
def test_malformed_structural_lesson_evidence_does_not_publish(run, bad_evidence):
    archive.archive_split(run['root'], 'train')
    current = run['root'] / 'archive/train/v2/current.json'
    before = current.read_bytes()
    path = run['task'] / 'analysis/lessons.json'
    save(path, [dict(id='bad-one', kind='measurement_method', operator='exp', title='Bad evidence',
        intervention={'statement': 'Malformed structural evidence remains invalid.'},
        evidence=bad_evidence)])
    with pytest.raises(ValueError, match='structural lesson evidence must be a pointer list'):
        archive.archive_split(run['root'], 'train')
    assert current.read_bytes() == before


def test_opaque_attribute_protection_does_not_change_legacy_stringification(run):
    path = run['task'] / 'analysis/lessons.json'
    limitations = [{'attributes': {'foo': 'bar'}}, {'details': [{'attributes': {'count': 2}}]},
                   {'attributes': 'ordinary nested limitation text'}]
    payload = {'evidence': {'native_started': False}, 'literal': 'msprof-opaque-attributes-json-v1:test'}
    save(path, [dict(id='stringification-one', kind='measurement_method', operator='exp', title='Preserve boundaries',
        intervention={'statement': 'Keep fact JSON and limitation strings separate.',
                      'attributes': payload, 'limitations': limitations},
        effective_conditions=[{'statement': 'Nested fact attributes survive.', 'attributes': payload}],
        diagnosis={'symptoms': [{'statement': 'Observed.', 'attributes': payload}]},
        evidence=[{'path': str(run['task'] / 'manifest.json')}])])
    archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    body = v2.load_rows(base / 'train/lessons.jsonl')[0]['body']
    assert body['intervention']['limitations'] == [json.dumps(value, ensure_ascii=False) for value in limitations]
    for fact in [body['intervention'], body['effective_conditions'][0], body['diagnosis']['symptoms'][0]]:
        assert fact['attributes']['attributes'] == payload


def test_nested_opaque_attributes_preserve_payload_and_structural_refs(run):
    path = run['task'] / 'analysis/lessons.json'
    ref = {'path': str(run['task'] / 'manifest.json')}
    payload = {'evidence': {'native_started': False}, 'nested': [{'evidence': 'explanatory text'}]}
    limitation = {'details': {'attributes': payload}}
    save(path, [dict(id='nested-opaque-one', kind='measurement_method', operator='exp', title='Nested attributes',
        intervention={'statement': 'Preserve nested JSON without losing real references.',
                      'details': {'attributes': payload, 'evidence': [ref], 'evidence_ids': ['unbound-input-id']},
                      'limitations': [limitation]},
        claims=[{'statement': 'Conditional result.', 'status': 'inconclusive',
                 'details': {'attributes': payload}, 'evidence': [ref]}],
        evidence=[ref])])
    archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    body = v2.load_rows(base / 'train/lessons.jsonl')[0]['body']
    details = body['intervention']['attributes']['details']
    assert details['attributes'] == payload
    assert details['evidence_ids']
    assert 'unbound-input-id' not in details['evidence_ids']
    assert body['intervention']['limitations'] == [json.dumps(limitation, ensure_ascii=False)]
    assert body['claims'][0]['attributes']['details']['attributes'] == payload
    assert body['claims'][0]['evidence_ids'] and body['claims'][0]['status'] == 'inconclusive'


def test_real_report_fixture_roundtrip(run, monkeypatch):
    # The report suite's builder creates synthetic CSV/journal/binary bytes only.
    import test_msprof_exploration_report as fixture
    path = stage(run, status='passed', kind='timing', name='search')
    root = path.parent / 'direct_parent'
    dirs, plan = fixture.make_cohort(root, kind='ab')
    build = archive.load(plan['schedule'][0]['request']['role_build'])
    def retar(path, tree):
        with tarfile.open(path, 'w') as out:
            for sub in ('op_host', 'op_kernel'):
                for file in sorted((tree / sub).rglob('*')):
                    if file.is_file():
                        data = file.read_bytes()
                        info = tarfile.TarInfo('source/' + file.relative_to(tree).as_posix())
                        info.size = len(data)
                        out.addfile(info, io.BytesIO(data))
        return archive.sha(path)
    baseline = retar(run['task'] / 'baseline-source.tar', Path(build['roles']['A']['source_dir']))
    run['item']['source_hash'] = retar(run['candidate'] / 'source.tar', Path(build['roles']['B']['source_dir']))
    run['item']['source_parent']['source_hash'] = baseline
    instance = archive.campaign.Campaign(run['root'] / 'train/ledger')
    instance.config['tasks']['exp']['baseline_source_hash'] = baseline
    monkeypatch.setattr(archive.analysis, 'analyze_task_cohort', fixture.report.analyze_task_cohort)
    # fixture.report is the same module object; restore via its saved import below.
    import importlib.util
    spec = importlib.util.spec_from_file_location('independent_archive_report_test', Path(archive.analysis.__file__))
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    monkeypatch.setattr(archive.analysis, 'analyze_task_cohort', real.analyze_task_cohort)
    report = real.analyze_task_cohort(dirs, plan)
    save(root / 'plan.json', plan)
    save(root / 'report.json', report)
    save(root / 'group-completion.json', dict(status='passed', error=None, completed_sessions=[str(d) for d in dirs]))
    result = archive.archive_split(run['root'], 'train')
    assert result['verification']['valid']
    rows, _ = read_memory(run['root'])
    assert rows[0]['body']['evaluations'][0]['cases'] == report['results']


def test_calibration_scope_environment_enters_frozen_closure(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    environment = save(run['root'] / 'bootstrap/environment.json', {'kind': 'shared_environment', 'driver': 'fixture'})
    report['calibration_scope_artifacts'] = {str(environment): archive.sha(environment)}
    save(root / 'report.json', report)
    verify.return_value = deepcopy(report)
    archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    index = archive.load(base / 'evidence_index.json')
    assert any(row['sha256'] == archive.sha(environment) and '/external_evidence/' in row['path'] for row in index.values())


def aa_stage(run, name, calibration, *, status='passed'):
    root = run['task'] / 'stages' / name
    result = save(root / 'result.json', dict(stage_id=name, candidate_id=None, kind='control',
                                          status=status, **archive.POLICY))
    run['state']['stages'][name] = dict(kind='control', candidate_id=None, plan={'control_type': 'aa'},
        attempts=[dict(outcome='success' if status == 'passed' else 'failed',
                       evidence={'result': {'path': str(result), 'sha256': archive.sha(result)}})])
    return save(root / 'cohort/report.json', calibration)


@pytest.mark.parametrize('group', ['aa-initial', 'aa-initial-02'])
def test_ab_calibration_uses_same_split_task_directory(run, monkeypatch, group):
    root, report, verify = cohort(run, monkeypatch)
    calibration = {'fixture': 'previously frozen same-split A/A report'}
    path = aa_stage(run, group, calibration)
    aa_stage(run, 'aa-initial-failed', calibration, status='failed')
    report['calibration_report_hash'] = archive.analysis.digest(calibration)
    save(root / 'report.json', report)
    verify.return_value = deepcopy(report)
    archive.archive_split(run['root'], 'train')
    assert verify.call_args.kwargs['calibration'] == calibration
    _, base = read_memory(run['root'])
    assert any(row['sha256'] == archive.sha(path) for row in archive.load(base / 'evidence_index.json').values())


def test_ab_calibration_rejects_multiple_registered_matching_reports(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    calibration = {'fixture': 'same bytes in two successful A/A stages'}
    aa_stage(run, 'aa-initial', calibration)
    aa_stage(run, 'aa-initial-02', calibration)
    report['calibration_report_hash'] = archive.analysis.digest(calibration)
    save(root / 'report.json', report)
    with pytest.raises(ValueError, match='calibration report is ambiguous'):
        archive.archive_split(run['root'], 'train')


def test_ab_calibration_ignores_unregistered_or_other_task_reports(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    calibration = {'fixture': 'not registered for the measured task'}
    save(run['task'] / 'stages/aa-initial/cohort/report.json', calibration)
    save(run['root'] / 'train/tasks/other/stages/aa-initial-02/cohort/report.json', calibration)
    report['calibration_report_hash'] = archive.analysis.digest(calibration)
    save(root / 'report.json', report)
    with pytest.raises(ValueError, match='calibration report is unavailable'):
        archive.archive_split(run['root'], 'train')


def test_each_comparison_uses_its_frozen_source_specific_calibration(run, monkeypatch):
    child = run['task'] / 'candidates/exp002_new'
    child.mkdir()
    full_hash = source(child / 'source.tar', child / 'op', 'second optimized source')
    (child / 'optimization.patch').write_text('second source change')
    save(child / 'proposal.json', {'intent': 'Optimize the registered direct parent.'})
    item = dict(candidate_id='exp002_new', source_hash=full_hash, patch_hash=archive.sha(child / 'optimization.patch'),
                source_parent={'candidate_id': 'exp001', 'source_hash': run['item']['source_hash']},
                stable_id='new-run/train/exp002_new', inherited=False, observation_ids=[])
    run['state']['candidates']['exp002_new'] = item
    child_run = {**run, 'candidate': child, 'candidate_id': 'exp002_new', 'item': item}
    direct, direct_report, _ = cohort(child_run, monkeypatch, control_tar=run['candidate'] / 'source.tar',
                                       control_tree=run['candidate'] / 'op')
    original, original_report, _ = cohort(child_run, monkeypatch, label='original_baseline')
    parent_cal = {'source_hashes': {'A': direct_report['source_hashes']['A']}, 'fixture': 'direct-parent A/A'}
    baseline_cal = {'source_hashes': {'A': original_report['source_hashes']['A']}, 'fixture': 'original baseline A/A'}
    parent_path = aa_stage(run, 'aa-exp001', parent_cal)
    baseline_path = aa_stage(run, 'aa-initial-02', baseline_cal)
    ptr = lambda path: {'path': str(path), 'sha256': archive.sha(path)}
    run['state']['stages']['search']['plan'] = {'calibration_report': ptr(baseline_path),
        'cohorts': [{'relation': 'direct_parent', 'calibration_report': ptr(parent_path)},
                    {'relation': 'original_baseline'}]}
    for root, report, calibration in [(direct, direct_report, parent_cal), (original, original_report, baseline_cal)]:
        report['calibration_report_hash'] = archive.analysis.digest(calibration)
        save(root / 'report.json', report)
    seen = {}
    def reanalyze(paths, plan, *, calibration):
        root = paths[0].parent
        report = archive.load(root / 'report.json')
        assert calibration['source_hashes']['A'] == report['source_hashes']['A']
        seen[root.name] = calibration
        return report
    monkeypatch.setattr(archive.analysis, 'analyze_task_cohort', reanalyze)
    result = archive.archive_split(run['root'], 'train')
    assert result['verification']['valid']
    assert seen == {'direct_parent': parent_cal, 'original_baseline': baseline_cal}
    rows, _ = read_memory(run['root'])
    child_row = next(row for row in rows if row['body']['identity']['candidate_id'] == 'exp002_new')
    assert len(child_row['body']['evaluations']) == 2


def test_cohort_report_must_match_frozen_calibration_selection(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    selected = aa_stage(run, 'aa-selected', {'fixture': 'selected'})
    other = aa_stage(run, 'aa-other', {'fixture': 'different card'})
    report['calibration_report_hash'] = archive.analysis.digest(archive.load(other))
    save(root / 'report.json', report)
    run['state']['stages']['search']['plan'] = {'cohorts': [{'relation': 'direct_parent',
        'calibration_report': {'path': str(selected), 'sha256': archive.sha(selected)}}]}
    with pytest.raises(ValueError, match='calibration differs from frozen stage plan'):
        archive.archive_split(run['root'], 'train')
    verify.assert_not_called()


def test_fixed_aa_reanalyzes_registered_candidate_source_without_candidate_timing(run, monkeypatch):
    original, report, verify = cohort(run, monkeypatch, control_tar=run['candidate'] / 'source.tar',
                                       control_tree=run['candidate'] / 'op')
    destination = run['task'] / 'stages/aa-exp001'
    destination.parent.mkdir(parents=True)
    original.parent.rename(destination)
    root = destination / 'cohort'
    (destination / 'direct_parent').rename(root)
    for path in destination.rglob('*.json'):
        path.write_text(path.read_text().replace(str(original), str(root)))
    report = archive.load(root / 'report.json')
    verify.return_value = deepcopy(report)
    run['state']['stages'].pop('search')
    result = save(destination / 'result.json', dict(stage_id='baseline-aa-exp001', candidate_id=None,
                  kind='control', status='passed', **archive.POLICY))
    run['state']['stages']['baseline-aa-exp001'] = {'kind': 'control', 'candidate_id': None,
        'plan': {'control_type': 'aa', 'source_hash': run['item']['source_hash']},
        'attempts': [{'outcome': 'success', 'evidence': {'result': {'path': str(result), 'sha256': archive.sha(result)}}}]}
    published = archive.archive_split(run['root'], 'train')
    assert published['verification']['valid']
    assert verify.call_args.kwargs['calibration'] is None
    assert read_memory(run['root'])[0][0]['body']['evaluations'] == []
    assert run['state']['used']['timing_groups'] == 0


def test_fixed_control_rejects_unregistered_source_identity(run):
    with pytest.raises(ValueError, match='fixed control source is not registered'):
        archive.Archive(run['root'], 'train').control_source_tar('exp', 'sha256:' + 'f' * 64)


def test_standalone_correctness_subtree_is_preserved(run):
    result = stage(run, status='passed', kind='correctness', name='correctness')
    evidence = result.parent / 'standalone/case_01/native.json'
    save(evidence, {'status': 'passed', 'standalone': True})
    archive.archive_split(run['root'], 'train')
    _, base = read_memory(run['root'])
    assert any(row['sha256'] == archive.sha(evidence) for row in archive.load(base / 'evidence_index.json').values())


def frozen_script(run, monkeypatch, *, freeze=True):
    scripts = run['root'].parent / 'engineering/scripts'
    scripts.mkdir(parents=True)
    monkeypatch.setattr(archive, 'ENGINEERING_SCRIPTS', scripts)
    live = scripts / 'stage.py'
    live.write_text('# original executed producer\n')
    expected = archive.sha(live)
    snapshot = run['root'] / 'bootstrap/source-cas' / expected[7:]
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(live.read_bytes())
    declaration = dict(path=str(live), sha256=expected, snapshot=str(snapshot))
    if freeze:
        save(run['root'] / 'bootstrap/frozen-engineering.json', {'revision': 'engineering-01', 'files': [declaration]})
    live.write_text('# newly repaired producer, not the old execution\n')
    return live, snapshot, declaration


def test_changed_producer_binds_exact_frozen_bytes_and_preserves_origin(run, monkeypatch):
    live, snapshot, declared = frozen_script(run, monkeypatch)
    result = stage(run)
    run['state']['stages']['build']['plan'] = {'producer': {'path': str(live), 'sha256': declared['sha256']}}
    before = result.read_bytes()
    archive.archive_split(run['root'], 'train')
    assert result.read_bytes() == before
    _, base = read_memory(run['root'])
    metadata = archive.load(base / 'metadata.json')
    binding = metadata['engineering_snapshot_bindings'][0]
    assert binding['origin'] == {'path': str(live), 'sha256': declared['sha256']}
    assert binding['snapshot']['path'] == str(snapshot)
    assert binding['observed_live_sha256'] == archive.sha(live) != declared['sha256']
    assert binding['live_path_contains_expected_bytes'] is False
    index = archive.load(base / 'evidence_index.json')
    refs = [ref for ref, item in index.items() if item['sha256'] == declared['sha256']]
    assert refs and Path(index[refs[0]]['path']).read_bytes() == snapshot.read_bytes()
    assert str(live) in metadata['original_evidence_locations'][refs[0]]
    assert any(item['sha256'] == archive.sha(run['root'] / 'bootstrap/frozen-engineering.json') for item in index.values())


def test_changed_producer_without_manifest_is_rejected(run, monkeypatch):
    live, snapshot, declared = frozen_script(run, monkeypatch, freeze=False)
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='evidence hash differs'):
        bridge.audit_paths({'producer': {'path': str(live), 'sha256': declared['sha256']}}, 'exp')


def test_expected_hash_selects_frozen_engineering_revision(run, monkeypatch):
    live, snapshot, declared = frozen_script(run, monkeypatch)
    save(run['root'] / 'bootstrap/frozen-engineering-02.json', {'revision': 'engineering-02', 'files': [
        {**declared, 'sha256': archive.sha(live), 'snapshot': str(run['root'] / 'bootstrap/source-cas' / archive.sha(live)[7:])}]})
    bridge = archive.Archive(run['root'], 'train')
    # An earlier unbound read of the live file cannot satisfy the old hash.
    assert bridge.pointer(live)['sha256'] != declared['sha256']
    bound = bridge.pointer(live, expected=declared['sha256'])
    assert bound['path'] == str(snapshot) and bound['sha256'] == declared['sha256']
    assert len(bridge.engineering_bindings) == 1


def test_changed_input_never_uses_engineering_snapshot(run, monkeypatch):
    live, snapshot, declared = frozen_script(run, monkeypatch)
    inp = run['task'] / 'prepared/input.py'
    inp.parent.mkdir()
    inp.write_text('# changed input, even if a script extension is used\n')
    save(run['root'] / 'bootstrap/frozen-engineering.json', {'files': [{**declared, 'path': str(inp)}]})
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='evidence hash differs'):
        bridge.audit_paths({'input': {'path': str(inp), 'sha256': declared['sha256']}}, 'exp')


def test_corrupt_frozen_producer_is_rejected(run, monkeypatch):
    live, snapshot, declared = frozen_script(run, monkeypatch)
    snapshot.write_text('# corrupted frozen bytes\n')
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='snapshot hash differs'):
        bridge.pointer(live, expected=declared['sha256'])


def test_pointer_dictionary_hash_is_checked_even_for_relative_paths(run):
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='evidence hash differs'):
        bridge.audit_paths({'nested': {'path': 'train/tasks/exp/manifest.json', 'sha256': 'sha256:' + '0' * 64}}, 'exp')


def test_legacy_runner_hash_is_verified_and_original_manifest_is_preserved(run, monkeypatch):
    root, report, verify = cohort(run, monkeypatch)
    build = root / 'build/build_manifest.json'
    runner = root / 'build/shared_context_runner'
    runner.write_bytes(b'original shared-context runner bytes; never executed')
    original = {**archive.load(build), 'version': 'shared_context_build_v1',
                'runner': {'path': str(runner), 'sha256': archive.sha(runner)[7:]}}
    save(build, original)
    original_bytes = build.read_bytes()
    result = archive.archive_split(run['root'], 'train')
    assert result['verification']['valid']
    assert build.read_bytes() == original_bytes
    _, base = read_memory(run['root'])
    bindings = archive.load(base / 'metadata.json')['pointer_hash_normalizations']
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding == {
        'binding_mode': 'shared_context_build_v1_runner_raw_sha256', 'field': '/runner/sha256',
        'source_object_sha256': v2.digest(original), 'original_pointer': original['runner'],
        'normalized_pointer': {'path': str(runner), 'sha256': archive.sha(runner)},
        'source_document': {'path': str(build), 'sha256': archive.sha(build)}}
    index = archive.load(base / 'evidence_index.json')
    assert any(item['sha256'] == archive.sha(runner) for item in index.values())
    originals = [item for item in index.values() if item['sha256'] == archive.sha(build)]
    assert originals and Path(originals[0]['path']).read_bytes() == original_bytes


def test_legacy_runner_hash_still_rejects_changed_binary_even_after_unbound_read(run):
    runner = run['task'] / 'shared_context_runner'
    runner.write_bytes(b'original bytes')
    value = {'version': 'shared_context_build_v1', 'runner': {'path': str(runner), 'sha256': archive.sha(runner)[7:]}}
    runner.write_bytes(b'tampered bytes')
    bridge = archive.Archive(run['root'], 'train')
    bridge.pointer(runner, 'exp')
    with pytest.raises(ValueError, match='evidence hash differs'):
        bridge.audit_paths(value, 'exp')
    assert bridge.pointer_hash_normalizations == {}


@pytest.mark.parametrize('version,field', [
    ('shared_context_build_v2', 'runner'), (None, 'runner'),
    ('shared_context_build_v1', 'standalone'), ('shared_context_build_v1', 'producer'),
    ('shared_context_build_v1', 'component_builds')])
def test_bare_hash_remains_forbidden_outside_exact_legacy_runner_field(run, version, field):
    path = run['task'] / 'manifest.json'
    value = {'version': version, field: {'path': str(path), 'sha256': archive.sha(path)[7:]}}
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='invalid evidence pointer hash'):
        bridge.audit_paths(value, 'exp')
    assert bridge.pointer_hash_normalizations == {}


@pytest.mark.parametrize('digest', ['f' * 63, 'f' * 65, 'A' * 64, 'g' * 64, 123, None])
def test_malformed_legacy_runner_hash_is_never_normalized(run, digest):
    value = {'version': 'shared_context_build_v1',
             'runner': {'path': str(run['task'] / 'manifest.json'), 'sha256': digest}}
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='pointer hash'):
        bridge.audit_paths(value, 'exp')
    assert bridge.pointer_hash_normalizations == {}


def test_runner_normalization_does_not_mutate_input_or_allow_other_raw_pointers(run):
    path = run['task'] / 'manifest.json'
    pointer = {'path': str(path), 'sha256': archive.sha(path)[7:]}
    value = {'version': 'shared_context_build_v1', 'runner': pointer, 'other': pointer}
    original = deepcopy(value)
    bridge = archive.Archive(run['root'], 'train')
    with pytest.raises(ValueError, match='invalid evidence pointer hash'):
        bridge.audit_paths(value, 'exp')
    assert value == original and value['runner'] is value['other']


def preparation_relocation(run, monkeypatch):
    fresh_planning_run(run, monkeypatch)
    import msprof_exploration_execute as execute
    task=run['task'];old=task/'input-generation/started.json';snapshot=task/'input-generation-failed-01/started.json'
    save(snapshot,{'hardware_executed':False,'status':'interrupted'});expected=archive.sha(snapshot)
    execute.event(task,'input_generation_started',{'request':{'path':str(old),'sha256':expected}})
    save(old,{'hardware_executed':False,'status':'new-attempt'})
    manifest=save(task/'evidence-relocations-v2.json',dict(version='fresh_preparation_relocations_v1',operator='maximum',
        task_manifest={'path':str(task/'manifest.json'),'sha256':archive.sha(task/'manifest.json')},
        entries=[dict(origin={'path':str(old),'sha256':expected},snapshot={'path':str(snapshot),'sha256':expected},reason='Preserve failed preparation bytes')]))
    execute.event(task,'preparation_evidence_relocated',{'manifest':{'path':str(manifest),'sha256':archive.sha(manifest)}})
    return old,snapshot,expected,manifest


def test_fresh_preparation_relocation_requires_prior_event_and_exact_retained_bytes(run,monkeypatch):
    old,snapshot,expected,manifest=preparation_relocation(run,monkeypatch)
    adapter=archive.Archive(run['root'],'train')
    result=adapter.pointer(old,'maximum',expected=expected)
    assert result=={'path':str(snapshot),'sha256':expected}
    assert len(adapter.preparation_relocations)==1
    # A normal read still describes the new attempt, never the failed one.
    assert adapter.pointer(old,'maximum')['sha256']==archive.sha(old)


@pytest.mark.parametrize('fault',['manifest','snapshot','event','input_scope'])
def test_fresh_preparation_relocation_rejects_unattested_or_mutated_alias(run,monkeypatch,fault):
    old,snapshot,expected,manifest=preparation_relocation(run,monkeypatch)
    if fault=='manifest':save(manifest,{'version':'forged'})
    elif fault=='snapshot':save(snapshot,{'hardware_executed':False,'status':'tampered'})
    elif fault=='event':
        p=run['task']/'events.jsonl';rows=v2.load_rows(p);rows[0]['hash']='sha256:'+'f'*64;p.write_bytes(b''.join(v2.canonical(row) for row in rows))
    else:
        old=save(run['task']/'inputs/x.bin',{'changed':True})
    with pytest.raises(ValueError):archive.Archive(run['root'],'train').pointer(old,'maximum',expected=expected)


def test_fresh_graph_bundle_cannot_change_provenance_after_registration(run, monkeypatch):
    fresh_planning_run(run, monkeypatch)
    graph = run['root'] / 'graph/v0002'
    save(graph / 'lineage.json', {'changed': 'after registration'})
    checksums = archive.load(graph / 'checksums.json')
    checksums['files']['lineage.json'] = archive.sha(graph / 'lineage.json').removeprefix('sha256:')
    save(graph / 'checksums.json', checksums)
    with pytest.raises(ValueError, match='hash|changed|checksum'):
        archive.archive_split(run['root'], 'train')
    assert not (run['root'] / 'archive/train/v2/current.json').exists()


def local_method_fixture(run, monkeypatch, *, passed=True):
    root=run['task']/'stages/raw-local-method-01';directory=root/'evidence'
    run['state']['candidates']={};run['state']['new_rounds_started']=0
    raw=directory/'raw/PROF/device_0/data.bin';raw.parent.mkdir(parents=True);raw.write_bytes(b'full raw bytes')
    output=directory/'native/1_normal_A.bin';output.parent.mkdir(parents=True);output.write_bytes(b'output bytes')
    transport=save(directory/'raw-storage.json',{'immutable':'transport proof'})
    native_hash=archive.native_tar_hash(run['task']/'baseline-source.tar')
    build=save(run['task']/'build/build_manifest.json',{'roles':{r:{'source_dir':str(run['task']/'baseline'),
        'source_sha256':native_hash} for r in 'AB'}})
    request={'role_build':str(build)}
    template={'comparison_kind':'aa','case_ids':[1],'schedule':[{'request':request} for _ in range(6)]}
    plan={'version':'level2_local_raw_method_qualification_v1','control_type':'method',
        'source_hash':run['baseline'],'case_ids':[1],'declared_native_processes':1,'calibration_eligible':False,
        'selected_schedule_index':0,'cohort_template':template,'request':request}
    save(root/'request.json',request);save(root/'stage-plan.json',plan)
    observation={'operator':'exp','source_hashes':dict.fromkeys('AB',native_hash),
        'artifacts':{str(p):archive.sha(p) for p in (raw,output,transport)},'bound_artifacts':{}}
    if passed:
        save(root/'observation.json',observation)
        save(root/'method-qualification.json',{'version':plan['version'],'status':'passed','native_processes':1,
            'case_ids':[1],'calibration_eligible':False,'six_process_cohort_report_emitted':False,
            'request':{'path':str(root/'request.json'),'sha256':archive.sha(root/'request.json')},
            'observation':{'path':str(root/'observation.json'),'sha256':archive.sha(root/'observation.json')}})
    result=save(root/'result.json',{'stage_id':'baseline-raw-local-method-01','candidate_id':None,
        'kind':'control','control_type':'method','calibration_eligible':False,
        'status':'passed' if passed else 'failed',**archive.POLICY})
    run['state']['stages']={'baseline-raw-local-method-01':{'kind':'control','candidate_id':None,'plan':plan,
        'attempts':[{'outcome':'success' if passed else 'failed',
            'evidence':{'result':{'path':str(result),'sha256':archive.sha(result)}}}]}}
    monkeypatch.setattr(archive.analysis,'validate_plan',lambda p:p)
    verifier=Mock(return_value=observation)
    monkeypatch.setattr(archive.analysis,'verify_observation',verifier)
    return root,(raw,output,transport),verifier


def test_local_method_archives_full_raw_outputs_and_replays_one_observation_only(run,monkeypatch):
    root,files,verifier=local_method_fixture(run,monkeypatch)
    prepared=archive.Archive(run['root'],'train').prepare()
    verifier.assert_called_once_with(root/'evidence',expected_request=archive.load(root/'request.json'))
    assert {str(p) for p in files}<={row['path'] for row in prepared['artifact_index']}
    assert prepared['attempts']==[]
    method=prepared['task_checkpoints'][0]['methods'][0]
    projection=archive.load(method['single_process_qualification']['path'])
    assert projection['native_process_count']==1 and projection['calibration_eligible'] is False
    assert 'observations' not in method  # No six-process cohort summary is fabricated.


def test_local_method_failed_capture_keeps_partial_bytes_without_replay_or_calibration(run,monkeypatch):
    root,files,verifier=local_method_fixture(run,monkeypatch,passed=False)
    prepared=archive.Archive(run['root'],'train').prepare()
    verifier.assert_not_called()
    assert {str(p) for p in files}<={row['path'] for row in prepared['artifact_index']}
    method=prepared['task_checkpoints'][0]['methods'][0]
    assert method['status']=='failed' and method['single_process_qualification'] is None


def test_method_raw_mutation_cannot_be_blessed_by_new_archive_file_inventory(run,monkeypatch):
    root,files,verifier=local_method_fixture(run,monkeypatch)
    files[0].write_bytes(b'changed raw file')
    with pytest.raises(ValueError,match='evidence hash differs'):
        archive.Archive(run['root'],'train').prepare()

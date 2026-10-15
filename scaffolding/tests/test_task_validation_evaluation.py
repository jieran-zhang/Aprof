"""CPU evaluator wiring; explicit leaf doubles confer no baseline or hardware qualification."""
import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

import evaluate_skill_release as evaluator
import task_validation_trial as trial
from aprof_runtime.errors import ContractError
from aprof_runtime.jsonio import content_hash, to_primitive
from aprof_runtime.local_evidence import LocalEvidence
from eval_tool_broker import BUDGET_POLICY, CONFIG, inventory
from feedback_attempt_verify import expected_patch
from test_task_baseline_build import Clock


@pytest.fixture
def evaluation(tmp_path, monkeypatch):
    clock = Clock()
    for module in (trial, trial.bridge): monkeypatch.setattr(module, 'time', clock)
    output = tmp_path / 'evaluation'; directory = output / 'runs/cpu'
    work = directory / 'worker/root/work'; work.mkdir(parents=True)
    local_parent = tmp_path / 'task-scratch'; local_parent.mkdir()
    root = local_parent / 'local-task'
    def task_directory(**kwargs):
        assert kwargs == dict(prefix='aprof-task-validation-', dir=str(local_parent))
        root.mkdir(); return str(root)
    monkeypatch.setattr(trial.tempfile, 'mkdtemp', task_directory)
    baseline = LocalEvidence(tmp_path / 'baseline-records')
    def save(path, value):
        path.write_text(json.dumps(value)); return {'path': str(path), 'sha256': trial.file_hash(path)}
    def indexed(name, value):
        pointer = save(tmp_path / name, value); baseline.register_artifact(pointer['path']); return pointer
    row = dict(operator='gelu', arm='skill-only', seed=1, run_id='cpu')
    model = dict(name='CPU model boundary', reasoning_effort='none')
    original = indexed('baseline-plan.json', {'operator': 'gelu'})
    qualification = indexed('qualification.json', {'plan_ref': original['sha256'], 'CPU': 'not a qualification'})
    derivation = indexed('derivation.json', {'plan_ref': original['sha256']})
    graph, _ = trial.load_snapshot(trial.bridge.RELEASE / 'skillgraph/versions/v0002/graph.json')
    graph = copy.deepcopy(graph)
    transformation = next(t for t in graph['transformations'] if t['id'] == 'transformation.narrow_sync_scope')
    transformation['version'] = '9.8.7-cpu'  # Version must come from these graph bytes.
    graph_pointer = indexed('graph.json', graph)
    registry = indexed('registry.json', {'graph': graph_pointer, 'derivation_ref': derivation['sha256']})
    route_value = dict(graph_version='v0002', policy_version='expert-prior', selected_edge_id='CPU edge',
        behavior_probability=1.0, selection_mode='argmax', selection_seed=None,
        selected_mechanism_id='mechanism.cpu', mechanism_derivation='fixed_supports_refutes_tri_state_v1',
        mechanism_scores={'mechanism.cpu': 1.0}, candidates=[dict(edge_id='CPU edge', source_id='mechanism.cpu',
            target_id=transformation['id'], logit=0.0, probability=1.0, allowed=True, mask_reasons=[])])
    route = save(work / 'route_receipt.json', dict(registry_ref=registry, graph_hash=content_hash(graph), route=route_value))
    files = {'baseline': {'kernel.asc': b'old\n', 'removed.h': b'removed\n'},
             'candidate': {'kernel.asc': b'new\n', 'added.h': b'added\n'}}
    for role, sources in files.items():
        (work / role).mkdir()
        for name, data in sources.items(): (work / role / name).write_bytes(data)
    submitted = dict(actual_parent='original baseline', intent='CPU wiring only', route_receipt_ref=route,
        transformation_id=transformation['id'], parameters={})
    submitted_pointer = save(work / 'candidate_plan.json', submitted)
    (work / 'prompt.txt').write_text('CPU proposer prompt')
    worker_qualification = indexed('worker-qualification.json', {'CPU': 'provider boundary'})
    worker = dict(status='completed', role='proposer', model=model['name'], reasoning_effort=model['reasoning_effort'],
        qualification_ref=worker_qualification, config=CONFIG, worker_builds=0, budget_policy=BUDGET_POLICY,
        usage={'totalTokens': 1}, submission={'plan': submitted_pointer, 'source_inventory': inventory(work / 'candidate')},
        events_ref=save(tmp_path / 'events.json', {}), broker_ref=save(tmp_path / 'broker.json', {}))
    save(directory / 'worker/worker.json', worker)
    save(work / 'candidate_review.json', {'CPU': 'independent review boundary'})
    submission_work = work
    work = directory / 'controller-workspace'
    shutil.copytree(submission_work, work)
    index = baseline.write_index(tmp_path / 'baseline-index.json')
    budget_plan = save(tmp_path / 'budget.json', {'equal_budget_evaluation': {'budget_seconds': 7200}})
    task = dict(evaluation_plan=original, baseline_qualification=qualification,
        baseline_local_index={'path': str(index), 'sha256': trial.file_hash(index)},
        context_derivation_ref=derivation['sha256'], route_registry=registry)
    manifest = dict(plan=budget_plan, model=model, worker_qualification=worker_qualification,
        libraries={'candidate': {'path': str(trial.bridge.RELEASE)}},
        evaluator={'physical_device': 0, 'task_local_root': str(local_parent)}, tasks={'gelu': task})
    freeze = save(output / 'freeze.json', manifest)
    matrix = save(output / 'matrix.json', {'freeze_sha256': freeze['sha256'], 'runs': [row]})
    job = save(directory / 'job.json', evaluator._trial_job(output, row, manifest))
    origin = save(directory / 'dispatcher-plan.json', dict(schema_version=1, kind='skill_release_trial_plan',
        run_id='cpu', row=row, freeze_ref=freeze, matrix_ref=matrix, job_ref=job, budget_seconds=7200))
    attempt = save(directory / 'attempt.json', dict(plan_ref=origin, budget_seconds=7200, created_at=clock.time()))
    launch = dict(attempt_ref=attempt, started_at=clock.time(), started_monotonic=clock.monotonic(),
        deadline_monotonic=clock.monotonic()+7200, issued_monotonic=clock.monotonic(), child_timeout_seconds=7200)
    launch_pointer = save(directory / 'dispatcher-launch.json', launch)
    calls = []; fault = {}
    def stage(name):
        calls.append(name)
        if fault.get('stage') == name: raise ValueError('CPU '+name+' failure')
    def review(local, *args, **kw):
        stage('review'); local.register_artifact(route['path'])
    monkeypatch.setattr(trial.candidate, 'register_candidate_evidence', review)
    monkeypatch.setattr(trial.candidate, 'prepare_candidate_assembly', lambda *a, **kw: stage('assembly'))
    def plan(local, **kw):
        stage('plan'); assert kw['deadline'] == launch['deadline_monotonic']
        roles = {role: {'files': {name: local.register_artifact(work / role / name) for name in sources}}
            for role, sources in files.items()}
        return local.register_json(dict(**kw['identity'], route=route, roles=roles,
            source_hashes={role: local.register_json({'schema_version': '1.0.0', 'files': value['files']})
                for role, value in roles.items()}))
    monkeypatch.setattr(trial.candidate, 'prepare_candidate_plan', plan)
    def planning(local, **kw):
        stage('planning'); return dict(execution_context_ref=local.register_json({'CPU': 'planning boundary'}), selections=[])
    monkeypatch.setattr(trial, 'materialize_submitted_planning', planning)
    def prepare(local, **kw):
        stage('prepare'); return local.register_json({'CPU': 'trial boundary', 'draft_ref': kw['draft_ref']})
    monkeypatch.setattr(trial, 'prepare_trial', prepare)
    def run(local, **kw):
        stage('run')
        return dict(status='completed', result_ref=local.register_json({'CPU': 'hardware boundary', 'error': None}))
    monkeypatch.setattr(trial, 'run_trial', run)
    def replay(local, **kw):
        stage('replay')
        if fault.get('expire'): clock.elapsed = 7201
        return dict(valid=True, verdict='measurement_unknown', admission_authority=False)
    monkeypatch.setattr(trial, 'replay_trial', replay)
    def execute():
        return trial.execute_evaluation(manifest, row, work, directory / 'evaluation.json',
            launch_path=launch_pointer['path'], launch_sha256=launch_pointer['sha256'])
    return SimpleNamespace(**locals())


def test_entry_binds_real_draft_diff_graph_version_and_original_deadline(evaluation):
    f = evaluation; receipt = f.execute()
    assert receipt['status'] == 'completed', receipt['error']
    assert f.calls == ['review', 'assembly', 'plan', 'planning', 'prepare', 'run', 'replay']
    assert receipt['deadline_monotonic'] == f.launch['deadline_monotonic']
    assert receipt['measurement_protocol'] == trial.bridge.timing.PROTOCOL
    local = LocalEvidence.from_index(receipt['local_index']['path'])
    draft = trial.CandidateDraft.from_dict(trial._read(local, receipt['draft_ref']['sha256']))
    assert draft.transformation_version == '9.8.7-cpu' and draft.parent_candidate_id is None
    assert to_primitive(draft.route) == f.route_value
    assert local.verify_artifact(draft.patch_artifact_hash).read_bytes() == expected_patch(f.files['baseline'], f.files['candidate'])
    assert trial._read(local, draft.producer_hashes.model)['model'] == f.model
    assert local.verify_artifact(f.original['sha256']) == Path(f.original['path'])
    assert local.directory != f.baseline.directory
    assert not receipt['archive_performed'] and not receipt['eligible_for_publication']
    assert 'cases' not in receipt and 'formal_outcome' not in receipt
    assert not list(f.root.rglob('*.sqlite')) and not list(f.root.rglob('*.objects'))
    with pytest.raises(ValueError, match='output/workspace'): f.execute()


@pytest.mark.parametrize('stage', ['review', 'assembly', 'planning', 'run', 'replay'])
def test_entry_retains_failure_index_and_stops(evaluation, stage):
    f = evaluation; f.fault['stage'] = stage
    receipt = f.execute()
    assert receipt['status'] == 'failed' and receipt['error']['message'] == 'CPU '+stage+' failure'
    assert f.calls[-1] == stage and Path(receipt['local_index']['path']).is_file()
    assert Path(f.directory / 'evaluation-started.json').is_file()


@pytest.mark.parametrize('change', ['deadline', 'expired', 'manifest', 'submission', 'late_replay',
                                  'copy_source', 'copy_plan', 'copy_review'])
def test_entry_rejects_parent_submission_and_budget_changes(evaluation, change):
    f = evaluation
    if change == 'deadline':
        f.launch['deadline_monotonic'] += 1
        f.launch_pointer.update(f.save(Path(f.launch_pointer['path']), f.launch))
    elif change == 'expired': f.clock.elapsed = 7201
    elif change == 'manifest': f.manifest['model']['name'] = 'substituted'
    elif change == 'submission':
        f.worker['submission']['source_inventory'] = {}
        f.save(f.directory / 'worker/worker.json', f.worker)
    elif change.startswith('copy_'):
        path = {'copy_source': f.work / 'candidate/kernel.asc', 'copy_plan': f.work / 'candidate_plan.json',
                'copy_review': f.work / 'candidate_review.json'}[change]
        path.write_text(path.read_text() + ' ')
    else: f.fault['expire'] = True
    receipt = f.execute()
    assert receipt['status'] == 'failed' and receipt['error'] is not None
    if change in {'deadline', 'expired', 'manifest'} or change.startswith('copy_'): assert not f.calls
    if change == 'submission': assert f.calls == ['review', 'assembly', 'plan']
    if change == 'late_replay': assert receipt['error']['type'] == 'TimeoutError'


def test_runtime_episode_rejects_rehashed_outcome_change():
    from test_store_integrity import _noop_episode
    episode = _noop_episode('sha256:' + '1'*64)
    value = to_primitive(episode)
    value['outcome']['speedup'] = 12345.0
    value['episode_hash'] = content_hash({k: v for k, v in value.items() if k != 'episode_hash'})
    with pytest.raises(ContractError, match='outcome'):
        trial.CandidateEpisode.from_dict(value)


@pytest.mark.parametrize('defect', ['missing_directory', 'remote_mount'])
def test_entry_requires_frozen_existing_local_scratch(evaluation, monkeypatch, defect):
    f = evaluation
    if defect == 'missing_directory': f.local_parent.rmdir()
    else:
        monkeypatch.setattr(trial.bridge.timing.old, 'select_mount', lambda *args: {'filesystem_type': 'nfs'})
    with pytest.raises(ValueError): f.execute()
    assert not f.calls and not f.root.exists()

"""Orchestration CPU boundaries only; doubles never establish qualification/routes.

Real source/build/Task/PMU validators have separate focused suites. Here explicit
leaf doubles exercise ordering, immutable partials and deadline propagation.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import task_validation_trial as trial
from aprof_runtime.local_evidence import LocalEvidence
from test_task_baseline_build import Clock
from test_task_baseline_context import fixture as context_fixture


@pytest.fixture
def wiring(tmp_path, monkeypatch):
    local = LocalEvidence(tmp_path/'records'); root = tmp_path/'trial'; root.mkdir()
    clock = Clock(); calls = []; faults = {}
    for module in (trial, trial.bridge): monkeypatch.setattr(module, 'time', clock)
    ref = local.register_json
    plan = dict(candidate_id='CPU', session_id='CPU', run_id='CPU', operator='gelu',
        source_hashes={'baseline':ref({'CPU':'baseline'}),'candidate':ref({'CPU':'candidate'})},
        launch_ref=ref({'CPU':'original supervisor boundary'}), deadline_monotonic=clock.monotonic()+3600,
        assembly_dir=str(tmp_path/'assembly'), workspace=str(tmp_path/'workspace'),
        model={'name':'CPU double','reasoning_effort':'none'}, baseline_qualification={'CPU':'not a qualification'})
    binding = dict(candidate_plan_ref=ref(plan), directory=str(root), selections=['CPU only'])
    trial_ref = ref(binding); config = {'CPU':'full Task boundary'}; context = {}; draft = {}; graph = {}
    monkeypatch.setattr(trial, '_checked_trial', lambda *args:(binding, plan, context, draft, graph))
    def stage(name):
        calls.append(name); clock.elapsed += .1
        if faults.get('fail') == name: raise ValueError('CPU '+name+' failure')
        if faults.get('expire') == name: clock.elapsed = 3601
    def record(name):
        start=clock.time(); stage(name)
        return dict(started_at=start, finished_at=clock.time(), started_monotonic=clock.monotonic()-.1,
                    finished_monotonic=clock.monotonic(),deadline_monotonic=plan['deadline_monotonic'])
    def build(*args, **kwargs):
        assert args[2].deadline == plan['deadline_monotonic']
        value={**record('build'), 'artifacts':{'build_log':ref({'CPU':'build'})}}
        return {'build_receipt_ref':ref(value)}
    monkeypatch.setattr(trial.candidate, 'reviewed_build_once', build)
    def pmu_plan(*args, **kwargs):
        stage('pmu_plan'); return ref({'CPU':'predeclared complete PMU'})
    monkeypatch.setattr(trial.pmu, 'prepare_candidate_pmu_plan', pmu_plan)
    monkeypatch.setattr(trial.candidate, 'collect_candidate_correctness', lambda *a,**kw:ref(record('correctness')))
    monkeypatch.setattr(trial.candidate, 'verify_candidate_correctness', lambda *a,**kw:{'valid':True})
    def task(*args, **kwargs):
        assert kwargs['deadline'] == plan['deadline_monotonic']
        window=record('task_measurement'); report=ref({'CPU':'not timing evidence','gate_projection':{}})
        proof=dict(config_ref=ref(config), raw_ref=ref({'CPU':'raw boundary'}), registration_ref=ref({'CPU':'registration'}),
                   measurement_report_ref=report)
        proof_ref=ref(proof); completion=ref({**window,'proof_ref':proof_ref,'measurement_report_ref':report})
        return {'artifacts':dict(measurement_admission=completion,measurement_proof=proof_ref,measurement_report=report,
            timing_config=proof['config_ref'],timing_raw=proof['raw_ref'],measurement_registration=proof['registration_ref'])}
    monkeypatch.setattr(trial.candidate, 'collect_candidate_task', task)
    def profile(local, **kwargs):
        assert kwargs['deadline'] == plan['deadline_monotonic']
        capture=ref(record('profile')); report=ref({'capture_report_ref':capture})
        result=trial._read(local,kwargs['completion_ref'])
        build_ref=next(trial._read(local,x)['artifacts']['build_log'] for x in local._paths
                       if trial._read(local,x).get('artifacts',{}).get('build_log'))
        # Use the wrapper, not the nested native build ref.
        wrapper=next(x for x in local._paths if trial._read(local,x).get('artifacts',{}).get('build_log')==build_ref)
        return {'replay':{'valid':True,'alignment':None}, 'artifacts':dict(mechanism_report=report,
            mechanism_plan=kwargs['plan_ref'],measurement_admission=kwargs['completion_ref'],
            measurement_report=result['measurement_report_ref'],task_launch=plan['launch_ref'],build_window=wrapper)}
    monkeypatch.setattr(trial.pmu,'collect_candidate_pmu',profile)
    request={'CPU':'gate input boundary, not a route or acceptance'}
    monkeypatch.setattr(trial,'_request',lambda *args:request)
    def finalize(context, requested, graph, local, *, deadline):
        assert deadline == plan['deadline_monotonic'] and requested == request
        stage('online_admission')
        return dict(episodes=[{'CPU':'finalizer boundary, no authority'}],archive_performed=False,store_sequences=[])
    monkeypatch.setattr(trial.candidate,'finalize_local',finalize)
    return SimpleNamespace(**locals())


def test_four_phases_once_share_original_deadline_and_remain_local(wiring):
    f=wiring; answer=trial.run_trial(f.local,trial_ref=f.trial_ref)
    result=trial._read(f.local,answer['result_ref'])
    assert f.calls == ['build','pmu_plan',*trial.PHASES]
    assert result['status']=='completed' and len(result['stages'])==4 and result['active_stage'] is None
    assert [trial._read(f.local,r)['name'] for r in result['stages']]==list(trial.PHASES)
    assert not answer['admission_authority'] and not answer['eligible_for_publication']
    assert not list(f.tmp_path.rglob('*.sqlite')) and not list(f.tmp_path.rglob('*.objects'))
    assert isinstance(f.local,LocalEvidence)
    with pytest.raises(FileExistsError):trial.run_trial(f.local,trial_ref=f.trial_ref)


@pytest.mark.parametrize('phase',trial.PHASES)
def test_fail_stop_preserves_partial_without_fake_completed_event(wiring,phase):
    f=wiring; f.faults['fail']=phase
    answer=trial.run_trial(f.local,trial_ref=f.trial_ref); result=trial._read(f.local,answer['result_ref'])
    assert result['status']=='failed' and result['error']['type']=='ValueError'
    assert result['active_stage']['name']==phase and len(result['stages'])==trial.PHASES.index(phase)
    assert not (f.root/(phase+'-completed.json')).exists()
    assert f.calls[-1]==phase and Path(answer['local_index']).is_file()
    with pytest.raises(ValueError,match='failed or incomplete'):
        trial.replay_trial(f.local,trial_ref=f.trial_ref,result_ref=answer['result_ref'])


def test_late_gate_does_not_complete_online_phase(wiring):
    f=wiring; f.faults['expire']='online_admission'
    answer=trial.run_trial(f.local,trial_ref=f.trial_ref); result=trial._read(f.local,answer['result_ref'])
    assert result['status']=='failed' and result['error']['type']=='TimeoutError'
    assert len(result['stages'])==3 and not (f.root/'online_admission-completed.json').exists()


def test_expired_trial_rejects_before_any_stage(wiring):
    f=wiring; f.clock.elapsed=3601
    with pytest.raises(TimeoutError):trial.run_trial(f.local,trial_ref=f.trial_ref)
    assert not f.calls and not (f.root/'started.json').exists()


@pytest.mark.parametrize('mutation',['reorder','omit','deadline'])
def test_replay_rejects_changed_stage_roster_or_deadline_before_raw_read(wiring,monkeypatch,mutation):
    f=wiring; answer=trial.run_trial(f.local,trial_ref=f.trial_ref)
    result=trial._read(f.local,answer['result_ref'])
    if mutation=='reorder':result['stages'].reverse()
    elif mutation=='omit':result['stages'].pop()
    else:result['deadline_monotonic']+=3600
    path=f.root/'result.json'; path.write_text(json.dumps(result)); changed=f.local.register_artifact(path)
    monkeypatch.setattr(trial.candidate,'checked_candidate_build',lambda *a,**kw:(None,trial._read(f.local,result['build_receipt_ref'])))
    with pytest.raises(ValueError):trial.replay_trial(f.local,trial_ref=f.trial_ref,result_ref=changed)


@pytest.mark.parametrize('mutation',['architecture','predicate','metadata','budget'])
def test_execution_context_cannot_invent_qualified_facts(tmp_path,mutation):
    local=LocalEvidence(tmp_path/'records')
    baseline=dict(schema_version='1.0.0',task_id='CPU',operator='gelu',hardware_fingerprint='CPU unknown',
        workload={'source_hash':'CPU original','metadata':{'shape':[1]}},budget={'candidate_limit':1},
        evidence={'architecture_profile':{'CPU':'no qualification'},'predicate_states':{'CPU':'unknown'}})
    changed=copy.deepcopy(baseline)
    if mutation=='architecture':changed['evidence']['architecture_profile']={'CPU':'invented'}
    elif mutation=='predicate':changed['evidence']['predicate_states']['CPU']='true'
    elif mutation=='metadata':changed['workload']['metadata']['shape']=[2]
    else:changed['budget']['candidate_limit']=2
    with pytest.raises(ValueError,match='qualified'):
        trial._execution_context(local,baseline,changed,None)


def test_real_candidate_preflight_rejects_unqualified_plan(tmp_path):
    local=LocalEvidence(tmp_path/'records')
    with pytest.raises(ValueError,match='candidate plan protocol'):
        trial.candidate._checked_candidate_plan(local,local.register_json({'status':'passed'}))
    assert trial.ENABLED_IN_1_0 is False


@pytest.fixture
def submitted_planning(context_fixture, monkeypatch):
    # The qualification/device boundary is explicitly doubled by context_fixture;
    # all 20 metadata/planning checks and original graph attestations below run.
    import task_baseline_context as contexts
    f=context_fixture; local=f['local']
    registry_ref=contexts.build_baseline_contexts(local,derivation_ref=f['derivation_ref'],
        qualification_ref=f['qualification_ref'],destination=f['tmp_path']/'contexts')
    trusted=contexts.replay_baseline_contexts(local,derivation_ref=f['derivation_ref'],
        qualification_ref=f['qualification_ref'],registry_ref=registry_ref)
    graph,_=trial.load_snapshot(contexts.GRAPH)
    work=f['tmp_path']/'work';work.mkdir()
    parallel=copy.deepcopy(f['parallel']);dispatch=copy.deepcopy(f['dispatch'])
    for value in (parallel,dispatch):
        for key in ('schema_version','operator','source_hash','architecture_profile_ref','parallel_plan_ref'):
            value.pop(key,None)
    submitted=dict(parallel_plan=parallel,dispatch_plan=dispatch,
        mechanism=dict(case_id=1,kernel='group_norm_kernel',metric='aic',expected_direction='decrease'))
    path=work/'candidate_plan.json'
    plan={**f['plan'],'workspace':str(work),'deadline_monotonic':trial.time.monotonic()+f['plan']['budget_seconds'],
          'profile':{**f['plan']['profile'],'kernels':['group_norm_kernel']},
          'source_hashes':{**f['plan']['source_hashes'],'candidate':local.register_json({'CPU':'changed source'})}}
    route=dict(context_id='group_norm-case-1',route=trusted['routes']['group_norm-case-1'])
    draft=trial.CandidateDraft.from_dict(dict(schema_version='1.0.0',candidate_id='CPU',session_id='CPU',
        route=route['route'],transformation_id='transformation.narrow_sync_scope',transformation_version='1.0.0',
        producer_hashes=dict(model='unknown',prompt='unknown',agent='unknown'),source_hashes=plan['source_hashes'],
        patch_artifact_hash=local.register_json({'CPU':'patch boundary'}),parameters={},proposed_by='CPU fixture',
        created_at='2020-01-01T00:00:00Z'))
    def review():
        path.write_text(json.dumps(submitted))
        plan_ref=local.register_artifact(path)
        ref=local.register_json({'CPU':'review boundary only','plan_sha256':plan_ref})
        plan['independent_review']={'path':str(local.verify_artifact(ref)),'sha256':ref}
    review()
    kwargs=dict(candidate_plan_ref='CPU boundary',draft_ref='CPU boundary',registry_ref=registry_ref,
                derivation_ref=f['derivation_ref'])
    monkeypatch.setattr(trial,'_inputs',lambda *a,**kw:(plan,route,trusted,draft,graph))
    return SimpleNamespace(**locals())


def test_same_submission_materializes_real_planning_without_new_file_tools(submitted_planning):
    f=submitted_planning; original=f.path.read_bytes()
    result=trial.materialize_submitted_planning(f.local,**f.kwargs)
    context=trial._read(f.local,result['execution_context_ref'])
    assert f.path.read_bytes()==original and result['submitted_plan_ref']==trial.file_hash(f.path)
    assert result['checked_case_ids']==list(range(1,21))
    assert result['selections']==[dict(name='aic',kernel='group_norm_kernel',unit='us',expected_direction='decrease')]
    assert context['budget']['wall_time_limit_seconds']==f.plan['budget_seconds']
    assert context['workload']['implementation_source_hash']==f.plan['source_hashes']['candidate']
    assert context['evidence']['predicate_states']==f.trusted['contexts'][f.route['context_id']]['evidence']['predicate_states']
    trial._execution_context(f.local,f.trusted['contexts'][f.route['context_id']],context,f.draft)
    assert trial._read(f.local,result['parallel_plan_ref'])['groups']==f.submitted['parallel_plan']['groups']


@pytest.mark.parametrize('defect',['missing','source','architecture','capacity','predicate','evidence',
                                  'case20','review_hash','route','pmu_case','pmu_metric'])
def test_submitted_planning_cannot_fill_facts_or_unlock_routes(submitted_planning,defect):
    from aprof_runtime.errors import ContractError, StoreError
    f=submitted_planning
    if defect=='missing':f.submitted.pop('parallel_plan')
    elif defect=='source':f.submitted['dispatch_plan']['source_hash']=f.plan['source_hashes']['baseline']
    elif defect=='architecture':f.submitted['parallel_plan']['architecture_profile_ref']=f.plan['source_hashes']['candidate']
    elif defect=='capacity':f.submitted['parallel_plan']['groups'][0]['memory_requirements']['UB']=10**12
    elif defect=='predicate':f.submitted['parallel_plan']['predicate_states']={'CPU':'true'}
    elif defect=='evidence':f.submitted['parallel_plan']['groups'][0]['selection_evidence']=['sha256:'+'0'*64]
    elif defect=='case20':f.plan['cases']=copy.deepcopy(f.plan['cases']);f.plan['cases'][-1]['metadata_ref']=f.plan['source_hashes']['candidate']
    elif defect=='route':f.trusted['routes']['group_norm-case-20']['behavior_probability']=0.5
    elif defect=='pmu_case':f.submitted['mechanism']['case_id']=2
    elif defect=='pmu_metric':f.submitted['mechanism']['metric']='unfrozen'
    if defect=='review_hash':
        f.submitted['parallel_plan']['plan_id']='changed after review'
        f.path.write_text(json.dumps(f.submitted))
    else:f.review()
    before=f.local._sequence
    with pytest.raises((ValueError,ContractError,StoreError)):
        trial.materialize_submitted_planning(f.local,**f.kwargs)
    assert f.local._sequence==before

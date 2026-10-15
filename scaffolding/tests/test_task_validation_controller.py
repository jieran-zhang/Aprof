"""CPU primitive joins only; no provider, CANN, hardware or baseline admission."""
import json
from pathlib import Path
import sys
import time

import pytest

import task_validation_controller as validation
from aprof_runtime.errors import ContractError

bridge = validation.bridge


def config(tmp_path, operator='dynamic_quant'):
    workload = ({'query_shape':[1,2,2,16], 'key_shape':[1,2,1,16], 'dtype':'float16'}
                if operator=='gqa' else {'dtype':['float16']} if operator=='weight_quant_batch_matmul' else {})
    scope=validation.baseline.case_scope(operator,workload)
    roles = {}
    for role in bridge.ROLES:
        directory = tmp_path / role
        directory.mkdir()
        (directory / 'kernel.asc').write_text('// CPU fixture source\n')
        roles[role] = dict(source_dir=str(directory),
            launches_per_operator={str(i): scope['launches_per_call'][role] for i in range(1, 21)})
    keys = ['output_y', 'output_scale'] if operator == 'dynamic_quant' else ['output']
    binary = str(tmp_path / 'binary')
    value = dict(operator=operator, run_id='cpu', session_id='cpu-candidate', candidate_id='cpu-candidate',
        expected_case_ids=list(range(1, 21)), roles=roles,
        build=dict(binary=binary, source_dir=str(tmp_path / 'assembly')),
        task_profile=dict(role_kernel_names={r: {str(i): scope['role_kernel_names'][r]
            for i in range(1, 21)} for r in bridge.ROLES}), cases=[])
    for cid in value['expected_case_ids']:
        outputs = {r: ['{cycle_dir}/' + r + '-' + key + '.bin' for key in keys] for r in bridge.ROLES}
        value['cases'].append(dict(case_id=cid, workload=workload, output_files=outputs, prepared_files=[str(tmp_path/'input.bin')],
            command=[binary, *[p for paths in outputs.values() for p in paths]],
            verify_commands={r: ['python', 'original_oracle.py', *outputs[r], '--result', '{cycle_dir}/'+r+'.json']
                             for r in bridge.ROLES}))
    return value


@pytest.mark.parametrize('operator', validation.OPERATORS)
def test_complete_correctness_plan_selects_every_role_and_output(tmp_path, operator):
    value = config(tmp_path, operator)
    destination = tmp_path/'correctness'
    rows = validation.correctness_calls(value, destination)
    assert [(r['case_id'], r['role']) for r in rows] == [(i, role) for i in range(1, 21) for role in bridge.ROLES]
    for row in rows:
        assert row['argv'][-2:] == ['--aprof-mechanism-role', row['role']]
        assert len(row['output_files']) == (2 if operator == 'dynamic_quant' else 1)
        assert set(row['output_files']).isdisjoint(row['inactive_output_files'])
        assert all(path in row['oracle_argv'] for path in row['output_files'])
        assert row['environment'] == {'APROF_SHARED_CYCLE': '0'}
    assert not destination.exists()  # A plan neither executes nor copies inputs.


@pytest.mark.parametrize('defect', ['missing_case', 'multi_kernel', 'wrong_kernel', 'missing_scale', 'escape', 'gqa', 'weight_quantized_matmul'])
def test_correctness_plan_rejects_partial_or_unregistered_scope(tmp_path, defect):
    value = config(tmp_path)
    if defect == 'missing_case': value['cases'].pop()
    elif defect == 'multi_kernel': value['roles']['candidate']['launches_per_operator']['1'] = 2
    elif defect == 'wrong_kernel': value['task_profile']['role_kernel_names']['candidate']['1'] = ['baseline_kernel']
    elif defect == 'missing_scale': value['cases'][0]['output_files']['candidate'].pop()
    elif defect == 'escape': value['cases'][0]['output_files']['candidate'][0] = '{cycle_dir}/../outside.bin'
    else: value['operator'] = defect
    with pytest.raises(ValueError):
        validation.correctness_calls(value, tmp_path/'correctness')


def candidate_setup(tmp_path, monkeypatch, operator='gelu'):
    from test_task_baseline_correctness import prepared, OracleCommands
    from test_task_baseline_build import write, Commands
    import eval_candidate_evidence
    # Match the real supervisor's PYTHONDONTWRITEBYTECODE=1 source freeze.
    monkeypatch.setattr(sys,'dont_write_bytecode',True)
    (tmp_path/'baseline').mkdir()
    local,original_ref,_,old_commands,clock=prepared(tmp_path/'baseline',monkeypatch,operator)
    monkeypatch.setattr(validation,'time',clock)
    monkeypatch.setattr(bridge,'time',clock)
    original=json.loads(local.verify_artifact(original_ref).read_text())
    def pointer(path):return {'path':str(path),'sha256':local.register_artifact(path)}
    def record(name,value):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value));return pointer(path)
    qualified={'valid':True,'status':'passed','qualification_passed':True,'plan_ref':original_ref,
        'attempt_ref':local.register_json({'CPU':'original baseline attempt'}),
        'result_ref':local.register_json({'CPU':'full qualification boundary explicitly mocked'})}
    qualification=record('qualified.json',qualified)
    qualification_calls=[]
    def replay(store,*,attempt_ref,result_ref):
        qualification_calls.append((attempt_ref,result_ref))
        assert (attempt_ref,result_ref)==(qualified['attempt_ref'],qualified['result_ref'])
        return dict(qualified)
    monkeypatch.setattr(validation,'verify_baseline_qualification',replay)
    workspace=tmp_path/'candidate-work';assembly=tmp_path/'candidate-assembly'
    for role in bridge.ROLES:
        files={name:local.verify_artifact(ref).read_bytes() for name,ref in original['roles'][role]['files'].items()}
        if role=='candidate':files['op_kernel/'+operator+'_kernel.asc']+=b'\n// CPU candidate edit; no device execution\n'
        write(workspace/role,files)
    model={'name':'CPU','reasoning_effort':'max'}
    review={'accepted':True,'source_review_ref':record('review.json',{'CPU':'model boundary mocked'}),
            'route_receipt_ref':record('route.json',{'CPU':'legal route boundary mocked'})}
    review_calls=[]
    def review_check(work,release,*,model,baseline_qualification):
        review_calls.append(str(work));assert Path(work)==workspace and release==bridge.RELEASE
        assert model=={'name':'CPU','reasoning_effort':'max'} and baseline_qualification==qualification
        return dict(review)
    monkeypatch.setattr(validation,'verify_candidate_evidence',review_check)
    monkeypatch.setattr(eval_candidate_evidence,'verify_candidate_evidence',review_check)
    monkeypatch.setattr(validation,'register_candidate_evidence',lambda store,*a,**kw:{
        'source_review':review['source_review_ref']['sha256'],'route_receipt':review['route_receipt_ref']['sha256']})
    validation.prepare_candidate_assembly(local,workspace=workspace,destination=assembly,
                                          baseline_qualification=qualification)
    identity={'run_id':'CPU-candidate','session_id':'CPU-candidate','candidate_id':'CPU-candidate'}
    row={'operator':operator,'run_id':identity['run_id'],'arm':'skill-only','seed':0}
    origin=record('dispatcher-plan.json',{'schema_version':1,'kind':'skill_release_trial_plan',
        'run_id':identity['run_id'],'row':row,'budget_seconds':3600,
        'freeze_ref':record('freeze.json',{'model':{**model,'cli_version':'CPU frozen CLI'},
            'plan':record('evaluation-plan.json',{'equal_budget_evaluation':{'budget_seconds':3600}}),
            'tasks':{operator:{'baseline_qualification':qualification}}}),
        'matrix_ref':record('matrix.json',{'runs':[row]}), 'job_ref':record('job.json',{'timeout_seconds':3600,
            'environment':{'APROF_SKILL_LIB':str(bridge.RELEASE),'ASCEND_RT_VISIBLE_DEVICES':'2',
                           'APROF_PHYSICAL_DEVICE':'2','APROF_LOGICAL_DEVICE':'0', **validation.builder.CPU_REFERENCE_ENV}})})
    attempt=record('attempt.json',{'plan_ref':origin,'created_at':clock.time(),'budget_seconds':3600})
    launch={'attempt_ref':attempt,'started_at':clock.time(),'started_monotonic':clock.monotonic(),
        'issued_monotonic':clock.monotonic(),'deadline_monotonic':clock.monotonic()+3600,'child_timeout_seconds':3600}
    launch_ref=record('launch.json',launch)['sha256']
    commands=OracleCommands(Commands(tmp_path/'candidate-commands',assembly,operator,clock))
    plan_ref=validation.prepare_candidate_plan(local,assembly=assembly,workspace=workspace,model=model,
        baseline_qualification=qualification,identity=identity,scratch_root=tmp_path/'candidate-scratch',
        deadline=commands.deadline,launch_ref=launch_ref)
    return locals()


def build_candidate(f):
    return validation.reviewed_build_once(f['assembly'],f['workspace'],f['commands'],f['local'],
        model=f['model'],baseline_qualification=f['qualification'],plan_ref=f['plan_ref'])


def test_real_freeze_model_projection_preserves_name_and_effort(tmp_path,monkeypatch):
    f=candidate_setup(tmp_path,monkeypatch)
    plan=json.loads(f['local'].verify_artifact(f['plan_ref']).read_text())
    assert plan['model']==f['model']
    for key in ('name','reasoning_effort'):
        with pytest.raises(ValueError,match='original task identity'):
            validation._launch(f['local'],f['launch_ref'],deadline=f['commands'].deadline,
                run_id=f['identity']['run_id'],operator=f['operator'],
                model={**f['model'],key:'changed'},qualification=f['qualification'],physical_device=2)


@pytest.mark.parametrize('operator',validation.OPERATORS)
def test_five_original_source_builds_complete_task_scopes_and_real_oracles(tmp_path,monkeypatch,operator):
    f=candidate_setup(tmp_path,monkeypatch,operator);local=f['local'];commands=f['commands']
    result=build_candidate(f)
    assert commands.calls==['configure','build'] and not result['archive_performed']
    config=validation.candidate_task_config(local,plan_ref=f['plan_ref'],build_receipt_ref=result['build_receipt_ref'])
    assert len(validation.correctness_calls(config,tmp_path/'pure-plan'))==40
    assert config['roles']['baseline']['launches_per_operator']==config['roles']['candidate']['launches_per_operator']
    if operator=='gqa':assert all(n>=5 for n in config['roles']['baseline']['launches_per_operator'].values())
    if operator=='weight_quant_batch_matmul':assert set(config['roles']['baseline']['launches_per_operator'].values())=={3}
    reference=validation.collect_candidate_correctness(local,plan_ref=f['plan_ref'],
        build_receipt_ref=result['build_receipt_ref'],commands=commands,destination=tmp_path/'candidate-correctness')
    replay=validation.verify_candidate_correctness(local,plan_ref=f['plan_ref'],
        build_receipt_ref=result['build_receipt_ref'],report_ref=reference)
    assert replay['valid'] and not replay['admission_authority']
    report=json.loads(local.verify_artifact(reference).read_text())
    assert report['kind']=='reviewed_candidate_correctness' and len(report['rows'])==40
    assert sum(len(row['executions']) for row in report['rows'])==80
    assert report['source_hashes']['baseline']!=report['source_hashes']['candidate']
    assert report['deadline_monotonic']==f['launch']['deadline_monotonic']
    with pytest.raises(FileExistsError):build_candidate(f)
    assert commands.calls.count('build')==1
    assert not list(tmp_path.rglob('*.sqlite')) and not list(tmp_path.rglob('*.objects'))


@pytest.mark.parametrize('defect',['review','route','source','oracle','deadline','launch','qualification'])
def test_candidate_authority_and_deadline_fail_before_build(tmp_path,monkeypatch,defect):
    f=candidate_setup(tmp_path,monkeypatch)
    if defect=='review':f['review']['accepted']=False
    elif defect=='route':f['review']['route_receipt_ref']=f['record']('other-route.json',{'CPU':'unbound'})
    elif defect=='source':(f['workspace']/'candidate/op_host/gelu.asc').write_text('changed host')
    elif defect=='oracle':(f['workspace']/'candidate/scripts/verify_result.py').write_text('changed oracle')
    elif defect=='deadline':f['commands'].deadline+=1
    elif defect=='launch':
        local=f['local'];plan=json.loads(local.verify_artifact(f['plan_ref']).read_text())
        launch=dict(f['launch'],deadline_monotonic=f['launch']['deadline_monotonic']+1,
                    child_timeout_seconds=f['launch']['child_timeout_seconds']+1)
        plan.update(launch_ref=local.register_json(launch),deadline_monotonic=launch['deadline_monotonic'])
        f['plan_ref']=local.register_json(plan);f['commands'].deadline+=1
    else:monkeypatch.setattr(validation,'verify_baseline_qualification',lambda *a,**kw:{'status':'passed'})
    with pytest.raises((ValueError,KeyError)):build_candidate(f)
    assert not f['commands'].calls and not (f['assembly']/'build-attempt.json').exists()


def test_baseline_wrapper_still_rejects_candidate_plan(tmp_path,monkeypatch):
    f=candidate_setup(tmp_path,monkeypatch);result=build_candidate(f)
    with pytest.raises(ValueError):
        validation.correctness.collect_baseline_correctness(f['local'],plan_ref=f['plan_ref'],
            build_receipt_ref=result['build_receipt_ref'],commands=f['commands'],destination=tmp_path/'invalid-baseline')
    assert f['commands'].calls==['configure','build']


def test_changed_correctness_stops_before_task_collection(tmp_path,monkeypatch):
    f=candidate_setup(tmp_path,monkeypatch);result=build_candidate(f)
    calls=[];monkeypatch.setattr(validation,'collect_task_artifacts',lambda *a,**kw:calls.append(True))
    with pytest.raises((ValueError,KeyError)):
        validation.collect_candidate_task(f['local'],plan_ref=f['plan_ref'],
            build_receipt_ref=result['build_receipt_ref'],correctness_ref=f['local'].register_json({'status':'passed'}),
            output=tmp_path/'task',deadline=f['commands'].deadline)
    assert calls==[]


@pytest.mark.parametrize('wrong_protocol', [False, True])
def test_task_completion_join_uses_real_local_merge_and_current_keys(tmp_path, monkeypatch, wrong_protocol):
    value = config(tmp_path)
    local = validation.LocalEvidence(tmp_path/'records')
    deadline=time.monotonic()+60
    def collect(supplied, output, *, timeout_seconds,deadline_monotonic,budget_binding,budget_reader):
        assert supplied == value and 0 < timeout_seconds <= 60
        assert deadline_monotonic==deadline and budget_binding is None and budget_reader is local
        output.mkdir()
        child = validation.LocalEvidence(output/'records')
        sources = {r: child.register_json(dict(schema_version='1.0.0',
            files=bridge.profile_capture.source_inventory(value['roles'][r]['source_dir']))) for r in bridge.ROLES}
        report = {'CPU':'schema fixture only; not measured evidence'}
        identity = {k: value[k] for k in ('operator', 'run_id', 'session_id', 'candidate_id')}
        identity.update(protocol=bridge.timing.PROTOCOL, source_hashes=sources,
                        measurement_report_ref=child.register_json(report))
        proof = dict(identity, config_ref=child.register_json(value), raw_ref=child.register_json({'CPU':'raw'}),
                     registration_ref=child.register_json({'CPU':'registration'}))
        completion = dict(identity, kind='local_measurement_completion', status='passed', error=None,
                          proof_ref=child.register_json(proof))
        if wrong_protocol: completion['protocol'] = 'shared_buffer_msprof_task_window_v4'
        return dict(status='passed', report=report, measurement_admission_ref=child.register_json(completion),
                    local_index=str(child.write_index(output/'local-index.json')))
    monkeypatch.setattr(bridge.timing, 'collect_local', collect)
    if wrong_protocol:
        with pytest.raises(ValueError, match='completion/proof'):
            validation.collect_task_artifacts(value, tmp_path/'measurement', local, deadline=deadline)
        assert (tmp_path/'measurement/local-index.json').is_file()
    else:
        result = validation.collect_task_artifacts(value, tmp_path/'measurement', local, deadline=deadline)
        assert result['admission_authority'] is False and result['archive_performed'] is False
        assert set(result['artifacts']) == {'measurement_admission', 'measurement_proof', 'measurement_report',
                                          'timing_config', 'timing_raw', 'measurement_registration'}
        for reference in result['artifacts'].values(): local.verify_artifact(reference)


def test_local_gate_keeps_runtime_validation_and_original_deadline(tmp_path):
    local = validation.LocalEvidence(tmp_path/'records')
    with pytest.raises(TimeoutError, match='deadline'):
        validation.finalize_local({}, {}, {}, local, deadline=time.monotonic()-1)
    with pytest.raises(ValueError, match='LocalEvidence'):
        validation.finalize_local({}, {}, {}, object(), deadline=time.monotonic()+10)
    with pytest.raises(ContractError):
        validation.finalize_local({}, {}, {}, local, deadline=time.monotonic()+10)
    assert not list(tmp_path.rglob('*.sqlite'))

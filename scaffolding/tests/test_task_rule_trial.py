"""CPU-only preparation and actual dispatcher; never invokes the hardware driver."""
import json
from pathlib import Path
import sys
import time

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'scaffolding/collection/scripts'
sys.path.insert(0, str(SCRIPTS))
import task_rule_trial as trial
from task_rule_admission import verify_task_attempt_roster
from timing_admission import read


CPU_CHILD = '''
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, SCRIPTS)
from task_rule_recorder import TaskRuleRecorder, LocalEvidence, STAGES
from timing_admission import read
p=argparse.ArgumentParser();p.add_argument('--anchor');p.add_argument('--local-index');a=p.parse_args()
local=LocalEvidence.from_index(a.local_index);anchor=read(local,local.register_artifact(a.anchor))
plan=read(local,anchor['controller_plan_ref']);root=Path(plan['directory']);launch=json.loads(Path(plan['launch_path']).read_text())
assert launch['anchor_ref']==local.register_artifact(a.anchor) and launch['job_ref']==anchor['job_ref']
assert 0 < launch['monotonic_deadline']-time.monotonic() <= 3600
ref=local.register_json({'CPU_fixture':True,'hardware':False})
post=dict(binary_hashes={r:ref for r in ('baseline','candidate')},oracle_files={'CPU-only':ref},
          task_config_ref=ref,profile_configs={r:ref for r in ('baseline','candidate')})
rec=TaskRuleRecorder(local,root/'admission',anchor_ref=launch['anchor_ref'],post_build=post,deadline=launch['monotonic_deadline'])
failed=anchor['operator']=='sigmoid'
for stage in STAGES:
    rec.start(stage)
    if failed and stage=='boundary':
        rec.fail_active(RuntimeError('actual CPU child failed'))
        break
    rec.complete(stage,[ref],report_ref=None if stage=='online_admission' else ref)
report=rec.partial_report() if failed else rec.finish()
result={'status':'failed' if failed else 'passed','child_report_ref':report,'measurement_expected':None,'anchor_ref':launch['anchor_ref'],
        'CPU_fixture':True,'archive_performed':False}
if root.name=='exp-mutated':
    producer=root.parent/'CPU-local_controller_bridge.py'
    producer.write_bytes(producer.read_bytes()+b'\\n# changed during actual CPU child\\n')
(root/'controller-result.json').write_text(json.dumps(result))
local.write_index(root/'controller-local-index.json')
raise SystemExit(7 if failed else 0)
'''


def dump(path, value):
    path.write_text(json.dumps(value))
    return path


def cpu_campaign(path):
    import aprof_runtime
    bindings={op:trial.screen.rule.frozen_binding(op) for op in ('exp','sigmoid')}
    return dump(path, dict(schema_version=1,kind='teacher_task_rule_campaign',protocol=trial.PROTOCOL,
        task_protocol=trial.TASK_PROTOCOL,runtime_build='aprof-runtime/'+aprof_runtime.__version__,model=trial.MODEL,
        budget_seconds=3600,budget_policy=trial.BUDGET_POLICY,reviewer_token_limit=None,
        max_attempts_per_operator=1,stop_on_failure=True,
        resampling='none',created_at=time.time(),prior_campaign_refs=[],attempts=[dict(operator=op,run_id='CPU-'+op,
            candidate_id='CPU-'+op+'-candidate',source_hashes={r:bindings[op]['roles'][r]['sha256'] for r in trial.screen.ROLES})
            for op in ('exp','sigmoid')],source_freezes=[bindings[op]['freeze'] for op in ('exp','sigmoid')],
        trace_index_sha256=trial.pointer(REPO.parent/'optimization-traces/index.json')['sha256'],
        split_index_sha256=trial.pointer(REPO/'scaffolding/benchmarks/cannbench/split_index.json')['sha256']))


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp('task-rule-trial-CPU')
    child = root/'cpu-controller.py'
    child.write_text('SCRIPTS='+repr(str(SCRIPTS))+'\n'+CPU_CHILD)
    review = {key:trial.pointer(dump(root/(key+'.json'), {'CPU_fixture':key})) for key in trial.REVIEW_KEYS}
    reviews = dump(root/'review-inputs.json', review)
    qualification = dump(root/'qualification.json', {'CPU_fixture':'no provider invoked'})
    campaign=cpu_campaign(root/'CPU-campaign.json')
    producer=root/'CPU-local_controller_bridge.py'
    producer.write_bytes((SCRIPTS/'local_controller_bridge.py').read_bytes())
    original_producers=trial.producer_paths
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(trial, 'CONTROLLER', child)
        patch.setattr(trial,'producer_paths',lambda:[*original_producers(),producer])
        # Qualification itself has dedicated integration tests; no provider in this suite.
        patch.setattr(trial, 'require_worker_build_budget_enforcement', lambda *a,**k:None)
        values = {}
        for label,operator in [('exp','exp'),('sigmoid','sigmoid'),('exp-mutated','exp')]:
            proposal = dump(root/(operator+'-candidate-plan.json'), {'actual_parent':'original baseline',
                'mechanism':dict(case_id=trial.CHOICES[operator][0], kernel=operator+'_kernel',
                                metric=trial.CHOICES[operator][1], expected_direction='decrease'),
                'intent':'CPU wiring only', 'source_anchors':[{'path':'op_kernel/'+operator+'_kernel.asc',
                'line':1,'why':'CPU fixture only'}]})
            output = root/label
            value = trial.prepare(output, operator=operator, run_id='CPU-'+operator,
                qualification=qualification, review_inputs=reviews, candidate_plan=proposal,campaign=campaign)
            values[label] = (output, value)
        yield values


@pytest.mark.parametrize('operator,count', [('exp',42),('sigmoid',57)])
def test_real_round_sources_inputs_boundaries_and_job_are_frozen(prepared, operator, count):
    output, result = prepared[operator]
    local = trial.LocalEvidence.from_index(output/'prepared-local-index.json')
    anchor = read(local, result['anchor_ref']); plan=read(local,anchor['controller_plan_ref'])
    inputs = read(local,anchor['input_inventory_ref']); boundary=read(local,anchor['boundary_plan_ref'])
    assert len(inputs)==2*(20+count) and len(boundary['cases'])==count
    assert len(anchor['history_refs'])>=20
    binding=trial.screen.rule.frozen_binding(operator)
    assert anchor['source_hashes']=={r:binding['roles'][r]['sha256'] for r in trial.screen.ROLES}
    assert trial.screen.source_identity(plan['assembly'])['historical_source_binding']==binding
    assert read(local,anchor['profile_plan_ref'])['choice']['case_id']==trial.CHOICES[operator][0]
    assert read(local,anchor['campaign_ref'])['attempts'][0]['operator']=='exp'
    frozen=read(local,plan['frozen_files_ref'])
    assert str(SCRIPTS/'local_controller_bridge.py') in frozen
    assert str(trial.bridge.RELEASE/'runtime/src/aprof_runtime/exploration.py') in frozen
    job=read(local,anchor['job_ref'])
    assert job['timeout_seconds']==3600 and 'physical_device' not in job
    assert {key:job['environment'][key] for key in ('ASCEND_RT_VISIBLE_DEVICES','APROF_PHYSICAL_DEVICE','APROF_LOGICAL_DEVICE')} == {
        'ASCEND_RT_VISIBLE_DEVICES':'0','APROF_PHYSICAL_DEVICE':'0','APROF_LOGICAL_DEVICE':'0'}
    assert not (output/'dispatcher-launch.json').exists() and not (output/'job').exists()
    assert not (output/'assembly/build').exists()
    for path in inputs: assert str(output) not in path  # Input bytes are referenced, never copied.


def test_preflight_rejects_wrong_anchor_and_changed_source_without_launch(prepared):
    output, result = prepared['exp']
    with pytest.raises(ValueError,match='trusted anchor'):
        trial.run(output,expected_anchor='sha256:'+'0'*64)
    path=output.parent/'CPU-local_controller_bridge.py'; original=path.read_bytes()
    try:
        path.write_bytes(original+b' ')
        with pytest.raises(ValueError,match='frozen trial file'):
            trial.run(output,expected_anchor=result['anchor_ref'])
        assert not (output/'dispatcher-launch.json').exists()
    finally:
        path.write_bytes(original)


def test_real_dispatcher_binds_actual_exit_without_rewriting_child(prepared):
    output, prepared_result=prepared['exp']
    result=trial.run(output,expected_anchor=prepared_result['anchor_ref'])
    assert result['status']=='completed_child' and result['admission_authority'] is False
    local=trial.LocalEvidence.from_index(output/'dispatcher-local-index.json')
    child=read(local,result['child_report_ref']); report=read(local,result['report_ref'])
    assert 'execution_ref' not in child and report['execution_ref']==result['execution_ref']
    assert read(local,result['execution_ref'])['exit_code']==0
    assert verify_task_attempt_roster(local,result['report_ref'],expected=result['expected'])['valid']
    with pytest.raises(ValueError,match='already attempted'):
        trial.run(output,expected_anchor=prepared_result['anchor_ref'])
    for reference in local._paths: local.verify_artifact(reference)


def test_actual_nonzero_child_retains_partial_without_completed_event(prepared):
    output, prepared_result=prepared['sigmoid']
    result=trial.run(output,expected_anchor=prepared_result['anchor_ref'])
    assert result['status']=='failed' and result['report_ref']
    local=trial.LocalEvidence.from_index(output/'dispatcher-local-index.json')
    assert read(local,result['execution_ref'])['exit_code']==7
    report=read(local,result['report_ref']);roster=read(local,report['attempt_roster_ref'])
    assert len(roster['events'])==3 and read(local,roster['events'][-1])['state']=='started'
    with pytest.raises(ValueError,match='did not exit successfully'):
        verify_task_attempt_roster(local,result['report_ref'],expected=result['expected'])
    with pytest.raises(ValueError,match='already attempted'):
        trial.run(output,expected_anchor=prepared_result['anchor_ref'])


def test_changed_producer_during_actual_child_never_completes(prepared):
    output, prepared_result=prepared['exp-mutated']
    path=output.parent/'CPU-local_controller_bridge.py';original=path.read_bytes()
    try:
        result=trial.run(output,expected_anchor=prepared_result['anchor_ref'])
        local=trial.LocalEvidence.from_index(output/'dispatcher-local-index.json')
        assert read(local,result['execution_ref'])['exit_code']==0
        assert result['status']=='failed' and result['report_ref']
        assert 'frozen trial file changed' in result['error']['message']
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize('fault',['duplicate_operator','unregistered_run','old_token_cap','wrong_budget_policy'])
def test_campaign_cannot_add_attempt_or_change_identity(prepared,fault):
    root=prepared['exp'][0].parent
    campaign=trial.load(root/'CPU-campaign.json')
    if fault=='duplicate_operator': campaign['attempts'][1]=campaign['attempts'][0]
    if fault=='old_token_cap': campaign['reviewer_token_limit']=8000
    if fault=='wrong_budget_policy': campaign['budget_policy']='historical_token_limited'
    path=dump(root/(fault+'-campaign.json'),campaign)
    with pytest.raises(ValueError,match='campaign'):
        trial.prepare(root/fault,operator='exp',run_id='other' if fault=='unregistered_run' else 'CPU-exp',
            qualification=root/'qualification.json',review_inputs=root/'review-inputs.json',
            candidate_plan=root/'exp-candidate-plan.json',campaign=path)


def test_missing_review_inputs_preserves_failed_preparation(tmp_path,monkeypatch):
    monkeypatch.setattr(trial,'require_worker_build_budget_enforcement',lambda *a,**k:None)
    qualification=dump(tmp_path/'qualification.json',{'CPU_fixture':True})
    reviews=dump(tmp_path/'review.json',{})
    output=tmp_path/'failed'
    with pytest.raises(ValueError,match='review input'):
        trial.prepare(output,operator='exp',run_id='CPU',qualification=qualification,
                      review_inputs=reviews,candidate_plan=tmp_path/'unused',campaign=tmp_path/'unused')
    assert (output/'preparation-failure.json').is_file()
    assert (output/'preparation-partial-index.json').is_file()
    with pytest.raises(FileExistsError):
        trial.prepare(output,operator='exp',run_id='CPU',qualification=qualification,
                      review_inputs=reviews,candidate_plan=tmp_path/'unused',campaign=tmp_path/'unused')

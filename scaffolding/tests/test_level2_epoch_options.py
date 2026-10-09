"""CPU-only checks for prospective capture epochs and closed-stage reclamation."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import level2_iteration as iteration
import msprof_raw_storage as storage
import run_msprof_exploration_stage as stage
from msprof_exploration_execute import load, pointer, save
from msprof_exploration_report import DESIGN
from msprof_search_protocol import LITE_PROTOCOL


def local_plan():
    request = {'version': 'msprof_kernel_time_study_v2', 'capture_storage': deepcopy(storage.LOCAL),
               'capture_storage_producer': pointer(storage.__file__)}
    return {'protocol': 'msprof_task_time_exploration_v2', 'analysis_version': 'msprof_exploration_analysis_v2',
            'comparison_kind': 'ab', 'calibration_scope': {'epoch': 'local-02', 'capture_storage': deepcopy(storage.LOCAL),
                'capture_storage_producer_hash': request['capture_storage_producer']['sha256']},
            'schedule': [{'name': 'p'+str(i), 'request': {**deepcopy(request),
                         'load_order': a, 'first_order': b, 'buffer_configs': c}} for i, (a,b,c) in enumerate(DESIGN)]}


def calibration(plan):
    return {'protocol': plan['protocol'], 'analysis_version': plan['analysis_version'],
            'comparison_kind': 'aa', 'evidence_status': 'verified_complete', 'formal_admission': 'not_evaluated',
            'calibration_scope': deepcopy(plan['calibration_scope']), 'environment_binding': {
                'capture_storage': deepcopy(storage.LOCAL),
                'capture_storage_producer_hash': pointer(storage.__file__)['sha256']}}


@pytest.mark.parametrize('options', [[], {'unknown': 1}, {'epoch': '../escape'}, {'epoch': ''},
    {'capture_storage': storage.LOCAL}, {'epoch': 'local-02', 'capture_storage': {'mode': 'unknown'}},
    {'calibration_by_relation': {'other': '/tmp/report.json'}}, {'calibration_by_relation': []},
    {'calibration_path': None}, {'capture_storage': None}])
def test_invalid_options_fail_before_candidate_registration_or_any_stage(tmp_path, monkeypatch, options):
    monkeypatch.setattr(iteration, 'Campaign', lambda *_: pytest.fail('invalid option reached ledger'))
    with pytest.raises(ValueError):
        iteration.candidate(tmp_path, 'gcd', 'gcd001', measurement=options)


def test_default_cli_retains_legacy_search_plan_shape_and_task_path_api(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(iteration, 'candidate', lambda *a, **kw: calls.append((a,kw)) or {'status': 'measured'})
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py', 'candidate', '--run', str(tmp_path),
        '--operator', 'gcd', '--candidate', 'gcd001', '--search-protocol', 'full'])
    assert iteration.main() == 0
    assert calls[0][1] == {'measurement': {}, 'deduplicate_outputs': False}
    assert 'calibration_path' not in calls[0][1]['measurement']


def test_local_cli_binds_explicit_epoch_group_and_dedup(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(iteration, 'candidate', lambda *a, **kw: calls.append((a,kw)) or {'status': 'measured'})
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py', 'candidate', '--run', str(tmp_path),
        '--operator', 'gcd', '--candidate', 'gcd001', '--capture-storage', 'local', '--epoch', 'local-02',
        '--calibration-group', 'aa-local-02', '--deduplicate-outputs', '--search-protocol', 'full'])
    assert iteration.main() == 0
    assert calls[0][1] == {'measurement': {'epoch': 'local-02', 'capture_storage': storage.LOCAL,
        'calibration_path': iteration.task_path(tmp_path, 'gcd')/'stages/aa-local-02/cohort/report.json'},
        'deduplicate_outputs': True}


@pytest.mark.parametrize('extra', [['--capture-storage','local'], ['--calibration-group','../aa-escape']])
def test_invalid_cli_options_do_not_reach_coordinator(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(iteration, 'candidate', lambda *a, **kw: pytest.fail('invalid CLI reached coordinator'))
    monkeypatch.setattr(sys, 'argv', ['level2_iteration.py','candidate','--run',str(tmp_path),
        '--operator','gcd','--candidate','gcd001',*extra])
    with pytest.raises(SystemExit) as exc:
        iteration.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('fault', ['epoch', 'storage', 'producer', 'unknown'])
def test_control_resume_rejects_changed_explicit_identity(fault):
    frozen = local_plan();settings = {'epoch': 'local-02', 'capture_storage': storage.LOCAL}
    iteration.check_control_settings(frozen,settings)
    if fault == 'epoch':settings['epoch'] = 'local-03'
    elif fault == 'storage':settings['capture_storage'] = storage.DIRECT
    elif fault == 'producer':frozen['schedule'][0]['request']['capture_storage_producer']['sha256'] = 'sha256:'+'0'*64
    else:settings['ignored_option'] = True
    with pytest.raises(ValueError):iteration.check_control_settings(frozen,settings)


@pytest.mark.parametrize('fault', ['old_network','scope_relabel_only','old_epoch','producer','not_verified'])
def test_local_measurement_rejects_incompatible_aa_identity(fault):
    plan = local_plan();aa = calibration(plan)
    stage.validate_calibration_storage(plan,aa)
    if fault == 'old_network':
        aa['calibration_scope'] = {'epoch': 'epoch-01'};aa['environment_binding'] = {}
    elif fault == 'scope_relabel_only':aa['environment_binding'] = {}
    elif fault == 'old_epoch':aa['calibration_scope']['epoch'] = 'epoch-01'
    elif fault == 'producer':aa['environment_binding']['capture_storage_producer_hash'] = 'sha256:'+'0'*64
    else:aa['evidence_status'] = 'incomplete'
    with pytest.raises(ValueError,match='fresh A/A'):stage.validate_calibration_storage(plan,aa)


def test_all_local_calibrations_checked_before_first_cohort_native(tmp_path,monkeypatch):
    class Ledger:
        config = {'policy': {'protocol': stage.PROTOCOL}}
        def __init__(self,*_):pass
        def validate_start(self,**_):pass
        def start(self,**_):pass
        def finish(self,**_):pass
    monkeypatch.setattr(stage,'Campaign',Ledger)
    monkeypatch.setattr(stage,'collect_cohort',lambda *a,**kw:pytest.fail('must reject second calibration before first launch'))
    good = local_plan();aa = calibration(good)
    aa_path=tmp_path/'local-aa.json';save(aa_path,aa)
    old_path=tmp_path/'old-aa.json';save(old_path,{**aa,'environment_binding':{}})
    cohorts=[]
    for relation in ('direct_parent','original_baseline'):
        path=tmp_path/(relation+'.json');save(path,good)
        cohorts.append({'relation':relation,'plan':pointer(path)})
    cohorts[1]['calibration_report']=pointer(old_path)
    path=tmp_path/'plan.json';save(path,{'calibration_report':pointer(aa_path),'cohorts':cohorts})
    result=stage.run_stage(tmp_path,'gcd','gcd001','timing','search',plan_path=path)
    assert result['status']=='failed' and result['native_started'] is False
    assert 'fresh A/A' in result['error']['message']
    assert result['actual_costs']['native_processes_started']==0


@pytest.mark.parametrize('outcome',['passed','failed','raises'])
def test_baseline_dedup_is_synchronous_and_only_after_successful_closed_control(tmp_path,monkeypatch,outcome):
    calls=[]
    def execute(run,op,cid,kind,group,**kwargs):
        calls.append('start-'+kind)
        if kind=='control' and outcome=='raises':raise OSError('capture still incomplete')
        calls.append('closed-'+kind)
        return {'status':outcome if kind=='control' else 'passed'}
    monkeypatch.setattr(iteration,'stage',execute)
    def reclaim(*args):
        assert calls[-1]=='closed-control'
        calls.append('dedup')
    monkeypatch.setattr(iteration,'reclaim_outputs',reclaim)
    if outcome=='raises':
        with pytest.raises(OSError):iteration.baseline(tmp_path,'gcd',deduplicate_outputs=True)
    else:
        result=iteration.baseline(tmp_path,'gcd',deduplicate_outputs=True)
        assert result['status']==('baseline_validated_and_calibrated' if outcome=='passed' else 'blocked')
    assert ('dedup' in calls)==(outcome=='passed')


def test_dedup_not_requested_keeps_existing_behavior(tmp_path,monkeypatch):
    monkeypatch.setattr(iteration,'stage',lambda *a,**kw:{'status':'passed'})
    monkeypatch.setattr(iteration,'reclaim_outputs',lambda *a:pytest.fail('default must not dedup'))
    assert iteration.baseline(tmp_path,'gcd')['status']=='baseline_validated_and_calibrated'


def test_resume_rejects_invalid_stage_kwargs_before_existing_result_lookup(tmp_path,monkeypatch):
    monkeypatch.setattr(iteration,'task_paths',lambda *a:pytest.fail('must reject before touching frozen stage'))
    with pytest.raises(ValueError,match='frozen plan'):
        iteration.stage(tmp_path,'gcd','gcd001','timing','search',capture_storage=storage.LOCAL,epoch='local-02')
    with pytest.raises(ValueError,match='unknown stage'):
        iteration.stage(tmp_path,'gcd','gcd001','build','build',unknown=True)


def test_local_prepare_requires_explicit_calibration_before_plan_artifacts(tmp_path,monkeypatch):
    from types import SimpleNamespace
    row={'source_parent':{'candidate_id':None,'source_hash':'sha256:'+'b'*64},'probes':[]}
    ledger=SimpleNamespace(state={'tasks':{'gcd':{'candidates':{'gcd001':row}}}},
        config={'tasks':{'gcd':{'baseline_source_hash':'sha256:'+'b'*64}}})
    monkeypatch.setattr(stage,'Campaign',lambda *_:ledger)
    with pytest.raises(ValueError,match='explicit fresh calibration'):
        stage.prepare_timing(tmp_path,'gcd','gcd001','search',epoch='local-02',capture_storage=storage.LOCAL)
    assert not (tmp_path/'train/tasks/gcd/candidates/gcd001/plans').exists()


def test_resumed_timing_requires_exact_calibration_pointer_and_relation(tmp_path):
    aa_path=tmp_path/'aa.json';save(aa_path,calibration(local_plan()))
    cohort=tmp_path/'cohort.json';save(cohort,local_plan())
    plan={'calibration_report':pointer(aa_path),'cohorts':[{'relation':'direct_parent','plan':pointer(cohort)}]}
    settings={'epoch':'local-02','capture_storage':storage.LOCAL,'calibration_path':aa_path}
    iteration.check_timing_settings(plan,settings)
    for change in ({'epoch':'local-03'}, {'calibration_by_relation':{'original_baseline':aa_path}},
                   {'calibration_path':tmp_path/'other.json'}):
        if change.get('calibration_path') is not None:save(change['calibration_path'],calibration(local_plan()))
        with pytest.raises(ValueError):iteration.check_timing_settings(plan,{**settings,**change})
    aa_path.write_text('{}')
    with pytest.raises(ValueError,match='calibration differs'):
        iteration.check_timing_settings(plan,settings)


def test_feedback_lookup_uses_observation_hash_for_explicit_later_same_source_record(tmp_path):
    task=tmp_path/'train/tasks/gcd';cid='gcd001'
    blocked={'operator':'gcd','candidate_id':cid,'status':'infrastructure_blocked'}
    recovered={**blocked,'status':'source_attempt_failed'}
    old=task/'feedback/gcd001.json';new=task/'feedback/gcd001-observation-02.json'
    save(old,blocked);save(new,recovered)
    before=old.read_bytes()
    observation={'report_ref':pointer(new)['sha256'],'feedback':recovered}
    assert iteration.feedback_pointer(task,cid,observation)==pointer(new)
    assert old.read_bytes()==before
    with pytest.raises(ValueError,match='identity'):
        iteration.feedback_pointer(task,'gcd002',observation)
    new.unlink()
    with pytest.raises(ValueError,match='immutable observation'):
        iteration.feedback_pointer(task,cid,observation)


@pytest.mark.parametrize('protocol', ['msprof_task_time_exploration_v2', LITE_PROTOCOL])
@pytest.mark.parametrize('requested,expected', [(None, 'old-epoch-05'), ('epoch-01', 'epoch-01'),
                                               ('old-epoch-05', 'old-epoch-05')])
def test_auto_inherits_only_omitted_epoch(tmp_path, monkeypatch, protocol, requested, expected):
    task=tmp_path/'train/tasks/gather'
    cohort=task/'candidates/gather001/plans/search/cohort.json'
    cohort.parent.mkdir(parents=True)
    cohort.write_text(json.dumps({'calibration_scope': {'epoch': 'old-epoch-05'}}))
    plan={'protocol':protocol,'cohorts':[{'relation':'direct_parent','plan':iteration.pointer(cohort)}]}
    (cohort.parent/'stage-plan.json').write_text(json.dumps(plan))
    argv=['level2_iteration.py','candidate','--run',str(tmp_path),'--operator','gather','--candidate','gather001']
    if requested is not None:argv+=['--epoch',requested]
    monkeypatch.setattr(sys,'argv',argv)
    captured=[]
    def candidate(*args, **kwargs):
        captured.append(kwargs['measurement'])
        return {'status':'measured'}
    monkeypatch.setattr(iteration,'candidate',candidate)
    assert iteration.main()==0
    assert captured[0]['epoch']==expected
    # An explicit epoch does not invent a calibration pointer absent from the
    # frozen plan; the existing candidate settings check rejects epoch changes.
    assert 'calibration_path' not in captured[0]
    assert 'calibration_by_relation' not in captured[0]


def test_explicit_epoch_change_reaches_frozen_setting_rejection(tmp_path, monkeypatch):
    task=tmp_path/'train/tasks/gather'
    cohort=task/'candidates/gather001/plans/search/cohort.json'
    cohort.parent.mkdir(parents=True)
    frozen={'protocol':LITE_PROTOCOL,'calibration_scope':{'epoch':'old-epoch-05'},
            'schedule':[{'request':{}},{'request':{}}]}
    cohort.write_text(json.dumps(frozen))
    plan={'protocol':LITE_PROTOCOL,'cohorts':[{'relation':'direct_parent','plan':iteration.pointer(cohort)}]}
    (cohort.parent/'stage-plan.json').write_text(json.dumps(plan))
    monkeypatch.setattr(sys,'argv',['level2_iteration.py','candidate','--run',str(tmp_path),
        '--operator','gather','--candidate','gather001','--epoch','epoch-01'])
    monkeypatch.setattr(iteration,'candidate',lambda *a,**kw:iteration.check_timing_settings(plan,kw['measurement']))
    with pytest.raises(ValueError,match='requested epoch differs'):
        iteration.main()

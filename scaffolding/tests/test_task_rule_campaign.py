"""Small real CPU dispatcher fixtures; no provider, CANN or performance claim."""
import json
from pathlib import Path
import shutil
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'collection/scripts'
sys.path.insert(0, str(SCRIPTS))
import task_rule_campaign as campaign
import task_rule_trial as trial
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import StoreError
from timing_admission import read


CHILD = '''
import argparse,json,time,sys
from pathlib import Path
sys.path.insert(0,SCRIPTS)
from task_rule_recorder import TaskRuleRecorder,LocalEvidence,STAGES
from timing_admission import read
p=argparse.ArgumentParser();p.add_argument('--anchor');p.add_argument('--local-index');args=p.parse_args()
started=time.time();mono=time.monotonic();local=LocalEvidence.from_index(args.local_index)
anchor_ref=local.register_artifact(args.anchor);anchor=read(local,anchor_ref)
plan=read(local,anchor['controller_plan_ref']);root=Path(plan['directory']);mode=plan['CPU_mode']
terminal=dict(schema_version=1,status='failed',anchor_ref=anchor_ref,started_at=started,
    archive_performed=False,storage_mode='local_profile_only',actual_builds=0)
if mode!='prebuild':
    value=local.register_json({'CPU_fixture':True,'not_real_components':True})
    post=dict(binary_hashes={r:value for r in ('baseline','candidate')},oracle_files={'CPU':value},
        task_config_ref=value,profile_configs={r:value for r in ('baseline','candidate')})
    launch=json.loads((root/'dispatcher-launch.json').read_text())
    rec=TaskRuleRecorder(local,root/'admission',anchor_ref=anchor_ref,post_build=post,deadline=launch['monotonic_deadline'])
    for stage in STAGES:
        rec.start(stage)
        if mode=='partial' and stage=='boundary':
            rec.fail_active(RuntimeError('CPU boundary failure'));break
        rec.complete(stage,[value],report_ref=None if stage=='online_admission' else value)
    terminal['child_report_ref']=rec.partial_report() if mode=='partial' else rec.finish()
    terminal['actual_builds']=1
    terminal['measurement_expected']={'CPU_fixture':True}
    if mode=='complete':terminal['status']='passed'
terminal.update(error=None if terminal['status']=='passed' else {'type':'CPUFailure','message':'CPU-only rejection'},
    finished_at=time.time(),duration_seconds=time.monotonic()-mono)
(root/'controller-result.json').write_text(json.dumps(terminal))
local.register_artifact(root/'controller-result.json');local.write_index(root/'controller-local-index.json')
raise SystemExit(0 if terminal['status']=='passed' else 2)
'''


def save(path, value):
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def make_campaign(tmp_path, monkeypatch):
    def make(modes=('prebuild', 'partial')):
        root = tmp_path / ('fixture-' + str(len(list(tmp_path.iterdir())))); root.mkdir()
        top = LocalEvidence(root / 'records')
        child = root / 'task_rule_controller.py'; child.write_text('SCRIPTS=' + repr(str(SCRIPTS)) + '\n' + CHILD)
        monkeypatch.setattr(trial, 'CONTROLLER', child)
        monkeypatch.setattr(trial, 'producer_paths', lambda: [child])
        attempts, freezes = [], []
        for op in ('exp', 'sigmoid'):
            sources = {role: top.register_json({'schema_version':'1.0.0','files':{},'CPU_fixture':op+role})
                       for role in ('baseline','candidate')}
            attempts.append(dict(operator=op,run_id='CPU-'+op,candidate_id='CPU-'+op+'-candidate',source_hashes=sources))
            f=save(root/(op+'-freeze.json'),dict(schema_version=1,operator=op,source_hashes=sources))
            freezes.append(dict(path=str(f),sha256=top.register_artifact(f)))
        prior=save(root/'old-token-budget-rejection.json',{'status':'failed','budget_policy':'old_8000','CPU_fixture':True})
        prior_ref=top.register_artifact(prior)
        value=dict(schema_version=1,kind='teacher_task_rule_campaign',protocol=campaign.PROTOCOL,
            task_protocol=campaign.TASK_PROTOCOL,runtime_build='aprof-runtime/0.2.3',model=campaign.MODEL,
            budget_seconds=3600,budget_policy='time_only_v1',reviewer_token_limit=None,max_attempts_per_operator=1,
            stop_on_failure=True,resampling='none',created_at=time.time(),attempts=attempts,source_freezes=freezes,
            trace_index_sha256=prior_ref,split_index_sha256=prior_ref,
            prior_campaign_refs=[dict(path=str(prior),sha256=prior_ref)])
        path=save(root/'campaign.json',value);ref=top.register_artifact(path)
        qual=save(root/'qualification.json',dict(model='gpt-6-sol',reasoning_effort='max',budget_policy='time_only_v1',
            review_submission_protocol='final_json_review_v1',CPU_fixture=True));qref=top.register_artifact(qual)
        trials={}; results={}; locals_={}
        for attempt,mode in zip(attempts,modes,strict=True):
            op=attempt['operator'];d=root/op;d.mkdir();local=LocalEvidence(d/'records');locals_[op]=local
            for reference in list(top._paths):local.register_artifact(top.verify_artifact(reference))
            metadata=save(d/'original-metadata.json',{'case_id':12,'range':[float('-inf'),float('inf')]})
            mref=local.register_artifact(metadata);fixture=local.register_json({'CPU_fixture':True})
            inputs=local.register_json({str(metadata):mref})
            frozen=local.register_json({str(path):ref,str(child):local.register_artifact(child)})
            plan=dict(directory=str(d),release=str(trial.bridge.RELEASE),model=campaign.MODEL,
                launch_path=str(d/'dispatcher-launch.json'),physical_device=0,frozen_files_ref=frozen,
                worker_qualification={'path':str(qual),'sha256':qref},CPU_mode=mode)
            pref=local.register_artifact(save(d/'controller-plan.json',plan))
            job=dict(job_id=attempt['run_id'],argv=[str(Path(sys.executable).resolve()),str(child),
                '--anchor',str(d/'anchor.json'),'--local-index',str(d/'prepared-local-index.json')],
                cwd=str(root),output_dir=str(d/'job'),timeout_seconds=3600,
                environment={'APROF_SKILL_LIB':str(trial.bridge.RELEASE),'PYTHONDONTWRITEBYTECODE':'1',
                    'ASCEND_RT_VISIBLE_DEVICES':'0','APROF_PHYSICAL_DEVICE':'0','APROF_LOGICAL_DEVICE':'0'})
            jref=local.register_artifact(save(d/'job.json',job))
            anchor=dict(schema_version=1,protocol=campaign.PROTOCOL,task_protocol=campaign.TASK_PROTOCOL,purpose='promotion',
                **attempt,campaign_ref=ref,controller_plan_ref=pref,job_ref=jref,budget_seconds=3600,created_at=time.time(),
                input_inventory_ref=inputs,boundary_plan_ref=fixture,screen_plan_ref=fixture,profile_plan_ref=fixture,
                source_review_ref=fixture,history_refs=[prior_ref])
            aref=local.register_artifact(save(d/'anchor.json',anchor))
            local.write_index(d/'prepared-local-index.json')
            save(d/'prepared.json',dict(anchor_ref=aref,local_index=trial.pointer(d/'prepared-local-index.json')))
            if mode=='not_run':
                blocker=results['exp'];er=read(locals_['exp'],blocker['execution_ref']);static_start=time.time()
                closure=dict(schema_version=1,kind='unstarted_task_dependency_closure',status='not_run',created_at=time.time(),
                    anchor_ref={'path':str(d/'anchor.json'),'sha256':aref},campaign_ref=ref,
                    **{k:attempt[k] for k in ('operator','run_id','candidate_id')},reason='CPU fixed shared prerequisite failure',
                    blocking_controller_result_ref={'path':str(root/'exp/controller-result.json'),'sha256':blocker['controller_result_ref']},
                    blocking_execution_ref={'path':str(root/'exp/job/execution.json'),'sha256':blocker['execution_ref']},
                    affected_metadata_ref={'path':str(metadata),'sha256':mref},static_check=dict(started_at=static_start,
                        duration_seconds=0.001,error='Out of range float values are not JSON compliant',
                        method='json.dumps(original_metadata, allow_nan=False); no source or input mutation'),
                    actual_builds=0,hardware_stages_started=0,admission_authority=False,archive_performed=False)
                nref=top.register_artifact(save(d/'not-run.json',closure))
                trials[op]=dict(reader=local,index_ref=top.register_artifact(d/'prepared-local-index.json'),not_run_ref=nref)
            else:
                result=trial.run(d,expected_anchor=aref);results[op]=result
                local=LocalEvidence.from_index(d/'dispatcher-local-index.json');locals_[op]=local
                trials[op]=dict(reader=local,index_ref=top.register_artifact(d/'dispatcher-local-index.json'),
                    dispatcher_result_ref=local.register_artifact(d/'dispatcher-result.json'))
        return dict(top=top,ref=ref,trials=trials,root=root,results=results)
    return make


def replay(f):
    return campaign.replay_task_rule_campaign(f['top'],f['ref'],trials=f['trials'])


def test_real_failed_exits_and_partial_chain_are_retained(make_campaign):
    f=make_campaign();result=replay(f)
    assert result['valid'] and result['complete'] and not result['all_components_valid']
    assert not result['admission_authority'] and not result['eligible_for_publication']
    assert [r['exit_code'] for r in result['trials']]==[2,2]
    assert result['trials'][0]['partial_roster'] is None
    assert result['trials'][1]['partial_roster']==dict(events=3,completed_stages=['correctness'],active_stage='boundary')
    for op, supplied in f['trials'].items():
        launch_path = f['root']/op/'dispatcher-launch.json'
        reader = supplied['reader']
        launch_ref = trial.pointer(launch_path)['sha256']
        launch = read(reader, launch_ref)
        execution = read(reader, f['results'][op]['execution_ref'])
        assert execution['job']['deadline_monotonic'] == launch['monotonic_deadline']
        assert execution['job']['timeout_seconds'] == launch['child_timeout_seconds']
        assert str(launch_path) in json.loads((f['root']/op/'dispatcher-local-index.json').read_text())['artifacts'].values()


def test_registered_prerequisite_not_run_has_no_fake_execution(make_campaign):
    f=make_campaign(('partial','not_run'));result=replay(f)
    assert result['complete'] and not result['all_components_valid']
    assert result['trials'][1]['status']=='not_run' and result['trials'][1]['execution_ref'] is None
    (f['root']/'sigmoid/job').mkdir()
    with pytest.raises(ValueError,match='actually launched'):replay(f)


@pytest.mark.parametrize('defect',['omitted','extra','old_budget','wrong_source'])
def test_campaign_registration_changes_reject(make_campaign,defect):
    f=make_campaign()
    if defect=='omitted':f['trials'].pop('sigmoid')
    elif defect=='extra':f['trials']['retry']=f['trials']['exp']
    else:
        value=read(f['top'],f['ref'])
        if defect=='old_budget':value['reviewer_token_limit']=8000
        else:value['attempts'][0]['source_hashes']['baseline']='sha256:'+'0'*64
        f['ref']=f['top'].register_json(value)
    with pytest.raises(ValueError):replay(f)


def test_failed_actual_exit_cannot_be_upgraded(make_campaign):
    f=make_campaign();row=f['trials']['exp'];value=read(row['reader'],row['dispatcher_result_ref'])
    value.update(status='completed_child',error=None)
    path=f['root']/'exp/dispatcher-result.json';path.write_text(json.dumps(value))
    ref=row['reader'].register_artifact(path);row['dispatcher_result_ref']=ref
    index=read(f['top'],row['index_ref']);index['artifacts'][ref]=str(path)
    row['index_ref']=f['top'].register_json(index)
    with pytest.raises(ValueError,match='cannot be completed'):replay(f)


def test_mutated_real_exit_log_is_rejected(make_campaign):
    f=make_campaign();(f['root']/'exp/job/stdout.log').write_text('changed')
    with pytest.raises(Exception,match='changed|hash'):replay(f)


def test_partial_failure_cannot_be_completed_and_followed_by_next_stage(make_campaign):
    f=make_campaign();row=f['trials']['sigmoid'];reader=row['reader'];result=f['results']['sigmoid']
    anchor=read(reader,result['anchor_ref']);report=read(reader,result['child_report_ref'])
    roster=read(reader,report['attempt_roster_ref']);event=read(reader,roster['events'][-1])
    failure_ref=report['stage_evidence']['boundary'][0]
    event.update(sequence=3,previous_ref=roster['events'][-1],state='completed',exit_status=0,
                 evidence_refs=report['stage_evidence']['boundary'])
    roster['events'].append(reader.register_json(event));report['attempt_roster_ref']=reader.register_json(roster)
    actual=read(reader,result['execution_ref'])
    with pytest.raises(ValueError,match='failed stage was completed'):
        campaign._partial(reader,report,anchor,result['anchor_ref'],campaign._timestamp(actual['started_at']),
                          campaign._timestamp(actual['finished_at']),failure_ref)


def test_not_run_requires_actual_registered_failure(make_campaign):
    f=make_campaign(('partial','not_run'));row=f['trials']['sigmoid'];value=read(f['top'],row['not_run_ref'])
    value['blocking_execution_ref']['sha256']='sha256:'+'0'*64
    row['not_run_ref']=f['top'].register_json(value)
    with pytest.raises(ValueError,match='earlier registered failure'):replay(f)


def test_completed_child_delegates_full_outer_once_each_and_cannot_skip_it(make_campaign,monkeypatch):
    f=make_campaign(('complete','complete'))
    import task_outer_admission as outer
    with pytest.raises(ValueError):replay(f)  # Real outer rejects CPU summaries, not mathematical evidence.
    calls=[]
    def only_wiring(reader,report_ref,**kwargs):
        calls.append((report_ref,kwargs));return dict(valid=True,admission_authority=False,CPU_fixture=True)
    monkeypatch.setattr(outer,'verify_task_rule_admission',only_wiring)
    result=replay(f)
    assert len(calls)==2 and result['all_components_valid'] and not result['admission_authority']
    assert {x[1]['expected']['execution_ref'] for x in calls}=={r['execution_ref'] for r in f['results'].values()}


def test_failed_evidence_replays_from_actual_readonly_cas_after_fixture_paths_removed(make_campaign,tmp_path):
    import sqlite3
    from aprof_runtime.store import EpisodeStore,_ReadOnlyArtifacts
    f=make_campaign(('partial','not_run'));database=tmp_path/'retained.sqlite'
    with EpisodeStore(database) as store:
        for local in [f['top'],*[row['reader'] for row in f['trials'].values()]]:
            for reference,path in local._paths.items():
                assert store.register_artifact(path)==reference
        objects=store.objects_path
    shutil.rmtree(f['root'])
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
        reader=_ReadOnlyArtifacts(connection,objects)
        trials={op:{**row,'reader':reader} for op,row in f['trials'].items()}
        result=campaign.replay_task_rule_campaign(reader,f['ref'],trials=trials)
    assert result['complete'] and [r['status'] for r in result['trials']]==['failed','not_run']


@pytest.fixture
def boundary_dependency_fixture(tmp_path, monkeypatch):
    """Tiny exact-code fixture for the narrow AST contract, not a controller run."""
    root=tmp_path/'sigmoid';root.mkdir();local=LocalEvidence(root/'records')
    controller=tmp_path/'task_rule_controller.py'
    controller.write_text("def run(workspace, local):\n    oracle = workspace / 'baseline/scripts/verify_result.py'\n    return dict(oracle_files={str(oracle): local.register_artifact(oracle)})\n")
    cref=local.register_artifact(controller)
    monkeypatch.setattr(campaign,'BOUNDARY_ONLY_VERIFIER_CONTROLLER',cref)
    oracle=root/'worker/root/work/baseline/scripts/verify_result.py';oracle.parent.mkdir(parents=True)
    oracle.write_text('# CPU verifier\n');oref=local.register_artifact(oracle)
    generator=tmp_path/'gen_data.py';generator.write_text('# CPU generator\n');gref=local.register_artifact(generator)
    boundary=save(tmp_path/'boundary-plan.json',dict(schema_version=1,operator='sigmoid',generator_ref=gref,verifier_ref=oref))
    bref=local.register_artifact(boundary)
    frozen={str(controller):cref,str(oracle):oref,str(generator):gref,str(boundary):bref}
    plan={'frozen_files_ref':local.register_json(frozen)}
    anchor={'operator':'sigmoid','created_at':1.0,'boundary_plan_ref':bref};aref=local.register_json(anchor)
    snapshot=dict(schema_version=1,kind='frozen_task_producer_source_archive',owner='trace_collection',cost_scope='post_task',
        source_anchors={'sigmoid':{'path':str(root/'anchor.json'),'sha256':aref}},
        frozen_files_refs={'sigmoid':plan['frozen_files_ref']},
        files={str(controller):dict(path=str(controller),sha256=cref,bytes=controller.stat().st_size)})
    spath=save(tmp_path/'producer-index.json',snapshot);sref=local.register_artifact(spath)
    check=dict(schema_version=1,kind='frozen_boundary_oracle_binding_preflight',started_at=2.0,duration_seconds=0.1,
        method='parse exact frozen controller AST and compare its verifier-only oracle_files to the frozen boundary plan; no execution',
        producer_snapshot={'path':str(spath),'sha256':sref},controller_snapshot={'path':str(controller),'sha256':cref},
        original_controller_path=str(controller),oracle_files_expression='{str(oracle): local.register_artifact(oracle)}',
        boundary_plan_ref={'path':str(boundary),'sha256':bref},required_oracle_refs={'generator':gref,'verifier':oref},
        bound_oracle_refs={str(oracle):oref},missing_oracle_refs=[gref],passed=False,admission_authority=False)
    kwargs=dict(anchor=anchor,anchor_ref=aref,plan=plan,frozen=frozen,root=root,controller_path=str(controller),created_at=3.0)
    return local,check,kwargs


def test_boundary_dependency_recomputes_exact_frozen_ast_and_missing_set(boundary_dependency_fixture):
    local,check,kwargs=boundary_dependency_fixture
    result=campaign._boundary_dependency(local,check,**kwargs)
    assert result['missing_oracle_refs']==[check['required_oracle_refs']['generator']]


@pytest.mark.parametrize('defect',['missing_set','required_source','bound_source','expression','snapshot_anchor','source_bytes','chronology'])
def test_boundary_dependency_tampering_rejects(boundary_dependency_fixture,defect):
    local,check,kwargs=boundary_dependency_fixture
    if defect=='missing_set':check['missing_oracle_refs']=[]
    elif defect=='required_source':check['required_oracle_refs']['generator']=check['required_oracle_refs']['verifier']
    elif defect=='bound_source':check['bound_oracle_refs']['invented-generator']=check['required_oracle_refs']['generator']
    elif defect=='expression':check['oracle_files_expression']='{}'
    elif defect=='snapshot_anchor':
        snapshot=read(local,check['producer_snapshot']['sha256'])
        snapshot['source_anchors']['sigmoid']['sha256']='sha256:'+'0'*64
        ref=local.register_json(snapshot);check['producer_snapshot']={'path':str(local.verify_artifact(ref)),'sha256':ref}
    elif defect=='source_bytes':Path(check['controller_snapshot']['path']).write_text('# corrupted saved code\n')
    else:check['started_at']=4.0
    with pytest.raises((ValueError,StoreError)):campaign._boundary_dependency(local,check,**kwargs)


def test_real_campaign3_schema2_replay_is_failed_and_not_run(tmp_path):
    """One bounded replay of already archived receipts; no hardware/blob reads."""
    import hashlib
    archive=SCRIPTS.parents[3]/'validation-graph-base-1.0.0/task-v5-boundary-binding-rejection-20261015'
    if not archive.exists():pytest.skip('retained campaign3 evidence is not installed on this host')
    raw=(archive/'archive-inventory.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='a13a7ec1ef00756c2aad342d13ed7581eed9914a2038d045d7b08dc9800c6986'
    inventory=json.loads(raw);rows=inventory['files']
    class Archived:
        def __init__(self):
            self.paths={r['sha256']:Path(r['path']) for r in rows.values()}
            p=inventory['producer_index_ref'];self.paths[p['sha256']]=Path(p['path'])
        def verify_artifact(self,reference):
            p=self.paths[reference];assert p.is_relative_to(archive)
            assert p.suffix not in {'.bin','.o','.so'}
            if 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()!=reference:raise ValueError('archive bytes changed')
            return p
    reader=Archived();root=Path('/tmp/aprof-teacher-native-json-fixed-20261015-9r1smydf')
    ref=lambda p:rows[str(p)]['sha256']
    trials={'exp':dict(reader=reader,index_ref=ref(root/'exp/dispatcher-local-index.json'),
                      dispatcher_result_ref=ref(root/'exp/dispatcher-result.json')),
            'sigmoid':dict(reader=reader,index_ref=ref(root/'sigmoid/prepared-local-index.json'),
                          not_run_ref=ref(root/'sigmoid/not-run.json'))}
    started=time.monotonic();result=campaign.replay_task_rule_campaign(reader,ref(root/'campaign.json'),trials=trials)
    assert result['valid'] and result['complete'] and not result['all_components_valid']
    assert not result['eligible_for_publication'] and not result['admission_authority']
    assert [r['status'] for r in result['trials']]==['failed','not_run']
    assert result['trials'][0]['exit_code']==2 and result['trials'][1]['execution_ref'] is None
    assert result['trials'][1]['closure']['schema_version']==2
    save(tmp_path/'actual-campaign3-replay.json',dict(result=result,elapsed_seconds=time.monotonic()-started,
        archive_inventory_ref='sha256:'+hashlib.sha256(raw).hexdigest(),read_only=True,no_hardware=True))

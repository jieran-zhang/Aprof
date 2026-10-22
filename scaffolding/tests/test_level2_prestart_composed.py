"""Real Campaign -> full certificate -> runner -> data-only reader, CPU only.

Only the binary preflight and native collector are replaced. Journals and oracle
metadata are synthetic test records; these tests make no device-qualified claim.
"""
from copy import deepcopy
from pathlib import Path
import json
import pytest
import msprof_exploration_campaign as campaign
import msprof_exploration_execute as execution
import run_msprof_exploration_stage as runner
import level2_prestart_recovery as authorizer
import level2_stage_recovery as resolver
import level2_verification_storage as verification
from test_level2_prestart_campaign import failed_final as seed_failure
from test_level2_prestart_authorize import author


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(verification.canonical(value))
    return authorizer.pointer(path)


@pytest.fixture
def failed_final(tmp_path):
    """Before author() snapshots anything, freeze one executable tiny plan."""
    source,plan,args=seed_failure.__wrapped__(tmp_path/'seed')
    plan=deepcopy(plan)
    plan['calibration_report']=put(tmp_path/'planned/calibration.json',{'synthetic':True})
    cohort=put(tmp_path/'planned/cohort.json',{'case_ids':list(range(1,21)),
               'schedule':[{'name':f'p{n:02}','request':{}} for n in range(1,7)],'synthetic':True})
    plan['cohorts']=[{'relation':'direct_parent','plan':cohort,'control_candidate_id':'baseline'}]
    ledger=campaign.create_fresh(tmp_path/'planned-ledger',campaign_id='tiny',workloads={
        'group_norm':{'baseline_source_hash':'sha256:'+f'{1:064x}','source_split':'validation',
                      'repeat_by_case':{str(c):10 for c in campaign.ALL_CASES},'pilot_ref':'sha256:'+f'{2:064x}'}})
    for row in source.events[1:]:
        values=deepcopy(row['arguments'])
        if row['operation']=='freeze':values['final_plans']['group_norm002']=plan
        if row['event_id']=='first-start':values['plan']=plan
        ledger._commit(row['operation'],event_id=row['event_id'],**values)
    return ledger,plan,{**args,'plan_hash':campaign.digest(plan)}


@pytest.fixture
def pipeline(author,monkeypatch):
    state={'preflight':0,'collect':0,'fail':False}
    def preflight(frozen):
        assert frozen['case_ids']==list(range(1,21)) and len(frozen['schedule'])==6
        state['preflight']+=1
    monkeypatch.setattr(execution,'preflight_cohort',preflight)
    def collect(frozen,out,calibration):
        state['collect']+=1
        assert calibration=={'synthetic':True}
        out.mkdir();put(out/'plan.json',frozen)
        sessions=[];observations=[]
        for n in range(1,7):
            session=out/f'p{n:02}';sessions.append(str(session));artifacts={}
            put(session/'completion.json',{'status':'passed','error':None})
            put(session/'msprof.execution.json',{'exit_code':0,'error':None,'ended_at':2})
            put(session/'bindings.json',{})
            outputs=[{'case_id':'1','buffer_config':'normal','role':r,'passed':True} for r in 'AB']
            put(session/'validation.json',{'scope':'final_call_of_final_sample_per_case_config_role','outputs':outputs})
            for row in outputs:
                for name in verification.NAMES:
                    path=session/'verification'/f"1_normal_{row['role']}"/name
                    pointer=put(path,{'synthetic':True,'passed':True})
                    if name!='result.json':artifacts[str(path)]=pointer['sha256']
            journal=session/'native/journal.jsonl';journal.parent.mkdir()
            rows=[{'type':'process_start','synthetic':True}]
            if state['fail']:
                journal.write_bytes(b''.join(verification.canonical(r) for r in rows))
                raise RuntimeError('simulated collector failure')
            # Exercise the real cost reader: 20 cases * 2 configs * 30 pairs *
            # 2 roles = 2400 role samples per process, 14400 over all six.
            rows.extend({'type':'sample','repeat':10,'launches_per_call':1} for _ in range(2400))
            rows.append({'type':'session_end','exit_code':0})
            journal.write_bytes(b''.join(verification.canonical(r) for r in rows))
            observations.append({'directory':str(session),'artifacts':artifacts})
        put(out/'group-completion.json',{'status':'passed','error':None,'completed_sessions':sessions})
        put(out/'report.json',{'sessions':observations,'synthetic':True})
    monkeypatch.setattr(runner,'collect_cohort',collect)
    state['author']=author
    state['qualify']=lambda:author['invoke'](True)
    def execute(qualified):
        ref=qualified['qualification']
        return runner.run_qualified_timing_recovery(author['run'],Path(ref['path']),ref['sha256'])
    state['execute']=execute
    return state


def test_real_ledger_authorize_stub_collect_finish_resolver_and_verification(pipeline):
    p=pipeline;f=p['author'];before=deepcopy(f['ledger'].state['tasks']['group_norm'])
    old=(f['stage']/'result.json').read_bytes();plan=(f['stage']/'stage-plan.json').read_bytes()
    prefix=(f['ledger'].directory/'events.jsonl').read_bytes()
    done=p['qualify']();result=p['execute'](done)
    assert result['status']=='passed' and p['preflight']==p['collect']==1
    assert result['actual_costs']['native_processes_started']==result['actual_costs']['native_processes_completed']==6
    assert result['actual_costs']['role_samples']==14400 and result['actual_costs']['timed_complete_calls']==144000
    assert (f['stage']/'result.json').read_bytes()==old and (f['stage']/'stage-plan.json').read_bytes()==plan
    ledger=campaign.Campaign(f['ledger'].directory);task=ledger.state['tasks']['group_norm']
    attempts=task['stages']['group_norm002-final']['attempts']
    assert attempts[0]==before['stages']['group_norm002-final']['attempts'][0]
    assert len(attempts)==2 and attempts[1]['outcome']=='success' and attempts[1]['charged'] is None
    assert task['used']==before['used'] and task['new_rounds_started']==before['new_rounds_started']
    assert (ledger.directory/'events.jsonl').read_bytes().startswith(prefix)
    resolved=resolver.resolve_from_reader(f['stage'],require_success=True)
    assert resolved['current_result']==authorizer.pointer(f['stage']/'result.recovery-01.json')
    assert resolved['original_failed_result']==f['old'] and resolved['qualification']==done['qualification']
    for n in range(1,7):
        facts,roster=verification.closed_from_reader(f['stage']/f'direct_parent/p{n:02}',Path.read_bytes)
        assert facts['stage_recovery']['current_result']==resolved['current_result'] and len(roster)==8
        assert f['old'] in facts['protected'] and done['qualification'] in facts['protected']
        assert len(facts['stage_recovery']['event_bindings'])==2
    with pytest.raises(ValueError):p['execute'](done)
    assert p['collect']==1


@pytest.mark.parametrize('field',['old','qualification','current'])
def test_completed_pipeline_does_not_hide_changed_recovery_evidence(pipeline,field):
    p=pipeline;f=p['author'];done=p['qualify']();p['execute'](done)
    paths={'old':f['stage']/'result.json','qualification':Path(done['qualification']['path']),
           'current':f['stage']/'result.recovery-01.json'}
    paths[field].write_bytes(b'{}\n')
    with pytest.raises(ValueError):resolver.resolve_from_reader(f['stage'],require_success=True)
    with pytest.raises(ValueError):verification.closed_from_reader(f['stage']/'direct_parent/p01',Path.read_bytes)


def test_real_certificate_tamper_prevents_any_stub_execution(pipeline):
    p=pipeline;done=p['qualify']();Path(done['qualification']['path']).write_bytes(b'{}\n')
    with pytest.raises(ValueError):p['execute'](done)
    assert p['preflight']==p['collect']==0
    ledger=campaign.Campaign(p['author']['ledger'].directory)
    assert len(ledger.state['tasks']['group_norm']['stages']['group_norm002-final']['attempts'])==1


def test_real_pipeline_second_failure_is_retained_and_never_success(pipeline):
    p=pipeline;f=p['author'];old=(f['stage']/'result.json').read_bytes()
    done=p['qualify']();p['fail']=True;result=p['execute'](done)
    assert result['status']=='failed' and result['error']['message']=='simulated collector failure'
    assert result['actual_costs']['native_processes_started']==1 and result['actual_costs']['role_samples']==0
    assert (f['stage']/'result.json').read_bytes()==old
    proof=resolver.resolve_from_reader(f['stage'])
    assert proof['current_result']==authorizer.pointer(f['stage']/'result.recovery-01.json')
    with pytest.raises(ValueError):resolver.resolve_from_reader(f['stage'],require_success=True)
    with pytest.raises(ValueError):p['execute'](done)
    assert p['collect']==1

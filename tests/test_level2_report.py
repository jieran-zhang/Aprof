"""Read-only Level2 reporting, including partial runs and six-process grouping."""
import copy
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_report as report


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True)+'\n');return path


def ptr(path):return {'path':str(path),'sha256':report.analysis.sha(path)}


def tree(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def partial(tmp_path):
    run=tmp_path/'fresh-level2';task=run/'train/tasks/maximum';task.mkdir(parents=True)
    baseline=task/'baseline-source.tar';baseline.write_bytes(b'original source')
    manifest=dict(version='msprof_task_time_exploration_v2',run_id=run.name,operator='maximum',
        split='train',source_split='test',task_dir=str(task),baseline=ptr(baseline))
    save(task/'manifest.json',manifest)
    return run,task,manifest


def test_partial_manifest_drafts_and_preflight_never_count_as_rounds(tmp_path):
    run,task,_=partial(tmp_path)
    save(task/'candidates/maximum001/proposal.json',{'candidate_id':'maximum001'})
    save(task/'preflight/pilot/pilot.json',{'status':'passed'})
    before=tree(run);value=report.build_report(run)
    assert value['roster_status']=='partial_manifest' and value['status']=='incomplete'
    assert value['registered_rounds']==value['completed_rounds']==0
    op=value['operators'][0]
    assert op['final_selection']['status']=='pending' and op['source_split']=='test'
    assert not op['rounds'] and 'preflight' in op['pending_reason']
    assert tree(run)==before and all('proposal.json' not in e['path'] for e in value['evidence_index'])


def test_key_aggregation_uses_six_process_units_and_keeps_configurations_separate():
    selections=[dict(case_id=i,tiling_key=10 if i<3 else 11,kernel_entry='small' if i<3 else 'large',group_id='same') for i in (1,2,3)]
    rows=[]
    for i in (1,2,3):
        for config,offset in [('normal',.1),('swapped',-.2)]:
            logs=[offset+i*.01+j*.001 for j in range(6)]
            rows.append(dict(case_id=str(i),buffer_config=config,**report.analysis.effect(logs)))
    actual=report.aggregate_effects(dict(evidence_status='verified_complete',case_ids=[1,2,3],results=rows),selections)
    small=next(x for x in actual['per_tiling_key'] if x['tiling_key']==10 and x['buffer_config']=='normal')
    assert small['n_processes']==6 and small['df']==5 and small['case_count']==2
    assert small['log_effects']==pytest.approx([.115+j*.001 for j in range(6)])
    assert small['speedup']==pytest.approx(math.exp(sum(small['log_effects'])/6))
    assert len(actual['per_case'])==6 and len(actual['per_tiling_key'])==4
    bad=copy.deepcopy(rows);bad.pop()
    with pytest.raises(ValueError,match='coverage'):
        report.aggregate_effects(dict(evidence_status='verified_complete',case_ids=[1,2,3],results=bad),selections)
    bad=copy.deepcopy(rows);bad[0]['log_effects'].append(0)
    with pytest.raises(ValueError,match='six finite'):
        report.aggregate_effects(dict(evidence_status='verified_complete',case_ids=[1,2,3],results=bad),selections)


def fake_registered_failure(run,task,manifest,monkeypatch):
    directory=run/'train/ledger'
    for name in ('config.json','config.sha256.json','events.jsonl'):save(directory/name,{})
    cid='maximum001';parent=task/'candidates'/cid;source=parent/'source.tar';source.parent.mkdir(parents=True);source.write_bytes(b'changed source')
    proposal=save(parent/'proposal.json',dict(operator='maximum',candidate_id=cid,implementation_source_hash=ptr(source)['sha256'],
        optimization_stage='execution',dispatch_selections=[dict(case_id=1,tiling_key=10,kernel_entry='entry',group_id='generic')],
        architecture_profile_ref='sha256:'+'a'*64,parallel_plan_ref='sha256:'+'b'*64,dispatch_plan_ref='sha256:'+'c'*64))
    feedback={'status':'source_attempt_failed','source_hash':ptr(source)['sha256']}
    feedback_path=save(task/'feedback'/f'{cid}.json',feedback)
    result=save(parent/'stages/build/result.json',dict(status='failed',native_started=False))
    item=dict(candidate_id=cid,source_hash=ptr(source)['sha256'],source_parent=dict(candidate_id=None,source_hash=manifest['baseline']['sha256']),
        decision_basis=[],feedback_closed=True,current_round_started=True,inherited=False,observation_ids=['feedback1'],
        artifacts=dict(proposal=ptr(proposal),source=ptr(source)))
    state=dict(candidates={cid:item},observations={'feedback1':dict(close_feedback=True,report_ref=ptr(feedback_path)['sha256'],feedback=feedback)},
        stages={'build':dict(stage_id='build',candidate_id=cid,kind='build',plan={},attempts=[dict(outcome='build_failed',native_started=False,formal_samples=0,start_order=1,evidence={'result':ptr(result)})])})
    ledger=SimpleNamespace(config={'schema_version':report.campaign.FRESH_SCHEMA,'tasks':{'maximum':{'baseline_source_hash':manifest['baseline']['sha256']}}},
        state={'tasks':{'maximum':state}},verify=lambda:{'valid':True})
    monkeypatch.setattr(report.campaign,'Campaign',lambda path:ledger)
    return ledger,feedback_path


def test_only_registered_real_failed_attempt_counts_and_never_becomes_selected(tmp_path,monkeypatch):
    run,task,manifest=partial(tmp_path);fake_registered_failure(run,task,manifest,monkeypatch)
    save(task/'candidates/maximum002/proposal.draft.json',dict(candidate_id='maximum002'))
    before=tree(run);value=report.build_report(run);row=value['operators'][0]
    assert value['registered_rounds']==value['completed_rounds']==1
    assert row['status']=='failed' and row['rounds'][0]['status']=='failed'
    assert row['rounds'][0]['optimization_stage']=='execution' and not row['rounds'][0]['measurements']
    assert tree(run)==before
    save(run/'final-selection.json',dict(version='level2_final_selection_v1',selections={'maximum':dict(candidate_id='maximum001',source_hash=row['rounds'][0]['source_hash'],reason='cannot pick failed source',evidence=[])}))
    value=report.build_report(run)
    assert value['status']=='blocked' and value['operators'][0]['final_selection']['status']=='pending'


def test_changed_closed_feedback_blocks_report_without_rewriting_evidence(tmp_path,monkeypatch):
    run,task,manifest=partial(tmp_path);_,feedback=fake_registered_failure(run,task,manifest,monkeypatch)
    save(feedback,{'status':'measured'})
    before=tree(run);value=report.build_report(run)
    assert value['status']=='blocked' and value['completed_rounds']==0 and tree(run)==before


def test_explicit_baseline_selection_stays_pending_evaluation_without_formal_gates(tmp_path):
    run,task,manifest=partial(tmp_path)
    save(run/'final-selection.json',dict(version='level2_final_selection_v1',selections={'maximum':dict(candidate_id='baseline',source_hash=manifest['baseline']['sha256'],reason='Retain original while search incomplete',evidence=[])}))
    value=report.build_report(run);row=value['operators'][0]
    assert row['final_selection']['status']=='selected_baseline' and row['final_evaluation']=='pending'
    assert value['status']=='incomplete'
    assert 'maximum' in report.markdown(value)


def test_final_selection_rejects_draft_or_unmeasured_candidate():
    evidence=report.Evidence();selection=dict(candidate_id='not-registered',source_hash='sha256:'+'a'*64,reason='no observation',evidence=[])
    with pytest.raises(ValueError,match='registered source'):
        report.final_selection(selection,'sha256:'+'b'*64,[],evidence)


def test_measurements_require_real_completed_stage_and_replay_bound_sources(tmp_path,monkeypatch):
    from prepare_trace_pilot import create_source_snapshot
    from shared_context_build import source_hash
    run,task,manifest=partial(tmp_path)
    # Replace this synthetic baseline with the same deterministic archive format
    # used by registration, so source closure itself is exercised here.
    (task/'baseline-source.tar').unlink()
    for tree_root,text in [(task/'baseline','original'),(task/'candidates/maximum001/op','candidate')]:
        (tree_root/'op_host').mkdir(parents=True)
        (tree_root/'op_host/maximum.asc').write_text(text)
    create_source_snapshot(task/'baseline',task/'baseline-source.tar',root_label='maximum')
    parent=task/'candidates/maximum001'
    create_source_snapshot(parent/'op',parent/'source.tar',root_label='maximum001')
    baseline_hash=report.analysis.sha(task/'baseline-source.tar')
    item=dict(candidate_id='maximum001',source_hash=report.analysis.sha(parent/'source.tar'),
        source_parent=dict(candidate_id=None,source_hash=baseline_hash))
    frozen=save(parent/'plans/cohort.json',{'case_ids':[1], 'comparison_kind':'ab'})
    plan=dict(purpose='final',case_ids=[1],comparisons=report.campaign.comparisons(item,baseline_hash),
        cohorts=[dict(relation='direct_parent',control_candidate_id='baseline',plan=ptr(frozen))])
    output=parent/'stages/final/direct_parent'
    save(output.parent/'stage-plan.json',plan)
    stage_result=save(output.parent/'result.json',dict(status='passed',native_started=True))
    complete=save(output/'group-completion.json',dict(status='passed',completed_sessions=['real-session-'+str(i) for i in range(6)],sessions=[]))
    save(task/'stages/aa-initial/cohort/report.json',dict(calibration='bound'))
    raw=dict(operator='maximum',comparison_kind='ab',case_ids=[1],evidence_status='verified_complete',
        source_hashes={'A':source_hash(task/'baseline'),'B':source_hash(parent/'op')},
        results=[dict(case_id=1,buffer_config=config,**report.analysis.effect([.1]*6)) for config in ('normal','swapped')])
    save(output/'report.json',raw)
    state=dict(stages={'final':dict(candidate_id='maximum001',kind='timing',plan=plan,
        attempts=[dict(outcome='success',evidence={'result':ptr(stage_result)})])})
    proposal=dict(operator='maximum',dispatch_selections=[dict(case_id=1,tiling_key=8,kernel_entry='entry',group_id='vector')])
    calls=[]
    def analyze(paths,value,**kwargs):
        calls.append((paths,value));assert kwargs['calibration']=={'calibration':'bound'};return copy.deepcopy(raw)
    monkeypatch.setattr(report.analysis,'analyze_task_cohort',analyze)
    result=report.measured_stages(task,state,item,proposal,report.Evidence())
    assert len(calls)==1 and len(calls[0][0])==6
    assert result[0]['verification']=='raw_observations_replayed_read_only' and result[0]['per_tiling_key'][0]['n_processes']==6
    raw['source_hashes']['B']='0'*64;save(output/'report.json',raw)
    with pytest.raises(ValueError,match='registered sources'):
        report.measured_stages(task,state,item,proposal,report.Evidence())
    state['stages']['final']['attempts'][0]['outcome']='failed';calls.clear()
    assert report.measured_stages(task,state,item,proposal,report.Evidence())==[] and calls==[]


def test_open_native_stage_is_running_and_not_analyzed(tmp_path,monkeypatch):
    evidence=report.Evidence()
    state=dict(stages={'baseline-aa':dict(candidate_id=None,kind='control',plan={},attempts=[dict(outcome=None,evidence={})]),
        'candidate-search':dict(candidate_id='maximum001',kind='timing',plan={},attempts=[dict(outcome=None,evidence={})])})
    assert report.stage_rows(state,None,evidence)[0]['status']=='running'
    assert report.stage_rows(state,'maximum001',evidence)[0]['status']=='running'
    assert evidence.rows=={}
    run,task,manifest=partial(tmp_path)
    fake=SimpleNamespace(config=dict(schema_version=report.campaign.FRESH_SCHEMA,
        tasks={'maximum':dict(baseline_source_hash=manifest['baseline']['sha256'])}),
        state={'tasks':{'maximum':dict(candidates={},stages={'baseline-aa':state['stages']['baseline-aa']})}})
    monkeypatch.setattr(report.analysis,'analyze_task_cohort',lambda *a,**k:pytest.fail('open stage must not be reanalyzed'))
    value=report.task_report(run,'train','maximum',task,manifest,fake,None,evidence)
    assert value['status']=='incomplete' and value['issues']==[]
    assert value['baseline']['stages'][0]['status']=='running'


def closed_roster(tmp_path, monkeypatch, *, statuses=('measured',)*3, frozen=True,
                  finals=(1,2,3), selected='baseline', parent_chain=False):
    """Bind real file evidence; isolate reporting from the existing raw replayer."""
    run,task,manifest=partial(tmp_path)
    baseline=manifest['baseline']['sha256']
    state=dict(candidates={},observations={},stages={},frozen=frozen,new_source_attempts=3,new_rounds_started=3,
               selection=[],final_plans={},frozen_roster=None)
    config=dict(schema_version=report.campaign.FRESH_SCHEMA,policy=copy.deepcopy(report.campaign.FRESH_POLICY),
                tasks={'maximum':dict(baseline_source_hash=baseline,repeat_by_case={str(i):10 for i in range(1,21)})})
    order=0
    def stage(cid,kind,group,outcome='success',plan=None):
        nonlocal order
        order+=1;sid=(cid or 'baseline')+'-'+group
        parent=task/'candidates'/cid if cid else task
        result=save(parent/'stages'/group/'result.json',dict(status='passed' if outcome=='success' else 'failed',
                    kind=kind,native_started=kind!='build'))
        state['stages'][sid]=dict(stage_id=sid,candidate_id=cid,kind=kind,plan=copy.deepcopy(plan or {}),
            attempts=[dict(start_order=order,outcome=outcome,native_started=kind!='build',evidence={'result':ptr(result)})])
        return sid
    for kind in ('build','correctness','runtime'):stage(None,kind,kind)
    script=task/'agent/boundary_guard.py';script.parent.mkdir();script.write_text('# immutable boundary guard')
    measured={}
    for number,status in enumerate(statuses,1):
        cid=f'maximum{number:03d}';parent=task/'candidates'/cid
        source=parent/'source.tar';source.parent.mkdir(parents=True);source.write_bytes(cid.encode())
        previous=f'maximum{number-1:03d}'
        source_parent=(dict(candidate_id=previous,source_hash=state['candidates'][previous]['source_hash'])
                       if parent_chain and number>1 else dict(candidate_id=None,source_hash=baseline))
        proposal=save(parent/'proposal.json',dict(operator='maximum',candidate_id=cid,implementation_source_hash=ptr(source)['sha256'],
            optimization_stage='execution',dispatch_selections=[],architecture_profile_ref='sha256:'+'a'*64,
            parallel_plan_ref='sha256:'+'b'*64,dispatch_plan_ref='sha256:'+'c'*64))
        item=dict(candidate_id=cid,source_hash=ptr(source)['sha256'],source_parent=source_parent,probes=[],
            decision_basis=[],feedback_closed=True,current_round_started=True,inherited=False,observation_ids=[cid+'-observation'],
            artifacts=dict(proposal=ptr(proposal),source=ptr(source)))
        state['candidates'][cid]=item
        guard_ref=None
        if status=='measured':
            for kind in ('build','correctness','runtime'):stage(cid,kind,kind)
            binary=parent/'build/standalone';binary.parent.mkdir();binary.write_bytes(b'executable')
            save(parent/'build/build_manifest.json',dict(standalone=ptr(binary)))
            plan_path=save(parent/'dispatch_plan.json',dict(source=cid))
            request=save(parent/'boundary-validation/request.json',dict(operator='maximum',candidate=cid,
                script=ptr(script),binary=ptr(binary),dispatch_plan=ptr(plan_path)))
            guard=save(parent/'boundary-validation/completion.json',dict(operator='maximum',candidate=cid,status='passed',
                request=ptr(request),error=None,verification_error=None,
                cases=[dict(expected_process_passed=True,dispatch_log_passed=True)]))
            guard_ref=ptr(guard)
            sid=stage(cid,'timing','search',plan={'purpose':'search'})
            measured[cid]=[dict(stage_id=sid,purpose='search',relation='direct_parent',full_twenty_case_suite=False)]
            state['selection'].append(cid)
            plan=report.campaign.timing_plan(item,baseline,purpose='final',manifest_ref='sha256:'+'d'*64,
                policy=config['policy'],repeat_by_case=config['tasks']['maximum']['repeat_by_case'])
            state['final_plans'][cid]=plan
            if number in finals:
                sid=stage(cid,'timing','final',plan=plan)
                relations=['direct_parent']+(['original_baseline'] if source_parent['source_hash']!=baseline else [])
                measured[cid]+=[dict(stage_id=sid,purpose='final',relation=r,full_twenty_case_suite=True) for r in relations]
                item['feedback_closed']=False  # Final timing legitimately reopens source feedback.
        else:
            stage(cid,'build','build','build_failed');measured[cid]=[]
        feedback=dict(operator='maximum',candidate_id=cid,status=status,source_hash=item['source_hash'],semantic_guards=guard_ref)
        # Recovery names are immutable and need not be exactly <candidate>.json.
        path=save(task/'feedback'/f'{cid}-observation.json',feedback)
        state['observations'][cid+'-observation']=dict(close_feedback=True,report_ref=ptr(path)['sha256'],feedback=feedback)
    roster=[{k:v for k,v in item.items() if k not in {'feedback_closed','observation_ids','current_round_started'}}
            for item in state['candidates'].values()]
    state['frozen_roster']={'candidates':copy.deepcopy(roster),'sha256':report.campaign.digest(roster)}
    ledger=SimpleNamespace(config=config,state={'tasks':{'maximum':state}},verify=lambda:{'valid':True})
    for name in ('config.json','config.sha256.json','events.jsonl'):save(run/'train/ledger'/name,{})
    save(run/'campaign-manifest.json',dict(version=report.campaign.FRESH_SCHEMA,operators={'train':['maximum']}))
    if selected:
        digest=baseline if selected=='baseline' else state['candidates'][selected]['source_hash']
        save(run/'final-selection.json',dict(version='level2_final_selection_v1',selections={
            'maximum':dict(candidate_id=selected,source_hash=digest,reason='Explicit tested source selection',evidence=[])}))
    monkeypatch.setattr(report.campaign,'Campaign',lambda path:ledger)
    monkeypatch.setattr(report,'measured_stages',lambda task,state,item,proposal,evidence:copy.deepcopy(measured[item['candidate_id']]))
    return run,task,ledger,measured,stage


def test_closed_infrastructure_observation_is_not_a_completed_round(tmp_path,monkeypatch):
    run,task,ledger,_,_=closed_roster(tmp_path,monkeypatch,statuses=('source_attempt_failed','source_attempt_failed','infrastructure_blocked'),frozen=False,finals=())
    before=tree(run);value=report.build_report(run)
    assert value['completed_rounds']==2 and value['status']=='blocked'
    assert value['operators'][0]['rounds'][2]['status']=='blocked' and tree(run)==before


def test_new_open_infrastructure_feedback_cannot_hide_behind_old_closed_feedback(tmp_path,monkeypatch):
    run,task,ledger,_,_=closed_roster(tmp_path,monkeypatch,statuses=('source_attempt_failed',)*3,frozen=False,finals=())
    state=ledger.state['tasks']['maximum'];item=state['candidates']['maximum003']
    feedback=dict(status='infrastructure_blocked',source_hash=item['source_hash'])
    path=save(task/'feedback/maximum003-blocked-new.json',feedback)
    state['observations']['new-blocked']=dict(close_feedback=False,report_ref=ptr(path)['sha256'],feedback=feedback)
    item['observation_ids'].append('new-blocked');item['feedback_closed']=False
    result=report.build_report(run)
    assert result['completed_rounds']==2 and result['operators'][0]['rounds'][2]['round_feedback_closed'] is False


def test_baseline_selection_cannot_bypass_ledger_freeze(tmp_path,monkeypatch):
    run,_,_,_,_=closed_roster(tmp_path,monkeypatch,frozen=False,finals=())
    value=report.build_report(run);row=value['operators'][0]
    assert row['completed_rounds']==3 and row['baseline']['current_safe'] is True
    assert row['final_evaluation']=='pending' and value['status']!='complete'


@pytest.mark.parametrize('selected',['baseline','maximum001'])
def test_nonwinner_requires_its_own_full_final_comparison(tmp_path,monkeypatch,selected):
    run,_,_,_,_=closed_roster(tmp_path,monkeypatch,finals=(1,2),selected=selected)
    value=report.build_report(run);row=value['operators'][0]
    assert row['completed_rounds']==3 and row['final_evaluation']=='pending' and value['status']!='complete'
    assert row['evaluation_roster']['candidates'][-1]==dict(candidate_id='maximum003',status='pending')


def test_frozen_roster_cannot_omit_a_safe_nonwinner(tmp_path,monkeypatch):
    run,_,ledger,_,_=closed_roster(tmp_path,monkeypatch,finals=(1,),selected='maximum001')
    state=ledger.state['tasks']['maximum'];state['selection']=['maximum001']
    state['final_plans']={'maximum001':state['final_plans']['maximum001']}
    value=report.build_report(run)
    assert value['status']=='blocked' and 'every currently qualified' in value['operators'][0]['issues'][0]


def test_all_qualified_parent_and_original_relations_are_required(tmp_path,monkeypatch):
    run,_,_,measured,_=closed_roster(tmp_path,monkeypatch,parent_chain=True)
    measured['maximum003']=[r for r in measured['maximum003'] if r['relation']!='original_baseline']
    value=report.build_report(run)
    assert value['status']=='blocked' and 'parent/original' in value['operators'][0]['issues'][0]


def test_three_real_failures_with_empty_frozen_roster_can_close_to_safe_baseline(tmp_path,monkeypatch):
    run,_,_,_,_=closed_roster(tmp_path,monkeypatch,statuses=('source_attempt_failed',)*3,finals=())
    before=tree(run);value=report.build_report(run);row=value['operators'][0]
    assert value['status']=='complete' and row['completed_rounds']==3
    assert row['evaluation_roster']['candidate_ids']==[] and row['final_selection']['candidate_id']=='baseline'
    assert row['final_selection']['current_safe'] is True and tree(run)==before


@pytest.mark.parametrize('kind',['build','correctness','runtime'])
def test_historical_baseline_success_does_not_override_latest_safety_failure(tmp_path,monkeypatch,kind):
    run,_,_,_,stage=closed_roster(tmp_path,monkeypatch,statuses=('source_attempt_failed',)*3,finals=())
    stage(None,kind,'new-failed-'+kind,'failed')
    value=report.build_report(run);row=value['operators'][0]
    assert row['baseline']['current_safe'] is False and row['final_selection']['current_safe'] is False
    assert value['status']!='complete'


def test_complete_full_roster_can_retain_baseline_after_all_candidates_measured(tmp_path,monkeypatch):
    run,_,_,_,_=closed_roster(tmp_path,monkeypatch,parent_chain=True)
    value=report.build_report(run)
    assert value['status']=='complete' and value['operators'][0]['final_evaluation']=='complete'
    assert value['formal_admission']=='not_evaluated' and value['episode_ref'] is None


def test_final_evaluations_without_explicit_source_selection_remain_unfinished(tmp_path,monkeypatch):
    run,_,_,_,_=closed_roster(tmp_path,monkeypatch,selected=None)
    value=report.build_report(run)
    assert value['operators'][0]['final_evaluation']=='complete'
    assert value['operators'][0]['final_selection']['status']=='pending' and value['status']!='complete'

"""CPU orchestration joins; leaf doubles make no hardware or acceptance claim."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import ContractError
from aprof_runtime import measurement_admission as shared
from aprof_runtime import measurement_entry, task_window_measurement_admission
import task_rule_continuation_admission as admission


@pytest.fixture
def prefix(tmp_path, monkeypatch):
    def make(defect=None):
        root = tmp_path/'exp'; root.mkdir()
        local = LocalEvidence(root/'records')
        def put(value):
            return local.register_json(value)
        def pointer(reference):
            return dict(path=str(local.verify_artifact(reference)), sha256=reference)
        sources = {role:put({'schema_version':'1.0.0','files':{'kernel.asc':put({'role':role})}})
                   for role in admission.ROLES}
        expected = dict(operator='exp', run_id='original-exp', candidate_id='original-candidate',
                        source_hashes=sources)
        source_archive_ref = put({'CPU':'original source archive'})
        campaign_ref = put({'CPU':'original closed campaign','budget_seconds':3600})
        job = dict(CPU='original job',timeout_seconds=3600)
        job_ref = put(job)
        anchor_ref = put(dict(**expected, budget_seconds=3600, job_ref=job_ref,
                              campaign_ref=campaign_ref,created_at=90))
        launch = dict(schema_version=1,anchor_ref=anchor_ref,job_ref=job_ref,started_at=99,
                      monotonic_deadline=3699)
        launch_ref = put(launch)
        review_ref = put({'CPU':'original independent review'})
        review_pointer = pointer(review_ref)
        mechanical_ref = put({'CPU':'mechanical source proof'})
        binary_ref = put({'CPU':'the single original binary'})
        input_path = str(root/'original-input.bin'); input_ref = put({'CPU':'original input'})
        input_inventory_ref = put({input_path:input_ref})
        build = dict(source_dir=str(root/'assembly/source'), binary=str(root/'assembly/build/exp'))
        config = dict(expected_case_ids=list(range(1,21)), cases=[dict(case_id=i) for i in range(1,21)], build=build)
        if defect == 'coverage': config['cases'].pop()
        config_ref = put(config)
        protocol_config_ref = config_ref
        if defect in ('config_pretty', 'protocol_config_changed'):
            protocol_config = copy.deepcopy(config)
            if defect == 'protocol_config_changed': protocol_config['cases'][0]['case_id'] = 99
            protocol_config_path = root/'protocol-task-config.json'
            protocol_config_path.write_text(json.dumps(protocol_config, indent=2) + '\n')
            protocol_config_ref = local.register_artifact(protocol_config_path)
        screen_build = dict(build)
        if defect == 'screen_build_swap': screen_build['binary'] += '-other'
        screen_config_ref = put({'build':screen_build})
        registration = {'identity':{'build':{'binary_ref':binary_ref}, 'cases':{
            '1':{'prepared_files':{input_path:input_ref}}}}}
        if defect == 'input_swap': registration['identity']['cases']['1']['prepared_files'][input_path] = put({'CPU':'different input'})
        registration_ref = put(registration)
        receipt_ref = put({'CPU':'original Task receipt'})
        measurement_report_ref = put({'CPU':'original Task report'})
        completion = dict(**expected, session_id='original-session', measurement_report_ref=measurement_report_ref,
                          started_at=142, finished_at=179)
        if defect == 'task_source_swap':
            completion['source_hashes'] = dict(sources, candidate=put({'schema_version':'1.0.0','files':{}}))
        if defect == 'task_window': completion['finished_at'] = 181
        completion_ref = put(completion)
        attempt = dict(source_review_hash=mechanical_ref, route={'mode':'exploration','anchor_ref':anchor_ref},
                       independent_review=review_pointer)
        if defect == 'changed_review': attempt['independent_review'] = pointer(put({'CPU':'substituted review'}))
        attempt_ref = put(attempt)
        built = dict(status='passed', binary={'sha256':binary_ref}, source_review_hash=mechanical_ref,
                     attempt_ref=pointer(attempt_ref))
        if defect == 'build_swap': built['binary']['sha256'] = put({'CPU':'second binary'})
        build_ref = put(built)
        correct_ref = put(dict(kind='task_rule_correctness',build_receipt_ref=build_ref))
        boundary_build_ref = put(dict(built, CPU='another build')) if defect == 'boundary_build_swap' else build_ref
        boundary_ref = put(dict(kind='task_rule_boundary',build_receipt_ref=boundary_build_ref))
        screen_ref = put({'CPU':'original screen report'})
        protocol = dict(**expected, task_config_ref=protocol_config_ref,
            binary_hashes={role:binary_ref for role in admission.ROLES},
            input_inventory_ref=input_inventory_ref, source_review_ref=mechanical_ref)
        if defect in ('protocol_launch','protocol_index_contradiction'):
            protocol['dispatcher_launch_ref'] = launch_ref
        protocol_ref = put(protocol)
        stage_evidence = dict(correctness=[correct_ref],boundary=[boundary_ref],screen=[screen_ref],
            task_measurement=[completion_ref,receipt_ref,config_ref,registration_ref,measurement_report_ref])
        if defect == 'missing_task_stage_binding': stage_evidence['task_measurement'].remove(receipt_ref)
        windows = dict(correctness=[110,120], boundary=[121,130],screen=[131,140],task_measurement=[141,180])
        events = []
        for stage, (start, finish) in windows.items():
            events.append(put(dict(stage=stage,state='started',at=start)))
            events.append(put(dict(stage=stage,state='completed',at=finish,exit_status=0,
                                   evidence_refs=stage_evidence[stage])))
        events.append(put(dict(stage='profile',state='started',at=181)))
        report = dict(**expected,protocol_ref=protocol_ref,attempt_roster_ref=put({'events':events}),
            qualification_registration_ref=put({'CPU':'original qualification'}),
            correctness_report_ref=correct_ref,boundary_report_ref=boundary_ref,screen_report_ref=screen_ref,
            measurement_admission_ref=completion_ref,stage_evidence=stage_evidence)
        if defect == 'report_source_swap': report['source_hashes'] = dict(sources,candidate=input_ref)
        report_ref = put(report)
        child_ref = put(dict(status='failed',actual_builds=1,child_report_ref=report_ref))
        finish = 3700 if defect == 'past_original_deadline' else 200
        timestamp = lambda v:datetime.fromtimestamp(v,timezone.utc).isoformat()
        execution_ref = put(dict(started_at=timestamp(100),finished_at=timestamp(finish),duration_seconds=100,
                                 job=job))
        index = {'artifacts':{launch_ref:str(root/'dispatcher-launch.json')}}
        archive = {'source_archive_refs':{'exp':[source_archive_ref]},'files':{}}
        if defect in ('archive_launch','archive_launch_hash','archive_launch_size','archive_launch_missing','protocol_launch'):
            index['artifacts'] = {}
            if defect != 'archive_launch_missing':
                retained = dict(**pointer(launch_ref),bytes=local.verify_artifact(launch_ref).stat().st_size)
                if defect == 'archive_launch_hash': retained['sha256'] = receipt_ref
                if defect == 'archive_launch_size': retained['bytes'] += 1
                archive['files'][str(root/'dispatcher-launch.json')] = retained
        if defect == 'protocol_index_contradiction':
            index['artifacts'] = {put(dict(launch,started_at=98)):str(root/'dispatcher-launch.json')}
        index_ref = put(index)
        archive_ref = put(archive)
        snapshot_ref = put({'CPU':'trusted original producer snapshot'})
        trusted = dict(archive_inventory_ref=archive_ref,producer_snapshot_ref=snapshot_ref)
        selected = dict(operator='exp',status='failed',execution_status='failed',exit_code=2,components=None,
            partial_roster=dict(events=9,completed_stages=list(admission.PREFIX),active_stage='profile'),
            controller_failure=dict(type='JSONDecodeError',message='Extra data: line 3 column 1 (char 228)'),
            anchor_ref=anchor_ref,controller_result_ref=child_ref,execution_ref=execution_ref,root=str(root))
        if defect == 'partial_shape': selected['partial_roster']['events'] = 8
        if defect == 'upgraded_parent': selected.update(status='completed_child',exit_code=0)
        campaign = dict(valid=True,complete=True,trials=[selected,dict(operator='sigmoid',status='not_run')])
        trials = dict(exp=dict(reader=local,index_ref=index_ref,source_archive_ref=source_archive_ref),
            sigmoid=dict(reader=local,index_ref=put({'CPU':'original sigmoid index'}),
                         not_run_ref=put({'CPU':'original sigmoid closure'})))
        calls = []
        def campaign_leaf(reader, reference, *, trials):
            calls.append(('campaign',reader,reference,dict(trials=trials)))
            return campaign
        def correctness_leaf(reader, reference, **kwargs):
            calls.append(('correctness',reader,reference,kwargs))
            if defect == 'correctness_leaf': raise ValueError('correctness leaf rejected')
            return dict(passed=True,case_count=20 if reference==correct_ref else 42)
        def screen_leaf(reader, reference, **kwargs):
            calls.append(('screen',reader,reference,kwargs))
            if defect == 'screen_leaf': raise ValueError('screen leaf rejected')
            return dict(valid=True,config_ref=screen_config_ref)
        def task_leaf(reader, reference, **kwargs):
            calls.append(('task',reader,reference,kwargs))
            if defect == 'task_leaf': raise ValueError('task leaf rejected')
            return dict(valid=True,completion_ref=completion_ref,config_ref=config_ref,
                        registration_ref=registration_ref,receipt_ref=receipt_ref)
        def review_leaf(reader, **kwargs):
            calls.append(('review',reader,None,kwargs))
            if defect == 'review_leaf': raise ValueError('review leaf rejected')
            return dict(accepted=True,source_review_ref=review_pointer)
        for name, function in [('replay_task_rule_campaign',campaign_leaf),
            ('verify_archived_rule_correctness',correctness_leaf),('verify_task_screen',screen_leaf),
            ('replay_current_measurement_admission',task_leaf),('replay_retained_source_review',review_leaf)]:
            monkeypatch.setattr(admission,name,function)
        def replay():
            return admission._replay_reused_prefix(local,campaign_ref=campaign_ref,trials=trials,
                                                   operator='exp',trusted_review_refs=trusted)
        return SimpleNamespace(**locals())
    return make


def test_original_references_windows_and_failed_parent_survive_leaf_orchestration(prefix):
    f=prefix(); original=copy.deepcopy(f.campaign); result=f.replay()
    assert f.campaign==original and result['parent_status']=='failed'
    assert result['valid'] and not result['admission_authority'] and not result['eligible_for_publication']
    assert result['original_duration_seconds']==100 and result['original_wall_deadline']==3699
    assert result['original_deadline_monotonic']==3699 and result['stage_windows']==f.windows
    assert result['original_profile_window']==[181,200]
    assert [x[0] for x in f.calls]==['campaign','correctness','correctness','screen','task','review']
    assert f.calls[0][1:]==(f.local,f.campaign_ref,dict(trials=f.trials))
    for row, stage, reference in zip(f.calls[1:4],admission.PREFIX[:3],
                                   [f.correct_ref,f.boundary_ref,f.screen_ref],strict=True):
        assert row[2]==reference
        assert row[3]==dict(protocol_ref=f.protocol_ref,expected=f.expected,window=f.windows[stage],
                            source_archive_ref=f.source_archive_ref)
    assert f.calls[4][2:]==(f.completion_ref,dict(expected={key:f.completion[key] for key in
        ('operator','run_id','candidate_id','session_id','source_hashes','measurement_report_ref')}))
    assert f.calls[5][3]==dict(anchor_ref=f.anchor_ref,source_review_ref=f.review_ref,**f.trusted)


def test_task_config_serializer_preserves_distinct_refs_and_original_bytes(prefix):
    f = prefix('config_pretty')
    references = (f.protocol_config_ref, f.config_ref)
    before = {ref: f.local.verify_artifact(ref).read_bytes() for ref in references}
    assert references[0] != references[1]
    assert json.loads(before[references[0]]) == json.loads(before[references[1]])
    result = f.replay()
    assert result['protocol_task_config_ref'] == references[0]
    assert result['collected_task_config_ref'] == references[1]
    assert result['parent_status'] == 'failed' and not result['admission_authority']
    assert not result['eligible_for_publication']
    assert {ref: f.local.verify_artifact(ref).read_bytes() for ref in references} == before


def test_task_config_serializer_rejects_changed_protocol_payload(prefix):
    f = prefix('protocol_config_changed')
    assert f.protocol_config_ref != f.config_ref
    assert json.loads(f.local.verify_artifact(f.protocol_config_ref).read_bytes()) != f.config
    with pytest.raises(ValueError, match='original Task config/completion differs'):
        f.replay()


@pytest.mark.parametrize('defect,reason', [
    ('partial_shape','stopped PMU'),('upgraded_parent','stopped PMU'),
    ('report_source_swap','source_hashes'),('task_source_swap','canonical source'),
    ('missing_task_stage_binding','registered stage'),('input_swap','prepared inputs'),
    ('build_swap','original build'),('screen_build_swap','original single build'),
    ('boundary_build_swap','one build'),('changed_review','review did not replay'),
    ('task_window','registered stage'),('past_original_deadline','unchanged budget'),
    ('coverage','full coverage'),('correctness_leaf','leaf rejected'),
    ('screen_leaf','leaf rejected'),('task_leaf','leaf rejected'),('review_leaf','leaf rejected'),
])
def test_prefix_join_rejects_changed_evidence_or_rejected_leaf(prefix,defect,reason):
    f=prefix(defect)
    with pytest.raises(ValueError,match=reason):f.replay()


@pytest.mark.parametrize('source',['archive_launch','protocol_launch'])
def test_original_launch_replays_from_bound_protocol_or_trusted_archive(prefix,source):
    f=prefix(source); before=copy.deepcopy(f.index)
    result=f.replay()
    assert result['original_launch_ref']==f.launch_ref and result['parent_status']=='failed'
    assert f.index==before and f.index['artifacts']=={}
    assert not result['eligible_for_publication']


@pytest.mark.parametrize('defect,reason',[
    ('archive_launch_hash','external file changed'),('archive_launch_size','launch size'),
    ('archive_launch_missing','missing from trusted archive'),
    ('protocol_index_contradiction','disagree on dispatcher launch'),
])
def test_retained_original_launch_must_keep_its_hash_size_and_binding(prefix,defect,reason):
    f=prefix(defect)
    with pytest.raises(ValueError,match=reason):f.replay()


@pytest.fixture
def producer_archive(tmp_path,monkeypatch):
    def make(defect=None):
        local=LocalEvidence(tmp_path/'producer-records')
        release=admission.selected_runtime();root=tmp_path/'original-exp'
        names=admission.PRODUCER_FILES
        assert len(names)==23
        files={};cohort={}
        for i,name in enumerate(names):
            path=tmp_path/('retained-producer-'+str(i)+'.py')
            path.write_text('# CPU retained producer '+name+'\n')
            ref=local.register_artifact(path);cohort[name]=ref
            files[str(release/name)]=dict(path=str(path),sha256=ref,bytes=path.stat().st_size)
        frozen={path:item['sha256'] for path,item in files.items()}
        trusted_hash=admission.content_hash(cohort)
        monkeypatch.setattr(admission,'KNOWN_PRODUCER_COHORT',trusted_hash)
        first,second=names[:2];logical=str(release/first)
        if defect=='unknown_hash':monkeypatch.setattr(admission,'KNOWN_PRODUCER_COHORT','sha256:'+'0'*64)
        if defect=='mixed_cohort':files[logical]=dict(files[str(release/second)])
        if defect=='freeze_mismatch':frozen[logical]=cohort[second]
        if defect=='size':files[logical]['bytes']+=1
        if defect=='path':files[logical]['path']=files[str(release/second)]['path']
        frozen_ref=local.register_json(frozen)
        plan_ref=local.register_json(dict(directory=str(root),release=str(release),frozen_files_ref=frozen_ref))
        anchor_ref=local.register_json(dict(operator='exp',controller_plan_ref=plan_ref))
        snapshot=dict(kind='frozen_task_producer_source_archive',owner='trace_collection',cost_scope='post_task',
            source_anchors={'exp':dict(path=str(root/'anchor.json'),sha256=anchor_ref)},
            frozen_files_refs={'exp':frozen_ref},files=files)
        snapshot_ref=local.register_json(snapshot)
        archive=dict(owner='trace_collection',cost_scope='post_task',
            producer_index_ref=dict(path=str(local.verify_artifact(snapshot_ref)),sha256=snapshot_ref),
            files=copy.deepcopy(files))
        if defect=='archive_mismatch':archive['files'][logical]['bytes']+=1
        if defect=='anchor_path':
            snapshot['source_anchors']['exp']['path']=str(root/'different-anchor.json')
            snapshot_ref=local.register_json(snapshot)
            archive['producer_index_ref']=dict(path=str(local.verify_artifact(snapshot_ref)),sha256=snapshot_ref)
        trusted=dict(archive_inventory_ref=local.register_json(archive),producer_snapshot_ref=snapshot_ref)
        def scope():return admission.retained_producer_scope(local,anchor_ref=anchor_ref,trusted_review_refs=trusted)
        return SimpleNamespace(**locals())
    return make


def producer_identity_boundary(f):
    name='runtime/src/aprof_runtime/episodes.py'
    registration=dict(producer_files={name:f.cohort[name]},identity={'source_hashes':{'baseline':'old','candidate':'old'}})
    return shared._registered_identity(f.local,{'source_hashes':{}},{},registration,producer_files=(name,))


def test_complete_retained_cohort_scope_changes_only_producer_resolution(producer_archive):
    f=producer_archive()
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None
    with pytest.raises(ContractError,match='untrusted producer bytes'):producer_identity_boundary(f)
    with f.scope():
        resolver=shared._HISTORICAL_PRODUCER_RESOLVER.get()
        name='runtime/src/aprof_runtime/episodes.py'
        assert resolver(f.release/name,f.cohort[name])==f.local.verify_artifact(f.cohort[name])
        with pytest.raises(ValueError,match='unapproved historical producer'):
            resolver(f.release/name,f.cohort[f.first])
        with pytest.raises(ValueError,match='unapproved historical producer'):
            resolver(f.release/'unknown.py',f.cohort[name])
        # Reaching the next real identity guard proves only producer resolution.
        with pytest.raises(ContractError,match='source identity differs'):producer_identity_boundary(f)
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None
    with pytest.raises(ContractError,match='untrusted producer bytes'):producer_identity_boundary(f)


@pytest.mark.parametrize('defect,reason',[
    ('unknown_hash','unknown historical producer cohort'),('mixed_cohort','unknown historical producer cohort'),
    ('freeze_mismatch','freeze/snapshot/archive'),('archive_mismatch','freeze/snapshot/archive'),
    ('size','producer size'),('path','external file changed'),('anchor_path','original Exp freeze'),
])
def test_retained_cohort_rejects_unknown_or_mixed_or_unbound_bytes(producer_archive,defect,reason):
    f=producer_archive(defect)
    with pytest.raises(ValueError,match=reason):f.scope()
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None


def test_scoped_resolver_still_hashes_bytes_and_restores_after_exception(producer_archive):
    f=producer_archive()
    with pytest.raises(RuntimeError,match='after replay'):
        with f.scope():
            approved=shared._HISTORICAL_PRODUCER_RESOLVER.get()
            with shared.historical_producer_scope(lambda *args:f.release/'runtime/src/aprof_runtime/episodes.py'):
                with pytest.raises(ContractError,match='untrusted producer bytes'):producer_identity_boundary(f)
            assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is approved
            raise RuntimeError('after replay')
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None


@pytest.mark.parametrize('module,current,historical',[
    (measurement_entry,'replay_current_measurement_admission','replay_historical_current_measurement_admission'),
    (task_window_measurement_admission,'replay_task_window_measurement_admission','replay_historical_task_window_measurement_admission'),
])
@pytest.mark.parametrize('reject',[False,True])
def test_historical_wrappers_keep_existing_calls_and_restore_scope(monkeypatch,module,current,historical,reject):
    reader=object();reference='sha256:'+'a'*64;expected={'original':'expected'};calls=[];marker=object()
    resolver=lambda path,ref:path
    def replay(actual,ref,*,expected):
        calls.append((actual,ref,expected))
        assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is resolver
        if reject:raise ValueError('existing verifier rejected')
        return marker
    monkeypatch.setattr(module,current,replay)
    if reject:
        with pytest.raises(ValueError,match='existing verifier rejected'):
            getattr(module,historical)(reader,reference,expected=expected,producer_resolver=resolver)
    else:assert getattr(module,historical)(reader,reference,expected=expected,producer_resolver=resolver) is marker
    assert calls==[(reader,reference,expected)]
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None


def test_public_prefix_authenticates_factory_before_private_replay(producer_archive,monkeypatch):
    f=producer_archive();campaign_ref=f.local.register_json({'CPU':'campaign'})
    trials={'exp':{'reader':f.local,'dispatcher_result_ref':f.local.register_json({'anchor_ref':f.anchor_ref})}}
    calls=[]
    def replay(reader,**kwargs):
        calls.append((reader,kwargs))
        assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is not None
        raise ValueError('private replay rejected')
    monkeypatch.setattr(admission,'_replay_reused_prefix',replay)
    with pytest.raises(ValueError,match='private replay rejected'):
        admission.replay_reused_prefix(f.local,campaign_ref=campaign_ref,trials=trials,trusted_review_refs=f.trusted)
    assert calls==[(f.local,dict(campaign_ref=campaign_ref,trials=trials,operator='exp',trusted_review_refs=f.trusted))]
    assert shared._HISTORICAL_PRODUCER_RESOLVER.get() is None

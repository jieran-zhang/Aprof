"""Small files, real immutable campaign ledger; native analysis is an explicit fake."""
from aprof_layout import skill_lib
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
ROOT=Path(os.environ.get('APROF_TEST_REPO',Path(__file__).resolve().parents[2]))
sys.path[:0]=[str(ROOT/'scaffolding/collection/scripts'),str(skill_lib() / 'runtime/src'),str(ROOT/'scaffolding/tests')]
from test_level2_finalize import Fixture
import level2_finalize as final
import msprof_exploration_campaign as campaign
from msprof_exploration_execute import load, pointer
from run_msprof_exploration_stage import verify_source_snapshot
from shared_context_build import source_hash
SPEC=importlib.util.spec_from_file_location('prospective_final_attestor',Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts/level2_final_report_attestation.py')
a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(a.canonical(value))


class FakeRuntime:
    campaign=campaign
    storage_profile={'version':'closed_evidence_facade_epoch_v1',
                     'reviewed_patch_sha256':a.REVIEWED_STORAGE_PATCH,
                     'expected_producer_sha256':dict(a.STORAGE_PRODUCERS)}
    def __init__(self):self.expected={};self.calls=[];self.host_calls=0;self.rechecks=0
    def ledger(self,path):return campaign.Campaign(path)
    def read(self,path):return Path(path).read_bytes()
    def fingerprint(self,path):return a.digest(Path(path).read_bytes())
    def source(self,archive,tree):verify_source_snapshot(archive,tree);return source_hash(tree)
    def producer_paths(self):return [Path(a.__file__)]
    def historical_producer(self,*args):raise ValueError('unattested historical producer')
    @contextmanager
    def reader_session(self):yield
    @contextmanager
    def host_lock(self):self.host_calls+=1;yield
    def reverify(self):self.rechecks+=1
    def analyze(self,directories,plan,calibration):
        self.calls.append(tuple(directories));return deepcopy(self.expected[directories[0]])
    def compare(self,saved,actual,path):
        assert saved==actual,'saved report differs from full replay'
        return {'comparison':{'matched':True,'comparison':'exact'},'historical_producers':[]}


class Small:
    def __init__(self,tmp_path,monkeypatch,*,chain=False,failed=(1,)):
        self.fixture=Fixture(tmp_path,monkeypatch,failed=failed,parent_chain=chain)
        self.run=tmp_path;self.task=self.fixture.task;self.runtime=FakeRuntime()
        self.cal=self.task/'stages/aa-initial/cohort'
        h=source_hash(self.task/'baseline')
        self.make_report(self.cal,{'case_ids':a.ALL_CASES,'comparison_kind':'aa',
                                  'schedule':[{'name':f'p{i}'} for i in range(6)]},{'A':h,'B':h})
        result=final.finalize(tmp_path,'maximum')
        assert result['status'] in ('final_evaluations_completed','closed_no_qualified_candidates'),result
        # Fill the tiny finalizer fixture with real report metadata shape. The
        # analyzer's independent retained expected values are captured here.
        for candidate in result['comparisons']:
            parent=self.task/'candidates'/candidate['candidate_id']
            plan=load(parent/'stages/final/stage-plan.json')
            for row in plan['cohorts']:
                directory=parent/'stages/final'/row['relation'];p=load(directory/'plan.json')
                build=load(p['identity_bindings']['role_build']['path'])
                self.make_report(directory,p,{r:build['roles'][r]['source_sha256'] for r in 'AB'})
            for row in candidate['comparisons']:
                row['report']=pointer(parent/'stages/final'/row['relation']/'report.json')
        save(self.task/'finalization/completion.json',result)
        manifest=load(self.task/'manifest.json');manifest.update(operator='maximum',task_dir=str(self.task));save(self.task/'manifest.json',manifest)
        (self.task/'.recorder.lock').touch();(self.task/'events.jsonl').write_bytes(b'')
        producer=pointer(a.__file__);snapshot=self.run/'bootstrap/source-cas'/producer['sha256'][7:]
        snapshot.parent.mkdir(parents=True);snapshot.write_bytes(Path(a.__file__).read_bytes())
        self.engineering=self.run/'bootstrap/frozen-engineering-attestor.json'
        save(self.run/'campaign-manifest.json',{'run_id':self.run.name})
        save(self.engineering,{'version':'level2_frozen_engineering_v1','campaign_manifest':pointer(self.run/'campaign-manifest.json'),'files':[{**producer,'snapshot':str(snapshot)}],'task_manifests':[pointer(self.task/'manifest.json')]})
        self.request_sha=pointer(self.task/'finalization/request.json')['sha256']
        self.before_ledger=(self.run/'train/ledger/events.jsonl').read_bytes()

    def make_report(self,directory,plan,hashes):
        save(directory/'plan.json',plan)
        sessions=[]
        for row in plan['schedule']:
            p=directory/row['name'];p.mkdir(exist_ok=True,parents=True);output=p/'tiny-output.bin';output.write_bytes(b'fixed-output')
            sessions.append({'directory':str(p),'artifacts':{str(output):pointer(output)['sha256']}})
        save(directory/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[s['directory'] for s in sessions]})
        report={'case_ids':list(map(str,a.ALL_CASES)),'comparison_kind':plan['comparison_kind'],
                'source_hashes':hashes,'evidence_status':'verified_complete','sessions':sessions,
                'results':[{'case_id':str(c),'buffer_config':b,'qualified_performance_eligible':False,
                            'calibration_status':'invalidated','speedup':.8} for c in a.ALL_CASES for b in ('normal','swapped')]}
        save(directory/'report.json',report);self.runtime.expected[sessions[0]['directory']]=deepcopy(report)

    def inspect(self):return a.audit(self.runtime,self.run,'maximum',self.request_sha,self.engineering,full=False)
    def apply(self):return a.attest(self.runtime,self.run,'maximum',self.request_sha,self.engineering,writers_closed=True)
    def request(self):return load(self.task/'finalization/request.json')


@pytest.fixture
def small(tmp_path,monkeypatch):return Small(tmp_path,monkeypatch)


def test_metadata_inspect_never_replays_or_publishes(small):
    before=list(small.task.glob('finalization/report-attestation-*'))
    value=small.inspect()
    assert value['full_replay'] is False and len(value['scope']['jobs'])==2
    assert not small.runtime.calls and before==list(small.task.glob('finalization/report-attestation-*'))
    assert small.before_ledger==(small.run/'train/ledger/events.jsonl').read_bytes()


def test_full_all_final_groups_unique_calibration_and_no_ledger_mutation(small):
    result=small.apply();assert result['status']=='attested'
    assert len(small.runtime.calls)==3 # one A/A shared by two final candidates
    proof=load(result['attestation']['path']);assert len(proof['comparisons'])==2
    assert proof['historical_report_authority'] is False and proof['selected_candidate_id'] is None
    assert proof['native_executed'] is False and proof['formal_admission']=='not_evaluated'
    assert small.before_ledger==(small.run/'train/ledger/events.jsonl').read_bytes()
    assert len(a.task_events(small.task))==1
    again=small.apply();assert again['status']=='already_attested' and len(a.task_events(small.task))==1
    assert proof==load(result['attestation']['path'])


def test_chained_parents_all_five_final_groups(tmp_path,monkeypatch):
    s=Small(tmp_path,monkeypatch,chain=True,failed=())
    value=s.apply();proof=load(value['attestation']['path'])
    assert len(proof['comparisons'])==5 and len(s.runtime.calls)==6
    assert {p['relation'] for p in proof['comparisons']}=={'direct_parent','original_baseline'}


@pytest.mark.parametrize('mutation',['missing_completion','report_rehash','missing_session','case_missing','source_archive','request','source_feedback','stage_result','engineering_snapshot','pending_stage','guard_rehash','wrong_completion_relation'])
def test_mutations_block_without_authority_event(small,mutation):
    request=small.request();cid=request['evaluation_candidate_ids'][0]
    parent=small.task/'candidates'/cid;directory=parent/'stages/final/direct_parent'
    if mutation=='missing_completion':(small.task/'finalization/completion.json').unlink()
    elif mutation=='report_rehash':
        p=directory/'report.json';v=load(p);v['results'][0]['speedup']=99;save(p,v)
        c=load(small.task/'finalization/completion.json');c['comparisons'][0]['comparisons'][0]['report']=pointer(p);save(small.task/'finalization/completion.json',c)
    elif mutation=='missing_session':
        p=directory/'group-completion.json';v=load(p);v['completed_sessions'].pop();save(p,v)
    elif mutation=='case_missing':
        p=directory/'report.json';v=load(p);v['case_ids'].pop();save(p,v)
    elif mutation=='source_archive':(parent/'source.tar').write_bytes(b'wrong source')
    elif mutation=='request':
        p=small.task/'finalization/request.json';v=load(p);v['evaluation_candidate_ids'].pop();save(p,v)
    elif mutation=='source_feedback':
        p=Path(request['source_attempts'][1]['feedback']['path']);v=load(p);v['status']='infrastructure_blocked';save(p,v)
    elif mutation=='stage_result':
        p=parent/'stages/final/result.json';v=load(p);v['status']='failed';save(p,v)
    elif mutation=='engineering_snapshot':
        p=Path(load(small.engineering)['files'][0]['snapshot']);p.write_text('different')
    elif mutation=='pending_stage':
        from types import SimpleNamespace
        small.runtime.campaign=SimpleNamespace(_active=lambda _: True,_safe_source=campaign._safe_source,FRESH_SCHEMA=campaign.FRESH_SCHEMA)
    elif mutation=='guard_rehash':
        p=Path(request['source_attempts'][1]['semantic_guards']['path']);v=load(p);v['status']='failed';save(p,v)
    elif mutation=='wrong_completion_relation':
        p=small.task/'finalization/completion.json';v=load(p);v['comparisons'][0]['comparisons'][0]['relation']='invented';save(p,v)
    with pytest.raises((ValueError,AssertionError,FileNotFoundError,KeyError)):
        small.apply()
    assert a.task_events(small.task)==[]


def test_output_changed_with_unchanged_report_rejected(small):
    p=small.task/'candidates/maximum002/stages/final/direct_parent/p0/tiny-output.bin';p.write_bytes(b'mutated')
    with pytest.raises(ValueError,match='artifact'):small.apply()
    assert not a.task_events(small.task)


def test_unrelated_public_event_suffix_preserves_idempotence(small):
    first=small.apply();from msprof_exploration_execute import event
    event(small.task,'unrelated_review',{'nothing_to_do_with_original_measurement':True})
    second=small.apply();assert first['attestation']==second['attestation']
    assert len([v for v in a.task_events(small.task) if v['kind']==a.EVENT])==1


def test_published_uncommitted_artifact_requires_full_replay_before_event(small,monkeypatch):
    original=a.task_events;count=0
    def fail_once(task):
        nonlocal count
        count+=1
        if count==2:raise OSError('before event append')
        return original(task)
    monkeypatch.setattr(a,'task_events',fail_once)
    with pytest.raises(OSError):small.apply()
    assert len(list(small.task.glob('finalization/report-attestation-*')))==1
    monkeypatch.setattr(a,'task_events',original)
    assert not original(small.task)
    small.runtime.calls.clear();result=small.apply()
    assert result['status']=='attested' and len(small.runtime.calls)==3


def test_publication_failure_leaves_no_event_or_partial_official_directory(small,monkeypatch):
    def failure(*args):raise OSError('simulated directory rename failure')
    monkeypatch.setattr(a.os,'rename',failure)
    with pytest.raises(OSError):small.apply()
    assert not list(small.task.glob('finalization/report-attestation-*')) and not a.task_events(small.task)


def test_existing_committed_event_cannot_bless_changed_attestation(small):
    result=small.apply();p=Path(result['attestation']['path']);v=load(p);v['comparisons'].pop();save(p,v)
    with pytest.raises(ValueError):small.apply()
    assert len(a.task_events(small.task))==1


def test_false_writers_closed_rejected_before_lock(small):
    with pytest.raises(ValueError,match='writers-closed'):
        a.attest(small.runtime,small.run,'maximum',small.request_sha,small.engineering,writers_closed=False)
    assert small.runtime.host_calls==0


def test_noncanonical_paths_rejected(tmp_path):
    with pytest.raises(ValueError,match='noncanonical'):a.safe(tmp_path/'x/../victim')
    victim=tmp_path/'victim';victim.write_text('x');link=tmp_path/'link';link.symlink_to(victim)
    with pytest.raises(ValueError):a.safe(link)


def test_committed_reentry_preserves_cost_snapshot_after_unrelated_closed_control(small):
    result=small.apply();root=Path(result['attestation']['path']).parent
    request_bytes=(root/'request.json').read_bytes()
    ledger=campaign.Campaign(small.run/'train/ledger');baseline=ledger.config['tasks']['maximum']['baseline_source_hash']
    plan={'control_type':'method','source_hash':baseline,'case_ids':a.ALL_CASES,'manifest_ref':'sha256:'+'d'*64}
    ledger.start(event_id='unrelated-control-start',workload='maximum',stage_id='other-control',kind='control',plan=plan)
    ledger.finish(event_id='unrelated-control-finish',workload='maximum',stage_id='other-control',outcome='success',evidence={'synthetic':'sha256:'+'e'*64},native_started=True,formal_samples=0)
    after=small.apply()
    assert after['status']=='already_attested' and after['attestation']==result['attestation']
    assert (root/'request.json').read_bytes()==request_bytes and len(a.task_events(small.task))==1


def test_stored_original_cost_snapshot_cannot_be_forged_before_commit(small,monkeypatch):
    original=a.task_events;count=0
    def crash(task):
        nonlocal count
        count+=1
        if count==2:raise OSError('uncommitted')
        return original(task)
    monkeypatch.setattr(a,'task_events',crash)
    with pytest.raises(OSError):small.apply()
    monkeypatch.setattr(a,'task_events',original)
    root=next(small.task.glob('finalization/report-attestation-*'))
    request=load(root/'request.json');request['costs_before']['maximum']['source']=0;save(root/'request.json',request)
    proof=load(root/'attestation.json');proof['request']=pointer(root/'request.json');save(root/'attestation.json',proof)
    with pytest.raises(ValueError,match='cost snapshot'):small.apply()
    assert not original(small.task)


@pytest.mark.parametrize('key,value',[('operator','other'),('historical_report_authority',True),('graph_policy_eligible',True),('episode_ref','fake'),('kind','historical_measurement')])
def test_uncommitted_forged_attestation_fields_rejected(small,monkeypatch,key,value):
    original=a.task_events;count=0
    def crash(task):
        nonlocal count
        count+=1
        if count==2:raise OSError('uncommitted')
        return original(task)
    monkeypatch.setattr(a,'task_events',crash)
    with pytest.raises(OSError):small.apply()
    monkeypatch.setattr(a,'task_events',original)
    root=next(small.task.glob('finalization/report-attestation-*'));proof=load(root/'attestation.json');proof[key]=value;save(root/'attestation.json',proof)
    with pytest.raises(ValueError):small.apply()
    assert not original(small.task)


def test_three_failed_attempts_attest_closure_without_report_authority(tmp_path,monkeypatch):
    s=Small(tmp_path,monkeypatch,failed=(1,2,3));result=s.apply()
    proof=load(result['attestation']['path'])
    assert proof['comparisons']==[] and not s.runtime.calls
    assert proof['selected_candidate_id'] is None


@pytest.mark.parametrize('fault',['calibration_wrong_kind','duplicate_result_cell'])
def test_structural_report_failures_cannot_hide_in_replay_stub(small,fault):
    if fault=='calibration_wrong_kind':
        p=small.cal/'plan.json';value=load(p);value['comparison_kind']='ab';save(p,value)
    else:
        p=small.task/'candidates/maximum002/stages/final/direct_parent/report.json';value=load(p)
        value['results'][-1]=deepcopy(value['results'][0]);save(p,value)
        small.runtime.expected[value['sessions'][0]['directory']]=deepcopy(value)
        c=load(small.task/'finalization/completion.json');c['comparisons'][0]['comparisons'][0]['report']=pointer(p);save(small.task/'finalization/completion.json',c)
    with pytest.raises(ValueError):small.apply()
    assert not a.task_events(small.task)


@pytest.mark.parametrize('proof_kind',['matching','absent','wrong_origin','wrong_snapshot'])
def test_only_actual_same_replay_producer_proof_can_preserve_old_logical_origin(small,proof_kind):
    directory=small.task/'candidates/maximum002/stages/final/direct_parent'
    origin=directory/'p0/tiny-output.bin' # fake analyzer substitutes a known code-origin slot in tiny fixture
    old=pointer(origin);snapshot=small.run/'old-producer.snapshot';snapshot.write_bytes(origin.read_bytes())
    manifest=small.run/'old-producer.manifest.json';save(manifest,{'origin':old,'snapshot':pointer(snapshot)})
    origin.write_bytes(b'new reviewed producer')
    proof={'origin':old,'snapshot':pointer(snapshot),'frozen_manifest':pointer(manifest),'binding_mode':'frozen_engineering_snapshot'}
    if proof_kind=='wrong_origin':proof['origin']={**old,'path':str(small.run/'unrelated')}
    if proof_kind=='wrong_snapshot':proof['snapshot']={**pointer(snapshot),'sha256':'sha256:'+'0'*64}
    original=small.runtime.analyze
    def analyze(directories,plan,calibration):
        value=original(directories,plan,calibration)
        small.runtime.observation_provenance=[proof] if proof_kind!='absent' and directories[0]==str(directory/'p0') else []
        return value
    small.runtime.analyze=analyze
    if proof_kind=='matching':
        result=small.apply();assert load(result['attestation']['path'])['comparisons'][0]['observation_producers']==[proof]
    else:
        with pytest.raises(ValueError):small.apply()
        assert not a.task_events(small.task)


@pytest.mark.parametrize('fault',['external_manifest','wrong_protocol','wrong_campaign','unbound_current_producer'])
def test_engineering_requires_exact_current_canonical_closure(small,fault):
    value=load(small.engineering)
    if fault=='external_manifest':
        p=small.run/'self-generated-engineering.json';save(p,value);small.engineering=p
    else:
        if fault=='wrong_protocol':value['version']='anything'
        if fault=='wrong_campaign':value['campaign_manifest']={'path':str(small.run/'wrong'),'sha256':'sha256:'+'b'*64}
        if fault=='unbound_current_producer':value['files']=[]
        save(small.engineering,value)
    with pytest.raises(ValueError):small.apply()
    assert not a.task_events(small.task)


def test_exact_real_style_descriptive_schedule_names_are_supported(small):
    directory=small.task/'independent-replay-fixture'
    plan={'case_ids':a.ALL_CASES,'comparison_kind':'aa',
          'schedule':[{'name':f'aa-parent-local-refresh-02-p{i:02}'} for i in range(1,7)]}
    hashes={'A':'x','B':'x'};small.make_report(directory,plan,hashes)
    job={'directory':str(directory),'plan':pointer(directory/'plan.json'),'report':pointer(directory/'report.json'),
         'completion':pointer(directory/'group-completion.json'),'source_hashes':hashes,'comparison_kind':'aa'}
    result=a.replay(a.Evidence(small.runtime),small.runtime,job)
    assert [Path(p).name for p in result['session_directories']]==[r['name'] for r in plan['schedule']]


@pytest.mark.parametrize('name',['../p01','x/p01','.','..','/absolute/p01'])
def test_descriptive_schedule_never_accepts_path_escape(small,name):
    directory=small.cal;plan=load(directory/'plan.json');plan['schedule'][0]['name']=name;save(directory/'plan.json',plan)
    job={'directory':str(directory),'plan':pointer(directory/'plan.json'),'report':pointer(directory/'report.json'),
         'completion':pointer(directory/'group-completion.json'),'source_hashes':{'A':'x','B':'x'},'comparison_kind':'aa'}
    with pytest.raises(ValueError,match='schedule'):a.replay(a.Evidence(small.runtime),small.runtime,job)


def test_last_reader_exit_failure_cannot_publish_event(small):
    # First session belongs to full audit, second to final pre-event recheck.
    count=0
    @contextmanager
    def readers():
        nonlocal count
        count+=1
        yield
        if count==2:raise ValueError('final reader exit rejected')
    small.runtime.reader_session=readers
    with pytest.raises(ValueError,match='final reader exit rejected'):small.apply()
    assert a.task_events(small.task)==[]
    assert small.before_ledger==(small.run/'train/ledger/events.jsonl').read_bytes()


def test_uncommitted_reentry_cannot_drop_archived_member_closure(small,monkeypatch):
    target=small.cal/'p0/tiny-output.bin'
    proof={'version':'level2_closed_raw_storage_v1','origin':pointer(target),
           'seal':{'path':str(small.cal/'seal.json'),'sha256':'sha256:'+'1'*64},
           'archive':{'path':str(small.cal/'raw.tar'),'sha256':'sha256:'+'2'*64},
           'producer':{'path':str(small.cal/'producer.py'),'sha256':'sha256:'+'3'*64},
           'closed_evidence':{'explicit_fixture':True}}
    small.runtime.binding=lambda p,h:proof if Path(p)==target else None
    original=a.committed
    # Make the final reader exit fail after durable files but before the event.
    count=0
    @contextmanager
    def readers():
        nonlocal count
        count+=1;yield
        if count==2:raise ValueError('synthetic final check')
    small.runtime.reader_session=readers
    with pytest.raises(ValueError):small.apply()
    directory=next(small.task.glob('finalization/report-attestation-*'))
    request=load(directory/'request.json');request['storage_bindings']=a.compact_storage_bindings([]);save(directory/'request.json',request)
    attestation=load(directory/'attestation.json');attestation['request']=pointer(directory/'request.json');save(directory/'attestation.json',attestation)
    small.runtime.reader_session=FakeRuntime.reader_session.__get__(small.runtime)
    with pytest.raises(ValueError,match='uncommitted audit storage closure'):small.apply()
    assert not a.task_events(small.task)

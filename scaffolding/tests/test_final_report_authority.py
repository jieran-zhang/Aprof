from pathlib import Path
import importlib.util
import json
import os
import sys
import pytest

if os.environ.get('APROF_ATTESTOR_TEST_ROOT'):
    sys.path.insert(0,str(Path(os.environ['APROF_ATTESTOR_TEST_ROOT'])/'tests'))
from test_final_report_attestation import Small, save, load, pointer, a
S=importlib.util.spec_from_file_location('authority_under_test',Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts/level2_final_report_authority.py')
f=importlib.util.module_from_spec(S);S.loader.exec_module(f)

def provision_storage(s):
    from reviewed_storage_fixture import materialize_reviewed_storage
    readers=materialize_reviewed_storage(s.run/'bootstrap/reviewed-storage-test-epoch',a.STORAGE_PRODUCERS)
    paths=[Path(a.__file__),*readers]
    eng=load(s.engineering)
    for file in paths[1:]:
        ref=pointer(file);assert ref['sha256']==a.STORAGE_PRODUCERS[file.name]
        snap=s.run/'bootstrap/source-cas'/ref['sha256'][7:];snap.write_bytes(file.read_bytes())
        eng['files'].append({**ref,'snapshot':str(snap)})
    for ref in s.request()['producers']:
        snap=s.run/'bootstrap/source-cas'/ref['sha256'][7:]
        assert pointer(ref['path'])==ref;snap.write_bytes(Path(ref['path']).read_bytes())
    save(s.engineering,eng);s.runtime.producer_paths=lambda:paths

@pytest.fixture
def proof(tmp_path,monkeypatch):
    s=Small(tmp_path,monkeypatch);provision_storage(s);result=s.apply()
    att=load(result['attestation']['path']);p=Path(att['comparisons'][0]['session_directories'][0])
    return s,result,p

def read(p):return Path(p).read_bytes()

def test_real_ledger_tiny_attestation_admits_canonical_final(proof):
    s,r,p=proof;before=(s.run/'train/ledger/events.jsonl').read_bytes();calls=list(s.runtime.calls)
    result=f.authority(p,read)
    assert result['kind']==f.KIND and result['report']==pointer(p.parent/'report.json')
    assert result['historical_report_authority'] is False and result['authority_timing']==f.TIMING
    assert before==(s.run/'train/ledger/events.jsonl').read_bytes() and calls==s.runtime.calls
    assert len(result['event_bindings'])==2

@pytest.mark.parametrize('which',['request','attestation','report','source','feedback','result','engineering','snapshot','manifest','ledger_prefix'])
def test_exact_original_objects_cannot_change(proof,which):
    s,r,p=proof;attpath=Path(r['attestation']['path']);att=load(attpath);req=load(att['request']['path']);scope=req['scope']
    paths={'request':Path(att['request']['path']),'attestation':attpath,'report':p.parent/'report.json',
           'source':Path(scope['sources']['baseline']['archive']['path']),
           'feedback':Path(s.request()['source_attempts'][1]['feedback']['path']),
           'result':Path(scope['jobs'][0]['stage_result']['path']),'engineering':s.engineering,
           'snapshot':Path(scope['producers'][0]['snapshot']['path']),'manifest':s.task/'manifest.json',
           'ledger_prefix':attpath.parent/'ledger-prefix.jsonl'}
    paths[which].write_bytes(paths[which].read_bytes()+b' ')
    with pytest.raises((ValueError,KeyError,json.JSONDecodeError)):f.authority(p,read)

def test_uncommitted_files_do_not_create_authority(proof):
    s,r,p=proof;(s.task/'events.jsonl').write_bytes(b'')
    with pytest.raises(ValueError,match='no unique'):f.authority(p,read)

def test_unrelated_valid_event_suffix_does_not_change_authority(proof):
    s,r,p=proof;before=f.authority(p,read)
    from msprof_exploration_execute import event
    event(s.task,'other_closed_audit',{'unrelated':True})
    assert f.authority(p,read)==before

def rewrite_commit(s,r,mutate_att=None,mutate_req=None):
    attpath=Path(r['attestation']['path']);att=load(attpath);reqpath=Path(att['request']['path']);req=load(reqpath)
    if mutate_req:mutate_req(req);save(reqpath,req);att['request']=pointer(reqpath)
    if mutate_att:mutate_att(att)
    save(attpath,att);ev=load(s.task/'events.jsonl');ev['value']['attestation']=pointer(attpath)
    ev['hash']=a.digest(a.canonical({k:v for k,v in ev.items() if k!='hash'}));save(s.task/'events.jsonl',ev)

@pytest.mark.parametrize('which',['capture_claim','wrong_relation','missing_comparison','self_signed_report','calibration','incomplete_sessions','native','old_v1','unreviewed_writer','foreign_slot','evidence_drop'])
def test_self_rehashed_unknown_or_incomplete_attestation_rejected(proof,which):
    s,r,p=proof
    def att(v):
        if which=='capture_claim':v['historical_report_authority']=True
        elif which=='wrong_relation':v['comparisons'][0]['relation']='invented'
        elif which=='missing_comparison':v['comparisons'].pop()
        elif which=='calibration':v['comparisons'][0]['calibration_replay']['report']=v['comparisons'][0]['report']
        elif which=='incomplete_sessions':v['comparisons'][0]['session_directories'].pop()
        elif which=='native':v['native_executed']=True
        elif which=='old_v1':v['version']='level2_final_report_consistency_attestation_v1'
        elif which=='foreign_slot':v['comparisons'][0]['report']['path']=str(p.parent/'else.json')
    def req(v):
        if which=='unreviewed_writer':v['scope']['producers'][0]['origin']['sha256']='sha256:'+'0'*64
        elif which=='evidence_drop':
            logical=p/'tiny-output.bin';v['scope']['evidence']=[r for r in v['scope']['evidence'] if r['path']!=str(logical)]
        elif which=='self_signed_report':
            report=load(p.parent/'report.json');report['results'][0]['speedup']=99;save(p.parent/'report.json',report)
            # Updating its own output pointer does not change frozen completion.
            v['scope']['jobs'][0]['report']=pointer(p.parent/'report.json')
    rewrite_commit(s,r,att,req)
    with pytest.raises((ValueError,KeyError)):f.authority(p,read)

def test_report_slots_with_identical_bytes_cannot_move(proof):
    s,r,p=proof;other=p.parent/'copied-report.json';other.write_bytes((p.parent/'report.json').read_bytes())
    rewrite_commit(s,r,lambda v:v['comparisons'][0].update(report=pointer(other)))
    with pytest.raises(ValueError):f.authority(p,read)

def test_data_only_callback_never_reads_payloads_or_executes_snapshot(proof):
    s,r,p=proof
    def bounded(q):
        assert q.name!='tiny-output.bin','payload must remain logical evidence, not be reread'
        return read(q)
    result=f.authority(p,bounded)
    assert result['storage_catalog']['origins']=={}

@pytest.mark.parametrize('rel',['search/direct_parent/p0','final/invented/p0','final/direct_parent/../p0'])
def test_foreign_paths_fail_before_any_read(proof,rel):
    s,r,p=proof
    with pytest.raises(ValueError):f.authority(p.parents[2]/rel,lambda _:pytest.fail('not canonical'))

def test_five_chained_final_relations_all_preserved(tmp_path,monkeypatch):
    s=Small(tmp_path,monkeypatch,chain=True,failed=());provision_storage(s);r=s.apply();att=load(r['attestation']['path'])
    assert len(att['comparisons'])==5
    for row in att['comparisons']:
        assert f.authority(Path(row['session_directories'][0]),read)['report']==row['report']


def test_offline_data_authority_needs_no_original_paths(proof):
    s,r,p=proof;value=f.authority(p,read)
    memory={ref['path']:read(ref['path']) for ref in value['protected']}
    memory.update({row['path']:read(row['path']) for row in value['event_bindings']})
    assert f.authority(p,lambda q:memory[str(q)])==value


def test_exact_cost_snapshot_recomputed_not_self_asserted(proof):
    s,r,p=proof
    rewrite_commit(s,r,mutate_req=lambda q:q['costs_before']['maximum'].update(source=0))
    with pytest.raises(ValueError,match='cost snapshot'):f.authority(p,read)


def test_profile_self_rehash_cannot_substitute_unreviewed_raw_epoch(proof):
    s,r,p=proof
    rewrite_commit(s,r,mutate_req=lambda q:q['scope']['storage_profile'].update(reviewed_patch_sha256='sha256:'+'0'*64))
    with pytest.raises(ValueError,match='profile differs'):f.authority(p,read)


def test_later_valid_ledger_suffix_does_not_change_original_snapshot(proof):
    s,r,p=proof;before=f.authority(p,read)
    import msprof_exploration_campaign as campaign
    ledger=campaign.Campaign(s.run/'train/ledger')
    ledger.checkpoint(event_id='post-audit-checkpoint',checkpoint_id='post-audit-checkpoint',reason='later independent work',next_action='none',resources_released=True,artifacts={})
    assert f.authority(p,read)==before


def test_changed_prior_ledger_prefix_rejected(proof):
    s,r,p=proof;ledger=s.run/'train/ledger/events.jsonl';data=ledger.read_bytes();ledger.write_bytes(data.replace(b'genesis',b'genesiX',1))
    with pytest.raises(ValueError,match='ledger'):f.authority(p,read)


def catalog_fixture():
    sha='sha256:'+'1'*64;h='sha256:'+'2'*64;body={'protected':[],'event_binding':{'path':'/run/events.jsonl','sequence':1,'hash':h}}
    ph=f.digest(f.canonical(body))
    value={'version':'level2_attestation_storage_closure_v1','origins':{'/run/output1.bin':{'sha256':h,'seal':sha},'/run/output2.bin':{'sha256':h,'seal':sha}},
           'archives':{sha:{'version':'level2_closed_native_outputs_v1','seal':{'path':'/run/storage/seal.json','sha256':sha},
                            'archive':{'path':'/run/storage/outputs.tar','sha256':h},'producer':{'path':'/run/storage/producer.py','sha256':h},'closed_evidence_ref':ph}},
           'closed_evidence':{ph:body}}
    return value


def test_catalog_reconstruction_keeps_every_origin_full_proof_once():
    value=catalog_fixture();rows=list(f.catalog_bindings({'kind':f.KIND,'historical_report_authority':False,'storage_catalog':value}))
    assert len(rows)==1 and len(rows[0]['origins'])==2
    assert rows[0]['binding']['closed_evidence']==next(iter(value['closed_evidence'].values()))
    assert {r['path'] for r in rows[0]['origins']}==set(value['origins'])

@pytest.mark.parametrize('what',['orphan','missing_archive','wrong_proof','wrong_origin_sha','unsupported_version','extra_member_key'])
def test_catalog_rejects_dropped_conflicting_unknown_proofs(what):
    value=catalog_fixture();evidence={p:r['sha256'] for p,r in value['origins'].items()}
    if what=='orphan':value['origins']={}
    elif what=='missing_archive':value['archives']={}
    elif what=='wrong_proof':next(iter(value['closed_evidence'].values()))['protected']=[{'changed':True}]
    elif what=='wrong_origin_sha':value['origins']['/run/output1.bin']['sha256']='sha256:'+'3'*64
    elif what=='unsupported_version':next(iter(value['archives'].values()))['version']='untrusted'
    else:value['origins']['/run/output1.bin']['extra']='ignored'
    with pytest.raises(ValueError):f.storage_catalog(value,evidence)


def test_verification_reader_uses_trusted_sibling_final_authority(proof):
    s,r,p=proof
    spec=importlib.util.spec_from_file_location('verification_under_test',Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts/level2_verification_storage.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    assert Path(v.__file__).resolve().parents[3]==Path(__file__).resolve().parents[2]
    value=v.report_authority(p,read,allow_final=True)
    assert value==f.authority(p,read)
    with pytest.raises(ValueError,match='protocol v3'):v.report_authority(p,read)
    assert v.admission_version(p)==v.FINAL_VERSION
    prior={'path':'/run/task-events','sequence':0,'hash':'sha256:'+'0'*64}
    assert v.event_bindings({'event_binding':prior,'report_authority':value})==[prior,*value['event_bindings']]

@pytest.mark.parametrize('candidate',[False,True])
def test_prior_aa_search_v1_v2_facts_are_exactly_unchanged(tmp_path,monkeypatch,candidate):
    from contextlib import nullcontext
    from test_level2_native_output_storage import fixture as native_fixture
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',lambda:nullcontext())
    _,cohort,_,_=native_fixture(tmp_path,candidate=candidate)
    values=[]
    for location in ('base','scripts'):
        source=(Path(__file__).parent/'fixtures/level2_verification_storage_452c.py' if location=='base' else Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts/level2_verification_storage.py')
        if location=='base':assert a.digest(source.read_bytes())=='sha256:452c479151a6d0a9be43df4388a68f6577f0212c2fbd005c4501dbd8f43d7594'
        spec=importlib.util.spec_from_file_location('verification_compat_'+location,source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        values.append([module.facts_for_version(cohort/'p01',read,version) for version in (module.VERSION,module.ANCHORED_VERSION)])
    assert values[0]==values[1]

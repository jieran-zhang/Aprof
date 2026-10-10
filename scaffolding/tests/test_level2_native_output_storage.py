from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import pytest
PROPOSAL=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROPOSAL/'scaffolding/collection/scripts'))
import level2_native_output_storage as native
import level2_verification_storage as verification
import level2_adapters as adapters
import trace_v2_dataset as dataset
import trace_v2_portable as portable
import msprof_exploration_report as report
import msprof_exploration_archive as archive
for module in (native,verification,adapters,dataset,portable,report,archive):
    assert Path(module.__file__).resolve().parent==PROPOSAL/'scaffolding/collection/scripts'
import level2_storage as dedup
from msprof_exploration_execute import event


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(native.canonical(value));return path

def blob(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

@pytest.fixture(autouse=True)
def no_hardware(monkeypatch):
    @contextmanager
    def lock():yield
    monkeypatch.setattr(dedup,'exclusive_host',lock)


def fixture(tmp_path,operator='maximum',size=8,candidate=False,*,candidate_id=None,stage_name=None):
    task=tmp_path/'run/train/tasks'/operator
    stage=(task/'candidates'/(candidate_id or operator+'001')/'stages'/(stage_name or 'search')
           if candidate else task/'stages'/(stage_name or 'aa'))
    cohort=stage/('direct_parent' if candidate else 'cohort')
    schedule=[];observations=[];sessions=[];original={}
    for number in range(1,7):
        session=cohort/f'p{number:02d}';sessions.append(str(session));artifacts={};outputs=[];journal=[]
        request={'version':'msprof_kernel_time_study_v2','cases':[{'case_id':1}],'buffer_configs':'normal,swapped'}
        schedule.append({'name':session.name,'request':request});save(session/'request.json',request)
        for config in ('normal','swapped'):
            for role in 'AB':
                stem=f'1_{config}_{role}';output=session/'native'/(stem+'.bin');data=b'12345678'*(size//8)
                keys=native.OUTPUT_KEYS.get(operator)
                if keys:
                    rows=[];bundle=b''
                    for i,key in enumerate(keys):
                        partdata=data+bytes([i]);part=output.with_name(output.name+'.'+key);blob(part,partdata);original[str(part)]=partdata
                        rows.append({'name':key,'path':str(part),'bytes':len(partdata),'sha256':native.digest(partdata)});bundle+=struct.pack('<Q',len(partdata))+partdata
                    data=bundle;index=output.with_name(output.name+'.outputs.json');save(index,{'version':'level2_output_bundle_v1','operator':operator,'outputs':rows});original[str(index)]=index.read_bytes()
                blob(output,data);original[str(output)]=data
                row={'case_id':'1','buffer_config':config,'role':role,'passed':True,'output_hash':native.digest(data)};outputs.append(row)
                journal.append({**row,'type':'output','path':str(output),'validation_scope':'final_call_of_final_formal_sample'})
                for name in verification.verification_names(session):
                    p=save(session/'verification'/stem/name,{'exit_code':0,'ended_at':1,'passed':True})
                    if name!='result.json':artifacts[str(p)]=native.digest(p.read_bytes())
        for path,data in original.items():
            if Path(path).is_relative_to(session):artifacts[path]=native.digest(data)
        journal.append({'type':'session_end','exit_code':0,'stream_destroyed':True,'context_destroyed':True})
        (session/'native/journal.jsonl').write_bytes(b''.join(native.canonical(row) for row in journal))
        save(session/'validation.json',{'scope':'final_call_of_final_sample_per_case_config_role','outputs':outputs})
        save(session/'completion.json',{'version':'msprof_kernel_time_study_v2','status':'passed','error':None});save(session/'samples.json',{'samples':[]});save(session/'msprof.execution.json',{'exit_code':0,'error':None,'ended_at':1});save(session/'bindings.json',{})
        observations.append({'directory':str(session),'artifacts':artifacts})
    save(cohort/'plan.json',{'schedule':schedule,'case_ids':[1]})
    save(cohort/'report.json',{'operator':operator,'evidence_status':'verified_complete','sessions':observations})
    save(cohort/'group-completion.json',{'status':'passed','error':None,'ended_at':2,'completed_sessions':sessions,'sessions':[{'directory':directory,'completion':native.raw_ref(Path(directory)/'completion.json'),'samples':native.raw_ref(Path(directory)/'samples.json'),'journal':native.raw_ref(Path(directory)/'native/journal.jsonl')} for directory in sessions]})
    save(task/'manifest.json',{'version':'msprof_task_time_exploration_v2','operator':operator})
    save(stage/'stage-plan.json',{'cohorts':[{'relation':cohort.name,'plan':native.raw_ref(cohort/'plan.json')}]} if candidate else {'cohort':json.loads((cohort/'plan.json').read_text())});save(stage/'result.json',{'kind':'timing' if candidate else 'control','status':'passed','error':None,'ended_at':2})
    event(task,'stage_completed',{'result':native.raw_ref(stage/'result.json')})
    from verification_authority_fixture import anchor
    anchor(task,cohort,'observe' if candidate else 'calibration')
    # Synthetic immutable prior maintenance authority: exact read-only Inventory
    # results, with the terminal outcome represented as a fixture state.
    authority=dedup.deduplicate(task.parents[2],cohort,kind='cohort',writers_closed=True,apply=False)
    authority.update(status='passed',error=None,ended_at=3,original_records_modified=False)
    manifest=save(task.parents[2]/'storage/dedup'/('0'*31+'1.json'),authority)
    event(task,'closed_outputs_deduplicated',{'manifest':native.raw_ref(manifest),'reclaimed_bytes':0,'evidence_bytes_deleted':0})
    return task,cohort,tmp_path/'shadow',original


def test_unary_shadow_exact_bounded_stream_and_no_original_mutation(tmp_path):
    task,cohort,destination,original=fixture(tmp_path,size=2*native.CHUNK)
    result=native.prepare(cohort,destination,writers_closed=True)
    assert result['status']=='sealed_shadow' and result['logical_files']==24
    assert {p:Path(p).read_bytes() for p in original}==original
    with native.reader_session({cohort:destination}):
        for path,data in original.items():
            with verification.open_binary(path) as stream:
                assert stream.read(11)==data[:11];stream.seek(len(data)-5);assert stream.read(6)==data[-5:]
            assert report.sha(path)==native.digest(data)
            assert native.evidence_binding(path,native.digest(data))['origin']=={'path':path,'sha256':native.digest(data)}
        assert len(native.logical_files(cohort))==24
    assert len(native.verified(cohort,destination)['offsets'])==1

def test_report_authority_v2_archives_without_dedup_event(tmp_path):
    task,cohort,destination,original=fixture(tmp_path)
    events=task/'events.jsonl'
    rows=events.read_bytes().splitlines(keepends=True)
    assert json.loads(rows[-1])['kind']=='closed_outputs_deduplicated'
    events.write_bytes(b''.join(rows[:-1]))
    result=native.prepare(cohort,destination,writers_closed=True,report_authority=True)
    assert result['version']==native.REPORT_VERSION and result['status']=='sealed_shadow'
    with native.reader_session({cohort:destination}):
        for path,data in original.items():
            assert native.fingerprint(path)=={'sha256':native.digest(data),'size_bytes':len(data)}
    assert {p:Path(p).read_bytes() for p in original}==original

def test_report_authority_v2_retirement_replays_original_outputs(tmp_path):
    task,cohort,_,original=fixture(tmp_path)
    events=task/'events.jsonl';events.write_bytes(b''.join(events.read_bytes().splitlines(keepends=True)[:-1]))
    result=native.prepare(cohort,writers_closed=True,retire=True,report_authority=True)
    assert result['version']==native.REPORT_VERSION and result['status']=='complete'
    assert all(not Path(path).exists() for path in original)
    with verification.reader_session():
        for path,data in original.items():
            assert verification.fingerprint(path)=={'sha256':native.digest(data),'size_bytes':len(data)}
    assert (cohort/'native-output-storage/compacted.json').is_file()

@pytest.mark.parametrize('changed',['report','output'])
def test_report_authority_v2_rejects_changed_original(tmp_path,changed):
    task,cohort,destination,_=fixture(tmp_path)
    events=task/'events.jsonl';events.write_bytes(b''.join(events.read_bytes().splitlines(keepends=True)[:-1]))
    path=cohort/'report.json' if changed=='report' else cohort/'p01/native/1_normal_A.bin'
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError):native.prepare(cohort,destination,writers_closed=True,report_authority=True)
    assert not (destination/'seal.json').exists() and path.exists()

@pytest.mark.parametrize('operator',list(native.OUTPUT_KEYS))
def test_named_bundle_report_metadata_and_retirement(tmp_path,operator):
    task,cohort,shadow,original=fixture(tmp_path,operator)
    result=native.prepare(cohort,writers_closed=True,retire=True)
    assert result['logical_files']==96 and all(not Path(p).exists() for p in original)
    with verification.reader_session():
        for path,data in original.items():
            assert verification.fingerprint(path)=={'sha256':native.digest(data),'size_bytes':len(data)}
        output=cohort/'p01/native/1_normal_A.bin'
        result=adapters.verify_output_metadata(operator,{},output)
        assert set(result)==set(native.OUTPUT_KEYS[operator])
        assert dataset.Evidence().file(output)
    assert native.prepare(cohort,writers_closed=True,retire=True)['status']=='complete'
    assert (cohort/'p01/native/journal.jsonl').is_file()
    assert (cohort/'p01/verification/1_normal_A/metadata.json').is_file()

@pytest.mark.parametrize('mutation',['stage_open','session_failed','missing_teardown','missing_role','wrong_output_hash','wrong_schedule','extra_native_bin','unrecognized_suffix','symlink','missing_original','missing_case'])
def test_invalid_original_fails_closed_before_retire(tmp_path,mutation):
    task,cohort,destination,original=fixture(tmp_path)
    first=cohort/'p01';output=first/'native/1_normal_A.bin'
    if mutation=='stage_open':save(cohort.parent/'result.json',{'status':'running'})
    elif mutation=='session_failed':save(first/'completion.json',{'status':'failed'})
    elif mutation=='missing_teardown':blob(first/'native/journal.jsonl',native.canonical({'type':'session_end','exit_code':0}))
    elif mutation=='missing_role':
        p=first/'validation.json';v=json.loads(p.read_text());v['outputs'].pop();save(p,v)
    elif mutation=='wrong_output_hash':output.write_bytes(b'changed!')
    elif mutation=='wrong_schedule':
        p=cohort/'plan.json';v=json.loads(p.read_text());v['schedule'][0]['name']='p99';save(p,v)
    elif mutation=='extra_native_bin':blob(first/'native/extra.bin',b'bad')
    elif mutation=='unrecognized_suffix':blob(first/'native/1_normal_A.bin.secret',b'bad')
    elif mutation=='symlink':output.unlink();output.symlink_to(first/'completion.json')
    elif mutation=='missing_original':output.unlink()
    elif mutation=='missing_case':
        p=first/'request.json';v=json.loads(p.read_text());v['cases'].append({'case_id':2});save(p,v)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        native.prepare(cohort,writers_closed=True,retire=True)
    assert (first/'native/1_normal_B.bin').is_file()

@pytest.mark.parametrize('mutation',['archive','seal','producer','bound_report','source_plan','event','reappearing_output'])
def test_retained_archive_and_closure_cannot_change(tmp_path,mutation):
    task,cohort,shadow,original=fixture(tmp_path);native.prepare(cohort,writers_closed=True,retire=True)
    destination=cohort/'native-output-storage'
    if mutation=='archive':blob(destination/'outputs.tar',b'bad')
    elif mutation=='seal':save(destination/'seal.json',{})
    elif mutation=='producer':blob(destination/'producer.py',b'bad')
    elif mutation=='bound_report':save(cohort/'report.json',{})
    elif mutation=='source_plan':save(cohort.parent/'stage-plan.json',{})
    elif mutation=='event':save(task/'events.jsonl',{})
    elif mutation=='reappearing_output':blob(Path(next(iter(original))),next(iter(original.values())))
    with pytest.raises((ValueError,KeyError,FileNotFoundError,tarfile.TarError)):
        native.verified(cohort)


def test_cache_commit_recheck_rejects_changed_protected_file(tmp_path):
    task,cohort,dest,original=fixture(tmp_path);native.prepare(cohort,dest,writers_closed=True)
    with pytest.raises((ValueError,KeyError)):
        with native.reader_session({cohort:dest}):
            assert verification.fingerprint(next(iter(original)))
            save(cohort.parent/'stage-plan.json',{'tampered':True})


def test_large_archived_output_requires_streaming_even_for_legacy_byte_api(tmp_path,monkeypatch):
    task,cohort,dest,original=fixture(tmp_path,size=32)
    native.prepare(cohort,dest,writers_closed=True)
    with native.reader_session({cohort:dest}):
        monkeypatch.setattr(native,'MAX_METADATA',16)
        # Disable only the metadata bound for already verified closure via cache;
        # large native read itself must reject without materializing all bytes.
        with pytest.raises(ValueError):native.read_bytes(next(iter(original)))


def portable_fixture(tmp_path,operator='maximum'):
    task,cohort,dest,original=fixture(tmp_path,operator)
    native.prepare(cohort,writers_closed=True,retire=True)
    seal_path=cohort/'native-output-storage/seal.json';seal=json.loads(seal_path.read_text());bundle=tmp_path/'portable'
    manifest={'files':{}};locations={}
    refs=[native.raw_ref(seal_path),seal['archive'],seal['producer'],*seal['closed_evidence']['protected']]
    event_path=Path(seal['closed_evidence']['event_binding']['path']);refs.append(native.raw_ref(event_path))
    for ref in refs:
        name='evidence/sha256/'+ref['sha256'][7:];path=bundle/name;blob(path,Path(ref['path']).read_bytes())
        manifest['files'][name]=portable.fingerprint(path);locations[ref['path']]=name
    for name in ('level2_native_output_storage.py','level2_verification_storage.py'):
        target=bundle/'verifier'/name;blob(target,(PROPOSAL/'scaffolding/collection/scripts'/name).read_bytes());manifest['files'][target.relative_to(bundle).as_posix()]=portable.fingerprint(target)
    origin=next(iter(original));h=native.digest(original[origin]);key=native.raw_ref(seal_path)['sha256']
    closure={'version':'level2_storage_portable_v2','origins':{origin:key},'archives':{key:{'seal':native.raw_ref(seal_path),'files':locations}}}
    name='storage-verification/bindings.json';save(bundle/name,closure);manifest['files'][name]=portable.fingerprint(bundle/name)
    manifest['storage_closure']={'path':name,'sha256':manifest['files'][name]['sha256']}
    # Include protected originals in the signed roster, as real Archive.pointer does.
    index={str(i):ref for i,ref in enumerate(refs) if ref!=seal['archive'] and ref!=native.raw_ref(seal_path)}
    index['output']={'path':origin,'sha256':h}
    return task,cohort,bundle,manifest,index,closure

@pytest.mark.parametrize('operator',['maximum','dynamic_quant'])
def test_portable_full_roster_verification_never_needs_original_tree(tmp_path,operator):
    task,cohort,bundle,manifest,index,closure=portable_fixture(tmp_path,operator)
    task.rename(task.with_name(task.name+'-original-unavailable'))
    portable.verify_storage_closure(bundle,manifest,index)


def test_portable_rehashed_supplemental_seal_cannot_drop_unindexed_logical_output(tmp_path):
    task,cohort,bundle,manifest,index,closure=portable_fixture(tmp_path)
    old_key=next(iter(closure['archives']));entry=closure['archives'].pop(old_key);name=entry['files'][entry['seal']['path']]
    seal=json.loads((bundle/name).read_text());removed=seal['members'].pop();assert removed['path'] not in closure['origins']
    data=native.canonical(seal);new_hash=native.digest(data);new_name='evidence/sha256/'+new_hash[7:];blob(bundle/new_name,data)
    manifest['files'].pop(name);(bundle/name).unlink();manifest['files'][new_name]=portable.fingerprint(bundle/new_name)
    entry['files'][entry['seal']['path']]=new_name;entry['seal']['sha256']=new_hash
    closure['archives'][new_hash]=entry;closure['origins']={p:new_hash for p in closure['origins']}
    cname='storage-verification/bindings.json';save(bundle/cname,closure);manifest['files'][cname]=portable.fingerprint(bundle/cname);manifest['storage_closure']['sha256']=manifest['files'][cname]['sha256']
    with pytest.raises(ValueError,match='roster'):
        portable.verify_storage_closure(bundle,manifest,index)


def test_external_portable_verifier_does_not_execute_bundle_reader(tmp_path):
    task,cohort,bundle,manifest,index,closure=portable_fixture(tmp_path)
    marker=tmp_path/'executed';name='verifier/level2_native_output_storage.py'
    (bundle/name).write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n")
    manifest['files'][name]=portable.fingerprint(bundle/name)
    portable.verify_storage_closure(bundle,manifest,index);assert not marker.exists()

@pytest.mark.parametrize('failure',['archive_fsync','parent_fsync','seal_publish'])
def test_durability_failure_precedes_first_output_unlink(tmp_path,monkeypatch,failure):
    task,cohort,dest,original=fixture(tmp_path)
    if failure=='archive_fsync':
        monkeypatch.setattr(native.os,'fsync',lambda fd:(_ for _ in ()).throw(OSError('injected fsync')))
    elif failure=='seal_publish':
        base=dedup.write_new
        def fail(path,value):
            if Path(path).name=='seal.json':raise OSError('injected seal')
            return base(path,value)
        monkeypatch.setattr(dedup,'write_new',fail)
    else:
        base=dedup.sync_directory
        def fail(path):
            if Path(path)==cohort:raise OSError('injected parent sync')
            return base(path)
        monkeypatch.setattr(dedup,'sync_directory',fail)
    with pytest.raises(OSError):native.prepare(cohort,writers_closed=True,retire=True)
    assert all(Path(path).read_bytes()==data for path,data in original.items())


def test_partial_retirement_resumes_from_sealed_bytes(tmp_path,monkeypatch):
    task,cohort,dest,original=fixture(tmp_path,'dynamic_quant');base=Path.unlink;count=0
    def fail(path,*args,**kwargs):
        nonlocal count
        if str(path) in original:
            count+=1
            if count==3:raise OSError('crash during retire')
        return base(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',fail)
        with pytest.raises(OSError):native.prepare(cohort,writers_closed=True,retire=True)
    assert not (cohort/'native-output-storage/compacted.json').exists()
    assert native.prepare(cohort,writers_closed=True,retire=True)['status']=='complete'
    with verification.reader_session():
        assert all(verification.read_bytes(path)==data for path,data in original.items())


def test_dedup_before_retire_then_archived_noop_and_new_scope_aliases(tmp_path):
    task,cohort,dest,original=fixture(tmp_path);run=task.parents[2]
    before=dedup.deduplicate(run,cohort,kind='cohort',writers_closed=True,apply=True)
    assert before['status']=='passed'
    native.prepare(cohort,writers_closed=True,retire=True)
    after=dedup.deduplicate(run,cohort,kind='cohort',writers_closed=True,apply=True)
    assert after['status']=='verified_archived' and after['reclaimed_bytes']==0
    # A new independent ordinary output scope can still reuse the old CAS inode.
    from test_level2_storage import pilot
    _,_,scope,outputs=pilot(tmp_path,contents=(b'12345678',b'12345678'))
    following=dedup.deduplicate(run,scope,kind='pilot',writers_closed=True,apply=True)
    assert following['status']=='passed'
    pooled=run/'storage/output-cas'/native.digest(b'12345678')[7:]
    assert all(p.stat().st_ino==pooled.stat().st_ino for p in outputs)
    assert pooled.stat().st_nlink==3



def test_archive_pointer_preserves_original_identity_one_mapping_document(tmp_path):
    task,cohort,dest,original=fixture(tmp_path);native.prepare(cohort,writers_closed=True,retire=True)
    collector=archive.Archive.__new__(archive.Archive);collector.root=tmp_path/'artifact-archive';collector.artifacts={};collector.pointer_cache={}
    collector.safe=lambda path,owner=None:Path(path)
    with verification.reader_session():
        for origin,data in original.items():assert collector.pointer(origin,expected=native.digest(data))=={'path':origin,'sha256':native.digest(data)}
    assert len(list((collector.root/'documents').glob('*.json')))==1
    assert str(cohort/'native-output-storage/outputs.tar') in {r['path'] for r in collector.artifacts.values()}


def test_dataset_export_and_offline_verification_after_native_retirement(tmp_path):
    import subprocess
    from test_trace_v2_dataset import fixture_data
    task,cohort,dest,original=fixture(tmp_path,'dynamic_quant')
    evidence,body=fixture_data(tmp_path);origin=Path(next(iter(original)))
    body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    pointer=(root/'current.json').read_bytes();native.prepare(cohort,writers_closed=True,retire=True)
    assert dataset.verify(root,deep=True)['valid']
    bundle=tmp_path/'bundle';assert portable.export(root,bundle)['valid']
    assert (root/'current.json').read_bytes()==pointer
    task.rename(task.with_name('unavailable'));root.rename(root.with_name('dataset-unavailable'))
    assert portable.verify(bundle)['valid']
    result=subprocess.run([sys.executable,'-B',str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['valid']


def test_portable_revalidates_archive_before_publishing_destination(tmp_path,monkeypatch):
    from test_trace_v2_dataset import fixture_data
    task,cohort,dest,original=fixture(tmp_path)
    evidence,body=fixture_data(tmp_path);origin=Path(next(iter(original)));body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False});native.prepare(cohort,writers_closed=True,retire=True)
    base=portable.verify
    def verify_then_mutate(bundle):
        result=base(bundle);save(cohort.parent/'stage-plan.json',{'changed':True});return result
    monkeypatch.setattr(portable,'verify',verify_then_mutate)
    destination=tmp_path/'must-not-publish'
    with pytest.raises(ValueError):portable.export(root,destination)
    assert not destination.exists()


def test_rehashed_output_report_and_validation_cannot_replace_original_dedup_bytes(tmp_path):
    task,cohort,dest,original=fixture(tmp_path)
    output=cohort/'p01/native/1_normal_A.bin';output.write_bytes(b'CHANGED!');h=native.digest(output.read_bytes())
    path=cohort/'p01/validation.json';value=json.loads(path.read_text());value['outputs'][0]['output_hash']=h;save(path,value)
    path=cohort/'report.json';value=json.loads(path.read_text());value['sessions'][0]['artifacts'][str(output)]=h;save(path,value)
    with pytest.raises(ValueError,match='original dedup'):native.prepare(cohort,writers_closed=True,retire=True)
    assert all(Path(p).exists() for p in original)


def test_missing_preexisting_dedup_authority_blocks_without_creating_new_one(tmp_path):
    task,cohort,dest,original=fixture(tmp_path)
    event_path=task/'events.jsonl';event_path.write_bytes(event_path.read_bytes().splitlines(keepends=True)[0])
    with pytest.raises(ValueError,match='no previously event-bound'):
        native.prepare(cohort,writers_closed=True,retire=True)
    assert not (cohort/'native-output-storage').exists()


def test_native_portable_after_all_six_verification_trees_already_retired(tmp_path):
    from test_trace_v2_dataset import fixture_data
    task,cohort,dest,original=fixture(tmp_path)
    evidence,body=fixture_data(tmp_path);origin=Path(next(iter(original)));body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    for number in range(1,7):verification.prepare(cohort/f'p{number:02d}',writers_closed=True,retire=True)
    native.prepare(cohort,writers_closed=True,retire=True)
    bundle=tmp_path/'bundle';assert portable.export(root,bundle)['valid']
    task.rename(task.with_name('original-unavailable'))
    assert portable.verify(bundle)['valid']

def test_report_authority_v2_portable_after_verification_retirement(tmp_path):
    from test_trace_v2_dataset import fixture_data
    task,cohort,_,original=fixture(tmp_path)
    events=task/'events.jsonl';events.write_bytes(b''.join(events.read_bytes().splitlines(keepends=True)[:-1]))
    evidence,body=fixture_data(tmp_path);origin=Path(next(iter(original)))
    body['sources']['evidence_ids'].append(evidence.file(origin))
    root=tmp_path/'dataset';dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    for number in range(1,7):verification.prepare(cohort/f'p{number:02d}',writers_closed=True,retire=True)
    native.prepare(cohort,writers_closed=True,retire=True,report_authority=True)
    bundle=tmp_path/'bundle';assert portable.export(root,bundle)['valid']
    task.rename(task.with_name('original-unavailable'))
    assert portable.verify(bundle)['valid']


def test_native_supplemental_execution_rehash_still_rejected_by_original_dedup_index(tmp_path):
    task,cohort,bundle,manifest,index,closure=portable_fixture(tmp_path)
    origin=str(cohort/'p01/verification/1_normal_A/execution.json')
    # A minimal native-only signed index is legal. The copied supplemental
    # execution is still independently pinned by the prior dedup authority.
    index={k:r for k,r in index.items() if r['path']!=origin}
    entry=next(iter(closure['archives'].values()));old_name=entry['files'][origin]
    payload=native.canonical({'exit_code':0,'ended_at':1,'passed':True,'changed':True});h=native.digest(payload)
    new_name='evidence/sha256/'+h[7:];blob(bundle/new_name,payload);manifest['files'][new_name]=portable.fingerprint(bundle/new_name)
    entry['files'][origin]=new_name
    cname='storage-verification/bindings.json';save(bundle/cname,closure);manifest['files'][cname]=portable.fingerprint(bundle/cname);manifest['storage_closure']['sha256']=manifest['files'][cname]['sha256']
    with pytest.raises(ValueError,match='dedup index|proof'):
        portable.verify_storage_closure(bundle,manifest,index)


def test_unarchived_legacy_level1_output_keeps_ordinary_reader_behavior(tmp_path):
    path=tmp_path/'run/train/tasks/exp/stages/search/cohort/p01/native/1_normal_A.bin'
    blob(path,b'legacy bytes')
    assert native.resolve(path) is None
    assert verification.read_bytes(path)==b'legacy bytes'
    assert verification.is_file(path)
    assert verification.fingerprint(path)=={'sha256':native.digest(b'legacy bytes'),'size_bytes':12}
    assert report.sha(path)==native.digest(b'legacy bytes')


def test_declared_invalid_legacy_archive_cannot_fallback_to_ordinary_bytes(tmp_path):
    path=tmp_path/'run/train/tasks/exp/stages/search/cohort/p01/native/1_normal_A.bin'
    blob(path,b'legacy bytes');(path.parents[2]/'native-output-storage').mkdir()
    for read in (native.resolve,verification.read_bytes,verification.is_file,verification.fingerprint,report.sha):
        with pytest.raises(ValueError,match='unknown output operator'):read(path)

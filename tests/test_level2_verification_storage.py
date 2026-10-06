"""Archived bytes must preserve exact logical evidence, never reinterpret reports."""
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_verification_storage as store
# Load proposal readers before legacy imports can prepend another checkout.
import trace_v2_dataset as proposal_v2
import trace_v2_portable as proposal_portable
import msprof_exploration_report as proposal_report
import msprof_exploration_archive as proposal_archive
for module in (store,proposal_v2,proposal_portable,proposal_report,proposal_archive):
    assert Path(module.__file__).resolve().parent==Path(__file__).resolve().parents[1]/'scripts'
import level2_storage
from msprof_exploration_execute import event


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True)+'\n');return path


@pytest.fixture(autouse=True)
def locks(monkeypatch):
    @contextmanager
    def lock():yield
    monkeypatch.setattr(level2_storage,'exclusive_host',lock)


def fixture(tmp_path):
    task=tmp_path/'run/train/tasks/maximum';stage=task/'stages/aa';cohort=stage/'cohort';session=cohort/'p01'
    scope=session/'verification';artifacts={}
    for stem in ('1_normal_A','1_normal_B'):
        for name in store.NAMES:
            value={'exit_code':0,'ended_at':1} if name=='execution.json' else {'passed':True}
            path=save(scope/stem/name,value)
            if name!='result.json':artifacts[str(path)]=store.digest(path.read_bytes())
    save(stage/'result.json',{'status':'passed','error':None,'ended_at':2})
    save(stage/'stage-plan.json',{'version':'test','source_hash':'frozen'})
    save(cohort/'plan.json',{'version':'test','schedule':[]})
    save(cohort/'report.json',{'sessions':[{'directory':str(session),'artifacts':artifacts}]})
    save(cohort/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[str(cohort/f'p{i:02d}') for i in range(1,7)]})
    save(session/'completion.json',{'status':'passed','error':None})
    save(session/'msprof.execution.json',{'exit_code':0,'error':None,'ended_at':1})
    save(session/'native/journal.jsonl',{'type':'session_end','exit_code':0})
    save(session/'bindings.json',{})
    save(session/'validation.json',{'scope':'final_call_of_final_sample_per_case_config_role','outputs':[
        {'case_id':'1','buffer_config':'normal','role':r,'passed':True} for r in 'AB']})
    event(task,'stage_completed',{'result':store.raw_ref(stage/'result.json')})
    return task,session,tmp_path/'shadow'


def test_shadow_preserves_all_live_bytes_and_reads_exact_logical_identity(tmp_path):
    task,session,destination=fixture(tmp_path)
    before={str(p):p.read_bytes() for p in task.rglob('*') if p.is_file()}
    result=store.prepare(session,destination,writers_closed=True)
    assert result['status']=='sealed_shadow' and result['archived_files']==8
    assert {p:Path(p).read_bytes() for p in before}==before
    with store.reader_session({session:destination}):
        for path,data in before.items():
            if '/verification/' in path:
                assert store.read_bytes(path)==data and store.is_file(path)
                proof=store.evidence_binding(path,store.digest(data))
                assert proof['origin']=={'path':path,'sha256':store.digest(data)}
                assert proof['bytes']==data
        assert len(store.logical_files(session.parent))==8
    assert store.prepare(session,destination,writers_closed=True)==result


@pytest.mark.parametrize('target',['report','stage','group','session','execution','journal','event','source_plan'])
def test_closed_original_binding_is_required(tmp_path,target):
    task,session,destination=fixture(tmp_path)
    paths={'report':session.parent/'report.json','stage':session.parent.parent/'result.json',
           'group':session.parent/'group-completion.json','session':session/'completion.json',
           'execution':session/'msprof.execution.json','journal':session/'native/journal.jsonl',
           'event':task/'events.jsonl','source_plan':session.parent.parent/'stage-plan.json'}
    if target=='source_plan':paths[target].unlink()
    else:save(paths[target],{})
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):store.prepare(session,destination,writers_closed=True)
    assert (session/'verification/1_normal_A/metadata.json').exists()


@pytest.mark.parametrize('change',['archive','seal','producer','original','extra_file','extra_dir','symlink','missing_file','wrong_hash','foreign_scope'])
def test_strict_archive_and_full_path_identity(tmp_path,change):
    task,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    origin=session/'verification/1_normal_A/metadata.json'
    if change=='archive':(destination/'verification.tar').write_bytes(b'bad')
    elif change=='seal':save(destination/'seal.json',{})
    elif change=='producer':(destination/'producer.py').write_text('bad')
    elif change=='original':origin.write_text('bad')
    elif change=='extra_file':save(session/'verification/1_normal_A/extra.json',{})
    elif change=='extra_dir':(session/'verification/foreign').mkdir()
    elif change=='symlink':origin.unlink();origin.symlink_to(session/'completion.json')
    elif change=='missing_file':
        # Partial retirement is valid only because exact bytes remain sealed.
        origin.unlink()
        with store.reader_session({session:destination}):assert store.read_bytes(origin)
        return
    elif change=='wrong_hash':
        with store.reader_session({session:destination}):
            with pytest.raises(ValueError,match='hash differs'):store.evidence_binding(origin,'sha256:'+'0'*64)
        return
    elif change=='foreign_scope':
        fake=session.parent/'p02';fake.mkdir()
        with store.reader_session({fake:destination}):
            with pytest.raises(ValueError,match='identity'):store.read_bytes(fake/'verification/1_normal_A/metadata.json')
        return
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        with store.reader_session({session:destination}):store.read_bytes(origin)


def test_mutation_after_cached_read_is_rejected_before_reader_returns(tmp_path):
    task,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    with pytest.raises(ValueError,match='changed'):
        with store.reader_session({session:destination}):
            store.read_bytes(session/'verification/1_normal_A/metadata.json')
            save(session/'bindings.json',{'mutated':True})


def test_unrelated_event_append_does_not_change_stage_prefix(tmp_path):
    task,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    event(task,'later_source',{'candidate':'later'})
    assert store.verified(session,destination)['payloads']


def test_nonarchive_legacy_files_keep_normal_reader_behavior(tmp_path):
    p=save(tmp_path/'plain.json',{'hello':'world'});alias=tmp_path/'alias.json';alias.symlink_to(p)
    assert store.read_bytes(alias)==p.read_bytes() and store.resolve(alias) is None


def test_shadow_cannot_retire_live_tree(tmp_path):
    _,session,destination=fixture(tmp_path)
    with pytest.raises(ValueError,match='shadow archives'):store.prepare(session,destination,writers_closed=True,retire=True)
    assert (session/'verification/1_normal_A/metadata.json').exists()


def test_failed_context_entry_does_not_leak_cache(tmp_path):
    _,session,destination=fixture(tmp_path)
    with pytest.raises(FileNotFoundError):
        with store.reader_session({session:destination}):pass
    assert store._CACHE.get() is None and store._OVERRIDES.get() is None


def test_old_dataset_logical_refs_verify_and_export_after_files_are_archived(tmp_path):
    import trace_v2_dataset as v2
    import trace_v2_portable as portable
    from test_trace_v2_dataset import fixture_data
    task,session,destination=fixture(tmp_path)
    evidence,body=fixture_data(tmp_path)
    origin=session/'verification/1_normal_A/metadata.json'
    ref=evidence.file(origin);body['sources']['evidence_ids'].append(ref)
    root=tmp_path/'dataset'
    v2.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    pointer=(root/'current.json').read_bytes()
    store.prepare(session,destination,writers_closed=True)
    (session/'verification').rename(tmp_path/'preserved-loose-fixture')
    bundle=tmp_path/'bundle'
    with store.reader_session({session:destination}):
        assert v2.verify(root,deep=True)['valid']
        result=portable.export(root,bundle)
        assert result['valid'] and result['portable']
    assert (root/'current.json').read_bytes()==pointer
    manifest=json.loads((bundle/'bundle.json').read_bytes())
    assert manifest['storage_closure']['path']=='storage-verification/bindings.json'
    closure=json.loads((bundle/'storage-verification/bindings.json').read_bytes())
    assert str(origin) in closure['origins']
    # Offline verification must never reopen any original task/archive file.
    import shutil
    shutil.rmtree(task);shutil.rmtree(destination);shutil.rmtree(root)
    assert portable.verify(bundle)['valid']
    import subprocess
    output=subprocess.run([sys.executable,str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],cwd=tmp_path,text=True,capture_output=True,check=True)
    assert json.loads(output.stdout)['valid']


def test_archive_pointer_keeps_logical_identity_without_per_member_cas(tmp_path):
    import msprof_exploration_archive as archive
    _,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    origin=session/'verification/1_normal_A/metadata.json';expected=store.raw_ref(origin)
    (session/'verification').rename(tmp_path/'preserved-loose-fixture')
    collector=archive.Archive.__new__(archive.Archive)
    collector.root=tmp_path/'archive';collector.artifacts={};collector.pointer_cache={}
    collector.safe=lambda path,owner=None:Path(path)
    with store.reader_session({session:destination}):actual=collector.pointer(origin,expected=expected['sha256'])
    assert actual==expected
    assert not (collector.root/'verification-bytes').exists()
    refs={p['path'] for p in collector.artifacts.values()}
    assert str(destination/'verification.tar') in refs and str(destination/'seal.json') in refs
    assert str(origin) in refs


def test_real_retirement_is_resumable_and_keeps_logical_bytes_in_tmp_fixture(tmp_path):
    _,session,_=fixture(tmp_path)
    original={str(p):p.read_bytes() for p in (session/'verification').rglob('*') if p.is_file()}
    result=store.prepare(session,writers_closed=True,retire=True)
    assert result['status']=='complete' and not (session/'verification').exists()
    assert store.prepare(session,writers_closed=True,retire=True)==result
    with store.reader_session():
        for path,data in original.items():assert store.read_bytes(path)==data
    assert store.logical_files(session)==sorted(original)


@pytest.mark.parametrize('failure',['archive_fsync','seal_publish','one_unlink','receipt_publish'])
def test_retirement_faults_preserve_archive_or_original_bytes(tmp_path,monkeypatch,failure):
    _,session,_=fixture(tmp_path);original={str(p):p.read_bytes() for p in (session/'verification').rglob('*') if p.is_file()}
    original_fsync=store.os.fsync;original_write=level2_storage.write_new;original_unlink=Path.unlink;fired=False
    def fsync(fd):
        nonlocal fired
        path=store.os.readlink('/proc/self/fd/'+str(fd))
        if failure=='archive_fsync' and path.endswith('/verification.tar') and not fired:
            fired=True;raise OSError('injected archive fsync')
        return original_fsync(fd)
    def write(path,value):
        nonlocal fired
        target='seal.json' if failure=='seal_publish' else 'compacted.json'
        if failure in ('seal_publish','receipt_publish') and path.name==target and not fired:
            fired=True;raise OSError('injected publication')
        return original_write(path,value)
    def unlink(path,*a,**kw):
        nonlocal fired
        if failure=='one_unlink' and path.name in store.NAMES and path.parent.parent.name=='verification' and not fired:
            fired=True;original_unlink(path,*a,**kw);raise OSError('injected retirement')
        return original_unlink(path,*a,**kw)
    monkeypatch.setattr(store.os,'fsync',fsync);monkeypatch.setattr(level2_storage,'write_new',write);monkeypatch.setattr(Path,'unlink',unlink)
    with pytest.raises(OSError,match='injected'):store.prepare(session,writers_closed=True,retire=True)
    assert fired
    if (session/'verification-storage/seal.json').exists():assert store.verified(session)['payloads']==original
    else:assert all(Path(p).read_bytes()==data for p,data in original.items())
    monkeypatch.setattr(store.os,'fsync',original_fsync);monkeypatch.setattr(level2_storage,'write_new',original_write);monkeypatch.setattr(Path,'unlink',original_unlink)
    assert store.prepare(session,writers_closed=True,retire=True)['status']=='complete'
    assert store.verified(session)['payloads']==original


def test_one_mapping_document_per_archive_not_per_logical_member(tmp_path):
    import msprof_exploration_archive as archive
    _,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    collector=archive.Archive.__new__(archive.Archive)
    collector.root=tmp_path/'archive';collector.artifacts={};collector.pointer_cache={}
    collector.safe=lambda path,owner=None:Path(path)
    with store.reader_session({session:destination}):
        for path in store.logical_files(session):collector.pointer(path)
    assert len(list((collector.root/'documents').glob('*.json')))==1
    assert not (collector.root/'verification-bytes').exists()


def test_archive_directory_entry_is_durable_before_first_unlink(tmp_path,monkeypatch):
    _,session,_=fixture(tmp_path);seen=[]
    sync=level2_storage.sync_directory;unlink=Path.unlink
    def tracked_sync(path):seen.append(('sync',Path(path)));return sync(path)
    def tracked_unlink(path,*args,**kwargs):
        if path.name in store.NAMES and path.parent.parent.name=='verification':
            assert ('sync',session/'verification-storage') in seen
            assert ('sync',session) in seen
            seen.append(('unlink',path))
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(level2_storage,'sync_directory',tracked_sync);monkeypatch.setattr(Path,'unlink',tracked_unlink)
    store.prepare(session,writers_closed=True,retire=True)
    assert any(kind=='unlink' for kind,path in seen)


# Independent reviewer reproductions retained as regressions.
def test_portable_must_preserve_entire_sealed_verification_roster(tmp_path):
    import sys,importlib,json,tarfile,io
    portable=importlib.import_module('trace_v2_portable')
    import test_level2_verification_storage as fixtures
    fixtures.test_old_dataset_logical_refs_verify_and_export_after_files_are_archived(tmp_path)
    bundle=tmp_path/'bundle';manifest=json.loads((bundle/'bundle.json').read_bytes())
    closure_path=bundle/'storage-verification/bindings.json';closure=json.loads(closure_path.read_bytes())
    oldkey,entry=next(iter(closure['archives'].items()))
    seal=json.loads((bundle/entry['files'][entry['seal']['path']]).read_bytes())
    tar_path=bundle/entry['files'][seal['archive']['path']]
    removed='1_normal_B/stdout.log'
    buf=io.BytesIO()
    with tarfile.open(tar_path,'r:') as source,tarfile.open(fileobj=buf,mode='w') as target:
        for member in source.getmembers():
            if member.name!=removed:target.addfile(member,source.extractfile(member))
    def replace(ref,data):
        oldname=entry['files'][ref['path']];oldpath=bundle/oldname
        h=store.digest(data);name='evidence/sha256/'+h[7:];(bundle/name).write_bytes(data)
        oldpath.unlink();manifest['files'].pop(oldname)
        manifest['files'][name]=portable.fingerprint(bundle/name);entry['files'][ref['path']]=name;ref['sha256']=h
    replace(seal['archive'],buf.getvalue())
    seal['members']=[r for r in seal['members'] if r['relative_path']!=removed]
    replace(entry['seal'],store.canonical(seal))
    newkey=entry['seal']['sha256'];closure['archives']={newkey:entry}
    closure['origins']={k:newkey for k in closure['origins']}
    closure_path.write_bytes(store.canonical(closure))
    manifest['files']['storage-verification/bindings.json']=portable.fingerprint(closure_path)
    manifest['storage_closure']['sha256']=store.digest(closure_path.read_bytes())
    (bundle/'bundle.json').write_bytes(store.canonical(manifest))
    # All signed logical bytes remain unchanged; only an originally sealed member
    # is dropped from the supplemental archive. The claimed full closure must fail.
    with pytest.raises(ValueError):portable.verify(bundle)

@pytest.mark.parametrize('mutation',['bytes','symlink','hardlink','traversal','foreign_scope'])
def test_logical_archive_rehash_cannot_replace_original_bound_identity(tmp_path,mutation):
    import json,tarfile,io,shutil
    _,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    shutil.rmtree(session/'verification')
    seal_path=destination/'seal.json';seal=json.loads(seal_path.read_bytes());archive=destination/'verification.tar'
    buf=io.BytesIO();targetname='1_normal_A/metadata.json'
    with tarfile.open(archive,'r:') as source,tarfile.open(fileobj=buf,mode='w') as target:
        for member in source.getmembers():
            data=source.extractfile(member).read()
            if member.name==targetname:
                row=next(r for r in seal['members'] if r['relative_path']==targetname)
                if mutation=='bytes':
                    data=b'{"forged":true}\n';member.size=len(data);row.update(size_bytes=len(data),sha256=store.digest(data))
                elif mutation in ('symlink','hardlink'):
                    member.type=tarfile.SYMTYPE if mutation=='symlink' else tarfile.LNKTYPE;member.linkname='/tmp/foreign';member.size=0;row['size_bytes']=0
                elif mutation=='traversal':
                    member.name='../metadata.json';row.update(relative_path=member.name,path=str(session/'metadata.json'))
                elif mutation=='foreign_scope':row['path']=str(session.parent/'p02/verification'/targetname)
            target.addfile(member,io.BytesIO(data) if member.isfile() else None)
    archive.write_bytes(buf.getvalue());seal['archive']=store.raw_ref(archive);seal_path.write_bytes(store.canonical(seal))
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        with store.reader_session({session:destination}):store.read_bytes(session/'verification'/targetname)

def test_trusted_verifier_must_not_execute_helper_from_untrusted_bundle(tmp_path):
    import sys,importlib,json
    portable=importlib.import_module('trace_v2_portable')
    import test_level2_verification_storage as fixtures
    fixtures.test_old_dataset_logical_refs_verify_and_export_after_files_are_archived(tmp_path)
    bundle=tmp_path/'bundle';manifest=json.loads((bundle/'bundle.json').read_bytes())
    helper=bundle/'verifier/level2_verification_storage.py';marker=tmp_path/'untrusted-helper-executed'
    helper.write_text(helper.read_text()+f'\nfrom pathlib import Path as _ReviewPath\n_ReviewPath({str(marker)!r}).write_text("executed")\n')
    manifest['files']['verifier/level2_verification_storage.py']=portable.fingerprint(helper)
    (bundle/'bundle.json').write_bytes(store.canonical(manifest))
    try:portable.verify(bundle)
    except ValueError:pass
    assert not marker.exists(),'trusted verification executed a self-rehashed bundle payload'


def test_explicit_precommit_revalidation_rejects_mutation_before_publication(tmp_path):
    _,session,destination=fixture(tmp_path);store.prepare(session,destination,writers_closed=True)
    committed=False
    with pytest.raises(ValueError,match='changed'):
        with store.reader_session({session:destination}):
            store.read_bytes(session/'verification/1_normal_A/metadata.json')
            save(session/'bindings.json',{'changed':True})
            store.reverify_cached()
            committed=True
    assert not committed


def test_legacy_portable_v1_without_storage_remains_readable(tmp_path):
    from test_trace_v2_dataset import publication
    root,_,_,_=publication(tmp_path)
    bundle=tmp_path/'legacy-bundle';proposal_portable.export(root,bundle)
    manifest=json.loads((bundle/'bundle.json').read_bytes())
    assert manifest.pop('storage_closure') is None
    manifest['version']=proposal_portable.LEGACY_VERSION
    (bundle/'bundle.json').write_bytes(store.canonical(manifest))
    assert proposal_portable.verify(bundle)['valid']


def test_output_dedup_index_reader_retains_exact_archived_proof_and_rejects_changes(tmp_path):
    _,session,_=fixture(tmp_path)
    origin=session/'verification/1_normal_A/execution.json';original=store.raw_ref(origin)
    store.prepare(session,writers_closed=True,retire=True)
    inventory=level2_storage.Inventory.__new__(level2_storage.Inventory)
    inventory.run=tmp_path;inventory.evidence={}
    assert inventory.read(origin,original['sha256'])['exit_code']==0
    assert inventory.evidence=={str(origin):original['sha256']}
    inventory.recheck_evidence()
    with pytest.raises(ValueError,match='hash differs'):inventory.read(origin,'sha256:'+'0'*64)
    save(session/'bindings.json',{'changed':True})
    with pytest.raises(ValueError,match='changed'):inventory.recheck_evidence()


def test_output_file_hashing_never_accepts_archive_substitution(tmp_path):
    _,session,_=fixture(tmp_path)
    origin=session/'verification/1_normal_A/execution.json'
    store.prepare(session,writers_closed=True,retire=True)
    with pytest.raises(FileNotFoundError):level2_storage.digest(origin)


def test_closed_output_dedup_recover_and_known_aliases_after_full_verification_retirement(tmp_path):
    from test_level2_storage import cohort
    run,stage,scope,outputs=cohort(tmp_path);task=stage.parent.parent
    sessions=[]
    for session in sorted(p for p in scope.iterdir() if p.is_dir()):
        artifacts={}
        for directory in (session/'verification').iterdir():
            for name in store.NAMES:
                path=directory/name
                if not path.exists():save(path,{'passed':True})
                if name!='result.json':artifacts[str(path)]=store.raw_ref(path)['sha256']
        save(session/'bindings.json',{})
        sessions.append({'directory':str(session),'artifacts':artifacts})
    save(scope/'report.json',{'sessions':sessions})
    event(task,'stage_completed',{'result':store.raw_ref(stage/'result.json')})
    before=level2_storage.deduplicate(run,stage,kind='stage',writers_closed=True,apply=True)
    assert before['status']=='passed'
    for row in sessions:store.prepare(Path(row['directory']),writers_closed=True,retire=True)
    after=level2_storage.deduplicate(run,stage,kind='stage',writers_closed=True,apply=True)
    assert after['status']=='passed' and after['reclaimed_bytes']==0
    assert len(after['results'])==24 and len({p.stat().st_ino for p in outputs})==1

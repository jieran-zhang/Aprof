"""Synthetic CPU-only final authority + complete raw catalog export.

The attestor uses its explicit fake analyzer; these fixtures prove storage trust
and closure, not accelerator measurements or performance.
"""
import contextlib
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from test_level2_raw_storage_integration import (raw,storage,verification,native,report,archive,dataset,portable,
                                                dataset_for,rehash_bundle,tiny,HERE)
from test_level2_raw_archive_storage import save
import test_msprof_raw_storage as captured

from final_storage_fixture import Small,a,FIXTURE_ROOT,provision_storage
spec=importlib.util.spec_from_file_location('authority_for_composed_test',HERE/'scaffolding/collection/scripts/level2_final_report_authority.py')
final_authority=importlib.util.module_from_spec(spec);spec.loader.exec_module(final_authority)


def load(path):return json.loads(Path(path).read_bytes())

_dataset_for=dataset_for
def dataset_for(directory,paths):
    directory.mkdir(parents=True,exist_ok=True)
    return _dataset_for(directory,paths)

def build_final(tmp_path,monkeypatch,catalog_origin=None):
    import test_level2_finalize as final_fixture
    original_save=final_fixture.save
    def save_result(path,value):
        if Path(path).name=='result.json' and Path(path).parent.name=='final':value={**value,'ended_at':200}
        return original_save(path,value)
    monkeypatch.setattr(final_fixture,'save',save_result)
    from test_msprof_exploration_report import make_session as original_make
    counter=[0]
    class FullFinal(Small):
        def make_report(self,directory,plan,hashes):
            super().make_report(directory,plan,hashes)
            if directory.parent.name!='final' or directory.parent.parent.parent.name!='maximum002':return
            saved=load(directory/'report.json');rows=[]
            for row in plan['schedule']:
                shutil.rmtree(directory/row['name'])
                def make(path,*args,**kwargs):return original_make(directory,*args,**kwargs,name=row['name'])
                with monkeypatch.context() as m:
                    m.setattr(captured,'make_session',make)
                    session,req,build=captured.v2_session(tmp_path/'captures'/str(counter[0]));counter[0]+=1
                    (session/'raw/unused/empty').mkdir(parents=True)
                    (session/'raw/unused/extra.bin').write_bytes(b'noncsv\x00whole-roster')
                    req=captured.localize(session,req);observed=report.verify_observation(session,req)
                    for p in (session/'verification').iterdir():save(p/'result.json',{'passed':True})
                if catalog_origin is not None:
                    for origin in (catalog_origin if isinstance(catalog_origin,list) else [catalog_origin]):
                        observed['artifacts'][str(origin)]=storage.fingerprint(origin)['sha256']
                rows.append(observed)
            saved.update(protocol=report.PROTOCOL_V2,sessions=rows)
            save(directory/'report.json',saved);self.runtime.expected[rows[0]['directory']]=deepcopy(saved)
    s=FullFinal(tmp_path/'final-run',monkeypatch)
    provision_storage(s)
    from msprof_exploration_execute import event
    for cid in ('maximum002','maximum003'):
        result=s.task/'candidates'/cid/'stages/final/result.json'
        event(s.task,'stage_completed',{'result':raw.pointer(result)})
    s.runtime.read=storage.read_bytes
    s.runtime.fingerprint=lambda p:storage.fingerprint(p)['sha256']
    s.runtime.binding=storage.evidence_binding
    s.runtime.reader_session=storage.reader_session
    s.runtime.reverify=storage.reverify_cached
    result=s.apply()
    session=s.task/'candidates/maximum002/stages/final/direct_parent/p0'
    f=final_authority.authority(session,storage.read_bytes)
    assert f['historical_report_authority'] is False
    return s,session,result


@pytest.fixture
def final_case(tmp_path,monkeypatch):
    monkeypatch.setattr(raw,'host_lock',lambda:contextlib.nullcontext())
    return build_final(tmp_path,monkeypatch)


def test_final_requires_separate_authority_then_new_raw_v2(final_case,tmp_path):
    s,session,result=final_case
    before=report.verify_observation(session)
    seal_result=raw.prepare(session,writers_closed=True,retire=True)
    assert seal_result['version']==raw.VERSION
    seal=load(seal_result['seal']['path'])
    assert seal['closed_evidence']['report_authority']['kind']=='retrospective_final_report_authority_v1'
    assert report.verify_observation(session)==before
    ds=dataset_for(tmp_path/'dataset-input',[session/'raw/unused/extra.bin']);bundle=tmp_path/'bundle'
    portable.export(ds,bundle)
    assert load(bundle/'storage-verification/bindings.json')['version']=='level2_storage_portable_v5'
    shutil.rmtree(s.run);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']


def test_legacy_raw_rejects_final_even_with_retrospective_authority(final_case):
    _,session,_=final_case
    with pytest.raises(ValueError,match='unsupported'):raw.cohort_facts(session,version=raw.LEGACY_VERSION)


def test_final_no_committed_authority_never_creates_destination(final_case,tmp_path):
    s,session,result=final_case
    events=s.task/'events.jsonl';rows=[json.loads(v) for v in events.read_bytes().splitlines()]
    assert rows[-1]['kind']=='final_report_consistency_attested'
    events.write_bytes(b''.join(verification.canonical(v) for v in rows[:-1]))
    target=tmp_path/'unissued-shadow'
    with pytest.raises(ValueError):raw.prepare(session,target,writers_closed=True)
    assert not target.exists()


@contextlib.contextmanager
def original_raw_writer(monkeypatch):
    """Run exact reviewed 43d writer against exact 452 reader on tiny fixtures."""
    base=FIXTURE_ROOT/'raw_v1'
    expected={'level2_raw_archive_storage.py':'43d246d2dbde09f3d6a0814bf1d7fac4bd66d26cd4e77134f796a3812ed6b4d0',
              'level2_verification_storage.py':'452c479151a6d0a9be43df4388a68f6577f0212c2fbd005c4501dbd8f43d7594'}
    for name,h in expected.items():assert raw.fingerprint(base/name)['sha256']=='sha256:'+h
    v_spec=importlib.util.spec_from_file_location('level2_verification_storage',base/'level2_verification_storage.py')
    old_v=importlib.util.module_from_spec(v_spec);v_spec.loader.exec_module(old_v)
    spec=importlib.util.spec_from_file_location('original_43d_writer',base/'level2_raw_archive_storage.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    nspec=importlib.util.spec_from_file_location('level2_native_output_storage',FIXTURE_ROOT/'approved_v3/level2_native_output_storage.py')
    old_n=importlib.util.module_from_spec(nspec);nspec.loader.exec_module(old_n)
    with monkeypatch.context() as m:
        m.setitem(sys.modules,'level2_native_output_storage',old_n)
        m.setitem(sys.modules,'level2_verification_storage',old_v)
        m.setattr(old,'host_lock',lambda:contextlib.nullcontext())
        # These synthetic captures use the current transport. Keep the exact
        # historical authority/closure writer; only admit that fixture transport.
        m.setattr(old,'CAPTURE_SHA',raw.CURRENT_CAPTURE_SHA)
        yield old


def test_real_43d_v1_seal_facts_receipt_report_and_portable_remain_exact(tiny,tmp_path,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0]
    before=report.verify_observation(s)
    with original_raw_writer(monkeypatch) as old:
        expected=old.cohort_facts(s)
        result=old.prepare(s,writers_closed=True,retire=True)
    sealpath=Path(result['seal']['path']);receipt=sealpath.with_name('compacted.json')
    sealbytes=sealpath.read_bytes();receiptbytes=receipt.read_bytes()
    assert raw.cohort_facts(s,version=raw.LEGACY_VERSION)==expected
    assert raw.prepare(s,writers_closed=True,retire=True)==result
    assert report.verify_observation(s)==before
    assert sealpath.read_bytes()==sealbytes and receipt.read_bytes()==receiptbytes
    ds=dataset_for(tmp_path/'legacy-dataset',[s/'raw/unused/extra.bin']);bundle=tmp_path/'legacy-bundle'
    portable.export(ds,bundle)
    assert load(bundle/'storage-verification/bindings.json')['version']=='level2_storage_portable_v4'
    shutil.rmtree(s.parents[4]);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']


def catalog_fixture(tiny,tmp_path,monkeypatch):
    task,sessions,*_=tiny;session=sessions[0];origin=session/'raw/unused/extra.bin'
    with original_raw_writer(monkeypatch) as old:old.prepare(session,writers_closed=True,retire=True)
    s,final_session,result=build_final(tmp_path/'final-fixture',monkeypatch,origin)
    raw.prepare(final_session,writers_closed=True,retire=True)
    return task,session,s,final_session,result


def test_final_catalog_retains_actual_old_raw_tar_all_members_once(tiny,tmp_path,monkeypatch):
    task,prior,s,session,result=catalog_fixture(tiny,tmp_path,monkeypatch)
    origin=session/'raw/unused/extra.bin';ds=dataset_for(tmp_path/'input',[origin]);bundle=tmp_path/'bundle'
    portable.export(ds,bundle)
    closure=load(bundle/'storage-verification/bindings.json')
    assert closure['version']=='level2_storage_portable_v5' and len(closure['archives'])==2
    priororigin=str(prior/'raw/unused/extra.bin')
    assert priororigin in closure['dependencies'] and priororigin not in closure['origins']
    # Every original raw member, including unindexed non-CSV files, is in full tar.
    for entry in closure['archives'].values():
        seal=load(bundle/entry['files'][entry['seal']['path']])
        assert seal['archive']['path'] in entry['files']
    collector=archive.Archive.__new__(archive.Archive)
    collector.root=tmp_path/'collected';collector.artifacts={};collector.pointer_cache={};collector.safe=lambda p,owner=None:Path(p)
    collector.run=s.run;collector.split='train'
    # This synthetic catalog spans two runs. The portable authenticated reader
    # can replay it, but a split-isolated campaign collector must reject the
    # foreign ledger instead of silently widening its task boundary.
    with pytest.raises(ValueError,match='outside the current run/split'):
        with storage.reader_session():collector.pointer(origin,expected=storage.fingerprint(origin)['sha256'])
    shutil.rmtree(task.parents[2]);shutil.rmtree(s.run);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']


def exported_catalog(tiny,tmp_path,monkeypatch):
    task,prior,s,session,result=catalog_fixture(tiny,tmp_path,monkeypatch)
    ds=dataset_for(tmp_path/'input',[session/'raw/unused/extra.bin']);bundle=tmp_path/'bundle'
    portable.export(ds,bundle)
    return bundle,task,prior,s,session


def rewrite_closure(bundle,closure):
    name='storage-verification/bindings.json';save(bundle/name,closure);rehash_bundle(bundle,name)
    manifest=load(bundle/'bundle.json');manifest['storage_closure']['sha256']=manifest['files'][name]['sha256'];save(bundle/'bundle.json',manifest)


@pytest.mark.parametrize('fault',['missing_catalog_origin','wrong_origin_sha','wrong_seal','missing_nested_tar','missing_nested_producer','missing_nested_proof','unindexed_raw_byte','catalog_only','downgrade'])
def test_complete_catalog_cannot_be_replaced_by_just_self_hashed_metadata(tiny,tmp_path,monkeypatch,fault):
    bundle,task,prior,s,session=exported_catalog(tiny,tmp_path,monkeypatch)
    closure=load(bundle/'storage-verification/bindings.json')
    origin=str(prior/'raw/unused/extra.bin');key=closure['dependencies'][origin]['seal'];entry=closure['archives'][key]
    seal=load(bundle/entry['files'][entry['seal']['path']])
    if fault=='missing_catalog_origin':del closure['dependencies'][origin]
    elif fault=='wrong_origin_sha':closure['dependencies'][origin]['sha256']='sha256:'+'0'*64
    elif fault=='wrong_seal':closure['dependencies'][origin]['seal']=closure['origins'][str(session/'raw/unused/extra.bin')]
    elif fault in ('missing_nested_tar','missing_nested_producer','missing_nested_proof'):
        ref=seal['archive'] if fault=='missing_nested_tar' else seal['producer_snapshot'] if fault=='missing_nested_producer' else seal['closed_evidence']['protected'][0]
        del entry['files'][ref['path']]
    elif fault=='catalog_only':
        closure['dependencies']={};del closure['archives'][key]
    elif fault=='downgrade':closure['version']='level2_storage_portable_v4'
    elif fault=='unindexed_raw_byte':
        import tarfile
        target=entry['files'][seal['archive']['path']]
        with tarfile.open(bundle/target,'r:') as tf:offset=tf.getmember('unused/extra.bin').offset_data
        with (bundle/target).open('r+b') as stream:stream.seek(offset);stream.write(b'X')
        rehash_bundle(bundle,target)
    rewrite_closure(bundle,closure)
    with pytest.raises((ValueError,KeyError)):portable.verify(bundle)


def test_current_verifier_never_executes_bundle_chosen_authority(tiny,tmp_path,monkeypatch):
    bundle,task,prior,s,session=exported_catalog(tiny,tmp_path,monkeypatch)
    marker=tmp_path/'executed'
    for name in ('level2_final_report_authority.py','level2_evidence_storage.py'):
        relative='verifier/'+name;(bundle/relative).write_text('open('+repr(str(marker))+',"w").write("executed")\n');rehash_bundle(bundle,relative)
    assert portable.verify(bundle)['valid'] and not marker.exists()


def test_final_catalog_composes_raw_native_verification_full_closure_offline(tiny,tmp_path,monkeypatch):
    from test_level2_raw_storage_integration import add_native_authority
    task,sessions,cohort=add_native_authority(tiny,monkeypatch);prior=sessions[0]
    native.prepare(cohort,writers_closed=True,retire=True)
    for session in sessions:verification.prepare(session,writers_closed=True,retire=True)
    origins=[prior/'raw/unused/extra.bin',prior/'native/1_normal_A.bin',prior/'verification/1_normal_A/metadata.json']
    with original_raw_writer(monkeypatch) as old:old.prepare(prior,writers_closed=True,retire=True)
    s,session,_=build_final(tmp_path/'nested-final',monkeypatch,origins)
    raw.prepare(session,writers_closed=True,retire=True)
    ds=dataset_for(tmp_path/'input',[session/'raw/unused/extra.bin']);bundle=tmp_path/'bundle'
    portable.export(ds,bundle)
    closure=load(bundle/'storage-verification/bindings.json')
    assert len(closure['archives'])==9 and all(str(p) in closure['dependencies'] for p in origins)
    shutil.rmtree(task.parents[2]);shutil.rmtree(s.run);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']
    import subprocess
    result=subprocess.run([sys.executable,'-B',str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],
                          cwd='/tmp',env={**os.environ,'PYTHONPATH':''},capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['original_evidence_locations_accessed'] is False


def test_final_verification_v3_does_not_expand_historical_v2(final_case,tmp_path,monkeypatch):
    _,session,_=final_case
    with pytest.raises(ValueError,match='protocol v3'):
        verification.facts_for_version(session,storage.read_bytes,verification.ANCHORED_VERSION)
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',lambda:contextlib.nullcontext())
    result=verification.prepare(session,writers_closed=True,retire=True)
    assert load(result['seal']['path'])['version']==verification.FINAL_VERSION
    origin=session/'verification/1_normal_A/metadata.json'
    ds=dataset_for(tmp_path/'input',[origin]);bundle=tmp_path/'portable'
    portable.export(ds,bundle)
    assert load(bundle/'storage-verification/bindings.json')['version']=='level2_storage_portable_v5'
    assert portable.verify(bundle)['valid']


def test_catalog_slots_are_explicit_and_unknown_embedded_dicts_do_not_grant_authority():
    fake={'kind':'retrospective_final_report_authority_v1','storage_catalog':{'not':'accepted'}}
    assert storage.catalog_bindings({'arbitrary':fake,'sessions':[{'not_facts':fake}]})=={'archives':{},'origins':{}}
    with pytest.raises((ValueError,KeyError)):storage.catalog_bindings({'report_authority':fake})


@pytest.mark.parametrize('fault',['wrong_bytes','not_bytes','unknown_extra','raw_with_bytes'])
def test_facade_rejects_forged_or_unknown_transient_binding_payload(tmp_path,monkeypatch,fault):
    data=b'verified metadata';digest=raw.digest(data) if hasattr(raw,'digest') else 'sha256:'+raw.hashlib.sha256(data).hexdigest()
    row={'version':verification.VERSION,'origin':{'path':str(tmp_path/'logical'),'sha256':digest},
         'seal':{},'archive':{},'producer':{},'closed_evidence':{},'bytes':data}
    if fault=='wrong_bytes':row['bytes']=b'forged'
    elif fault=='not_bytes':row['bytes']='verified metadata'
    elif fault=='unknown_extra':row['unexpected']='ignored'
    else:row['version']=raw.LEGACY_VERSION
    monkeypatch.setattr(verification,'evidence_binding',lambda *a,**k:row)
    with pytest.raises(ValueError):storage.evidence_binding(tmp_path/'logical')



def test_collector_failed_catalog_retention_cannot_poison_retry_cache(tiny,tmp_path,monkeypatch):
    task,sessions,*_=tiny;session=sessions[0]
    raw.prepare(session,writers_closed=True,retire=True)
    origin=session/'raw/unused/extra.bin';binding=storage.evidence_binding(origin,storage.fingerprint(origin)['sha256'])
    collector=archive.Archive.__new__(archive.Archive)
    collector.root=tmp_path/'collected';collector.artifacts={};collector.pointer_cache={};collector.safe=lambda p,owner=None:Path(p)
    collector.run=task.parents[2];collector.split=task.parents[1].name
    original=collector.pointer;called=[False]
    def fail_once(path,*args,**kwargs):
        if str(path)==binding['archive']['path'] and not called[0]:
            called[0]=True;raise OSError('synthetic interruption before full retention')
        return original(path,*args,**kwargs)
    collector.pointer=fail_once
    with pytest.raises(OSError):collector.retain_storage_binding(binding,None)
    assert not collector._retained_storage_bindings and not collector._retaining_storage_bindings
    collector.retain_storage_binding(binding,None)
    assert binding['seal']['sha256'] in collector._retained_storage_bindings
    assert binding['archive']['path'] in {r['path'] for r in collector.artifacts.values()}


def test_partial_original_v1_retirement_resumes_without_rewriting_seal(tiny,monkeypatch):
    _,sessions,*_=tiny;session=sessions[0]
    with original_raw_writer(monkeypatch) as old:
        count=[0];remove=old.remove_file
        def interrupt(path,expected):
            remove(path,expected);count[0]+=1
            if count[0]==2:raise OSError('old v1 interrupted after two removals')
        monkeypatch.setattr(old,'remove_file',interrupt)
        with pytest.raises(OSError):old.prepare(session,writers_closed=True,retire=True)
    sealpath=session/'raw-archive-storage/seal.json';before=sealpath.read_bytes()
    original_tar=raw.pointer(sealpath.with_name('raw.tar'))
    from msprof_exploration_execute import event
    event(session.parents[3],'unrelated_later_work',{'retained_v1':True})
    result=raw.prepare(session,writers_closed=True,retire=True)
    assert result['version']==raw.LEGACY_VERSION and result['status']=='complete'
    assert sealpath.read_bytes()==before and raw.pointer(sealpath.with_name('raw.tar'))==original_tar
    assert load(sealpath.with_name('compacted.json'))['version']==raw.LEGACY_VERSION


@contextlib.contextmanager
def original_raw_v2_writer(monkeypatch):
    base=FIXTURE_ROOT/'raw_v2'
    expected={'level2_raw_archive_storage.py':'68742f237190c2c5869b2e0ed916f9e480abc3c3a45f72d9b531ee92662cc864',
              'level2_verification_storage.py':'78ff7dfc3d7494c074b9dd6a2d3d316d35efe50d288584cee5f391cd84fae1eb',
              'level2_native_output_storage.py':'a08bb1813cb7503b58ba95d9f1a780c61a433c955dbc8dd2254b66ac5985787c'}
    with monkeypatch.context() as m:
        for name in ('level2_native_output_storage','level2_verification_storage'):
            source=base/(name+'.py');assert raw.fingerprint(source)['sha256']=='sha256:'+expected[source.name]
            spec=importlib.util.spec_from_file_location(name,source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);m.setitem(sys.modules,name,module)
        source=base/'level2_raw_archive_storage.py';assert raw.fingerprint(source)['sha256']=='sha256:'+expected[source.name]
        spec=importlib.util.spec_from_file_location('original_687_writer',source);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        m.setattr(old,'host_lock',lambda:contextlib.nullcontext())
        # Current synthetic capture, exact historical authority and seal facts.
        m.setattr(old,'CAPTURE_SHA',raw.CURRENT_CAPTURE_SHA)
        yield old


def test_real_687_v2_seal_replays_exactly_after_recovery_reader(tiny,tmp_path,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];before=report.verify_observation(s)
    with original_raw_v2_writer(monkeypatch) as old:
        expected=old.cohort_facts(s);result=old.prepare(s,writers_closed=True,retire=True)
    sealpath=Path(result['seal']['path']);receipt=sealpath.with_name('compacted.json');frozen=(sealpath.read_bytes(),receipt.read_bytes())
    assert raw.cohort_facts(s,version=raw.PRE_RECOVERY_VERSION)==expected
    assert expected['authority_producer_hashes']=={'level2_verification_storage.py':raw.PRE_RECOVERY_AUTHORITY_SHA,'level2_native_output_storage.py':raw.LEGACY_NATIVE_SHA}
    assert raw.prepare(s,writers_closed=True,retire=True)==result
    assert report.verify_observation(s)==before
    assert (sealpath.read_bytes(),receipt.read_bytes())==frozen
    ds=dataset_for(tmp_path/'v2-dataset',[s/'raw/unused/extra.bin']);bundle=tmp_path/'v2-bundle';portable.export(ds,bundle)
    shutil.rmtree(s.parents[4]);shutil.rmtree(ds);assert portable.verify(bundle)['valid']


def test_final_catalog_retains_new_v3_raw_before_final_seal(tiny,tmp_path,monkeypatch):
    task,sessions,*_=tiny;prior=sessions[0];origin=prior/'raw/unused/extra.bin'
    sealed=raw.prepare(prior,writers_closed=True,retire=True)
    assert sealed['version']==raw.VERSION=='level2_closed_raw_storage_v4'
    s,session,_=build_final(tmp_path/'v3-catalog-final',monkeypatch,origin)
    raw.prepare(session,writers_closed=True,retire=True)
    ds=dataset_for(tmp_path/'input',[session/'raw/unused/extra.bin']);bundle=tmp_path/'bundle'
    portable.export(ds,bundle)
    closure=load(bundle/'storage-verification/bindings.json')
    assert len(closure['archives'])==2 and str(origin) in closure['dependencies']
    shutil.rmtree(task.parents[2]);shutil.rmtree(s.run);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']

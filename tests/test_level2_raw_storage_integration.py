"""Tiny CPU end-to-end raw/archive/dataset/portable checks; never real raw/NPU."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
HERE=Path(__file__).resolve().parents[1]
LIVE=Path(os.environ.get('APROF_TEST_REPO',HERE))
sys.path[:0]=[str(HERE/'scripts'),str(HERE/'tests'),str(LIVE/'scripts'),str(LIVE/'tests'),str(LIVE/'src')]
import importlib
for _name in ('level2_raw_archive_storage','level2_evidence_storage','level2_verification_storage','level2_native_output_storage',
              'trace_v2_dataset','trace_v2_portable','msprof_exploration_report','msprof_exploration_archive','level2_storage'):
    sys.path.insert(0,str(HERE/'scripts'))
    _module=importlib.import_module(_name)
    assert Path(_module.__file__).resolve().parent==HERE/'scripts'
raw=sys.modules['level2_raw_archive_storage'];storage=sys.modules['level2_evidence_storage']
verification=sys.modules['level2_verification_storage'];native=sys.modules['level2_native_output_storage']
report=sys.modules['msprof_exploration_report'];archive=sys.modules['msprof_exploration_archive']
dataset=sys.modules['trace_v2_dataset'];portable=sys.modules['trace_v2_portable'];dedup=sys.modules['level2_storage']
from test_level2_raw_archive_storage import tiny
from test_trace_v2_dataset import fixture_data


def dataset_for(tmp_path,paths):
    evidence,body=fixture_data(tmp_path)
    for p in paths:body['sources']['evidence_ids'].append(evidence.file(p))
    root=tmp_path/'dataset'
    dataset.publish(root,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
    return root


def test_original_complete_observation_is_identical_after_raw_retirement(tiny):
    _,sessions,*_=tiny;s=sessions[0]
    before=report.verify_observation(s)
    raw.prepare(s,writers_closed=True,retire=True)
    assert report.verify_observation(s)==before
    assert report.verify_observation(sessions[1])


def test_partial_unarchived_and_shadow_original_reports_stay_identical(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    before=report.verify_observation(s)
    raw.prepare(s,destination,writers_closed=True)
    with storage.reader_session({s:destination}):
        assert report.verify_observation(s)==before
        assert s/'raw/unused/extra.bin' in storage.logical_files(s)
    assert (s/'raw').is_dir()


def test_archive_collector_keeps_logical_raw_paths_without_member_cas(tiny,tmp_path):
    _,sessions,*_=tiny;s=sessions[0];origin=s/'raw/unused/extra.bin';expected=raw.pointer(origin)
    raw.prepare(s,writers_closed=True,retire=True)
    collector=archive.Archive.__new__(archive.Archive)
    collector.root=tmp_path/'collected';collector.artifacts={};collector.pointer_cache={};collector.safe=lambda p,owner=None:Path(p)
    with storage.reader_session():assert collector.pointer(origin,expected=expected['sha256'])==expected
    assert not (collector.root/'verification-bytes').exists()
    refs={r['path'] for r in collector.artifacts.values()}
    assert str(origin) in refs and str(s/'raw-archive-storage/raw.tar') in refs


def test_portable_keeps_entire_raw_tar_without_raw_member_cas_and_offline_replays(tiny,tmp_path):
    _,sessions,*_=tiny;s=sessions[0]
    origins=sorted(p for p in (s/'raw').rglob('*') if p.is_file())
    raw.prepare(s,writers_closed=True,retire=True)
    ds=dataset_for(tmp_path,origins);pointer=(ds/'current.json').read_bytes()
    bundle=tmp_path/'portable';result=portable.export(ds,bundle)
    assert result['valid'] and result['bundle_version']=='optimization_trace_portable_v3'
    manifest=json.loads((bundle/'bundle.json').read_bytes())
    for origin in origins:
        mapping=manifest['evidence_map'][str(origin)]
        assert set(mapping)=={'archive','relative_path'}
        with storage.open_binary(origin) as stream:data=stream.read()
        assert 'evidence/sha256/'+dataset.digest_bytes(data)[7:] not in manifest['files']
    assert (ds/'current.json').read_bytes()==pointer
    shutil.rmtree(s.parents[4]);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']
    result=subprocess.run([sys.executable,'-B',str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],cwd='/tmp',capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['original_evidence_locations_accessed'] is False


def test_nested_verification_raw_closure_offline(tiny,tmp_path,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0]
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',raw.host_lock)
    verification.prepare(s,writers_closed=True,retire=True)
    raw.prepare(s,writers_closed=True,retire=True)
    origin=s/'raw/unused/extra.bin';ds=dataset_for(tmp_path,[origin]);bundle=tmp_path/'portable'
    portable.export(ds,bundle)
    closure=json.loads((bundle/'storage-verification/bindings.json').read_bytes())
    assert closure['version']=='level2_storage_portable_v4' and closure['dependencies']
    assert len(closure['archives'])==2
    shutil.rmtree(s.parents[4]);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']


def rehash_bundle(bundle,relative):
    manifest=json.loads((bundle/'bundle.json').read_bytes())
    manifest['files'][relative]=portable.fingerprint(bundle/relative)
    (bundle/'bundle.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')


@pytest.mark.parametrize('what',['raw_unindexed_byte','missing_empty_dir','missing_proof','changed_logical_path','false_offset','helper_code'])
def test_portable_raw_closure_tampering_fails_or_never_executes_bundle_code(tiny,tmp_path,what):
    import io,tarfile
    _,sessions,*_=tiny;s=sessions[0]
    origin=next((s/'raw').rglob('op_summary*.csv'))
    raw.prepare(s,writers_closed=True,retire=True)
    ds=dataset_for(tmp_path,[origin]);bundle=tmp_path/'portable';portable.export(ds,bundle)
    m=json.loads((bundle/'bundle.json').read_bytes());closure_path='storage-verification/bindings.json';closure=json.loads((bundle/closure_path).read_bytes())
    if what=='helper_code':
        path='verifier/level2_raw_archive_storage.py';marker=tmp_path/'executed'
        (bundle/path).write_text('open('+repr(str(marker))+',"w").write("bad")\n');rehash_bundle(bundle,path)
        assert portable.verify(bundle)['valid'] and not marker.exists();return
    if what in ('changed_logical_path','false_offset'):
        member=m['evidence_map'][str(origin)]
        if what=='changed_logical_path':member['relative_path']='unused/extra.bin'
        else:member['offset']=123
        (bundle/'bundle.json').write_text(json.dumps(m,sort_keys=True)+'\n')
    elif what=='missing_proof':
        entry=next(iter(closure['archives'].values()));entry['files'].pop(str(sessions[-1]/'request.json'))
        (bundle/closure_path).write_text(json.dumps(closure,sort_keys=True)+'\n');rehash_bundle(bundle,closure_path)
        m=json.loads((bundle/'bundle.json').read_bytes());m['storage_closure']['sha256']=m['files'][closure_path]['sha256'];(bundle/'bundle.json').write_text(json.dumps(m,sort_keys=True)+'\n')
    else:
        key=next(iter(closure['archives']));entry=closure['archives'][key];seal=json.loads((bundle/entry['files'][entry['seal']['path']]).read_bytes());path=entry['files'][seal['archive']['path']]
        with tarfile.open(bundle/path,'r:') as tf:rows=[(v,tf.extractfile(v).read() if v.isfile() else None) for v in tf]
        if what=='missing_empty_dir':rows=[r for r in rows if r[0].name!='unused/empty']
        else:rows=[(v,b'x'+data[1:] if v.name=='unused/extra.bin' else data) for v,data in rows]
        with tarfile.open(bundle/path,'w',format=tarfile.USTAR_FORMAT) as tf:
            for v,data in rows:tf.addfile(v,io.BytesIO(data) if data is not None else None)
        rehash_bundle(bundle,path)
    with pytest.raises((ValueError,KeyError)):portable.verify(bundle)


def test_level1_unarchived_readers_keep_prior_semantics(tmp_path):
    p=tmp_path/'legacy/measurement/raw/sub/data.bin';p.parent.mkdir(parents=True);p.write_bytes(b'legacy')
    assert storage.read_bytes(p)==b'legacy'
    assert storage.fingerprint(p)==verification.fingerprint(p)
    assert storage.evidence_binding(p) is None


def test_preceding_portable_v1_v2_are_accepted_without_new_raw_mapping(tmp_path):
    ds=dataset_for(tmp_path,[]);bundle=tmp_path/'portable';portable.export(ds,bundle)
    m=json.loads((bundle/'bundle.json').read_bytes())
    for version in ('optimization_trace_portable_v2','optimization_trace_portable_v1'):
        value=dict(m,version=version)
        if version.endswith('_v1'):value.pop('storage_closure')
        (bundle/'bundle.json').write_text(json.dumps(value,sort_keys=True)+'\n')
        assert portable.verify(bundle)['valid']


def add_native_authority(tiny,monkeypatch):
    """Upgrade only synthetic metadata before any archive is created."""
    from test_level2_raw_archive_storage import save
    from verification_authority_fixture import anchor
    from msprof_exploration_execute import event
    import level2_storage as dedup
    task,sessions,*_=tiny;cohort=sessions[0].parent;stage=cohort.parent
    plan={'case_ids':[1],'schedule':[{'name':s.name,'request':json.loads((s/'request.json').read_bytes())} for s in sessions]}
    save(cohort/'plan.json',plan);save(stage/'stage-plan.json',{'cohort':plan})
    group=json.loads((cohort/'group-completion.json').read_bytes())
    group['ended_at']=200
    group['sessions']=[{'directory':str(s),'completion':raw.pointer(s/'completion.json'),'samples':raw.pointer(s/'samples.json'),'journal':raw.pointer(s/'native/journal.jsonl')} for s in sessions]
    save(cohort/'group-completion.json',group)
    result=json.loads((stage/'result.json').read_bytes());result['kind']='control';save(stage/'result.json',result)
    event(task,'stage_completed',{'result':raw.pointer(stage/'result.json')})
    save(task/'manifest.json',{'version':'msprof_task_time_exploration_v2','operator':'maximum'})
    anchor(task,cohort)
    monkeypatch.setattr(dedup,'exclusive_host',raw.host_lock)
    facts=dedup.deduplicate(task.parents[2],cohort,kind='cohort',writers_closed=True,apply=False)
    facts.update(status='passed',error=None,ended_at=3,original_records_modified=False)
    path=task.parents[2]/'storage/dedup'/('f'*32+'.json');save(path,facts)
    event(task,'closed_outputs_deduplicated',{'manifest':raw.pointer(path),'reclaimed_bytes':0,'evidence_bytes_deleted':0})
    return task,sessions,cohort


def test_three_storage_layers_and_all_dependencies_verify_offline(tiny,tmp_path,monkeypatch):
    task,sessions,cohort=add_native_authority(tiny,monkeypatch);s=sessions[0]
    before=report.verify_observation(s)
    native.prepare(cohort,writers_closed=True,retire=True)
    for session in sessions:verification.prepare(session,writers_closed=True,retire=True)
    raw.prepare(s,writers_closed=True,retire=True)
    assert report.verify_observation(s)==before
    paths=[s/'raw/unused/extra.bin',s/'native/1_normal_A.bin',s/'verification/1_normal_A/metadata.json']
    ds=dataset_for(tmp_path,paths);bundle=tmp_path/'portable';portable.export(ds,bundle)
    closure=json.loads((bundle/'storage-verification/bindings.json').read_bytes())
    assert closure['version']=='level2_storage_portable_v4' and len(closure['archives'])==8
    shutil.rmtree(task.parents[2]);shutil.rmtree(ds)
    assert portable.verify(bundle)['valid']
    result=subprocess.run([sys.executable,'-B',str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],cwd='/tmp',capture_output=True,text=True)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('fault',['missing_directory','missing_seal','symlink','foreign_scope'])
def test_explicit_raw_shadow_is_a_fail_closed_declaration(tiny,tmp_path,fault):
    _,sessions,*_,destination=tiny;s=sessions[0]
    if fault=='missing_seal':destination.mkdir()
    elif fault=='symlink':destination.symlink_to(s,target_is_directory=True)
    elif fault=='foreign_scope':raw.prepare(sessions[1],destination,writers_closed=True)
    with pytest.raises((ValueError,OSError)):
        with storage.reader_session({s:destination}):pytest.fail('invalid explicit override yielded')
    assert storage._CACHE.get() is None and storage._OVERRIDES.get() is None
    assert report.verify_observation(s)  # no archive declaration is ordinary fallback


def test_nested_invalid_override_does_not_replace_outer_cache(tiny,tmp_path):
    _,sessions,*_,destination=tiny;s=sessions[0];raw.prepare(s,destination,writers_closed=True)
    with storage.reader_session({s:destination}):
        cache=storage._CACHE.get();mapping=storage._OVERRIDES.get()
        with pytest.raises(ValueError,match='nested'):
            with storage.reader_session({s:tmp_path/'absent'}):pass
        assert storage._CACHE.get() is cache and storage._OVERRIDES.get() is mapping
        assert report.verify_observation(s)


def test_raw_exit_revalidation_keeps_underlying_caches_alive(tiny,monkeypatch):
    _,sessions,*_,destination=tiny;s=sessions[0];raw.prepare(s,destination,writers_closed=True)
    original=raw.RawArchive.reverify_cached;observed=[]
    def checked(reader):
        observed.append((verification._CACHE.get() is not None,native._CACHE.get() is not None))
        return original(reader)
    monkeypatch.setattr(raw.RawArchive,'reverify_cached',checked)
    with storage.reader_session({s:destination}):assert report.verify_observation(s)
    assert observed and all(a and b for a,b in observed)
    assert storage._CACHE.get() is None and verification._CACHE.get() is None and native._CACHE.get() is None


def test_portable_detects_unindexed_payload_mutation_during_deep_verify(tiny,tmp_path,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0]
    origin=next((s/'raw').rglob('op_summary*.csv'))
    raw.prepare(s,writers_closed=True,retire=True)
    ds=dataset_for(tmp_path,[origin]);bundle=tmp_path/'portable';portable.export(ds,bundle)
    closure=json.loads((bundle/'storage-verification/bindings.json').read_bytes())
    entry=next(iter(closure['archives'].values()));seal=json.loads((bundle/entry['files'][entry['seal']['path']]).read_bytes())
    target=bundle/entry['files'][seal['archive']['path']]
    import tarfile
    with tarfile.open(target,'r:') as tf:offset=tf.getmember('unused/extra.bin').offset_data
    original=dataset.verify
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        with target.open('r+b') as stream:stream.seek(offset);stream.write(b'!')
        return result
    monkeypatch.setattr(dataset,'verify',mutate)
    with pytest.raises(ValueError,match='changed during verification'):portable.verify(bundle)

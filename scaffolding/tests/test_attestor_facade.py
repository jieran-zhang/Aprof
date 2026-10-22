"""Small source fixtures and actual reviewed storage readers; no native analyzer."""
from contextlib import contextmanager
import hashlib,importlib.util,sys,types,os
from pathlib import Path
import pytest
P=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('attestor_facade_unit',P/'scaffolding/collection/scripts/level2_final_report_attestation.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
from reviewed_storage_fixture import materialize_reviewed_storage

@pytest.fixture
def epoch(tmp_path):
    repo=tmp_path/'repo';(repo/'scaffolding/collection/scripts').mkdir(parents=True)
    materialize_reviewed_storage(repo/'scaffolding/collection/scripts',a.STORAGE_PRODUCERS)
    return repo

def test_exact_reviewed_facade_and_capture_epoch(epoch):
    profile=a.storage_profile(epoch)
    assert profile['reviewed_patch_sha256']==a.REVIEWED_STORAGE_PATCH
    assert profile['expected_producer_sha256']==a.STORAGE_PRODUCERS
    assert a.VERSION=='level2_final_report_consistency_attestation_v2'
    assert 'level2_evidence_storage' in a.Runtime.MODULES
    assert 'level2_final_report_authority' in a.Runtime.MODULES
    assert 'level2_final_report_authority.py' not in a.STORAGE_PRODUCERS

@pytest.mark.parametrize('name',list(a.STORAGE_PRODUCERS))
def test_epoch_rejects_changed_reader_or_capture_before_import(epoch,name,monkeypatch):
    (epoch/'scaffolding/collection/scripts'/name).write_bytes(b'# changed producer\n')
    monkeypatch.setattr(a.importlib,'import_module',lambda _:pytest.fail('unqualified reader was imported'))
    with pytest.raises(ValueError,match='reviewed storage/capture producer'):a.Runtime(epoch)

def test_epoch_rejects_canonical_path_alias(epoch):
    p=epoch/'scaffolding/collection/scripts/level2_evidence_storage.py';content=p.read_bytes();p.unlink()
    other=epoch/'outside.py';other.write_bytes(content);p.symlink_to(other)
    with pytest.raises(ValueError,match='noncanonical|symlink'):a.storage_profile(epoch)

def test_runtime_routes_every_evidence_operation_through_facade(epoch,tmp_path,monkeypatch):
    modules={}
    for name in a.Runtime.MODULES:
        path=epoch/'scaffolding/collection/scripts'/(name+'.py')
        if not path.exists():path.write_bytes(b'# inert dependency\n')
        modules[name]=types.SimpleNamespace(__file__=str(path))
    calls=[];facade=modules['level2_evidence_storage'];prior=modules['level2_verification_storage']
    logical=tmp_path/'retired/raw/proof.json';payload=b'{"immutable":true}'
    facade.read_bytes=lambda p:(calls.append(('read',p)) or payload)
    facade.fingerprint=lambda p:(calls.append(('hash',p)) or {'sha256':a.digest(payload),'size_bytes':len(payload)})
    facade.evidence_binding=lambda p,h:(calls.append(('binding',p)) or {'version':'level2_closed_raw_storage_v1','origin':{'path':str(p),'sha256':h},'closed_evidence':{'fixture':'explicit'}})
    facade.reverify_cached=lambda:calls.append(('reverify',None))
    @contextmanager
    def readers():
        calls.append(('enter',None))
        try:yield
        finally:calls.append(('exit',None))
    facade.reader_session=readers
    prior.read_bytes=lambda _:pytest.fail('legacy reader bypassed facade')
    monkeypatch.setattr(a.importlib,'import_module',lambda n:modules[n])
    runtime=a.Runtime(epoch);assert runtime.storage is facade
    evidence=a.Evidence(runtime)
    with runtime.reader_session():
        assert evidence.checked({'path':str(logical),'sha256':a.digest(payload)})=={'immutable':True}
        assert evidence.storage_bindings[str(logical)]['version']=='level2_closed_raw_storage_v1'
        evidence.recheck()
    assert calls[0][0]=='enter' and calls[-1][0]=='exit'
    assert {'read','hash','binding','reverify'} <= {v[0] for v in calls}
    assert not logical.exists()


def binding(path,index=0,proof=None):
    token=a.digest(str(index).encode())
    return {'version':'level2_closed_raw_storage_v1','origin':{'path':str(path),'sha256':a.digest(b'logical')},
            'seal':{'path':str(path.parent/f'seal-{index}.json'),'sha256':token},
            'archive':{'path':str(path.parent/f'raw-{index}.tar'),'sha256':a.digest(b'archive')},
            'producer':{'path':str(path.parent/f'producer-{index}.py'),'sha256':a.digest(b'producer')},
            'closed_evidence':proof or {'independent':'prior report authority'}}


def expand(value):
    result=[]
    for path,row in value['origins'].items():
        archive=value['archives'][row['seal']]
        result.append({**{k:v for k,v in archive.items() if k!='closed_evidence_ref'},
                       'origin':{'path':path,'sha256':row['sha256']},
                       'closed_evidence':value['closed_evidence'][archive['closed_evidence_ref']]})
    return result


def test_compact_proofs_preserve_every_member_and_nested_fact(tmp_path):
    proof={'nested':{'report':{'path':str(tmp_path/'original-report.json'),'sha256':a.digest(b'report')}},
           'sessions':[{'oracle':{'path':str(tmp_path/'oracle.json'),'sha256':a.digest(b'oracle')}}]}
    rows=[binding(tmp_path/f'file{i}.bin',i//2,proof) for i in range(6)]
    value=a.compact_storage_bindings(rows)
    assert expand(value)==rows
    assert len(value['origins'])==6 and len(value['archives'])==3 and len(value['closed_evidence'])==1


def test_compact_full_proof_scale_stays_below_metadata_limit(tmp_path):
    proof={'all_nested_evidence':['x'*65536], 'exact_original_authority':True}
    rows=[binding(tmp_path/f'member-{i}.json',i//1000,proof) for i in range(6000)]
    assert len(a.canonical(rows[0]))*len(rows)>32*1024*1024
    value=a.compact_storage_bindings(rows)
    assert len(value['origins'])==6000 and len(value['archives'])==6 and len(value['closed_evidence'])==1
    assert len(a.canonical(value))<2*1024*1024
    assert expand(value)==rows


@pytest.mark.parametrize('fault',['logical_conflict','seal_conflict','dropped_archive','extra_archive','proof_rehash','dropped_proof'])
def test_compact_binding_conflicts_and_incomplete_closure_reject(tmp_path,fault):
    from copy import deepcopy
    first=binding(tmp_path/'member.json');second=deepcopy(first)
    if fault=='logical_conflict':
        second['origin']['sha256']=a.digest(b'changed')
        with pytest.raises(ValueError,match='logical'):a.compact_storage_bindings([first,second])
    elif fault=='seal_conflict':
        second['origin']['path']=str(tmp_path/'other.json');second['closed_evidence']={'changed':True}
        with pytest.raises(ValueError,match='seal'):a.compact_storage_bindings([first,second])
    else:
        value=a.compact_storage_bindings([first])
        if fault=='dropped_archive':value['archives'].clear()
        elif fault=='extra_archive':value['archives'][a.digest(b'extra')]=deepcopy(next(iter(value['archives'].values())))
        elif fault=='proof_rehash':next(iter(value['closed_evidence'].values()))['changed']=True
        else:value['closed_evidence'].clear()
        with pytest.raises(ValueError):a.validate_storage_bindings(value)


def test_final_authority_is_an_actual_engineering_dependency_without_static_cycle(epoch,monkeypatch):
    modules={}
    for name in a.Runtime.MODULES:
        path=epoch/'scaffolding/collection/scripts'/(name+'.py')
        if not path.exists():path.write_bytes(b'# explicit tiny dependency\n')
        modules[name]=types.SimpleNamespace(__file__=str(path))
        monkeypatch.setitem(sys.modules,name,modules[name])
    monkeypatch.setattr(a.importlib,'import_module',lambda n:modules[n])
    runtime=a.Runtime(epoch)
    assert epoch/'scaffolding/collection/scripts/level2_final_report_authority.py' in runtime.producer_paths()
    assert runtime.modules['level2_final_report_authority'] is modules['level2_final_report_authority']

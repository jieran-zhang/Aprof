"""Real Archive.publish/FrozenRecorder with tiny retired evidence; CPU only."""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"scripts"),str(ROOT/"tests")]
import msprof_exploration_archive as archive
import level2_raw_archive_storage as raw
import level2_verification_storage as verification
import level2_evidence_storage as storage
import trace_v2_dataset as dataset
import trace_v2_portable as portable
import feedback_trace_export as export
from shared_context_archive import FrozenRecorder
from test_level2_raw_archive_storage import tiny
from test_msprof_exploration_archive import run,stage,save,read_memory

@pytest.fixture(autouse=True)
def no_host_device_lock(monkeypatch):
    import level2_storage
    monkeypatch.setattr(level2_storage,"exclusive_host",contextlib.nullcontext)
    monkeypatch.setattr(raw,"host_lock",contextlib.nullcontext)

def collected(run,tiny,retire,monkeypatch):
    task,sessions,*_=tiny;session=sessions[0]
    # Put both fixture operators under the same real run; keep the actual safe()
    # boundary, including rejection of foreign/split ledger paths.
    destination=task.parents[2];old_root=run["root"]
    moved=destination/"train/tasks/exp"
    shutil.move(str(run["task"]),moved)
    prior_ledger=archive.campaign.Campaign
    monkeypatch.setattr(archive.campaign,"Campaign",lambda directory:prior_ledger(old_root/"train/ledger"))
    run.update(root=destination,task=moved,candidate=moved/"candidates/exp001")
    origin=session/"raw/unused/extra.bin"
    metadata=session/"verification/1_normal_A/result.json"
    if not metadata.exists():metadata=next((session/"verification").glob("*/result.json"))
    expected={p:dataset.evidence_fingerprint(p)["sha256"] for p in (origin,metadata)}
    if retire:
        verification.prepare(session,writers_closed=True,retire=True)
        raw.prepare(session,writers_closed=True,retire=True)
        assert not origin.exists() and not metadata.exists()
    stage(run)
    a=archive.Archive(run["root"],"train")
    config=a.prepare()
    with storage.reader_session():
        for path in (origin,metadata):a.pointer(path,expected=expected[path])
        selected=a.pointer(metadata,expected=expected[metadata],selector="/passed")
    config["attempts"][0]["intervention"]["evidence"].append(selected)
    config["artifact_index"]=list(a.artifacts.values())
    return a,config,session,origin,metadata,expected

def test_real_archive_publish_retired_raw_verification_portable(tiny,run,tmp_path,monkeypatch):
    a,config,session,origin,metadata,expected=collected(run,tiny,True,monkeypatch)
    result=a.publish(config)
    assert result["verification"]["valid"] and result["new_source_attempts"]==1
    rows,base=read_memory(run["root"]);assert rows[0]["id"]=="new-run/train/exp001"
    index=json.loads((base/"evidence_index.json").read_text())
    assert {str(origin),str(metadata)} <= {r["path"] for r in index.values()}
    for p,h in expected.items():assert not dataset.object_path(a.output/"external_evidence",h).exists()
    rec=FrozenRecorder(a.document(config)["path"],a.output)
    _,value=rec.selected({"path":str(metadata),"sha256":expected[metadata],"selector":"/passed"})
    assert value is True
    bundle=tmp_path/"portable";portable.export(a.output,bundle)
    mapping=json.loads((bundle/"bundle.json").read_text())["evidence_map"]
    assert set(mapping[str(origin)])=={"archive","relative_path"}
    assert isinstance(mapping[str(metadata)],str)  # existing verification portable protocol unchanged
    shutil.rmtree(run["root"])
    # The actual bundled CLI must work from the original producer checkout with
    # every read of that checkout denied. Removed fixture RUNs cannot be read.
    code="""import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('barrier',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
bundle=Path(sys.argv[2]);deny=Path(sys.argv[3]);m.install_read_barrier(deny)
sys.path.insert(0,str(bundle/'verifier'));import trace_v2_portable
print(json.dumps(trace_v2_portable.verify(bundle)))
"""
    barrier=str(ROOT/"tests/fixtures/archive_offline_read_barrier.py")
    proc=subprocess.run([sys.executable,"-I","-B","-c",code,barrier,str(bundle),str(ROOT)],cwd=ROOT,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    assert json.loads(proc.stdout)["valid"]

def test_tampered_archive_cannot_advance_current(tiny,run,tmp_path,monkeypatch):
    a,config,session,origin,metadata,expected=collected(run,tiny,False,monkeypatch)
    first=a.publish(config);before=(a.output/"current.json").read_bytes()
    verification.prepare(session,writers_closed=True,retire=True)
    raw.prepare(session,writers_closed=True,retire=True)
    # A fresh collector must resolve the original paths through strict storage.
    a.pointer_cache.clear()
    with storage.reader_session():a.pointer(origin,expected=expected[origin])
    config["artifact_index"]=list(a.artifacts.values())
    tar=session/"raw-archive-storage/raw.tar"
    with tar.open("ab") as f:f.write(b"tamper")
    with pytest.raises((ValueError,OSError)):a.publish(config)
    assert (a.output/"current.json").read_bytes()==before

def test_physical_freeze_streams_empty_selector_and_preserves_identity(tmp_path,monkeypatch):
    path=tmp_path/"large.tar";data=b"abcdefgh"*200000;path.write_bytes(data)
    manifest=tmp_path/"manifest.json";manifest.write_text("{}\n")
    recorder=FrozenRecorder(manifest,tmp_path/"dataset")
    original=Path.read_bytes
    def guarded(self):
        if self==path or (self.is_file() and self.stat().st_size==len(data)):raise AssertionError("large payload read_bytes")
        return original(self)
    monkeypatch.setattr(Path,"read_bytes",guarded)
    ref=recorder.pointer({"path":str(path)})
    entry=recorder.evidence.entries[ref]
    assert entry["sha256"]=="sha256:"+hashlib.sha256(data).hexdigest()
    assert entry["size_bytes"]==len(data) and not recorder.evidence.bytes_cache
    assert recorder.pointer({"path":str(path)})==ref
    assert not list((tmp_path/"dataset/external_evidence").glob(".freeze-*"))

def test_wrong_expected_hash_never_publishes_cas(tmp_path):
    path=tmp_path/"source.txt";path.write_text("original")
    rec=export.Recorder(tmp_path/"manifest.json",tmp_path/"dataset")
    with pytest.raises(ValueError,match="hash mismatch"):
        rec.pointer({"path":str(path),"sha256":"sha256:"+"0"*64})
    assert not list((tmp_path/"dataset").rglob("[0-9a-f]"*62))
    assert not list((tmp_path/"dataset").rglob(".freeze-*"))


@pytest.mark.parametrize("relative",["other/train/ledger/config.json","run/validation/ledger/config.json","run/ledger/config.json","run/train/ledger/arbitrary.json"])
def test_storage_ledger_scope_remains_narrow(tmp_path,relative):
    a=archive.Archive.__new__(archive.Archive);a.run=tmp_path/"run";a.split="train";a.artifacts={}
    a._active_ledger_authorities={"validated-fixture-seal"}
    path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text("{}\n")
    with pytest.raises(ValueError):
        a._authenticated_authority_pointer(path,None,expected=dataset.digest_bytes(path.read_bytes()),verified_source="validated-fixture-seal")
    assert not a.artifacts


def test_unverified_closure_cannot_enable_ledger_pointer(tmp_path):
    a=archive.Archive.__new__(archive.Archive);a.run=tmp_path/"run";a.split="train";a.artifacts={}
    path=a.run/"train/ledger/config.json";path.parent.mkdir(parents=True);path.write_text("{}\n")
    with pytest.raises(ValueError,match="active authenticated"):
        a._authenticated_authority_pointer(path,None,expected=dataset.digest_bytes(path.read_bytes()))
    origin=tmp_path/"loose.bin";origin.write_bytes(b"plain physical file")
    ref={"path":str(origin),"sha256":dataset.digest_bytes(origin.read_bytes())}
    binding={"version":"forged","origin":ref,"seal":ref,"archive":ref,"producer":ref,"closed_evidence":{"protected":[{"path":str(path),"sha256":dataset.digest_bytes(path.read_bytes())}]}}
    with pytest.raises(ValueError,match="not authenticated"):
        a.retain_storage_binding(binding,None)
    assert not a.artifacts


def test_ordinary_pointer_still_rejects_same_split_ledger(run):
    a=archive.Archive(run["root"],"train")
    path=run["root"]/"train/ledger/config.json";path.parent.mkdir(parents=True);path.write_text("{}\n")
    with pytest.raises(ValueError,match="ledger"):
        a.pointer(path)


def test_late_tar_tamper_after_inner_publish_does_not_commit(tiny,run,tmp_path,monkeypatch):
    a,config,session,origin,metadata,expected=collected(run,tiny,True,monkeypatch)
    original=dataset.publish
    def late(*args,**kwargs):
        result=original(*args,**kwargs)
        with (session/"raw-archive-storage/raw.tar").open("ab") as stream:stream.write(b"late mutation")
        return result
    monkeypatch.setattr(dataset,"publish",late)
    with pytest.raises((ValueError,OSError)):a.publish(config)
    assert not (a.output/"current.json").exists()
    assert list(a.root.glob(".publish-staging-*"))


from types import SimpleNamespace
from test_level2_final_prestart_resolver import certified
import level2_stage_recovery as recovery


def recovery_collector(f):
    a=archive.Archive.__new__(archive.Archive)
    a.run=f["run"];a.split="validation";a.root=a.run/"archive/validation";a.output=a.root/"v2"
    a.fresh=True;a.ledger=SimpleNamespace(config={"tasks":{"group_norm":{"split":"validation"}}})
    a.artifacts={};a.pointer_cache={};a.engineering_bindings={};a.observation_producer_bindings={}
    return a


def test_real_certified_recovery_refs_cross_actual_archive_safe(certified):
    f=certified;a=recovery_collector(f)
    task={"stages":{"group_norm002-final":f["state"]}}
    rows=list(a.stage_result_groups(f["task"]/"candidates/group_norm002",task,"group_norm002","group_norm"))
    assert rows==[([Path(f["original"]["path"]),Path(f["current"]["path"])],Path(f["current"]["path"]))]
    paths={r["path"] for r in a.artifacts.values()}
    resolved=recovery.resolve_from_reader(f["stage"])
    assert {r["path"] for r in resolved["protected"]}<=paths
    assert str(f["ledger"]/"events.jsonl") in paths
    assert not a._active_ledger_authorities
    with pytest.raises(ValueError,match="ledger"):a.pointer(f["ledger"]/"config.json","group_norm")


def test_recovery_pointer_list_cannot_be_self_declared(certified):
    f=certified;a=recovery_collector(f)
    value=recovery.resolve_from_reader(f["stage"])
    value["protected"].append({"path":str(f["ledger"]/"unapproved.json"),"sha256":"sha256:"+"0"*64})
    with pytest.raises(ValueError,match="current resolver"):a._retain_recovery_refs(value,"group_norm")
    assert not a.artifacts


@pytest.mark.parametrize('ledger',[True,False])
def test_bound_event_mutation_after_resolver_is_rejected(certified,monkeypatch,ledger):
    f=certified;a=recovery_collector(f)
    bound=recovery.resolve_from_reader(f['stage']);original=recovery.resolve_from_reader
    event=next(row for row in bound['event_bindings'] if ('ledger' in Path(row['path']).parts)==ledger)
    def changed(*args,**kwargs):
        value=original(*args,**kwargs)
        path=Path(event['path']);lines=path.read_bytes().splitlines()
        row=json.loads(lines[event['sequence']]);row['recorded_at']='changed after authentication'
        body={k:v for k,v in row.items() if k!='hash'}
        row['hash']=(recovery.digest(body) if ledger else
                     recovery.sha((json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()))
        lines[event['sequence']]=recovery.canonical(row)
        path.write_bytes(b'\n'.join(lines)+b'\n')
        return value
    monkeypatch.setattr(recovery,'resolve_from_reader',changed)
    with pytest.raises(ValueError,match='prefix changed after authentication'):
        a._retain_recovery_refs(bound,'group_norm')


def test_authenticated_event_prefix_allows_later_valid_suffix(certified,monkeypatch):
    f=certified;a=recovery_collector(f)
    bound=recovery.resolve_from_reader(f['stage']);original=recovery.resolve_from_reader
    event=next(row for row in bound['event_bindings'] if 'ledger' not in Path(row['path']).parts)
    def appended(*args,**kwargs):
        value=original(*args,**kwargs)
        path=Path(event['path']);lines=path.read_bytes().splitlines();last=json.loads(lines[-1])
        row={'sequence':last['sequence']+1,'recorded_at':'later','kind':'later_fixture_event',
             'previous_hash':last['hash'],'value':{}}
        row['hash']=recovery.sha((json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())
        path.write_bytes(b'\n'.join([*lines,recovery.canonical(row)])+b'\n')
        return value
    monkeypatch.setattr(recovery,'resolve_from_reader',appended)
    a._retain_recovery_refs(bound,'group_norm')
    assert any(row['path']==event['path'] and row['selector']=='line:'+str(event['sequence']+1)
               for row in a.artifacts.values())


def test_nested_closed_observation_recovery_dict_is_not_a_flat_pointer(certified,tmp_path,monkeypatch):
    # Historical producer lookup is stubbed; certified resolver is genuine and
    # must reauthenticate the nested result before any ledger pointer is kept.
    import msprof_exploration_provenance as provenance
    f=certified;a=recovery_collector(f)
    origin=tmp_path/"repo/scripts/old-producer.py";origin.parent.mkdir(parents=True,exist_ok=True);origin.write_text("current\n")
    expected=dataset.digest_bytes(b"historical\n")
    session=f["stage"]/"direct_parent/p01";session.mkdir(parents=True)
    save(session/"bindings.json",{str(origin):expected});done=save(session/"completion.json",{"fixture":"producer lookup only"})
    resolved=recovery.resolve_from_reader(f["stage"])
    pointer=lambda p:{"path":str(p),"sha256":dataset.evidence_fingerprint(p)["sha256"]}
    binding={"snapshot":pointer(origin),"frozen_manifest":f["certificate"]["recovery_engineering"],
             "closed_observation":{"completion":pointer(done),"stage_recovery":resolved}}
    monkeypatch.setattr(provenance,"frozen_producer",lambda *args,**kwargs:binding)
    a.bind_closed_observation_producers(session,"group_norm")
    assert a.observation_producer_bindings[(str(origin),expected)]==binding
    assert {r["path"] for r in resolved["protected"]}<={r["path"] for r in a.artifacts.values()}
    docs=[json.loads(p.read_text()) for p in (a.root/"documents").glob("*.json")]
    assert {"closed_observation_producer_binding":binding} in docs

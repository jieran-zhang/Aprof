"""Closed journals retire only after exact, durable, replayable archival proof."""
import io
import json
import tarfile
from pathlib import Path
import pytest
from test_level2_storage import storage, pilot, dedup, ptr, sha, save, binary, tree, local_host_lock
from msprof_exploration_execute import event


def closed(tmp_path):
    run,task,scope,outputs=pilot(tmp_path,contents=(b'same',b'same',b'same'))
    manifest=dedup(run,scope);tx=Path(manifest['transaction'])
    event(task,'closed_outputs_deduplicated',{'manifest':ptr(Path(manifest['manifest_path']))})
    return run,task,scope,outputs,tx


def compact(run,tx,**kwargs):
    return storage.compact_journals(run,tx,writers_closed=True,apply=kwargs.pop('apply',True),**kwargs)


def journals(tx):return {p.name:p.read_bytes() for p in tx.iterdir() if storage.JOURNAL.fullmatch(p.name)}


def test_exact_tar_preserves_original_bytes_paths_modes_and_provenance(tmp_path):
    run,task,scope,outputs,tx=closed(tmp_path)
    original=journals(tx);plan=ptr(tx/'plan.json');manifest=ptr(run/'storage/dedup'/(tx.name+'.json'))
    result=compact(run,tx)
    assert result['status']=='complete' and result['removed_journal_paths']==4 and not journals(tx)
    seal,payloads=storage.archived_journals(run,tx)
    assert payloads==original and plan==ptr(tx/'plan.json') and manifest==ptr(Path(manifest['path']))
    for name,data in original.items():
        assert storage.read_compacted_journal(tx/name,'sha256:'+storage.hashlib.sha256(data).hexdigest())==data
    # Existing provenance checks still verify the unchanged public storage manifest.
    from msprof_exploration_provenance import verify_pointer_tree
    verify_pointer_tree({'manifest':manifest},evidence_path=task/'events.jsonl')
    assert all(p.read_bytes()==b'same' for p in outputs)
    assert compact(run,tx)==result
    again=dedup(run,scope)
    assert again['status']=='passed' and again['reclaimed_bytes']==0
    assert storage.recover(storage.Inventory(run,scope,'pilot'),run/'storage/transactions')==[]


def test_dry_run_and_missing_attestation(tmp_path):
    run,_,_,_,tx=closed(tmp_path);before=tree(run)
    with pytest.raises(ValueError,match='affirm'):storage.compact_journals(run,tx)
    report=compact(run,tx,apply=False)
    assert report['journal_paths']==4 and report['new_archive_records']==3 and tree(run)==before


@pytest.mark.parametrize('change',['status','error','unknown','recovery','manifest_plan','journal_value','missing_intent','missing_result','extra','backup','temporary','external_ref','no_event','bad_event'])
def test_refuse_unproved_or_live_transaction_without_removal(tmp_path,change):
    run,task,scope,outputs,tx=closed(tmp_path);mp=run/'storage/dedup'/(tx.name+'.json')
    manifest=json.loads(mp.read_bytes())
    if change=='status':manifest['status']='failed';save(mp,manifest)
    elif change=='error':manifest['error']={'message':'test'};save(mp,manifest)
    elif change=='unknown':manifest['reclaimed_bytes_known']=False;save(mp,manifest)
    elif change=='recovery':manifest['recovery']=[{}];save(mp,manifest)
    elif change=='manifest_plan':manifest['kind']='other';save(mp,manifest)
    elif change=='journal_value':save(tx/'000001.intent.json',{'made_up':True})
    elif change=='missing_intent':(tx/'000001.intent.json').unlink()
    elif change=='missing_result':(tx/'000001.result.json').unlink()
    elif change=='extra':save(tx/'999999.intent.json',{})
    elif change in ('backup','temporary'):
        intent=json.loads((tx/'000001.intent.json').read_bytes());binary(Path(intent[change]),b'same')
    elif change=='external_ref':save(task/'external.json',{'evidence':ptr(tx/'000001.intent.json')})
    elif change=='no_event':(task/'events.jsonl').unlink()
    elif change=='bad_event':(task/'events.jsonl').write_text('{}\n')
    before=journals(tx)
    with pytest.raises((ValueError,FileNotFoundError)):compact(run,tx)
    assert journals(tx)==before and not (tx/'journals.seal.json').exists()


@pytest.mark.parametrize('where',['archive_publish','seal_publish','after_one_unlink','completion_publish'])
def test_interruption_preserves_bytes_and_explicit_resume(tmp_path,monkeypatch,where):
    run,_,_,_,tx=closed(tmp_path);original=journals(tx)
    old_write=storage.write_new;old_unlink=Path.unlink;old_sync=storage.sync_directory;fired=False
    def write(path,value):
        nonlocal fired
        target='journals.seal.json' if where=='seal_publish' else 'journals.compacted.json'
        if where in ('seal_publish','completion_publish') and path.name==target and not fired:
            fired=True;raise OSError('injected durable publish failure')
        return old_write(path,value)
    def sync(path):
        nonlocal fired
        if where=='archive_publish' and (tx/'journals.tar').exists() and not fired:
            fired=True;raise OSError('injected directory fsync failure')
        return old_sync(path)
    def unlink(path,*a,**kw):
        nonlocal fired
        if where=='after_one_unlink' and storage.JOURNAL.fullmatch(path.name) and not fired:
            fired=True;old_unlink(path,*a,**kw);raise OSError('injected after unlink')
        return old_unlink(path,*a,**kw)
    monkeypatch.setattr(storage,'write_new',write);monkeypatch.setattr(storage,'sync_directory',sync);monkeypatch.setattr(Path,'unlink',unlink)
    with pytest.raises(OSError,match='injected'):compact(run,tx)
    assert fired
    if (tx/'journals.seal.json').exists():assert storage.archived_journals(run,tx)[1]==original
    else:assert journals(tx)==original
    monkeypatch.setattr(storage,'write_new',old_write);monkeypatch.setattr(storage,'sync_directory',old_sync);monkeypatch.setattr(Path,'unlink',old_unlink)
    assert compact(run,tx)['status']=='complete' and storage.archived_journals(run,tx)[1]==original


@pytest.mark.parametrize('change',['archive','seal','missing_archive','missing_seal','missing_all','missing_all_and_manifest','receipt','plan','event','extra_loose','returned_loose','symlink_archive'])
def test_future_recovery_and_alias_inventory_reject_missing_or_tampered_archive(tmp_path,change):
    run,task,scope,outputs,tx=closed(tmp_path);original=journals(tx);compact(run,tx)
    if change=='archive':(tx/'journals.tar').write_bytes(b'bad')
    elif change=='seal':save(tx/'journals.seal.json',{})
    elif change=='missing_archive':(tx/'journals.tar').unlink()
    elif change=='missing_seal':(tx/'journals.seal.json').unlink()
    elif change in ('missing_all','missing_all_and_manifest'):
        for name in ('journals.tar','journals.seal.json','journals.compacted.json'):(tx/name).unlink()
        if change=='missing_all_and_manifest':(run/'storage/dedup'/(tx.name+'.json')).unlink()
    elif change=='receipt':save(tx/'journals.compacted.json',{})
    elif change=='plan':save(tx/'plan.json',{})
    elif change=='event':(task/'events.jsonl').write_text('{}\n')
    elif change=='extra_loose':save(tx/'999999.result.json',{})
    elif change=='returned_loose':binary(tx/'000001.intent.json',original['000001.intent.json'])
    elif change=='symlink_archive':
        target=tx/'other.tar';(tx/'journals.tar').rename(target);(tx/'journals.tar').symlink_to(target)
    inventory=storage.Inventory(run,scope,'pilot')
    with pytest.raises((ValueError,FileNotFoundError,KeyError)):
        storage.recover(inventory,run/'storage/transactions')
    with pytest.raises((ValueError,FileNotFoundError,KeyError)):
        storage.KnownOutputLinks(inventory,run/'storage/transactions')
    assert all(p.read_bytes()==b'same' for p in outputs)


def test_later_unrelated_events_do_not_invalidate_stable_prefix(tmp_path):
    run,task,_,_,tx=closed(tmp_path);compact(run,tx)
    event(task,'unrelated',{'new_source':'later'})
    assert storage.archived_journals(run,tx)[1]
    assert compact(run,tx)['status']=='complete'


def test_exact_path_hash_reader_rejects_substitution_and_traversal(tmp_path):
    run,_,_,_,tx=closed(tmp_path);original=journals(tx);compact(run,tx)
    with pytest.raises(ValueError,match='hash differs'):storage.read_compacted_journal(tx/'000001.intent.json','sha256:'+'0'*64)
    with pytest.raises(ValueError,match='invalid historical'):storage.read_compacted_journal(tx/'../000001.intent.json','sha256:'+'0'*64)
    with pytest.raises(ValueError,match='not sealed'):storage.read_compacted_journal(tx/'999999.intent.json','sha256:'+'0'*64)


def test_partial_cleanup_validates_on_next_dedup_but_requires_explicit_compaction_completion(tmp_path,monkeypatch):
    run,_,scope,_,tx=closed(tmp_path);old_unlink=Path.unlink;fired=False
    def unlink(path,*a,**kw):
        nonlocal fired
        if storage.JOURNAL.fullmatch(path.name) and not fired:
            fired=True;old_unlink(path,*a,**kw);raise OSError('stop')
        return old_unlink(path,*a,**kw)
    monkeypatch.setattr(Path,'unlink',unlink)
    with pytest.raises(OSError):compact(run,tx)
    monkeypatch.setattr(Path,'unlink',old_unlink)
    assert storage.recover(storage.Inventory(run,scope,'pilot'),run/'storage/transactions')==[]
    assert len(journals(tx))==3 and not (tx/'journals.compacted.json').exists()
    assert dedup(run,scope)['status']=='passed'
    assert compact(run,tx)['status']=='complete'


@pytest.mark.parametrize('target',['journals.tar','journals.seal.json'])
def test_reentry_reestablishes_durability_before_any_unlink(tmp_path,monkeypatch,target):
    run,_,_,_,tx=closed(tmp_path);original=journals(tx)
    original_unlink=Path.unlink
    def stop(path,*args,**kwargs):
        if storage.JOURNAL.fullmatch(path.name):raise OSError('stop before cleanup')
        return original_unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',stop)
    with pytest.raises(OSError,match='stop before'):compact(run,tx)
    monkeypatch.setattr(Path,'unlink',original_unlink)
    assert journals(tx)==original
    original_fsync=storage.os.fsync
    def fsync(fd):
        if storage.os.readlink('/proc/self/fd/'+str(fd))==str(tx/target):raise OSError('durability unavailable')
        return original_fsync(fd)
    monkeypatch.setattr(storage.os,'fsync',fsync)
    with pytest.raises(OSError,match='durability unavailable'):compact(run,tx)
    assert journals(tx)==original
    monkeypatch.setattr(storage.os,'fsync',original_fsync)
    assert compact(run,tx)['status']=='complete'

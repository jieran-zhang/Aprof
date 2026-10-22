"""Tiny synthetic local files only; no real raw, host lock, ASC or NPU."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import pytest
ROOT=Path(os.environ.get('APROF_TEST_REPO',Path(__file__).resolve().parents[2]))
SIB=Path(os.environ.get('APROF_REVIEWED_STORAGE_ROOT',ROOT))
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'scripts'),str(SIB/'scaffolding/collection/scripts'),str(SIB/'scaffolding/tests'),str(ROOT/'scaffolding/collection/scripts'),str(ROOT/'scaffolding/tests')]
import level2_raw_archive_storage as raw
import level2_verification_storage as authority
import level2_native_output_storage
import msprof_exploration_report as report
from msprof_exploration_execute import event
import test_msprof_raw_storage as fixture_module
from verification_authority_fixture import anchor


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,sort_keys=True)+'\n')


@pytest.fixture
def tiny(tmp_path,monkeypatch,request):
    @contextlib.contextmanager
    def lock():yield
    monkeypatch.setattr(raw,'host_lock',lock)
    task=tmp_path/'run/train/tasks/maximum'
    kind=getattr(request,'param','calibration')
    cohort=task/'stages/aa-test/cohort' if kind=='calibration' else task/'candidates/maximum001/stages/search/direct_parent'
    old=fixture_module.make_session
    counter=[0]
    def make(path,*args,**kwargs):
        counter[0]+=1
        return old(cohort,*args,**kwargs,name=f'p{counter[0]:02d}')
    monkeypatch.setattr(fixture_module,'make_session',make)
    rows=[];sessions=[]
    for i in range(6):
        session,req,build=fixture_module.v2_session(tmp_path/f'fixture{i}')
        (session/'raw/unused/empty').mkdir(parents=True)
        (session/'raw/unused/extra.bin').write_bytes(b'\x00arbitrary-unparsed\xff')
        req=fixture_module.localize(session,req)
        rows.append(report.verify_observation(session,req));sessions.append(session)
        for directory in (session/'verification').iterdir():
            save(directory/'result.json',{'passed':True})
    save(cohort/'report.json',{'protocol':'msprof_task_time_exploration_v2','evidence_status':'verified_complete','sessions':rows})
    save(cohort/'plan.json',{'version':'synthetic fixed plan'})
    save(cohort/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[str(s) for s in sessions]})
    stage=cohort.parent
    save(stage/'stage-plan.json',{'version':'synthetic original control'})
    save(stage/'result.json',{'status':'passed','error':None,'ended_at':200})
    event(task,'stage_completed',{'result':raw.pointer(stage/'result.json')})
    ledger,events=anchor(task,cohort,kind)
    return task,sessions,ledger,events,tmp_path/'shadow'


def test_shadow_full_roster_original_transport_and_parser(tiny):
    task,sessions,_,_,destination=tiny;s=sessions[0]
    before={str(p):p.read_bytes() for p in (s/'raw').rglob('*') if p.is_file()}
    result=raw.prepare(s,destination,writers_closed=True)
    assert result['status']=='sealed_shadow'
    reader=raw.RawArchive(s,result['seal'],shadow=True)
    assert set(map(str,reader.logical_files()))==set(before)
    for path,data in before.items():
        with reader.open_binary(Path(path)) as stream:assert stream.read()==data
    assert 'unused/empty' in reader.dirs
    assert {p:Path(p).read_bytes() for p in before}==before
    capture,paths,env=reader.verify_transport()
    assert env['capture_storage']==fixture_module.storage.LOCAL
    assert not any('raw-archive' in str(p) for p in paths)
    assert raw.prepare(s,destination,writers_closed=True)==result


def test_retire_idempotent_and_streamed_original_bytes(tiny):
    _,sessions,*_=tiny;s=sessions[0]
    before={str(p):p.read_bytes() for p in (s/'raw').rglob('*') if p.is_file()}
    result=raw.prepare(s,writers_closed=True,retire=True)
    assert result['status']=='complete' and not (s/'raw').exists()
    assert raw.prepare(s,writers_closed=True,retire=True)==result
    reader=raw.RawArchive(s,result['seal'])
    for path,data in before.items():
        with reader.open_binary(Path(path)) as stream:assert stream.read()==data


def test_missing_independent_report_anchor_fails_without_writes(tiny):
    _,sessions,ledger,events,destination=tiny
    (ledger/'events.jsonl').write_bytes(b''.join(json.dumps(r,sort_keys=True,separators=(',',':')).encode()+b'\n' for r in events[:-1]))
    with pytest.raises(ValueError):raw.prepare(sessions[0],destination,writers_closed=True)
    assert not destination.exists()


@pytest.mark.parametrize('which',['nonlocal','incomplete','bad_hash','bad_oracle'])
def test_any_of_six_must_have_original_closed_bound_evidence(tiny,which):
    _,sessions,*_,destination=tiny;s=sessions[-1]
    p=s/({'nonlocal':'request.json','incomplete':'completion.json','bad_hash':'raw-storage.json','bad_oracle':'verification/1_normal_A/stdout.log'}[which])
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError):raw.prepare(sessions[0],destination,writers_closed=True)
    assert not destination.exists()


def test_shadow_cannot_retire(tiny):
    _,sessions,*_,destination=tiny
    with pytest.raises(ValueError,match='shadow'):raw.prepare(sessions[0],destination,writers_closed=True,retire=True)


def test_partial_unlink_failure_then_reentry_preserves_every_byte(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];original=raw.remove_file;count=[0]
    def fail(path,expected):
        original(path,expected);count[0]+=1
        if count[0]==2:raise RuntimeError('injected unlink interruption')
    monkeypatch.setattr(raw,'remove_file',fail)
    with pytest.raises(RuntimeError,match='injected'):raw.prepare(s,writers_closed=True,retire=True)
    assert (s/'raw-archive-storage/seal.json').exists() and not (s/'raw-archive-storage/compacted.json').exists()
    monkeypatch.setattr(raw,'remove_file',original)
    result=raw.prepare(s,writers_closed=True,retire=True)
    assert result['status']=='complete' and not (s/'raw').exists()


def test_parent_directory_fsync_precedes_first_unlink(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];order=[];sync=raw.sync_directory;remove=raw.remove_file
    def synced(p):order.append(('sync',str(p)));return sync(p)
    def removed(p,e):
        assert ('sync',str(s)) in order and ('sync',str(s/'raw-archive-storage')) in order
        order.append(('unlink',str(p)));return remove(p,e)
    monkeypatch.setattr(raw,'sync_directory',synced);monkeypatch.setattr(raw,'remove_file',removed)
    raw.prepare(s,writers_closed=True,retire=True)
    assert any(k=='unlink' for k,_ in order)


def append_ledger(ledger,events):
    row={k:v for k,v in events[-1].items() if k!='hash'}
    row.update(sequence=len(events),event_id='legal-later',operation='later_unrelated',arguments={},previous_hash=events[-1]['hash'])
    data=json.dumps(row,sort_keys=True,separators=(',',':')).encode()
    row['hash']='sha256:'+hashlib.sha256(data).hexdigest()
    with (ledger/'events.jsonl').open('ab') as stream:stream.write(json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n')


def test_legal_later_task_and_ledger_events_do_not_change_seal(tiny):
    task,sessions,ledger,events,destination=tiny;s=sessions[0]
    result=raw.prepare(s,destination,writers_closed=True)
    before=(destination/'seal.json').read_bytes()
    event(task,'later_unrelated',{'later':True});append_ledger(ledger,events)
    assert raw.prepare(s,destination,writers_closed=True)==result
    assert (destination/'seal.json').read_bytes()==before


@pytest.mark.parametrize('journal',['task','ledger'])
def test_authority_prefix_mutation_rejected_on_resume(tiny,journal):
    task,sessions,ledger,_,destination=tiny;s=sessions[0]
    raw.prepare(s,destination,writers_closed=True)
    path=(task if journal=='task' else ledger)/'events.jsonl'
    rows=path.read_bytes().splitlines();value=json.loads(rows[0]);value['recorded_at']='altered';rows[0]=json.dumps(value).encode();path.write_bytes(b'\n'.join(rows)+b'\n')
    with pytest.raises(ValueError):raw.prepare(s,destination,writers_closed=True)
    assert (s/'raw').is_dir()


def test_self_rehashed_report_and_seal_cannot_change_original_authority(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    raw.prepare(s,destination,writers_closed=True)
    report_path=s.parent/'report.json';obj=json.loads(report_path.read_text());obj['sessions'][0]['artifacts'].pop(str(s/'raw/unused/extra.bin'));save(report_path,obj)
    seal=destination/'seal.json';obj=json.loads(seal.read_text());obj['original_report']=raw.pointer(report_path);obj['closed_evidence']['original_report']=raw.pointer(report_path);save(seal,obj)
    with pytest.raises(ValueError,match='authority'):raw.RawArchive(s,raw.pointer(seal))


@pytest.mark.parametrize('kind',['file','directory','symlink','corruption'])
def test_unrecorded_or_changed_loose_members_prevent_retirement(tiny,kind):
    _,sessions,*_=tiny;s=sessions[0];destination=raw.default_destination(s)
    raw.prepare(s,writers_closed=True)
    path=s/'raw/unused/extra.bin'
    if kind=='file':(s/'raw/extra').write_bytes(b'foreign')
    elif kind=='directory':(s/'raw/foreign-empty').mkdir()
    elif kind=='symlink':path.unlink();path.symlink_to(s/'request.json')
    else:path.write_bytes(b'changed')
    with pytest.raises((ValueError,OSError)):raw.prepare(s,writers_closed=True,retire=True)
    assert (s/'raw').exists() and not (destination/'compacted.json').exists()


@pytest.mark.parametrize('point',['archive_fsync','seal_publish','parent_fsync','receipt_publish'])
def test_faults_preserve_archive_or_originals_and_resume(tiny,monkeypatch,point):
    _,sessions,*_=tiny;s=sessions[0]
    publish=raw.publish_bytes;sync=raw.sync_directory;syncfile=raw.sync_file
    def published(path,data):
        if point=='seal_publish' and path.name=='seal.json':raise OSError('fault at seal')
        if point=='receipt_publish' and path.name=='compacted.json':raise OSError('fault at receipt')
        return publish(path,data)
    def synced(path):
        if point=='parent_fsync' and path==s:raise OSError('fault at parent fsync')
        return sync(path)
    def syncedfile(path):
        if point=='archive_fsync' and path.name=='raw.tar':raise OSError('fault at archive fsync')
        return syncfile(path)
    monkeypatch.setattr(raw,'publish_bytes',published);monkeypatch.setattr(raw,'sync_directory',synced);monkeypatch.setattr(raw,'sync_file',syncedfile)
    with pytest.raises(OSError,match='fault'):raw.prepare(s,writers_closed=True,retire=True)
    if point!='receipt_publish':assert (s/'raw/unused/extra.bin').is_file()
    else:assert not (s/'raw').exists()
    monkeypatch.setattr(raw,'publish_bytes',publish);monkeypatch.setattr(raw,'sync_directory',sync);monkeypatch.setattr(raw,'sync_file',syncfile)
    assert raw.prepare(s,writers_closed=True,retire=True)['status']=='complete'


def test_authority_mutation_after_tar_but_before_seal_does_not_delete(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0];write=raw.write_tar
    def changed(*args):
        write(*args);p=s.parent/'report.json';p.write_bytes(p.read_bytes()+b' ')
    monkeypatch.setattr(raw,'write_tar',changed)
    with pytest.raises(ValueError):raw.prepare(s,writers_closed=True,retire=True)
    assert (s/'raw/unused/extra.bin').exists() and not (raw.default_destination(s)/'seal.json').exists()


def test_archive_corruption_with_rehashed_seal_rejected_by_original_member_hash(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    raw.prepare(s,destination,writers_closed=True);r=raw.RawArchive(s,raw.pointer(destination/'seal.json'))
    p=destination/'raw.tar'
    with p.open('r+b') as f:f.seek(r.offsets['unused/extra.bin']);f.write(b'!')
    value=json.loads((destination/'seal.json').read_bytes());value['archive']=raw.pointer(p);save(destination/'seal.json',value)
    with pytest.raises(ValueError,match='member bytes'):raw.RawArchive(s,raw.pointer(destination/'seal.json'))


def test_unanchored_final_scope_is_excluded_before_any_write(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    with pytest.raises((ValueError,FileNotFoundError)):raw.prepare(s.parent.parent.parent/'final/cohort/p01',destination,writers_closed=True)
    assert not destination.exists()


def test_destination_and_ancestor_symlinks_rejected(tiny,tmp_path):
    _,sessions,*_=tiny;s=sessions[0]
    alias=tmp_path/'alias';alias.symlink_to(s,target_is_directory=True)
    with pytest.raises(OSError):raw.prepare(s,alias/'other',writers_closed=True)
    assert not (s/'other').exists()


def test_new_parser_paths_are_rejected(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    raw.prepare(s,destination,writers_closed=True);r=raw.RawArchive(s,raw.pointer(destination/'seal.json'))
    import cannbench_msprof_timing as timing
    build=json.loads((s/'request.json').read_bytes())['role_build']
    build=json.loads(Path(build).read_bytes()) if isinstance(build,str) else build
    cases=json.loads((s/'cases.json').read_bytes())
    expected=timing.parse_profile(s/'raw',s/'native/journal.jsonl',build,cases,10)
    assert raw.parse_profile(r,s/'native/journal.jsonl',build,cases,10)==expected
    def malicious(*args):
        value=timing.parse_profile(*args);value['future_path']='/tmp/unchecked';return value
    with pytest.raises(ValueError,match='unreviewed'):raw.parse_profile(r,s/'native/journal.jsonl',build,cases,10,parser=malicious)


@pytest.mark.parametrize('tiny',['observe'],indirect=True)
def test_closed_search_feedback_is_an_independent_admission_authority(tiny):
    _,sessions,*_,destination=tiny
    result=raw.prepare(sessions[0],destination,writers_closed=True)
    reader=raw.RawArchive(sessions[0],result['seal'])
    assert all(row['facts']['report_authority']['kind']=='ledger_closed_feedback_report_v1' for row in reader.closed['sessions'])


def test_raw_archive_composes_after_oracle_verification_retirement(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0]
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',raw.host_lock)
    authority.prepare(s,writers_closed=True,retire=True)
    assert not (s/'verification').exists()
    result=raw.prepare(s,writers_closed=True,retire=True)
    reader=raw.RawArchive(s,result['seal'])
    assert len(reader.logical_files())>2


def test_raw_first_then_verification_retirement_preserves_original_authority(tiny,monkeypatch):
    _,sessions,*_=tiny;s=sessions[0]
    result=raw.prepare(s,writers_closed=True,retire=True)
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',raw.host_lock)
    authority.prepare(s,writers_closed=True,retire=True)
    assert raw.prepare(s,writers_closed=True,retire=True)==result


def test_receipt_tamper_and_recreated_loose_tree_are_rejected(tiny):
    _,sessions,*_=tiny;s=sessions[0]
    result=raw.prepare(s,writers_closed=True,retire=True)
    (s/'raw').mkdir()
    with pytest.raises(ValueError,match='receipt'):raw.RawArchive(s,result['seal'])
    (s/'raw').rmdir()
    save(raw.default_destination(s)/'compacted.json',{'status':'complete'})
    with pytest.raises(ValueError,match='receipt'):raw.RawArchive(s,result['seal'])


def test_reader_transaction_rechecks_original_authority_after_payload_read(tiny):
    _,sessions,*_,destination=tiny;s=sessions[0]
    result=raw.prepare(s,destination,writers_closed=True);reader=raw.RawArchive(s,result['seal'])
    with pytest.raises(ValueError):
        with reader.reader_session():
            with reader.open_binary(s/'raw/unused/extra.bin') as stream:assert stream.read(1)==b'\0'
            path=sessions[-1]/'completion.json';path.write_bytes(path.read_bytes()+b' ')


@pytest.mark.parametrize('kind',['missing_file','missing_empty_dir','duplicate','link','extra','trailer'])
def test_full_tar_grammar_and_inventory_cannot_be_self_rehashed(tiny,kind):
    import io,tarfile
    _,sessions,*_,destination=tiny;s=sessions[0]
    result=raw.prepare(s,destination,writers_closed=True);path=destination/'raw.tar'
    if kind=='trailer':
        with path.open('r+b') as stream:stream.seek(-1,2);stream.write(b'x')
    else:
        with tarfile.open(path,'r:') as tar:rows=[(m,tar.extractfile(m).read() if m.isfile() else None) for m in tar]
        if kind=='missing_file':rows=[r for r in rows if r[0].name!='unused/extra.bin']
        elif kind=='missing_empty_dir':rows=[r for r in rows if r[0].name!='unused/empty']
        elif kind=='duplicate':rows.append(rows[-1])
        else:
            member=tarfile.TarInfo('unexpected');data=b''
            if kind=='link':member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
            rows.append((member,data))
        with tarfile.open(path,'w',format=tarfile.USTAR_FORMAT) as tar:
            for member,data in rows:tar.addfile(member,io.BytesIO(data) if data is not None else None)
    seal=json.loads((destination/'seal.json').read_bytes());seal['archive']=raw.pointer(path);save(destination/'seal.json',seal)
    with pytest.raises(ValueError):raw.RawArchive(s,raw.pointer(destination/'seal.json'))


def test_no_implicit_writer_attestation(tiny):
    _,sessions,*_,destination=tiny
    with pytest.raises(ValueError,match='attestation'):raw.prepare(sessions[0],destination)
    assert not destination.exists()


def test_all_original_nonraw_evidence_and_other_sessions_are_byte_unchanged(tiny):
    task,sessions,*_=tiny;s=sessions[0]
    before={str(p):p.read_bytes() for p in task.rglob('*') if p.is_file() and not p.is_relative_to(s/'raw')}
    oldreport=raw.pointer(s.parent/'report.json')
    original=fixture_module.storage.verify(json.loads((s/'request.json').read_bytes()),s,json.loads((s/'msprof.execution.json').read_bytes()))
    result=raw.prepare(s,writers_closed=True,retire=True)
    reader=raw.RawArchive(s,result['seal'])
    assert reader.verify_transport()==original
    assert raw.pointer(s.parent/'report.json')==oldreport
    assert {path:Path(path).read_bytes() for path in before}==before


def test_special_file_rejected_without_blocking(tmp_path):
    path=tmp_path/'fifo';os.mkfifo(path)
    with pytest.raises(ValueError,match='regular'):raw.fingerprint(path)


def test_invalid_orphan_tar_never_publishes_a_seal_or_deletes_originals(tiny):
    _,sessions,*_=tiny;s=sessions[0];dest=raw.default_destination(s)
    dest.mkdir();(dest/'raw.tar').write_bytes(b'partial archive')
    with pytest.raises(ValueError):raw.prepare(s,writers_closed=True,retire=True)
    assert (s/'raw/unused/extra.bin').exists() and not (dest/'seal.json').exists()

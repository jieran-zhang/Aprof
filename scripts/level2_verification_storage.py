#!/usr/bin/env python3
"""Archive closed oracle verification trees while preserving logical evidence identity.

Only four fixed per-case files are eligible. This does not touch profiler raw data,
native outputs, source, input, or any measurement policy. Shadow archives must be
explicitly selected by a scoped reader context; production discovery is fixed.
"""
from __future__ import annotations
import argparse
import contextlib
import contextvars
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile

VERSION='level2_closed_verification_storage_v1'
NAMES={'metadata.json','execution.json','stdout.log','result.json'}
STEM=re.compile(r'(?:[1-9]|1[0-9]|20)_(?:normal|swapped)_[AB]\Z')
HASH=re.compile(r'sha256:[0-9a-f]{64}\Z')
_OVERRIDES=contextvars.ContextVar('verification_archive_overrides',default=None)
_CACHE=contextvars.ContextVar('verification_archive_cache',default=None)


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()


def safe(path,*,exists=True,directory=False):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts,'canonical absolute verification path required')
    for p in [*reversed(path.parents),path]:
        if not p.exists():
            require(not p.is_symlink(),'symlink verification path')
            if exists:raise FileNotFoundError(p)
            continue
        mode=p.lstat().st_mode
        require(not stat.S_ISLNK(mode),'symlink verification path')
        if p!=path:require(stat.S_ISDIR(mode),'non-directory verification ancestor')
    if exists:require(path.is_dir() if directory else path.is_file(),'unexpected verification file type')
    return path


def raw_read(path):return safe(path).read_bytes()
def raw_ref(path):return {'path':str(path),'sha256':digest(raw_read(path))}
def raw_json(path):return json.loads(raw_read(path))


def location(path, *, check_files=True):
    """Return a process for one exact eligible logical path, otherwise None."""
    path=Path(path)
    if path.name not in NAMES or not STEM.fullmatch(path.parent.name) or path.parent.parent.name!='verification':return None
    require(path.is_absolute() and '..' not in path.parts,'canonical absolute verification path required')
    if check_files:path=safe(path,exists=False)
    session=path.parent.parent.parent;parts=session.parts
    matches=[i for i,p in enumerate(parts) if p=='tasks']
    if len(matches)!=1:return None
    i=matches[0]
    require(i>=1 and parts[i-1] in ('train','validation','test'),'verification split differs')
    tail=parts[i+2:]
    if tail[:1]==('candidates',):
        require(len(tail)>2 and re.fullmatch(r'[A-Za-z0-9_-]+',tail[1]),'invalid candidate verification scope');tail=tail[2:]
    require(len(tail)==4 and tail[0]=='stages' and tail[2] in ('cohort','direct_parent','original_baseline')
            and all(re.fullmatch(r'[A-Za-z0-9_-]+',v) for v in tail[1:]),'unsupported verification scope')
    return session


def process_location(session):
    session=safe(session,directory=True)
    require(location(session/'verification/1_normal_A/metadata.json')==session,'unsupported verification process')
    return session


def closed_from_reader(session, read_bytes):
    """Replay closure using only provided bytes; never access original paths."""
    session=Path(session)
    require(location(session/'verification/1_normal_A/metadata.json',check_files=False)==session,
            'unsupported verification process')
    cohort=session.parent;stage=cohort.parent
    def ref(path):return {'path':str(path),'sha256':digest(read_bytes(path))}
    def load(path):return json.loads(read_bytes(path))
    parts=session.parts;i=parts.index('tasks');task=Path(*parts[:i+2])
    paths=[stage/'result.json',stage/'stage-plan.json',cohort/'plan.json',cohort/'report.json',
           cohort/'group-completion.json',session/'completion.json',session/'msprof.execution.json',
           session/'native/journal.jsonl',session/'validation.json',session/'bindings.json']
    stage_result=load(paths[0]);group=load(paths[4]);completion=load(paths[5]);execution=load(paths[6])
    require(stage_result.get('status')=='passed' and stage_result.get('error') is None
            and stage_result.get('ended_at') is not None,'stage is not terminal passed')
    require(group.get('status')=='passed' and group.get('error') is None and str(session) in group.get('completed_sessions',[])
            and len(group['completed_sessions'])==len(set(group['completed_sessions']))==6,'cohort is not six-process closed')
    require(completion.get('status')=='passed' and completion.get('error') is None,'session did not pass')
    require(execution.get('exit_code')==0 and execution.get('error') is None and execution.get('ended_at') is not None,'native profiler execution is not closed')
    journal=[json.loads(line) for line in read_bytes(paths[7]).splitlines()]
    require(journal and journal[-1].get('type')=='session_end' and journal[-1].get('exit_code')==0,'native session teardown is absent')
    report=load(paths[3]);sessions=[v for v in report['sessions'] if v['directory']==str(session)]
    require(len(sessions)==1,'saved report process identity differs')
    rows=load(paths[8]);require(rows.get('scope')=='final_call_of_final_sample_per_case_config_role','verification scope differs')
    expected={}
    for row in rows['outputs']:
        stem=f"{row['case_id']}_{row['buffer_config']}_{row['role']}"
        require(STEM.fullmatch(stem) and row.get('passed') is True,'unclosed oracle result')
        for name in NAMES:
            logical=session/'verification'/stem/name
            require(str(logical) not in expected,'duplicate verification coverage')
            expected[str(logical)]=sessions[0]['artifacts'].get(str(logical))
            if name!='result.json':require(HASH.fullmatch(expected[str(logical)] or ''),'verification file was not bound by the original report')
    require(expected,'empty verification scope')
    # The existing public event binds the completed stage; later events can append.
    event_path=task/'events.jsonl';previous=None;binding=None;stage_ref=ref(paths[0])
    for number,line in enumerate(read_bytes(event_path).splitlines()):
        row=json.loads(line);body={k:v for k,v in row.items() if k!='hash'}
        require(row.get('sequence')==number and row.get('previous_hash')==previous
                and row.get('hash')==digest((json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()),'verification stage event chain differs')
        previous=row['hash']
        if row.get('kind')=='stage_completed' and row.get('value',{}).get('result')==stage_ref:
            binding={'path':str(event_path),'sequence':number,'hash':previous};break
    require(binding is not None,'no public completed stage binding')
    return {'protected':[ref(p) for p in paths],'event_binding':binding},expected


def closed(session):
    return closed_from_reader(process_location(session),raw_read)


def archive_dir(session):
    overrides=_OVERRIDES.get() or {}
    return Path(overrides.get(str(session),session/'verification-storage'))


def signatures(paths):
    result=[]
    for path in paths:
        s=safe(path).stat();result.append((str(path),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns))
    return tuple(result)


def verified(session,destination=None):
    session=process_location(session);destination=safe(destination or archive_dir(session),directory=True)
    seal_path=destination/'seal.json';archive=destination/'verification.tar'
    signature=signatures([seal_path,archive]);key=(str(session),str(destination));cache=_CACHE.get()
    if cache is not None and key in cache and cache[key][0]==signature:return cache[key][1]
    seal=raw_json(seal_path)
    require(seal.get('version')==VERSION and seal.get('session')==str(session)
            and seal.get('logical_root')==str(session/'verification') and seal.get('source_bytes_preserved') is True,'verification seal identity differs')
    facts,expected=closed(session)
    require(seal.get('closed_evidence')==facts,'closed verification evidence changed')
    require(seal.get('archive')==raw_ref(archive),'verification archive hash differs')
    producer=seal.get('producer',{});require(producer==raw_ref(destination/'producer.py'),'verification producer snapshot differs')
    rows=seal.get('members');require(isinstance(rows,list) and len(rows)==len(expected)
            and {r['path'] for r in rows}==set(expected),'verification member coverage differs')
    by_name={r['relative_path']:r for r in rows}
    require(len(by_name)==len(rows),'duplicate verification archive member')
    payloads={}
    with tarfile.open(archive,'r:') as stream:
        members=stream.getmembers();require(len(members)==len(rows) and {m.name for m in members}==set(by_name),'verification tar coverage differs')
        for member in members:
            row=by_name[member.name];logical=Path(row['path'])
            require(location(logical)==session and member.name==logical.relative_to(session/'verification').as_posix()
                    and member.isfile() and not member.issym() and not member.islnk()
                    and member.size==row['size_bytes'] and member.mode==row['mode']
                    and member.uid==row['uid'] and member.gid==row['gid'] and member.mtime==row['mtime_ns']//1000000000,
                    'verification tar member identity differs')
            data=stream.extractfile(member).read()
            require(digest(data)==row['sha256'] and (expected[str(logical)] is None or expected[str(logical)]==row['sha256']),
                    'verification original bytes differ')
            payloads[str(logical)]=data
    loose_root=session/'verification'
    if loose_root.exists():
        safe(loose_root,directory=True)
        expected_dirs={Path(p).parent.name for p in payloads}
        require(all(p.is_dir() and not p.is_symlink() and p.name in expected_dirs for p in loose_root.iterdir()),
                'unexpected verification case directory')
        for path in loose_root.rglob('*'):
            safe(path,directory=path.is_dir())
            if path.is_file():require(str(path) in payloads and raw_read(path)==payloads[str(path)],'loose verification file differs from sealed archive')
    completion=destination/'compacted.json'
    if completion.exists() or completion.is_symlink():
        receipt=raw_json(completion)
        require(receipt=={'version':VERSION,'status':'complete','seal':raw_ref(seal_path),'source_bytes_preserved':True}
                and not loose_root.exists(),'verification completion changed or loose tree reappeared')
    value={'seal':seal,'seal_ref':raw_ref(seal_path),'payloads':payloads,'destination':str(destination)}
    if cache is not None:cache[key]=(signature,value)
    return value


def reverify_cached():
    """Recheck every visited seal/protected proof before a caller publishes."""
    cache=_CACHE.get()
    if cache is None:return
    values=list(cache.keys());token=_CACHE.set(None)
    try:
        for session,destination in values:verified(Path(session),Path(destination))
    finally:_CACHE.reset(token)


@contextlib.contextmanager
def reader_session(overrides=None):
    mapped=None
    if overrides is not None:
        require(_OVERRIDES.get() is None,'nested shadow archive replacement prohibited')
        mapped={str(process_location(Path(k))):str(safe(v,directory=True)) for k,v in overrides.items()}
    token=_CACHE.set({}) if _CACHE.get() is None else None
    mapping_token=_OVERRIDES.set(mapped) if mapped is not None else None
    try:
        yield
        if token is not None:
            # Detect mutation during a complete reader transaction before returning.
            reverify_cached()
    finally:
        if mapping_token is not None:_OVERRIDES.reset(mapping_token)
        if token is not None:_CACHE.reset(token)


def resolve(path):
    session=location(path)
    if session is None:return None
    destination=archive_dir(session)
    if not destination.exists() and not destination.is_symlink():return None
    value=verified(session,destination)
    require(str(path) in value['payloads'],'logical verification file not sealed')
    return value


def read_bytes(path):
    path=Path(path);value=resolve(path)
    return value['payloads'][str(path)] if value is not None else Path(path).read_bytes()


def is_file(path):
    value=resolve(Path(path))
    if value is not None:return True
    return safe(path,exists=False).is_file()


def evidence_binding(path,expected=None):
    value=resolve(Path(path))
    if value is None:return None
    data=value['payloads'][str(path)];actual=digest(data)
    require(expected is None or expected==actual,'logical verification hash differs')
    return {'origin':{'path':str(path),'sha256':actual},'seal':value['seal_ref'],
            'archive':value['seal']['archive'],'producer':value['seal']['producer'],
            'closed_evidence':value['seal']['closed_evidence'],'bytes':data}


def logical_files(directory):
    """Expose only archived verification files to artifact closure walkers."""
    directory=safe(directory,directory=True);values=set()
    for marker in directory.rglob('verification-storage/seal.json'):
        session=marker.parent.parent;values.update(verified(session)['payloads'])
    for session,destination in (_OVERRIDES.get() or {}).items():
        if Path(session).is_relative_to(directory):values.update(verified(Path(session),Path(destination))['payloads'])
    return sorted(values)


def prepare(session,destination=None,*,writers_closed=False,retire=False):
    """Create/verify a sealed archive; explicit retire removes only its fixed files."""
    require(writers_closed is True,'coordinator must attest all selected writers closed')
    session=process_location(session);destination=Path(destination) if destination else session/'verification-storage'
    require(not retire or destination==session/'verification-storage','shadow archives cannot retire live evidence')
    from level2_storage import exclusive_host, storage_lock, mkdir, write_new, publish_archive, sync_directory
    # Shadows only create /tmp evidence and cannot remove live files.
    require(retire or destination.is_relative_to(Path('/tmp')),'non-retiring shadow archive must be under /tmp')
    with exclusive_host():
        facts,expected=closed(session)
        if not destination.exists():safe(destination.parent,directory=True);destination.mkdir()
        safe(destination,directory=True)
        with storage_lock(destination):
            if (destination/'seal.json').exists():value=verified(session,destination)
            else:
                root=safe(session/'verification',directory=True)
                paths=[p for p in root.rglob('*') if not p.is_dir()]
                require({str(p) for p in paths}==set(expected),'original verification tree coverage differs')
                rows=[];buffer=io.BytesIO()
                with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                    for path in sorted(paths):
                        data=raw_read(path);info=path.stat();actual=digest(data)
                        require(expected[str(path)] is None or expected[str(path)]==actual,'original report verification hash differs')
                        row={'path':str(path),'relative_path':path.relative_to(root).as_posix(),'sha256':actual,'size_bytes':len(data),
                             'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'mtime_ns':info.st_mtime_ns}
                        rows.append(row);member=tarfile.TarInfo(row['relative_path']);member.size=len(data);member.mode=row['mode'];member.uid=row['uid'];member.gid=row['gid'];member.mtime=row['mtime_ns']//1000000000
                        archive.addfile(member,io.BytesIO(data))
                publish_archive(destination/'verification.tar',buffer.getvalue())
                publish_archive(destination/'producer.py',raw_read(Path(__file__).resolve()))
                seal={'version':VERSION,'session':str(session),'logical_root':str(root),'closed_evidence':facts,
                      'archive':raw_ref(destination/'verification.tar'),'producer':raw_ref(destination/'producer.py'),
                      'members':rows,'source_bytes_preserved':True}
                write_new(destination/'seal.json',seal);value=verified(session,destination)
            if retire:
                require(closed(session)[0]==value['seal']['closed_evidence'],'verification evidence changed before retirement')
                for name in ('verification.tar','seal.json','producer.py'):
                    fd=os.open(safe(destination/name),os.O_RDONLY|os.O_NOFOLLOW)
                    try:os.fsync(fd)
                    finally:os.close(fd)
                sync_directory(destination)
                sync_directory(destination.parent)  # Persist the archive directory entry before retiring originals.
                for path,data in value['payloads'].items():
                    path=Path(path)
                    if path.exists() or path.is_symlink():
                        require(raw_read(path)==data,'verification file changed before retirement');path.unlink()
                root=session/'verification'
                if root.exists():
                    for directory in sorted(root.iterdir()):safe(directory,directory=True);sync_directory(directory);directory.rmdir()
                    sync_directory(root)
                    root.rmdir();sync_directory(session)
                receipt={'version':VERSION,'status':'complete','seal':raw_ref(destination/'seal.json'),'source_bytes_preserved':True}
                if (destination/'compacted.json').exists():require(raw_json(destination/'compacted.json')==receipt,'verification receipt changed')
                else:write_new(destination/'compacted.json',receipt)
                verified(session,destination)
            return {'version':VERSION,'status':'complete' if retire else 'sealed_shadow','session':str(session),
                    'seal':raw_ref(destination/'seal.json'),'archived_files':len(value['payloads']),'original_bytes_preserved':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',required=True);parser.add_argument('--shadow-destination')
    parser.add_argument('--writers-closed',action='store_true');parser.add_argument('--retire',action='store_true')
    args=parser.parse_args();print(json.dumps(prepare(Path(args.session),Path(args.shadow_destination) if args.shadow_destination else None,
        writers_closed=args.writers_closed,retire=args.retire),indent=2))

if __name__=='__main__':main()

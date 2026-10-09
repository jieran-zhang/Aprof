#!/usr/bin/env python3
"""Versioned byte-preserving raw-profiler transport; no native calls at import."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
from msprof_search_protocol import LITE_PRODUCER

VERSION = 'msprof_raw_storage_transport_v1'
# Reviewed pre-lite reader identity; accepted only for replay of v2 capture.
LEGACY_CAPTURE_PRODUCER_SHA = 'sha256:4d4f8d3f8d39d627bf6d5ead55d0a9e8d774a28be9f976384dc25584112e3b23'
DIRECT = {'mode': 'direct_artifact_raw_v1'}
LOCAL = {'mode': 'local_tmp_full_copyback_v1', 'scratch_root': '/tmp',
         'inventory': 'all_regular_files_sha256_and_directories', 'local_filesystem_required': True}
LOCAL_FILESYSTEMS = {'ext4', 'xfs', 'tmpfs', 'overlay', 'btrfs'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return 'sha256:'+h.hexdigest()


def fsync_directory(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def save(path, value):
    """Publish a new JSON file atomically and persist its directory entry.

    The caller owns the exclusive campaign lock and a fresh observation path.
    Existing immutable records are never intentionally replaced.
    """
    path=Path(path)
    if path.exists() or path.is_symlink():raise FileExistsError(path)
    descriptor,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w') as stream:
            json.dump(value,stream,sort_keys=True,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():raise FileExistsError(path)
        os.rename(temporary,path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def persist_tree(root,snapshot):
    """Require successful file and directory fsync before publishing transfer proof."""
    root=Path(root)
    for row in snapshot['files']:
        descriptor=os.open(root/row['relative_path'],os.O_RDONLY|os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):raise ValueError('raw file is no longer regular')
            os.fsync(descriptor)
        finally:os.close(descriptor)
    # Children before parents: entries for empty directories matter as well.
    relative=sorted(snapshot['directories'],key=lambda name:(-len(Path(name).parts),name))
    for name in relative:fsync_directory(root/name)
    for parent in (root,root.parent,root.parent.parent):fsync_directory(parent)
    return {'mode':'fsync_raw_files_directories_atomic_records_v1','file_count':len(snapshot['files']),
            'relative_directories':relative,'raw_root_and_two_parents':True}


def producer_matches(pointer, *, historical=False):
    allowed = {sha(__file__)}
    if historical:
        allowed.add(LEGACY_CAPTURE_PRODUCER_SHA)
    return (isinstance(pointer, dict) and set(pointer) == {'path', 'sha256'}
            and pointer['path'] == str(Path(__file__).resolve()) and pointer['sha256'] in allowed)


def policy(request):
    value=request.get('capture_storage')
    if request.get('version') not in ('msprof_kernel_time_study_v2', LITE_PRODUCER):
        if 'capture_storage' in request:raise ValueError('capture_storage requires a supported prepared producer')
        return dict(DIRECT)
    if value is None:
        if 'capture_storage_producer' in request:raise ValueError('undeclared raw transport producer')
        return dict(DIRECT)
    if value not in (DIRECT,LOCAL):raise ValueError('unreviewed capture_storage policy')
    if value==LOCAL and not producer_matches(request.get('capture_storage_producer'),
            historical=request.get('version')=='msprof_kernel_time_study_v2'):
        raise ValueError('raw transport producer must be frozen in request')
    return dict(value)


def local_filesystem(path):
    """Record actual local mount type, rejecting network/FUSE scratch mounts."""
    target=Path(path).resolve();mounts=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);fields=left.split();point=Path(re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),fields[4]))
        if target.is_relative_to(point):mounts.append((len(point.parts),str(point),right.split()[0]))
    if not mounts:raise ValueError('scratch filesystem cannot be verified')
    _,point,kind=max(mounts)
    if kind not in LOCAL_FILESYSTEMS:raise ValueError('scratch is not an approved local filesystem: '+kind)
    return {'mount_point':point,'filesystem_type':kind}


def inventory(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('raw root must be a real directory')
    directories=[];files=[]
    for path in sorted(root.rglob('*')):
        mode=path.lstat().st_mode;relative=path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode):raise ValueError('raw symlink not allowed: '+relative)
        if stat.S_ISDIR(mode):directories.append(relative)
        elif stat.S_ISREG(mode):
            before=path.stat();digest=sha(path);after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('raw file changed while hashing')
            files.append({'relative_path':relative,'bytes':after.st_size,'sha256':digest})
        else:raise ValueError('nonregular raw entry: '+relative)
    return {'directories':directories,'files':files}


def allocate(request,directory):
    """Create scratch only after the cohort host lock has been acquired."""
    chosen=policy(request);directory=Path(directory).resolve()
    if chosen==LOCAL and not producer_matches(request.get('capture_storage_producer')):
        raise ValueError('new capture requires the current transport producer')
    if chosen==DIRECT:return directory/'raw',None
    filesystem=local_filesystem('/tmp')
    temporary=Path(tempfile.mkdtemp(prefix='aprof-msprof-',dir='/tmp'));raw=temporary/'raw';raw.mkdir()
    record={'version':VERSION,'capture_storage':chosen,'capture_root':str(raw),'scratch_container':str(temporary),
            'archive_root':str(directory/'raw'),'filesystem':filesystem,'allocated_at':time.time(),
            'capture_storage_producer':request['capture_storage_producer']}
    save(directory/'raw-storage.request.json',record)
    return raw,record


def checked_allocation(record,directory,execution,*,live):
    """Validate destructive-action operands before copying or removing anything."""
    fields={'version','capture_storage','capture_root','scratch_container','archive_root','filesystem',
            'allocated_at','capture_storage_producer'}
    declared=json.loads((directory/'raw-storage.request.json').read_text())
    if not isinstance(record,dict) or set(record)!=fields or declared!=record:
        raise ValueError('raw allocation and caller identity differ')
    if record['version']!=VERSION or record['capture_storage']!=LOCAL:
        raise ValueError('unreviewed raw allocation policy')
    if not producer_matches(record['capture_storage_producer'],historical=not live):
        raise ValueError('raw transport producer differs')
    source=Path(record['capture_root']);container=Path(record['scratch_container'])
    if source!=container/'raw' or container.parent!=Path('/tmp') or not re.fullmatch(r'aprof-msprof-[A-Za-z0-9_-]+',container.name):
        raise ValueError('unreviewed raw scratch root')
    if record['archive_root']!=str(directory/'raw'):raise ValueError('raw archive root differs')
    if [v for v in execution.get('argv',[]) if isinstance(v,str) and v.startswith('--output=')]!=['--output='+str(source)]:
        raise ValueError('raw capture argv not the declared scratch root')
    times=[record['allocated_at'],execution.get('started_at'),execution.get('ended_at')]
    if any(type(t) not in (int,float) or not math.isfinite(t) for t in times) or not times[0]<=times[1]<=times[2]<=time.time():
        raise ValueError('raw capture allocation/execution timing invalid')
    if execution.get('exit_code') is None and execution.get('error') is None:raise ValueError('raw execution has not ended')
    fs=record['filesystem']
    if not isinstance(fs,dict) or set(fs)!={'mount_point','filesystem_type'} or fs['filesystem_type'] not in LOCAL_FILESYSTEMS or not isinstance(fs['mount_point'],str) or not Path('/tmp').is_relative_to(Path(fs['mount_point'])):
        raise ValueError('raw scratch filesystem evidence invalid')
    if live and (source.is_symlink() or container.is_symlink() or source.resolve()!=source or container.resolve()!=container or not source.is_dir() or local_filesystem(container)!=fs):
        raise ValueError('live raw scratch identity differs')
    successful=execution.get('exit_code')==0 and execution.get('error') is None
    journal=directory/'native/journal.jsonl'
    final=None
    if journal.is_file():
        lines=journal.read_text().splitlines()
        if lines:final=json.loads(lines[-1])
    native_complete=bool(final and final.get('type')=='session_end' and final.get('exit_code')==0 and
                         final.get('context_destroyed') is True and final.get('stream_destroyed') is True)
    if successful and not native_complete:raise ValueError('successful raw capture has no complete native teardown')
    return source,container,native_complete


def archive(record,directory):
    """Copy after reaping msprof; persist all required evidence before cleanup.

    Cleanup is separate best-effort housekeeping. Its optional receipt can be
    absent after a storage error; absence never proves that scratch was removed.
    Required transport persistence failure always leaves scratch untouched.
    """
    if record is None:return
    directory=Path(directory).resolve();started=time.time();source=None
    try:
        execution=directory/'msprof.execution.json';event=json.loads(execution.read_text())
        source,container,native_complete=checked_allocation(record,directory,event,live=True)
        destination=directory/'raw';source_before=inventory(source)
        shutil.copytree(source,destination,copy_function=shutil.copyfile)
        source_after=inventory(source);archived=inventory(destination)
        if source_before!=source_after or source_before!=archived:raise ValueError('raw relocation tree/bytes differ')
        durability=persist_tree(destination,archived)
        if inventory(destination)!=archived:raise ValueError('raw archive changed during persistence')
        proof={**record,'source_inventory':source_before,'archive_inventory':archived,'durability':durability,
               'native_teardown_complete':native_complete,
               'execution':{'path':str(execution),'sha256':sha(execution)},
               'allocation':{'path':str(directory/'raw-storage.request.json'),'sha256':sha(directory/'raw-storage.request.json')},
               'archive_started_at':started,'archive_completed_at':time.time()}
        save(directory/'raw-storage.copyback.json',proof)
        manifest={**proof,'status':'complete',
                  'scratch_cleanup':{'policy':'best_effort_after_durable_transfer','outcome':'consult_optional_receipt'},
                  'copyback':{'path':str(directory/'raw-storage.copyback.json'),'sha256':sha(directory/'raw-storage.copyback.json')}}
        # No destructive housekeeping is reachable before BOTH required records
        # and their parent entries have been persisted successfully.
        save(directory/'raw-storage.json',manifest)
    except BaseException as exc:
        save(directory/'raw-storage.failed.json',{**record,'status':'failed','error':{'type':type(exc).__name__,'message':str(exc)},
             'scratch_preserved':Path(record['capture_root']).exists(),
             'archive_may_be_partial':(directory/'raw').exists(),'started_at':started,'ended_at':time.time()})
        raise
    cleanup={'status':'retained','error':None,'reason':'native_teardown_incomplete'}
    if native_complete:
        cleanup={'status':'removed','error':None}
        try:shutil.rmtree(container)
        except OSError as exc:cleanup={'status':'retained','error':str(exc),'reason':'cleanup_failed'}
    receipt={'version':VERSION,'transfer':{'path':str(directory/'raw-storage.json'),'sha256':sha(directory/'raw-storage.json')},
             'scratch_container':str(container),'cleanup':cleanup,'recorded_at':time.time()}
    try:save(directory/'raw-storage.cleanup.json',receipt)
    except OSError:pass  # Transfer is already durable; cleanup outcome stays unknown.


def verify(request,directory,execution):
    """Return the actual argv raw path, closure files and observed storage identity."""
    chosen=policy(request);directory=Path(directory).resolve()
    if chosen==LOCAL and not producer_matches(request.get('capture_storage_producer')):
        raise ValueError('new capture requires the current transport producer')
    if chosen==DIRECT:
        if any((directory/name).exists() for name in ('raw-storage.request.json','raw-storage.copyback.json','raw-storage.json','raw-storage.failed.json','raw-storage.cleanup.json')):
            raise ValueError('undeclared raw relocation evidence')
        return directory/'raw',[],({'capture_storage':chosen} if 'capture_storage' in request else {})
    if (directory/'raw-storage.failed.json').exists():raise ValueError('raw transport recorded a persistence or identity failure')
    path=directory/'raw-storage.json';manifest=json.loads(path.read_text());allocation=directory/'raw-storage.request.json'
    declared=json.loads(allocation.read_text())
    if manifest.get('version')!=VERSION or manifest.get('status')!='complete' or manifest.get('capture_storage')!=chosen:
        raise ValueError('raw transport manifest contract differs')
    if any(manifest.get(k)!=v for k,v in declared.items()):raise ValueError('raw allocation declaration differs')
    source,container,native_complete=checked_allocation(declared,directory,execution,live=False)
    proof_path=directory/'raw-storage.copyback.json';proof=json.loads(proof_path.read_text())
    if manifest.get('copyback')!={'path':str(proof_path),'sha256':sha(proof_path)} or proof!={k:v for k,v in manifest.items() if k not in ('status','scratch_cleanup','copyback')}:
        raise ValueError('raw copyback attestation differs')
    if manifest.get('capture_storage_producer')!=request['capture_storage_producer']:raise ValueError('raw transport producer binding differs')
    fs=manifest['filesystem']
    for key,actual in [('execution',directory/'msprof.execution.json'),('allocation',allocation)]:
        if manifest.get(key)!={'path':str(actual),'sha256':sha(actual)}:raise ValueError('raw transport '+key+' binding differs')
    expected=inventory(directory/'raw')
    if manifest.get('source_inventory')!=expected or manifest.get('archive_inventory')!=expected:raise ValueError('raw full relative tree/bytes differ')
    if not (execution['ended_at']<=manifest['archive_started_at']<=manifest['archive_completed_at']):raise ValueError('raw archive precedes completed capture')
    if manifest.get('scratch_cleanup')!={'policy':'best_effort_after_durable_transfer','outcome':'consult_optional_receipt'}:raise ValueError('raw cleanup policy invalid')
    expected_durability={'mode':'fsync_raw_files_directories_atomic_records_v1','file_count':len(expected['files']),
        'relative_directories':sorted(expected['directories'],key=lambda name:(-len(Path(name).parts),name)),
        'raw_root_and_two_parents':True}
    if manifest.get('durability')!=expected_durability or manifest.get('native_teardown_complete')!=native_complete:raise ValueError('raw durability/teardown proof differs')
    if [v for v in execution.get('argv',[]) if v.startswith('--output=')]!=['--output='+str(source)]:raise ValueError('raw capture argv not the declared scratch root')
    files=[path,allocation,proof_path,*[directory/'raw'/row['relative_path'] for row in expected['files']]]
    return source,files,{'capture_storage':chosen,'capture_filesystem':fs,'capture_storage_producer_hash':request['capture_storage_producer']['sha256']}

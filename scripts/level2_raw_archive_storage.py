"""Closed LOCAL raw storage, separate post-capture reader/writer.

Only existing ledger-anchored six-process AA/search reports authorize storage.
Shared parser/report/dataset/portable integration is not installed by this module.
Archived producer snapshots are inert and never executed.
"""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import tempfile

LEGACY_VERSION='level2_closed_raw_storage_v1'
VERSION='level2_closed_raw_storage_v2'
VERSIONS=(LEGACY_VERSION,VERSION)
HASH=re.compile(r'sha256:[0-9a-f]{64}\Z')
CHUNK=1024*1024
TOP={'version','csv','csv_hash','target_tasks','warmup_tasks_excluded','other_tasks','samples'}
AUX={'auxiliary_csv','auxiliary_csv_hash','compute_tasks','auxiliary_tasks'}
SAMPLE={'case_id','buffer_config','pair_id','role','order','task_us','core_us','event_us','task_span_us','inter_task_gap_us','launches','csv_rows'}
SAMPLE_AUX={'auxiliary_tasks','auxiliary_csv_rows','auxiliary_task_us'}
# Exact select_dispatch result copied by the unchanged timing parser, plus its
# observed native sequence. Legacy baseline samples omit this object entirely.
DISPATCH={'tiling_key','kernel_entry','group_id','fallback','captured_kernel_sequence'}


def require(x,m):
    if not x:raise ValueError(m)


def safe(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts,'absolute canonical path required')
    for q in [*reversed(p.parents),p]:
        require(not q.is_symlink(),'symlink path forbidden')
    require(p.is_file(),'regular file required')
    require(stat.S_ISREG(p.stat().st_mode),'special file forbidden')
    return p


def pointer(path):return {'path':str(path),'sha256':fingerprint(path)['sha256']}


def load_ref(ref):
    require(isinstance(ref,dict) and set(ref)=={'path','sha256'} and HASH.fullmatch(ref['sha256']),'invalid reference')
    data=small_read(ref['path'])
    require('sha256:'+hashlib.sha256(data).hexdigest()==ref['sha256'],'reference hash differs')
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def nonfinite(v):raise ValueError('nonfinite JSON')
    return json.loads(data,object_pairs_hook=pairs,parse_constant=nonfinite)


def relative(name):
    require(isinstance(name,str) and name and '\\' not in name,'invalid member name')
    p=PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and '.' not in name.split('/') and str(p)==name,'noncanonical member name')
    return name


def signature(path):
    s=safe(path).stat();return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


class RawArchive:
    """One independently report-authorized full raw inventory, without extraction."""
    def __init__(self,session,seal_ref,closed_report_ref=None,*,shadow=False):
        self.session=Path(session);self.logical=self.session/'raw'
        require(self.session.is_absolute() and '..' not in self.session.parts,'invalid session')
        self.seal=load_ref(seal_ref)
        self.version=self.seal.get('version')
        require(self.version in VERSIONS,'unsupported raw storage version')
        group=self.session.parent.parent.name
        require(self.session.parent.name in {'cohort','direct_parent','original_baseline'}
                and (group=='search' or re.fullmatch(r'aa-[A-Za-z0-9_-]+',group) or (self.version==VERSION and group=='final'))
                and self.session.parent.parent.parent.name=='stages','unsupported/unanchored final scope')
        self.closed=cohort_facts(self.session,version=self.version)
        original=self.closed['original_report']
        require(closed_report_ref is None or closed_report_ref==original,'external report anchor differs')
        closed_report_ref=original
        self.seal_ref=seal_ref;self.report_ref=closed_report_ref
        report=load_ref(closed_report_ref)
        require(set(self.seal)=={'version','logical_root','archive','original_report','closed_evidence','producer','producer_snapshot','source_bytes_preserved'}
                and self.seal['source_bytes_preserved'] is True,'unknown/incomplete raw seal schema')
        require(self.seal.get('version')==self.version and self.seal.get('logical_root')==str(self.logical),'seal scope differs')
        require(self.seal.get('original_report')==closed_report_ref,'external report anchor differs')
        require(self.seal.get('closed_evidence')==self.closed,'closed authority differs')
        snapshot=Path(seal_ref['path']).parent/'producer.py'
        require(self.seal.get('producer_snapshot')==pointer(snapshot)
                and self.seal['producer_snapshot']['sha256']==self.seal['producer']['sha256'],'inert producer snapshot differs')
        require(report.get('evidence_status')=='verified_complete' and report.get('protocol')=='msprof_task_time_exploration_v2','unverified report')
        sessions=report.get('sessions',[])
        require(len(sessions)==6 and len({s['directory'] for s in sessions})==6,'six-session report required')
        matches=[s for s in sessions if s['directory']==str(self.session)]
        require(len(matches)==1,'report session differs');self.report_session=matches[0]
        self.refs=self.report_session['artifacts'];self.protected=[]
        def read(name):
            p=self.session/name;digest=self.refs.get(str(p))
            require(isinstance(digest,str) and HASH.fullmatch(digest),'unbound original transport evidence')
            ref={'path':str(p),'sha256':digest};self.protected.append(ref);return load_ref(ref)
        require(type(shadow) is bool,'explicit shadow boolean required')
        require(not self.logical.is_symlink(),'symlink logical raw root')
        self.request=read('request.json');self.manifest=read('raw-storage.json')
        allocation=read('raw-storage.request.json');proof=read('raw-storage.copyback.json');execution=read('msprof.execution.json')
        require(not (self.session/'raw-storage.failed.json').exists(),'failed raw transport')
        import msprof_raw_storage as transport
        require(transport.policy(self.request)==transport.LOCAL,'only unchanged LOCAL capture supported')
        source,_,native_complete=transport.checked_allocation(allocation,self.session,execution,live=False)
        m=self.manifest
        require(m.get('status')=='complete' and m.get('capture_storage')==transport.LOCAL,'incomplete transport')
        require(all(m.get(k)==v for k,v in allocation.items()),'allocation declaration differs')
        require(m.get('copyback')==pointer(self.session/'raw-storage.copyback.json')
                and proof=={k:v for k,v in m.items() if k not in {'status','scratch_cleanup','copyback'}},'copyback binding differs')
        require(m.get('capture_storage_producer')==self.request.get('capture_storage_producer'),'capture producer differs')
        for key,name in [('execution','msprof.execution.json'),('allocation','raw-storage.request.json')]:
            require(m.get(key)==pointer(self.session/name),'transport source reference differs')
        require(m.get('scratch_cleanup')=={'policy':'best_effort_after_durable_transfer','outcome':'consult_optional_receipt'},'cleanup policy differs')
        require(execution['ended_at']<=m['archive_started_at']<=m['archive_completed_at'],'copyback timing differs')
        inv=m.get('archive_inventory');require(isinstance(inv,dict) and set(inv)=={'files','directories'} and inv==m.get('source_inventory'),'full inventories differ')
        self.files={};self.dirs=set()
        for d in inv['directories']:
            relative(d);require(d not in self.dirs,'duplicate directory');self.dirs.add(d)
        for row in inv['files']:
            require(set(row)=={'relative_path','bytes','sha256'},'inventory file fields differ')
            n=relative(row['relative_path']);require(n not in self.files and n not in self.dirs,'duplicate member')
            require(type(row['bytes']) is int and row['bytes']>=0 and HASH.fullmatch(row['sha256']),'invalid file inventory')
            require(self.refs.get(str(self.logical/n))==row['sha256'],'raw member is not in original report')
            self.files[n]=row
        for n in [*self.files,*self.dirs]:
            for p in PurePosixPath(n).parents:
                if str(p)!='.':require(str(p) in self.dirs,'missing ancestor directory')
        require(self.files and not self.files.keys() & self.dirs,'invalid roster')
        raw_report_paths={k for k in self.refs if k.startswith(str(self.logical)+'/')}
        require(raw_report_paths=={str(self.logical/n) for n in self.files},'report/raw inventory roster differs')
        expected_durability={'mode':'fsync_raw_files_directories_atomic_records_v1','file_count':len(self.files),
          'relative_directories':sorted(self.dirs,key=lambda n:(-len(Path(n).parts),n)),'raw_root_and_two_parents':True}
        require(m.get('durability')==expected_durability and m.get('native_teardown_complete')==native_complete and native_complete,'durability/teardown differs')
        self.actual_capture_root=source
        self.environment={'capture_storage':dict(transport.LOCAL),'capture_filesystem':m['filesystem'],
                          'capture_storage_producer_hash':m['capture_storage_producer']['sha256']}
        require(all(self.report_session.get('environment_binding',{}).get(k)==v for k,v in self.environment.items()),'original capture identity differs')
        self.archive=Path(self.seal['archive']['path'])
        require(self.archive.parent==Path(seal_ref['path']).parent,'archive outside seal directory')
        require(pointer(self.archive)==self.seal['archive'],'archive hash differs')
        self.offsets={};self._verify_tar()
        self.protected += [seal_ref,closed_report_ref,pointer(Path(transport.__file__).resolve()),pointer(Path(__file__).resolve()),pointer(snapshot)]
        # Native teardown used by the unchanged transport validator must also be bound.
        journal=self.session/'native/journal.jsonl'
        require(self.refs.get(str(journal))==fingerprint(journal)['sha256'],'unbound native journal')
        self.protected.append(pointer(journal))
        self._check_loose(complete=shadow)
        receipt=Path(seal_ref['path']).parent/'compacted.json'
        if receipt.exists() or receipt.is_symlink():
            require(load_ref(pointer(receipt))==completion(self.seal_ref,self.version) and not self.logical.exists(),'retirement receipt differs or raw tree reappeared')
            self.protected.append(pointer(receipt))
        self.signatures={p['path']:signature(p['path']) for p in self.protected+[self.seal['archive']]}
        self.reverify_cached()  # No authority may change between its first read and cache publication.

    def _verify_tar(self):
        self.offsets=validate_tar(self.archive,self.files,self.dirs)

    def _unchanged(self):
        for path,before in self.signatures.items():require(signature(path)==before,'protected storage evidence changed')

    def reverify_cached(self):
        authority=checked_authority()
        # The opt-in byte lookup defers physical checks until an explicit
        # boundary. Raw writers call this before unlink and receipt publication;
        # ordinary readers retain the verifier's default eager behavior.
        self._unchanged()
        # Frozen signatures are only a fast mutation guard; exact hashes anchor each opening.
        for ref in self.protected:require(pointer(Path(ref['path']))==ref,'protected evidence hash differs')
        require(pointer(self.archive)==self.seal['archive'],'archive hash changed')
        require(cohort_facts(self.session,version=self.version)==self.closed,'closed authority changed')
        self._check_loose()
        # The final logical read must precede the physical check, so a changed
        # oracle cannot escape until the next post-unlink boundary.
        if authority.lookup_cache_enabled():authority.reverify_cached()

    def _check_loose(self,complete=False):
        files,dirs=loose_inventory(self.logical)
        require(set(files)<=set(self.files) and dirs<=self.dirs,'unknown loose raw member')
        if complete:require(set(files)==set(self.files) and dirs==self.dirs,'incomplete original raw tree')
        for name,value in files.items():
            row=self.files[name]
            require(value=={'sha256':row['sha256'],'size_bytes':row['bytes']},'loose raw bytes differ')

    @contextlib.contextmanager
    def reader_session(self):
        try:yield self
        finally:self.reverify_cached()

    def logical_files(self):return [self.logical/n for n in sorted(self.files)]

    def verify_transport(self):
        # Exact original verifier tuple. Maintenance proofs must remain separate
        # or replay would mutate the signed original report artifacts map.
        self._unchanged()
        files=[self.session/n for n in ('raw-storage.json','raw-storage.request.json','raw-storage.copyback.json')]
        return self.actual_capture_root,files+[self.logical/n for n in self.files],dict(self.environment)

    def name(self,path):
        p=Path(path)
        require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(self.logical),'logical raw path outside scope')
        n=relative(p.relative_to(self.logical).as_posix());require(n in self.files,'unknown logical member');return n

    def fingerprint(self,path):
        n=self.name(path);r=self.files[n];self._unchanged()
        return {'sha256':r['sha256'],'size_bytes':r['bytes']}

    @contextlib.contextmanager
    def open_binary(self,path):
        n=self.name(path);self._unchanged()
        with file_stream(self.archive) as archive_stream, tarfile.open(fileobj=archive_stream,mode='r:') as tf:
            member=tf.getmember(n)
            require(member.offset_data==self.offsets[n] and member.size==self.files[n]['bytes'],'member offset changed')
            with tf.extractfile(member) as stream:yield stream
        self._unchanged()

    def evidence_binding(self,path,expected):
        n=self.name(path);require(expected==self.files[n]['sha256'],'expected logical digest differs')
        self._unchanged()
        return {'version':self.version,'origin':{'path':str(path),'sha256':expected},'seal':self.seal_ref,
                'archive':self.seal['archive'],'producer':self.seal['producer_snapshot'],
                'closed_evidence':self.closed}


def validate_tar(archive, files, dirs):
    """Validate every original member before seal publication or reader use."""
    offsets={}
    seen=set();cursor=0
    logical_size=sum(512+((r['bytes']+511)//512)*512 for r in files.values())+512*len(dirs)
    exact_size=((logical_size+1024+10239)//10240)*10240
    require(archive.stat().st_size==exact_size,'unexpected tar size/trailer')
    with file_stream(archive) as archive_stream, tarfile.open(fileobj=archive_stream,mode='r:') as tf:
        for member in tf:
            n=relative(member.name);require(n not in seen,'duplicate tar member');seen.add(n)
            require(member.offset==cursor and member.offset_data==cursor+512,'unreviewed tar extension header')
            cursor=member.offset_data+((member.size+511)//512)*512
            require(not member.pax_headers and not member.issym() and not member.islnk(),'unreviewed tar extension/link')
            if member.isdir():require(n in dirs and member.size==0,'unexpected directory');continue
            require(member.isfile() and n in files,'unexpected raw member')
            row=files[n];require(member.size==row['bytes'],'raw member size differs')
            h=hashlib.sha256();size=0
            with tf.extractfile(member) as stream:
                for b in iter(lambda:stream.read(CHUNK),b''):h.update(b);size+=len(b)
            require(size==row['bytes'] and 'sha256:'+h.hexdigest()==row['sha256'],'raw member bytes differ')
            offsets[n]=member.offset_data
    require(seen==set(files)|dirs,'full raw roster differs')
    with file_stream(archive) as stream:
        stream.seek(cursor)
        for block in iter(lambda:stream.read(CHUNK),b''):require(not any(block),'nonzero tar trailer')
    return offsets


def _no_paths(value):
    if isinstance(value,str):require('/' not in value and '\\' not in value,'unexpected parser path')
    elif isinstance(value,dict):
        for k,v in value.items():_no_paths(k);_no_paths(v)
    elif isinstance(value,list):
        for v in value:_no_paths(v)


def remap_parsed(result,mapping,raw):
    require(isinstance(result,dict) and (set(result)==TOP or set(result)==TOP|AUX),'unreviewed parser result fields')
    require(result['version']=='msprof_kernel_time_study_v2' and set(result)==TOP|AUX,'only v2 full parser contract supported')
    for field in ('csv','auxiliary_csv'):
        physical=result[field];require(type(physical) is str and physical in mapping,'unexpected CSV path')
        logical=mapping[physical]
        require(Path(logical).name.startswith('op_summary' if field=='csv' else 'task_time'),'CSV role differs')
        require(result[field+'_hash']==raw.fingerprint(logical)['sha256'],'parsed CSV hash differs')
    for row in result['samples']:
        require(isinstance(row,dict) and (set(row)==SAMPLE|SAMPLE_AUX or set(row)==SAMPLE|SAMPLE_AUX|{'verified_dispatch'}),'unreviewed sample fields')
        if 'verified_dispatch' in row:
            dispatch=row['verified_dispatch']
            require(isinstance(dispatch,dict) and set(dispatch)==DISPATCH,'unreviewed dispatch fields')
            require(type(dispatch['tiling_key']) is int and 0<=dispatch['tiling_key']<2**64,'invalid dispatch key')
            require(type(dispatch['fallback']) is bool,'invalid dispatch fallback')
            require(type(dispatch['group_id']) is str and bool(dispatch['group_id']),'invalid dispatch group')
            require(type(dispatch['kernel_entry']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',dispatch['kernel_entry']),'invalid dispatch entry')
            sequence=dispatch['captured_kernel_sequence']
            require(type(sequence) is list and bool(sequence) and all(type(v) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',v) for v in sequence),'invalid dispatch sequence')
    for row in result['other_tasks']:require(set(row)=={'line','name','task_type'},'unreviewed other-task fields')
    json.dumps(result,allow_nan=False)  # Reject non-JSON/nonfinite extensions too.
    _no_paths({k:v for k,v in result.items() if k not in {'csv','auxiliary_csv'}})
    return {**result,'csv':str(mapping[result['csv']]),'auxiliary_csv':str(mapping[result['auxiliary_csv']])}


def parse_profile(raw,journal,build,cases,repeat,*,parser=None):
    """Use unchanged producer parser via bounded local CSV-only projection.

    The full tar has already been checked, including all non-CSV members.
    No temporary path may escape into returned original samples/artifacts.
    """
    if parser is None:
        import cannbench_msprof_timing
        parser=cannbench_msprof_timing.parse_profile
    chosen=[]
    for prefix in ('op_summary','task_time'):
        names=[n for n in raw.files if PurePosixPath(n).name.startswith(prefix) and n.endswith('.csv')]
        require(len(names)==1,'expected exactly one '+prefix+' CSV');chosen+=names
    with tempfile.TemporaryDirectory(prefix='aprof-raw-csv-read-',dir='/tmp') as temp:
        import msprof_raw_storage
        msprof_raw_storage.local_filesystem(temp)
        mapping={}
        for name in chosen:
            target=Path(temp)/name;target.parent.mkdir(parents=True,exist_ok=True)
            with raw.open_binary(raw.logical/name) as source,target.open('xb') as dest:
                for block in iter(lambda:source.read(CHUNK),b''):dest.write(block)
            require(fingerprint(target)==raw.fingerprint(raw.logical/name),'CSV projection changed')
            mapping[str(target)]=str(raw.logical/name)
        result=parser(Path(temp),journal,build,cases,repeat)
        for physical,logical in mapping.items():require(fingerprint(physical)==raw.fingerprint(logical),'parser mutated projected input')
        value=remap_parsed(result,mapping,raw)
        raw.reverify_cached()
        return value

# Authority implementation is a reviewed prerequisite, never chosen by a seal.
LEGACY_AUTHORITY_SHA='sha256:452c479151a6d0a9be43df4388a68f6577f0212c2fbd005c4501dbd8f43d7594'
AUTHORITY_SHA='sha256:78ff7dfc3d7494c074b9dd6a2d3d316d35efe50d288584cee5f391cd84fae1eb'
NATIVE_SHA='sha256:a08bb1813cb7503b58ba95d9f1a780c61a433c955dbc8dd2254b66ac5985787c'
CAPTURE_SHA='sha256:4d4f8d3f8d39d627bf6d5ead55d0a9e8d774a28be9f976384dc25584112e3b23'
MAX_METADATA=16*1024*1024


@contextlib.contextmanager
def directory_fd(path):
    """Walk every ancestor without symlinks, retain a descriptor for mutations."""
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and str(p)==str(path),'canonical absolute directory required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in p.parts[1:]:
            other=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=other
        yield fd
    finally:os.close(fd)


@contextlib.contextmanager
def file_stream(path):
    p=Path(path)
    with directory_fd(p.parent) as parent:
        fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            os.close(fd);raise ValueError('regular file required')
        with os.fdopen(fd,'rb') as stream:
            try:yield stream
            finally:
                after=os.fstat(stream.fileno());current=os.stat(p.name,dir_fd=parent,follow_symlinks=False)
                keys=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
                require(keys(before)==keys(after)==keys(current),'file changed during read')


def fingerprint(path):
    h=hashlib.sha256();size=0
    with file_stream(path) as stream:
        for block in iter(lambda:stream.read(CHUNK),b''):h.update(block);size+=len(block)
    return {'sha256':'sha256:'+h.hexdigest(),'size_bytes':size}


def small_read(path):
    with file_stream(path) as stream:
        result=stream.read(MAX_METADATA+1)
    require(len(result)<=MAX_METADATA,'metadata limit exceeded');return result


def checked_authority(require_capture=True):
    import importlib.util,sys
    for name,expected in [('level2_native_output_storage',NATIVE_SHA),('level2_verification_storage',AUTHORITY_SHA)]:
        spec=importlib.util.find_spec(name)
        require(spec is not None and spec.origin,'reviewed authority dependency missing')
        require(fingerprint(Path(spec.origin))['sha256']==expected,'reviewed authority producer differs')
        if name in sys.modules:require(Path(sys.modules[name].__file__).resolve()==Path(spec.origin).resolve(),'authority module identity differs')
    import level2_verification_storage as authority
    if require_capture:
        import msprof_raw_storage as transport
        require(fingerprint(Path(transport.__file__).resolve())['sha256']==CAPTURE_SHA,'reviewed capture producer differs')
    return authority


LOCAL={'mode':'local_tmp_full_copyback_v1','scratch_root':'/tmp',
       'inventory':'all_regular_files_sha256_and_directories','local_filesystem_required':True}


def cohort_facts(session, read_bytes=None, *, version=VERSION):
    """Pure original authority replay when a complete logical byte reader is given."""
    session=Path(session);cohort=session.parent;stage=cohort.parent.name
    require(version in VERSIONS and (stage=='search' or re.fullmatch(r'aa-[A-Za-z0-9_-]+',stage) or (version==VERSION and stage=='final')),'unsupported/unanchored final scope')
    offline=read_bytes is not None
    authority=checked_authority(require_capture=not offline)
    if not offline:session=authority.process_location(session)
    else:require(authority.location(session/'verification/1_normal_A/metadata.json',check_files=False)==session,'unsupported raw session')
    read=read_bytes or authority.read_bytes
    def ptr(path):return {'path':str(path),'sha256':'sha256:'+hashlib.sha256(read(Path(path))).hexdigest()}
    def load(path):
        data=read(Path(path));require(len(data)<=MAX_METADATA,'metadata limit exceeded');return json.loads(data)
    report=load(cohort/'report.json')
    require(report.get('evidence_status')=='verified_complete' and report.get('protocol')=='msprof_task_time_exploration_v2','unverified original report')
    sessions=report.get('sessions',[]);directories=[row['directory'] for row in sessions]
    require(len(directories)==len(set(directories))==6 and str(session) in directories,'six original sessions required')
    facts=[];transport_refs=[];oracle_refs=[]
    with (contextlib.nullcontext() if offline else authority.reader_session(cache_verified_bytes=authority.lookup_cache_enabled())):
        for row in sessions:
            current=Path(row['directory']);require(current.parent==cohort,'foreign report session')
            proof_version=authority.FINAL_VERSION if stage=='final' else authority.ANCHORED_VERSION
            value,expected=authority.facts_for_version(current,read,proof_version)
            for logical,digest in expected.items():
                if Path(logical).name in {'metadata.json','execution.json','stdout.log'}:
                    ref=ptr(logical);require(ref['sha256']==digest,'original oracle bytes differ');oracle_refs.append(ref)
            require(value['report_authority']['kind']==('ledger_timing_calibration_v1' if stage.startswith('aa-') else 'retrospective_final_report_authority_v1' if stage=='final' else 'ledger_closed_feedback_report_v1'),'report authority kind/scope differs')
            facts.append({'session':str(current),'facts':value});observed={}
            for name in ('request.json','raw-storage.json','raw-storage.request.json','raw-storage.copyback.json'):
                p=current/name;ref=ptr(p)
                require(row['artifacts'].get(str(p))==ref['sha256'],'unbound original raw transport evidence')
                observed[name]=load(p);transport_refs.append(ref)
            req=observed['request.json'];manifest=observed['raw-storage.json']
            require(req.get('capture_storage')==LOCAL and manifest.get('capture_storage')==LOCAL,'only LOCAL cohort eligible')
            require(manifest.get('status')=='complete' and manifest.get('native_teardown_complete') is True
                    and manifest.get('source_inventory')==manifest.get('archive_inventory'),'incomplete raw copyback')
            if not offline:require(not (current/'raw-storage.failed.json').exists(),'failed raw copyback')
            require(manifest.get('copyback')==ptr(current/'raw-storage.copyback.json')
                    and manifest.get('allocation')==ptr(current/'raw-storage.request.json'),'copyback refs differ')
    protected={}
    for ref in [*transport_refs,*oracle_refs,*(ref for row in facts for ref in row['facts']['protected'])]:
        require(ref['path'] not in protected or protected[ref['path']]==ref,'conflicting closed evidence identity')
        protected[ref['path']]=ref
    events={canonical(binding):binding for row in facts for binding in authority.event_bindings(row['facts'])}
    return {'original_report':ptr(cohort/'report.json'),'sessions':facts,'raw_transport':transport_refs,
            'protected':[protected[k] for k in sorted(protected)],'event_bindings':[events[k] for k in sorted(events)],
            'report_authority':facts[0]['facts']['report_authority'],
            'authority_producer_hashes':{'level2_verification_storage.py':LEGACY_AUTHORITY_SHA if version==LEGACY_VERSION else AUTHORITY_SHA,'level2_native_output_storage.py':NATIVE_SHA}}


def validate_archive(session, seal, archive, read_bytes):
    """Offline streaming raw archive validator; reads only caller-mapped evidence."""
    session=Path(session);logical=session/'raw';facts=cohort_facts(session,read_bytes,version=seal.get('version'))
    require(set(seal)=={'version','logical_root','archive','original_report','closed_evidence','producer','producer_snapshot','source_bytes_preserved'}
            and seal['version'] in VERSIONS and seal['source_bytes_preserved'] is True
            and seal['logical_root']==str(logical) and seal['closed_evidence']==facts
            and seal['original_report']==facts['original_report'],'portable raw closed authority differs')
    require(fingerprint(archive)['sha256']==seal['archive']['sha256'],'portable raw archive hash differs')
    report=json.loads(read_bytes(session.parent/'report.json'))
    row=next(v for v in report['sessions'] if v['directory']==str(session));refs=row['artifacts']
    manifest=json.loads(read_bytes(session/'raw-storage.json'));inv=manifest['archive_inventory']
    require(set(inv)=={'files','directories'} and inv==manifest['source_inventory'],'portable full raw inventory differs')
    files={};dirs=set()
    for name in inv['directories']:
        relative(name);require(name not in dirs,'duplicate raw directory');dirs.add(name)
    for item in inv['files']:
        require(set(item)=={'relative_path','bytes','sha256'} and type(item['bytes']) is int and item['bytes']>=0
                and HASH.fullmatch(item['sha256']),'invalid raw inventory member')
        name=relative(item['relative_path']);require(name not in files and name not in dirs,'duplicate raw member')
        require(refs.get(str(logical/name))==item['sha256'],'portable raw member not in original report');files[name]=item
    require(files,'empty raw inventory')
    for name in [*files,*dirs]:
        for parent in PurePosixPath(name).parents:
            if str(parent)!='.':require(str(parent) in dirs,'missing raw parent directory')
    require({p for p in refs if p.startswith(str(logical)+'/')}=={str(logical/n) for n in files},'portable original raw roster differs')
    offsets=validate_tar(Path(archive),files,dirs)
    return {str(logical/n):{'relative_path':n,'sha256':r['sha256'],'size_bytes':r['bytes'],'offset':offsets[n]} for n,r in files.items()}


def loose_inventory(root):
    """Only this one raw tree. Full file hashes and empty directory identities."""
    root=Path(root);files={};dirs=set()
    with directory_fd(root.parent) as parent:
        try:fd=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        except FileNotFoundError:return files,dirs
        def walk(current,prefix):
            before=os.fstat(current)
            for name in sorted(os.listdir(current)):
                rel=relative(prefix+name);st=os.stat(name,dir_fd=current,follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
                    try:dirs.add(rel);walk(child,rel+'/')
                    finally:os.close(child)
                else:
                    require(stat.S_ISREG(st.st_mode),'symlink or special raw member')
                    files[rel]=fingerprint(root/rel)
            after=os.fstat(current)
            require((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns),'raw directory changed during inventory')
        try:walk(fd,'')
        finally:os.close(fd)
    return files,dirs


def sync_directory(path):
    with directory_fd(path) as fd:os.fsync(fd)


def sync_file(path):
    with file_stream(path) as stream:os.fsync(stream.fileno())


def publish_bytes(path,data):
    """Durable no-clobber publication; an existing identical file is idempotent."""
    path=Path(path)
    with directory_fd(path.parent) as parent:
        if path.exists() or path.is_symlink():
            require(small_read(path)==data,'existing publication differs');return
        temp='.'+path.name+'.pending-'+os.urandom(12).hex()
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.link(temp,path.name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
            os.fsync(parent)
        finally:
            try:os.unlink(temp,dir_fd=parent);os.fsync(parent)
            except FileNotFoundError:pass


def canonical(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def completion(seal,version=VERSION):return {'version':version,'status':'complete','seal':seal,'source_bytes_preserved':True}
def default_destination(session):return Path(session)/'raw-archive-storage'


@contextlib.contextmanager
def maintenance_lock(destination):
    """Caller must also hold global maintenance lock; no NPU is launched here."""
    import fcntl
    with directory_fd(destination) as parent:
        fd=os.open('maintenance.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=parent)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode),'invalid lock file')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
        finally:os.close(fd)


def host_lock():
    import level2_storage
    return level2_storage.exclusive_host()


def write_tar(session,destination,manifest):
    """Plain USTAR; stream every original inventory file, retain empty dirs."""
    root=Path(session)/'raw';archive=destination/'raw.tar'
    files={row['relative_path']:row for row in manifest['archive_inventory']['files']}
    dirs=set(manifest['archive_inventory']['directories'])
    actual,actual_dirs=loose_inventory(root)
    require(actual=={n:{'sha256':r['sha256'],'size_bytes':r['bytes']} for n,r in files.items()} and actual_dirs==dirs,'original inventory differs before archive')
    # Retry after pre-seal interruption is safe only with all originals intact.
    if archive.exists() or archive.is_symlink():return
    with directory_fd(destination) as parent:
        temp='.raw.tar.pending-'+os.urandom(12).hex()
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        try:
            with os.fdopen(fd,'wb') as output:
                with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as tar:
                    for name in sorted(dirs):
                        relative(name);member=tarfile.TarInfo(name);member.type=tarfile.DIRTYPE;member.mode=0o700;tar.addfile(member)
                    for name,row in sorted(files.items()):
                        relative(name);member=tarfile.TarInfo(name);member.size=row['bytes'];member.mode=0o600
                        with file_stream(root/name) as source:tar.addfile(member,source)
                output.flush();os.fsync(output.fileno())
            os.link(temp,'raw.tar',src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False);os.fsync(parent)
        finally:
            try:os.unlink(temp,dir_fd=parent);os.fsync(parent)
            except FileNotFoundError:pass


def remove_file(path,expected):
    path=Path(path)
    with directory_fd(path.parent) as parent:
        try:before=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
        except FileNotFoundError:return
        require(stat.S_ISREG(before.st_mode),'retirement member is not regular')
        require(fingerprint(path)==expected,'retirement source bytes differ')
        after=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
        require((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns),'retirement member changed')
        os.unlink(path.name,dir_fd=parent);os.fsync(parent)


def remove_directory(path):
    path=Path(path)
    try:
        with directory_fd(path.parent) as parent:
            try:os.rmdir(path.name,dir_fd=parent);os.fsync(parent)
            except FileNotFoundError:pass
    except FileNotFoundError:pass


def prepare(session,destination=None,*,writers_closed=False,retire=False):
    """Create shadow/seal, or retire only into the fixed adjacent archive scope.

    Existing receipt and seal are immutable. A crash during unlink is replayed
    from the durable archive plus fresh original ledger authority, never guessed.
    """
    require(writers_closed is True,'explicit closed-writer attestation required')
    require(type(retire) is bool,'explicit retirement boolean required')
    session=Path(session);destination=Path(destination) if destination is not None else default_destination(session)
    require(not retire or destination==default_destination(session),'shadow archives cannot retire originals')
    require(destination==default_destination(session) or destination.is_relative_to('/tmp'),'shadow destination must be local /tmp')
    authority=checked_authority()
    with host_lock(), authority.reader_session(cache_verified_bytes=True):
        existing=destination/'seal.json'
        version=load_ref(pointer(existing))['version'] if existing.exists() or existing.is_symlink() else VERSION
        closed=cohort_facts(session,version=version)
        with directory_fd(destination.parent) as parent:
            try:os.mkdir(destination.name,0o700,dir_fd=parent);os.fsync(parent)
            except FileExistsError:pass
        with maintenance_lock(destination):
            seal_path=destination/'seal.json'
            if not seal_path.exists() and not seal_path.is_symlink():
                require(not (destination/'compacted.json').exists(),'receipt exists without seal')
                request=json.loads(small_read(session/'request.json'));manifest=json.loads(small_read(session/'raw-storage.json'))
                import msprof_raw_storage as transport
                transport.verify(request,session,json.loads(small_read(session/'msprof.execution.json')))
                write_tar(session,destination,manifest)
                inventory=manifest['archive_inventory']
                validate_tar(destination/'raw.tar',{r['relative_path']:r for r in inventory['files']},set(inventory['directories']))
                publish_bytes(destination/'producer.py',small_read(Path(__file__).resolve()))
                value={'version':version,'logical_root':str(session/'raw'),'archive':pointer(destination/'raw.tar'),
                       'original_report':closed['original_report'],'closed_evidence':closed,
                       'producer':pointer(Path(__file__).resolve()),'producer_snapshot':pointer(destination/'producer.py'),
                       'source_bytes_preserved':True}
                # Recheck the authority after streaming; no deletion has occurred.
                require(cohort_facts(session,version=version)==closed,'authority changed during archive')
                authority.reverify_cached()
                publish_bytes(seal_path,canonical(value))
            reader=RawArchive(session,pointer(seal_path))
            if retire:
                # Durable bytes, identity and BOTH directory entries precede unlink.
                for path in (reader.archive,seal_path,destination/'producer.py'):sync_file(path)
                sync_directory(destination);sync_directory(destination.parent)
                reader.reverify_cached()
                for name,row in sorted(reader.files.items()):
                    path=reader.logical/name
                    try:remove_file(path,{'sha256':row['sha256'],'size_bytes':row['bytes']})
                    except FileNotFoundError:pass  # prior durable partial retirement
                for name in sorted(reader.dirs,key=lambda n:(-len(Path(n).parts),n)):remove_directory(reader.logical/name)
                remove_directory(reader.logical)
                require(not reader.logical.exists() and not reader.logical.is_symlink(),'raw tree remains after retirement')
                reader.reverify_cached()
                publish_bytes(destination/'compacted.json',canonical(completion(pointer(seal_path),reader.version)))
            else:reader.reverify_cached()
            return {'version':reader.version,'status':'complete' if retire else 'sealed_shadow','seal':pointer(seal_path),
                    'files':len(reader.files),'directories':len(reader.dirs),'source_bytes_preserved':True}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--writers-closed',action='store_true')
    parser.add_argument('--retire',action='store_true')
    args=parser.parse_args()
    result=prepare(args.session,args.destination,writers_closed=args.writers_closed,retire=args.retire)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()

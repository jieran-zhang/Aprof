#!/usr/bin/env python3
"""Strict streaming storage for closed versioned Level2 native output bundles.

No profiler raw, journal, input, source, pilot or semantic guard file is retired.
Historical logical paths remain evidence identities. Archived producer copies are
inert provenance and are never executed. All large payload processing is streamed.
"""
from __future__ import annotations
from msprof_storage_protocol import cohort_process_count, validate_prepared_request
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
import struct
import tarfile

VERSION='level2_closed_native_outputs_v1'
REPORT_VERSION='level2_closed_native_outputs_v2'
VERSIONS={VERSION,REPORT_VERSION}
OPERATORS={'apply_adam_w','apply_rotary_pos_emb','arg_max','cross_entropy_loss','cummin','dynamic_quant','gather','gcd','grid_sampler_3d','group_norm','maximum','resize_bilinear','rms_norm','scatter','softmax','unsorted_segment_sum'}
CHUNK=1024*1024
MAX_METADATA=16*1024*1024
HASH=re.compile(r'sha256:[0-9a-f]{64}\Z')
TOKEN=re.compile(r'[A-Za-z0-9_-]+\Z')
STEM=re.compile(r'([1-9]|1[0-9]|20)_(normal|swapped)_([AB])\.bin(.*)\Z')
# Keep the reviewed ordered payload names explicit; no user-supplied suffixes.
OUTPUT_KEYS={'apply_rotary_pos_emb':('query_out','key_out'), 'cummin':('values','indices'), 'dynamic_quant':('output_y','output_scale')}
_CACHE=contextvars.ContextVar('native_output_archive_cache',default=None)
_OVERRIDES=contextvars.ContextVar('native_output_archive_overrides',default=None)

def require(value,message):
    if not value:raise ValueError(message)

def canonical(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def safe(path,exists=True,directory=False):
    path=Path(path);require(path.is_absolute() and '..' not in path.parts,'canonical absolute output path required')
    for item in [*reversed(path.parents),path]:
        require(not item.is_symlink(),'symlink output evidence prohibited')
        if item.exists() and item!=path:require(item.is_dir(),'non-directory output ancestor')
    if exists:require(path.is_dir() if directory else path.is_file(),'missing output evidence: '+str(path))
    return path

def fingerprint_stream(stream):
    h=hashlib.sha256();size=0
    while block:=stream.read(CHUNK):h.update(block);size+=len(block)
    return {'sha256':'sha256:'+h.hexdigest(),'size_bytes':size}

def raw_fingerprint(path):
    with safe(path).open('rb') as stream:return fingerprint_stream(stream)

def raw_ref(path):return {'path':str(path),'sha256':raw_fingerprint(path)['sha256']}
def small_read(path):
    with safe(path).open('rb') as stream:
        data=stream.read(MAX_METADATA+1);require(len(data)<=MAX_METADATA,'metadata size exceeds bound');return data

def cohort_location(cohort,check_files=True):
    cohort=Path(cohort);require(cohort.is_absolute() and '..' not in cohort.parts,'canonical cohort path required')
    parts=cohort.parts;matches=[i for i,p in enumerate(parts) if p=='tasks']
    require(len(matches)==1,'output must belong to one task');i=matches[0]
    require(i>=1 and parts[i-1] in ('train','validation','test'),'output split differs')
    require(parts[i+1] in OPERATORS,'unknown output operator')
    tail=parts[i+2:]
    if tail[:1]==('candidates',):require(len(tail)>2 and TOKEN.fullmatch(tail[1]),'invalid candidate output');tail=tail[2:]
    require(len(tail)==3 and tail[0]=='stages' and TOKEN.fullmatch(tail[1]) and tail[2] in ('cohort','direct_parent','original_baseline'),'unsupported output cohort')
    if check_files:safe(cohort,directory=True)
    return Path(*parts[:i+2]),parts[i+1]

def location(path,check_files=True):
    path=Path(path)
    if path.parent.name!='native' or not STEM.fullmatch(path.name):return None
    require(path.is_absolute() and '..' not in path.parts,'canonical native output path required')
    session=path.parent.parent;cohort=session.parent
    task,operator=cohort_location(cohort,check_files=check_files)
    require(TOKEN.fullmatch(session.name),'invalid output session')
    suffix=STEM.fullmatch(path.name)[4]
    allowed=('', '.outputs.json', *('.'+key for key in OUTPUT_KEYS[operator])) if operator in OUTPUT_KEYS else ('',)
    require(suffix in allowed,'unsupported native output suffix')
    if check_files:safe(path,exists=False)
    return cohort

def closed_from_reader(cohort,read_bytes,*,version=VERSION):
    """Pure closure reconstruction. Never opens original paths or runs code."""
    import level2_verification_storage as verification
    cohort=Path(cohort);task,operator=cohort_location(cohort,False)
    def read(path):
        data=read_bytes(path);require(len(data)<=MAX_METADATA,'closed proof exceeds metadata bound');return data
    def load(path):return json.loads(read(path))
    def ref(path):return {'path':str(path),'sha256':digest(read(path))}
    plan=load(cohort/'plan.json');group=load(cohort/'group-completion.json');report=load(cohort/'report.json')
    require(report.get('operator')==operator and report.get('evidence_status')=='verified_complete','not a verified operator report')
    schedule=plan['schedule'];sessions=group['completed_sessions']
    count=cohort_process_count(plan=plan,report=report)
    require(len(schedule)==len(sessions)==count and len(set(sessions))==count,'protocol process coverage differs')
    require(sessions==[str(cohort/row['name']) for row in schedule],'scheduled output session coverage differs')
    require([row['directory'] for row in report['sessions']]==sessions,'reported output session coverage differs')
    require(version in VERSIONS,'unsupported native output storage version')
    protected={};event_binding=None;expected={};bundles=[];case_ids=None;stage_recovery=None;report_authority=None
    for number,(directory,entry,observed) in enumerate(zip(sessions,schedule,report['sessions'])):
        session=Path(directory)
        if version==VERSION:facts,oracle_roster=verification.closed_from_reader(session,read)
        else:
            proof_version=(verification.FINAL_VERSION if cohort.parent.name=='final' else verification.ANCHORED_VERSION)
            facts,oracle_roster=verification.facts_for_version(session,read,proof_version)
            authority=facts['report_authority']
            require(authority['kind'] in {'retrospective_final_report_authority_v1','ledger_timing_calibration_v1','ledger_closed_feedback_report_v1'},'unsupported native output report authority')
            require(report_authority in (None,authority),'native sessions have different report authority')
            report_authority=authority
        if number==0:stage_recovery=facts.get('stage_recovery')
        else:require(stage_recovery==facts.get('stage_recovery'),'recovery identity differs across native sessions')
        for p in facts['protected']:protected[p['path']]=p
        require(event_binding in (None,facts['event_binding']),'stage event identity differs');event_binding=facts['event_binding']
        request=load(session/'request.json');require(request==entry['request'],'session request differs')
        protected[str(session/'request.json')]=ref(session/'request.json')
        validate_prepared_request(request,lite=count==2)
        ids=[str(row['case_id']) for row in request['cases']]
        require(ids and len(set(ids))==len(ids) and all(re.fullmatch(r'[1-9]|1[0-9]|20',v) for v in ids),'invalid output case roster')
        require(case_ids in (None,ids),'cohort case roster differs');case_ids=ids
        configs=request.get('buffer_configs','normal,swapped').split(',');require(len(configs)==2 and set(configs)=={'normal','swapped'},'normal/swapped required')
        roster=[(case,config,role) for case in ids for config in configs for role in 'AB']
        validation=load(session/'validation.json')['outputs']
        journal=[json.loads(line) for line in read(session/'native/journal.jsonl').splitlines()]
        require(journal[-1].get('stream_destroyed') is True and journal[-1].get('context_destroyed') is True,'native teardown incomplete')
        native=[row for row in journal if row.get('type')=='output']
        key=lambda row:(str(row['case_id']),row['buffer_config'],row['role'])
        require([key(row) for row in validation]==[key(row) for row in native]==roster,'complete output coverage differs')
        require(set(oracle_roster)=={str(session/'verification'/f'{c}_{k}_{r}'/name) for c,k,r in roster for name in verification.verification_names(session)},'oracle coverage differs from requested output cases')
        for checked,actual in zip(validation,native):
            c,k,r=key(checked);path=session/'native'/f'{c}_{k}_{r}.bin';h=checked.get('output_hash')
            require(checked.get('passed') is True and HASH.fullmatch(h or '') and actual.get('path')==str(path)
                    and actual.get('validation_scope')=='final_call_of_final_formal_sample','native output identity/verdict differs')
            require(observed['artifacts'].get(str(path))==h,'output hash differs from protected report')
            expected[str(path)]={'sha256':h,'size_bytes':None}
            if operator in OUTPUT_KEYS:
                index=path.with_name(path.name+'.outputs.json');data=read(index);index_hash=digest(data)
                require(observed['artifacts'].get(str(index))==index_hash,'bundle index differs from protected report')
                doc=json.loads(data);rows=doc.get('outputs',[])
                require(doc.get('version')=='level2_output_bundle_v1' and doc.get('operator')==operator
                        and [row.get('name') for row in rows]==list(OUTPUT_KEYS[operator]),'named output bundle identity differs')
                expected[str(index)]={'sha256':index_hash,'size_bytes':len(data)}
                for name,row in zip(OUTPUT_KEYS[operator],rows):
                    part=path.with_name(path.name+'.'+name);h=row.get('sha256');size=row.get('bytes')
                    require(row.get('path')==str(part) and HASH.fullmatch(h or '') and type(size) is int and size>=0,'named output path/size differs')
                    require(observed['artifacts'].get(str(part))==h,'named output hash differs from protected report')
                    expected[str(part)]={'sha256':h,'size_bytes':size}
                bundles.append({'path':str(path),'rows':rows})
    require(sorted(map(int,plan['case_ids']))==sorted(map(int,case_ids)),'cohort plan case coverage differs')
    if version==REPORT_VERSION:
        require(report_authority is not None,'missing closed report authority')
        facts={'protected':[protected[k] for k in sorted(protected)],'event_binding':event_binding,
               'report_authority':report_authority,'authority':'closed_report_outputs_v2'}
        if stage_recovery is not None:facts['stage_recovery']=stage_recovery
        return facts,expected,bundles
    # A terminal stage says execution ended, but does not itself authenticate
    # output/report bytes. Require the earliest already event-bound successful
    # output-dedup inventory for this scope. Do not manufacture that authority.
    run=task.parents[2];event_path=task/'events.jsonl';previous=None;authority=None
    for number,line in enumerate(read(event_path).splitlines()):
        item=json.loads(line);body={k:v for k,v in item.items() if k!='hash'}
        h=digest((json.dumps(body,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())
        require(item.get('sequence')==number and item.get('previous_hash')==previous and item.get('hash')==h,'dedup authority event chain differs')
        previous=h
        if item.get('kind')!='closed_outputs_deduplicated':continue
        pointer=item.get('value',{}).get('manifest',{});path=Path(pointer.get('path',''))
        require(path.is_absolute() and '..' not in path.parts and path.parent==run/'storage/dedup'
                and re.fullmatch(r'[0-9a-f]{32}\.json',path.name) and HASH.fullmatch(pointer.get('sha256','')),'invalid dedup authority path')
        data=read(path);require(digest(data)==pointer['sha256'],'dedup authority manifest hash differs')
        manifest=json.loads(data)
        if manifest.get('scope') not in (str(cohort),str(cohort.parent)):continue
        require(manifest.get('version')=='level2_output_dedup_v1' and manifest.get('run')==str(run)
                and manifest.get('operator')==operator and manifest.get('kind') in ('stage','cohort')
                and manifest.get('status')=='passed' and manifest.get('error') is None
                and manifest.get('writers_closed_attested') is True and manifest.get('evidence_bytes_deleted')==0
                and manifest.get('original_records_modified') is False,'dedup authority is not closed passed')
        rows=manifest.get('files',[]);indices=manifest.get('index_evidence',[])
        by_path={r['path']:r for r in rows};index={r['path']:r for r in indices}
        require(len(by_path)==len(rows) and len(index)==len(indices),'duplicate dedup authority entry')
        wanted_files={k for k in expected if not k.endswith('.outputs.json')}
        scoped_files={k for k in by_path if Path(k).is_relative_to(cohort)}
        require(scoped_files==wanted_files,'dedup authority output roster differs')
        for output,row in expected.items():
            declared=index.get(output) if output.endswith('.outputs.json') else by_path.get(output)
            require(declared is not None and declared.get('sha256')==row['sha256'],'original dedup output hash differs')
            if not output.endswith('.outputs.json'):
                require(type(declared.get('bytes')) is int and declared['bytes']>=0
                        and (row['size_bytes'] is None or row['size_bytes']==declared['bytes']),'original dedup output length differs')
                row['size_bytes']=declared['bytes']
        mandatory={str(cohort/'plan.json'),str(cohort/'group-completion.json'),str(cohort.parent/'result.json'),str(cohort.parent/'stage-plan.json')}
        if stage_recovery is not None:
            mandatory.update(stage_recovery[key]['path'] for key in
                             ('current_result','original_failed_result','qualification'))
        mandatory.update(str(Path(directory)/name) for directory in sessions for name in
                         ('request.json','completion.json','validation.json','msprof.execution.json','native/journal.jsonl'))
        require(mandatory<=set(index),'dedup authority lacks original closed-state hashes')
        for origin,pointer_ in index.items():
            original=Path(origin)
            if not original.is_relative_to(cohort) and origin not in mandatory:continue
            require(original.is_absolute() and '..' not in original.parts and HASH.fullmatch(pointer_.get('sha256','')),'invalid dedup index identity')
            require(digest(read(original))==pointer_['sha256'],'original dedup index evidence changed')
            if origin not in expected:protected[origin]=pointer_
        protected[str(path)]=pointer
        authority={'path':str(event_path),'sequence':number,'hash':h};break
    require(authority is not None,'no previously event-bound passed output-dedup authority; archive is blocked')
    facts={'protected':[protected[k] for k in sorted(protected)],'event_binding':authority,
            'stage_event_binding':event_binding,'authority':'closed_outputs_deduplicated_v1'}
    if stage_recovery is not None:facts['stage_recovery']=stage_recovery
    return facts,expected,bundles

class SliceReader(io.RawIOBase):
    def __init__(self,path,offset,size):
        self.stream=safe(path).open('rb');self.offset=offset;self.length=size;self.position=0
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=os.SEEK_SET):
        target=offset if whence==os.SEEK_SET else self.position+offset if whence==os.SEEK_CUR else self.length+offset if whence==os.SEEK_END else -1
        require(0<=target<=self.length,'member seek outside bounds');self.position=target;return target
    def read(self,size=-1):
        # Even an accidental read() is capped; callers requesting whole objects
        # must explicitly stream. Small JSON readers use bounded read_bytes().
        require(size is not None and size>=0,'archive reads require an explicit bounded size')
        size=min(size,self.length-self.position)
        self.stream.seek(self.offset+self.position);data=self.stream.read(size)
        require(len(data)==size,'truncated archive member');self.position+=len(data);return data
    def close(self):
        if not self.closed:self.stream.close()
        super().close()

def check_bundles(bundles,opener):
    for bundle in bundles:
        with opener(Path(bundle['path'])) as stream:
            for row in bundle['rows']:
                header=stream.read(8);require(len(header)==8 and struct.unpack('<Q',header)[0]==row['bytes'],'bundle header differs')
                with opener(Path(row['path'])) as part:
                    remaining=row['bytes']
                    while remaining:
                        block=stream.read(min(CHUNK,remaining));require(block and part.read(len(block))==block,'bundle part bytes differ');remaining-=len(block)
                    require(not part.read(1),'extra named output bytes')
            require(not stream.read(1),'extra bundle bytes')

def archive_dir(cohort):return Path((_OVERRIDES.get() or {}).get(str(cohort),str(cohort/'native-output-storage')))
def signatures(paths):
    return tuple((str(p),*(getattr(safe(p).stat(),k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))) for p in paths)

def archive_members(archive,seal):
    """Validate regular content-addressed objects in bounded memory; return offsets."""
    rows=seal['members'];objects={}
    for row in rows:
        h=row.get('sha256');require(HASH.fullmatch(h or '') and row.get('member')=='objects/'+h[7:],'invalid content-addressed member')
        size=row.get('size_bytes');require(type(size) is int and size>=0,'invalid output length')
        require(h not in objects or objects[h]['size_bytes']==size,'same hash has conflicting lengths');objects[h]=row
    offsets={}
    with tarfile.open(archive,'r:') as tar:
        for member in tar:
            require(member.name not in offsets and member.name.startswith('objects/') and member.name[8:] in {h[7:] for h in objects},'unexpected/duplicate output archive member')
            row=objects['sha256:'+member.name[8:]]
            require(member.isfile() and not member.issym() and not member.islnk() and member.size==row['size_bytes']
                    and member.mode==0o600 and member.uid==member.gid==member.mtime==0,'output tar member metadata differs')
            stream=tar.extractfile(member);fp=fingerprint_stream(stream)
            require(fp=={'sha256':row['sha256'],'size_bytes':row['size_bytes']},'output tar content differs')
            offsets[member.name]=(member.offset_data,member.size)
    require(set(offsets)=={'objects/'+h[7:] for h in objects},'output tar object roster differs')
    return offsets

def validate_archive(cohort,seal,archive,read_proof):
    """Shared offline validator; read_proof is a complete trusted byte mapping."""
    require(seal.get('version') in VERSIONS and seal.get('cohort')==str(cohort) and seal.get('source_bytes_preserved') is True,'native output seal identity differs')
    require(raw_fingerprint(archive)['sha256']==seal['archive']['sha256'],'native output archive hash differs')
    offsets=archive_members(archive,seal);rows=seal['members'];mapping={r['path']:r for r in rows}
    require(len(mapping)==len(rows),'duplicate native output logical path')
    for path in mapping:require(location(path,False)==Path(cohort),'native output member scope differs')
    def member_open(path):
        row=mapping[str(path)];return SliceReader(archive,*offsets[row['member']])
    def read(path):
        if str(path) not in mapping:return read_proof(path)
        with member_open(path) as stream:
            data=stream.read(MAX_METADATA+1);require(len(data)<=MAX_METADATA,'metadata too large');return data
    facts,expected,bundles=closed_from_reader(cohort,read,version=seal['version'])
    require(facts==seal['closed_evidence'],'closed native output proof changed')
    require(set(mapping)==set(expected),'native output logical roster differs')
    for path,row in mapping.items():
        require(row['sha256']==expected[path]['sha256'] and (expected[path]['size_bytes'] is None or row['size_bytes']==expected[path]['size_bytes']),'native output differs from original evidence')
    check_bundles(bundles,member_open)
    return mapping,offsets

def verified(cohort,destination=None):
    cohort=Path(cohort);cohort_location(cohort);destination=safe(destination or archive_dir(cohort),directory=True)
    archive=destination/'outputs.tar';seal_path=destination/'seal.json';producer=destination/'producer.py'
    signature=signatures([archive,seal_path,producer]);key=(str(cohort),str(destination));cache=_CACHE.get()
    if cache is not None and key in cache and cache[key][0]==signature:return cache[key][1]
    seal=json.loads(small_read(seal_path));require(seal.get('archive')==raw_ref(archive) and seal.get('producer')==raw_ref(producer),'native storage proof snapshot differs')
    import level2_verification_storage as verification
    mapping,offsets=validate_archive(cohort,seal,archive,verification.read_bytes)
    for path,row in mapping.items():
        p=safe(path,exists=False)
        if p.exists():require(raw_fingerprint(p)=={k:row[k] for k in ('sha256','size_bytes')},'remaining native output differs from archive')
    # Reject unknown binary-like artifacts, without touching journal/control files.
    for session in json.loads(verification.read_bytes(cohort/'group-completion.json'))['completed_sessions']:
        for path in (Path(session)/'native').iterdir():
            if '.bin' in path.name:require(str(path) in mapping,'unindexed native output file')
    receipt=destination/'compacted.json'
    if receipt.exists() or receipt.is_symlink():
        require(json.loads(small_read(receipt))=={'version':seal['version'],'status':'complete','seal':raw_ref(seal_path),'source_bytes_preserved':True}
                and not any(Path(path).exists() for path in mapping),'retired output reappeared or completion differs')
    value={'seal':seal,'seal_ref':raw_ref(seal_path),'members':mapping,'offsets':offsets,'archive_path':archive,'destination':destination}
    if cache is not None:cache[key]=(signature,value)
    return value

def reverify_cached():
    cache=_CACHE.get()
    if cache is None:return
    keys=list(cache);token=_CACHE.set(None)
    try:
        for cohort,destination in keys:verified(Path(cohort),Path(destination))
    finally:_CACHE.reset(token)

@contextlib.contextmanager
def reader_session(overrides=None):
    token=_CACHE.set({}) if _CACHE.get() is None else None;mapping=None
    if overrides is not None:
        require(_OVERRIDES.get() is None,'nested native shadow overrides prohibited')
        mapping=_OVERRIDES.set({str(k):str(v) for k,v in overrides.items()})
    try:
        yield
        if token is not None:reverify_cached()
    finally:
        if mapping is not None:_OVERRIDES.reset(mapping)
        if token is not None:_CACHE.reset(token)

def resolve(path):
    path=Path(path)
    # Ordinary files predate this Level2 transport (including Level1 outputs
    # with the same basename). Enter its strict namespace only when a canonical
    # storage marker or explicit shadow mapping actually declares the archive.
    if path.parent.name!='native' or not STEM.fullmatch(path.name):return None
    cohort=path.parent.parent.parent;destination=archive_dir(cohort)
    declared=str(cohort) in (_OVERRIDES.get() or {})
    if not declared and not destination.exists() and not destination.is_symlink():return None
    require(location(path)==cohort,'declared native archive path differs')
    value=verified(cohort,destination);require(str(path) in value['members'],'native output not in sealed roster');return value

@contextlib.contextmanager
def open_binary(path):
    value=resolve(path)
    if value is None:
        with Path(path).open('rb') as stream:yield stream
    else:
        member=value['members'][str(path)]
        with SliceReader(value['archive_path'],*value['offsets'][member['member']]) as stream:yield stream

def fingerprint(path):
    with open_binary(path) as stream:return fingerprint_stream(stream)

def read_bytes(path):
    value=resolve(path)
    if value is None:return Path(path).read_bytes()
    row=value['members'][str(path)]
    with SliceReader(value['archive_path'],*value['offsets'][row['member']]) as stream:
        data=stream.read(MAX_METADATA+1);require(len(data)<=MAX_METADATA,'large output requires streaming reader');return data

def evidence_binding(path,expected=None):
    value=resolve(path)
    if value is None:return None
    row=value['members'][str(path)];require(expected is None or expected==row['sha256'],'native logical hash differs')
    return {'version':value['seal']['version'],'origin':{'path':str(path),'sha256':row['sha256']},'seal':value['seal_ref'],
            'archive':value['seal']['archive'],'producer':value['seal']['producer'],'closed_evidence':value['seal']['closed_evidence']}

def logical_files(directory):
    values=set();directory=Path(directory)
    for marker in directory.rglob('native-output-storage/seal.json'):values.update(verified(marker.parent.parent)['members'])
    for cohort,destination in (_OVERRIDES.get() or {}).items():
        if Path(cohort).is_relative_to(directory):values.update(verified(Path(cohort),Path(destination))['members'])
    return sorted(values)

def prepare(cohort,destination=None,*,writers_closed=False,retire=False,report_authority=False):
    require(writers_closed is True,'closed writers attestation required')
    cohort=Path(cohort);task,operator=cohort_location(cohort)
    destination=Path(destination) if destination else cohort/'native-output-storage'
    require((retire and destination==cohort/'native-output-storage') or (not retire and destination.is_relative_to(Path('/tmp'))),'unsupported archive destination')
    from level2_storage import exclusive_host,storage_lock,write_new,sync_directory
    import level2_verification_storage as verification
    with exclusive_host(),verification.reader_session():
        seal_path=destination/'seal.json'
        selected_version=json.loads(small_read(seal_path))['version'] if seal_path.exists() else REPORT_VERSION if report_authority else VERSION
        require(selected_version in VERSIONS,'unsupported native seal version')
        require(not seal_path.exists() or not report_authority or selected_version==REPORT_VERSION,
                'report authority request differs from existing native seal')
        facts,expected,bundles=closed_from_reader(cohort,verification.read_bytes,version=selected_version)
        if not destination.exists():safe(destination.parent,directory=True);destination.mkdir()
        safe(destination,directory=True)
        with storage_lock(destination):
            if (destination/'seal.json').exists():
                value=verified(cohort,destination)
            else:
                rows=[];objects={}
                for path,item in sorted(expected.items()):
                    p=safe(path);fp=raw_fingerprint(p);require(fp['sha256']==item['sha256'] and (item['size_bytes'] is None or fp['size_bytes']==item['size_bytes']),'unsealed output differs from protected evidence')
                    rows.append({'path':path,**fp,'member':'objects/'+fp['sha256'][7:]});objects.setdefault(fp['sha256'],p)
                check_bundles(bundles,lambda p:safe(p).open('rb'))
                # An interrupted unsealed tar is never authoritative. Preserve it
                # and fail closed; use a distinct reviewed destination to retry.
                archive=destination/'outputs.tar';pending=destination/'outputs.tar.pending'
                require(not archive.exists() and not pending.exists(),'unsealed native archive already exists; explicit review required')
                with pending.open('xb') as stream:
                    with tarfile.open(fileobj=stream,mode='w',format=tarfile.PAX_FORMAT) as tar:
                        for h,path in sorted(objects.items()):
                            size=raw_fingerprint(path)['size_bytes'];member=tarfile.TarInfo('objects/'+h[7:]);member.size=size;member.mode=0o600;member.uid=member.gid=member.mtime=0
                            with safe(path).open('rb') as source:tar.addfile(member,source)
                    stream.flush();os.fsync(stream.fileno())
                os.link(pending,archive);sync_directory(destination);pending.unlink();sync_directory(destination)
                producer=destination/'producer.py'
                data=Path(__file__).read_bytes()
                with producer.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
                seal={'version':selected_version,'cohort':str(cohort),'source_bytes_preserved':True,'archive':raw_ref(archive),'producer':raw_ref(producer),'closed_evidence':facts,'members':rows}
                validate_archive(cohort,seal,archive,verification.read_bytes)
                write_new(destination/'seal.json',seal);value=verified(cohort,destination)
            if retire:
                for name in ('outputs.tar','seal.json','producer.py'):
                    fd=os.open(safe(destination/name),os.O_RDONLY|os.O_NOFOLLOW)
                    try:os.fsync(fd)
                    finally:os.close(fd)
                sync_directory(destination);sync_directory(destination.parent)
                # Reject unfinished dedup operations: their backup/recovery state
                # belongs to the inode-replacement protocol, not this transport.
                for path in value['members']:
                    p=Path(path);require(not list(p.parent.glob(p.name+'.aprof-*')),'unfinished output dedup replacement')
                value=verified(cohort,destination)
                for path,row in value['members'].items():
                    p=Path(path)
                    if p.exists():require(raw_fingerprint(p)=={k:row[k] for k in ('sha256','size_bytes')},'output changed before retirement');p.unlink()
                for directory in {Path(p).parent for p in value['members']}:sync_directory(directory)
                receipt={'version':value['seal']['version'],'status':'complete','seal':raw_ref(destination/'seal.json'),'source_bytes_preserved':True}
                if (destination/'compacted.json').exists():require(json.loads(small_read(destination/'compacted.json'))==receipt,'native completion receipt differs')
                else:write_new(destination/'compacted.json',receipt)
                verified(cohort,destination)
            return {'version':value['seal']['version'],'status':'complete' if retire else 'sealed_shadow','cohort':str(cohort),'seal':raw_ref(destination/'seal.json'),'logical_files':len(value['members']),'original_bytes_preserved':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',required=True);p.add_argument('--shadow-destination');p.add_argument('--writers-closed',action='store_true');p.add_argument('--retire',action='store_true');p.add_argument('--report-authority',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(Path(a.cohort),Path(a.shadow_destination) if a.shadow_destination else None,writers_closed=a.writers_closed,retire=a.retire,report_authority=a.report_authority),indent=2))
if __name__=='__main__':main()

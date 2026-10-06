#!/usr/bin/env python3
"""Deduplicate closed Level2 outputs without changing paths, bytes or evidence.

No collector calls this module. The coordinator must close the selected scope's
writers, then call outside exclusive_host(): this operation takes that same host
lock to keep hashing and filesystem work outside a measurement interval. Call
synchronously from the serial coordinator before it schedules any next collector;
a background worker could take the nonblocking lock between another group's
sessions. No concurrent launch loop is allowed until this call returns. Hardlinks
share future writes, so outputs and the CAS must remain immutable after closure.
Only indexed pilot/cohort outputs are eligible; inputs, source and arbitrary .bin
files are never discovered. This is storage maintenance, not a measurement stage.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tarfile
import time
import uuid
sys.dont_write_bytecode = True
from level2_adapters import OPERATORS, OUTPUT_KEYS
from run_level1_serial import exclusive_host

VERSION = 'level2_output_dedup_v1'
CHUNK = 8 * 1024 * 1024
DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')
TOKEN = re.compile(r'[A-Za-z0-9_-]+\Z')
COMPACTION = 'level2_closed_storage_journals_v1'
JOURNAL = re.compile(r'[0-9]{6}\.(intent|result)\.json\Z')


def require(condition, message):
    if not condition: raise ValueError(message)


def safe(path, root=None, *, directory=False):
    """Check lexical containment and every component, without following symlinks."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute unaliased path required')
    if root is not None: require(path.is_relative_to(root), 'path escapes storage scope')
    for component in [*reversed(path.parents), path]:
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'symlink prohibited: ' + str(component))
        if component != path: require(stat.S_ISDIR(info.st_mode), 'non-directory path component')
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'unexpected file type: ' + str(path))
    return path


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def metadata(info):
    return {'device':info.st_dev, 'inode':info.st_ino, 'bytes':info.st_size,
            'allocated_bytes':info.st_blocks * 512, 'links':info.st_nlink,
            'mode':stat.S_IMODE(info.st_mode), 'uid':info.st_uid, 'gid':info.st_gid,
            'mtime_ns':info.st_mtime_ns, 'ctime_ns':info.st_ctime_ns}


def digest(path, expected=None):
    path = safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd); h = hashlib.sha256()
        require(stat.S_ISREG(before.st_mode), 'not a regular output')
        while block := os.read(fd, CHUNK): h.update(block)
        after = os.fstat(fd)
        require(signature(before) == signature(after) == signature(path.lstat()), 'file changed while hashing: ' + str(path))
        value = 'sha256:' + h.hexdigest()
        require(expected is None or value == expected, 'hash differs: ' + str(path))
        return value, metadata(after)
    finally: os.close(fd)


def mkdir(path):
    if not path.exists():
        safe(path.parent, directory=True)
        path.mkdir()
    safe(path, directory=True)


def sync_directory(path):
    directory = os.open(path,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(directory)
    finally: os.close(directory)


def write_new(path, value):
    """Publish a complete fsynced JSON file without overwriting existing evidence."""
    safe(path.parent, directory=True)
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    temporary = path.with_name('.record-'+uuid.uuid4().hex+'.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary,path,follow_symlinks=False)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class Inventory:
    def __init__(self, run, scope, kind):
        self.run = safe(Path(os.path.abspath(run)), directory=True)
        self.scope = safe(Path(os.path.abspath(scope)), self.run, directory=True)
        self.kind, self.files, self.evidence = kind, {}, {}
        parts = self.scope.relative_to(self.run).parts
        require(len(parts) >= 5 and parts[0] in ('train','validation','test') and parts[1] == 'tasks', 'scope must belong to a Level2 task')
        self.task = self.run.joinpath(*parts[:3])
        manifest = self.read(self.task/'manifest.json')
        self.operator = manifest.get('operator')
        require(manifest.get('version') == 'msprof_task_time_exploration_v2' and self.operator in OPERATORS and parts[2] == self.operator, 'fresh Level2 task manifest required')
        tail = parts[3:]
        if kind == 'pilot':
            require(tail == ('preflight','pilot'), 'pilot must use fixed preflight/pilot directory')
            self.pilot(self.scope)
        else:
            stage_tail = tail[2:] if len(tail) >= 2 and tail[0] == 'candidates' and TOKEN.fullmatch(tail[1]) else tail
            require(len(stage_tail) == (2 if kind == 'stage' else 3) and stage_tail[0] == 'stages' and TOKEN.fullmatch(stage_tail[1]), 'scope must use a fixed stage directory')
            stage = self.scope if kind == 'stage' else self.scope.parent
            result = self.read(stage/'result.json')
            require(result.get('status') in ('passed','failed') and isinstance(result.get('ended_at'), (int,float)), 'stage still open or lacks terminal result')
            require(result.get('kind') in ('control','timing'), 'only timing/control stage outputs are indexed')
            plan = self.read(stage/'stage-plan.json')
            if result['kind'] == 'control':
                scopes = {'cohort':plan['cohort']}
            else:
                scopes = {}
                for row in plan['cohorts']:
                    relation = row['relation']
                    require(relation in ('direct_parent','original_baseline') and relation not in scopes, 'unexpected/duplicate cohort relation')
                    scopes[relation] = self.read_pointer(row['plan'])
            require(bool(scopes), 'stage has no indexed cohorts')
            if kind == 'stage':
                require(result['status'] == 'passed', 'whole stage dedup requires passed stage; select an individually closed cohort after a failed stage')
                for name, cohort_plan in scopes.items(): self.cohort(stage/name, cohort_plan)
            else:
                require(self.scope.name in scopes, 'cohort not indexed by terminal stage')
                self.cohort(self.scope, scopes[self.scope.name])
        require(bool(self.files), 'no verified output files')
        self.recheck_evidence()

    def read(self, path, expected=None):
        path = safe(Path(path), self.run)
        value, _ = digest(path, expected)
        with path.open('rb') as stream: raw = stream.read()
        require('sha256:'+hashlib.sha256(raw).hexdigest() == value, 'index changed while reading')
        self.evidence[str(path)] = value
        return json.loads(raw)

    def read_pointer(self, ref, expected_path=None):
        require(isinstance(ref,dict) and DIGEST.fullmatch(ref.get('sha256','')), 'invalid evidence pointer')
        path = Path(ref['path'])
        require(expected_path is None or path == expected_path, 'evidence pointer path differs')
        return self.read(path, ref['sha256'])

    def recheck_evidence(self):
        for path, value in self.evidence.items(): digest(path, value)

    def add(self, path, expected):
        require(isinstance(expected,str) and DIGEST.fullmatch(expected), 'invalid indexed output hash')
        path = safe(path, self.scope)
        value, info = digest(path, expected)
        row = {'path':str(path), 'sha256':value, 'bytes':info['bytes']}
        require(str(path) not in self.files, 'duplicate indexed output')
        self.files[str(path)] = row

    def bundle(self, path, expected):
        self.add(path, expected)
        keys = OUTPUT_KEYS.get(self.operator)
        if not keys: return
        index = self.read(path.with_name(path.name+'.outputs.json'))
        require(index.get('version') == 'level2_output_bundle_v1' and index.get('operator') == self.operator, 'bundle index identity differs')
        rows = index.get('outputs',[])
        require([r.get('name') for r in rows] == list(keys), 'bundle output names differ')
        with path.open('rb') as stream:
            for key,row in zip(keys,rows):
                part = path.with_name(path.name+'.'+key)
                require(row.get('path') == str(part), 'bundle part escapes fixed output filename')
                header = stream.read(8)
                require(len(header) == 8, 'truncated output bundle')
                size = struct.unpack('<Q',header)[0]
                require(type(row.get('bytes')) is int and row['bytes'] == size, 'bundle length differs')
                self.add(part, row['sha256'])
                with part.open('rb') as separate:
                    remaining = size
                    while remaining:
                        block = stream.read(min(remaining,CHUNK))
                        require(block and separate.read(len(block)) == block, 'bundle part bytes differ')
                        remaining -= len(block)
                    require(not separate.read(1), 'bundle part has extra bytes')
            require(not stream.read(1), 'bundle has extra bytes')

    def pilot(self, path):
        request = self.read(path/'request.json'); completed = self.read(path/'pilot.json')
        require(request.get('version') == completed.get('version') == 'level2_prepared_pilot_v1', 'unknown pilot version')
        require(completed.get('operator') == self.operator and completed.get('status') == 'passed' and completed.get('error') is None, 'pilot is not successfully closed')
        ids = request['case_ids']; rows = completed['cases']
        require(ids and len(ids) == len(set(ids)) and all(type(i) is int and 1 <= i <= 20 for i in ids), 'invalid pilot case IDs')
        require([r['case_id'] for r in rows] == ids, 'pilot case coverage differs')
        for row in rows:
            case = path/f"case_{row['case_id']:02d}"
            require(self.read(case/'pilot-case.json') == row, 'pilot case index differs')
            native = self.read_pointer(row['native'], case/'native.json')
            expected = dict(version='level2_prepared_pilot_native_v1',mode='pilot',exit_code=0,
                            warmup_complete_calls=1,profile_complete_calls=1,stream_destroyed=True,context_destroyed=True,finalized=True)
            require(all(native.get(k) == v for k,v in expected.items()), 'pilot native is not closed')
            self.exited(case/'native.execution.json'); self.exited(case/'verify.execution.json')
            require(row['correctness'].get('passed') is True, 'pilot output not verified')
            self.bundle(case/'output.bin', row['correctness']['output_hash'])

    def exited(self, path):
        row = self.read(path)
        require(row.get('exit_code') == 0 and row.get('error') is None and isinstance(row.get('ended_at'),(float,int)), 'process still open or failed')

    def cohort(self, path, plan):
        safe(path, self.scope, directory=True)
        require(self.read(path/'plan.json') == plan, 'cohort plan differs from stage')
        completed = self.read(path/'group-completion.json')
        require(completed.get('status') == 'passed' and completed.get('error') is None and completed.get('ended_at') is not None, 'cohort is not successfully closed')
        schedule = plan['schedule']; sessions = completed['sessions']
        require(len(schedule) == len(sessions) == 6, 'cohort must have six completed sessions')
        names = [row['name'] for row in schedule]
        require(len(set(names)) == 6 and all(TOKEN.fullmatch(name) for name in names), 'invalid session directory')
        paths = [path/name for name in names]
        require(completed['completed_sessions'] == [str(p) for p in paths] == [row['directory'] for row in sessions], 'cohort session coverage differs')
        for directory, item, scheduled in zip(paths,sessions,schedule):
            completion = self.read_pointer(item['completion'], directory/'completion.json')
            self.read_pointer(item['samples'], directory/'samples.json')
            journal_path = directory/'native/journal.jsonl'
            require(Path(item['journal']['path']) == journal_path, 'journal pointer differs')
            journal_path = safe(journal_path, self.scope)
            journal_hash,_ = digest(journal_path,item['journal']['sha256'])
            records = [json.loads(line) for line in journal_path.read_text().splitlines()]
            require(digest(journal_path)[0] == journal_hash, 'journal changed while reading')
            self.evidence[str(journal_path)] = journal_hash
            request = self.read(directory/'request.json')
            require(request == scheduled['request'] and request.get('version') == 'msprof_kernel_time_study_v2', 'session request differs')
            require(completion.get('version') == request['version'] and completion.get('status') == 'passed' and completion.get('error') is None, 'session not closed')
            require(records and records[-1].get('type') == 'session_end' and records[-1].get('exit_code') == 0 and records[-1].get('stream_destroyed') is True and records[-1].get('context_destroyed') is True, 'native session has no successful teardown')
            self.exited(directory/'msprof.execution.json')
            ids = [str(row['case_id']) for row in request['cases']]
            require(ids and len(set(ids)) == len(ids) and all(i.isdigit() and str(int(i)) == i and 1 <= int(i) <= 20 for i in ids), 'invalid session case IDs')
            configs = request.get('buffer_configs','normal,swapped').split(',')
            require(len(configs) == 2 and set(configs) == {'normal','swapped'}, 'normal/swapped output coverage required')
            expected = [(case,config,role) for case in ids for config in configs for role in 'AB']
            validation = self.read(directory/'validation.json')
            require(validation.get('scope') == 'final_call_of_final_sample_per_case_config_role', 'unknown output validation scope')
            checked = validation['outputs']; native = [r for r in records if r.get('type') == 'output']
            key = lambda row:(row['case_id'],row['buffer_config'],row['role'])
            require([key(r) for r in checked] == [key(r) for r in native] == expected, 'verified output index coverage differs')
            for row, raw in zip(checked,native):
                stem = f"{row['case_id']}_{row['buffer_config']}_{row['role']}"
                output = directory/'native'/(stem+'.bin')
                require(row.get('passed') is True and raw.get('path') == str(output) and raw.get('validation_scope') == 'final_call_of_final_formal_sample', 'output path/verdict/scope differs')
                self.exited(directory/'verification'/stem/'execution.json')
                self.bundle(output,row['output_hash'])


@contextmanager
def storage_lock(storage):
    path = storage/'dedup.lock'
    if path.exists(): safe(path)
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o644)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally: os.close(fd)


def same_inode(a,b): return (a['device'],a['inode']) == (b['device'],b['inode'])


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def file_ref(path):
    return {'path':str(path), 'sha256':digest(path)[0]}


def checked_ref(ref):
    require(isinstance(ref,dict) and set(ref)=={'path','sha256'}, 'invalid storage evidence pointer')
    path=safe(ref['path']);digest(path,ref['sha256']);return json.loads(path.read_bytes())


def transaction_context(run, transaction):
    run=safe(Path(run),directory=True)
    transaction=safe(Path(transaction),run,directory=True)
    require(transaction.parent==run/'storage/transactions' and re.fullmatch(r'[0-9a-f]{32}',transaction.name),
            'compaction requires an exact storage transaction directory')
    plan_path=safe(transaction/'plan.json');plan=json.loads(plan_path.read_bytes())
    manifest_path=safe(run/'storage/dedup'/(transaction.name+'.json'));manifest=json.loads(manifest_path.read_bytes())
    require(plan.get('version')==VERSION and plan.get('run')==str(run) and plan.get('writers_closed_attested') is True,
            'unrecognized closed transaction plan')
    require(manifest.get('version')==VERSION and manifest.get('status')=='passed' and manifest.get('error') is None
            and manifest.get('accounting_status')=='complete' and manifest.get('reclaimed_bytes_known') is True
            and manifest.get('recovery')==[] and manifest.get('transaction')==str(transaction)
            and manifest.get('evidence_bytes_deleted')==0 and manifest.get('original_records_modified') is False
            and all(manifest.get(k)==v for k,v in plan.items()), 'transaction is not a fully passed original manifest')
    scope=safe(Path(plan['scope']),run,directory=True);parts=scope.relative_to(run).parts
    require(len(parts)>=5 and parts[0] in ('train','validation','test') and parts[1]=='tasks'
            and parts[2]==plan['operator'] and plan['operator'] in OPERATORS, 'transaction task scope differs')
    task=run.joinpath(*parts[:3])
    return run,transaction,plan,manifest,task


def event_binding(task, manifest_ref, expected=None):
    """Bind a stable public event prefix; subsequent unrelated events may append."""
    path=safe(task/'events.jsonl');previous=None
    with path.open('rb') as stream:
        for sequence,line in enumerate(stream):
            record=json.loads(line);body={k:v for k,v in record.items() if k!='hash'}
            require(record.get('sequence')==sequence and record.get('previous_hash')==previous
                    and record.get('hash')=='sha256:'+hashlib.sha256(json_bytes(body)).hexdigest(), 'storage public event chain differs')
            previous=record['hash']
            if record.get('kind')=='closed_outputs_deduplicated' and record.get('value',{}).get('manifest')==manifest_ref:
                result={'path':str(path),'sequence':sequence,'hash':previous}
                require(expected is None or result==expected, 'storage event prefix changed')
                return result
    raise ValueError('passed storage manifest has no public closed-output event')


def expected_journals(transaction, plan, manifest):
    """Prove each linked result and exact intent from the original final manifest."""
    files=plan['files'];results=manifest['results']
    require(isinstance(files,list) and len(files)==len(results)
            and len({r['path'] for r in files})==len(files), 'transaction output coverage differs')
    expected={}
    for number,(row,result) in enumerate(zip(files,results)):
        output=Path(row['path'])
        require(output.is_absolute() and '..' not in output.parts and output.is_relative_to(Path(plan['scope']))
                and DIGEST.fullmatch(row['sha256']) and isinstance(row['bytes'],int) and row['bytes']>=0,
                'transaction output identity is invalid')
        pool=Path(plan['run'])/'storage/output-cas'/row['sha256'].removeprefix('sha256:')
        require(result.get('path')==row['path'] and result.get('pool')==str(pool)
                and result.get('before_hash')==result.get('after_hash')==row['sha256']
                and result.get('status') in ('linked','already_linked_or_pool_seed'), 'transaction result identity differs')
        if result['status']!='linked':continue
        require(result.get('version')==VERSION, 'linked result version differs')
        stem=f'{number:06d}';suffix='.aprof-dedup-'+transaction.name+'-'+stem
        backup=output.with_name(output.name+suffix+'.bak');temporary=output.with_name(output.name+suffix+'.tmp')
        require(not backup.exists() and not backup.is_symlink() and not temporary.exists() and not temporary.is_symlink(),
                'transaction still has backup or temporary output links')
        expected[stem+'.intent.json']={'version':VERSION,'path':str(output),'sha256':row['sha256'],
            'before':result['before'],'pool':str(pool),'backup':str(backup),'temporary':str(temporary)}
        expected[stem+'.result.json']=result
    require(sum(r['reclaimed_bytes'] for r in results)==manifest['reclaimed_bytes'], 'transaction reclamation accounting differs')
    return expected


def audit_external_journal_refs(run, transaction, names):
    """Existing pointer readers require loose files; refuse removing referenced ones."""
    targets={str(transaction/name) for name in names};marker=str(transaction).encode()+b'/'
    hits=[]
    for directory,dirs,files in os.walk(run,followlinks=False):
        dirs[:]=[name for name in dirs if not (Path(directory)/name).is_symlink()]
        for name in files:
            if not name.endswith(('.json','.jsonl')):continue
            path=Path(directory)/name
            if path.parent==transaction:continue  # Compaction's own archival index is intentional.
            data=safe(path,run).read_bytes()
            if marker not in data:continue
            values=[json.loads(line) for line in data.splitlines() if line] if name.endswith('.jsonl') else [json.loads(data)]
            def visit(value):
                if isinstance(value,str) and value in targets:hits.append(str(path))
                elif isinstance(value,dict):
                    for k,v in value.items():visit(k);visit(v)
                elif isinstance(value,list):
                    for v in value:visit(v)
            for value in values:visit(value)
    require(not hits, 'external journal references require a reviewed resolver before compaction: '+str(sorted(set(hits))[:5]))
    return {'checked':'JSON/JSONL exact original journal paths outside transaction','external_references':[]}


def archived_journals(run, transaction):
    """Verify the archive, historical bindings, every member and any loose remainder."""
    run,transaction,plan,manifest,task=transaction_context(run,transaction)
    seal_path=safe(transaction/'journals.seal.json');seal=json.loads(seal_path.read_bytes())
    require(seal.get('version')==COMPACTION and seal.get('transaction')==str(transaction)
            and seal.get('run')==str(run) and seal.get('source_bytes_preserved') is True,
            'invalid journal compaction seal')
    require(seal.get('plan')==file_ref(transaction/'plan.json')
            and seal.get('manifest')==file_ref(run/'storage/dedup'/(transaction.name+'.json')), 'sealed original transaction changed')
    event_binding(task,seal['manifest'],seal.get('event_binding'))
    archive=safe(transaction/'journals.tar');require(seal.get('archive')==file_ref(archive), 'sealed journal archive changed')
    expected=expected_journals(transaction,plan,manifest)
    rows=seal.get('members');require(isinstance(rows,list) and len(rows)==len(expected)
        and {r['name'] for r in rows}==set(expected), 'sealed journal member set differs')
    by_name={r['name']:r for r in rows};payloads={}
    with tarfile.open(archive,'r:') as stream:
        members=stream.getmembers()
        require(len(members)==len(expected) and {m.name for m in members}==set(expected), 'journal tar member set differs')
        for member in members:
            row=by_name[member.name]
            require(member.isfile() and not member.issym() and not member.islnk() and JOURNAL.fullmatch(member.name)
                    and row.get('path')==str(transaction/member.name) and member.size==row.get('bytes')
                    and member.mode==row.get('mode') and member.uid==row.get('uid') and member.gid==row.get('gid')
                    and member.mtime==row.get('mtime_ns',-1)//1000000000, 'journal tar metadata differs')
            data=stream.extractfile(member).read()
            require('sha256:'+hashlib.sha256(data).hexdigest()==row.get('sha256')
                    and json.loads(data)==expected[member.name], 'archived journal differs from closed manifest')
            payloads[member.name]=data
    loose={p.name for p in transaction.iterdir() if JOURNAL.fullmatch(p.name)}
    require(loose<=set(expected), 'unexpected loose journal after compaction seal')
    for name in loose:
        path=safe(transaction/name);info=path.stat();row=by_name[name]
        require(path.read_bytes()==payloads[name] and stat.S_IMODE(info.st_mode)==row['mode']
                and info.st_uid==row['uid'] and info.st_gid==row['gid'], 'loose journal differs from sealed archive')
    receipt=transaction/'journals.compacted.json'
    if receipt.exists() or receipt.is_symlink():
        completion=json.loads(safe(receipt).read_bytes())
        require(completion.get('version')==COMPACTION and completion.get('status')=='complete'
                and completion.get('seal')==file_ref(seal_path) and completion.get('removed_paths')==[r['path'] for r in rows]
                and completion.get('source_bytes_preserved') is True and not loose,
                'completed journal compaction changed or loose journal reappeared')
    return seal,payloads


def validate_journal_storage(run, transaction):
    """A missing archive/seal cannot silently turn a closed transaction into empty recovery."""
    markers=[transaction/name for name in ('journals.tar','journals.seal.json','journals.compacted.json')]
    if any(p.exists() or p.is_symlink() for p in markers):
        archived_journals(run,transaction)
        return True
    manifest_path=run/'storage/dedup'/(transaction.name+'.json')
    if manifest_path.exists() or manifest_path.is_symlink():
        manifest=json.loads(safe(manifest_path).read_bytes())
        if manifest.get('status')=='passed' and manifest.get('accounting_status')=='complete':
            _,_,plan,manifest,_=transaction_context(run,transaction)
            expected=expected_journals(transaction,plan,manifest)
            require({p.name for p in transaction.iterdir() if JOURNAL.fullmatch(p.name)}==set(expected),
                    'closed transaction journal evidence is missing without an archive')
            for name,value in expected.items():
                require(json.loads(safe(transaction/name).read_bytes())==value,'closed transaction journal changed')
    else:
        # A deleted final manifest must not masquerade as a pre-mutation crash.
        plan_path=transaction/'plan.json'
        if plan_path.exists():
            plan=json.loads(safe(plan_path).read_bytes())
            scope=Path(plan.get('scope',''))
            if scope.is_absolute() and scope.is_relative_to(run):
                parts=scope.relative_to(run).parts
                if len(parts)>=3:
                    events=run.joinpath(*parts[:3])/'events.jsonl'
                    if events.exists():
                        for line in safe(events).read_bytes().splitlines():
                            record=json.loads(line)
                            ref=record.get('value',{}).get('manifest',{})
                            require(not (record.get('kind')=='closed_outputs_deduplicated'
                                        and ref.get('path')==str(manifest_path)),
                                    'publicly closed storage manifest is missing')
    return False


def read_compacted_journal(path, expected_sha):
    """Recover exact historical bytes by full original path+hash, never basename."""
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and JOURNAL.fullmatch(path.name), 'invalid historical journal path')
    transaction=path.parent;run=transaction.parents[2]
    _,payloads=archived_journals(run,transaction)
    require(path.name in payloads, 'historical journal not sealed')
    data=payloads[path.name]
    require('sha256:'+hashlib.sha256(data).hexdigest()==expected_sha, 'historical journal hash differs')
    return data


def publish_archive(path, data):
    """Fsync a complete sibling before publication; never overwrite an archive."""
    if path.exists() or path.is_symlink():
        require(safe(path).read_bytes()==data,'preexisting journal archive differs');return
    temporary=path.with_name('.journal-archive-'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path,follow_symlinks=False);sync_directory(path.parent)
    finally:temporary.unlink(missing_ok=True)


def compact_journals(run, transaction, *, writers_closed=False, apply=False):
    require(writers_closed is True,'coordinator must affirm closed output and journal writers')
    with exclusive_host():
        run,transaction,plan,manifest,task=transaction_context(run,transaction)
        with storage_lock(run/'storage'):
            expected=expected_journals(transaction,plan,manifest)
            if not expected:
                return {'status':'not_needed','transaction':str(transaction),'journal_paths':0,'source_bytes_preserved':True}
            manifest_ref=file_ref(run/'storage/dedup'/(transaction.name+'.json'))
            binding=event_binding(task,manifest_ref)
            external=audit_external_journal_refs(run,transaction,expected)
            seal_path=transaction/'journals.seal.json'
            if seal_path.exists() or seal_path.is_symlink():
                seal,payloads=archived_journals(run,transaction)
            else:
                loose={p.name for p in transaction.iterdir() if JOURNAL.fullmatch(p.name)}
                require(loose==set(expected),'original journal set is incomplete; refuse archive')
                rows=[];payloads={};buffer=io.BytesIO()
                with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
                    for name in sorted(expected):
                        path=safe(transaction/name);data=path.read_bytes();info=path.stat()
                        require(json.loads(data)==expected[name],'original journal differs from closed manifest')
                        row={'name':name,'path':str(path),'bytes':len(data),'sha256':'sha256:'+hashlib.sha256(data).hexdigest(),
                            'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'mtime_ns':info.st_mtime_ns}
                        rows.append(row);payloads[name]=data
                        member=tarfile.TarInfo(name);member.size=len(data);member.mode=row['mode'];member.uid=row['uid'];member.gid=row['gid'];member.mtime=row['mtime_ns']//1000000000
                        archive.addfile(member,io.BytesIO(data))
                archive_path=transaction/'journals.tar';archive_bytes=buffer.getvalue()
                seal={'version':COMPACTION,'run':str(run),'transaction':str(transaction),'plan':file_ref(transaction/'plan.json'),
                      'manifest':manifest_ref,'event_binding':binding,'archive':{'path':str(archive_path),'sha256':'sha256:'+hashlib.sha256(archive_bytes).hexdigest()},
                      'members':rows,'external_reference_audit':external,'source_bytes_preserved':True,
                      'producer':file_ref(Path(__file__).resolve())}
                if apply:
                    publish_archive(archive_path,archive_bytes)
                    write_new(seal_path,seal)
                    archived_journals(run,transaction)  # Required complete durable proof before unlink.
            if not apply:
                return {'status':'verified_dry_run','transaction':str(transaction),'journal_paths':len(expected),
                        'potential_removed_directory_entries':len(expected),'new_archive_records':3,'source_bytes_preserved':True}
            require(transaction_context(run,transaction)[2:4]==(plan,manifest),'transaction changed before journal removal')
            # Re-establish durability even for matching files found on reentry.
            # Their existence and hash alone cannot prove an earlier successful fsync.
            for durable in (transaction/'journals.tar',seal_path):
                fd=os.open(safe(durable),os.O_RDONLY|os.O_NOFOLLOW)
                try:os.fsync(fd)
                finally:os.close(fd)
            sync_directory(transaction)
            # Every file is already independently durable in the verified archive.
            # Interruption leaves a valid seal and an explicitly resumable remainder.
            for row in seal['members']:
                path=transaction/row['name']
                if path.exists() or path.is_symlink():
                    require(safe(path).read_bytes()==payloads[row['name']],'journal changed before removal')
                    path.unlink()
            sync_directory(transaction)
            receipt=transaction/'journals.compacted.json'
            completion={'version':COMPACTION,'status':'complete','seal':file_ref(seal_path),
                        'removed_paths':[r['path'] for r in seal['members']], 'source_bytes_preserved':True,
                        'quota_relief':'Directory entries removed; actual filesystem quota relief is not inferred from inode counts.'}
            if receipt.exists():require(json.loads(safe(receipt).read_bytes())==completion,'compaction completion differs')
            else:write_new(receipt,completion)
            archived_journals(run,transaction)
            return {'status':'complete','transaction':str(transaction),'seal':file_ref(seal_path),
                    'completion':file_ref(receipt),'removed_journal_paths':len(expected),'source_bytes_preserved':True}


class KnownOutputLinks:
    """Account for every existing alias before sharing an inode with the CAS.

    Previous immutable transaction inventories attest already closed output
    paths. Stat only matching content hashes; unknown aliases (including an input
    hardlink) fail closed. This does not discover arbitrary files by inode.
    """
    def __init__(self, inventory, transactions):
        hashes = {row['sha256'] for row in inventory.files.values()}
        paths = set(inventory.files)
        for transaction in transactions.iterdir():
            validate_journal_storage(inventory.run,transaction)
            plan_path = transaction/'plan.json'
            if not plan_path.exists(): continue  # Crash before any mutation.
            safe(plan_path,transactions)
            plan = json.loads(plan_path.read_text())
            require(plan.get('version') == VERSION and plan.get('writers_closed_attested') is True,
                    'unrecognized prior storage inventory')
            for row in plan['files']:
                if row['sha256'] in hashes: paths.add(row['path'])
        self.counts = {}
        for value in paths:
            path = Path(value)
            require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(inventory.run), 'prior output path escapes run')
            parts = path.relative_to(inventory.run).parts
            require(len(parts) >= 7 and parts[0] in ('train','validation','test') and parts[1] == 'tasks' and parts[2] in OPERATORS,
                    'prior inventory contains a non-output path')
            tail = parts[3:]
            if tail[:1] == ('candidates',):
                require(len(tail) > 2 and TOKEN.fullmatch(tail[1]), 'invalid candidate output path')
                tail = tail[2:]
            suffixes = ['', *('.'+key for key in OUTPUT_KEYS.get(parts[2],()))]
            if tail[:2] == ('preflight','pilot'):
                valid = len(tail) == 4 and re.fullmatch(r'case_(0[1-9]|1[0-9]|20)',tail[2]) and tail[3] in ['output.bin'+s for s in suffixes]
            else:
                valid = (len(tail) == 6 and tail[0] == 'stages' and TOKEN.fullmatch(tail[1]) and
                    tail[2] in ('cohort','direct_parent','original_baseline') and TOKEN.fullmatch(tail[3]) and tail[4] == 'native' and
                    any(re.fullmatch(r'([1-9]|1[0-9]|20)_(normal|swapped)_[AB]\.bin'+re.escape(s),tail[5]) for s in suffixes))
            require(valid, 'prior inventory contains a non-output artifact')
            if not path.exists() and not path.is_symlink(): continue
            info = safe(path,inventory.run).stat()
            key = (info.st_dev,info.st_ino)
            self.counts[key] = self.counts.get(key,0)+1

    def count(self, info): return self.counts.get((info['device'],info['inode']),0)

    def moved(self, before, after):
        for info,delta in ((before,-1),(after,1)):
            key = (info['device'],info['inode'])
            self.counts[key] = self.counts.get(key,0)+delta


def recover(inventory, transactions):
    """Finish only interrupted replacements for this verified output inventory."""
    recovered = []
    for transaction in sorted(transactions.iterdir()):
        safe(transaction,transactions,directory=True)
        require(re.fullmatch(r'[0-9a-f]{32}',transaction.name), 'unknown transaction directory')
        if validate_journal_storage(inventory.run,transaction):
            continue  # Every archived intent is paired with its proved original result.
        for intent_path in sorted(transaction.glob('*.intent.json')):
            safe(intent_path,transaction)
            intent = json.loads(intent_path.read_text())
            output = intent.get('path')
            if output not in inventory.files: continue
            result_path = intent_path.with_name(intent_path.name.replace('.intent.json','.result.json'))
            if result_path.exists(): safe(result_path,transaction); continue
            require(intent.get('version') == VERSION and intent.get('sha256') == inventory.files[output]['sha256'], 'recovery intent differs from verified index')
            output = Path(output); expected = intent['sha256']
            suffix = '.aprof-dedup-'+transaction.name+'-'+intent_path.name.split('.')[0]
            backup = output.with_name(output.name+suffix+'.bak'); temporary = output.with_name(output.name+suffix+'.tmp')
            require(intent.get('backup') == str(backup) and intent.get('temporary') == str(temporary), 'recovery path differs')
            # Inventory verification already proved that the visible path is intact.
            digest(output,expected)
            leftovers = []
            for path in (temporary,backup):
                if path.exists() or path.is_symlink():
                    digest(path,expected); path.unlink(); leftovers.append(str(path))
            sync_directory(output.parent)
            result = {'version':VERSION,'path':str(output),'before_hash':expected,'after_hash':expected,
                      'status':'recovered_intact_output','removed_temporary_links':leftovers,
                      'reclaimed_bytes':0,'reclaimed_bytes_known':False,
                      'reason':'Interrupted transaction cleanup; prior link reclamation cannot be reconstructed exactly.'}
            write_new(result_path,result); recovered.append(result)
    return recovered


def replace_one(row, pool, transaction, number, known_links):
    output = Path(row['path']); expected = row['sha256']
    _,before = digest(output,expected)
    cas = pool/expected.removeprefix('sha256:')
    require(before['device'] == pool.stat().st_dev, 'CAS and output must be on the same filesystem')
    if not cas.exists() and not cas.is_symlink():
        require(before['links'] == known_links.count(before), 'output has an alias outside verified closed outputs; refusing CAS seed')
        os.link(output,cas,follow_symlinks=False)
        sync_directory(pool)
    _,pooled = digest(cas,expected)
    require(pooled['links'] == known_links.count(pooled)+1, 'CAS has an alias outside verified closed outputs')
    if not same_inode(before,pooled):
        require(before['links'] == known_links.count(before), 'output has an alias outside verified closed outputs')
    require(all(before[k] == pooled[k] for k in ('mode','uid','gid')), 'CAS permissions/ownership differ; output unchanged')
    if same_inode(before,pooled):
        return {'path':str(output),'pool':str(cas),'before_hash':expected,'after_hash':expected,
                'before':before,'after':digest(output,expected)[1],'status':'already_linked_or_pool_seed',
                'reclaimed_bytes':0,'reclaimed_allocated_bytes_estimate':0}
    stem = f'{number:06d}'; suffix = '.aprof-dedup-'+transaction.name+'-'+stem
    backup = output.with_name(output.name+suffix+'.bak'); temporary = output.with_name(output.name+suffix+'.tmp')
    intent = {'version':VERSION,'path':str(output),'sha256':expected,'before':before,
              'pool':str(cas),'backup':str(backup),'temporary':str(temporary)}
    write_new(transaction/(stem+'.intent.json'),intent)
    replaced = False; backup_created = False; temporary_created = False
    try:
        os.link(output,backup,follow_symlinks=False)
        backup_created = True
        _,backed = digest(backup,expected)
        require(same_inode(before,backed), 'output inode changed before backup')
        os.link(cas,temporary,follow_symlinks=False)
        temporary_created = True
        _,linked = digest(temporary,expected)
        require(same_inode(pooled,linked), 'CAS inode changed before replacement')
        _,current = digest(output,expected)
        require(same_inode(before,current), 'output inode changed before replacement')
        sync_directory(output.parent)
        os.replace(temporary,output); replaced = True
        _,after = digest(output,expected)
        require(same_inode(pooled,after), 'replacement does not reference verified CAS')
        sync_directory(output.parent)
        backup.unlink()
        sync_directory(output.parent)
    except BaseException:
        if replaced and backup.exists():
            digest(backup,expected)
            os.replace(backup,output)
            digest(output,expected)
            sync_directory(output.parent)
        for path,created in ((temporary,temporary_created),(backup,backup_created)):
            if created and (path.exists() or path.is_symlink()):
                digest(path,expected); path.unlink()
        raise
    known_links.moved(before,after)
    result = {'version':VERSION,'path':str(output),'pool':str(cas),'before_hash':expected,'after_hash':expected,
              'before':before,'after':after,'status':'linked',
              'reclaimed_bytes':before['bytes'] if before['links'] == 1 else 0,
              'reclaimed_allocated_bytes_estimate':before['allocated_bytes'] if before['links'] == 1 else 0}
    write_new(transaction/(stem+'.result.json'),result)
    return result


def deduplicate(run, scope, *, kind, writers_closed=False, apply=False):
    require(kind in ('pilot','cohort','stage'), 'unsupported output scope')
    require(writers_closed is True, 'coordinator must affirm that all selected output writers are closed')
    started = time.time()
    # This is also the collector lock, not merely a dedup-vs-dedup lock.
    with exclusive_host():
        inventory = Inventory(run,scope,kind)
        plan = {'version':VERSION,'run':str(inventory.run),'scope':str(inventory.scope),'kind':kind,
                'operator':inventory.operator,'writers_closed_attested':True,
                'started_at':started,'host_exclusive_lock_held':True,
                'coordinator_requirement':'No concurrent collector launch loop; invoke synchronously between terminal stages.',
                'producer':{'path':str(Path(__file__).resolve()),'sha256':digest(Path(__file__).resolve())[0]},
                'logical_bytes':sum(r['bytes'] for r in inventory.files.values()),
                'files':list(inventory.files.values()),
                'index_evidence':[{'path':p,'sha256':h} for p,h in sorted(inventory.evidence.items())]}
        if not apply: return {**plan,'status':'verified_dry_run','evidence_bytes_deleted':0}
        storage = inventory.run/'storage'; mkdir(storage)
        with storage_lock(storage):
            pool = storage/'output-cas'; transactions = storage/'transactions'; manifests = storage/'dedup'
            for path in (pool,transactions,manifests): mkdir(path)
            transaction = transactions/uuid.uuid4().hex; mkdir(transaction)
            write_new(transaction/'plan.json',plan)
            results = []; recovered = []; error = None
            try:
                recovered = recover(inventory,transactions)
                known_links = KnownOutputLinks(inventory,transactions)
                for number,row in enumerate(inventory.files.values()):
                    results.append(replace_one(row,pool,transaction,number,known_links))
                inventory.recheck_evidence()
            except BaseException as exc:
                error = {'type':type(exc).__name__,'message':str(exc)}
                raise
            finally:
                manifest = {**plan,'status':'failed' if error else 'passed','error':error,'ended_at':time.time(),
                    'transaction':str(transaction),'results':results,'recovery':recovered,
                    'reclaimed_bytes':sum(r['reclaimed_bytes'] for r in results),
                    'reclaimed_bytes_known':error is None and not any(r.get('reclaimed_bytes_known') is False for r in recovered),
                    'reclaimed_bytes_lower_bound':sum(r['reclaimed_bytes'] for r in results),
                    'accounting_status':'lower_bound' if error or recovered else 'complete',
                    'reclaimed_allocated_bytes_estimate':sum(r['reclaimed_allocated_bytes_estimate'] for r in results),
                    'reclamation_definition':'Bytes of duplicate inodes whose last link was removed in this invocation; filesystem snapshots, reflinks and delayed allocation may change physical free space.',
                    'evidence_bytes_deleted':0,'original_records_modified':False,
                    'metadata_note':'Hardlinks share inode permissions and modification time; ctime/link counts change. Output bytes and evidence paths remain unchanged.'}
                path = manifests/(transaction.name+'.json'); write_new(path,manifest)
                manifest['manifest_path'] = str(path)
            return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True); parser.add_argument('--scope')
    parser.add_argument('--kind',choices=('pilot','cohort','stage'))
    parser.add_argument('--writers-closed',action='store_true',help='Coordinator attests the selected scope has no live/future output writer')
    parser.add_argument('--compact-transaction',help='Archive and retire only fully passed transaction journals; preserve original plan/manifest')
    parser.add_argument('--apply',action='store_true',help='Replace duplicate output inodes; default verifies and prints a read-only inventory')
    args = parser.parse_args()
    if args.compact_transaction:
        require(args.scope is None and args.kind is None,'compaction cannot also select an output scope')
        result=compact_journals(args.run,args.compact_transaction,writers_closed=args.writers_closed,apply=args.apply)
    else:
        require(args.scope is not None and args.kind is not None,'output scope and kind required')
        result=deduplicate(args.run,args.scope,kind=args.kind,writers_closed=args.writers_closed,apply=args.apply)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()

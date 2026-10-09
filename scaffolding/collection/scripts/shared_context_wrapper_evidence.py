"""Bounded evidence helpers for explicit wrappers; no devices or ledger mutations."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import signal
import tarfile

from cannbench_shared_context import sha,load,save
from shared_context_build import source_hash

VERSION='shared_context_wrapper_v4'


def safe_token(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',value):raise ValueError('unsafe identifier')
    return value


def cases_checked(values):
    if not values or any(type(c) is not int or c not in range(1,21) for c in values) or len(set(values))!=len(values):
        raise ValueError('cases must be distinct integers 1..20')
    return list(values)


def producers(paths):
    return {str(Path(p).resolve()):sha(p) for p in paths}


def verify_refs(refs):
    for path,expected in refs.items():
        if sha(path)!=expected:raise ValueError('frozen command/build/input identity changed: '+path)


def snapshot_producers(out,refs):
    directory=Path(out)/'producers';directory.mkdir()
    result={}
    for path,digest in refs.items():
        data=Path(path).read_bytes()
        if 'sha256:'+hashlib.sha256(data).hexdigest()!=digest:raise ValueError('producer changed before snapshot')
        target=directory/Path(path).name
        with target.open('xb') as stream:stream.write(data)
        target.chmod(0o444);result[path]={'sha256':digest,'snapshot':str(target)}
    return result


def archive_native_binding(binding,build,roles):
    """Require archive bytes to cover exactly the native source dependency trees."""
    if sha(binding['path'])!=binding['sha256']:raise ValueError('source archive hash changed')
    archived={};tar_entries={};snapshot=None;snapshot_bytes=None
    def unique_pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate snapshot manifest JSON key')
            result[key]=value
        return result
    with tarfile.open(binding['path']) as archive:
        for member in archive:
            name=PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts:raise ValueError('unsafe archive member')
            if member.name=='APROF_SOURCE_SNAPSHOT.json':
                if snapshot is not None or not member.isfile():raise ValueError('duplicate/nonregular snapshot manifest')
                snapshot_bytes=archive.extractfile(member).read()
                snapshot=json.loads(snapshot_bytes,object_pairs_hook=unique_pairs)
                continue
            if not member.name.startswith('source/'):
                if member.isdir() and member.name=='source':continue
                raise ValueError('unknown archive root member')
            if member.isdir():continue
            if not member.isfile():raise ValueError('nonregular source archive member')
            relative=member.name[len('source/'):]
            if str(PurePosixPath(relative))!=relative or not relative or relative in archived:raise ValueError('duplicate/noncanonical source archive path')
            stream=archive.extractfile(member);digest=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            archived[relative]='sha256:'+digest.hexdigest()
            tar_entries[relative]={'path':relative,'mode':member.mode,'size_bytes':member.size,'sha256':archived[relative]}
    if not isinstance(snapshot,dict) or set(snapshot)!={'schema_version','kind','root_label','excludes','files'} or snapshot.get('schema_version')!='1.0.0' or snapshot.get('kind')!='aprof_source_snapshot_v1':
        raise ValueError('missing or unsupported APROF source snapshot manifest')
    if not isinstance(snapshot['root_label'],str) or not snapshot['root_label'] or not isinstance(snapshot['excludes'],list) or any(not isinstance(p,str) for p in snapshot['excludes']):raise ValueError('invalid snapshot source/exclusion declaration')
    declared={}
    if not isinstance(snapshot['files'],list):raise ValueError('snapshot files must be an array')
    for item in snapshot['files']:
        if not isinstance(item,dict) or set(item)!={'path','mode','size_bytes','sha256'}:raise ValueError('invalid snapshot file record')
        relative=item['path']
        if not isinstance(relative,str) or not relative or PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts or str(PurePosixPath(relative))!=relative or relative in declared:raise ValueError('invalid/duplicate snapshot file path')
        if type(item['mode']) is not int or not 0<=item['mode']<=0o777 or type(item['size_bytes']) is not int or item['size_bytes']<0 or not re.fullmatch(r'sha256:[0-9a-f]{64}',str(item['sha256'])):raise ValueError('invalid snapshot file mode/size/hash')
        declared[relative]=item
    if declared!=tar_entries:raise ValueError('snapshot manifest files do not match actual tar source paths/modes/sizes/hashes')
    snapshot_hash='sha256:'+hashlib.sha256(snapshot_bytes).hexdigest()
    if 'manifest_sha256' in binding and binding['manifest_sha256']!=snapshot_hash:raise ValueError('snapshot manifest hash differs from source binding')
    if 'file_count' in binding and binding['file_count']!=len(declared):raise ValueError('snapshot file count differs from source binding')
    if not any(p.startswith('op_host/') for p in archived) or not any(p.startswith('op_kernel/') for p in archived) or 'CMakeLists.txt' not in archived:
        raise ValueError('archive is missing native source/CMake coverage')
    identities={}
    for role in roles:
        item=build['roles'][role];source=Path(item['source_dir']).resolve()
        actual_native={str(p.relative_to(source)) for sub in ('op_host','op_kernel') for p in (source/sub).rglob('*') if p.is_file()}
        declared_native={p for p in archived if p.startswith(('op_host/','op_kernel/'))}
        if actual_native!=declared_native:raise ValueError('archive/native dependency coverage differs')
        for relative,digest in archived.items():
            path=source/relative
            if not path.is_file() or sha(path)!=digest:raise ValueError('native source differs from archive: '+relative)
        if source_hash(source)!=item['source_sha256']:raise ValueError('build native source hash mismatch')
        if sha(source/'CMakeLists.txt')!='sha256:'+item['cmake_sha256']:raise ValueError('source CMake differs from build')
        if sha(item['binary'])!='sha256:'+item['binary_sha256']:raise ValueError('native binary differs from build')
        identities[role]={k:item[k] for k in ('source_sha256','source_dir','cmake_sha256','binary_sha256','kernel_symbols')}
    return {'archive':binding,'archive_hash_verified':True,'snapshot_manifest_hash':snapshot_hash,'snapshot_kind':snapshot['kind'],'snapshot_file_count':len(declared),'native_roles':identities,
            'identity_scopes':{'archive':'entire deterministic source snapshot','native':'exact op_host/op_kernel dependency paths and bytes, plus separately bound CMake'}}


def input_refs(bindings,cases,opdir):
    rows={int(row['case_id']):row for row in bindings['cases']}
    if len(rows)!=len(bindings['cases']):raise ValueError('duplicate input binding case')
    refs={};metadata={}
    for case in cases:
        row=rows[case];metadata[case]=str(Path(row['metadata']['path']).resolve())
        if Path(row['verifier']['path']).resolve()!=Path(opdir).resolve()/'scripts/verify_result.py':raise ValueError('original oracle path mismatch')
        for item in [row['metadata'],row['verifier'],*row['inputs'].values(),*([row['oracle_file']] if row['oracle_file'] else [])]:
            path=str(Path(item['path']).resolve())
            if path in refs and refs[path]!=item['sha256']:raise ValueError('conflicting input identity')
            refs[path]=item['sha256']
        # Legacy metadata may intentionally encode nonfinite workload values.
        value=json.loads(Path(metadata[case]).read_text())
        for key,item in row['inputs'].items():
            if Path(value[key]).resolve()!=Path(item['path']).resolve():raise ValueError('metadata points outside frozen input binding')
        if row['oracle_file'] and Path(value['golden']).resolve()!=Path(row['oracle_file']['path']).resolve():raise ValueError('golden path differs from binding')
    verify_refs(refs)
    return metadata,refs


def inspect_json(path,errors):
    try:
        value=load(path)
        if not isinstance(value,dict):raise ValueError('evidence record must be an object')
        return value
    except (ValueError,OSError) as exc:
        errors.append({'path':str(path),'type':type(exc).__name__,'message':str(exc)});return None


def qualification_costs(out):
    costs=dict(native_sessions_attempted=0,native_sessions_started=0,native_sessions_completed=0,event_samples=0,
               timed_complete_calls=0,warmup_complete_calls=0,unparsed_raw_rows=0)
    errors=[]
    directories={p.parent for p in Path(out).glob('*/started.json')}|{p.parent for p in Path(out).glob('*/journal.jsonl')}
    costs['native_sessions_attempted']=len(directories)
    for directory in sorted(directories):
        path=directory/'journal.jsonl';rows=[]
        if not path.exists():continue
        try:
            stream=path.open(errors='replace')
        except OSError as exc:
            errors.append({'path':str(path),'message':str(exc)});continue
        with stream:
            for index,line in enumerate(stream,1):
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('journal row is not an object')
                    rows.append(row)
                except ValueError as exc:
                    costs['unparsed_raw_rows']+=1;errors.append({'path':str(path),'line':index,'message':str(exc)})
        costs['native_sessions_started']+=int(any(r.get('type') in ('process_start','session_start','sample') for r in rows))
        costs['native_sessions_completed']+=int(any(r.get('type')=='session_end' and r.get('exit_code')==0 for r in rows))
        for row in rows:
            if row.get('type')=='sample':
                costs['event_samples']+=1
                count=row.get('repeat')
                if type(count) is int and count>0:costs['timed_complete_calls']+=count
            if row.get('type')=='warmup_complete':
                count=row.get('calls_per_role')
                if type(count) is int and count>0:costs['warmup_complete_calls']+=2*count
    return costs,errors


def diagnostic_costs(out,stage,cases):
    costs=dict(native_sessions_attempted=0,native_sessions_completed=0,native_complete_calls=0,native_kernel_launches_submitted=0,
               warmup_complete_calls=0,profile_launches_captured=0,diagnostic_cases_completed=0)
    errors=[];completed=[]
    for case in cases:
        directory=Path(out)/'evidence'/f'case_{case:02d}' if stage=='correctness' else Path(out)/f'case_{case:02d}'
        execution=directory/('native.execution.json' if stage=='correctness' else 'profile.execution.json')
        if execution.exists() or (directory/'native.json').exists():costs['native_sessions_attempted']+=1
        if (directory/'native.json').exists():
            native=inspect_json(directory/'native.json',errors)
            if native:
                costs['native_sessions_completed']+=int(native.get('exit_code')==0)
                warmup=native.get('warmup_complete_calls',0);calls=native.get('profile_complete_calls',0);launches=native.get('launches_per_call',0)
                if all(type(v) is int and v>=0 for v in (warmup,calls,launches)):
                    costs['warmup_complete_calls']+=warmup;costs['native_complete_calls']+=warmup+calls
                    costs['native_kernel_launches_submitted']+=(warmup+calls)*launches
        result_path=directory/('correctness.json' if stage=='correctness' else 'profile-summary.json')
        if result_path.exists():
            result=inspect_json(result_path,errors)
            verification=inspect_json(directory/'verify.execution.json',errors) if (directory/'verify.execution.json').exists() else None
            native=inspect_json(directory/'native.json',errors) if (directory/'native.json').exists() else None
            native_ok=bool(native and native.get('exit_code')==0 and native.get('mode')==stage and native.get('warmup_complete_calls')==(0 if stage=='correctness' else 10) and native.get('profile_complete_calls')==(1 if stage=='correctness' else 5))
            verifier_ok=bool(verification and verification.get('exit_code')==0 and verification.get('error') is None)
            output_ok=True
            if stage=='profile':
                validation=inspect_json(directory/'output-validation.json',errors) if (directory/'output-validation.json').exists() else None
                output_ok=bool(validation and validation.get('passed') is True)
            if result and native_ok and verifier_ok and output_ok and (result.get('passed') is True if stage=='correctness' else result.get('complete') is True):completed.append(case)
            if stage=='profile' and result and type(result.get('launch_count')) is int and result['launch_count']>=0:costs['profile_launches_captured']+=result['launch_count']
    costs['diagnostic_cases_completed']=len(completed)
    return costs,completed,errors


def evidence_hashes(paths,errors):
    result={}
    for path in paths:
        path=Path(path)
        if path.exists():
            try:result[str(path)]=sha(path)
            except OSError as exc:errors.append({'path':str(path),'message':str(exc)})
    return result


def install_termination_handler():
    def stop(signum,frame):raise KeyboardInterrupt('wrapper received SIGTERM')
    signal.signal(signal.SIGTERM,stop)


def memory_preflight(run_dir,task,label,build_path,cases,*,qualification=False):
    """Freeze/replay small allocation-plan evidence; never rehash tensor/compiler blobs."""
    from shared_context_memory_plan import plan as recompute
    run_dir=Path(run_dir).resolve();task=Path(task).resolve();build_path=Path(build_path).resolve()
    path=task/(safe_token(label)+'-memory-plan.json')
    # Case descriptors are opaque legacy metadata, including intentional NaN/Inf.
    document=json.loads(path.read_text());build=load(build_path)
    audit_path=run_dir/'bootstrap/resource-preflight-audit.json';sizeof_path=run_dir/'bootstrap/sizeof-metadata.json'
    audit=load(audit_path);sizeof=load(sizeof_path);provenance=document.get('provenance',{})
    if document.get('label')!=label:raise ValueError('memory plan candidate/baseline label mismatch')
    if type(document.get('prospective')) is not bool or qualification and document['prospective'] is not True:
        raise ValueError('future qualification requires a prospective baseline memory plan')
    if provenance.get('audit')!=sha(audit_path) or provenance.get('sizeof')!=sha(sizeof_path):
        raise ValueError('memory plan uses stale audit/sizeof evidence')
    bindings_path=task/'input-bindings.json';bindings=load(bindings_path)
    descriptors={int(row['case_id']):row['attributes'] for row in bindings['cases']}
    rows={row['case_id']:row for row in document.get('cases',[])}
    if len(rows)!=len(document.get('cases',[])) or not set(cases)<=set(rows):raise ValueError('memory plan missing/duplicate declared cases')
    refs={str(path):sha(path),str(audit_path):sha(audit_path),str(sizeof_path):sha(sizeof_path),str(build_path):sha(build_path),str(bindings_path):sha(bindings_path)}
    identities={};peaks=[]
    for role in ('A','B'):
        adapter=build_path.parent/role/'op_host'/f"{build['operator']}.asc"
        entries=[entry for entry in audit.get('adapters',[]) if Path(entry['adapter_path']).resolve()==adapter]
        if len(entries)!=1:raise ValueError('memory audit lacks exact build/role adapter')
        entry=entries[0];identity=build['roles'][role]
        if entry['source_sha256']!=identity['source_sha256'] or entry['adapter_sha256']!=identity['adapter_sha256'] or entry['role']!=role or entry['operator']!=build['operator']:
            raise ValueError('memory audit does not match frozen native source/build')
        identities[role]={'source_sha256':identity['source_sha256'],'adapter_sha256':identity['adapter_sha256'],'binary_sha256':identity['binary_sha256']}
        for key in ('adapter','header','kernel'):refs[entry[key+'_path']]='sha256:'+entry[key+'_sha256']
        matches=[meta for meta in sizeof.get('entries',[]) if meta.get('adapter_sha256')==entry['adapter_sha256']]
        if len(matches)!=1:raise ValueError('memory plan lacks unique compiler sizeof evidence')
        meta=matches[0];refs[meta['evidence_path']]='sha256:'+meta['evidence_sha256']
    for item in audit.get('harness',[]):refs[item['path']]='sha256:'+item['sha256']
    for case in cases:
        row=rows[case];request=row['request']
        if json.dumps(request.get('case'),sort_keys=True,allow_nan=True)!=json.dumps(descriptors.get(case),sort_keys=True,allow_nan=True):
            raise ValueError('memory plan case differs from declared input attributes')
        expected_roles={r:str(build_path.parent/r/'op_host'/f"{build['operator']}.asc") for r in ('A','B')}
        if request.get('roles')!=expected_roles:raise ValueError('memory plan references another baseline/candidate build')
        if qualification and set(request.get('buffer_configs',[]))!={'normal','swapped'}:raise ValueError('qualification memory plan lacks both buffer configurations')
        actual=recompute(audit,sizeof,request)
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(row['plan'],sort_keys=True,allow_nan=False):raise ValueError('memory plan does not match audited allocation formulas')
        peaks.append(actual['peak_requested_device_bytes'])
    verify_refs(refs)
    return {'version':'shared_context_memory_binding_v1','label':label,'prospective':document['prospective'],
        'case_ids':list(cases),'native_roles':identities,'frozen_files':refs,'max_declared_requested_device_bytes':max(peaks),
        'scope':'explicit allocation requests only; no physical free-memory bound or runtime/allocator overhead guarantee'}

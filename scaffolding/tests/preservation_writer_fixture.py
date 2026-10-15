#!/usr/bin/env python3
"""Synthetic test writer. All roots are injected; no native or host lock."""
from pathlib import Path
import argparse, hashlib, json, os, stat, sys, tarfile

# All roots/refs are supplied by the tiny fixture before execute().
# No real campaign path or scratch is available as a default.
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import level2_failed_capture_preservation as reader
from level2_failed_capture_preservation import VERSION,BLOCK,require,canonical,local_open,DigestReader,ref,small,load_ref,decimal_mtime,verify_tar,verify_completion,verify_document








def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def write_bytes(path,data):
    with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sync_dir(Path(path).parent)

def save(path,value):
    write_bytes(path,(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
    return ref(path)

def signature(st):
    return {'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'gid':st.st_gid,'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns}

def metadata(root):
    root=canonical(root);rst=root.lstat();require(stat.S_ISDIR(rst.st_mode),'source root is not a directory')
    rows=[]
    def walk(p):
        p=canonical(p);st=p.lstat();require(st.st_dev==rst.st_dev,'nested mount rejected')
        kind='directory' if stat.S_ISDIR(st.st_mode) else 'file' if stat.S_ISREG(st.st_mode) else None
        require(kind is not None,'special source entry rejected')
        row={'relative_path':p.relative_to(root).as_posix() if p!=root else '', 'kind':kind,**signature(st)};rows.append(row)
        if kind=='directory':
            with os.scandir(p) as entries:names=sorted(e.name for e in entries)
            for name in names:walk(p/name)
    walk(root)
    return sorted(rows,key=lambda r:r['relative_path'])


def write_tar(root,label,path,rows):
    indexed=[]
    with Path(path).open('xb') as output:
        with tarfile.open(fileobj=output,mode='w|',format=tarfile.PAX_FORMAT) as archive:
            for row in rows:
                original=canonical(root/row['relative_path']);require(signature(original.lstat())=={k:row[k] for k in signature(original.lstat())},'source metadata changed before TAR')
                item=tarfile.TarInfo(label+('/'+row['relative_path'] if row['relative_path'] else ''))
                item.mode=row['mode'];item.uid=row['uid'];item.gid=row['gid'];item.mtime=row['mtime_ns']//1_000_000_000;item.pax_headers={'mtime':decimal_mtime(row['mtime_ns'])}
                if row['kind']=='directory':item.type=tarfile.DIRTYPE;archive.addfile(item);indexed.append(dict(row));continue
                item.type=tarfile.REGTYPE;item.size=row['bytes']
                with local_open(original) as source:
                    require(signature(os.fstat(source.fileno()))=={k:row[k] for k in signature(os.fstat(source.fileno()))},'source file changed before read')
                    stream=DigestReader(source);archive.addfile(item,stream)
                    require(stream.count==row['bytes'] and not source.read(1),'source file length changed')
                    require(signature(os.fstat(source.fileno()))=={k:row[k] for k in signature(os.fstat(source.fileno()))},'source file changed during read')
                    indexed.append({**row,'sha256':stream.sha})
                require(signature(original.lstat())=={k:row[k] for k in signature(original.lstat())},'source entry changed during read')
        output.flush();os.fsync(output.fileno())
    sync_dir(Path(path).parent)
    return indexed


def original_unchanged(root,rows):
    current=metadata(root)
    require(current==[{k:v for k,v in r.items() if k!='sha256'} for r in rows],'original tree/metadata changed')
    for row in rows:
        if row['kind']=='file':require(ref(root/row['relative_path'])['sha256']==row['sha256'],'original payload changed after copy')
    require(metadata(root)==current,'original metadata changed during final verification')



def execute(owner_sha):
    producer=Path(__file__).resolve();require(ref(producer)['sha256']==owner_sha,'externally reviewed owner SHA differs')
    allocation_data=small(ALLOCATION);journal_data=small(JOURNAL);terminal_data=small(TERMINAL)
    allocation=json.loads(allocation_data);terminal=json.loads(terminal_data)
    require(allocation['capture_root']==str(SCRATCH) and allocation['archive_root']==str(P03/'raw'),'exact original allocation differs')
    require(terminal['writer_terminal'] is True and terminal['source_feedback_closed'] is False and terminal['tool_result']['session_id']==89943 and type(terminal['tool_result']['exit_code']) is int and terminal['tool_result']['exit_code']==1,'original root terminal receipt differs')
    rows=[json.loads(x) for x in journal_data.splitlines()];require(rows[-1]['type']=='session_end' and rows[-1]['exit_code']==1 and rows[-1]['context_destroyed'] is True and rows[-1]['stream_destroyed'] is True,'original failed native terminal differs')
    require(not (P03/'msprof.execution.json').exists() and not (P03/'completion.json').exists(),'failed original collector namespace changed')
    roots={'native':canonical(P03/'native'),'scratch':canonical(SCRATCH)}
    output=canonical(OUTPUT);require(not output.exists(),'preservation namespace exists; no automatic retry')
    require(all(not output.is_relative_to(r) and not r.is_relative_to(output) for r in roots.values()),'output overlaps original tree')
    metadata_before={label:metadata(root) for label,root in roots.items()}
    output.mkdir();sync_dir(output.parent);retained=output/'retained';retained.mkdir();sync_dir(output)
    reader_source=Path(reader.__file__).resolve()
    for name,data in [('allocation.json',allocation_data),('terminal-receipt.json',terminal_data),('journal.jsonl',journal_data),('producer.py',producer.read_bytes()),('reader.py',reader_source.read_bytes())]:write_bytes(retained/name,data)
    originals=[ALLOCATION,JOURNAL,TERMINAL,ref(producer),ref(reader_source),terminal['forensics'],terminal['health_after'],terminal['owner_request']]
    forensic=load_ref(terminal['forensics'])
    for row in forensic['preserved_refs']:originals.append(row if 'path' in row else row['retained_prefix'])
    for row in forensic['sessions']:
        originals.append(row['journal'])
        if row['completion'] is not None:originals.append(row['completion'])
    unique={}
    for original in originals:
        if original['path'] in unique:require(unique[original['path']]==original,'contradictory original metadata reference')
        unique[original['path']]=original
    mapped=output/'inputs';mapped.mkdir();sync_dir(output);retained_inputs=[]
    for number,original in enumerate(sorted(unique.values(),key=lambda r:r['path'])):
        data=small(original);dest=mapped/f'{number:03d}.bin';write_bytes(dest,data)
        retained_inputs.append({'original':original,'retained':ref(dest)})
    request={'version':VERSION,'scope':'failed_physical_evidence_only_no_observation_reclassification','original_roots':{k:str(v) for k,v in roots.items()},'original_bindings':{'allocation':ALLOCATION,'journal':JOURNAL,'terminal':TERMINAL},'originals_will_be_deleted':False,'retained_inputs':retained_inputs,'retained':{k:ref(retained/name) for k,name in [('allocation','allocation.json'),('terminal','terminal-receipt.json'),('journal','journal.jsonl'),('producer','producer.py'),('reader','reader.py')]}}
    request_ref=save(output/'request.json',request)
    try:
        archives=[]
        for label,root in roots.items():
            path=output/f'original-{label}.tar';entries=write_tar(root,label,path,metadata_before[label]);archives.append({'label':label,'archive':ref(path),'entries':entries})
        inventory_ref=save(output/'inventory.json',{'version':VERSION,'request':request_ref,'roots':archives})
        verified=[verify_tar(r['archive'],r['label'],r['entries']) for r in archives]
        for root in archives:original_unchanged(roots[root['label']],root['entries'])
        require(small(ALLOCATION)==allocation_data and small(JOURNAL)==journal_data and small(TERMINAL)==terminal_data and ref(producer)['sha256']==owner_sha,'original fixed evidence changed')
        verification_ref=save(output/'verification.json',{'version':VERSION,'status':'passed','request':request_ref,'inventory':inventory_ref,'archives':verified,'original_trees_rechecked':True})
        for value in [request_ref,inventory_ref,verification_ref,*[a['archive'] for a in archives],*request['retained'].values(),*[r['retained'] for r in retained_inputs]]:require(ref(value['path'])==value,'attachment changed before completion')
        # Full original recheck follows final metadata/attachment production as well.
        for root in archives:original_unchanged(roots[root['label']],root['entries'])
        done={'version':VERSION,'status':'passed','request':request_ref,'inventory':inventory_ref,'verification':verification_ref,'archives':[a['archive'] for a in archives],'originals_deleted':False,'native_execution_performed':False,'source_feedback_closed':False,'scope':request['scope']}
        encoded=(json.dumps(done,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();completion={'path':str(output/'completion.json'),'sha256':'sha256:'+hashlib.sha256(encoded).hexdigest()}
        protected=[request_ref,inventory_ref,verification_ref,*[r['archive'] for r in archives],*request['retained'].values(),*[r['retained'] for r in retained_inputs]]
        signatures={v['path']:signature(canonical(v['path']).lstat()) for v in protected}
        verify_document(completion,done)
        for root in archives:original_unchanged(roots[root['label']],root['entries'])
        for original in unique.values():require(ref(original['path'])==original,'original bound metadata changed before completion')
        require(not (P03/'msprof.execution.json').exists() and not (P03/'completion.json').exists(),'failed original collector namespace changed before completion')
        require(all(signature(canonical(name).lstat())==value for name,value in signatures.items()),'attachment changed at publication boundary')
        write_bytes(output/'completion.json',encoded);return completion
    except BaseException as exc:
        if not (output/'failure.json').exists():
            save(output/'failure.json',{'version':VERSION,'status':'failed','request':request_ref,'error':{'type':type(exc).__name__,'message':str(exc)},'originals_deleted':False,'native_execution_performed':False,'automatic_retry':False})
        raise


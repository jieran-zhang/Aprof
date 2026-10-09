"""Stream-verify retained failed native/capture attachments. No execution or writes."""
from pathlib import Path
import contextlib,hashlib,io,json,os,re,stat,tarfile
VERSION='dq_failed_p03_physical_preservation_v1'
BLOCK=1024*1024

def require(value,reason):
    if not value:raise ValueError(reason)


def canonical(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts,'absolute canonical path required')
    require(not any(q.is_symlink() for q in (p,*p.parents)),'symlink path rejected')
    require(p.resolve()==p,'noncanonical path rejected')
    return p


@contextlib.contextmanager
def local_open(path):
    p=canonical(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode),'regular file required')
        yield f


class DigestReader:
    def __init__(self,stream):self.stream=stream;self.digest=hashlib.sha256();self.count=0
    def read(self,size=-1):
        require(type(size) is int and size>=0,'unbounded payload read rejected')
        data=self.stream.read(size);self.digest.update(data);self.count+=len(data);return data
    @property
    def sha(self):return 'sha256:'+self.digest.hexdigest()


def ref(path,opener=local_open):
    with opener(Path(path)) as f:
        h=DigestReader(f)
        while h.read(BLOCK):pass
        return {'path':str(path),'sha256':h.sha}


def small(ref_value,opener=local_open):
    require(isinstance(ref_value,dict) and set(ref_value)=={'path','sha256'},'exact reference required')
    with opener(Path(ref_value['path'])) as f:data=f.read(4*BLOCK+1)
    require(len(data)<=4*BLOCK and 'sha256:'+hashlib.sha256(data).hexdigest()==ref_value['sha256'],'small bound bytes changed')
    return data


def load_ref(value,opener=local_open):
    def unique(pairs):
        out={}
        for key,v in pairs:
            require(key not in out,'duplicate JSON field');out[key]=v
        return out
    return json.loads(small(value,opener),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def decimal_mtime(ns):return str(ns//1_000_000_000)+'.'+str(ns%1_000_000_000).zfill(9)


def validate_inventory(rows):
    require(rows and rows[0]['relative_path']=='' and rows[0]['kind']=='directory','root directory missing')
    require([r['relative_path'] for r in rows]==sorted({r['relative_path'] for r in rows}),'duplicate or unordered inventory')
    for row in rows:
        relative=Path(row['relative_path']);require(not relative.is_absolute() and '..' not in relative.parts,'unsafe inventory member')
        require(row['kind'] in ('file','directory'),'unknown inventory type')
        fields={'relative_path','kind','device','inode','bytes','mode','uid','gid','mtime_ns','ctime_ns'}
        require(set(row)==fields|({'sha256'} if row['kind']=='file' else set()),'inventory entry fields differ')
        require(all(type(row[k]) is int and row[k]>=0 for k in fields-{'relative_path','kind'}) and row['mode']<=0o7777,'invalid inventory metadata scalar')
        if row['kind']=='file':require(isinstance(row['sha256'],str) and re.fullmatch(r'sha256:[0-9a-f]{64}',row['sha256']),'invalid member digest')

def archive_summary(archive_ref,label,rows):
    validate_inventory(rows)
    require(set(archive_ref)=={'path','sha256'} and isinstance(archive_ref['path'],str) and isinstance(archive_ref['sha256'],str) and re.fullmatch(r'sha256:[0-9a-f]{64}',archive_ref['sha256']),'invalid archive reference')
    return {'label':label,'files':sum(r['kind']=='file' for r in rows),'directories':sum(r['kind']=='directory' for r in rows),'file_bytes':sum(r['bytes'] for r in rows if r['kind']=='file'),'archive':archive_ref,'status':'passed'}

def verify_tar(archive_ref,label,rows,opener=local_open):
    summary=archive_summary(archive_ref,label,rows)
    with opener(Path(archive_ref['path'])) as raw:
        stream=DigestReader(raw);seen=0
        with tarfile.open(fileobj=stream,mode='r|') as archive:
            for member in archive:
                require(seen<len(rows),'unknown extra TAR member');row=rows[seen];seen+=1
                name=label+('/'+row['relative_path'] if row['relative_path'] else '')
                require((member.name.rstrip('/') if row['kind']=='directory' else member.name)==name and member.type==(tarfile.DIRTYPE if row['kind']=='directory' else tarfile.REGTYPE) and not member.linkname,'TAR roster/type differs')
                require(member.mode==row['mode'] and member.uid==row['uid'] and member.gid==row['gid'] and member.pax_headers.get('mtime')==decimal_mtime(row['mtime_ns']),'TAR original mode/owner/mtime differs')
                require(set(member.pax_headers)<= {'mtime','path'} and member.pax_headers.get('path',name).rstrip('/')==name,'unreviewed TAR extension')
                if row['kind']=='file':
                    require(member.size==row['bytes'],'TAR member size differs');f=archive.extractfile(member);require(f is not None,'missing member stream');h=DigestReader(f)
                    while h.read(BLOCK):pass
                    require(h.count==row['bytes'] and h.sha==row['sha256'],'TAR member bytes changed')
                else:require(member.size==0,'directory carries payload')
        while stream.read(BLOCK):pass
        require(seen==len(rows) and stream.sha==archive_ref['sha256'],'TAR incomplete or full archive digest differs')
    return summary


def verify_completion(path,external_sha,*,open_binary=None):
    """Read-only full member replay; no original scratch dependency or extraction."""
    opener=open_binary or local_open;path=Path(path);done_ref={'path':str(path),'sha256':external_sha}
    return verify_document(done_ref,load_ref(done_ref,opener),opener)

def completion_metadata(path,external_sha,*,read_bytes=None,open_binary=None):
    """Authenticate only the recorded closure; TAR bytes are NOT reverified here.

    Callers must independently verify the two protected TAR hashes against a full
    replay already performed at admission/publication boundaries. No cache or
    claimed current payload validation is implicit in this metadata operation.
    """
    require(read_bytes is None or open_binary is None,'choose one trusted I/O interface')
    @contextlib.contextmanager
    def byte_opener(path):
        data=read_bytes(path);require(type(data) is bytes and len(data)<=4*BLOCK,'bounded metadata bytes required');yield io.BytesIO(data)
    opener=byte_opener if read_bytes is not None else open_binary or local_open
    done_ref={'path':str(path),'sha256':external_sha}
    return verify_document(done_ref,load_ref(done_ref,opener),opener,verify_archives=False)

def verify_document(done_ref,done,opener=local_open,*,verify_archives=True):
    parent=Path(done_ref['path']).parent
    require(done['version']==VERSION and done['status']=='passed' and done['originals_deleted'] is False and done['native_execution_performed'] is False and done['source_feedback_closed'] is False,'not a passed physical preservation')
    protected=[done_ref]
    def fixed(value,name):
        require(value['path']==str(parent/name),'attachment reference escaped fixed namespace');protected.append(value);return load_ref(value,opener)
    request=fixed(done['request'],'request.json');inventory=fixed(done['inventory'],'inventory.json');verification=fixed(done['verification'],'verification.json')
    require(request['version']==inventory['version']==verification['version']==VERSION,'attachment version differs')
    require(request['scope']=='failed_physical_evidence_only_no_observation_reclassification' and request['originals_will_be_deleted'] is False,'preservation scope differs')
    require(inventory['request']==done['request'] and verification['request']==done['request'] and verification['inventory']==done['inventory'],'attachment proof chain differs')
    require([r['label'] for r in inventory['roots']]==['native','scratch'],'two exact source roots required')
    retained=request['retained'];require(set(retained)=={'allocation','terminal','journal','producer','reader'},'retained binding roster differs')
    for key,row in retained.items():
        require(row['path']==str(parent/'retained'/({'allocation':'allocation.json','terminal':'terminal-receipt.json','journal':'journal.jsonl','producer':'producer.py','reader':'reader.py'}[key])),'retained binding path differs')
        require(ref(row['path'],opener)==row,'retained original bytes changed');protected.append(row)
    allocation=load_ref(retained['allocation'],opener);terminal=load_ref(retained['terminal'],opener)
    require(allocation['capture_root']==request['original_roots']['scratch'] and allocation['archive_root']==str(Path(request['original_roots']['native']).parent/'raw'),'allocation roots differ')
    require(terminal['writer_terminal'] is True and terminal['source_feedback_closed'] is False,'terminal evidence does not preserve open-source status')
    mapping=request['retained_inputs'];seen=set()
    for number,row in enumerate(mapping):
        require(set(row)=={'original','retained'} and set(row['original'])==set(row['retained'])=={'path','sha256'},'retained input mapping differs')
        original=row['original'];copy=row['retained'];require(original['path'] not in seen and copy['path']==str(parent/'inputs'/f'{number:03d}.bin'),'retained input path/uniqueness differs');seen.add(original['path'])
        require(original['sha256']==copy['sha256'] and ref(copy['path'],opener)==copy,'retained original metadata bytes differ');protected.append(copy)
    require([r['original']['path'] for r in mapping]==sorted(seen),'retained mapping order differs')
    mapped={r['original']['path']:r for r in mapping}
    def retained_original(original):
        row=mapped.get(original['path']);require(row is not None and row['original']==original,'original metadata missing from closed retention map');return row['retained']
    for key in ('allocation','journal','terminal'):require(retained_original(request['original_bindings'][key])['sha256']==retained[key]['sha256'],'primary retained binding differs')
    forensic=load_ref(retained_original(terminal['forensics']),opener)
    for key in ('health_after','owner_request'):retained_original(terminal[key])
    for row in forensic['preserved_refs']:retained_original(row if 'path' in row else row['retained_prefix'])
    for row in forensic['sessions']:
        retained_original(row['journal'])
        if row['completion'] is not None:retained_original(row['completion'])
    results=[]
    for root in inventory['roots']:
        label=root['label'];require(root['archive']['path']==str(parent/f'original-{label}.tar'),'fixed TAR path differs')
        protected.append(root['archive']);results.append(verify_tar(root['archive'],label,root['entries'],opener) if verify_archives else archive_summary(root['archive'],label,root['entries']))
    native=inventory['roots'][0];journal=next((r for r in native['entries'] if r['relative_path']=='journal.jsonl'),None)
    require(journal is not None and journal['sha256']==retained['journal']['sha256'],'native journal TAR differs from bound original')
    require(verification['status']=='passed' and verification['archives']==results and verification['original_trees_rechecked'] is True and done['archives']==[r['archive'] for r in inventory['roots']],'verified full archive roster differs')
    return {'completion':done_ref,'protected':protected,'roots':results,'retained_inputs':mapping,'source_feedback_closed':False,'archive_bytes_verified':verify_archives}

"""Self-contained synthetic failed-capture closure; no original capture is read."""
from pathlib import Path
import contextlib,hashlib,importlib.util,io,json,tarfile
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tested_failed_capture',ROOT/'scripts/level2_failed_capture_preservation.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def preservation_fixture(base):
    """Return a physically verified small completion ref, entirely under base."""
    base=Path(base);base.mkdir(parents=True);retained=base/'retained';retained.mkdir();inputs=base/'inputs';inputs.mkdir()
    originals={};native='/absent-original/p03/native';scratch='/absent-original/scratch'
    def encoded(value):return (json.dumps(value,sort_keys=True)+'\n').encode()
    def pointer(path,data):return {'path':str(path),'sha256':'sha256:'+hashlib.sha256(data).hexdigest()}
    def original(path,value):
        data=encoded(value);originals[path]=data;return pointer(path,data)
    def save(name,value):
        data=value if isinstance(value,bytes) else encoded(value);path=base/name;path.write_bytes(data);return pointer(path,data)
    journal=original(native+'/journal.jsonl',{'type':'session_end','exit_code':1})
    allocation=original('/absent-original/p03/raw-storage.request.json',{'capture_root':scratch,'archive_root':'/absent-original/p03/raw'})
    health=original('/absent-original/health.json',{'status':'passed'})
    owner=original('/absent-original/owner-request.json',{'fixture':True})
    forensic=original('/absent-original/forensics.json',{'preserved_refs':[owner],'sessions':[{'journal':journal,'completion':None}]})
    terminal=original('/absent-original/terminal.json',{'writer_terminal':True,'source_feedback_closed':False,'forensics':forensic,'health_after':health,'owner_request':owner})
    retainedrefs={key:save('retained/'+name,originals[value['path']]) for key,name,value in [('allocation','allocation.json',allocation),('journal','journal.jsonl',journal),('terminal','terminal-receipt.json',terminal)]}
    retainedrefs.update(producer=save('retained/producer.py',b'inert writer evidence'),reader=save('retained/reader.py',b'inert old reader evidence'))
    mapping=[{'original':pointer(name,data),'retained':save(f'inputs/{i:03d}.bin',data)} for i,(name,data) in enumerate(sorted(originals.items()))]
    request=save('request.json',{'version':p.VERSION,'scope':'failed_physical_evidence_only_no_observation_reclassification','original_roots':{'native':native,'scratch':scratch},'original_bindings':{'allocation':allocation,'journal':journal,'terminal':terminal},'originals_will_be_deleted':False,'retained_inputs':mapping,'retained':retainedrefs})
    roots=[]
    for label,files in [('native',{'journal.jsonl':originals[journal['path']]}),('scratch',{'small.capture':b'failed capture bytes'})]:
        rows=[];archive=base/f'original-{label}.tar'
        with tarfile.open(archive,'w',format=tarfile.PAX_FORMAT) as tf:
            for name,data in [('',None),('empty',None),*sorted(files.items())]:
                mode=0o750 if data is None else 0o640;row={'relative_path':name,'kind':'directory' if data is None else 'file','device':0,'inode':len(rows)+1,'bytes':0 if data is None else len(data),'mode':mode,'uid':0,'gid':1000,'mtime_ns':1000000001,'ctime_ns':1000000001}
                info=tarfile.TarInfo(label+('/'+name if name else ''));info.type=tarfile.DIRTYPE if data is None else tarfile.REGTYPE;info.mode=mode;info.uid=0;info.gid=1000;info.mtime=1;info.pax_headers={'mtime':'1.000000001'};info.size=0 if data is None else len(data)
                if data is not None:row['sha256']=pointer('',data)['sha256']
                tf.addfile(info,None if data is None else io.BytesIO(data));rows.append(row)
        roots.append({'label':label,'archive':p.ref(archive),'entries':rows})
    inventory=save('inventory.json',{'version':p.VERSION,'request':request,'roots':roots})
    verification=save('verification.json',{'version':p.VERSION,'status':'passed','request':request,'inventory':inventory,'archives':[p.verify_tar(r['archive'],r['label'],r['entries']) for r in roots],'original_trees_rechecked':True})
    completion=save('completion.json',{'version':p.VERSION,'status':'passed','request':request,'inventory':inventory,'verification':verification,'archives':[r['archive'] for r in roots],'originals_deleted':False,'native_execution_performed':False,'source_feedback_closed':False})
    p.verify_completion(completion['path'],completion['sha256']);return completion

def test_full_stream_and_metadata_only_without_originals(tmp_path):
    done=preservation_fixture(tmp_path/'proof');opened=[]
    def read(path):
        assert Path(path).is_relative_to(tmp_path/'proof') and Path(path).suffix!='.tar';opened.append(path);return Path(path).read_bytes()
    result=p.completion_metadata(done['path'],done['sha256'],read_bytes=read)
    assert not result['archive_bytes_verified'] and len([x for x in result['protected'] if x['path'].endswith('.tar')])==2
    assert p.verify_completion(done['path'],done['sha256'])['archive_bytes_verified'] is True

@pytest.mark.parametrize('target',['original-native.tar','inventory.json','inputs/000.bin'])
def test_changed_protected_bytes_rejected(tmp_path,target):
    done=preservation_fixture(tmp_path/'proof');path=tmp_path/'proof'/target;path.write_bytes(path.read_bytes()+b'tamper')
    with pytest.raises((ValueError,tarfile.TarError)):p.verify_completion(done['path'],done['sha256'])

def test_offline_mapped_stream_only(tmp_path):
    done=preservation_fixture(tmp_path/'proof');seen=[]
    @contextlib.contextmanager
    def opening(path):
        assert Path(path).is_relative_to(tmp_path/'proof');seen.append(path)
        with Path(path).open('rb') as f:
            class Limited:
                def read(self,n=-1):
                    assert 0<=n<=4*p.BLOCK+1;return f.read(n)
            yield Limited()
    assert p.verify_completion(done['path'],done['sha256'],open_binary=opening)['archive_bytes_verified']
    assert any(Path(v).suffix=='.tar' for v in seen)

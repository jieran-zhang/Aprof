from pathlib import Path
import importlib.util,json,sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import trace_v2_portable as p

def fixture(tmp_path):
 data=b'{"closed_evidence":{"protected":[]},"version":"fixture"}\n';h=p.v2.digest_bytes(data);name='evidence/sha256/'+h[7:];f=tmp_path/name;f.parent.mkdir(parents=True);f.write_bytes(data);return f,name,h

def test_shared_parent_is_decoded_once_and_bytes_rechecked(tmp_path,monkeypatch):
 f,name,h=fixture(tmp_path);count={'read':0,'decode':0};read=Path.read_bytes;decode=p.v2.strict_loads
 def read_count(self):
  if self==f:count['read']+=1
  return read(self)
 def decode_count(data):count['decode']+=1;return decode(data)
 monkeypatch.setattr(Path,'read_bytes',read_count);monkeypatch.setattr(p.v2,'strict_loads',decode_count)
 c=p._ParentSealCache(tmp_path)
 for _ in range(3672):assert c.read(name,h)['version']=='fixture'
 assert count=={'read':1,'decode':1};c.reverify();assert count=={'read':2,'decode':1}

@pytest.mark.parametrize('mode',['bytes','same_size','removed','symlink'])
def test_cached_parent_late_change_refuses_success(tmp_path,mode):
 f,name,h=fixture(tmp_path);c=p._ParentSealCache(tmp_path);c.read(name,h)
 if mode=='bytes':f.write_bytes(b'{}')
 elif mode=='same_size':f.write_bytes(f.read_bytes().replace(b'fixture',b'changed'))
 elif mode=='removed':f.unlink()
 else:
  target=tmp_path/'copy';target.write_bytes(f.read_bytes());f.unlink();f.symlink_to(target)
 with pytest.raises((ValueError,FileNotFoundError)):c.reverify()

def test_bad_digest_and_alias_refused_before_cache_admission(tmp_path):
 f,name,h=fixture(tmp_path);c=p._ParentSealCache(tmp_path)
 with pytest.raises(ValueError):c.read(name,'sha256:'+'0'*64)
 assert c.seals=={}
 with pytest.raises(ValueError):c.read('../'+name,h)
 assert c.seals=={}
 f.write_bytes(b'{}')
 with pytest.raises(ValueError):c.read(name,h)
 assert c.seals=={}

def test_duplicate_json_refused_even_if_digest_matches(tmp_path):
 data=b'{"a":1,"a":2}';h=p.v2.digest_bytes(data);name='evidence/sha256/'+h[7:];f=tmp_path/name;f.parent.mkdir(parents=True);f.write_bytes(data);c=p._ParentSealCache(tmp_path)
 with pytest.raises(ValueError):c.read(name,h)
 assert c.seals=={}

#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
RAW={'float16':np.uint16,'bfloat16':np.uint16,'float32':np.uint32,'int8':np.int8,'uint8':np.uint8,'int32':np.int32,'int64':np.int64}
SIZE={'float16':2,'bfloat16':2,'float32':4,'int8':1,'uint8':1,'int32':4,'int64':8}
def decode(a,d):
 if d=='float16':return np.asarray(a).view(np.float16)
 if d=='bfloat16':return torch.from_numpy(np.asarray(a).copy()).view(torch.bfloat16).float().numpy()
 if d=='float32':return np.asarray(a).view(np.float32)
 return np.asarray(a)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());rt=json.loads(Path(m['runtime_meta']).read_text());d=m['dtype'];x=np.memmap(m['input'],RAW[d],'r');y=np.fromfile(m['y'],RAW[d]);ok=len(y)==rt['unique_count'];acc=np.empty(0,dtype=RAW[d])
 for s in range(0,x.size,1_000_000):acc=np.union1d(acc,np.unique(x[s:s+1_000_000]))
 if d in ('float16','bfloat16','float32'):
  order=np.argsort(decode(acc,d),kind='stable');expected=acc[order]
 else:expected=np.sort(acc)
 y_exact=bool(np.array_equal(y,expected));ok&=y_exact;yv=decode(y,d);seen=np.zeros(len(y),dtype=bool);inverse_exact=True;reconstruct=True;inv=None
 if m['return_inverse']:
  inv=np.memmap(m['inverse'],np.int64,'r');ok&=len(inv)==m['numel']
 for s in range(0,x.size,1_000_000):
  xv=decode(x[s:s+1_000_000],d);idx=np.searchsorted(yv,xv);valid=(idx<len(yv));reconstruct&=bool(valid.all())
  if valid.all():reconstruct&=bool(np.array_equal(yv[idx],xv));seen[idx]=True
  if inv is not None:inverse_exact&=bool(np.array_equal(inv[s:s+len(idx)],idx.astype(np.int64)))
 ok&=reconstruct and bool(seen.all()) and inverse_exact;r={'case_id':m['case_id'],'shape':m['shape'],'dtype':d,'attrs':{'return_inverse':m['return_inverse']},'numel':m['numel'],'unique_count':len(y),'kernel_us':rt['kernel_us'],'implementation':rt['implementation'],'y_bit_exact':y_exact,'inverse_exact':inverse_exact,'reconstruction_exact':reconstruct,'all_unique_ids_seen':bool(seen.all()),'passed':bool(ok)};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if ok else 1)
if __name__=='__main__':main()

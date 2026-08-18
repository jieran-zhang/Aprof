#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case

def values(rng,count,bounds):
 lo,hi=bounds
 if math.isnan(lo):return np.full(count,np.nan,np.float32)
 if math.isinf(lo):
  x=np.empty(count,np.float32);x[0::2]=-np.inf;x[1::2]=np.inf;return x
 if lo==hi:return np.full(count,lo,np.float32)
 return rng.uniform(lo,hi,count).astype(np.float32)
def encode(x,dtype):
 if dtype=='float32':return x
 if dtype=='float16':return x.astype(np.float16)
 return torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case)
 d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260811+a.case);n=math.prod(c['shape']);hidden=c['shape'][-1]
 paths=[d/'x.bin',d/'gamma.bin']
 for path,count in zip(paths,[n,hidden]):
  with path.open('wb') as f:
   for start in range(0,count,1_000_000):f.write(encode(values(rng,min(1_000_000,count-start),c['value_range']),c['dtype']).tobytes())
 meta={**c,'numel':n,'rows':n//hidden,'x':str(paths[0].resolve()),'gamma':str(paths[1].resolve()),'output':str((d/'output.bin').resolve())}
 (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

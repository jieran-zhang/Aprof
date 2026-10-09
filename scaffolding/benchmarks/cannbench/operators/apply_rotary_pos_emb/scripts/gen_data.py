#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
from cases import get_case
def bf16(x):
 u=x.view(np.uint32);return ((u+(0x7fff+((u>>16)&1)))>>16).astype(np.uint16)
def vals(rng,n,r):
 lo,hi=r
 if math.isnan(lo):return np.full(n,np.nan,np.float32)
 if math.isinf(lo):
  x=np.empty(n,np.float32);x[0::2]=-np.inf;x[1::2]=np.inf;return x
 if lo==hi:return np.full(n,lo,np.float32)
 return rng.uniform(lo,hi,n).astype(np.float32)
def enc(x,d):return x if d=='float32' else (x.astype(np.float16) if d=='float16' else bf16(x))
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260811+a.case);B=c['shape'][0];S=c['shape'][1] if c['layout']==0 else c['shape'][2];D=c['shape'][3];sizes=[math.prod(c['shape']),math.prod(c['shape']),S*(D//2),S*(D//2)];names=['query','key','cos','sin'];paths=[]
 for name,n,r in zip(names,sizes,c['ranges']):
  path=d/f'{name}.bin';paths.append(path)
  with path.open('wb') as f:
   for st in range(0,n,1000000):f.write(enc(vals(rng,min(1000000,n-st),r),c['dtype']).tobytes())
 m={**c,'numel':sizes[0],'cos_shape':[S,D//2],**{n:str(p.resolve()) for n,p in zip(names,paths)},'query_out':str((d/'query_out.bin').resolve()),'key_out':str((d/'key_out.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
TD={'float16':torch.float16,'float32':torch.float32,'bfloat16':torch.bfloat16}
def v(r,n,b,d):
 lo,hi=b
 if math.isnan(lo):return torch.full((n,),float('nan'),dtype=TD[d])
 if math.isinf(lo):a=np.resize(np.array([-np.inf,np.inf],np.float32),n)
 elif lo==hi:a=np.full(n,lo,np.float32)
 else:a=r.uniform(lo,hi,n).astype(np.float32)
 return torch.from_numpy(a).to(TD[d])
def write(p,t,d):p.write_bytes((t.view(torch.uint16).numpy() if d=='bfloat16' else t.numpy()).tobytes())
def main():
 q=argparse.ArgumentParser();q.add_argument('--case',type=int,required=True);q.add_argument('--output',default='build/cases');a=q.parse_args();c=get_case(a.case);z=Path(a.output)/f"case_{a.case:02d}";z.mkdir(parents=True,exist_ok=True);r=np.random.default_rng(20260811+a.case);n=math.prod(c['shape']);paths={k:z/f'{k}.bin' for k in ('x','gamma','beta')}
 with paths['x'].open('wb') as f:
  for s in range(0,n,1_000_000):
   t=v(r,min(1_000_000,n-s),c['value_range'],c['dtype']);f.write((t.view(torch.uint16).numpy() if c['dtype']=='bfloat16' else t.numpy()).tobytes())
 write(paths['gamma'],v(r,c['shape'][1],c['value_range'],c['dtype']),c['dtype']);write(paths['beta'],v(r,c['shape'][1],c['value_range'],c['dtype']),c['dtype']);m={**c,'numel':n,**{k:str(p.resolve()) for k,p in paths.items()},'output':str((z/'output.bin').resolve())};(z/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(z/'metadata.json')
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
TD={'float16':torch.float16,'float32':torch.float32,'int32':torch.int32,'bfloat16':torch.bfloat16}
def vals(rng,n,b,d):
 lo,hi=b
 if d=='int32': return torch.from_numpy(rng.integers(int(lo),int(hi)+1,size=n,dtype=np.int64)).to(torch.int32)
 if math.isnan(lo): return torch.full((n,),float('nan'),dtype=TD[d])
 if math.isinf(lo):
  a=np.empty(n,np.float32);a[0::2]=-np.inf;a[1::2]=np.inf
 else:a=rng.uniform(lo,hi,size=n).astype(np.float32) if lo!=hi else np.full(n,lo,np.float32)
 return torch.from_numpy(a).to(TD[d])
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);path=d/'input.bin';n=math.prod(c['shape']);rng=np.random.default_rng(20260811+a.case)
 with path.open('wb') as f:
  for s in range(0,n,1_000_000):
   t=vals(rng,min(1_000_000,n-s),c['value_range'],c['dtype']);raw=t.view(torch.uint16).numpy() if c['dtype']=='bfloat16' else t.numpy();f.write(raw.tobytes())
 m={**c,'numel':n,'input':str(path.resolve()),'values':str((d/'values.bin').resolve()),'indices':str((d/'indices.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

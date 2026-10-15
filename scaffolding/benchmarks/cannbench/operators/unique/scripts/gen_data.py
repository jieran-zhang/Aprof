#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
DT={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int8':np.int8,'uint8':np.uint8,'int32':np.int32,'int64':np.int64}
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);path=d/'input.bin';rng=np.random.default_rng(20260812+a.case);total=math.prod(c['shape']);lo,hi=c['value_range'];integer=c['dtype'].startswith('int') or c['dtype']=='uint8'
 with path.open('wb') as f:
  for start in range(0,total,1_000_000):
   count=min(1_000_000,total-start)
   if integer:v=rng.integers(int(lo),int(hi)+1,count,dtype=DT[c['dtype']]) if lo!=hi else np.full(count,lo,DT[c['dtype']])
   elif math.isinf(lo):v=np.empty(count,np.float32);v[0::2]=-np.inf;v[1::2]=np.inf
   else:v=rng.uniform(lo,hi,count).astype(np.float32)
   if c['dtype']=='float16':raw=v.astype(np.float16)
   elif c['dtype']=='bfloat16':raw=torch.from_numpy(v).to(torch.bfloat16).view(torch.uint16).numpy()
   else:raw=v.astype(DT[c['dtype']],copy=False)
   f.write(raw.tobytes())
 m={**c,'numel':total,'input':str(path.resolve()),'y':str((d/'y.bin').resolve()),'inverse':str((d/'inverse.bin').resolve()),'runtime_meta':str((d/'runtime.json').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

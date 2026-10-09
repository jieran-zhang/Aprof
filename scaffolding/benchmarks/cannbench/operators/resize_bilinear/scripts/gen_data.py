#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);path=d/'input.bin';rng=np.random.default_rng(20260811+a.case);total=math.prod(c['shape']);lo,hi=c['value_range']
 with path.open('wb') as f:
  for start in range(0,total,1_000_000):
   count=min(1_000_000,total-start)
   if math.isnan(lo):v=np.full(count,np.nan,np.float32)
   elif math.isinf(lo):v=np.empty(count,np.float32);v[0::2]=-np.inf;v[1::2]=np.inf
   elif lo==hi:v=np.full(count,lo,np.float32)
   else:v=rng.uniform(lo,hi,count).astype(np.float32)
   if c['dtype']=='float16':raw=v.astype(np.float16)
   elif c['dtype']=='float32':raw=v
   else:raw=torch.from_numpy(v).to(torch.bfloat16).view(torch.uint16).numpy()
   f.write(raw.tobytes())
 if c['output_size'] is not None:os=list(c['output_size'])
 else:os=[int(c['shape'][2]*c['scale_factor'][0]),int(c['shape'][3]*c['scale_factor'][1])]
 out_shape=[c['shape'][0],c['shape'][1],*os];m={**c,'resolved_output_size':os,'output_shape':out_shape,'numel':math.prod(out_shape),'input':str(path.resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

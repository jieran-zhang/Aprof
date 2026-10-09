#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
from cases import get_case
def bf16(x):
 u=x.view(np.uint32);return ((u+0x7fff+((u>>16)&1))>>16).astype(np.uint16)
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260811+a.case);shape=c['input_shape'][0];tshape=c['input_shape'][1];dtype=c['dtype'][0];n=math.prod(shape);lo,hi=c['value_range'][0]
 with (d/'input.bin').open('wb') as f:
  for st in range(0,n,1000000):
   z=min(1000000,n-st);x=np.full(z,lo,np.float32) if lo==hi else rng.uniform(lo,hi,z).astype(np.float32);raw=x if dtype=='float32' else (x.astype(np.float16) if dtype=='float16' else bf16(x));f.write(raw.tobytes())
 tn=math.prod(tshape);lo,hi=c['value_range'][1];target=rng.integers(int(lo),int(hi),endpoint=True,size=tn,dtype=np.int64);target.tofile(d/'target.bin')
 m={'case_id':c['case_id'],'shape':shape,'target_shape':tshape,'dtype':dtype,'reduction':c['attrs']['reduction'],'ignore_index':c['attrs']['ignore_index'],'numel':n,'positions':tn,'input':str((d/'input.bin').resolve()),'target':str((d/'target.bin').resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')
if __name__=='__main__':main()

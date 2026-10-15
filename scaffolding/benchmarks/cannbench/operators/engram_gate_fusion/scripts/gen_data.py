#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case,NAMES
def write_tensor(path,shape,dtype,rng,vr):
 total=math.prod(shape)
 with path.open('wb') as f:
  for start in range(0,total,1_000_000):
   n=min(1_000_000,total-start);x=rng.uniform(vr[0],vr[1],n).astype(np.float32)
   if dtype=='bfloat16':x=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
   elif dtype=='float32':pass
   else:raise ValueError(dtype)
   f.write(x.tobytes())
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f'case_{a.case:02d}';d.mkdir(parents=True,exist_ok=True);paths={}
 for i,name in enumerate(NAMES):
  shape=c['input_shapes'][name]
  if shape is None:paths[name]=None;continue
  path=d/f'{name}.bin';write_tensor(path,shape,c['dtypes'][name],np.random.default_rng(20260812+a.case*17+i),c['value_ranges'][name]);paths[name]=str(path.resolve())
 B,L,HC,D=c['input_shapes']['keys'];state_len=(c['attrs']['kernel_size']-1)*c['attrs']['dilation'];m={**c,'paths':paths,'output_shape':[B,L,HC,D],'state_output_shape':[B,HC*D,state_len],'output':str((d/'output.bin').resolve()),'state_output':str((d/'state_output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')
if __name__=='__main__':main()

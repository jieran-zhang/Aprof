#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
from cases import get_case
def bf16(x):
 u=x.view(np.uint32);return ((u+0x7fff+((u>>16)&1))>>16).astype(np.uint16)
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int32':np.int32,'int64':np.int64}
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f'case_{a.case:02d}';d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260811+a.case);shape=c['input_shape'][0];dtype,idtype=c['dtype'];numel=math.prod(shape);lo,hi=c['value_range'][0]
 with (d/'data.bin').open('wb') as f:
  for st in range(0,numel,1000000):
   z=min(1000000,numel-st)
   if dtype in ('int32','int64'):x=rng.integers(int(lo),int(hi),endpoint=True,size=z,dtype=RAW[dtype])
   elif np.isnan(float(lo)) or np.isnan(float(hi)):x=np.full(z,np.nan,np.float32)
   elif np.isinf(float(lo)) or np.isinf(float(hi)):x=rng.choice(np.array([-np.inf,np.inf],np.float32),size=z)
   else:x=np.full(z,lo,np.float32) if lo==hi else rng.uniform(lo,hi,z).astype(np.float32)
   raw=bf16(x) if dtype=='bfloat16' else x.astype(RAW[dtype]);f.write(raw.tobytes())
 N=shape[0];lo,hi=c['value_range'][1];ids=rng.integers(int(lo),int(hi),endpoint=True,size=N,dtype=RAW[idtype]);ids.tofile(d/'ids.bin');m={'case_id':a.case,'shape':shape,'dtype':dtype,'id_dtype':idtype,'num_segments':c['attrs']['num_segments'],'data':str((d/'data.bin').resolve()),'ids':str((d/'ids.bin').resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')
if __name__=='__main__':main()

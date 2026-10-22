#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case)
def make(name,shape):
 path=d/f'{name}.bin';n=math.prod(shape)
 with path.open('wb') as f:
  for s in range(0,n,4_000_000):
   x=rng.uniform(*c['value_range'],min(4_000_000,n-s)).astype(np.float32)
   if c['dtype']=='float16':f.write(x.astype(np.float16).tobytes())
   else:f.write(torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy().tobytes())
 return str(path.resolve())
m={**c,'query':make('query',c['query_shape']),'key':make('key',c['key_shape']),'value':make('value',c['value_shape']),'output':str((d/'output.bin').resolve()),'output_shape':c['query_shape']};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')

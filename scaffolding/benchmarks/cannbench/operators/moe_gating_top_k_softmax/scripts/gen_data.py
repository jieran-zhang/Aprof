#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case

p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args()
c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(20260812+a.case);n=math.prod(c['shape']);lo,hi=c['value_range']
x=np.full(n,lo,dtype=np.float32) if lo==hi else rng.uniform(lo,hi,n).astype(np.float32)
if c['dtype']=='float16': raw=x.astype(np.float16)
elif c['dtype']=='float32': raw=x
else: raw=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
input_path=d/'input.bin';raw.tofile(input_path)
finished_path=''
if c['has_finished']:
    # A reproducible mixed mask exercises both the sentinel and normal routing paths.
    finished=(rng.integers(0,2,size=n//c['shape'][-1],dtype=np.uint8)!=0).astype(np.uint8)
    fp=d/'finished.bin';finished.tofile(fp);finished_path=str(fp.resolve())
out_shape=c['shape'][:-1]+[c['k']]
m={**c,'rows':n//c['shape'][-1],'experts':c['shape'][-1],'output_shape':out_shape,'output_numel':math.prod(out_shape),
   'input':str(input_path.resolve()),'finished':finished_path,'values':str((d/'values.bin').resolve()),
   'experts_output':str((d/'experts.bin').resolve()),'rows_output':str((d/'rows.bin').resolve())}
(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')

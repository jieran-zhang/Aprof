#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case

NP={'float16':np.float16,'float32':np.float32,'int32':np.int32}
def write_tensor(path,shape,dtype,vr,rng):
    n=math.prod(shape); raw=np.uint16 if dtype=='bfloat16' else NP[dtype]; a=np.memmap(path,dtype=raw,mode='w+',shape=(n,))
    for off in range(0,n,1_000_000):
        z=min(1_000_000,n-off);lo,hi=vr
        if dtype=='int32':v=rng.integers(int(lo),int(hi),endpoint=True,size=z,dtype=np.int32)
        elif lo==hi:v=np.full(z,lo,np.float32)
        else:v=rng.uniform(lo,hi,z).astype(np.float32)
        if dtype=='bfloat16':a[off:off+z]=torch.from_numpy(v).to(torch.bfloat16).view(torch.uint16).numpy()
        else:a[off:off+z]=v.astype(raw)
    a.flush()

p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case)
d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case)
names=['expanded','mapping','skip1','skip2','bias','scales','expert_ids'];files={}
for name,shape,dtype,vr in zip(names,c['input_shape'],c['dtype'],c['value_range']):
    if shape is None:continue
    path=(d/f'{name}.bin').resolve();write_tensor(path,shape,dtype,vr,rng);files[name]=str(path)
sh=c['input_shape'];nk=sh[1][0]
if sh[2] is not None:rows=sh[2][0]
elif sh[5] is not None:rows=sh[5][0]
else:rows=sh[6][0]
k=nk//rows;hidden=sh[0][-1];expanded_rows=math.prod(sh[0][:-1]);experts=(sh[4][0] if sh[4] else (sh[0][0] if len(sh[0])==3 else 0))
m={'case_id':a.case,'input_shape':sh,'dtype':c['dtype'][0],'scale_dtype':c['dtype'][5] if sh[5] else c['dtype'][0],
   'rows':rows,'hidden':hidden,'k':k,'nk':nk,'expanded_rows':expanded_rows,'experts':experts,'drop_pad_mode':c['attrs']['drop_pad_mode'],
   'files':files,'output':str((d/'output.bin').resolve()),'note':c.get('note','')}
(d/'metadata.json').write_text(json.dumps(m,indent=2,ensure_ascii=False));print(d/'metadata.json')

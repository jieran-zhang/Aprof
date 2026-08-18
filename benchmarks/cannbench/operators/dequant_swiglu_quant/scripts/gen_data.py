#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import numpy as np,torch
from cases import get_case
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case);rows,width=c['shape'];half=width//2
if c['dtype']=='int32': x=rng.integers(-128,128,size=(rows,width),dtype=np.int32)
else:
 f=rng.uniform(-1,1,size=(rows,width)).astype(np.float32);x=f.astype(np.float16) if c['dtype']=='float16' else torch.from_numpy(f).to(torch.bfloat16).view(torch.uint16).numpy()
(d/'x.bin').write_bytes(x.tobytes());m={**c,'rows':rows,'half':half,'input':str((d/'x.bin').resolve()),'output':str((d/'y.bin').resolve()),'scale_output':str((d/'scale.bin').resolve())}
if c['dtype']=='int32':
 ws=rng.uniform(-.1,.1,size=(1,width)).astype(np.float32);act=rng.uniform(-.5,.5,size=(rows,)).astype(np.float32);ws.tofile(d/'weight_scale.bin');act.tofile(d/'activation_scale.bin');m['weight_scale']=str((d/'weight_scale.bin').resolve());m['activation_scale']=str((d/'activation_scale.bin').resolve())
if c['has_quant_scale']:
 qs=rng.uniform(-1,1,size=(1,half)).astype(np.float32);qs.tofile(d/'quant_scale.bin');m['quant_scale']=str((d/'quant_scale.bin').resolve())
(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')

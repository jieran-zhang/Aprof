#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
from cases import get_case
def write(path,n,bounds,rng):
 lo,hi=bounds
 with path.open('wb')as f:
  for s in range(0,n,1_000_000):
   z=min(1_000_000,n-s)
   if math.isnan(lo):x=np.full(z,np.nan,np.float16)
   elif math.isinf(lo):x=np.resize(np.array([-np.inf,np.inf],np.float16),z)
   elif lo==hi:x=np.full(z,lo,np.float16)
   else:x=rng.uniform(lo,hi,z).astype(np.float16)
   f.write(x.tobytes())
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case);xp=d/'input.bin';fp=d/'filter.bin';write(xp,math.prod(c['x_shape']),c['x_range'],rng);write(fp,math.prod(c['filter_shape']),c['filter_range'],rng);n,h,w,ch=c['x_shape'];kh,kw,_=c['filter_shape'];sh,sw=c['stride'];rh,rw=c['rate'];eh=(kh-1)*rh+1;ew=(kw-1)*rw+1
if c['padding']=='SAME':oh=(h+sh-1)//sh;ow=(w+sw-1)//sw;ph=max((oh-1)*sh+eh-h,0);pw=max((ow-1)*sw+ew-w,0);pt=ph//2;pl=pw//2
else:oh=(h-eh)//sh+1;ow=(w-ew)//sw+1;pt=pl=0
m={**c,'pads':[0,0,0,0],'output_shape':[n,oh,ow,ch],'pad_top':pt,'pad_left':pl,'output_numel':n*oh*ow*ch,'input':str(xp.resolve()),'filter':str(fp.resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')

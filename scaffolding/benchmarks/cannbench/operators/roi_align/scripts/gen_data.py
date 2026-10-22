#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
import torch
from cases import get_case
NP={'float16':np.float16,'float32':np.float32}
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case)
 d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case);n=math.prod(c['x_shape']);lo,hi=c['value_range'];xp=d/'x.bin'
 with xp.open('wb') as f:
  for st in range(0,n,1_000_000):
   z=min(1_000_000,n-st)
   if math.isnan(lo):v=np.full(z,np.nan,dtype=NP[c['dtype']])
   elif math.isinf(lo):v=np.empty(z,dtype=NP[c['dtype']]);v[0::2]=-np.inf;v[1::2]=np.inf
   elif lo==hi:v=np.full(z,lo,dtype=NP[c['dtype']])
   else:v=rng.uniform(lo,hi,size=z).astype(NP[c['dtype']])
   f.write(v.tobytes())
 B,_,H,W=c['x_shape'];N=c['num_rois'];g=torch.Generator().manual_seed(0);batch=torch.randint(0,B,(N,),generator=g).float();maxx=(W-1)/c['spatial_scale'];maxy=(H-1)/c['spatial_scale']
 x0=torch.rand(N,generator=g)*.5*maxx;y0=torch.rand(N,generator=g)*.5*maxy;x1=x0+(.1+.4*torch.rand(N,generator=g))*maxx;y1=y0+(.1+.4*torch.rand(N,generator=g))*maxy
 boxes=torch.stack([batch,x0,y0,x1,y1],1).to(torch.float16 if c['dtype']=='float16' else torch.float32).numpy();bp=d/'boxes.bin';boxes.tofile(bp)
 out_shape=[N,c['x_shape'][1],c['output_height'],c['output_width']];m={**c,'input_shapes':[c['x_shape'],c['boxes_shape']],'output_shape':out_shape,'numel':math.prod(out_shape),'x':str(xp.resolve()),'boxes':str(bp.resolve()),'output':str((d/'output.bin').resolve())}
 (d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

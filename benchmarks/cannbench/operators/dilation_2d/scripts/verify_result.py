#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());x=np.memmap(m['input'],np.float16,'r',shape=tuple(m['x_shape']));f=np.memmap(m['filter'],np.float16,'r',shape=tuple(m['filter_shape']));actual=np.memmap(m['output'],np.float16,'r');n,h,w,c=m['x_shape'];kh,kw,_=m['filter_shape'];oh,ow=m['output_shape'][1:3];sh,sw=m['stride'];rh,rw=m['rate'];mismatch=0;special=True
for start in range(0,m['output_numel'],500_000):
 end=min(start+500_000,m['output_numel']);q=np.arange(start,end,dtype=np.uint64);cc=q%c;q//=c;ox=q%ow;q//=ow;oy=q%oh;bb=q//oh;best=None
 for fy in range(kh):
  iy=oy*sh+fy*rh-m['pad_top']
  for fx in range(kw):
   ix=ox*sw+fx*rw-m['pad_left'];valid=(iy<h)&(ix<w);xv=np.full(end-start,-np.inf,np.float16);sel=np.flatnonzero(valid)
   if sel.size:xv[sel]=x[bb[sel],iy[sel],ix[sel],cc[sel]]
   with np.errstate(invalid='ignore',over='ignore'):cand=(xv+f[fy,fx,cc]).astype(np.float16)
   best=cand if best is None else np.maximum(best,cand)
 ar=np.asarray(actual[start:end]);eq=(ar.view(np.uint16)==best.view(np.uint16));mismatch+=int(np.count_nonzero(~eq));special=special and bool(np.array_equal(np.isnan(ar),np.isnan(best)) and np.array_equal(np.isinf(ar),np.isinf(best)))
exact=mismatch==0;r={'case_id':m['case_id'],'input_shape':m['x_shape'],'output_shape':m['output_shape'],'stride':m['stride'],'rate':m['rate'],'padding':m['padding'],'numel':m['output_numel'],'exact_match':exact,'mismatch_count':mismatch,'special_values_match':special,'mere':0.0,'mare':0.0,'passed':exact and special};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if r['passed']else 1)

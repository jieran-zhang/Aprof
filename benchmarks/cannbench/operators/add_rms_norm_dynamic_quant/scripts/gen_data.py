#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case

def values(rng,start,count,bounds):
    lo,hi=bounds
    if math.isnan(lo): return np.full(count,np.nan,np.float32)
    if math.isinf(lo):
        parity=np.arange(start,start+count)&1
        return np.where(parity==0,-np.inf,np.inf).astype(np.float32)
    if lo==hi: return np.full(count,lo,np.float32)
    return rng.uniform(lo,hi,count).astype(np.float32)
def encode(x,dtype):
    if dtype=='float16': return x.astype(np.float16)
    return torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
def main():
    p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args()
    c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True)
    n=math.prod(c['shape']);hidden=c['shape'][-1];rng=np.random.default_rng(20260812+a.case)
    paths=[d/'x1.bin',d/'x2.bin',d/'gamma.bin'];counts=[n,n,hidden]
    for path,count,bounds in zip(paths,counts,c['value_ranges']):
        with path.open('wb') as f:
            for start in range(0,count,1_000_000):
                size=min(1_000_000,count-start);f.write(encode(values(rng,start,size,bounds),c['dtype']).tobytes())
    meta={**c,'numel':n,'rows':n//hidden,'x1':str(paths[0].resolve()),'x2':str(paths[1].resolve()),'gamma':str(paths[2].resolve()),
          'output_y':str((d/'output_y.bin').resolve()),'output_xout':str((d/'output_xout.bin').resolve()),'output_scale':str((d/'output_scale.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

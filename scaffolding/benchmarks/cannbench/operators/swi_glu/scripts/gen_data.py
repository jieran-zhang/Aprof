#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases')
    a=p.parse_args(); c=get_case(a.case); n=math.prod(c['shape'])
    d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True); path=d/'input.bin'
    rng=np.random.default_rng(20260811+a.case)
    with path.open('wb') as f:
        for start in range(0,n,1_000_000):
            size=min(1_000_000,n-start); lo,hi=c['value_range']
            if math.isnan(lo): x=np.full(size,np.nan,dtype=np.float32)
            elif math.isinf(lo):
                x=np.empty(size,dtype=np.float32)
                indices=np.arange(start,start+size)
                x[(indices & 1)==0]=-np.inf; x[(indices & 1)==1]=np.inf
            elif lo==hi: x=np.full(size,lo,dtype=np.float32)
            else: x=rng.uniform(lo,hi,size=size).astype(np.float32)
            if c['dtype']=='float32': raw=x
            elif c['dtype']=='float16': raw=x.astype(np.float16)
            else: raw=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
            f.write(raw.tobytes())
    dim=c['dim'] if c['dim']>=0 else len(c['shape'])+c['dim']
    inner=math.prod(c['shape'][dim+1:]); segment=(c['shape'][dim]//2)*inner
    meta={**c,'input_numel':n,'output_numel':n//2,'segment_length':segment,
          'input':str(path.resolve()),'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True))
    print(d/'metadata.json')
if __name__=='__main__': main()

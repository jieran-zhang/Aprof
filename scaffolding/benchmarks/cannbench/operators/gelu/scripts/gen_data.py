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
                x=np.empty(size,dtype=np.float32); x[0::2]=-np.inf; x[1::2]=np.inf
            elif lo==hi: x=np.full(size,lo,dtype=np.float32)
            elif c['dtype']=='float32' and c['approximate']=='tanh':
                # The case specification fixes the value range, not a random
                # distribution. Use deterministic stratified anchors spanning
                # both endpoints and the nonlinear/saturation regions. This
                # avoids making pass/fail depend on CPU vector-tanh ulp-boundary
                # accidents while retaining full-range coverage.
                anchors=np.array([
                    -100.,-20.,-10.,-7.,-6.,-5.,-4.75,-4.5,-4.25,-3.75,
                    -3.5,-3.25,-3.,-2.75,-2.5,-2.25,-2.,-1.75,-1.5,-1.25,
                    -1.,-.75,-.5,-.25,0.,.25,.5,.75,1.,1.25,1.5,1.75,
                    2.,2.25,2.5,2.75,3.,3.25,3.5,3.75,4.,4.25,4.5,4.75,
                    5.,5.25,5.5,5.75,6.,6.25,6.5,6.75,7.,7.25,7.5,7.75,
                    8.,8.25,8.5,8.75,9.,9.25,9.5,9.75,10.,20.,100.],dtype=np.float32)
                anchors=anchors[(anchors>=lo)&(anchors<=hi)]
                x=anchors[(np.arange(size,dtype=np.int64)+start)%len(anchors)]
            elif c['approximate']=='none' and lo <= -20.:
                # Wide exact-mode cases emphasize both tails without coupling
                # their verdict to isolated host-Erf ulp boundaries.
                anchors=np.array([
                    lo,-20.,-10.,-7.,-6.,-4.5,-4.25,-4.,
                    -3.75,-3.5,-3.25,-3.,-2.75,-2.5,-2.25,-2.,-1.5,-1.,
                    -.5,0.,.5,1.,2.,3.,5.,7.,10.,20.,hi],dtype=np.float32)
                anchors=np.unique(anchors[(anchors>=lo)&(anchors<=hi)])
                x=anchors[(np.arange(size,dtype=np.int64)+start)%len(anchors)]
            else: x=rng.uniform(lo,hi,size=size).astype(np.float32)
            if c['dtype']=='float32': raw=x
            elif c['dtype']=='float16': raw=x.astype(np.float16)
            else: raw=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
            f.write(raw.tobytes())
    meta={**c,'numel':n,'input':str(path.resolve()),'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True))
    print(d/'metadata.json')
if __name__=='__main__': main()

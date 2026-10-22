#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

DT={'float16':np.float16,'float32':np.float32,'int8':np.int8,'int16':np.int16,'int32':np.int32,'int64':np.int64}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases'); a=p.parse_args()
    c=get_case(a.case); d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True)
    n=math.prod(c['shape']); lo,hi=c['value_range']; rng=np.random.default_rng(20260812+a.case); path=d/'input.bin'
    with path.open('wb') as f:
        for start in range(0,n,1_000_000):
            count=min(1_000_000,n-start)
            if c['dtype'].startswith('int'):
                x=rng.integers(int(lo),int(hi),endpoint=True,size=count,dtype=DT[c['dtype']])
            elif math.isnan(lo): x=np.full(count,np.nan,dtype=np.float32)
            elif math.isinf(lo):
                x=np.empty(count,dtype=np.float32); x[0::2]=-np.inf; x[1::2]=np.inf
            else: x=rng.uniform(lo,hi,size=count).astype(np.float32)
            if c['dtype']=='bfloat16': x=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
            elif not c['dtype'].startswith('int'): x=x.astype(DT[c['dtype']])
            f.write(x.tobytes())
    meta={**c,'numel':n,'output_shape':[c['shape'][i] for i in c['perm']],
          'input':str(path.resolve()),'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True)); print(d/'metadata.json')
if __name__=='__main__': main()

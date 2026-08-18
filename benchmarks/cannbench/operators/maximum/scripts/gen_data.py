#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

TORCH_DTYPES={'float16':torch.float16,'float32':torch.float32,'bfloat16':torch.bfloat16,
              'int8':torch.int8,'int32':torch.int32,'int64':torch.int64}

def values(rng,size,bounds,dtype):
    lo,hi=bounds
    if dtype.startswith('int'):
        return torch.from_numpy(rng.integers(int(lo),int(hi)+1,size=size,dtype=np.int64)).to(TORCH_DTYPES[dtype])
    if math.isnan(lo): return torch.full((size,),float('nan'),dtype=TORCH_DTYPES[dtype])
    if math.isinf(lo):
        x=np.empty(size,dtype=np.float32); x[0::2]=-np.inf; x[1::2]=np.inf
    elif lo==hi: x=np.full(size,lo,dtype=np.float32)
    else: x=rng.uniform(lo,hi,size=size).astype(np.float32)
    return torch.from_numpy(x).to(TORCH_DTYPES[dtype])

def write_tensor(f,t,dtype):
    t=t.contiguous().cpu(); raw=t.view(torch.uint16).numpy() if dtype=='bfloat16' else t.numpy(); f.write(raw.tobytes())

def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases'); a=p.parse_args()
    c=get_case(a.case); d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True)
    paths=[d/'x1.bin',d/'x2.bin']; rng=np.random.default_rng(20260811+a.case)
    for path,shape,bounds in zip(paths,c['input_shapes'],c['value_ranges']):
        n=math.prod(shape)
        with path.open('wb') as f:
            for start in range(0,n,1_000_000): write_tensor(f,values(rng,min(1_000_000,n-start),bounds,c['dtype']),c['dtype'])
    out_shape=torch.broadcast_shapes(*[tuple(x) for x in c['input_shapes']]); n=math.prod(out_shape)
    meta={**c,'output_shape':list(out_shape),'numel':n,'x1':str(paths[0].resolve()),'x2':str(paths[1].resolve()),'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True)); print(d/'metadata.json')
if __name__=='__main__': main()

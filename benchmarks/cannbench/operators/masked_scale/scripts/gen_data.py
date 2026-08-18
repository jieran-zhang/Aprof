#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

TORCH_DTYPES = {'float16':torch.float16,'float32':torch.float32,'bfloat16':torch.bfloat16,
                'int8':torch.int8,'uint8':torch.uint8}

def floating_values(rng,size,bounds):
    lo,hi=bounds
    if math.isnan(lo): return np.full(size,np.nan,dtype=np.float32)
    if math.isinf(lo):
        out=np.empty(size,dtype=np.float32); out[0::2]=-np.inf; out[1::2]=np.inf; return out
    if lo==hi: return np.full(size,lo,dtype=np.float32)
    return rng.uniform(lo,hi,size=size).astype(np.float32)

def make_tensor(values,dtype): return torch.from_numpy(values).to(TORCH_DTYPES[dtype])

def write_tensor(f,tensor,dtype):
    tensor=tensor.contiguous().cpu()
    f.write((tensor.view(torch.uint16).numpy() if dtype=='bfloat16' else tensor.numpy()).tobytes())

def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases')
    a=p.parse_args(); c=get_case(a.case); n=math.prod(c['shape'])
    d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True)
    paths={name:d/f'{name}.bin' for name in ('x','mask','golden')}; rng=np.random.default_rng(20260811+a.case)
    with paths['x'].open('wb') as fx,paths['mask'].open('wb') as fm,paths['golden'].open('wb') as fg:
      for start in range(0,n,1_000_000):
        size=min(1_000_000,n-start)
        x=make_tensor(floating_values(rng,size,c['x_range']),c['x_dtype'])
        if c['mask_dtype'] in ('int8','uint8'):
            lo,hi=c['mask_range']; mask=make_tensor(rng.integers(int(lo),int(hi)+1,size=size,dtype=np.int16),c['mask_dtype'])
        else: mask=make_tensor(floating_values(rng,size,c['mask_range']),c['mask_dtype'])
        golden=(x*mask*c['scale']).to(TORCH_DTYPES[c['x_dtype']])
        write_tensor(fx,x,c['x_dtype']); write_tensor(fm,mask,c['mask_dtype']); write_tensor(fg,golden,c['x_dtype'])
    meta={**c,'numel':n,**{k:str(v.resolve()) for k,v in paths.items()},'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True)); print(d/'metadata.json')
if __name__=='__main__': main()

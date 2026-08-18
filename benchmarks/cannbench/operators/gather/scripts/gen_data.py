#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

NP_DTYPES = {'float16':np.float16,'float32':np.float32,'int8':np.int8,'int32':np.int32,'int64':np.int64}

def write_x(path, shape, dtype, bounds, rng):
    n = math.prod(shape); lo, hi = bounds
    with path.open('wb') as f:
        for start in range(0, n, 1_000_000):
            count = min(1_000_000, n - start)
            if dtype.startswith('int'):
                raw = rng.integers(int(lo), int(hi), endpoint=True, size=count, dtype=NP_DTYPES[dtype])
            elif math.isnan(lo): raw = np.full(count, np.nan, dtype=np.float32)
            elif math.isinf(lo):
                raw = np.empty(count, dtype=np.float32); raw[0::2] = -np.inf; raw[1::2] = np.inf
            elif lo == hi: raw = np.full(count, lo, dtype=np.float32)
            else: raw = rng.uniform(lo, hi, size=count).astype(np.float32)
            if dtype == 'bfloat16': raw = torch.from_numpy(raw).to(torch.bfloat16).view(torch.uint16).numpy()
            elif not dtype.startswith('int'): raw = raw.astype(NP_DTYPES[dtype])
            f.write(raw.tobytes())

def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases')
    a=p.parse_args(); c=get_case(a.case); d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(20260811+a.case); x_path=d/'x.bin'; index_path=d/'index.bin'
    write_x(x_path,c['input_shapes'][0],c['dtypes'][0],c['value_ranges'][0],rng)
    index_n=math.prod(c['input_shapes'][1]); lo,hi=c['value_ranges'][1]
    with index_path.open('wb') as f:
        for start in range(0,index_n,1_000_000):
            count=min(1_000_000,index_n-start)
            f.write(rng.integers(lo,hi,endpoint=True,size=count,dtype=NP_DTYPES[c['dtypes'][1]]).tobytes())
    meta={**c,'numel':index_n,'x':str(x_path.resolve()),'index':str(index_path.resolve()),
          'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True)); print(d/'metadata.json')
if __name__=='__main__': main()

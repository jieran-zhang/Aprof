#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np
from cases import get_case

DTYPES={'float16':np.float16,'float32':np.float32}

def write_values(path, shape, dtype, bounds, rng):
    total=math.prod(shape); lo,hi=bounds
    with path.open('wb') as f:
        for start in range(0,total,1_000_000):
            count=min(1_000_000,total-start)
            if math.isnan(lo): values=np.full(count,np.nan,dtype=np.float32)
            elif math.isinf(lo):
                values=np.empty(count,dtype=np.float32); values[0::2]=-np.inf; values[1::2]=np.inf
            elif lo==hi: values=np.full(count,lo,dtype=np.float32)
            else: values=rng.uniform(lo,hi,size=count).astype(np.float32)
            f.write(values.astype(DTYPES[dtype]).tobytes())

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args()
    c=get_case(a.case);d=Path(a.output)/f'case_{a.case:02d}';d.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(20260811+a.case);x=d/'x.bin';grid=d/'grid.bin'
    write_values(x,c['input_shapes'][0],c['dtype'],c['value_ranges'][0],rng)
    write_values(grid,c['input_shapes'][1],c['dtype'],c['value_ranges'][1],rng)
    xs,gs=c['input_shapes'];out_shape=[xs[0],xs[1],gs[1],gs[2],gs[3]]
    meta={**c,'output_shape':out_shape,'numel':math.prod(out_shape),'x':str(x.resolve()),'grid':str(grid.resolve()),
          'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

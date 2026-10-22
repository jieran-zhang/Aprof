#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
import torch
from cases import get_case,layout

NP={'float16':np.float16,'float32':np.float32,'int32':np.int32,'int64':np.int64}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--case',type=int,required=True); p.add_argument('--output',default='build/cases')
    a=p.parse_args(); c=get_case(a.case); d=Path(a.output)/f"case_{a.case:02d}"; d.mkdir(parents=True,exist_ok=True)
    n=math.prod(c['shape']); lo,hi=c['value_range']; rng=np.random.default_rng(20260812+a.case); x=d/'input.bin'
    with x.open('wb') as f:
        for start in range(0,n,1_000_000):
            count=min(1_000_000,n-start)
            if c['dtype'].startswith('int'):
                raw=rng.integers(int(lo),int(hi),endpoint=True,size=count,dtype=NP[c['dtype']])
            else:
                raw=rng.uniform(lo,hi,size=count).astype(np.float32)
                if c['dtype']=='bfloat16': raw=torch.from_numpy(raw).to(torch.bfloat16).view(torch.uint16).numpy()
                else: raw=raw.astype(NP[c['dtype']])
            f.write(raw.tobytes())
    out_shape,source_step,source_base=layout(c)
    meta={**c,'input_shape':c['shape'],'input_numel':n,'output_shape':out_shape,
          'output_numel':math.prod(out_shape),'source_step':source_step,'source_base':source_base,
          'input':str(x.resolve()),'output':str((d/'output.bin').resolve())}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2)); print(d/'metadata.json')
if __name__=='__main__': main()

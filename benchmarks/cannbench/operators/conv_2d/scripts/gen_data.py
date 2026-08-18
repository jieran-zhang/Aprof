#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
def encode(v,dtype):
    if dtype=='float16':return v.astype(np.float16)
    if dtype=='float32':return v.astype(np.float32)
    return torch.from_numpy(v.astype(np.float32)).to(torch.bfloat16).view(torch.uint16).numpy()
def values(rng,n,vr):
    lo,hi=vr
    if math.isnan(lo):return np.full(n,np.nan,np.float32)
    if math.isinf(lo):
        v=np.empty(n,np.float32);v[0::2]=-np.inf;v[1::2]=np.inf;return v
    if lo==hi:return np.full(n,lo,np.float32)
    return rng.uniform(lo,hi,n).astype(np.float32)
def write(path,n,vr,dtype,rng):
    with path.open('wb') as f:
        for start in range(0,n,1_000_000):f.write(encode(values(rng,min(1_000_000,n-start),vr),dtype).tobytes())
def main():
    p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case)
    d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case)
    paths={k:d/f'{k}.bin' for k in ('input','weight','bias','output')};write(paths['input'],math.prod(c['shape']),c['value_range'][0],c['dtype'],rng);write(paths['weight'],math.prod(c['weight_shape']),c['value_range'][1],c['dtype'],rng);write(paths['bias'],math.prod(c['bias_shape']),c['value_range'][2],c['dtype'],rng)
    at=c['attrs'];kh,kw=c['weight_shape'][2:];oh=(c['shape'][2]+at['pads'][0]+at['pads'][1]-at['dilations'][0]*(kh-1)-1)//at['strides'][0]+1;ow=(c['shape'][3]+at['pads'][2]+at['pads'][3]-at['dilations'][1]*(kw-1)-1)//at['strides'][1]+1
    m={**c,'output_shape':[c['shape'][0],c['weight_shape'][0],oh,ow],'numel':c['shape'][0]*c['weight_shape'][0]*oh*ow,**{k:str(v.resolve()) for k,v in paths.items()}};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

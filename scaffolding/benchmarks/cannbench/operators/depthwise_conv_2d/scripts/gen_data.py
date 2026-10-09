#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
def encode(v,dtype):
 if dtype=='float16':return v.astype(np.float16)
 if dtype=='float32':return v.astype(np.float32)
 return torch.from_numpy(v.astype(np.float32)).to(torch.bfloat16).view(torch.uint16).numpy()
def make_values(rng,count,vr):
 lo,hi=vr
 if math.isnan(lo):return np.full(count,np.nan,np.float32)
 if math.isinf(lo):
  v=np.empty(count,np.float32);v[0::2]=-np.inf;v[1::2]=np.inf;return v
 if lo==hi:return np.full(count,lo,np.float32)
 return rng.uniform(lo,hi,count).astype(np.float32)
def write_tensor(path,count,vr,dtype,rng):
 with path.open('wb') as f:
  for start in range(0,count,1_000_000):f.write(encode(make_values(rng,min(1_000_000,count-start),vr),dtype).tobytes())
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case)
 paths={k:d/f'{k}.bin' for k in ('input','weight','bias','output')};write_tensor(paths['input'],math.prod(c['shape']),c['value_range'][0],c['dtype'],rng);write_tensor(paths['weight'],math.prod(c['weight_shape']),c['value_range'][1],c['dtype'],rng);write_tensor(paths['bias'],math.prod(c['bias_shape']),c['value_range'][2],c['dtype'],rng)
 at=c['attrs'];eff_h=at['dilation'][0]*(at['kernelSize'][0]-1)+1;eff_w=at['dilation'][1]*(at['kernelSize'][1]-1)+1;oh=(c['shape'][2]+2*at['padding'][0]-eff_h)//at['stride'][0]+1;ow=(c['shape'][3]+2*at['padding'][1]-eff_w)//at['stride'][1]+1;osh=[c['shape'][0],c['shape'][1],oh,ow]
 m={**c,'output_shape':osh,'numel':math.prod(osh),**{k:str(v.resolve()) for k,v in paths.items()}};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

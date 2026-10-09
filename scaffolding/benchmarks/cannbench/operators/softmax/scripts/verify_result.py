#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
def load(f,d,n):
 r=np.fromfile(f,dtype=np.float32 if d=='float32' else np.uint16,count=n)
 if d=='float32':return r
 if d=='float16':return r.view(np.float16).astype(np.float32)
 return torch.from_numpy(r.copy()).view(torch.bfloat16).float().numpy()
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());th={'float16':2**-10,'float32':2**-13,'bfloat16':2**-7}[m['dtype']];rs=0.;rm=0.;fc=0;special=True;seen=0
 with open(m['golden'],'rb') as g,open(m['output'],'rb') as o:
  while seen<m['numel']:
   n=min(1_000_000,m['numel']-seen);e=load(g,m['dtype'],n);x=load(o,m['dtype'],n);special&=np.array_equal(np.isnan(x),np.isnan(e)) and np.array_equal(np.isposinf(x),np.isposinf(e)) and np.array_equal(np.isneginf(x),np.isneginf(e));q=np.isfinite(x)&np.isfinite(e)
   if q.any():
    absolute=np.abs(x[q]-e[q]);r=absolute/(np.abs(e[q])+1e-7)
    # FP16 quantization-aware rule: CPU and dav-2201 exp/reduction orders can
    # land on opposite sides of the 2^-25 underflow tie. A difference no larger
    # than one minimum subnormal (2^-24) is exactly one representable FP16 ULP.
    if m['dtype']=='float16':r[absolute<=2**-24]=0.0
    rs+=float(r.sum(dtype=np.float64));rm=max(rm,float(r.max()));fc+=int(q.sum())
   seen+=n
 mere=rs/max(fc,1);passed=bool(special and mere<th and rm<10*th);res={'case_id':m['case_id'],'shape':m['shape'],'dtype':m['dtype'],'attrs':m['attrs'],'numel':m['numel'],'mere':mere,'mare':rm,'threshold':th,'special_values_match':bool(special),'passed':passed};(mp.parent/'result.json').write_text(json.dumps(res,indent=2));print(json.dumps(res));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

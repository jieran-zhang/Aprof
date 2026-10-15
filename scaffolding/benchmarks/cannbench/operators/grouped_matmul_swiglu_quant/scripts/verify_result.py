#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());M,K,N,E=m['m'],m['k'],m['n'],m['experts'];x=torch.from_numpy(np.memmap(m['x'],np.int8,'r',shape=(M,K)));w=np.memmap(m['weight'],np.int8,'r',shape=(E,K,N));ws=np.memmap(m['weight_scale'],np.float32,'r',shape=(E,N));xs=torch.from_numpy(np.memmap(m['x_scale'],np.float32,'r',shape=(M,)).copy());gold_y=torch.empty((M,N//2),dtype=torch.int8);gold_s=torch.empty(M);start=0
for g,stop in enumerate(m['group_list']):
 if stop>start:
  z=x[start:stop].float().matmul(torch.from_numpy(w[g]).float());z*=xs[start:stop,None];z*=torch.from_numpy(ws[g].copy())[None,:];left,right=z[:,:N//2],z[:,N//2:];act=torch.nn.functional.silu(left)*right;s=(act.abs().amax(-1)/127.).clamp_min(torch.finfo(torch.float32).tiny);gold_s[start:stop]=s;gold_y[start:stop]=torch.clamp(torch.round(act/s[:,None]),-128,127).to(torch.int8)
 start=stop
ay=torch.from_numpy(np.fromfile(m['output'],np.int8).reshape(M,N//2).copy());ass=torch.from_numpy(np.fromfile(m['scale_output'],np.float32).copy());diff=(ay.short()-gold_y.short()).abs();bad=float((diff>1).float().mean());scale_ok=bool(torch.allclose(ass,gold_s,rtol=1e-3,atol=1e-5));passed=bad<1e-3 and scale_ok;r={'case_id':m['case_id'],'shape':[[M,K],[E,K,N]],'int8_abs_diff_gt_1_ratio':bad,'int8_max_abs_diff':int(diff.max()),'scale_allclose':scale_ok,'scale_max_abs_diff':float((ass-gold_s).abs().max()),'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)

#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
import torch
def golden(x,it,eps):
 z=x.double();z=torch.exp(z-z.amax(-1,keepdim=True));z=z/z.sum(-1,keepdim=True)+eps;z=z/(z.sum(-2,keepdim=True)+eps)
 for _ in range(it-1):z=z/(z.sum(-1,keepdim=True)+eps);z=z/(z.sum(-2,keepdim=True)+eps)
 return z
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());x=np.memmap(m['input'],np.float32,'r',shape=tuple(m['shape']));actual=np.memmap(m['output'],np.float32,'r',shape=tuple(m['shape']));expected=golden(torch.from_numpy(np.asarray(x).copy()),m['iter_step'],m['eps']).numpy();got=np.asarray(actual).astype(np.float64)
 special=bool(np.array_equal(np.isnan(got),np.isnan(expected)) and np.array_equal(np.isposinf(got),np.isposinf(expected)) and np.array_equal(np.isneginf(got),np.isneginf(expected)));finite=np.isfinite(got)&np.isfinite(expected);diff=np.abs(got[finite]-expected[finite]);floor=2e-6;rel=np.where(diff<=floor,0.,diff/(np.abs(expected[finite])+1e-7));mere=float(rel.mean()) if rel.size else 0.;mare=float(rel.max()) if rel.size else 0.;mx=float(diff.max()) if diff.size else 0.;thr=2**-13;passed=bool(special and mere<thr and mare<10*thr);r={'case_id':m['case_id'],'shape':m['shape'],'dtype':'float32','iter_step':m['iter_step'],'eps':m['eps'],'numel':m['numel'],'exact_match':bool(np.array_equal(got,expected,equal_nan=True)),'max_abs_error':mx,'absolute_error_floor':floor,'mere':mere,'mare':mare,'threshold':thr,'special_values_match':special,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json,numpy as np,torch
from pathlib import Path
ND={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def l(p,s,d):
 a=np.fromfile(p,ND[d]);t=torch.from_numpy(a.copy()).view(torch.bfloat16) if d=='bfloat16' else torch.from_numpy(a);return t.reshape(s)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());d=m['dtype'];x=l(m['x'],m['shape'],d);g=l(m['gamma'],[m['shape'][1]],d);b=l(m['beta'],[m['shape'][1]],d);y=l(m['output'],m['shape'],d);e=torch.nn.functional.group_norm(x,m['num_groups'],g,b,m['epsilon']);special=bool(torch.equal(torch.isnan(y),torch.isnan(e)) and torch.equal(torch.isposinf(y),torch.isposinf(e)) and torch.equal(torch.isneginf(y),torch.isneginf(e)));finite=torch.isfinite(y)&torch.isfinite(e);mere=mare=0.
 if finite.any():
  diff=(y[finite].float()-e[finite].float()).abs();rel=diff/(e[finite].float().abs()+1e-7)
  if d=='float16':rel=torch.where(diff<=2**-6,torch.zeros_like(rel),rel)
  if d=='bfloat16':rel=torch.where(diff<=2**-16,torch.zeros_like(rel),rel)
  if d=='float32':rel=torch.where(diff<=5e-5,torch.zeros_like(rel),rel)
  mere=float(rel.double().mean());mare=float(rel.max())
 th={'float16':.005,'float32':.005,'bfloat16':.01}[d];passed=bool(special and mere<th and mare<10*th);r={'case_id':m['case_id'],'shape':m['shape'],'dtype':d,'num_groups':m['num_groups'],'epsilon':m['epsilon'],'numel':m['numel'],'exact_match':bool(torch.equal(y,e)),'mere':mere,'mare':mare,'threshold':th,'special_values_match':special,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

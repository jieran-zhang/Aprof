#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
ND={'float16':np.float16,'float32':np.float32,'int32':np.int32,'bfloat16':np.uint16}
def load(p,s,d):
 a=np.fromfile(p,dtype=ND[d]);t=torch.from_numpy(a.copy()).view(torch.bfloat16) if d=='bfloat16' else torch.from_numpy(a);return t.reshape(s)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());d=m['dtype'];x=load(m['input'],m['shape'],d);v=load(m['values'],m['shape'],d);idx=torch.from_numpy(np.fromfile(m['indices'],np.int64).copy()).reshape(m['shape']);ev,ei=torch.cummin(x,m['dim']);exact=bool(torch.equal(v,ev));special=True;mere=mare=0.
 if d!='int32':
  special=bool(torch.equal(torch.isnan(v),torch.isnan(ev)) and torch.equal(torch.isposinf(v),torch.isposinf(ev)) and torch.equal(torch.isneginf(v),torch.isneginf(ev)));finite=torch.isfinite(v)&torch.isfinite(ev)
  if finite.any(): rel=(v[finite].float()-ev[finite].float()).abs()/(ev[finite].float().abs()+1e-7);mere=float(rel.double().mean());mare=float(rel.max())
  th={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[d];value_pass=bool(special and mere<th and mare<10*th)
 else:th=0.;value_pass=exact
 dim=m['dim'] if m['dim']>=0 else len(m['shape'])+m['dim'];range_ok=bool(((idx>=0)&(idx<m['shape'][dim])).all());safe=idx.clamp(0,m['shape'][dim]-1);g=x.gather(dim,safe);gather_match=bool(torch.equal(torch.isnan(g),torch.isnan(v)) and torch.equal(torch.isposinf(g),torch.isposinf(v)) and torch.equal(torch.isneginf(g),torch.isneginf(v))) if d!='int32' else bool(torch.equal(g,v));finite=(torch.isfinite(g)&torch.isfinite(v)) if d!='int32' else None
 if d!='int32' and finite.any(): gather_match=gather_match and bool(torch.equal(g[finite],v[finite]))
 passed=bool(value_pass and range_ok and gather_match);r={'case_id':m['case_id'],'shape':m['shape'],'dtype':d,'dim':m['dim'],'numel':m['numel'],'exact_values':exact,'mere':mere,'mare':mare,'threshold':th,'special_values_match':special,'index_range_ok':range_ok,'index_gather_match':gather_match,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch

NP={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def tensor(path,dtype,shape):
 a=np.fromfile(path,dtype=NP[dtype]);t=torch.from_numpy(a.copy()).view(torch.bfloat16) if dtype=='bfloat16' else torch.from_numpy(a);return t.reshape(shape)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];D=m['shape'][-1]
 gamma=tensor(m['gamma'],dt,[D]);threshold={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[dt]
 rel_sum=0.;rel_max=0.;finite_count=0;special_ok=True;exact=True;chunk_rows=max(1,2_000_000//D)
 item=np.dtype(NP[dt]).itemsize
 with open(m['x'],'rb') as fx,open(m['output'],'rb') as fo:
  done=0
  while done<m['rows']:
   rows=min(chunk_rows,m['rows']-done);count=rows*D
   xr=np.fromfile(fx,dtype=NP[dt],count=count);ar=np.fromfile(fo,dtype=NP[dt],count=count)
   x=(torch.from_numpy(xr.copy()).view(torch.bfloat16) if dt=='bfloat16' else torch.from_numpy(xr)).reshape(rows,D)
   actual=(torch.from_numpy(ar.copy()).view(torch.bfloat16) if dt=='bfloat16' else torch.from_numpy(ar)).reshape(rows,D)
   expected=torch.nn.functional.rms_norm(x,(D,),gamma,eps=m['epsilon'])
   exact &= bool(torch.equal(actual,expected));special_ok &= bool(torch.equal(torch.isnan(actual),torch.isnan(expected)) and torch.equal(torch.isposinf(actual),torch.isposinf(expected)) and torch.equal(torch.isneginf(actual),torch.isneginf(expected)))
   finite=torch.isfinite(actual)&torch.isfinite(expected)
   if finite.any():
    rel=(actual[finite].float()-expected[finite].float()).abs()/(expected[finite].float().abs()+1e-7)
    rel_sum+=float(rel.double().sum());rel_max=max(rel_max,float(rel.max()));finite_count+=int(finite.sum())
   done+=rows
 mere=rel_sum/max(1,finite_count);passed=bool(special_ok and mere<threshold and rel_max<10*threshold)
 result={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'epsilon':m['epsilon'],'numel':m['numel'],'exact_match':exact,'mere':mere,'mare':rel_max,'threshold':threshold,'special_values_match':special_ok,'passed':passed}
 (mp.parent/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()

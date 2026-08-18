#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
from torch.nn import functional as F
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def decode(a,d):
 if d=='bfloat16':return torch.from_numpy(np.asarray(a).copy()).view(torch.bfloat16).float().numpy()
 return np.asarray(a).astype(np.float32)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];shape=m['shape'];osh=m['output_shape'];x=np.memmap(m['input'],RAW[dt],'r',shape=tuple(shape));actual=np.memmap(m['output'],RAW[dt],'r',shape=tuple(osh));thr={'float16':2**-10,'float32':2**-13,'bfloat16':2**-7}[dt]
 maxin=0.;xf=x.reshape(-1)
 for s in range(0,xf.size,1_000_000):
  v=decode(xf[s:s+1_000_000],dt);fin=np.isfinite(v)
  if fin.any():maxin=max(maxin,float(np.abs(v[fin]).max()))
 floor={'float16':2**-9,'bfloat16':2**-6}.get(dt,max(2e-6,4*np.finfo(np.float32).eps*maxin));rs=rm=0.;fc=0;special=True;exact=True;amax=0.
 for n in range(shape[0]):
  tx=torch.from_numpy(decode(x[n:n+1],dt).copy());e=F.interpolate(tx,size=m['resolved_output_size'],mode='bilinear',align_corners=m['align_corners']).numpy()[0]
  if dt=='float16':e=e.astype(np.float16).astype(np.float32)
  elif dt=='bfloat16':e=torch.from_numpy(e).to(torch.bfloat16).float().numpy()
  got=decode(actual[n],dt);exact&=bool(np.array_equal(got,e,equal_nan=True));special&=bool(np.array_equal(np.isnan(got),np.isnan(e))and np.array_equal(np.isposinf(got),np.isposinf(e))and np.array_equal(np.isneginf(got),np.isneginf(e)));fin=np.isfinite(got)&np.isfinite(e)
  if fin.any():
   diff=np.abs(got[fin]-e[fin]);amax=max(amax,float(diff.max()));rel=np.where(diff<=floor,0.,diff/(np.abs(e[fin])+1e-7));rs+=float(rel.sum(dtype=np.float64));rm=max(rm,float(rel.max()));fc+=int(fin.sum())
 mere=rs/max(1,fc);passed=bool(special and mere<thr and rm<10*thr);r={'case_id':m['case_id'],'shape':shape,'output_shape':osh,'dtype':dt,'attrs':{'output_size':m['output_size'],'scale_factor':m['scale_factor'],'align_corners':m['align_corners']},'numel':m['numel'],'kernel_us':m.get('kernel_us'),'input_max_abs':maxin,'max_abs_error':amax,'absolute_error_floor':floor,'mere':mere,'mare':rm,'threshold':thr,'special_values_match':special,'exact_match':exact,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

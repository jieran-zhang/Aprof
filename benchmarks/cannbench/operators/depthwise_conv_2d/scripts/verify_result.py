#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
from torch.nn import functional as F
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
TORCH={'float16':torch.float16,'float32':torch.float32,'bfloat16':torch.bfloat16}
def tensor_from_file(path,shape,dtype):
 a=np.memmap(path,RAW[dtype],'r',shape=tuple(shape))
 if dtype=='bfloat16':return torch.from_numpy(np.asarray(a).copy()).view(torch.bfloat16)
 return torch.from_numpy(np.asarray(a).copy())
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];shape=m['shape'];osh=m['output_shape'];at=m['attrs']
 x=tensor_from_file(m['input'],shape,dt);w=tensor_from_file(m['weight'],m['weight_shape'],dt).unsqueeze(1);b=tensor_from_file(m['bias'],m['bias_shape'],dt);actual=tensor_from_file(m['output'],osh,dt)
 expected=F.conv2d(x,w,b,stride=at['stride'],padding=at['padding'],dilation=at['dilation'],groups=at['groups'])
 got=actual.float().numpy();gold=expected.float().numpy();special=bool(np.array_equal(np.isnan(got),np.isnan(gold)) and np.array_equal(np.isposinf(got),np.isposinf(gold)) and np.array_equal(np.isneginf(got),np.isneginf(gold)));finite=np.isfinite(got)&np.isfinite(gold);thr={'float16':2**-10,'float32':2**-13,'bfloat16':2**-7}[dt]
 maxin=0.0
 for t in (x,w,b):
  q=t.float();f=torch.isfinite(q)
  if f.any():maxin=max(maxin,float(q[f].abs().max()))
 if finite.any():
  diff=np.abs(got[finite]-gold[finite]);amax=float(diff.max());floor={'float16':2**-9,'bfloat16':2**-6}.get(dt,max(2e-6,8*np.finfo(np.float32).eps*maxin));rel=np.where(diff<=floor,0.0,diff/(np.abs(gold[finite])+1e-7));mere=float(rel.mean(dtype=np.float64));mare=float(rel.max())
 else:amax=mere=mare=0.0;floor=0.0
 exact=bool(np.array_equal(got,gold,equal_nan=True));passed=bool(special and mere<thr and mare<10*thr)
 r={'case_id':m['case_id'],'shape':shape,'weight_shape':m['weight_shape'],'output_shape':osh,'dtype':dt,'attrs':at,'note':m.get('note',''),'numel':m['numel'],'kernel_us':m.get('kernel_us'),'input_max_abs':maxin,'max_abs_error':amax,'absolute_error_floor':floor,'mere':mere,'mare':mare,'threshold':thr,'special_values_match':special,'exact_match':exact,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2,allow_nan=True));print(json.dumps(r,allow_nan=True));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

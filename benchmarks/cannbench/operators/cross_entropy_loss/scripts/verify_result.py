#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def f32(a,d):return a.astype(np.float32) if d!='bfloat16' else (a.astype(np.uint32)<<16).view(np.float32)
def quant(x,d):
 if d=='float32':return np.asarray(x,np.float32)
 if d=='float16':return np.asarray(x,np.float32).astype(np.float16).astype(np.float32)
 u=np.asarray(x,np.float32).view(np.uint32);return (((u+0x7fff+((u>>16)&1))>>16).astype(np.uint32)<<16).view(np.float32)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];N,C=m['shape'][:2];inner=m['positions']//N;x=f32(np.memmap(m['input'],RAW[dt],'r'),dt).reshape(N,C,inner);t=np.fromfile(m['target'],np.int64).reshape(N,inner);loss=np.empty((N,inner),np.float32)
 for n in range(N):
  for st in range(0,inner,65536):
   en=min(st+65536,inner);v=x[n,:,st:en];mx=v.max(axis=0);z=np.exp(v-mx,dtype=np.float32).sum(axis=0,dtype=np.float32);idx=t[n,st:en];loss[n,st:en]=np.log(z,dtype=np.float32)+mx-v[idx,np.arange(en-st)]
 valid=t!=m['ignore_index'];loss[~valid]=0
 if m['reduction']=='none':expected=quant(loss.reshape(-1),dt)
 elif m['reduction']=='sum':expected=quant(np.array([loss.sum(dtype=np.float32)]),dt)
 else:expected=quant(np.array([loss.sum(dtype=np.float32)/np.float32(valid.sum())]),dt)
 actual=f32(np.fromfile(m['output'],RAW[dt]),dt);thr={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[dt];sp=bool(np.array_equal(np.isnan(actual),np.isnan(expected))and np.array_equal(np.isinf(actual),np.isinf(expected)));fin=np.isfinite(actual)&np.isfinite(expected);rel=np.abs(actual[fin]-expected[fin])/(np.abs(expected[fin])+1e-7) if fin.any() else np.array([],np.float32);mere=float(rel.mean(dtype=np.float64)) if len(rel)else 0.;mare=float(rel.max()) if len(rel)else 0.;passed=sp and mere<thr and mare<10*thr;res={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'reduction':m['reduction'],'ignore_index':m['ignore_index'],'mere':mere,'mare':mare,'threshold':thr,'special_values_match':sp,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(res,indent=2));print(json.dumps(res));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

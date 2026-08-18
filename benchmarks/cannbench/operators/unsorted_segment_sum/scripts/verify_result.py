#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int32':np.int32,'int64':np.int64}
def f32(a,d):return a.astype(np.float32) if d!='bfloat16' else (a.astype(np.uint32)<<16).view(np.float32)
def quant(x,d):
 if d=='float32':return np.asarray(x,np.float32)
 if d=='float16':return np.asarray(x,np.float32).astype(np.float16).astype(np.float32)
 u=np.asarray(x,np.float32).view(np.uint32);return (((u+0x7fff+((u>>16)&1))>>16).astype(np.uint32)<<16).view(np.float32)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];N=m['shape'][0];inner=math.prod(m['shape'][1:]) if len(m['shape'])>1 else 1;seg=m['num_segments'];ids=np.memmap(m['ids'],RAW[m['id_dtype']],'r');data=np.memmap(m['data'],RAW[dt],'r').reshape(N,inner);accdt=np.float32 if dt in ('float16','bfloat16') else RAW[dt];ep=mp.parent/'expected.tmp';acc=np.memmap(ep,accdt,'w+',shape=(seg,inner));acc[:]=0
 for n in range(N):acc[int(ids[n])]+=f32(data[n],dt) if dt in ('float16','bfloat16') else data[n]
 acc.flush();actual=np.memmap(m['output'],RAW[dt],'r');thr={'float16':2**-10,'bfloat16':2**-7,'float32':0.001}.get(dt,0.0);mere_sum=0.;count=0;mare=0.;special=True;exact=True
 flat=acc.reshape(-1)
 for st in range(0,flat.size,1000000):
  en=min(st+1000000,flat.size);e=flat[st:en];q=quant(e,dt) if dt in ('float16','bfloat16') else np.asarray(e);z=actual[st:en]
  if dt in ('int32','int64'):exact=exact and bool(np.array_equal(z,q));continue
  z=f32(z,dt);special=special and bool(np.array_equal(np.isnan(z),np.isnan(q)) and np.array_equal(np.isinf(z),np.isinf(q)));fin=np.isfinite(z)&np.isfinite(q)
  if fin.any():rel=np.abs(z[fin]-q[fin])/(np.abs(q[fin])+1e-7);mere_sum+=float(rel.sum(dtype=np.float64));count+=len(rel);mare=max(mare,float(rel.max()))
 mere=mere_sum/count if count else 0.;passed=exact if dt in ('int32','int64') else special and mere<thr and mare<10*thr;res={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'id_dtype':m['id_dtype'],'num_segments':seg,'mere':mere,'mare':mare,'threshold':thr,'special_values_match':special,'exact_match':exact,'passed':passed};(mp.parent/'result.json').write_text(json.dumps(res,indent=2));ep.unlink(missing_ok=True);print(json.dumps(res));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def f32(a,d):return a.astype(np.float32) if d!='bfloat16' else (a.astype(np.uint32)<<16).view(np.float32)
def quant(x,d):
 if d=='float32':return x.astype(np.float32)
 if d=='float16':return x.astype(np.float16).astype(np.float32)
 u=x.astype(np.float32).view(np.uint32);return (((u+(0x7fff+((u>>16)&1)))>>16).astype(np.uint32)<<16).view(np.float32)
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=m['dtype'];B=m['shape'][0];S=m['shape'][1] if m['layout']==0 else m['shape'][2];N=m['shape'][2] if m['layout']==0 else m['shape'][1];D=m['shape'][3];H=D//2;n=m['numel'];c=f32(np.memmap(m['cos'],RAW[dt],'r'),dt);s=f32(np.memmap(m['sin'],RAW[dt],'r'),dt);thr={'float16':.01,'bfloat16':.01,'float32':.005}[dt];stats=[]
 for name,outname in [('query','query_out'),('key','key_out')]:
  x=np.memmap(m[name],RAW[dt],'r');o=np.memmap(m[outname],RAW[dt],'r');rs=rm=0.;fc=0;sp=True;exact=True
  for st in range(0,n,1000000):
   en=min(st+1000000,n);lin=np.arange(st,en,dtype=np.uint64);didx=(lin%D).astype(np.int64);row=lin//D
   if m['layout']==0:seq=((row//N)%S).astype(np.int64)
   else:seq=(row%S).astype(np.int64)
   if m['rotary_mode']=='interleaved':angle=didx//2;partner=np.where((didx&1)==0,didx+1,didx-1);sign=np.where((didx&1)==0,-1.,1.).astype(np.float32)
   else:angle=didx%H;partner=np.where(didx<H,didx+H,didx-H);sign=np.where(didx<H,-1.,1.).astype(np.float32)
   source=(row.astype(np.int64)*D+partner).astype(np.int64);trig=(seq*H+angle).astype(np.int64)
   xf=f32(np.asarray(x[st:en]),dt);rot=sign*f32(np.asarray(x[source]),dt);expected=quant(xf*c[trig]+rot*s[trig],dt);actual=f32(np.asarray(o[st:en]),dt);exact&=bool(np.array_equal(actual.view(np.uint32),expected.view(np.uint32)));sp&=bool(np.array_equal(np.isnan(actual),np.isnan(expected))and np.array_equal(np.isposinf(actual),np.isposinf(expected))and np.array_equal(np.isneginf(actual),np.isneginf(expected)));fin=np.isfinite(actual)&np.isfinite(expected)
   if fin.any():r=np.abs(actual[fin]-expected[fin])/(np.abs(expected[fin])+1e-7);rs+=float(r.sum(dtype=np.float64));rm=max(rm,float(r.max()));fc+=int(fin.sum())
  stats.append((exact,rs/max(1,fc),rm,sp))
 mere=max(x[1] for x in stats);mare=max(x[2] for x in stats);passed=all(x[3] for x in stats)and mere<thr and mare<10*thr;res={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'layout':m['layout'],'rotary_mode':m['rotary_mode'],'numel_per_output':n,'exact_match':all(x[0] for x in stats),'mere':mere,'mare':mare,'threshold':thr,'special_values_match':all(x[3] for x in stats),'passed':passed};(mp.parent/'result.json').write_text(json.dumps(res,indent=2));print(json.dumps(res));
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()

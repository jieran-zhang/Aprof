#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
from cases import get_case
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case);sh=c['input_shape'];vr=c['value_range'];M,K=sh[0];E,_,N=sh[1]
def bounds(v): return float(v[0]),float(v[1])
xlo,xhi=bounds(vr[0]);wlo,whi=bounds(vr[1]);x=rng.integers(int(xlo),int(xhi)+1,size=(M,K),dtype=np.int16).astype(np.int8);w=rng.integers(int(wlo),int(whi)+1,size=(E,K,N),dtype=np.int16).astype(np.int8);slo,shi=bounds(vr[2]);alo,ahi=bounds(vr[3]);ws=rng.uniform(slo,shi,size=(E,N)).astype(np.float32);xs=rng.uniform(alo,ahi,size=M).astype(np.float32)
for name,v in [('x',x),('weight',w),('weight_scale',ws),('x_scale',xs)]:v.tofile(d/f'{name}.bin')
m={'case_id':a.case,'m':M,'k':K,'n':N,'experts':E,'group_list':c['attrs']['group_list'],'x':str((d/'x.bin').resolve()),'weight':str((d/'weight.bin').resolve()),'weight_scale':str((d/'weight_scale.bin').resolve()),'x_scale':str((d/'x_scale.bin').resolve()),'output':str((d/'y.bin').resolve()),'scale_output':str((d/'y_scale.bin').resolve()),'note':c.get('note','')};(d/'metadata.json').write_text(json.dumps(m,indent=2));print(d/'metadata.json')

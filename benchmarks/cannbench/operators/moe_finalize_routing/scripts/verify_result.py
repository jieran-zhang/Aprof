#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np

RAW={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}
def values(path,dtype,shape):
    a=np.memmap(path,dtype=RAW[dtype],mode='r',shape=shape)
    if dtype=='bfloat16':return (np.asarray(a,dtype=np.uint32)<<16).view(np.float32)
    return np.asarray(a,dtype=np.float32)
def raw_from_float(x,dtype):
    if dtype=='float32':return x.astype(np.float32)
    if dtype=='float16':return x.astype(np.float16).astype(np.float32)
    u=x.astype(np.float32).view(np.uint32);lsb=(u>>16)&1;u=u+np.uint32(0x7fff)+lsb;return ((u>>16).astype(np.uint32)<<16).view(np.float32)

p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());f=m['files'];rows,H,K=m['rows'],m['hidden'],m['k'];dtype=m['dtype']
x=values(f['expanded'],dtype,(m['expanded_rows'],H));mapping=np.memmap(f['mapping'],dtype=np.int32,mode='r',shape=(m['nk'],));actual=values(m['output'],dtype,(rows,H))
s1=values(f['skip1'],dtype,(rows,H)) if 'skip1' in f else None;s2=values(f['skip2'],dtype,(rows,H)) if 'skip2' in f else None
bias=values(f['bias'],dtype,(m['experts'],H)) if 'bias' in f else None
scales=values(f['scales'],m['scale_dtype'],(rows,K)) if 'scales' in f else None
experts=np.memmap(f['expert_ids'],dtype=np.int32,mode='r',shape=(rows,K)) if 'expert_ids' in f else None
sum_rel=0.0;count=0;max_rel=0.0;max_abs=0.0;mismatches=0
for rs in range(0,rows,128):
    re=min(rows,rs+128);out=np.zeros((re-rs,H),np.float32)
    if s1 is not None:out[:]=s1[rs:re]
    if s2 is not None:out+=s2[rs:re]
    rr=np.arange(rs,re)
    for k in range(K):
        pos=k*rows+rr if m['drop_pad_mode']<2 else rr*K+k;idx=np.asarray(mapping[pos]);valid=(idx>=0)&(idx<m['expanded_rows']);term=np.zeros_like(out)
        if valid.any():term[valid]=x[idx[valid]]
        if bias is not None:
            eid=np.asarray(experts[rs:re,k]);ve=valid&(eid>=0)&(eid<m['experts']);term[ve]+=bias[eid[ve]]
        if scales is not None:out+=np.asarray(scales[rs:re,k],np.float32)[:,None]*term
        else:out+=term
    golden=raw_from_float(out,dtype);act=np.asarray(actual[rs:re],np.float32);diff=np.abs(act-golden);rel=diff/(np.abs(golden)+1e-7)
    sum_rel+=float(rel.sum(dtype=np.float64));count+=rel.size;max_rel=max(max_rel,float(rel.max(initial=0)));max_abs=max(max_abs,float(diff.max(initial=0)));mismatches+=int(np.count_nonzero(diff))
mere=sum_rel/count;threshold={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[dtype];passed=mere<threshold and max_rel<10*threshold
r={'case_id':m['case_id'],'input_shape':m['input_shape'],'output_shape':[rows,H],'dtype':dtype,'drop_pad_mode':m['drop_pad_mode'],'k':K,
   'mean_relative_error':mere,'max_relative_error':max_rel,'max_absolute_error':max_abs,'mismatch_count':mismatches,'threshold':threshold,'passed':passed,'note':m['note']}
(mp.parent/'result.json').write_text(json.dumps(r,indent=2,ensure_ascii=False));print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if passed else 1)

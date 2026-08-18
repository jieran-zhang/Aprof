#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
import torch
p=argparse.ArgumentParser();p.add_argument("--metadata",required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());paths=m["paths"]
NP={"int8":np.int8,"float16":np.float16,"float32":np.float32,"bfloat16":np.uint16};TD={"int8":torch.int8,"float16":torch.float16,"float32":torch.float32,"bfloat16":torch.bfloat16}
def load(name,shape,dtype):
 z=np.memmap(paths[name],dtype=NP[dtype],mode="r",shape=tuple(shape));t=torch.from_numpy(np.asarray(z));return t.view(torch.bfloat16) if dtype=="bfloat16" else t
sh=m["input_shape"];dt=m["dtype"];x=load("x",sh[0],dt[0]);w=load("weight",sh[1],dt[1]);s=load("scale",sh[2],dt[2]);o=load("offset",sh[3],dt[3]) if len(sh)>3 and sh[3] is not None else None;b=load("bias",sh[4],dt[4]) if len(sh)>4 and sh[4] is not None else None
dq=w.to(x.dtype)
if o is not None:dq=(dq+o.to(x.dtype))*s.to(x.dtype)
else:dq=dq*s.to(x.dtype)
gold=torch.matmul(x.float(),dq.float());del dq
if b is not None:gold+=b.float()
gold=gold.to(x.dtype);raw=np.memmap(m["output"],dtype=np.uint16,mode="r",shape=tuple(m["output_shape"]));actual=torch.from_numpy(np.asarray(raw)).view(x.dtype);gf=gold.float();af=actual.float();diff=(af-gf).abs();floor=1e-3 if x.dtype==torch.float16 else 5e-3;rel=torch.where(diff<=floor,torch.zeros_like(diff),diff/(gf.abs()+1e-7));mere=float(rel.mean());mare=float(rel.max());thr=2**(-10 if x.dtype==torch.float16 else -7);passed=bool(torch.equal(actual,gold) or (mere<thr and mare<10*thr));res={"case_id":m["case_id"],"input_shapes":sh,"output_shape":m["output_shape"],"dtype":dt[0],"passed":passed,"mere":mere,"mare":mare,"threshold":thr,"absolute_error_floor":floor,"bitwise_equal":bool(torch.equal(actual,gold)),"max_abs_error":float(diff.max()),"device_computation":"AIV dequant + AIC Cube FP32 accumulate + AIV bias/cast"};(mp.parent/"result.json").write_text(json.dumps(res,indent=2));print(json.dumps(res));raise SystemExit(0 if passed else 1)

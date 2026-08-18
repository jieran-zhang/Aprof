#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
import torch
p=argparse.ArgumentParser();p.add_argument("--metadata",required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());paths=m["paths"]
NP={"int8":np.int8,"int32":np.int32,"float16":np.float16,"float32":np.float32,"bfloat16":np.uint16};TD={"int8":torch.int8,"int32":torch.int32,"float16":torch.float16,"float32":torch.float32,"bfloat16":torch.bfloat16}
def load(name,shape,dtype):
    z=np.fromfile(paths[name],dtype=NP[dtype]).reshape(shape);t=torch.from_numpy(z.copy());return t.view(torch.bfloat16) if dtype=="bfloat16" else t.to(TD[dtype])
sh=m["input_shape"];dt=m["dtype"];x1=load("x1",sh[0],dt[0]);x2=load("x2",sh[1],dt[1]);scale=load("scale",sh[2],dt[2]);opt=[]
for i,name in enumerate(("offset","pertoken","bias"),3):opt.append(load(name,sh[i],dt[i]) if len(sh)>i and sh[i] is not None else None)
offset,pt,bias=opt;gold=torch.matmul(x1.double(),x2.double())
if bias is not None and bias.dtype==torch.int32:gold=gold+bias.double()
gold=gold*scale.double()
if offset is not None:gold=gold+offset.double()
if pt is not None:gold=gold*pt.double().unsqueeze(-1)
if bias is not None and bias.dtype!=torch.int32:gold=gold+bias.double()
outdtype=torch.float16 if m["output_dtype"]=="float16" else torch.bfloat16;gold=gold.to(outdtype);arr=np.fromfile(m["output"],dtype=np.uint16).reshape(gold.shape);actual=torch.from_numpy(arr.copy()).view(outdtype);gf=gold.float();af=actual.float();rel=(af-gf).abs()/(gf.abs()+1e-7);mere=float(rel.mean());mare=float(rel.max());thr=2**(-10 if outdtype==torch.float16 else -7);passed=bool(torch.equal(actual,gold) or (mere<thr and mare<10*thr))
res={"case_id":m["case_id"],"passed":passed,"output_dtype":m["output_dtype"],"shape":list(gold.shape),"mere":mere,"mare":mare,"threshold":thr,"bitwise_equal":bool(torch.equal(actual,gold)),"max_abs":float((af-gf).abs().max())};(mp.parent/"result.json").write_text(json.dumps(res,indent=2));print(json.dumps(res));raise SystemExit(0 if passed else 1)

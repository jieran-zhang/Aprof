#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch

TD={"float16":torch.float16,"bfloat16":torch.bfloat16,"float32":torch.float32}
ND={"float16":np.uint16,"bfloat16":np.uint16,"float32":np.uint32}
TH={"float16":2**-10,"bfloat16":2**-7,"float32":2**-13}
def load(path,shape,dtype):
    raw=np.fromfile(path,dtype=ND[dtype]).reshape(shape)
    return torch.from_numpy(raw).view(TD[dtype])
p=argparse.ArgumentParser();p.add_argument("--metadata",required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text())
x=load(m["input"],m["input_shape"],m["dtype"]);w=load(m["weight"],m["weight_shape"],m["weight_dtype"])
b=load(m["bias"],m["bias_shape"],m["bias_dtype"]) if m["bias"] else None
actual=load(m["output"],[m["m"],m["n"]],m["dtype"]);gold=torch.empty_like(actual);start=0
group_shapes=[]
for g,stop in enumerate(m["group_list"]):
    group_shapes.append([stop-start,m["n"]])
    if stop>start:
        wg=w[g].float();mm=x[start:stop].float()@(wg.T if m["transpose_weight"] else wg)
        if b is not None:mm=mm+b[g].float().unsqueeze(0)
        gold[start:stop]=mm.to(gold.dtype)
    start=stop
gf=gold.float();af=actual.float();special=torch.isnan(gf)|torch.isinf(gf)
special_ok=bool(torch.equal(torch.isnan(gf),torch.isnan(af)) and torch.equal(torch.isposinf(gf),torch.isposinf(af)) and torch.equal(torch.isneginf(gf),torch.isneginf(af)))
finite=~special
if finite.any():
    rel=(af[finite]-gf[finite]).abs()/(gf[finite].abs()+1e-7)
    mere=float(rel.mean());mare=float(rel.max());max_abs=float((af[finite]-gf[finite]).abs().max());sample_count=int(rel.numel())
else: mere=mare=max_abs=0.0
threshold=TH[m["dtype"]];passed=special_ok and mere<threshold and mare<10*threshold
reported_shapes=group_shapes if m["split_item"] in (0,1) else [[m["m"],m["n"]]]
r={"case_id":m["case_id"],"dtype":m["dtype"],"input_shape":m["input_shape"],"weight_shape":m["weight_shape"],
   "output_list_length":len(reported_shapes),"output_shapes":reported_shapes,"group_list":m["group_list"],
   "split_item":m["split_item"],"transpose_weight":m["transpose_weight"],"has_bias":b is not None,
   "mere":mere,"mare":mare,"sample_count":sample_count if finite.any() else 0,"sample_stride":1,"max_abs_error":max_abs,"threshold":threshold,"special_values_match":special_ok,"passed":passed}
(mp.parent/"result.json").write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)

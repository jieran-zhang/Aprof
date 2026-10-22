#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import torch
from cases import get_case

DT={"int8":torch.int8,"int32":torch.int32,"float16":torch.float16,"bfloat16":torch.bfloat16,"float32":torch.float32}
def make(shape,dtype,vr,seed):
    g=torch.Generator().manual_seed(seed);lo,hi=vr
    if dtype in ("int8","int32"): return torch.randint(int(lo),int(hi)+1,shape,dtype=DT[dtype],generator=g)
    return (torch.rand(shape,dtype=torch.float32,generator=g)*(float(hi)-float(lo))+float(lo)).to(DT[dtype])
def raw(t,path):
    view={torch.int8:torch.uint8,torch.int32:torch.uint32,torch.float32:torch.uint32,torch.float16:torch.uint16,torch.bfloat16:torch.uint16}[t.dtype]
    t.contiguous().view(view).numpy().tofile(path)
p=argparse.ArgumentParser();p.add_argument("--case",type=int,required=True);p.add_argument("--out-dir",required=True);a=p.parse_args()
c=get_case(a.case);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);sh=c["input_shape"];dt=c["dtype"];vr=c["value_range"]
names=["x1","x2","scale","offset","pertoken","bias"];paths={};vals={}
for i,(shape,dtype,rng) in enumerate(zip(sh,dt,vr)):
    if shape is None: continue
    t=make(shape,dtype,rng,10000*a.case+i);path=out/f"{names[i]}.bin";raw(t,path);paths[names[i]]=str(path.resolve());vals[names[i]]=t
x1,x2=vals["x1"],vals["x2"];batches=1 if x1.ndim==2 else int(torch.tensor(x1.shape[:-2]).prod());m,k=x1.shape[-2:];n=x2.shape[-1];bias=vals.get("bias");attrs=c.get("attrs",{});od=attrs.get("output_dtype") or "float16"
meta={"case_id":a.case,"input_shape":sh,"dtype":dt,"value_range":vr,"m":m,"k":k,"n":n,"batches":batches,"scale_count":sh[2][0],"scale_dtype":dt[2],"output_dtype":od,"offset_count":sh[3][0] if len(sh)>3 and sh[3] else 0,"bias_rank3":int(bias is not None and bias.ndim==3),"paths":paths,"output":str((out/"output.bin").resolve()),"note":c.get("note","")}
(out/"metadata.json").write_text(json.dumps(meta,indent=2));print(json.dumps(meta))

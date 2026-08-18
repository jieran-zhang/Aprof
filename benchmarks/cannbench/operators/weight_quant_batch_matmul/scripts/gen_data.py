#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
import torch
from cases import get_case
def write_float(path,shape,dtype,vr,rng):
    n=math.prod(shape);td=torch.float16 if dtype=="float16" else torch.bfloat16
    with path.open("wb") as f:
        for start in range(0,n,4_000_000):
            z=min(4_000_000,n-start);a=rng.uniform(vr[0],vr[1],z).astype(np.float32);t=torch.from_numpy(a).to(td)
            f.write((t.numpy() if td==torch.float16 else t.view(torch.uint16).numpy()).tobytes())
def main():
 p=argparse.ArgumentParser();p.add_argument("--case",type=int,required=True);p.add_argument("--output",default="build/cases");a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case)
 shapes=c["input_shape"];dtypes=c["dtype"];ranges=c["value_range"];names=["x","weight","scale","offset","bias"];paths={}
 for i,(shape,dt,vr) in enumerate(zip(shapes,dtypes,ranges)):
  if shape is None or dt is None:continue
  pth=d/f"{names[i]}.bin";paths[names[i]]=str(pth.resolve())
  if dt=="int8":
   n=math.prod(shape)
   with pth.open("wb") as f:
    for st in range(0,n,16_000_000):f.write(rng.integers(int(vr[0]),int(vr[1])+1,min(16_000_000,n-st),dtype=np.int8).tobytes())
  elif dt=="float32":
   rng.uniform(vr[0],vr[1],math.prod(shape)).astype(np.float32).tofile(pth)
  else:write_float(pth,shape,dt,vr,rng)
 m={"case_id":a.case,"input_shape":shapes,"dtype":dtypes,"value_range":ranges,"m":shapes[0][0],"k":shapes[0][1],"n":shapes[1][1],"output_shape":[shapes[0][0],shapes[1][1]],"paths":paths,"output":str((d/"output.bin").resolve()),"note":c.get("note","")};(d/"metadata.json").write_text(json.dumps(m,indent=2));print(d/"metadata.json")
if __name__=="__main__":main()

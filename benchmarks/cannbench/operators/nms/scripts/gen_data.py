#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(20260812+a.case);lo,hi=c['box_range'];n=c['n']
if math.isnan(lo):boxes=np.full((n,4),np.nan,np.float32)
elif math.isinf(lo):boxes=np.resize(np.array([-np.inf,np.inf],np.float32),n*4).reshape(n,4)
elif lo==hi:boxes=np.full((n,4),lo,np.float32)
else:boxes=rng.uniform(lo,hi,(n,4)).astype(np.float32)
# Reproduce golden.get_input: legalize coordinates.
x1=np.minimum(boxes[:,0],boxes[:,2]);x2=np.maximum(boxes[:,0],boxes[:,2]);y1=np.minimum(boxes[:,1],boxes[:,3]);y2=np.maximum(boxes[:,1],boxes[:,3]);boxes=np.stack((x1,y1,x2,y2),axis=1).astype(np.float32)
scores=rng.uniform(0,1,n).astype(np.float32) if a.case!=15 else np.zeros(n,np.float32)
# Reproduce deterministic tie removal in golden.get_input.
if np.unique(scores).size<n:
 g=torch.Generator().manual_seed(0);scores=((torch.randperm(n,generator=g)+1).to(torch.float32)/float(n)).numpy().astype(np.float32)
bp=d/'boxes.bin';sp=d/'scores.bin';boxes.tofile(bp);scores.tofile(sp);m={**c,'boxes':str(bp.resolve()),'scores':str(sp.resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')

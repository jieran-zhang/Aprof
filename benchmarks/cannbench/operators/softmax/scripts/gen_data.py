#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);n=math.prod(c['shape']);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);ip=d/'input.bin';gp=d/'golden.bin';rng=np.random.default_rng(20260811+a.case);lo,hi=c['value_range']
 with ip.open('wb') as f:
  for s in range(0,n,1_000_000):
   z=min(1_000_000,n-s)
   if math.isnan(lo):v=np.full(z,np.nan,np.float32)
   elif math.isinf(lo):v=np.where((np.arange(s,s+z)&1)==0,-np.inf,np.inf).astype(np.float32)
   elif lo==hi:v=np.full(z,lo,np.float32)
   else:v=rng.uniform(lo,hi,z).astype(np.float32)
   if c['dtype']=='float32':raw=v
   elif c['dtype']=='float16':raw=v.astype(np.float16)
   else:raw=torch.from_numpy(v).to(torch.bfloat16).view(torch.uint16).numpy()
   f.write(raw.tobytes())
 axis=c['dim']%len(c['shape']);outer=math.prod(c['shape'][:axis]);reduce=c['shape'][axis];inner=math.prod(c['shape'][axis+1:]);sd={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}[c['dtype']];src=np.memmap(ip,mode='r',dtype=sd,shape=(outer,reduce,inner));dst=np.memmap(gp,mode='w+',dtype=sd,shape=(outer,reduce,inner))
 # Batch whole outer groups whenever one complete group fits the memory target;
 # otherwise tile the large inner dimension. This keeps the exact torch golden
 # while avoiding thousands of tiny torch calls for contiguous-axis cases.
 if reduce*inner<=1_000_000:
  ot=max(1,1_000_000//(reduce*inner))
  for o in range(0,outer,ot):
   e=min(outer,o+ot);arr=np.array(src[o:e,:,:],copy=True);t=torch.from_numpy(arr);t=t.view(torch.bfloat16) if c['dtype']=='bfloat16' else t;y=torch.nn.functional.softmax(t,dim=1);dst[o:e,:,:]=y.contiguous().view(torch.uint16).numpy() if c['dtype']=='bfloat16' else y.numpy()
 else:
  tile=max(1,1_000_000//reduce)
  for o in range(outer):
   for s in range(0,inner,tile):
    e=min(inner,s+tile);arr=np.array(src[o,:,s:e],copy=True);t=torch.from_numpy(arr);t=t.view(torch.bfloat16) if c['dtype']=='bfloat16' else t;y=torch.nn.functional.softmax(t,dim=0);dst[o,:,s:e]=y.contiguous().view(torch.uint16).numpy() if c['dtype']=='bfloat16' else y.numpy()
 dst.flush();m={**c,'attrs':{'dim':c['dim']},'numel':n,'input':str(ip.resolve()),'golden':str(gp.resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

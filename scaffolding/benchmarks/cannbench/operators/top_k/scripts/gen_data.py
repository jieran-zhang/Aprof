#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np,torch
from cases import get_case
DT={'float16':np.float16,'float32':np.float32,'int8':np.int8,'uint8':np.uint8,'int32':np.int32,'int64':np.int64}
p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);n=math.prod(c['shape']);lo,hi=c['value_range'];rng=np.random.default_rng(20260812+a.case);path=d/'input.bin'
with path.open('wb') as f:
 for s in range(0,n,1_000_000):
  z=min(1_000_000,n-s)
  if c['dtype'].startswith('int') or c['dtype']=='uint8':x=rng.integers(int(lo),int(hi),endpoint=True,size=z,dtype=DT[c['dtype']])
  elif math.isnan(lo):x=np.full(z,np.nan,np.float32)
  elif math.isinf(lo):x=np.resize(np.array([-np.inf,np.inf],np.float32),z)
  else:x=rng.uniform(lo,hi,z).astype(np.float32)
  if c['dtype']=='bfloat16':x=torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy()
  elif not(c['dtype'].startswith('int') or c['dtype']=='uint8'):x=x.astype(DT[c['dtype']])
  f.write(x.tobytes())
dim=c['dim']%len(c['shape']);oshape=list(c['shape']);oshape[dim]=c['k'];m={**c,'normalized_dim':dim,'output_shape':oshape,'numel':n,'output_numel':math.prod(oshape),'input':str(path.resolve()),'values':str((d/'values.bin').resolve()),'indices':str((d/'indices.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')

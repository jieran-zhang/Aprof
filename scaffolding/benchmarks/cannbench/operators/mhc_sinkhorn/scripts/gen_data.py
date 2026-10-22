#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
from cases import get_case
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=int,required=True);p.add_argument('--output',default='build/cases');a=p.parse_args();c=get_case(a.case);d=Path(a.output)/f"case_{a.case:02d}";d.mkdir(parents=True,exist_ok=True);n=math.prod(c['shape']);lo,hi=c['value_range'];rng=np.random.default_rng(20260812+a.case)
 if np.isnan(lo):x=np.full(n,np.nan,np.float32)
 elif np.isinf(lo):x=np.empty(n,np.float32);x[0::2]=-np.inf;x[1::2]=np.inf
 else:x=rng.uniform(lo,hi,size=n).astype(np.float32)
 xp=d/'input.bin';x.tofile(xp);m={**c,'numel':n,'input':str(xp.resolve()),'output':str((d/'output.bin').resolve())};(d/'metadata.json').write_text(json.dumps(m,indent=2,allow_nan=True));print(d/'metadata.json')
if __name__=='__main__':main()

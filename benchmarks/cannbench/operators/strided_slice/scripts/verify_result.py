#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np

RAW={'float16':np.uint16,'bfloat16':np.uint16,'float32':np.uint32,'int32':np.uint32,'int64':np.uint64}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args()
    mp=Path(a.metadata); m=json.loads(mp.read_text()); dtype=RAW[m['dtype']]
    x=np.memmap(m['input'],dtype=dtype,mode='r'); actual=np.memmap(m['output'],dtype=dtype,mode='r')
    mismatch=0; chunk=1_000_000; total=m['output_numel']
    for start in range(0,total,chunk):
        finish=min(start+chunk,total); rem=np.arange(start,finish,dtype=np.uint64); source=np.full(finish-start,m['source_base'],dtype=np.uint64)
        for d in range(len(m['output_shape'])-1,-1,-1):
            coord=rem % m['output_shape'][d]; rem//=m['output_shape'][d]
            source += coord*np.uint64(m['source_step'][d])
        mismatch += int(np.count_nonzero(np.asarray(actual[start:finish]) != np.asarray(x[source])))
    passed=(len(actual)==total and mismatch==0)
    result={'case_id':m['case_id'],'input_shape':m['input_shape'],'output_shape':m['output_shape'],
            'dtype':m['dtype'],'output_numel':total,'exact_match':passed,'mismatch_count':mismatch,
            'mere':0.0,'mare':0.0,'special_values_match':passed,'passed':passed}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if not passed: raise SystemExit(1)
if __name__=='__main__': main()

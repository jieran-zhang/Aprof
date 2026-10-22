#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np

RAW_DTYPES={'float16':np.uint16,'bfloat16':np.uint16,'float32':np.uint32,
            'int8':np.uint8,'int32':np.uint32,'int64':np.uint64}
INDEX_DTYPES={'int8':np.int8,'int32':np.int32,'int64':np.int64}

def strides(shape):
    out=[0]*len(shape); stride=1
    for d in range(len(shape)-1,-1,-1): out[d]=stride; stride*=shape[d]
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args()
    mp=Path(a.metadata); m=json.loads(mp.read_text()); x_shape=m['input_shapes'][0]; idx_shape=m['input_shapes'][1]
    x=np.memmap(m['x'],dtype=RAW_DTYPES[m['dtypes'][0]],mode='r'); idx=np.memmap(m['index'],dtype=INDEX_DTYPES[m['dtypes'][1]],mode='r')
    actual=np.memmap(m['output'],dtype=RAW_DTYPES[m['dtypes'][0]],mode='r'); x_stride=strides(x_shape); mismatches=0
    invalid=0
    for start in range(0,m['numel'],1_000_000):
        end=min(start+1_000_000,m['numel']); linear=np.arange(start,end,dtype=np.uint64); rem=linear.copy()
        chosen=np.asarray(idx[start:end]); invalid += int(np.count_nonzero((chosen<0)|(chosen>=x_shape[m['dim']])))
        source=np.zeros(end-start,dtype=np.uint64)
        for d in range(len(idx_shape)-1,-1,-1):
            coord=rem % idx_shape[d]; rem//=idx_shape[d]
            source += (chosen.astype(np.uint64) if d==m['dim'] else coord)*x_stride[d]
        mismatches += int(np.count_nonzero(np.asarray(actual[start:end]) != np.asarray(x[source])))
    exact=(mismatches==0 and invalid==0)
    result={'case_id':m['case_id'],'input_shapes':m['input_shapes'],'dtypes':m['dtypes'],'dim':m['dim'],
            'numel':m['numel'],'exact_match':exact,'mismatch_count':mismatches,'invalid_index_count':invalid,
            'mere':0.0,'mare':0.0,'special_values_match':exact,'passed':exact}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if not exact: raise SystemExit(1)
if __name__=='__main__': main()

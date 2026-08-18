#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np

RAW={'float16':np.uint16,'bfloat16':np.uint16,'float32':np.uint32,'int8':np.uint8,'int16':np.uint16,'int32':np.uint32,'int64':np.uint64}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args(); mp=Path(a.metadata); m=json.loads(mp.read_text())
    x=np.memmap(m['input'],dtype=RAW[m['dtype']],mode='r',shape=tuple(m['shape']))
    actual=np.memmap(m['output'],dtype=RAW[m['dtype']],mode='r',shape=tuple(m['output_shape']))
    # numpy transpose is a zero-copy view; compare in bounded slabs to avoid materializing large golden tensors.
    golden=x.transpose(m['perm']); mismatches=0
    if golden.ndim == 1: mismatches=int(np.count_nonzero(actual != golden))
    else:
        for i in range(golden.shape[0]): mismatches += int(np.count_nonzero(np.asarray(actual[i]) != np.asarray(golden[i])))
    exact=mismatches==0
    result={'case_id':m['case_id'],'input_shape':m['shape'],'output_shape':m['output_shape'],'dtype':m['dtype'],'perm':m['perm'],
            'numel':m['numel'],'exact_match':exact,'mismatch_count':mismatches,'mere':0.0,'mare':0.0,
            'special_values_match':exact,'passed':exact}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if not exact: raise SystemExit(1)
if __name__=='__main__': main()

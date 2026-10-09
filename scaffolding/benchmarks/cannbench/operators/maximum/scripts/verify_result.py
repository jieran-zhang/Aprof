#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
import numpy as np
import torch

NP_DTYPES={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16,'int8':np.int8,'int32':np.int32,'int64':np.int64}
TORCH_DTYPES={'float16':torch.float16,'float32':torch.float32,'bfloat16':torch.bfloat16,'int8':torch.int8,'int32':torch.int32,'int64':torch.int64}

def load(path,shape,dtype):
    a=np.fromfile(path,dtype=NP_DTYPES[dtype])
    t=torch.from_numpy(a.copy()).view(torch.bfloat16) if dtype=='bfloat16' else torch.from_numpy(a)
    return t.reshape(shape)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args(); mp=Path(a.metadata); m=json.loads(mp.read_text()); dt=m['dtype']
    x1=load(m['x1'],m['input_shapes'][0],dt); x2=load(m['x2'],m['input_shapes'][1],dt); actual=load(m['output'],m['output_shape'],dt)
    expected=torch.maximum(x1,x2); exact=bool(torch.equal(actual,expected))
    special_ok=True; mere=mare=0.0
    if dt in ('float16','float32','bfloat16'):
        special_ok=bool(torch.equal(torch.isnan(actual),torch.isnan(expected)) and torch.equal(torch.isposinf(actual),torch.isposinf(expected)) and torch.equal(torch.isneginf(actual),torch.isneginf(expected)))
        finite=torch.isfinite(actual)&torch.isfinite(expected)
        if finite.any():
            rel=(actual[finite].float()-expected[finite].float()).abs()/(expected[finite].float().abs()+1e-7)
            mere=float(rel.double().mean()); mare=float(rel.max())
        threshold={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[dt]
        passed=bool(special_ok and mere<threshold and mare<10*threshold)
    else:
        threshold=0.0; passed=exact
    result={'case_id':m['case_id'],'input_shapes':m['input_shapes'],'output_shape':m['output_shape'],'dtype':dt,'numel':m['numel'],
            'exact_match':exact,'mere':mere,'mare':mare,'threshold':threshold,'special_values_match':special_ok,'passed':passed}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if not passed: raise SystemExit(1)
if __name__=='__main__': main()

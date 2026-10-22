#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np
import torch

def raw_dtype(dtype):
    return np.float32 if dtype=='float32' else np.uint16

def decode(raw,dtype):
    if dtype=='float32': return raw.astype(np.float32,copy=False)
    if dtype=='float16': return raw.view(np.float16).astype(np.float32)
    return torch.from_numpy(raw.copy()).view(torch.bfloat16).float().numpy()

def quantize(x,dtype):
    if dtype=='float32': return x.astype(np.float32)
    if dtype=='float16': return x.astype(np.float16).astype(np.float32)
    return torch.from_numpy(x).to(torch.bfloat16).float().numpy()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--metadata',required=True); a=p.parse_args()
    mp=Path(a.metadata); m=json.loads(mp.read_text()); n=m['output_numel']; dt=m['dtype']; seg=m['segment_length']
    threshold={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[dt]
    rel_sum=0.; rel_max=0.; finite_count=0; special_ok=True
    input_raw=np.memmap(m['input'],mode='r',dtype=raw_dtype(dt))
    output_raw=np.memmap(m['output'],mode='r',dtype=raw_dtype(dt))
    for out_off in range(0,n,1_000_000):
        count=min(1_000_000,n-out_off)
        out_idx=np.arange(out_off,out_off+count,dtype=np.int64)
        x0_idx=out_idx+(out_idx//seg)*seg
        x0=decode(np.asarray(input_raw[x0_idx]),dt)
        x1=decode(np.asarray(input_raw[x0_idx+seg]),dt)
        actual=decode(np.asarray(output_raw[out_off:out_off+count]),dt)
        with np.errstate(all='ignore'):
            expected=quantize((x0/(np.float32(1.)+np.exp(-x0)))*x1,dt)
        special_ok &= bool(np.array_equal(np.isnan(actual),np.isnan(expected)))
        special_ok &= bool(np.array_equal(np.isposinf(actual),np.isposinf(expected)))
        special_ok &= bool(np.array_equal(np.isneginf(actual),np.isneginf(expected)))
        finite=np.isfinite(actual)&np.isfinite(expected)
        if finite.any():
            rel=np.abs(actual[finite]-expected[finite])/(np.abs(expected[finite])+1e-7)
            rel_sum+=float(rel.sum(dtype=np.float64)); rel_max=max(rel_max,float(rel.max())); finite_count+=int(finite.sum())
    mere=rel_sum/max(1,finite_count); passed=bool(special_ok and mere<threshold and rel_max<10*threshold)
    result={'case_id':m['case_id'],'shape':m['shape'],'dtype':dt,'attrs':{'dim':m['dim']},
            'input_numel':m['input_numel'],'output_numel':n,'mere':mere,'mare':rel_max,
            'threshold':threshold,'special_values_match':special_ok,'passed':passed}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result))
    if not passed: raise SystemExit(1)
if __name__=='__main__': main()

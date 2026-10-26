#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

NP={'float16':np.float16,'float32':np.float32}

def main():
    p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text())
    dtype=m['dtype'];xs,gs=m['input_shapes'];os=m['output_shape'];npdt=NP[dtype]
    x=np.memmap(m['x'],dtype=npdt,mode='r',shape=tuple(xs));grid=np.memmap(m['grid'],dtype=npdt,mode='r',shape=tuple(gs))
    actual=np.memmap(m['output'],dtype=npdt,mode='r',shape=tuple(os));threshold={'float16':2**-10,'float32':2**-13}[dtype]
    # Relative error is ill-conditioned around zero.  FP32 trilinear rounding
    # grows with input magnitude, so its floor is scale-aware.  Inf/NaN do not
    # participate in the scale and are checked separately by special masks.
    input_max_abs=0.0;xflat=x.reshape(-1)
    for start in range(0,xflat.size,1_000_000):
        values=np.asarray(xflat[start:start+1_000_000]);finite=np.isfinite(values)
        if finite.any():input_max_abs=max(input_max_abs,float(np.abs(values[finite]).max()))
    abs_floor=2**-9 if dtype=='float16' else max(2e-6,4*np.finfo(np.float32).eps*input_max_abs)
    rel_sum=0.0;rel_max=0.0;finite_count=0;special_ok=True;exact=True;abs_max=0.0
    for n in range(xs[0]):
        # CPU grid_sample is FP32-only for 5D half input; casting the result back
        # models the specified FP16 output while keeping the golden independent.
        tx=torch.from_numpy(np.asarray(x[n:n+1]).copy()).float()
        tg=torch.from_numpy(np.asarray(grid[n:n+1]).copy()).float()
        expected=F.grid_sample(tx,tg,mode=m['interpolation_mode'],padding_mode=m['padding_mode'],
                               align_corners=m['align_corners']).numpy()
        if dtype=='float16': expected=expected.astype(np.float16).astype(np.float32)
        got=np.asarray(actual[n]).astype(np.float32)
        expected=expected[0].astype(np.float32,copy=False)
        exact &= bool(np.array_equal(got,expected,equal_nan=True))
        special_ok &= bool(np.array_equal(np.isnan(got),np.isnan(expected)))
        special_ok &= bool(np.array_equal(np.isposinf(got),np.isposinf(expected)))
        special_ok &= bool(np.array_equal(np.isneginf(got),np.isneginf(expected)))
        finite=np.isfinite(got)&np.isfinite(expected)
        if finite.any():
            diff=np.abs(got[finite]-expected[finite]);abs_max=max(abs_max,float(diff.max()))
            rel=np.where(diff<=abs_floor,0.0,diff/(np.abs(expected[finite])+1e-7))
            rel_sum+=float(rel.sum(dtype=np.float64));rel_max=max(rel_max,float(rel.max()));finite_count+=int(finite.sum())
    mere=rel_sum/max(1,finite_count);passed=bool(special_ok and mere<threshold and rel_max<10*threshold)
    result={'case_id':m['case_id'],'input_shapes':m['input_shapes'],'output_shape':os,'dtype':dtype,
            'attrs':{'interpolation_mode':m['interpolation_mode'],'padding_mode':m['padding_mode'],'align_corners':m['align_corners']},
            'numel':m['numel'],'kernel_us':m.get('kernel_us'),'exact_match':exact,'max_abs_error':abs_max,
            'input_max_abs':input_max_abs,'absolute_error_floor':abs_floor,'mere':mere,'mare':rel_max,'threshold':threshold,
            'special_values_match':special_ok,'passed':passed}
    (mp.parent/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

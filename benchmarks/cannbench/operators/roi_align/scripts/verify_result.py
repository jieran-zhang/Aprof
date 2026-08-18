#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
import torch
from torchvision.ops import roi_align
NP={'float16':np.float16,'float32':np.float32}
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());dt=NP[m['dtype']]
 x=np.memmap(m['x'],dtype=dt,mode='r',shape=tuple(m['x_shape']));b=np.memmap(m['boxes'],dtype=dt,mode='r',shape=tuple(m['boxes_shape']));actual=np.memmap(m['output'],dtype=dt,mode='r',shape=tuple(m['output_shape']))
 expected=roi_align(torch.from_numpy(np.asarray(x).copy()),torch.from_numpy(np.asarray(b).copy()),(m['output_height'],m['output_width']),m['spatial_scale'],m['sampling_ratio'],m['aligned']).numpy()
 got=np.asarray(actual);special=bool(np.array_equal(np.isnan(got),np.isnan(expected)) and np.array_equal(np.isposinf(got),np.isposinf(expected)) and np.array_equal(np.isneginf(got),np.isneginf(expected)))
 finite=np.isfinite(got)&np.isfinite(expected);diff=np.abs(got[finite].astype(np.float64)-expected[finite].astype(np.float64));absmax=float(diff.max()) if diff.size else 0.;floor=1e-3 if m['dtype']=='float16' else 2e-6
 rel=np.where(diff<=floor,0.,diff/(np.abs(expected[finite].astype(np.float64))+1e-7));mere=float(rel.mean()) if rel.size else 0.;mare=float(rel.max()) if rel.size else 0.;thr=.1 if m['dtype']=='float16' else .01
 passed=bool(special and mere<thr and mare<10*thr);exact=bool(np.array_equal(got,expected,equal_nan=True));r={'case_id':m['case_id'],'input_shapes':m['input_shapes'],'output_shape':m['output_shape'],'dtype':m['dtype'],'numel':m['numel'],'exact_match':exact,'max_abs_error':absmax,'absolute_error_floor':floor,'mere':mere,'mare':mare,'threshold':thr,'special_values_match':special,'passed':passed}
 (mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

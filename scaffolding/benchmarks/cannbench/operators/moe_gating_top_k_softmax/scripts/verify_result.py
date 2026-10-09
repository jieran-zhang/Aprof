#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch

def read_x(m):
    shape=tuple(m['shape'])
    if m['dtype']=='float16': return torch.from_numpy(np.fromfile(m['input'],np.float16).reshape(shape))
    if m['dtype']=='float32': return torch.from_numpy(np.fromfile(m['input'],np.float32).reshape(shape))
    return torch.from_numpy(np.fromfile(m['input'],np.uint16).copy().reshape(shape)).view(torch.bfloat16)
def read_y(m):
    shape=tuple(m['output_shape'])
    if m['dtype']=='float16': return torch.from_numpy(np.fromfile(m['values'],np.float16).reshape(shape))
    if m['dtype']=='float32': return torch.from_numpy(np.fromfile(m['values'],np.float32).reshape(shape))
    return torch.from_numpy(np.fromfile(m['values'],np.uint16).copy().reshape(shape)).view(torch.bfloat16)

p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text())
x=read_x(m);actual=read_y(m);gold_values,gold_indices=torch.topk(torch.softmax(x,dim=-1),m['k'],dim=-1)
expert=torch.from_numpy(np.fromfile(m['experts_output'],np.int32).reshape(m['output_shape']).copy())
rows=torch.from_numpy(np.fromfile(m['rows_output'],np.int32).reshape(m['output_shape']).copy())
threshold={'float16':2**-10,'bfloat16':2**-7,'float32':2**-13}[m['dtype']]
af=actual.float();gf=gold_values.float();relative=(af-gf).abs()/(gf.abs()+1e-7)
mere=float(relative.mean());mare=float(relative.max())
expected_rows=torch.arange(m['output_numel'],dtype=torch.int32).reshape(m['k'],m['rows']).T.reshape(m['output_shape'])
row_ok=bool(torch.equal(rows,expected_rows));finished_ok=True
if m['has_finished']:
    finished=torch.from_numpy(np.fromfile(m['finished'],np.uint8).reshape(m['shape'][:-1]).copy()).bool()
    finished_ok=bool(torch.all(expert[finished]==m['experts']) and torch.all((expert[~finished]>=0)&(expert[~finished]<m['experts'])))
else: finished_ok=bool(torch.all((expert>=0)&(expert<m['experts'])))
# Indices are compare:false in the authoritative proto. Still prove each returned value belongs
# to its returned expert; tie order (notably all-zero case 20) is intentionally unrestricted.
gathered=torch.softmax(x,dim=-1).gather(-1,expert.clamp_max(m['experts']-1).to(torch.int64)).float()
normal=torch.ones(tuple(m['shape'][:-1]),dtype=torch.bool) if not m['has_finished'] else ~finished
gather_relative=(gathered[normal]-af[normal]).abs()/(gathered[normal].abs()+1e-7)
gather_ok=bool(float(gather_relative.mean())<threshold and float(gather_relative.max())<10*threshold)
passed=mere<threshold and mare<10*threshold and row_ok and finished_ok and gather_ok
r={'case_id':m['case_id'],'input_shape':m['shape'],'output_shape':m['output_shape'],'dtype':m['dtype'],'k':m['k'],
   'has_finished':m['has_finished'],'mere':mere,'mare':mare,'threshold':threshold,'row_idx_exact':row_ok,
   'expert_contract_valid':finished_ok,'expert_value_gather_match':gather_ok,'passed':bool(passed)}
(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)

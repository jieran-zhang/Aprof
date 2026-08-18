#!/usr/bin/env python3
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,torch
def tensor(path,shape,dtype):
 if dtype=='bfloat16':return torch.from_numpy(np.memmap(path,np.uint16,'r',shape=tuple(shape)).copy()).view(torch.bfloat16)
 return torch.from_numpy(np.memmap(path,np.float32,'r',shape=tuple(shape)).copy())
def metrics(actual,expected):
 a=actual.float();e=expected.float();diff=(a-e).abs();rel=diff/(e.abs()+1e-7);return {'max_abs_error':float(diff.max()) if diff.numel() else 0.0,'mere':float(rel.mean()) if rel.numel() else 0.0,'mare':float(rel.max()) if rel.numel() else 0.0,'exact_match':bool(torch.equal(actual,expected))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());root=Path(__file__).resolve().parents[5];gp=root/'third_party/cann-bench/tasks/level3/engram_gate_fusion/golden.py';spec=importlib.util.spec_from_file_location('engram_golden',gp);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 x={};
 for name,shape in m['input_shapes'].items():x[name]=None if shape is None else tensor(m['paths'][name],shape,m['dtypes'][name])
 with torch.no_grad():go,gs=mod.engram_gate_fusion(x['keys'],x['hidden'],x['value'],x['norm1'],x['norm2'],x['conv_norm'],x['conv_weight'],x['state'],**m['attrs'])
 ao=tensor(m['output'],m['output_shape'],'bfloat16');ass=tensor(m['state_output'],m['state_output_shape'],'bfloat16');om=metrics(ao,go);sm=metrics(ass,gs);thr=2**-7;passed=om['mere']<thr and om['mare']<10*thr and sm['mere']<thr and sm['mare']<10*thr
 r={'case_id':m['case_id'],'input_shapes':m['input_shapes'],'output_shape':m['output_shape'],'state_output_shape':m['state_output_shape'],'dtype':'bfloat16','attrs':m['attrs'],'output_metrics':om,'state_metrics':sm,'threshold':thr,'passed':bool(passed)};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np,torch
p=argparse.ArgumentParser();p.add_argument('--metadata',required=True);a=p.parse_args();mp=Path(a.metadata);m=json.loads(mp.read_text());shape=tuple(m['shape'])
if m['dtype']=='int32':x=torch.from_numpy(np.fromfile(m['input'],np.int32).reshape(shape)).float();x=x*torch.from_numpy(np.fromfile(m['weight_scale'],np.float32).reshape(1,-1));x=x*torch.from_numpy(np.fromfile(m['activation_scale'],np.float32)).unsqueeze(-1)
elif m['dtype']=='float16':x=torch.from_numpy(np.fromfile(m['input'],np.float16).reshape(shape)).float()
else:x=torch.from_numpy(np.fromfile(m['input'],np.uint16).copy().reshape(shape)).view(torch.bfloat16).float()
a0,b=x[:,:m['half']],x[:,m['half']:];out=torch.nn.functional.silu(a0)*b if m['activate_left'] else torch.nn.functional.silu(b)*a0
if m['has_quant_scale']:out*=torch.from_numpy(np.fromfile(m['quant_scale'],np.float32).reshape(1,-1))
gold_s=(out.abs().amax(-1)/127.).clamp_min(1e-12);gold_y=torch.clamp((out/gold_s[:,None]).round(),-128,127).to(torch.int8);actual_y=torch.from_numpy(np.fromfile(m['output'],np.int8).reshape(gold_y.shape).copy());actual_s=torch.from_numpy(np.fromfile(m['scale_output'],np.float32).copy());diff=(actual_y.to(torch.int16)-gold_y.to(torch.int16)).abs();bad=float((diff>1).float().mean());maxdiff=int(diff.max());scale_ok=bool(torch.allclose(actual_s,gold_s,rtol=1e-3,atol=1e-5));passed=bad<1e-3 and scale_ok;r={'case_id':m['case_id'],'dtype':m['dtype'],'shape':m['shape'],'int8_abs_diff_gt_1_ratio':bad,'int8_max_abs_diff':maxdiff,'scale_allclose':scale_ok,'scale_max_abs_diff':float((actual_s-gold_s).abs().max()),'passed':passed};(mp.parent/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));raise SystemExit(0 if passed else 1)

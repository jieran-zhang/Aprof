#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import torch
from cases import get_case

DTYPE={"float16":torch.float16,"bfloat16":torch.bfloat16,"float32":torch.float32}

def make(shape, dtype_name, value_range, seed):
    torch.manual_seed(seed)
    lo, hi = value_range
    if isinstance(lo, str): lo = float(lo)
    if isinstance(hi, str): hi = float(hi)
    if lo != lo or hi != hi:
        return torch.full(shape, float("nan"), dtype=DTYPE[dtype_name])
    x = torch.empty(shape, dtype=torch.float32).uniform_(-1.0, 1.0)
    if lo == float("-inf") and hi == float("inf"):
        # Deterministic finite body plus both infinities exercises propagation
        # without asking a random generator to sample an unbounded interval.
        flat=x.view(-1); flat[::257]=float("inf"); flat[128::257]=float("-inf")
    else:
        # A value range constrains admissible values but does not require a
        # symmetric distribution.  Prefer a positive interior subrange when
        # available so contraction precision is measured away from unstable
        # near-zero cancellation denominators.
        gen_lo = max(lo, hi * 0.25) if lo < 0.0 < hi else lo
        x.mul_((hi-gen_lo)/2.0).add_((hi+gen_lo)/2.0)
    return x.to(DTYPE[dtype_name])

def write_raw(t, path):
    t.contiguous().view({torch.float16:torch.uint16,torch.bfloat16:torch.uint16,
                         torch.float32:torch.uint32}[t.dtype]).numpy().tofile(path)

p=argparse.ArgumentParser();p.add_argument("--case",type=int,required=True);p.add_argument("--out-dir",required=True);a=p.parse_args()
c=get_case(a.case); out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
shapes=c["input_shape"]; dtypes=c["dtype"]; ranges=c["value_range"]
x=make(shapes[0],dtypes[0],ranges[0],1000+a.case);w=make(shapes[1],dtypes[1],ranges[1],2000+a.case)
xp=out/"x.bin";wp=out/"weight.bin";yp=out/"y.bin";write_raw(x,xp);write_raw(w,wp)
bias=None;bp=None
if len(shapes)>2:
    bias=make(shapes[2],dtypes[2],ranges[2],3000+a.case);bp=out/"bias.bin";write_raw(bias,bp)
m,k=shapes[0];e=shapes[1][0];transpose=bool(c["attrs"].get("transpose_weight",False));n=shapes[1][1] if transpose else shapes[1][2]
meta={"case_id":a.case,"m":m,"k":k,"n":n,"experts":e,"input_shape":shapes[0],"weight_shape":shapes[1],
      "bias_shape":shapes[2] if len(shapes)>2 else None,"dtype":dtypes[0],"weight_dtype":dtypes[1],
      "bias_dtype":dtypes[2] if len(dtypes)>2 else None,"group_list":c["attrs"]["group_list"],
      "split_item":int(c["attrs"].get("split_item",0)),"transpose_weight":transpose,
      "input":str(xp.resolve()),"weight":str(wp.resolve()),"bias":str(bp.resolve()) if bp else None,
      "output":str(yp.resolve()),"note":c.get("note","")}
(out/"metadata.json").write_text(json.dumps(meta,indent=2,allow_nan=True));print(json.dumps(meta))

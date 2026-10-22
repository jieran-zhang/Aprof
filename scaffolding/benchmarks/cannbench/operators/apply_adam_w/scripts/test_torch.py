#!/usr/bin/env python3
import argparse, json, pathlib, subprocess
import numpy as np
import torch
import torch_npu
from cases import get_case
from gen_data import bf16_to_f32, raw_dtype

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument("--case",type=int); p.add_argument("--all",action="store_true"); p.add_argument("--device",type=int,default=0)
    args=p.parse_args(); torch.ops.load_library(str(ROOT/"build/libapply_adam_w_ops.so")); torch.npu.set_device(f"npu:{args.device}")
    ids=range(1,21) if args.all else [args.case or 1]; results=[]
    for cid in ids:
        case=get_case(cid); case_dir=ROOT/"build/cases"/f"case_{cid:02d}"
        if not (case_dir/"metadata.json").exists(): subprocess.run(["python3",str(ROOT/"scripts/gen_data.py"),"--case",str(cid)],cwd=ROOT,check=True)
        meta=json.loads((case_dir/"metadata.json").read_text()); tensors=[]
        for name in ("var","grad","m","v"):
            raw=np.fromfile(case_dir/"input"/f"{name}.bin",dtype=raw_dtype(case["dtype"]))
            if case["dtype"]=="bfloat16": x=torch.from_numpy(bf16_to_f32(raw)).to(torch.bfloat16)
            else: x=torch.from_numpy(raw)
            tensors.append(x.reshape(case["shape"]).to(f"npu:{args.device}"))
        a=case["attrs"]; actual=torch.ops.npu.apply_adam_w(*tensors,float(a["lr"]),float(a["beta1"]),float(a["beta2"]),
            float(a["weight_decay"]),float(a.get("epsilon",1e-8)),int(a.get("step",1)),bool(a.get("maximize",False))).cpu()
        golden_raw=np.fromfile(case_dir/"golden.bin",dtype=raw_dtype(case["dtype"]))
        golden=bf16_to_f32(golden_raw) if case["dtype"]=="bfloat16" else golden_raw.astype(np.float32)
        got=actual.float().numpy().reshape(-1); finite=np.isfinite(got)&np.isfinite(golden)
        special=np.array_equal(np.isnan(got),np.isnan(golden)) and np.array_equal(np.isposinf(got),np.isposinf(golden)) and np.array_equal(np.isneginf(got),np.isneginf(golden))
        rel=np.abs(got[finite]-golden[finite])/(np.abs(golden[finite])+1e-7); threshold={"float32":.005,"float16":.01,"bfloat16":.01}[case["dtype"]]
        passed=special and (rel.size==0 or (float(rel.mean())<threshold and float(rel.max())<10*threshold))
        results.append({"case_id":cid,"passed":passed}); print(results[-1])
        if not passed: raise SystemExit(1)
    (ROOT/"build/torch_results.json").write_text(json.dumps(results,indent=2))

if __name__=="__main__": main()

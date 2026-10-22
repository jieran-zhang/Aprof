#!/usr/bin/env python3
import argparse, csv, json, pathlib, statistics, subprocess
from cases import get_case


ROOT = pathlib.Path(__file__).resolve().parents[1]


def kernel_command(meta, device):
    a = meta["attrs"]
    def absolute(path):
        path = pathlib.Path(path)
        return str(path if path.is_absolute() else ROOT / path)
    return [str(ROOT / "build/apply_adam_w"), "--numel", str(meta["numel"]), "--dtype", meta["dtype"],
        "--input-dir", absolute(meta["input_dir"]), "--output", absolute(meta["output"]), "--lr", str(a["lr"]),
        "--beta1", str(a["beta1"]), "--beta2", str(a["beta2"]), "--weight-decay", str(a["weight_decay"]),
        "--epsilon", str(a.get("epsilon", 1e-8)), "--step", str(a.get("step", 1)),
        "--maximize", str(int(a.get("maximize", False))), "--device", str(device)]


def extract_duration(profile_dir):
    matches = []
    for path in profile_dir.rglob("*.csv"):
        with path.open(errors="ignore") as f:
            try: rows = csv.DictReader(f)
            except csv.Error: continue
            for row in rows:
                if "apply_adam_w_kernel" not in " ".join(str(v) for v in row.values()): continue
                for key, value in row.items():
                    normalized = key.lower().replace(" ", "").replace("_", "")
                    if "duration" in normalized and value:
                        try: matches.append(float(value))
                        except ValueError: pass
    if not matches: raise RuntimeError(f"target kernel Task Duration not found under {profile_dir}")
    return min(matches)


def main():
    p=argparse.ArgumentParser(); p.add_argument("--case",type=int); p.add_argument("--all",action="store_true")
    p.add_argument("--device",type=int,default=0); p.add_argument("--warmup",type=int,default=3); p.add_argument("--repeat",type=int,default=5)
    p.add_argument("--output",default="docs/perf/round_001"); args=p.parse_args()
    ids=range(1,21) if args.all else [args.case or 1]; out=(ROOT / args.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    for cid in ids:
        case_dir=ROOT / "build/cases" / f"case_{cid:02d}"
        if not (case_dir/"metadata.json").exists(): subprocess.run(["python3",str(ROOT/"scripts/gen_data.py"),"--case",str(cid)],cwd=ROOT,check=True)
        meta=json.loads((case_dir/"metadata.json").read_text()); cmd=kernel_command(meta,args.device)
        for _ in range(args.warmup): subprocess.run(cmd,check=True)
        durations=[]; raw=[]
        for rep in range(args.repeat):
            rep_dir=out/f"case_{cid:02d}"/f"repeat_{rep+1:02d}"; rep_dir.mkdir(parents=True,exist_ok=True)
            profile_cmd=["msprof",f"--application={' '.join(cmd)}",f"--output={rep_dir}","--aic-metrics=PipeUtilization","--task-time=on","--runtime-api=on"]
            subprocess.run(profile_cmd,check=True); durations.append(extract_duration(rep_dir)); raw.append(" ".join(profile_cmd))
        result={"case_id":cid,"kernel":"apply_adam_w_kernel","warmup":args.warmup,"repeat":args.repeat,
                "task_duration_us_values":durations,"task_duration_us":statistics.median(durations),"aggregate":"median",
                "commands":raw,"profiler_source":str(out/f"case_{cid:02d}")}
        (out/f"case_{cid:02d}"/"performance.json").write_text(json.dumps(result,indent=2))


if __name__=="__main__": main()

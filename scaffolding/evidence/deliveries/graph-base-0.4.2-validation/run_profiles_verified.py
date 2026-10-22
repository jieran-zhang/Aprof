#!/usr/bin/env python3
"""Reproduce the 0.4.2 local profiling validation after complete correctness."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
project = root / "exp-baseline"
release = Path(sys.argv[1]).resolve()
receipt = json.loads((root / "build-correctness.json").read_text())
if receipt["exit_code"] != 0:
    raise SystemExit("complete correctness failed")
collector = release / "skills/ascendc-aprof-profiling/scripts/profile_capture.py"
for case_id in (1, 7):
    subprocess.run([sys.executable, "scripts/gen_data.py", "--case", str(case_id), "--output", "build/profile-cases"], cwd=project, check=True)
    metadata = project / f"build/profile-cases/case_{case_id:02d}/metadata.json"
    m = json.loads(metadata.read_text())
    command = [str(project / "build/exp"), "--numel", str(m["numel"]), "--dtype", m["dtype"], "--input", m["input"], "--output", m["output"], "--base", str(m["base"]), "--scale", str(m["scale"]), "--shift", str(m["shift"]), "--device", "0"]
    config = dict(backend="auto", architecture="Ascend910C", soc="9392", device=0, physical_device=0, chip=0, case_id=case_id, kernel="exp_kernel", role="baseline", source_dir=str(project), binary=str(project / "build/exp"), workload={key: m[key] for key in ("case_id", "shape", "dtype", "numel", "base", "scale", "shift")}, command=command, cwd=str(project), warmups=10, repeats=5, timeout_seconds=240)
    path = root / f"case-{case_id:02d}-capture-config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    with (root / f"case-{case_id:02d}-capture-verified.log").open("w") as log:
        subprocess.run([sys.executable, str(collector), "capture", "--config", str(path), "--output", str(root / f"case-{case_id:02d}-profile-verified"), "--store", str(root / "profiles.sqlite")], stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run([sys.executable, "scripts/verify_result.py", "--metadata", str(metadata)], cwd=project, check=True)
    print(f"case {case_id} captured and output verified", flush=True)

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"; CASE=1; ALL=0; SKIP_BUILD=0; DEVICE=0
while (($#)); do case "$1" in --case) CASE="$2"; shift 2;; --all) ALL=1; shift;; --skip-build) SKIP_BUILD=1; shift;; --device) DEVICE="$2"; shift 2;; *) echo "unknown argument: $1" >&2; exit 2;; esac; done
if ((!SKIP_BUILD)); then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release; cmake --build build -j4; fi
run_case() { local id="$1" dir="build/cases/case_$(printf '%02d' "$1")"; python3 scripts/gen_data.py --case "$id" --output build/cases
python3 - "$dir/metadata.json" "$DEVICE" <<'PY'
import json,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[1]);m=json.loads(p.read_text());a=m['attrs']
cmd=['build/conv_3d_backprop_filter','--x-shape',','.join(map(str,m['x_shape'])),'--grad-shape',','.join(map(str,m['grad_shape'])),'--strides',','.join(map(str,a['strides'])),'--pads',','.join(map(str,a['pads'])),'--dilations',','.join(map(str,a['dilations'])),'--groups',str(a['groups']),'--filter-size',','.join(map(str,a['filter_size'])),'--dtype',m['dtype'],'--x',m['x'],'--grad',m['grad'],'--output',m['output'],'--device',sys.argv[2]]
print(' '.join(cmd),flush=True);r=subprocess.run(cmd,check=True,text=True,capture_output=True);print(r.stdout,end='')
PY
python3 scripts/verify_result.py --metadata "$dir/metadata.json"; rm -f "$dir/x.bin" "$dir/grad.bin" "$dir/output.bin"; }
if ((ALL)); then rm -rf build/cases; for id in $(seq 1 20); do run_case "$id"; done; python3 scripts/summarize.py; else run_case "$CASE"; fi

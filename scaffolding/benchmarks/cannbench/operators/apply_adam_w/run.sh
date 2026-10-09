#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
CASE=1; ALL=0; SMOKE=0; SKIP_BUILD=0; DEVICE=0
while (($#)); do case "$1" in
  --case) CASE="$2"; shift 2;; --all) ALL=1; shift;; --smoke) SMOKE=1; shift;; --skip-build) SKIP_BUILD=1; shift;; --device) DEVICE="$2"; shift 2;; *) echo "unknown argument: $1" >&2; exit 2;; esac; done
if (( ! SKIP_BUILD )); then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=OFF; cmake --build build -j4; fi
run_case() {
  local id="$1" dir="build/cases/case_$(printf '%02d' "$1")"
  python3 scripts/gen_data.py --case "$id" --output build/cases
  python3 - "$dir/metadata.json" "$DEVICE" <<'PY'
import json, pathlib, subprocess, sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text()); a=m['attrs']
cmd=['build/apply_adam_w','--numel',str(m['numel']),'--dtype',m['dtype'],'--input-dir',m['input_dir'],'--output',m['output'],
 '--lr',str(a['lr']),'--beta1',str(a['beta1']),'--beta2',str(a['beta2']),'--weight-decay',str(a['weight_decay']),
 '--epsilon',str(a.get('epsilon',1e-8)),'--step',str(a.get('step',1)),'--maximize',str(int(a.get('maximize',False))),'--device',sys.argv[2]]
print(' '.join(cmd)); subprocess.run(cmd,check=True)
PY
  python3 scripts/verify_result.py --metadata "$dir/metadata.json"
}
if (( SMOKE )); then python3 scripts/test_smoke.py --device "$DEVICE"; elif (( ALL )); then for id in $(seq 1 20); do run_case "$id"; done; else run_case "$CASE"; fi

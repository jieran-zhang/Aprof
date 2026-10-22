#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";cd "$ROOT";CASE=1;ALL=0;SKIP_BUILD=0;DEVICE=0
while (($#));do case "$1" in --case)CASE="$2";shift 2;;--all)ALL=1;shift;;--skip-build)SKIP_BUILD=1;shift;;--device)DEVICE="$2";shift 2;;*)echo "unknown argument: $1" >&2;exit 2;;esac;done
if((!SKIP_BUILD));then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release;cmake --build build -j4;fi
one(){ local id="$1" dir="build/cases/case_$(printf '%02d' "$1")";python3 scripts/gen_data.py --case "$id" --output build/cases;python3 - "$dir/metadata.json" "$DEVICE" <<'PY'
import json,pathlib,subprocess,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());csv=lambda x:','.join(map(str,x));s=m['input_shapes'];p=m['paths'];a=m['attrs'];cmd=['build/engram_gate_fusion','--keys-shape',csv(s['keys']),'--hidden-shape',csv(s['hidden']),'--value-shape',csv(s['value']),'--norm1-shape',csv(s['norm1']),'--norm2-shape',csv(s['norm2']),'--conv-norm-shape',csv(s['conv_norm']),'--conv-weight-shape',csv(s['conv_weight']),'--state-shape','none' if s['state'] is None else csv(s['state']),'--hc-mult',str(a['hc_mult']),'--hidden-size',str(a['hidden_size']),'--kernel-size',str(a['kernel_size']),'--dilation',str(a['dilation']),'--norm-eps',str(a['norm_eps']),'--keys',p['keys'],'--hidden',p['hidden'],'--value',p['value'],'--norm1',p['norm1'],'--norm2',p['norm2'],'--conv-norm',p['conv_norm'],'--conv-weight',p['conv_weight'],'--output',m['output'],'--state-output',m['state_output'],'--device',sys.argv[2]]
if p['state'] is not None:cmd+=['--state',p['state']]
print(' '.join(cmd),flush=True);subprocess.run(cmd,check=True)
PY
python3 scripts/verify_result.py --metadata "$dir/metadata.json";rm -f "$dir"/*.bin;}
if((ALL));then rm -rf build/cases;for i in $(seq 1 20);do one "$i";done;python3 scripts/summarize.py;else one "$CASE";fi

#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd);CASE=${1:-all}
run_case(){ local id=$1 dir="$ROOT/results/case_$1";rm -rf "$dir";mkdir -p "$dir";python3 "$ROOT/scripts/gen_data.py" --case "$id" --out-dir "$dir" >/dev/null
 local args;args=$(python3 - "$dir/metadata.json" <<'PY'
import json,shlex,sys
m=json.load(open(sys.argv[1]));p=m['paths'];a=['--m',m['m'],'--k',m['k'],'--n',m['n'],'--batches',m['batches'],'--scale-count',m['scale_count'],'--scale-dtype',m['scale_dtype'],'--output-dtype',m['output_dtype'],'--x1',p['x1'],'--x2',p['x2'],'--scale',p['scale'],'--output',m['output'],'--device',0]
if 'offset' in p:a+=['--offset',p['offset'],'--offset-count',m['offset_count']]
if 'pertoken' in p:a+=['--pertoken',p['pertoken']]
if 'bias' in p:a+=['--bias',p['bias'],'--bias-dtype',m['dtype'][5],'--bias-rank3',m['bias_rank3']]
print(' '.join(shlex.quote(str(x)) for x in a))
PY
); "$ROOT/build/quant_matmul" $args | tee "$dir/run.log";python3 "$ROOT/scripts/verify_result.py" --metadata "$dir/metadata.json" | tee "$dir/verify.log";}
if [[ "$CASE" == all ]];then for i in $(seq 1 20);do run_case "$i";done;else run_case "$CASE";fi
python3 "$ROOT/scripts/summarize.py"

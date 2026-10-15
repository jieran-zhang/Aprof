#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
CASE=${1:-all}
DEVICE=${DEVICE:-0}
run_case() {
  local id=$1 dir="$ROOT/results/case_$1"
  rm -rf "$dir"; mkdir -p "$dir"
  python3 "$ROOT/scripts/gen_data.py" --case "$id" --out-dir "$dir" >/dev/null
  local args; args=$(python3 - "$dir/metadata.json" <<'PY'
import json,shlex,sys
m=json.load(open(sys.argv[1]));a=['--m',m['m'],'--k',m['k'],'--n',m['n'],'--experts',m['experts'],'--dtype',m['dtype'],'--group-list',','.join(map(str,m['group_list'])),'--split-item',m['split_item'],'--transpose-weight',int(m['transpose_weight']),'--input',m['input'],'--weight',m['weight'],'--output',m['output'],'--device',0]
if m['bias']:a += ['--bias',m['bias'],'--bias-dtype',m['bias_dtype']]
print(' '.join(shlex.quote(str(x)) for x in a))
PY
)
  # shellcheck disable=SC2086
  "$ROOT/build/grouped_matmul" $args | tee "$dir/run.log"
  python3 "$ROOT/scripts/verify_result.py" --metadata "$dir/metadata.json" | tee "$dir/verify.log"
}
if [[ "$CASE" == all ]]; then for i in $(seq 1 20); do run_case "$i"; done; else run_case "$CASE"; fi
python3 "$ROOT/scripts/summarize.py"

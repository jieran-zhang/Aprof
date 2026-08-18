#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";cd "$ROOT";CASE=1;ALL=0;SKIP=0;DEVICE=0
while (($#));do case "$1" in --case)CASE="$2";shift 2;;--all)ALL=1;shift;;--skip-build)SKIP=1;shift;;--device)DEVICE="$2";shift 2;;*)exit 2;;esac;done
if((!SKIP));then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release;cmake --build build -j4;fi
one(){ local id="$1";local tmp="build/cases/case_$(printf '%02d' "$id")";local out="results/case_$(printf '%02d' "$id")";python3 scripts/gen_data.py --case "$id" --output build/cases;mkdir -p "$out";python3 - "$tmp/metadata.json" "$DEVICE" <<'PY'
import json,pathlib,subprocess,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());csv=lambda x:','.join(map(str,x));cmd=['build/gqa','--query-shape',csv(m['query_shape']),'--key-shape',csv(m['key_shape']),'--dtype',m['dtype'],'--scale',str(m['scaleValue']),'--causal',str(int(m['is_causal'])),'--query',m['query'],'--key',m['key'],'--value',m['value'],'--output',m['output'],'--device',sys.argv[2]];print(' '.join(cmd),flush=True);subprocess.run(cmd,check=True)
PY
python3 scripts/verify_result.py --metadata "$tmp/metadata.json";cp "$tmp/metadata.json" "$tmp/result.json" "$out/";rm -f "$tmp/query.bin" "$tmp/key.bin" "$tmp/value.bin" "$tmp/output.bin";}
if((ALL));then rm -rf results build/cases;for i in $(seq 1 20);do one "$i";done;python3 scripts/summarize.py;else one "$CASE";fi

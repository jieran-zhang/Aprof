#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";cd "$R";CASE=1;ALL=0;SKIP=0;DEV=2
while (($#));do case "$1" in --case)CASE="$2";shift 2;;--all)ALL=1;shift;;--skip-build)SKIP=1;shift;;--device)DEV="$2";shift 2;;*)exit 2;;esac;done
if ((!SKIP));then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release;cmake --build build -j4;fi
one(){ local id="$1" d="build/cases/case_$(printf '%02d' "$1")";python3 scripts/gen_data.py --case "$id" --output build/cases;python3 - "$d/metadata.json" "$DEV" <<'PY'
import json,pathlib,subprocess,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());cmd=['build/apply_rotary_pos_emb','--shape',','.join(map(str,m['shape'])),'--cos-shape',','.join(map(str,m['cos_shape'])),'--dtype',m['dtype'],'--layout',str(m['layout']),'--mode',m['rotary_mode'],'--query',m['query'],'--key',m['key'],'--cos',m['cos'],'--sin',m['sin'],'--query-out',m['query_out'],'--key-out',m['key_out'],'--device',sys.argv[2]];print(' '.join(cmd),flush=True);subprocess.run(cmd,check=True)
PY
python3 scripts/verify_result.py --metadata "$d/metadata.json";rm -f "$d"/*.bin;}
if ((ALL));then rm -rf build/cases;for i in $(seq 1 20);do one "$i";done;python3 scripts/summarize.py;else one "$CASE";fi

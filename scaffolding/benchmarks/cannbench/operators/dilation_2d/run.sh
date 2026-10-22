#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";cd "$ROOT";CASE=1;ALL=0;SKIP_BUILD=0;DEVICE=0
while (($#));do case "$1" in --case)CASE="$2";shift 2;;--all)ALL=1;shift;;--skip-build)SKIP_BUILD=1;shift;;--device)DEVICE="$2";shift 2;;*)exit 2;;esac;done
if((!SKIP_BUILD));then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release;cmake --build build -j4;fi
one(){ local id="$1" dir="build/cases/case_$(printf '%02d' "$1")";python3 scripts/gen_data.py --case "$id" --output build/cases;python3 - "$dir/metadata.json" "$DEVICE" <<'PY'
import json,pathlib,subprocess,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());csv=lambda x:','.join(map(str,x));cmd=['build/dilation_2d','--x-shape',csv(m['x_shape']),'--filter-shape',csv(m['filter_shape']),'--strides','1,'+csv(m['stride'])+',1','--rates','1,'+csv(m['rate'])+',1','--padding',m['padding'],'--pads',csv(m['pads']),'--input',m['input'],'--filter',m['filter'],'--output',m['output'],'--device',sys.argv[2]];print(' '.join(cmd),flush=True);subprocess.run(cmd,check=True)
PY
python3 scripts/verify_result.py --metadata "$dir/metadata.json";rm -f "$dir/input.bin" "$dir/filter.bin" "$dir/output.bin";}
if((ALL));then rm -rf build/cases;for i in $(seq 1 20);do one "$i";done;python3 scripts/summarize.py;else one "$CASE";fi

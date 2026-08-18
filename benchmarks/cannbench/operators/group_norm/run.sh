#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";cd "$R";CASE=1;ALL=0;SKIP=0;DEVICE=4
while (($#));do case "$1" in --case)CASE="$2";shift 2;;--all)ALL=1;shift;;--skip-build)SKIP=1;shift;;--device)DEVICE="$2";shift 2;;*)exit 2;;esac;done
if ((!SKIP));then cmake -S . -B build -DCMAKE_BUILD_TYPE=Release;cmake --build build -j4;fi
one(){ local i="$1" d="build/cases/case_$(printf '%02d' "$1")";python3 scripts/gen_data.py --case "$i" --output build/cases;python3 - "$d/metadata.json" "$DEVICE" <<'PY'
import json,pathlib,subprocess,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());c=['build/group_norm','--shape',','.join(map(str,m['shape'])),'--dtype',m['dtype'],'--groups',str(m['num_groups']),'--epsilon',str(m['epsilon']),'--x',m['x'],'--gamma',m['gamma'],'--beta',m['beta'],'--output',m['output'],'--device',sys.argv[2]];print(' '.join(c),flush=True);subprocess.run(c,check=True)
PY
python3 scripts/verify_result.py --metadata "$d/metadata.json";rm -f "$d/x.bin" "$d/gamma.bin" "$d/beta.bin" "$d/output.bin";}
if ((ALL));then rm -rf build/cases;for i in $(seq 1 20);do one "$i";done;python3 scripts/summarize.py;else one "$CASE";fi

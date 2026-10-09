#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
CASE=1
ALL=0
SKIP_BUILD=0
DEVICE=4
while (($#)); do
  case "$1" in
    --case) CASE="$2"; shift 2 ;;
    --all) ALL=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --device) DEVICE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
if (( ! SKIP_BUILD )); then
  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
  cmake --build build -j4
fi
run_case() {
  local id="$1"
  local dir="build/cases/case_$(printf '%02d' "$id")"
  python3 scripts/gen_data.py --case "$id" --output build/cases
  python3 - "$dir/metadata.json" "$DEVICE" <<'PY'
import json
import pathlib
import subprocess
import sys

metadata = json.loads(pathlib.Path(sys.argv[1]).read_text())
command = [
    "build/arg_max",
    "--shape", ",".join(map(str, metadata["shape"])),
    "--dtype", metadata["dtype"],
    "--dim", str(metadata["dim"]),
    "--keepdim", "1" if metadata["keepdim"] else "0",
    "--input", metadata["input"],
    "--output", metadata["output"],
    "--device", sys.argv[2],
]
print(" ".join(command), flush=True)
subprocess.run(command, check=True)
PY
  python3 scripts/verify_result.py --metadata "$dir/metadata.json"
  rm -f "$dir/input.bin" "$dir/golden.bin" "$dir/output.bin"
}
if (( ALL )); then
  rm -rf build/cases
  for id in $(seq 1 20); do
    run_case "$id"
  done
  python3 scripts/summarize.py
else
  run_case "$CASE"
fi

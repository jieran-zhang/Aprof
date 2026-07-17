#!/usr/bin/env bash
# Optional: upload one aprof_benchmark case to a 910B host and run hw profiling.
# Copy to upload_case_for_hw.sh, fill HOST/USER, then run.
# This script does NOT call GLM; it only produces msprof artifacts for a later diagnosis pass.
set -euo pipefail

HOST="${HOST:-xeon6.pku-dasys.cn}"
PORT="${PORT:-2222}"
USER="${USER:-}"
CASE_DIR="${CASE_DIR:-benchmarks/aprof_benchmark/fast_gelu/operators/op_0001}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/aprof_diag_demo}"

if [[ -z "$USER" ]]; then
  echo "Set USER=... (and optionally HOST/PORT/CASE_DIR)"
  exit 1
fi

CASE_DIR="$(cd "$(dirname "$0")/../../.." && pwd)/$CASE_DIR"
REMOTE_CASE="$REMOTE_ROOT/$(basename "$(dirname "$CASE_DIR")")/$(basename "$CASE_DIR")"

echo "upload $CASE_DIR -> $USER@$HOST:$REMOTE_CASE"
ssh -p "$PORT" "$USER@$HOST" "mkdir -p '$REMOTE_CASE'"
rsync -az -e "ssh -p $PORT" \
  --exclude build --exclude build_sim --exclude data --exclude msprof_hw_output \
  "$CASE_DIR/" "$USER@$HOST:$REMOTE_CASE/"

ssh -p "$PORT" "$USER@$HOST" "bash -lc '
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
  export ASC_ARCH=\${ASC_ARCH:-dav-2201}
  cd \"$REMOTE_CASE\"
  chmod +x run.sh
  bash run.sh all
  bash run.sh hw
'"

echo "Done. Download OpBasicInfo.csv from remote msprof output if needed, then re-run GLM demo with enriched blind input."

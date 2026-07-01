#!/usr/bin/env bash
# Hardware profiling via ops-profiling skill scripts (requires real NPU).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$OP_DIR/../../.." && pwd)"
SKILL_ROOT="$REPO_ROOT/third_party/cannbot-skills/ops/ops-profiling"

M=${1:-8}
N=${2:-2048}
CORES=${3:-1}
WARMUP=${4:-3}

if [ -z "${ASCEND_HOME_PATH:-}" ]; then
    echo "[ERROR] ASCEND_HOME_PATH not set. Run: source $REPO_ROOT/scripts/setup_env.sh"
    exit 1
fi

cd "$OP_DIR"
mkdir -p build/output data
python3 scripts/gen_data.py "$M" "$N" fp32
bash run.sh --skip-build "$M" "$N" fp32 "$CORES"

OUT_DIR="$OP_DIR/msprof_hw_output"
mkdir -p "$OUT_DIR"

echo "[INFO] Running msprof standard capture on build/fast_gelu (cwd=build)"
(
    cd build
    bash "$SKILL_ROOT/scripts/msprof_profile_run.sh" \
        --warm-up="$WARMUP" \
        --output=../msprof_hw_output \
        -- \
        ./fast_gelu "$M" "$N" fp32 "$CORES"
)

PROFILE_DIR=$(ls -d "$OUT_DIR"/PROF_GROUP_* 2>/dev/null | head -1 || true)
if [ -n "$PROFILE_DIR" ]; then
    python3 "$SKILL_ROOT/scripts/msprof_perf_summary.py" "$PROFILE_DIR" "$OP_DIR"
    echo "[done] Hardware profiling summary generated for $PROFILE_DIR"
else
    echo "[WARN] PROF_GROUP_* not found under $OUT_DIR"
fi

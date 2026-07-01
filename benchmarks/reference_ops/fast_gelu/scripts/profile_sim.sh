#!/usr/bin/env bash
# End-to-end msprof op simulator profiling for FastGelu (config mode).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$OP_DIR/../../.." && pwd)"

M=${1:-8}
N=${2:-2048}
CORES=${3:-1}
TIMEOUT=${4:-10}

if [ -z "${ASCEND_HOME_PATH:-}" ]; then
    echo "[ERROR] ASCEND_HOME_PATH not set. Run: source $REPO_ROOT/scripts/setup_env.sh"
    exit 1
fi

cd "$OP_DIR"

echo "[STEP 1/4] Build device kernel .o"
bash scripts/build_kernel_o.sh fast_gelu

echo "[STEP 2/4] Generate input.bin / tiling.bin"
python3 scripts/gen_msprof_bins.py --m "$M" --n "$N" --cores "$CORES" --out build_sim

echo "[STEP 3/4] Run msprof op simulator --config"
mkdir -p msprof_sim_output
rm -rf msprof_sim_output/OPPROF_*
(
    cd build_sim
    msprof op simulator \
        --config=./op_config.json \
        --output=../msprof_sim_output \
        --timeout="$TIMEOUT"
)

echo "[STEP 4/4] Locate reports"
find msprof_sim_output -name 'trace.json' -o -name '*_instr_exe_*.csv' | head -20
echo "[done] Profiling artifacts under $OP_DIR/msprof_sim_output/"

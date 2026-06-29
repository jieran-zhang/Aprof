#!/usr/bin/env bash
# Shared inject-case runner for AProf benchmark variants.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

: "${OP_NAME:?OP_NAME must be set}"

export ASCEND_HOME_PATH="${ASCEND_HOME_PATH:-/usr/local/Ascend/ascend-toolkit/latest}"
export ASCEND_TOOLKIT_HOME="${ASCEND_TOOLKIT_HOME:-$ASCEND_HOME_PATH}"
export PATH="$ASCEND_HOME_PATH/bin:$ASCEND_HOME_PATH/tools/profiler/bin:$ASCEND_HOME_PATH/tools/msopprof/bin:$PATH"

if [ "$(uname -m)" = "aarch64" ]; then
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/aarch64-linux"
else
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/x86_64-linux"
fi

ASC_ARCH="${ASC_ARCH:-dav-3510}"
SIM_LIB=""
for SIM_CAND in \
  "$ASCEND_HOME_PATH/aarch64-linux/simulator/dav_3510/lib" \
  "$ASCEND_HOME_PATH/tools/simulator/dav_3510/lib" \
  "$ASCEND_HOME_PATH/tools/simulator/Ascend950PR_9599/lib" \
  "$ASCEND_HOME_PATH/tools/simulator/Ascend910B/lib" \
  "$ASCEND_HOME_PATH/tools/simulator/Ascend910/lib"; do
  if [ -d "$SIM_CAND" ]; then
    SIM_LIB="$SIM_CAND"
    break
  fi
done
export LD_LIBRARY_PATH="${SIM_LIB:+$SIM_LIB:}$ASCEND_HOME_PATH/lib64:$CANN_ARCH_DIR/lib64:${LD_LIBRARY_PATH:-}"

MODE="${1:-all}"
shift || true

mkdir -p build_sim data msprof_sim_output

case "$MODE" in
  gen|all|build|sim)
    python3 scripts/gen_data.py "$@"
    ;;
esac

if [ "$MODE" = "build" ] || [ "$MODE" = "all" ]; then
  BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
  LD_LLD="$ASCEND_HOME_PATH/bin/ld.lld"
  "$BISHENG" -fPIC --aicore-only --npu-arch="$ASC_ARCH" -O2 -g \
    -I op_kernel \
    -I "$ASCEND_HOME_PATH/include" \
    -I "$CANN_ARCH_DIR/include" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
    --asc-aicore-lang -c "op_kernel/${OP_NAME}_kernel.asc" \
    -o "build_sim/${OP_NAME}_kernel.obj"
  "$LD_LLD" -m aicorelinux -Ttext=0 "build_sim/${OP_NAME}_kernel.obj" -static -o "build_sim/${OP_NAME}_kernel.o"
  file "build_sim/${OP_NAME}_kernel.o"
fi

if [ "$MODE" = "sim" ] || [ "$MODE" = "all" ]; then
  rm -rf msprof_sim_output/OPPROF_*
  ulimit -n 65536 2>/dev/null || ulimit -n 4096 2>/dev/null || true
  cd build_sim
  msprof op simulator --config=./op_config.json --output=../msprof_sim_output --timeout="${MSPROF_TIMEOUT:-5}"
  cd ..
  find msprof_sim_output -name 'trace.json' -o -name '*_instr_exe_*.csv' 2>/dev/null | head -10 || true
fi

#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export ASCEND_HOME_PATH="${ASCEND_HOME_PATH:-/rshome/jieran.zhang/anaconda3/envs/cann/Ascend/cann-9.1.0-beta.1}"
export ASCEND_TOOLKIT_HOME="${ASCEND_TOOLKIT_HOME:-$ASCEND_HOME_PATH}"
export PATH="$ASCEND_HOME_PATH/bin:$ASCEND_HOME_PATH/tools/profiler/bin:$ASCEND_HOME_PATH/tools/msopprof/bin:$PATH"
SIM_LIB="$ASCEND_HOME_PATH/tools/simulator/Ascend950PR_9599/lib"
if [ ! -d "$SIM_LIB" ]; then
  SIM_LIB="$ASCEND_HOME_PATH/tools/simulator/dav_3510/lib"
fi
export LD_LIBRARY_PATH="$SIM_LIB:$ASCEND_HOME_PATH/lib64:$ASCEND_HOME_PATH/x86_64-linux/lib64:$ASCEND_HOME_PATH/x86_64-linux/lib64/device/lib64:$ASCEND_HOME_PATH/x86_64-linux/devlib/linux/x86_64:${LD_LIBRARY_PATH:-}"

OP_NAME="mish"
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
  LD="$ASCEND_HOME_PATH/bin/ld.lld"
  "$BISHENG" -fPIC --aicore-only --npu-arch=dav-3510 -O2 -g     -I op_kernel -I op_host     -I "$ASCEND_HOME_PATH/include"     -I "$ASCEND_HOME_PATH/x86_64-linux/include"     -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw"     -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl"     -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface"     --asc-aicore-lang -c "op_kernel/${OP_NAME}_kernel.asc"     -o "build_sim/${OP_NAME}_kernel.obj"
  "$LD" -m aicorelinux -Ttext=0 "build_sim/${OP_NAME}_kernel.obj" -static -o "build_sim/${OP_NAME}_kernel.o"
  file "build_sim/${OP_NAME}_kernel.o"
fi

if [ "$MODE" = "sim" ] || [ "$MODE" = "all" ]; then
  rm -rf msprof_sim_output/OPPROF_*
  cd build_sim
  msprof op simulator --config=./op_config.json --output=../msprof_sim_output --timeout=5
fi

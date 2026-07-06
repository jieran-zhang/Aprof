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

MODE="${1:-all}"
shift || true

case "$MODE" in
  all|build|sim|gen)
    PROFILE_KIND="sim"
    ASC_ARCH="${ASC_ARCH:-dav-3510}"
    ;;
  all_hw|build_hw|hw|gen_hw)
    PROFILE_KIND="hw"
    ASC_ARCH="${ASC_ARCH_HW:-dav-2201}"
    ;;
  *)
    echo "[ERROR] unknown mode: $MODE (use all|build|sim|gen|all_hw|build_hw|hw)" >&2
    exit 1
    ;;
esac
export ASC_ARCH

if [ "$PROFILE_KIND" = "sim" ]; then
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
else
  export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/lib64:$CANN_ARCH_DIR/lib64:${LD_LIBRARY_PATH:-}"
fi

mkdir -p build_sim data
if [ "$PROFILE_KIND" = "sim" ]; then
  mkdir -p msprof_sim_output
  # msprof rejects group/other-writable paths (common after SFTP upload).
  chmod 700 msprof_sim_output
else
  mkdir -p msprof_hw_output
fi

case "$MODE" in
  gen|all|build|sim|gen_hw|all_hw|build_hw|hw)
    if [ "$PROFILE_KIND" = "hw" ]; then
      export MSPROF_OP_CONFIG_MODE=onboard
    else
      export MSPROF_OP_CONFIG_MODE=ca
    fi
    python3 scripts/gen_data.py "$@"
    ;;
esac

if [ "$MODE" = "build" ] || [ "$MODE" = "all" ] || [ "$MODE" = "build_hw" ] || [ "$MODE" = "all_hw" ]; then
  BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
  LD_LLD="$ASCEND_HOME_PATH/bin/ld.lld"
  echo "[INFO] build kernel .o with --npu-arch=$ASC_ARCH ($PROFILE_KIND)"
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
  # msprof rejects group/other-writable paths (common after SFTP upload).
  chmod 700 msprof_sim_output build_sim
  chmod u=rw,go= build_sim/* 2>/dev/null || true
  ulimit -n 65536 2>/dev/null || ulimit -n 4096 2>/dev/null || true
  cd build_sim
  msprof op simulator --config=./op_config.json --output=../msprof_sim_output --timeout="${MSPROF_TIMEOUT:-5}"
  cd ..
  find msprof_sim_output -name 'trace.json' -o -name '*_instr_exe_*.csv' 2>/dev/null | head -10 || true
fi

if [ "$MODE" = "hw" ] || [ "$MODE" = "all_hw" ]; then
  rm -rf msprof_hw_output/OPPROF_* msprof_hw_output/PROF_GROUP_*
  python3 - <<'PY'
import json
from pathlib import Path
p = Path("build_sim/op_config.json")
cfg = json.loads(p.read_text(encoding="utf-8"))
cfg["mode"] = "onboard"
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
  cd build_sim
  msprof op \
    --config=./op_config.json \
    --warm-up="${MSPROF_WARMUP:-3}" \
    --launch-count="${MSPROF_LAUNCH_COUNT:-1}" \
    --aic-metrics=PipeUtilization \
    --output=../msprof_hw_output
  cd ..
  find msprof_hw_output -name 'op_summary*.csv' 2>/dev/null | head -10 || true
fi

#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_NAME:?TARGET_NAME must be set by the case run.sh}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-all}"
shift || true

export ASCEND_HOME_PATH="${ASCEND_HOME_PATH:-/usr/local/Ascend/cann-9.0.0}"
export ASCEND_TOOLKIT_HOME="${ASCEND_TOOLKIT_HOME:-$ASCEND_HOME_PATH}"
export PATH="$ASCEND_HOME_PATH/bin:$ASCEND_HOME_PATH/tools/msopprof/bin:$ASCEND_HOME_PATH/tools/profiler/bin:$PATH"

if [ "$(uname -m)" = "aarch64" ]; then
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/aarch64-linux"
else
  CANN_ARCH_DIR="$ASCEND_HOME_PATH/x86_64-linux"
fi
export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/lib64:$CANN_ARCH_DIR/lib64:${LD_LIBRARY_PATH:-}"

ASC_ARCH="${ASC_ARCH:-dav-2201}"
KERNEL_NAME="${KERNEL_NAME:-fast_gelu_kernel}"

find_repo_root() {
  local dir="$SCRIPT_DIR"
  while [ "$dir" != "/" ]; do
    if [ -d "$dir/.git" ] || [ -d "$dir/skills/aprof" ]; then
      printf "%s\n" "$dir"
      return
    fi
    dir="$(dirname "$dir")"
  done
  printf "%s\n" "$SCRIPT_DIR"
}

bench_name="$(basename "$(dirname "$SCRIPT_DIR")")"
if [ "$bench_name" = "operators" ]; then
  bench_name="$(basename "$(dirname "$(dirname "$SCRIPT_DIR")")")"
fi
case_id="$(basename "$SCRIPT_DIR")"
APROF_REPO_ROOT="${APROF_REPO_ROOT:-$(find_repo_root)}"
APROF_TMP_ROOT="${APROF_TMP_ROOT:-$APROF_REPO_ROOT/tmp/aprof}"
APROF_CASE_TMP="${APROF_CASE_TMP:-$APROF_TMP_ROOT/aprof_injected_ops/$bench_name/$case_id}"
APROF_MSPROF_OUTPUT="${APROF_MSPROF_OUTPUT:-$APROF_CASE_TMP/msprof_hw_output}"
APROF_MSPROF_SIM_OUTPUT="${APROF_MSPROF_SIM_OUTPUT:-$APROF_CASE_TMP/msprof_sim_output}"

case "$MODE" in
  gen)
    python3 scripts/gen_data.py "$@"
    ;;
  build)
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_ASC_ARCHITECTURES="$ASC_ARCH"
    cmake --build build -j"$(nproc)"
    ;;
  run)
    mkdir -p build/output
    (cd build && "./$TARGET_NAME" "$@")
    ;;
  verify)
    python3 scripts/verify_result.py "$@"
    ;;
  sim-build)
    python3 scripts/gen_data.py "$@"
    mkdir -p build_sim
    "$ASCEND_HOME_PATH/bin/bisheng" -fPIC --aicore-only --npu-arch="$ASC_ARCH" -O2 -g \
      -I op_kernel \
      -I "$ASCEND_HOME_PATH/include" \
      -I "$CANN_ARCH_DIR/include" \
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
      -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
      --asc-aicore-lang -c "op_kernel/${KERNEL_NAME}.asc" \
      -o "build_sim/${KERNEL_NAME}.obj"
    "$ASCEND_HOME_PATH/bin/ld.lld" -m aicorelinux -Ttext=0 "build_sim/${KERNEL_NAME}.obj" -static -o "build_sim/${KERNEL_NAME}.o"
    if command -v file >/dev/null 2>&1; then file "build_sim/${KERNEL_NAME}.o"; fi
    ;;
  sim)
    mkdir -p "$APROF_MSPROF_SIM_OUTPUT" build_sim
    rm -rf "$APROF_MSPROF_SIM_OUTPUT"/OPPROF_*
    chmod 700 "$APROF_MSPROF_SIM_OUTPUT" build_sim
    chmod u=rw,go= build_sim/* 2>/dev/null || true
    (cd build_sim && msprof op simulator --config=./op_config.json --output="$APROF_MSPROF_SIM_OUTPUT" --timeout="${MSPROF_TIMEOUT:-5}")
    ;;
  profile)
    "$SCRIPT_DIR/run.sh" build
    "$SCRIPT_DIR/run.sh" gen "$@"
    rm -rf "$APROF_MSPROF_OUTPUT"
    mkdir -p "$APROF_MSPROF_OUTPUT"
    (cd build && msprof --application="./$TARGET_NAME" --output="$APROF_MSPROF_OUTPUT" \
      --aic-metrics="${APROF_AIC_METRICS:-PipeUtilization}" --task-time=on --runtime-api=on)
    ;;
  hw)
    # Onboard msprof op path (Task Duration from OpBasicInfo.csv), compatible with prior inject HW runs.
    "$SCRIPT_DIR/run.sh" gen "$@"
    "$SCRIPT_DIR/run.sh" sim-build "$@"
    python3 - <<'PY'
import json
from pathlib import Path
cfg = Path("build_sim/op_config.json")
data = json.loads(cfg.read_text(encoding="utf-8"))
data["mode"] = "onboard"
cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("op_config mode=onboard")
PY
    rm -rf "$APROF_MSPROF_OUTPUT"
    mkdir -p "$APROF_MSPROF_OUTPUT"
    chmod 700 "$APROF_MSPROF_OUTPUT" build_sim
    chmod u=rw,go= build_sim/* 2>/dev/null || true
    (
      cd build_sim &&
      msprof op --config=./op_config.json \
        --warm-up="${MSPROF_WARMUP:-3}" \
        --launch-count="${MSPROF_LAUNCH_COUNT:-1}" \
        --aic-metrics="${APROF_AIC_METRICS:-PipeUtilization}" \
        --output="$APROF_MSPROF_OUTPUT"
    )
    ;;
  all)
    "$SCRIPT_DIR/run.sh" build
    "$SCRIPT_DIR/run.sh" gen "$@"
    "$SCRIPT_DIR/run.sh" run
    "$SCRIPT_DIR/run.sh" verify
    ;;
  *)
    echo "usage: $0 [gen|build|run|verify|sim-build|sim|profile|hw|all]"
    exit 2
    ;;
esac

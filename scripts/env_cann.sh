#!/usr/bin/env bash
# Export CANN / Ascend runtime paths.
#
# Usage:
#   source scripts/env_cann.sh
#
# This script is intentionally lightweight: it only exports paths and sources
# CANN's set_env.sh when available. It does not enable strict shell modes and it
# does not exit your interactive terminal.

export ASCEND_CANN_ROOT="${ASCEND_CANN_ROOT:-/rshome/jieran.zhang/Ascend/ascend-toolkit}"
export ASCEND_SOC_VERSION="${ASCEND_SOC_VERSION:-Ascend910B1}"

# CANN's set_env.sh may be sourced from a strict-mode shell (`set -u`) and
# references these variables directly. Initialize them to empty strings so
# source scripts/setup_env.sh remains robust in a clean shell.
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${PYTHONPATH:-}"
export PATH="${PATH:-}"

aprof_prepend_ld_path() {
  if [ -d "$1" ]; then
    case ":${LD_LIBRARY_PATH:-}:" in
      *":$1:"*) ;;
      *) export LD_LIBRARY_PATH="$1:${LD_LIBRARY_PATH:-}" ;;
    esac
  fi
}

if [ -f "${ASCEND_CANN_ROOT}/set_env.sh" ]; then
  # shellcheck disable=SC1091
  source "${ASCEND_CANN_ROOT}/set_env.sh"
fi

if [ -n "${ASCEND_TOOLKIT_HOME:-}" ]; then
  sim_lib="${ASCEND_TOOLKIT_HOME}/tools/simulator/${ASCEND_SOC_VERSION}/lib"
  aprof_prepend_ld_path "${sim_lib}"
  aprof_prepend_ld_path "${ASCEND_TOOLKIT_HOME}/runtime/lib64"
fi

if [ -n "${ASCEND_DRIVER_PATH:-}" ]; then
  aprof_prepend_ld_path "${ASCEND_DRIVER_PATH}"
  aprof_prepend_ld_path "${ASCEND_DRIVER_PATH}/lib64"
  aprof_prepend_ld_path "${ASCEND_DRIVER_PATH}/lib64/driver"
  aprof_prepend_ld_path "${ASCEND_DRIVER_PATH}/driver/lib64"
  aprof_prepend_ld_path "${ASCEND_DRIVER_PATH}/tools/dcmi"
fi

if [ -n "${ASCEND_RUNTIME_PATH:-}" ]; then
  aprof_prepend_ld_path "${ASCEND_RUNTIME_PATH}"
  aprof_prepend_ld_path "${ASCEND_RUNTIME_PATH}/lib64"
  aprof_prepend_ld_path "${ASCEND_RUNTIME_PATH}/lib64/driver"
  aprof_prepend_ld_path "${ASCEND_RUNTIME_PATH}/driver/lib64"
  aprof_prepend_ld_path "${ASCEND_RUNTIME_PATH}/tools/dcmi"
fi

aprof_prepend_ld_path "/usr/local/Ascend/driver/lib64"
aprof_prepend_ld_path "/usr/local/Ascend/driver/lib64/driver"
aprof_prepend_ld_path "/usr/local/Ascend/driver/tools/dcmi"
aprof_prepend_ld_path "/usr/local/Ascend/runtime/lib64"
aprof_prepend_ld_path "${HOME}/Ascend/driver/lib64"
aprof_prepend_ld_path "${HOME}/Ascend/driver/lib64/driver"
aprof_prepend_ld_path "${HOME}/Ascend/driver/tools/dcmi"
aprof_prepend_ld_path "${PWD}/out/lib"
aprof_prepend_ld_path "${PWD}/out/lib64"

if [ "${APROF_CANN_CHECK_LIBS:-0}" = "1" ] && ! python3 - <<'PY' >/dev/null 2>&1
import os
from pathlib import Path

entries = [Path(item) for item in os.environ.get("LD_LIBRARY_PATH", "").split(":") if item]
missing = []
for name in ("libascend_hal.so", "libdcmi.so"):
    if not any((entry / name).exists() or list(entry.glob(f"{name}*")) for entry in entries if entry.exists()):
        missing.append(name)
raise SystemExit(1 if missing else 0)
PY
then
  echo "[AProf WARNING] Ascend driver/runtime libraries are not fully visible; real msprof simulator may fail to load libascend_hal.so or libdcmi.so." >&2
  echo "[AProf WARNING] Set ASCEND_DRIVER_PATH or ASCEND_RUNTIME_PATH before sourcing this script if the driver/runtime is mounted elsewhere." >&2
fi

echo "[env_cann] ASCEND_CANN_ROOT=${ASCEND_CANN_ROOT}" >&2
echo "[env_cann] ASCEND_TOOLKIT_HOME=${ASCEND_TOOLKIT_HOME:-unset}" >&2
echo "[env_cann] ASCEND_HOME_PATH=${ASCEND_HOME_PATH:-unset}" >&2
echo "[env_cann] ASCEND_SOC_VERSION=${ASCEND_SOC_VERSION}" >&2

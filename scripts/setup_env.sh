#!/usr/bin/env bash
# Set up the local AProf / CodingAgent development environment.
#
# Recommended usage:
#   source scripts/setup_env.sh --install
#
# Notes:
# - Use `source`, not `bash`, if you want `conda activate cann` and PYTHONPATH
#   to remain active in your current terminal.
# - This script never writes API keys. Export DASHSCOPE_API_KEY or OPENAI_API_KEY
#   in your shell before running model calls.
# - CANN/msprof setup uses the CANN package installed in the conda env by default.

_aprof_setup_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

_aprof_setup_log() {
    printf '[setup_env] %s\n' "$*" >&2
}

_aprof_setup_die() {
    _aprof_setup_log "ERROR: $*"
    if _aprof_setup_is_sourced; then
        return 1
    fi
    exit 1
}

_aprof_setup_prepend_path() {
    local var_name="$1"
    local path_value="$2"

    [[ -d "${path_value}" ]] || return 0

    local current_value="${!var_name:-}"
    case ":${current_value}:" in
        *":${path_value}:"*) ;;
        *) export "${var_name}=${path_value}${current_value:+:${current_value}}" ;;
    esac
}

APROF_SETUP_INSTALL=0
APROF_SETUP_CHECK_ONLY=0
APROF_SETUP_CONDA_ENV="${APROF_SETUP_CONDA_ENV:-cann}"
APROF_SETUP_CONDA_ROOT="${APROF_SETUP_CONDA_ROOT:-/rshome/jieran.zhang/anaconda3}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install)
            APROF_SETUP_INSTALL=1
            shift
            ;;
        --check-only)
            APROF_SETUP_CHECK_ONLY=1
            shift
            ;;
        --conda-env)
            APROF_SETUP_CONDA_ENV="${2:-}"
            [[ -n "${APROF_SETUP_CONDA_ENV}" ]] || _aprof_setup_die "--conda-env requires a value"
            shift 2
            ;;
        --conda-root)
            APROF_SETUP_CONDA_ROOT="${2:-}"
            [[ -n "${APROF_SETUP_CONDA_ROOT}" ]] || _aprof_setup_die "--conda-root requires a value"
            shift 2
            ;;
        -h|--help)
            cat >&2 <<'EOF'
Usage:
  source scripts/setup_env.sh [--install] [--check-only] [--conda-env cann] [--conda-root PATH]

Options:
  --install          Run `python -m pip install -e .` after activating conda env.
  --check-only       Only print diagnostics; do not install dependencies.
  --conda-env NAME   Conda env name. Default: cann.
  --conda-root PATH  Conda root. Default: /rshome/jieran.zhang/anaconda3.

Environment variables:
  APROF_SETUP_CONDA_ENV   Override default conda env.
  APROF_SETUP_CONDA_ROOT  Override default conda root.
  ASCEND_CANN_ROOT        Optional CANN install root. Default: $CONDA_PREFIX/Ascend/ascend-toolkit.
  SOC_VERSION             Optional simulator SoC version. Default: Ascend950.
  ASCEND_SOC_VERSION      Optional simulator SoC version alias. Default: SOC_VERSION.
  ASCEND_HOME_PATH        Optional CANN install root fallback after set_env.sh.
  DASHSCOPE_API_KEY       Required for DashScope model calls.
  OPENAI_API_KEY          Alternative OpenAI-compatible API key.
  OPENAI_BASE_URL         Optional API base URL override.
  CANNBOT_MODEL           Optional model name override.
EOF
            if _aprof_setup_is_sourced; then
                return 0
            fi
            exit 0
            ;;
        *)
            _aprof_setup_die "Unknown argument: $1"
            ;;
    esac
done

APROF_SETUP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APROF_REPO_ROOT="$(cd "${APROF_SETUP_SCRIPT_DIR}/.." && pwd)"
export APROF_REPO_ROOT

_aprof_setup_log "repo root: ${APROF_REPO_ROOT}"

if [[ -f "${APROF_SETUP_CONDA_ROOT}/etc/profile.d/conda.sh" ]]; then
    # shellcheck disable=SC1090
    source "${APROF_SETUP_CONDA_ROOT}/etc/profile.d/conda.sh"
else
    _aprof_setup_die "conda.sh not found under ${APROF_SETUP_CONDA_ROOT}; pass --conda-root PATH"
fi

conda activate "${APROF_SETUP_CONDA_ENV}"
_aprof_setup_log "conda env: ${CONDA_DEFAULT_ENV:-unknown}"
_aprof_setup_log "python: $(command -v python)"

cd "${APROF_REPO_ROOT}"

export PYTHONPATH="${APROF_REPO_ROOT}:${APROF_REPO_ROOT}/agents:${PYTHONPATH:-}"
_aprof_setup_log "PYTHONPATH includes repo root and agents/"

export ASCEND_CANN_ROOT="${ASCEND_CANN_ROOT:-${CONDA_PREFIX}/Ascend/ascend-toolkit}"

if [[ -f "${ASCEND_CANN_ROOT}/set_env.sh" ]]; then
    # shellcheck disable=SC1090
    source "${ASCEND_CANN_ROOT}/set_env.sh"
    _aprof_setup_log "sourced CANN env: ${ASCEND_CANN_ROOT}/set_env.sh"
elif [[ -f "${CONDA_PREFIX}/Ascend/cann/set_env.sh" ]]; then
    export ASCEND_CANN_ROOT="${CONDA_PREFIX}/Ascend/cann"
    # shellcheck disable=SC1090
    source "${ASCEND_CANN_ROOT}/set_env.sh"
    _aprof_setup_log "sourced CANN env: ${ASCEND_CANN_ROOT}/set_env.sh"
elif [[ -n "${ASCEND_HOME_PATH:-}" && -f "${ASCEND_HOME_PATH}/set_env.sh" ]]; then
    export ASCEND_CANN_ROOT="${ASCEND_HOME_PATH}"
    # shellcheck disable=SC1090
    source "${ASCEND_HOME_PATH}/set_env.sh"
    _aprof_setup_log "sourced legacy CANN env: ${ASCEND_HOME_PATH}/set_env.sh"
else
    _aprof_setup_log "CANN set_env.sh not found; CANN/msprof checks may be unavailable"
fi

export SOC_VERSION="${SOC_VERSION:-${ASCEND_SOC_VERSION:-Ascend950}}"
export ASCEND_SOC_VERSION="${ASCEND_SOC_VERSION:-${SOC_VERSION}}"

APROF_SETUP_SIM_BASE="${ASCEND_HOME_PATH:-${ASCEND_TOOLKIT_HOME:-${ASCEND_CANN_ROOT}/latest}}/tools/simulator"
APROF_SETUP_SIM_LIB="${APROF_SETUP_SIM_BASE}/${SOC_VERSION}/lib"

if [[ ! -d "${APROF_SETUP_SIM_LIB}" && "${SOC_VERSION}" == Ascend950 ]]; then
    for APROF_SETUP_SIM_CANDIDATE in "${APROF_SETUP_SIM_BASE}"/Ascend950*/lib; do
        if [[ -d "${APROF_SETUP_SIM_CANDIDATE}" ]]; then
            APROF_SETUP_SIM_LIB="${APROF_SETUP_SIM_CANDIDATE}"
            break
        fi
    done
fi

_aprof_setup_prepend_path LD_LIBRARY_PATH "${APROF_SETUP_SIM_LIB}"
_aprof_setup_log "SOC_VERSION=${SOC_VERSION}"
if [[ -d "${APROF_SETUP_SIM_LIB}" ]]; then
    _aprof_setup_log "simulator lib: ${APROF_SETUP_SIM_LIB}"
else
    _aprof_setup_log "simulator lib not found: ${APROF_SETUP_SIM_LIB}"
fi

if [[ "${APROF_SETUP_INSTALL}" -eq 1 && "${APROF_SETUP_CHECK_ONLY}" -eq 0 ]]; then
    _aprof_setup_log "installing project dependencies: python -m pip install -e ."
    python -m pip install -e .
fi

python - <<'PY'
import importlib.util
import os
import sys

checks = {
    "openai": importlib.util.find_spec("openai") is not None,
    "aprof": importlib.util.find_spec("aprof") is not None,
    "CodingAgent": importlib.util.find_spec("CodingAgent") is not None,
}

print("[setup_env] python version:", sys.version.split()[0])
for name, ok in checks.items():
    print(f"[setup_env] import {name}: {'ok' if ok else 'missing'}")

api_key_present = bool(os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY"))
print("[setup_env] API key:", "set" if api_key_present else "missing (export DASHSCOPE_API_KEY or OPENAI_API_KEY)")
print("[setup_env] OPENAI_BASE_URL:", os.getenv("OPENAI_BASE_URL", "default DashScope compatible URL"))
print("[setup_env] CANNBOT_MODEL:", os.getenv("CANNBOT_MODEL", "deepseek-v4-pro"))
print("[setup_env] ASCEND_CANN_ROOT:", os.getenv("ASCEND_CANN_ROOT", "unset"))
print("[setup_env] ASCEND_TOOLKIT_HOME:", os.getenv("ASCEND_TOOLKIT_HOME", "unset"))
print("[setup_env] ASCEND_HOME_PATH:", os.getenv("ASCEND_HOME_PATH", "unset"))
print("[setup_env] SOC_VERSION:", os.getenv("SOC_VERSION", "unset"))
print("[setup_env] ASCEND_SOC_VERSION:", os.getenv("ASCEND_SOC_VERSION", "unset"))
PY

_aprof_setup_log "ready"

if ! _aprof_setup_is_sourced; then
    _aprof_setup_log "script was executed directly; conda activation will not persist in parent shell"
    _aprof_setup_log "run this instead: source scripts/setup_env.sh --install"
fi

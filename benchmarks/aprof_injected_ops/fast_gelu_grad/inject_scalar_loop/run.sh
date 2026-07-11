#!/usr/bin/env bash
set -euo pipefail
OP_NAME="fast_gelu_grad"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INJECT_RUN="${APROF_INJECT_RUN:-$SCRIPT_DIR/../../common/inject_run.sh}"
# shellcheck disable=SC1090
source "$INJECT_RUN" "$@"

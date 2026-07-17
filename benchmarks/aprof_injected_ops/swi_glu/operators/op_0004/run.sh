#!/usr/bin/env bash
set -euo pipefail
TARGET_NAME="swi_glu_op_0004"
KERNEL_NAME="swi_glu_kernel"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../common/run_direct_invoke.sh" ]; then
  COMMON_RUN="$SCRIPT_DIR/../common/run_direct_invoke.sh"
else
  COMMON_RUN="$SCRIPT_DIR/../../common/run_direct_invoke.sh"
fi
# shellcheck disable=SC1090
source "$COMMON_RUN" "$@"

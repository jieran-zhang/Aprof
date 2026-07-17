#!/usr/bin/env bash
set -euo pipefail
TARGET_NAME="mish_op_0002"
KERNEL_NAME="mish_kernel"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../common/run_direct_invoke.sh" ]; then
  COMMON_RUN="$SCRIPT_DIR/../common/run_direct_invoke.sh"
else
  COMMON_RUN="$SCRIPT_DIR/../../common/run_direct_invoke.sh"
fi
# shellcheck disable=SC1090
source "$COMMON_RUN" "$@"

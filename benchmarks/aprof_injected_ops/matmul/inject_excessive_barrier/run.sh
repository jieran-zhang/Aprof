#!/usr/bin/env bash
set -euo pipefail
OP_NAME="matmul"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INJECT_RUN="${APROF_INJECT_RUN:-$SCRIPT_DIR/../../common/inject_run.sh}"
source "$INJECT_RUN" "$@"

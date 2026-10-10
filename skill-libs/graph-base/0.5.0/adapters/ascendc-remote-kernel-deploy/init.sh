#!/usr/bin/env bash
set -euo pipefail
APROF_RELEASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python3 "$APROF_RELEASE_ROOT/tools/install.py" --with-remote "$@"

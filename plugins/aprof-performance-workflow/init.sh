#!/usr/bin/env bash
# Install registry-selected AProf capabilities into Cursor project config.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

exec python3 "$REPO_ROOT/scripts/sync_aprof_registry.py" \
  --repo-root "$REPO_ROOT" install "$@"

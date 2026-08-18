#!/usr/bin/env bash
# Compatibility entry: install registry-selected AProf and support skills.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "link_cannbot_skills.sh now follows skillgraph/registry.json" >&2
exec python3 "$REPO_ROOT/scripts/sync_aprof_registry.py" \
  --repo-root "$REPO_ROOT" install "$@"

#!/usr/bin/env bash
# Install the optional remote adapter through the canonical AProf registry.
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/../../.." && pwd)"

exec python3 "$REPO_ROOT/scripts/sync_aprof_registry.py" \
  --repo-root "$REPO_ROOT" install --with-remote "$@"

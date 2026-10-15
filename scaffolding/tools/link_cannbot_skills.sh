#!/usr/bin/env bash
# Legacy command name; all skills now belong to the selected AProf release.
set -euo pipefail
: "${APROF_SKILL_LIB:?Set APROF_SKILL_LIB to an explicit release}"
exec python3 "$APROF_SKILL_LIB/tools/install.py" --skills-dir "$PWD/.cursor/skills" "$@"

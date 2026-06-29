#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANNBOT_ROOT="$ROOT/third_party/cannbot-skills"
CURSOR_SKILLS="$ROOT/.cursor/skills"

if [[ ! -d "$CANNBOT_ROOT/ops" ]]; then
  echo "CANNBot skills submodule is missing."
  echo "Run: git submodule update --init --recursive"
  exit 1
fi

mkdir -p "$CURSOR_SKILLS"

link_dir() {
  local category="$1"
  local src_root="$CANNBOT_ROOT/$category"
  [[ -d "$src_root" ]] || return 0
  local skill
  for skill in "$src_root"/*; do
    [[ -d "$skill" && -f "$skill/SKILL.md" ]] || continue
    local name
    name="$(basename "$skill")"
    local dest="$CURSOR_SKILLS/${category}-${name}"
    ln -sfn "$skill" "$dest"
    echo "linked $dest -> $skill"
  done
}

link_dir ops
link_dir graph
link_dir model
link_dir infra
link_dir ops-lab

# AProf-local skills stay alongside CANNBot skills.
for skill in "$ROOT/skills/aprof"/*; do
  [[ -d "$skill" && -f "$skill/SKILL.md" ]] || continue
  name="$(basename "$skill")"
  dest="$CURSOR_SKILLS/aprof-${name}"
  ln -sfn "$skill" "$dest"
  echo "linked $dest -> $skill"
done

echo "Done. Cursor skills are available under $CURSOR_SKILLS"

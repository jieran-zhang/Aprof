#!/usr/bin/env bash
# Install aprof-remote-kernel-deploy agent into Cursor (.cursor/skills + .cursor/agents).
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../../.." && pwd)"
CURSOR_DIR="$REPO_ROOT/.cursor"
SKILLS_DIR="$CURSOR_DIR/skills"
AGENTS_DIR="$CURSOR_DIR/agents"
CANNBOT_OPS="$REPO_ROOT/third_party/cannbot-skills/ops"

mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

link_skill() {
  local src="$1"
  local dest_name="$2"
  if [[ ! -f "$src/SKILL.md" ]]; then
    echo "skip skill (no SKILL.md): $src"
    return 0
  fi
  ln -sfn "$(realpath "$src")" "$SKILLS_DIR/$dest_name"
  echo "linked $SKILLS_DIR/$dest_name -> $src"
}

link_agent() {
  local src="$1"
  local dest_name="$2"
  ln -sfn "$(realpath "$src")" "$AGENTS_DIR/$dest_name"
  echo "linked $AGENTS_DIR/$dest_name -> $src"
}

# Core skill (this plugin directory)
link_skill "$PLUGIN_ROOT" "aprof-ascendc-remote-kernel-deploy"

# Companion skills referenced in AGENTS.md
if [[ -d "$REPO_ROOT/skills/aprof/benchmark/ascendc-msprof-simulator" ]]; then
  link_skill "$REPO_ROOT/skills/aprof/benchmark/ascendc-msprof-simulator" "aprof-ascendc-msprof-simulator"
fi

if [[ -d "$CANNBOT_OPS/ops-profiling" ]]; then
  link_skill "$CANNBOT_OPS/ops-profiling" "ops-profiling"
else
  echo "warn: third_party/cannbot-skills/ops/ops-profiling missing; run git submodule update --init"
fi

# Primary agent + subagent
link_agent "$PLUGIN_ROOT/AGENTS.md" "aprof-remote-kernel-deploy"
link_agent "$PLUGIN_ROOT/agents/aprof-remote-deployer.md" "aprof-remote-deployer"

cat > "$CURSOR_DIR/aprof-remote-kernel-deploy-manifest.json" <<EOF
{
  "plugin": "aprof-remote-kernel-deploy",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "skills": [
    "aprof-ascendc-remote-kernel-deploy",
    "aprof-ascendc-msprof-simulator",
    "ops-profiling"
  ],
  "agents": [
    "aprof-remote-kernel-deploy",
    "aprof-remote-deployer"
  ]
}
EOF

echo "Done. Invoke @aprof-remote-kernel-deploy in Cursor, or load /ascendc-remote-kernel-deploy"

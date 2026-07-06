#!/usr/bin/env bash
# Install AProf performance workflow plugin into Cursor project config.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"
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
  if [[ ! -f "$src" ]]; then
    echo "skip agent (missing): $src"
    return 0
  fi
  ln -sfn "$(realpath "$src")" "$AGENTS_DIR/$dest_name"
  echo "linked $AGENTS_DIR/$dest_name -> $src"
}

link_skill "$REPO_ROOT/skills/aprof/diagnosis" "aprof-ascendc-diagnosis"
link_skill "$REPO_ROOT/skills/aprof/profiling" "aprof-ascendc-profiling"
link_skill "$REPO_ROOT/skills/aprof/remote-kernel-deploy" "aprof-ascendc-remote-kernel-deploy"
link_skill "$REPO_ROOT/skills/aprof/benchmark/ascendc-msprof-simulator" "aprof-ascendc-msprof-simulator"

if [[ -d "$CANNBOT_OPS/ops-profiling" ]]; then
  link_skill "$CANNBOT_OPS/ops-profiling" "ops-profiling"
else
  echo "warn: third_party/cannbot-skills/ops/ops-profiling missing; run git submodule update --init"
fi

if [[ -d "$CANNBOT_OPS/npu-arch" ]]; then
  link_skill "$CANNBOT_OPS/npu-arch" "npu-arch"
else
  echo "warn: third_party/cannbot-skills/ops/npu-arch missing; run git submodule update --init"
fi

link_agent "$REPO_ROOT/skills/aprof/diagnosis/AGENTS.md" "aprof-diagnosis-agent"
link_agent "$REPO_ROOT/skills/aprof/profiling/AGENTS.md" "aprof-profiling-agent"
link_agent "$REPO_ROOT/skills/aprof/remote-kernel-deploy/AGENTS.md" "aprof-remote-kernel-deploy"
link_agent "$REPO_ROOT/skills/aprof/remote-kernel-deploy/agents/aprof-remote-deployer.md" "aprof-remote-deployer"

link_agent "$PLUGIN_ROOT/AGENTS.md" "aprof-performance-workflow"
for agent in "$PLUGIN_ROOT"/agents/*.md; do
  name="$(basename "$agent" .md)"
  link_agent "$agent" "$name"
done

cat > "$CURSOR_DIR/aprof-performance-workflow-manifest.json" <<EOF
{
  "plugin": "aprof-performance-workflow",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "skills": [
    "aprof-ascendc-diagnosis",
    "aprof-ascendc-profiling",
    "aprof-ascendc-remote-kernel-deploy",
    "aprof-ascendc-msprof-simulator",
    "ops-profiling",
    "npu-arch"
  ],
  "agents": [
    "aprof-performance-workflow",
    "aprof-diagnosis-agent",
    "aprof-profiling-agent",
    "aprof-remote-kernel-deploy",
    "aprof-remote-deployer",
    "aprof-diagnosis-wrapper",
    "aprof-profiling-wrapper",
    "aprof-remote-wrapper"
  ]
}
EOF

echo "Done. Invoke @aprof-performance-workflow in Cursor."

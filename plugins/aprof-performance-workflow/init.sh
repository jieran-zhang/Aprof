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

link_cannbot_skill() {
  local name="$1"
  if [[ -d "$CANNBOT_OPS/$name" ]]; then
    link_skill "$CANNBOT_OPS/$name" "$name"
  else
    echo "warn: third_party/cannbot-skills/ops/$name missing; run git submodule update --init"
  fi
}

link_skill "$REPO_ROOT/skills/aprof/diagnosis" "aprof-ascendc-diagnosis"
link_skill "$REPO_ROOT/skills/aprof/profiling" "aprof-ascendc-profiling"
link_skill "$REPO_ROOT/skills/aprof/optimization" "aprof-ascendc-optimization"
link_skill "$REPO_ROOT/skills/aprof/benchmark/ascendc-kernel-direct-invoke" "aprof-ascendc-kernel-direct-invoke"

for skill in \
  ascendc-env-check \
  ascendc-perf-optimize \
  ascendc-tiling-design \
  ascendc-performance-best-practices \
  ascendc-api-best-practices \
  ascendc-docs-search \
  ascendc-code-review \
  ascendc-precision-debug \
  ascendc-runtime-debug \
  ascendc-crash-debug \
  ops-profiling \
  ops-simulator \
  npu-arch
do
  link_cannbot_skill "$skill"
done

link_agent "$REPO_ROOT/skills/aprof/diagnosis/AGENTS.md" "aprof-diagnosis-agent"
link_agent "$REPO_ROOT/skills/aprof/profiling/AGENTS.md" "aprof-profiling-agent"
link_agent "$REPO_ROOT/skills/aprof/optimization/AGENTS.md" "aprof-optimization-agent"

link_agent "$PLUGIN_ROOT/AGENTS.md" "aprof-performance-workflow"
link_agent "$PLUGIN_ROOT/agents/aprof-diagnosis-wrapper.md" "aprof-diagnosis-wrapper"
link_agent "$PLUGIN_ROOT/agents/aprof-profiling-wrapper.md" "aprof-profiling-wrapper"
link_agent "$PLUGIN_ROOT/agents/aprof-optimization-wrapper.md" "aprof-optimization-wrapper"

cat > "$CURSOR_DIR/aprof-performance-workflow-manifest.json" <<EOF
{
  "plugin": "aprof-performance-workflow",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "skills": [
    "aprof-ascendc-diagnosis",
    "aprof-ascendc-profiling",
    "aprof-ascendc-optimization",
    "aprof-ascendc-kernel-direct-invoke",
    "ascendc-env-check",
    "ascendc-perf-optimize",
    "ascendc-tiling-design",
    "ascendc-performance-best-practices",
    "ascendc-api-best-practices",
    "ascendc-docs-search",
    "ascendc-code-review",
    "ascendc-precision-debug",
    "ascendc-runtime-debug",
    "ascendc-crash-debug",
    "ops-profiling",
    "ops-simulator",
    "npu-arch"
  ],
  "agents": [
    "aprof-performance-workflow",
    "aprof-diagnosis-agent",
    "aprof-profiling-agent",
    "aprof-optimization-agent",
    "aprof-diagnosis-wrapper",
    "aprof-profiling-wrapper",
    "aprof-optimization-wrapper"
  ]
}
EOF

echo "Done. Invoke @aprof-performance-workflow in Cursor."

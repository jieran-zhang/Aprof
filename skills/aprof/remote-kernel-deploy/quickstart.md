# AProf Remote Kernel Deploy — Quickstart

## CANNBot 里 Skill 与 Agent 的关系

```
SKILL（SKILL.md）     知识 + 工具 + SOP，被动加载
    ↑ 绑定
AGENT（AGENTS.md）    编排器：何时加载哪些 skill、调度 subagent
    ↑ 可选
agents/*.md           Subagent：执行层角色（mode: subagent）
    ↑ 安装
init.sh               软链到 .cursor/skills、.cursor/agents
```

CANNBot **没有** `agent.json`；Agent 全是 Markdown + YAML frontmatter。

参考：`third_party/cannbot-skills/plugins-official/ops-registry-invoke/`

## 安装到 Cursor（AProf 项目）

```bash
bash skills/aprof/remote-kernel-deploy/init.sh
```

效果：

- `.cursor/skills/ascendc-remote-kernel-deploy` → 本目录 SKILL
- `.cursor/skills/ops-profiling` → CANNBot ops-profiling
- `.cursor/agents/aprof-remote-kernel-deploy` → `AGENTS.md`
- `.cursor/agents/aprof-remote-deployer` → `agents/aprof-remote-deployer.md`

## 使用

在 Cursor Agent 对话中：

```
@aprof-remote-kernel-deploy 帮我把 benchmarks/aprof_injected_ops/fast_gelu/baseline 部署到远程并跑 simulator msprof
```

或显式加载 skill：

```
/ascendc-remote-kernel-deploy
```

## 与 CANNBot 官方 Plugin 的差异

| 项 | CANNBot Plugin | 本 Agent |
|----|----------------|----------|
| 位置 | `plugins-official/*/` | `skills/aprof/remote-kernel-deploy/` |
| 安装 | `bash init.sh project cursor <dir>` | 仓库内精简 `init.sh` |
| 范围 | 完整算子开发 Team | 仅远程部署 + msprof 采集 |

## 依赖

- `pip install paramiko`
- `scripts/server_config.json`
- 上板模式：`third_party/cannbot-skills` 子模块（ops-profiling 脚本）

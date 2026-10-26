# 本轮源码与入口变化

以下以任务开始的实际工作树为基线，不将已有未提交维护误计为本轮修改。完整新验收数据单列在本目录，原知识树、历史schema和1.2.0身份见保护检查。此表只列技能包内文件；包外维护说明和开发验收工作区不构成运行依赖。

| 文件 | 本轮状态 |
| --- | --- |
| [README.md](../../../../skill-libs/graph-base/1.3.1/README.md) | modified |
| [runtime/pyproject.toml](../../../../skill-libs/graph-base/1.3.1/runtime/pyproject.toml) | modified |
| [runtime/src/aprof_runtime/__init__.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/__init__.py) | modified |
| [runtime/src/aprof_runtime/action_decision.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/action_decision.py) | modified |
| [runtime/src/aprof_runtime/action_decision_v3.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/action_decision_v3.py) | added |
| [runtime/src/aprof_runtime/bindings.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/bindings.py) | modified |
| [runtime/src/aprof_runtime/bindings_v4.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/bindings_v4.py) | added |
| [runtime/src/aprof_runtime/cli.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/cli.py) | modified |
| [runtime/src/aprof_runtime/knowledge_outcome.py](../../../../skill-libs/graph-base/1.3.1/runtime/src/aprof_runtime/knowledge_outcome.py) | added |
| [runtime/tests/test_action_decision_v3.py](../../../../skill-libs/graph-base/1.3.1/runtime/tests/test_action_decision_v3.py) | added |
| [runtime/tests/test_action_handoff_v4.py](../../../../skill-libs/graph-base/1.3.1/runtime/tests/test_action_handoff_v4.py) | added |
| [runtime/tests/test_diagnosis_integration_v130.py](../../../../skill-libs/graph-base/1.3.1/runtime/tests/test_diagnosis_integration_v130.py) | modified |
| [runtime/tests/test_scheme_cli.py](../../../../skill-libs/graph-base/1.3.1/runtime/tests/test_scheme_cli.py) | added |
| [schemas/README.md](../../../../skill-libs/graph-base/1.3.1/schemas/README.md) | modified |
| [schemas/action-decision-v3.schema.json](../../../../skill-libs/graph-base/1.3.1/schemas/action-decision-v3.schema.json) | added |
| [schemas/knowledge-handoff-v4.schema.json](../../../../skill-libs/graph-base/1.3.1/schemas/knowledge-handoff-v4.schema.json) | added |
| [skills/ascendc-aprof-coordinator/SKILL.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-coordinator/SKILL.md) | modified |
| [skills/ascendc-aprof-diagnosis/SKILL.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-diagnosis/SKILL.md) | modified |
| [skills/ascendc-aprof-optimization/SKILL.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/SKILL.md) | modified |
| [skills/ascendc-aprof-parallel-planning/SKILL.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/SKILL.md) | modified |
| [skills/registry.json](../../../../skill-libs/graph-base/1.3.1/skills/registry.json) | modified |
| [tools/release.py](../../../../skill-libs/graph-base/1.3.1/tools/release.py) | modified |
| [workflows/agents/coordinator.md](../../../../skill-libs/graph-base/1.3.1/workflows/agents/coordinator.md) | modified |
| [workflows/agents/diagnosis.md](../../../../skill-libs/graph-base/1.3.1/workflows/agents/diagnosis.md) | modified |
| [workflows/agents/optimization.md](../../../../skill-libs/graph-base/1.3.1/workflows/agents/optimization.md) | modified |
| [workflows/agents/parallel-planning.md](../../../../skill-libs/graph-base/1.3.1/workflows/agents/parallel-planning.md) | modified |
| [workflows/aprof-performance-workflow.md](../../../../skill-libs/graph-base/1.3.1/workflows/aprof-performance-workflow.md) | modified |
| [workflows/contracts/candidate.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/candidate.md) | modified |
| [workflows/contracts/common.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/common.md) | modified |
| [workflows/contracts/decision.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/decision.md) | modified |
| [workflows/contracts/diagnosis.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/diagnosis.md) | modified |
| [workflows/contracts/planning.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/planning.md) | modified |
| [workflows/contracts/preparation.md](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/preparation.md) | modified |
| [workflows/references/action-decision-v3.md](../../../../skill-libs/graph-base/1.3.1/workflows/references/action-decision-v3.md) | added |
| [workflows/references/action-selection.md](../../../../skill-libs/graph-base/1.3.1/workflows/references/action-selection.md) | modified |
| [workflows/references/optimization-history.md](../../../../skill-libs/graph-base/1.3.1/workflows/references/optimization-history.md) | added |
| [workflows/references/optimization-schemes.md](../../../../skill-libs/graph-base/1.3.1/workflows/references/optimization-schemes.md) | added |
| [workflows/references/runtime-contracts.md](../../../../skill-libs/graph-base/1.3.1/workflows/references/runtime-contracts.md) | modified |

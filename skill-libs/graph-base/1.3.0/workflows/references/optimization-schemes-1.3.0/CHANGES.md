# 本轮源码与入口变化

以下以任务开始的实际工作树为基线，不将已有未提交维护误计为本轮修改。完整新验收数据单列在本目录，原知识树、历史schema和1.2.0身份见保护检查。此表只列技能包内文件；包外维护说明和开发验收工作区不构成运行依赖。

| 文件 | 本轮状态 |
| --- | --- |
| [README.md](../../../README.md) | modified |
| [runtime/pyproject.toml](../../../runtime/pyproject.toml) | modified |
| [runtime/src/aprof_runtime/__init__.py](../../../runtime/src/aprof_runtime/__init__.py) | modified |
| [runtime/src/aprof_runtime/action_decision.py](../../../runtime/src/aprof_runtime/action_decision.py) | modified |
| [runtime/src/aprof_runtime/action_decision_v3.py](../../../runtime/src/aprof_runtime/action_decision_v3.py) | added |
| [runtime/src/aprof_runtime/bindings.py](../../../runtime/src/aprof_runtime/bindings.py) | modified |
| [runtime/src/aprof_runtime/bindings_v4.py](../../../runtime/src/aprof_runtime/bindings_v4.py) | added |
| [runtime/src/aprof_runtime/cli.py](../../../runtime/src/aprof_runtime/cli.py) | modified |
| [runtime/src/aprof_runtime/knowledge_outcome.py](../../../runtime/src/aprof_runtime/knowledge_outcome.py) | added |
| [runtime/tests/test_action_decision_v3.py](../../../runtime/tests/test_action_decision_v3.py) | added |
| [runtime/tests/test_action_handoff_v4.py](../../../runtime/tests/test_action_handoff_v4.py) | added |
| [runtime/tests/test_diagnosis_integration_v130.py](../../../runtime/tests/test_diagnosis_integration_v130.py) | modified |
| [runtime/tests/test_scheme_cli.py](../../../runtime/tests/test_scheme_cli.py) | added |
| [schemas/README.md](../../../schemas/README.md) | modified |
| [schemas/action-decision-v3.schema.json](../../../schemas/action-decision-v3.schema.json) | added |
| [schemas/knowledge-handoff-v4.schema.json](../../../schemas/knowledge-handoff-v4.schema.json) | added |
| [skills/ascendc-aprof-coordinator/SKILL.md](../../../skills/ascendc-aprof-coordinator/SKILL.md) | modified |
| [skills/ascendc-aprof-diagnosis/SKILL.md](../../../skills/ascendc-aprof-diagnosis/SKILL.md) | modified |
| [skills/ascendc-aprof-optimization/SKILL.md](../../../skills/ascendc-aprof-optimization/SKILL.md) | modified |
| [skills/ascendc-aprof-parallel-planning/SKILL.md](../../../skills/ascendc-aprof-parallel-planning/SKILL.md) | modified |
| [skills/registry.json](../../../skills/registry.json) | modified |
| [tools/release.py](../../../tools/release.py) | modified |
| [workflows/agents/coordinator.md](../../../workflows/agents/coordinator.md) | modified |
| [workflows/agents/diagnosis.md](../../../workflows/agents/diagnosis.md) | modified |
| [workflows/agents/optimization.md](../../../workflows/agents/optimization.md) | modified |
| [workflows/agents/parallel-planning.md](../../../workflows/agents/parallel-planning.md) | modified |
| [workflows/aprof-performance-workflow.md](../../../workflows/aprof-performance-workflow.md) | modified |
| [workflows/contracts/candidate.md](../../../workflows/contracts/candidate.md) | modified |
| [workflows/contracts/common.md](../../../workflows/contracts/common.md) | modified |
| [workflows/contracts/decision.md](../../../workflows/contracts/decision.md) | modified |
| [workflows/contracts/diagnosis.md](../../../workflows/contracts/diagnosis.md) | modified |
| [workflows/contracts/planning.md](../../../workflows/contracts/planning.md) | modified |
| [workflows/contracts/preparation.md](../../../workflows/contracts/preparation.md) | modified |
| [workflows/references/action-decision-v3.md](../../../workflows/references/action-decision-v3.md) | added |
| [workflows/references/action-selection.md](../../../workflows/references/action-selection.md) | modified |
| [workflows/references/optimization-history.md](../../../workflows/references/optimization-history.md) | added |
| [workflows/references/optimization-schemes.md](../../../workflows/references/optimization-schemes.md) | added |
| [workflows/references/runtime-contracts.md](../../../workflows/references/runtime-contracts.md) | modified |

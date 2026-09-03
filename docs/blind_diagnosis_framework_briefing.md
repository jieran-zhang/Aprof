# 盲诊 Demo / 批量评测 —— 汇报说明

面向：向负责人说明「问题诊断模块」如何工作、如何避免答案泄漏、当前 demo/批量评测测了什么。

## 1. 一句话结论

我们用 **GLM-5.2** 扮演 `ascendc-aprof-diagnosis` 诊断 Agent：只读匿名算子工程（源码 + 中性 tiling 元数据），按诊断 skill 提出性能问题假设；**正确答案只存在维护者目录**，推理后再离线对齐，用于算准确率。

## 2. 整个框架如何运作

```text
┌──────────────────── 造题（维护者）────────────────────┐
│  inject skill: ascendc-aprof-inject-problems         │
│  六类问题 → 注入完整直调工程 → operators/op_XXXX       │
│  答案写入 .ground_truth/case_problem_map.json        │
└──────────────────────────────────────────────────────┘
                         │
                         ▼  (agent 不可见答案)
┌──────────────────── 解题（诊断）──────────────────────┐
│  diagnosis skill: ascendc-aprof-diagnosis            │
│  盲诊输入（无 GT）→ GLM-5.2 → single_case_diagnosis   │
└──────────────────────────────────────────────────────┘
                         │
                         ▼  (仅维护者)
┌──────────────────── 评测 ────────────────────────────┐
│  offline：预测 vs .ground_truth → family/id 命中率     │
└──────────────────────────────────────────────────────┘
```

两个 skill **互为取反、共享同一套六类问题表**：

| 问题族 | 注入（造题） | 诊断（解题） |
|--------|--------------|--------------|
| tiling / data_movement / pipeline_parallel / onchip_memory / ai_core_utilization / api_algorithm | `*-inject.md` + recipes | `*-diagnosis-metrics.md` |

辅助 skill：`ascendc-kernel-direct-invoke` 把单 kernel 脚手架成可编译工程，再注入。

## 3. Demo 怎么跑一个 case（防泄密）

入口：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py \
  --case-dir benchmarks/aprof_benchmark/fast_gelu/operators/op_0001
```

批量（会加载 diagnosis skill 文件进 system prompt）：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py --limit 6
```

### 单 case 步骤

1. **选匿名目录**：`operators/op_0001`（名字不含问题标签）。
2. **构造盲诊输入**：`build_blind_diagnosis_input.py` 只打包 kernel 源码、`case_metadata`（shape/blockdim/tile_length）、硬件上下文；剥离 `injected_label` / `problem_id` 等。
3. **装载 skill（批量脚本）**：把 `skills/aprof/diagnosis/SKILL.md`、路由表、六类诊断矩阵摘要、输出契约装进 system prompt —— 这就是「调用 skill」。
4. **调用 GLM-5.2**：user 消息 = 盲诊 JSON；**不包含** `.ground_truth`。
5. **写诊断结果**：`single_case_diagnosis.json`。
6. **离线对齐（维护者）**：本地读 `case_problem_map.json` 打分，生成 `offline_alignment.json` / 批量准确率表。

### 如何避免 Agent 直接知道答案

| 手段 | 说明 |
|------|------|
| 匿名目录 | `op_XXXX`，不用 `inject_tilelen_small` 这类名字 |
| 答案隔离 | GT 只在 `.ground_truth/`；demo 拒绝从该路径读入模型 |
| 盲诊输入清洗 | 禁止字段：problem_id、injected_label、inject_manifest… |
| 中性元数据 | `case_metadata.json` 只有 shape / blockdim / tile_length |
| 中性宏名 | `APROF_FEATURE_XX`，不用 `APROF_INJECT_*` |
| 评测后置 | 对齐只在模型返回之后做 |

## 4. 「批量评测」测什么

不是测 CANN 能不能编译（那是 910B `run.sh all/hw`），而是测：

> **诊断模型在看不到答案时，能否把问题归到正确问题族 / 接近正确根因。**

指标（当前启发式）：

- **family hit**：预测的 `problem_family` 是否覆盖 GT 家族  
- **id hit**：预测描述是否命中 GT `problem_id` 关键词（宽松）

## 5. 实测准确率（更新）

### 金标准 `aprof_benchmark/fast_gelu` 全部 12 case

| 指标 | 结果 |
|------|------|
| family hit | **10/12（83%）** |
| id hit（启发式） | **7/12（58%）** |
| 产物 | `plugins/.../demo/out/batch_eval_gold12/` |

未命中/异常：`op_0008`（JSON 解析失败）、`op_0011`（api_algorithm / scalar_loop 易被判成 tiling）。

### 新构造 `aprof_injected_ops`（57 匿名 case）

| 指标 | 结果 |
|------|------|
| family hit（legacy 家族名规范化后） | **50/57（88%）** |
| id hit（启发式） | **24/57（42%）** |
| 产物 | `plugins/.../demo/out/batch_eval_injected_ops/` |

说明：部分旧 GT 把家族写成 `blockdim`/`tail` 等，已映射到 `tiling` 再计分；少数 case 因 GLM JSON 解析失败计为未命中。

```bash
python plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py \
  --bench-root benchmarks/aprof_injected_ops --limit 0 \
  --out-dir plugins/aprof-performance-workflow/demo/out/batch_eval_injected_ops --resume
```

1. **闭环**：注入 skill 造带标签题 → 诊断 skill + GLM 盲解 → 离线算分。  
2. **科学评测**：答案不进模型，避免「开卷考试」。  
3. **可扩展**：同一套六类矩阵覆盖多算子；`aprof_benchmark/fast_gelu` 是金标准 demo，`aprof_injected_ops` 是扩展集。  
4. **工程真实**：case 是完整 CMake/op_host 直调工程，可上 910B 采 msprof（诊断还可进一步吃硬件证据）。

## 6. 相关路径

- 单 case demo：`plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py`
- 批量评测：`plugins/aprof-performance-workflow/demo/run_glm_batch_eval.py`
- 诊断 skill：`skills/aprof/diagnosis/`
- 注入 skill：`skills/aprof/benchmark/ascendc-aprof-inject-problems/`
- 金标准 case：`benchmarks/aprof_benchmark/fast_gelu/`
- 研究/论文思路活文档（含端到端与 skill-RL 规划）：`docs/aprof_research_thinking.md`

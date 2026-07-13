# AProf 注入 Benchmark 总览

> 维护者：yihan-long
> 最后更新：2026-07-11
> Skill 管线：`skills/aprof/benchmark/ascendc-aprof-inject-problems/`（PR #2 引入 schema v2 + 工具链）

本目录存放 AProf 性能问题注入 benchmark case。每个算子下有 1 个 `baseline` + N 个 `inject_*` variant，每个 variant 注入**单一性能问题**并保留数学正确性。ground-truth 写在 `inject_manifest.json.ground_truth`，供 `/ascendc-aprof-diagnosis` 盲诊闭环对齐。

---

## 1. 目录结构

```
benchmarks/aprof_injected_ops/
├── README.md                  ← 本文件（总览 + 扩展规划）
├── common/                    ← 共享脚本
│   ├── inject_gen_data.py     ← stdlib-only 数据生成器（含 golden 函数 + main_with_config / main_foreach_norm）
│   ├── inject_run.sh          ← 共享 runner（sim / hw 双模式）
│   └── parse_hw_op_summary.py ← 从 OpBasicInfo.csv 解析 Task Duration
├── closed_loop/               ← 诊断闭环测试（PR #2）
├── fast_gelu/                 ← ✅ 已对齐 schema v1（PR #2 retrofit）
├── mish/                      ← ⚠️ 缺 inject_manifest.json（legacy，待 retrofit）
├── swi_glu/                   ← ⚠️ 缺 inject_manifest.json（legacy，待 retrofit）
├── gelu_mul/                  ← ✅ schema v2（本批新增）
├── fast_gelu_grad/            ← ✅ schema v2（本批新增）
├── foreach_norm/              ← ✅ schema v2（本批新增）
├── manifest.json              ← legacy manifest（已被 inject_manifest.json 取代）
├── fast_gelu_inject_report.md ← fast_gelu 注入对比报告
└── new_ops_inject_report.md   ← 三新算子注入对比报告（gelu_mul / fast_gelu_grad / foreach_norm）
```

每个 `<op>/<variant>/` 的标准结构：

```
<op>/<variant>/
├── inject_manifest.json   ← ground_truth + quality（schema v2）
├── metadata.json          ← 旋钮快照（blockdim / tile_length / num_tensors 等）
├── profiling_plan.json    ← 采集计划（部分 case 有）
├── run.sh                 ← source ../../common/inject_run.sh
├── scripts/gen_data.py    ← 调用 common/inject_gen_data.py 生成 input.bin / golden.bin / tiling.bin / op_config.json
├── op_kernel/
│   ├── <op>_kernel.asc    ← kernel 源码（含 #if APROF_INJECT_* 注入点）
│   ├── aprof_variant_config.h  ← 编译期注入开关
│   └── aprof_vector_tiling.h   ← tiling 结构体（vector 类）或 aprof_foreach_tiling.h（foreach 类）
├── data/                  ← input.bin / golden.bin（gitignored on re-profile）
├── build_sim/             ← 编译产物 + op_config.json（gitignored）
├── msprof_sim_output/     ← simulator 产物（gitignored）
├── msprof_hw_output/      ← 真机产物（gitignored）
└── remote_inject_out/     ← 远程采集结果（results_hw.json + 下载的 CSV）
```

---

## 2. 命名规范

### 2.1 Variant 目录名

遵循 skill recipe index（`references/inject-problems-meta.md`）的 canonical variant 名：

| problem_family | problem_id | variant 目录名 | injected_label |
|----------------|------------|----------------|----------------|
| tiling | blockdim_too_small | `inject_blockdim` | blockdim_too_small |
| tiling | tile_length_too_small | `inject_tilelen_small` | tileLength_too_small |
| tiling | tile_length_too_large | `inject_tilelen_large` | tileLength_too_large |
| tiling | tile_num_unreasonable | `inject_tilenum` | tileNum_unreasonable |
| tiling | tail_inefficient | `inject_tail` | tail_inefficient |
| tiling | fixed_tiling_dynamic_shape | `inject_dynshape` | fixed_tiling_dynamic_shape |
| data_movement | redundant_copyin | `inject_redundant_copyin` | redundant_copyin |
| data_movement | extra_copyout | `inject_extra_copyout` | extra_copyout |
| data_movement | small_datacopy_granularity | `inject_small_datacopy` | small_datacopy_granularity |
| pipeline_parallel | serial_copy_compute_copyout | `inject_serial_pipeline` | serial_copy_compute_copyout |
| pipeline_parallel | excessive_pipe_barrier | `inject_excessive_barrier` | excessive_pipe_barrier |
| pipeline_parallel | double_buffer_disabled | `inject_double_buffer_disabled` | double_buffer_disabled |
| onchip_memory | ub_temp_overallocated | `inject_ub_temp_overalloc` | ub_temp_overallocated |
| onchip_memory | gm_spill_intermediate | `inject_gm_spill` | gm_spill_intermediate |
| onchip_memory | low_ub_reuse | `inject_low_ub_reuse` | low_ub_reuse |
| ai_core_utilization | underused_blockdim | `inject_underused_blockdim` | underused_blockdim |
| ai_core_utilization | overlaunched_empty_cores | `inject_overlaunched_cores` | overlaunched_empty_cores |
| ai_core_utilization | tail_core_imbalance | `inject_tail_core_imbalance` | tail_core_imbalance |
| api_algorithm | scalar_loop_redundant | `inject_scalar_loop` | scalar_loop_redundant |
| api_algorithm | small_vector_api_chunks | `inject_small_vector_chunks` | small_vector_api_chunks |
| api_algorithm | redundant_cast_or_vector_copy | `inject_redundant_vector` | redundant_cast_or_vector_copy |

### 2.2 已知不一致（待修复）

| 算子 | variant | 问题 | 修复方案 |
|------|---------|------|---------|
| mish / swi_glu | 全部 7 case | 缺 `inject_manifest.json` | 用 skill tool retrofit 或手工补 |
| fast_gelu | 全部 6 inject | manifest schema v1，`problem_family` 用 legacy 名（`blockdim` 而非 `tiling`） | 升级到 schema v2，family 改 `tiling` |
| foreach_norm | `inject_tiling_unreasonable` | ~~非 canonical~~ ✅ 已重命名为 `inject_tilelen_small` | 已修复 |
| foreach_norm | `inject_data_move_bottleneck` | ~~非 canonical~~ ✅ 已重命名为 `inject_redundant_copyin` | 已修复 |

---

## 3. 现有 case 总览表

### 3.1 已完成（有 inject_manifest.json + 真机 μs）

| 算子 | 类别 | variant | family | label | 真机 μs | 倍率 | quality |
|------|------|---------|--------|-------|---------|------|---------|
| fast_gelu | activation | baseline | baseline | baseline | — | — | active |
| fast_gelu | activation | inject_blockdim | tiling | blockdim_too_small | — | — | deprecated_or_weak |
| fast_gelu | activation | inject_tail | tiling | tail_inefficient | 5.82 | — | active |
| fast_gelu | activation | inject_tilelen_small | tiling | tileLength_too_small | 30.76 | — | active |
| fast_gelu | activation | inject_tilelen_large | tiling | tileLength_too_large | 3.78 | — | weak |
| fast_gelu | activation | inject_tilenum | tiling | tileNum_unreasonable | 8.10 | — | weak |
| fast_gelu | activation | inject_dynshape | tiling | fixed_tiling_dynamic_shape | 2.72 | — | weak |
| gelu_mul | activation | baseline | baseline | baseline | 7.60 | 1.00× | active |
| gelu_mul | activation | inject_blockdim | tiling | blockdim_too_small | 28.86 | 3.80× | unverified |
| gelu_mul | activation | inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | 9.90 | 1.30× | unverified |
| gelu_mul | activation | inject_tilelen_small | tiling | tileLength_too_small | 60.68 | **7.98×** | unverified |
| fast_gelu_grad | activation | baseline | baseline | baseline | 8.52 | 1.00× | active |
| fast_gelu_grad | activation | inject_blockdim | tiling | blockdim_too_small | 30.08 | 3.53× | unverified |
| fast_gelu_grad | activation | inject_scalar_loop | api_algorithm | scalar_loop_redundant | 8.48 | 1.00× | unverified |
| fast_gelu_grad | activation | inject_dynshape | tiling | fixed_tiling_dynamic_shape | 3.46 | — | unverified |
| foreach_norm | foreach | baseline | baseline | baseline | 8.20 | 1.00× | active |
| foreach_norm | foreach | inject_blockdim | tiling | blockdim_too_small | 28.32 | 3.45× | unverified |
| foreach_norm | foreach | inject_tilelen_small | tiling | tileLength_too_small | 54.60 | **6.66×** | unverified |
| foreach_norm | foreach | inject_redundant_copyin | data_movement | redundant_copyin | 10.26 | 1.25× | unverified |
| matmul | matmul | baseline | baseline | baseline | 38.48 | 1.00× | active |
| matmul | matmul | inject_blockdim | tiling | blockdim_too_small | 147.14 | **3.82×** | unverified |
| matmul | matmul | inject_tilelen_small | tiling | tileLength_too_small | 137.58 | 3.57× | unverified |
| matmul | matmul | inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | 51.90 | 1.35× | unverified |
| matmul | matmul | inject_ub_temp_overalloc | onchip_memory | ub_temp_overallocated | 37.98 | 0.99× | unverified |
| conv2d | conv | baseline | baseline | baseline | 2.60 | 1.00× | active |
| conv2d | conv | inject_blockdim | tiling | blockdim_too_small | 7.80 | 3.00× | unverified |
| conv2d | conv | inject_tilelen_small | tiling | tileLength_too_small | 13.44 | **5.17×** | unverified |
| conv2d | conv | inject_redundant_copyin | data_movement | redundant_copyin | 3.08 | 1.18× | unverified |
| layer_norm | norm | baseline | baseline | baseline | 2.78 | 1.00× | active |
| layer_norm | norm | inject_blockdim | tiling | blockdim_too_small | 8.22 | 2.96× | unverified |
| layer_norm | norm | inject_tilelen_small | tiling | tileLength_too_small | 15.24 | **5.48×** | unverified |
| layer_norm | norm | inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | 3.46 | 1.24× | unverified |
| topk | index | baseline | baseline | baseline | 3.10 | 1.00× | active |
| topk | index | inject_blockdim | tiling | blockdim_too_small | 9.14 | 2.95× | unverified |
| topk | index | inject_redundant_copyin | data_movement | redundant_copyin | 3.68 | 1.19× | unverified |
| max_pool | pooling | baseline | baseline | baseline | 2.92 | 1.00× | active |
| max_pool | pooling | inject_blockdim | tiling | blockdim_too_small | 8.90 | 3.05× | unverified |
| max_pool | pooling | inject_tilelen_small | tiling | tileLength_too_small | 15.64 | **5.36×** | unverified |
| mish | activation | baseline–inject_dynshape (7 case) | tiling | various | — | — | unverified (retrofit) |
| swi_glu | activation | baseline–inject_dynshape (7 case) | tiling | various | — | — | unverified (retrofit) |

### 3.2 mish / swi_glu（已 retrofit manifest，hw 采集待修复）

> **hw 采集失败原因**：mish / swi_glu 的 `gen_data.py` 仍使用 PR #1 时代的 `import numpy as np` 格式，远程 910B 机器无 numpy → `gen_data.py` 执行失败 → 无 tiling/op_config → 编译跳过 → `task_duration_us = null`。**这不是多卡集群问题**，单卡即可运行，只需将 gen_data.py 重构为 `main_with_config` 模式（stdlib-only，与 fast_gelu/new ops 一致）。修复后可直接采集。

| 算子 | 类别 | case 数 | manifest | hw μs | 阻塞原因 |
|------|------|---------|----------|-------|---------|
| mish | activation | 7 | ✅ schema v2 | ❌ null | `gen_data.py` 用 numpy（远程无） |
| swi_glu | activation | 7 | ✅ schema v2 | ❌ null | 同上 |

---

## 4. 六大问题 × 算子类别注入适配矩阵

基于 ops-nn 仓库算子类别 × 六大性能问题家族的注入适配性评估。✅ = 适合注入，⚠️ = 可注入但效果有限，❌ = 不建议注入。

| 算子类别 | 典型算子 | ① Tiling 不合理 | ② 数据搬运瓶颈 | ③ 流水并行不足 | ④ 片上内存不足 | ⑤ AI Core 利用率低 | ⑥ API/算法低效 |
|---------|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| activation | gelu_mul, fast_gelu, swiglu, celu | ⚠️ | ⚠️ | ✅ | ⚠️ | ✅ | ✅ |
| conv | conv2d, conv3d, quant_conv3d | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| foreach | foreach_add, foreach_norm, foreach_acos | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ |
| index | gather, scatter, topk, index_fill | ⚠️ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ |
| loss | cross_entropy_loss, ctc_loss, mse_loss | ⚠️ | ✅ | ⚠️ | ✅ | ⚠️ | ✅ |
| matmul | matmul, sparse4to2quant_matmul, transpose_batch_matmul | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| norm | batch_norm, layer_norm, rms_norm | ⚠️ | ✅ | ⚠️ | ✅ | ⚠️ | ✅ |
| pooling | max_pool, avg_pool, adaptive_avg_pool | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| quant | dynamic_quant, dynamic_mx_quant | ⚠️ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| rnn | lstm, gru | ⚠️ | ⚠️ | ✅ | ⚠️ | ✅ | ⚠️ |
| control | control类算子 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| vfusion | vfusion类算子 | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |

---

## 5. 注入优先级与扩展计划

按注入难度、效果显著性、诊断价值三维度排序。**已完成** = 已有 case；**计划中** = 用户规划的下一批。

| 优先级 | 算子 | 类别 | 推荐注入问题（按效果排序） | 状态 | case 数 |
|--------|------|------|---------------------------|------|---------|
| **P0** | matmul | matmul | Tiling > 流水 > 片上内存 > AI Core | ✅ 已完成 | 6 |
| **P0** | fast_gelu | activation | Tiling（6 variant） | ✅ 已完成 | 7 |
| **P1** | conv2d | conv | Tiling > 搬运 > 流水 > 片上 > AI Core > API | ✅ 已完成 | 8 |
| **P1** | foreach_norm | foreach | Tiling > 搬运 | ✅ 已完成 | 4 |
| **P2** | layer_norm | norm | Tiling > 流水 > 搬运 > 片上 > AI Core > API | ✅ 已完成 | 8 |
| **P2** | gelu_mul | activation | Tiling > 流水 > 搬运 > 片上 > API | ✅ 已完成 | 7 |
| **P3** | topk | index | Tiling > 搬运 > 流水 | ✅ 已完成 | 4 |
| **P3** | max_pool | pooling | Tiling > 搬运 > 流水 > AI Core | ✅ 已完成 | 6 |
| — | fast_gelu_grad | activation | Tiling > API | ✅ 已完成 | 4 |
| — | mish | activation | Tiling（6 variant） | ✅ 已 retrofit | 7 |
| — | swi_glu | activation | Tiling（6 variant） | ✅ 已 retrofit | 7 |

### 5.1 六大问题家族覆盖率与命中率（v3）

| 问题家族 | case 数 | 有信号(>1.2×) | 最强倍率 | 诊断准确率 | 评价 |
|---------|---------|--------------|---------|-----------|------|
| **tiling** | 21 | 16/21 | **8.10×** | 95% | ✅ 最可靠 |
| **ai_core_utilization** | 4 | 4/4 | **5.32×** | — | ✅ 新增，全命中 |
| **pipeline_parallel** | 6 | 6/6 | 1.38× | 100% | ⚠️ 信号弱但全部可见 |
| **data_movement** | 6 | 4/6 | 1.29× | 100% | ⚠️ 2/6 低于 1.2× |
| **onchip_memory** | 4 | 0/4 | 1.05× | 100% | ❌ 无信号，需更大 workload |
| **api_algorithm** | 4 | 0/4 | 1.05× | 100% | ❌ 无信号，Adds(+0) 被编译器消除 |

**诊断闭环**：23 个 active case 盲诊准确率 **87%**（20/23），使用 `build_blind_diagnosis_input.py` 剥离 ground truth + 源码模式路由自动预测。

### 5.1 P0–P3 详细注入策略

#### P0: matmul（matmul 类别）

| problem_family | problem_id | 注入策略 | 预期信号 |
|----------------|------------|---------|---------|
| tiling | blockdim_too_small | 强制固定 blockDim=1（本应多核） | 强 |
| tiling | tile_length_too_small/large | 将 baseM/baseN/baseK 设为极端值 | 强 |
| pipeline_parallel | serial_copy_compute_copyout | 禁用 DoubleBuffer，Queue 深度 2→1 | 强 |
| pipeline_parallel | excessive_pipe_barrier | 每次迭代插 pipe_wait() | 中 |
| onchip_memory | gm_spill_intermediate | 禁用 L1 缓存，每次从 GM 读 A/B | 强 |
| onchip_memory | low_ub_reuse | 临时 Tensor 声明为 GM 而非 UB | 中 |

#### P0: fast_gelu（activation 类别，已完成）

| problem_family | problem_id | variant | 状态 |
|----------------|------------|---------|------|
| tiling | blockdim_too_small | inject_blockdim | ✅ deprecated_or_weak |
| tiling | tail_inefficient | inject_tail | ✅ active |
| tiling | tile_length_too_small | inject_tilelen_small | ✅ active |
| tiling | tile_length_too_large | inject_tilelen_large | ✅ weak |
| tiling | tile_num_unreasonable | inject_tilenum | ✅ weak |
| tiling | fixed_tiling_dynamic_shape | inject_dynshape | ✅ weak |

> **扩展建议**：补 `api_algorithm/redundant_cast_or_vector_copy` 和 `ai_core_utilization/underused_blockdim`

#### P1: conv2d（conv 类别）

| problem_family | problem_id | 注入策略 | 预期信号 |
|----------------|------------|---------|---------|
| tiling | blockdim_too_small | 固定 blockDim=1 或 2 | 强 |
| tiling | tile_length_too_small | tileLength 非对齐值 | 强 |
| data_movement | redundant_copyin | 滑动窗口内重复搬运相同特征图区域 | 中 |
| onchip_memory | low_ub_reuse | 不利用 L1 缓存复用输入特征图 | 中 |

#### P1: foreach_norm（foreach 类别，已完成）

| problem_family | problem_id | variant | 状态 |
|----------------|------------|---------|------|
| tiling | blockdim_too_small | inject_blockdim | ✅ unverified |
| tiling | tile_length_too_small | inject_tiling_unreasonable | ✅ unverified |
| data_movement | redundant_copyin | inject_data_move_bottleneck | ✅ unverified |

> **扩展建议**：补 `ai_core_utilization/tail_core_imbalance`（张量列表分配不均）

#### P2: layer_norm（norm 类别）

| problem_family | problem_id | 注入策略 | 预期信号 |
|----------------|------------|---------|---------|
| onchip_memory | gm_spill_intermediate | 不缓存均值/方差，每次从 GM 读 | 强 |
| onchip_memory | low_ub_reuse | 计算均值和方差分别从 GM 读两次 | 中 |
| api_algorithm | redundant_cast_or_vector_copy | 用 Div/Sqrt 低级指令拼凑归一化 | 中 |
| pipeline_parallel | excessive_pipe_barrier | 计算链中插入同步点 | 弱 |

#### P2: gelu_mul（activation 类别，已完成）

| problem_family | problem_id | variant | 状态 |
|----------------|------------|---------|------|
| tiling | blockdim_too_small | inject_blockdim | ✅ unverified |
| pipeline_parallel | excessive_pipe_barrier | inject_excessive_barrier | ✅ unverified (1.30×) |
| tiling | tile_length_too_small | inject_tilelen_small | ✅ unverified (7.98×) |

> **扩展建议**：补 `ai_core_utilization/underused_blockdim` 和 `api_algorithm/redundant_cast_or_vector_copy`

#### P3: topk（index 类别）

| problem_family | problem_id | 注入策略 | 预期信号 |
|----------------|------------|---------|---------|
| ai_core_utilization | tail_core_imbalance | 控制流密集，负载不均 | 中 |
| data_movement | redundant_copyin | 不规则内存访问重复搬运 | 中 |

#### P3: max_pool（pooling 类别）

| problem_family | problem_id | 注入策略 | 预期信号 |
|----------------|------------|---------|---------|
| ai_core_utilization | underused_blockdim | 标量循环实现池化窗口归约 | 强 |
| api_algorithm | scalar_loop_redundant | 标量循环 + 比较指令替代向量化归约 | 中（需防 DCE）|

---

## 6. 新增算子流程

### 6.1 使用 skill 工具链（推荐）

```bash
# 1. 列出可用 recipes
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/inject_case.py --list-recipes

# 2. 从已有 baseline 生成 inject case
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/inject_case.py \
  --source-mode existing_aprof_baseline \
  --source-path benchmarks/aprof_injected_ops/<op>/baseline \
  --output-root benchmarks/aprof_injected_ops/<op> \
  --problem-family <family> \
  --problem-id <problem_id> \
  --variant inject_<variant>

# 3. 校验
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/validate_inject_cases.py \
  --op-root benchmarks/aprof_injected_ops/<op>

# 4. 远程真机采集
python scripts/run_remote_new_ops_inject_hw.py  # 设置 INJECT_OPS=<op>
```

### 6.2 手工创建（无 baseline 时）

1. 在 `common/inject_gen_data.py` 添加 golden 函数
2. 创建 `<op>/baseline/`（kernel + gen_data + run.sh + tiling 结构体）
3. 用 skill 工具或手工创建 inject variants
4. 补 `inject_manifest.json`（schema v2）

### 6.3 命名检查清单

- [ ] variant 目录名匹配 `references/inject-problems-meta.md` 的 canonical 名
- [ ] `metadata.json.injected_label` 匹配 recipe 的 `injected_label`
- [ ] `inject_manifest.json.ground_truth.problem_family` 用 canonical family 名（`tiling` 而非 `blockdim`）
- [ ] `inject_manifest.json.ground_truth.problem_id` 匹配 recipe 的 `problem_id`
- [ ] `validate_inject_cases.py` 输出 `pass=True`

---

## 7. 相关文档

| 文档 | 内容 |
|------|------|
| `docs/new_ops_inject_workflow.md` | 三新算子注入流程 + 矩阵 + 实测数据 |
| `fast_gelu_inject_report.md` | fast_gelu 注入对比报告 |
| `new_ops_inject_report.md` | 三新算子注入对比报告（v2，含 skill 优化） |
| `docs/fast_gelu_inject_workflow.md` | 原始 fast_gelu 注入流程 |
| `skills/aprof/benchmark/ascendc-aprof-inject-problems/SKILL.md` | skill 使用说明 |
| `skills/aprof/benchmark/ascendc-aprof-inject-problems/references/inject-problems-meta.md` | recipe 索引 |

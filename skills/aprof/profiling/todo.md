# AscendC AProf Profiling Metric Skill TODO

本文是 `ascendc-aprof-profiling` 的下一步建设任务说明：把 `/ascendc-aprof-diagnosis` 中已沉淀的问题诊断矩阵反推为可执行的 profiling 采集入口和具体 metric skill。

## 总目标

构建一组面向大模型的 profiling 采集技能，让模型在用户描述性能问题时，能够主动判断需要收集哪些 `msprof` / `aprof` CSV、trace/timeline、代码信息、TilingData 和 NPU 架构分母，并把缺失数据转化为明确的采集任务。

## 当前诊断问题族

- Tiling 问题：多核切分、UB 切分、Buffer 规划、tail、动态 shape。
- 数据搬运瓶颈：GM 访问频繁、DataCopy 粒度小、重复搬运、CopyIn/CopyOut 占比高。
- 流水并行不足：CopyIn/Compute/CopyOut 未重叠、DoubleBuffer/queue/stage 配置不合理、同步等待多。
- 片上内存利用不足：UB/L1/L0/L2 复用不足、临时 Tensor 过多、workspace 不合理、中间结果落 GM。
- AI Core 利用率低：Vector/Cube 利用不足、多核负载不均、空闲核、尾核拖尾。
- API 与算法实现低效：Scalar 循环、Vector/Cube API 使用不足、Cast 冗余、Reduce/Matmul 低效、融合不足。

## Metric 汇总

### 1. `OpBasicInfo.csv`

必须收集：

- `Task Duration`
- `Block Dim`

派生用途：

- 核利用率：`Block Dim / coreNum`
- 头开销占比：`(Task Duration - max(ai*_time)) / Task Duration`
- 小 shape 是否过开核、动态 shape 是否未更新 usedCoreNum

大模型采集提示：

- 询问用户提供目标 op 的 `OpBasicInfo.csv` 行，至少包含 op 名称、shape 对应上下文、`Task Duration`、`Block Dim`。
- 若要比较动态 shape，需要同一算子多个 shape 的 `Task Duration` 与 `Block Dim`。

### 2. `PipeUtilization.csv`

必须收集：

- 公共定位字段：`block_id`、`sub_block_id`
- AIV/AIC 总时间：`aiv_time(us)`、`aic_time(us)`
- 计算占比：`aiv_vec_ratio`、`aic_cube_ratio`
- Scalar：`ai*_scalar_ratio`、`ai*_scalar_time(us)`
- 搬运占比：`ai*_mte2_ratio`、`ai*_mte3_ratio`、Cube 场景关注 `aic_mte1_ratio`
- 搬运时间：`ai*_mte2_time`、`ai*_mte3_time`
- Fixpipe：`aic_fixpipe_ratio`
- ICache：`ai*_icache_miss_rate`

派生用途：

- 核间耗时不均衡：`(max(ai*_time) - min(ai*_time)) / max(ai*_time)`
- 最慢核定位：`argmax(ai*_time)` + `block_id`
- 分 pipe 不均衡：分别比较 `aiv_vec_time`、`aic_cube_time`、`ai*_mte2_time`、`ai*_mte3_time`
- VEC/CUBE/MTE/SCALAR Bound 判定
- 流水线气泡：多个 pipe 比例分散且无明显主导时，需继续采 trace

大模型采集提示：

- 要求用户提供完整 `PipeUtilization.csv`，不要只贴平均值；诊断负载均衡、尾核拖尾必须保留逐 `block_id` 数据。
- 若用户只给单行汇总，只能判断总体瓶颈，不能判断多核不均。

### 3. `ArithmeticUtilization.csv`

必须收集：

- Cube：`aic_cube_ratio`、`aic_cube_fp16_ratio`、`aic_cube_int8_ratio`、`aic_cube_fops`、`aic_cube_total_instr_number`、`aic_cube_fp_instr_number`、`aic_cube_int_instr_number`
- Vector：`aiv_vec_ratio`、`aiv_vec_fp32_ratio`、`aiv_vec_fp16_ratio`、`aiv_vec_int32_ratio`、`aiv_vec_int16_ratio`、`aiv_vec_misc_ratio`、`aiv_vec_fops`

派生用途：

- Vector 理论利用率：`aiv_vec_fops / (aiv_time * vector_peak_flops)`
- Cube 理论利用率：`aic_cube_fops / (aic_time * cube_peak_flops)`
- Cast 或 dtype 路径异常：`aiv_vec_fp32_ratio`、`aiv_vec_fp16_ratio`、`aiv_vec_misc_ratio` 与输入 dtype/算法预期对比
- Matmul/GMM/FA 的 Cube API 是否有效工作

大模型采集提示：

- 询问用户提供 dtype、shape、目标算子族和 `ArithmeticUtilization.csv`。
- 若要判断理论利用率，必须同时收集 `/npu-arch` 的 Vector/Cube 理论算力与频率信息。

### 4. `Memory.csv`

必须收集：

- GM/UB：`GM_to_UB_datas(KB)`、`UB_to_GM_datas(KB)`、`GM_to_UB_bw_usage_rate(%)`、`UB_to_GM_bw_usage_rate(%)`
- GM/L1/L0C：`GM_to_L1_datas(KB)`、`L0C_to_GM_datas(KB)`
- 主存总读写：`read_main_memory_datas`、`write_main_memory_datas`
- MTE 指令数：`ai*_mte2_instructions`、`ai*_mte3_instructions`

派生用途：

- 单次搬入字节数：`GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions`
- 单次搬出字节数：`UB_to_GM_datas(KB) * 1024 / ai*_mte3_instructions`
- MTE 指令密度：`ai*_mte2_instructions / GM_to_UB_datas(KB)`、`ai*_mte3_instructions / UB_to_GM_datas(KB)`
- 读流量放大：`read_main_memory_datas / 理论必需读数据量`
- 写流量放大：`write_main_memory_datas / 理论必需写数据量`
- 理论搬运耗时：`搬运字节数 / 理论带宽`
- MatMul 后处理拆分：`L0C_to_GM_datas`、GM→UB、UB→GM 同时升高

大模型采集提示：

- 要求用户同时提供 shape、dtype、输入/输出个数，才能计算理论必需读写量。
- 如果要判断 DataCopy 粒度，必须有数据量和 MTE 指令数，缺任一项只能做弱判断。

### 5. `ResourceConflictRatio.csv`

必须收集：

- Wait：`aiv_vec_wait_ratio`、`aic_cube_wait_ratio`、`ai*_mte2_wait_ratio`、`ai*_mte3_wait_ratio`
- MTE conflict：`aiv_vec_mte_cflt_ratio`
- UB conflict：`aiv_vec_total_cflt_ratio` 及 bank、bankgroup、resource、MTE 子项

派生用途：

- Vector/Cube 是否在等待搬运、同步或资源。
- MTE 与 Vector 资源冲突是否导致流水无法重叠。
- UB bank conflict 是否导致 Vector API 理论利用率低。

大模型采集提示：

- 若用户反馈 Vector/Cube 占比不高但 duration 高，要求补充 `ResourceConflictRatio.csv`。
- 若要定位 UB 地址/stride 问题，还要收集 LocalTensor offset、repeatStride、blockStride、对齐方式。

### 6. `L2Cache.csv`

必须收集：

- `ai*_total_hit_rate(%)`

派生用途：

- L2 命中率低：`ai*_total_hit_rate < 50%` 时关注 CacheMode、数据局部性、跨核重复读。
- 结合读流量放大判断重复搬运、切分维度错误或一次性数据污染 L2。

大模型采集提示：

- 要求用户说明输入是否存在跨核复用、是否设置 CacheMode、切分维度是否连续。
- 对 L2 hit 波动问题，需要同算子不同 shape 或不同访问顺序的 profiling 对比。

### 7. `MemoryUB.csv`

必须收集：

- `aiv_ub_read_bw_vector`
- `aiv_ub_write_bw_vector`
- `aiv_ub_read_bw_scalar`
- `aiv_ub_write_bw_scalar`

派生用途：

- 判断 UB 内读写是否成为瓶颈。
- Scalar 访问带宽异常时，结合 `ai*_scalar_ratio` 判断临时状态管理、小 shape 或标量循环问题。

大模型采集提示：

- 若怀疑 UB 临时 Tensor、UB 复用或 UB bank conflict，要求补充 `MemoryUB.csv`、UB buffer 公式和 LocalTensor 地址规划。

### 8. `MemoryL0.csv` / L1-L0 相关字段

必须收集：

- `aic_l0a/l0b/l0c_*_bw`
- `aic_l1_*_bw`

派生用途：

- MatMul/GMM/FA 判断 L1/L0 分块、K-axis 迭代、L0C 累加和 Cube 复用效率。
- 与 `aic_cube_ratio`、`aic_cube_fops`、`GM_to_L1_datas(KB)` 共同判断 Cube 低利用根因。

大模型采集提示：

- 只有 Cube-heavy 算子需要优先收集该组 metric。
- 必须同步收集 baseM/baseN/baseK、L1/L0 buffer 规划和平台 L1/L0 容量。

### 9. Trace / Timeline

必须收集的场景：

- 判断 CopyIn/Compute/CopyOut 是否重叠。
- 判断 DoubleBuffer 配置后是否真正生效。
- 判断 SyncAll、WaitFlag、PipeBarrier 等同步等待。
- 判断 queue depth、stage slot、workspace 轮转是否造成互等。
- 判断尾核拖尾、归并阶段串行、FA split-KV combine 等阶段级问题。

派生用途：

- MTE2/Compute 重叠率：`overlap(MTE2, VEC或CUBE) / min(MTE2_time, Compute_time)`
- Compute/MTE3 重叠率：`overlap(VEC或CUBE, MTE3) / min(Compute_time, MTE3_time)`
- CopyIn/Compute/CopyOut 串行度：timeline 中三阶段顺序执行比例
- Sync 等待占比：等待事件、WaitFlag、SyncAll、PipeBarrier 在 timeline 中的耗时占比

大模型采集提示：

- CSV 只能判断“可能有流水问题”，不能确认重叠关系；涉及 DB、queue、同步、stage 的结论必须提示用户补 trace/timeline。
- 要求用户保留 op 名称、block_id、pipe/stage 时间线和同步事件。

### 10. 非 msprof 但必须同步收集的信息

NPU 架构分母：

- `GetCoreNumAiv()`
- `GetCoreNumAic()`
- `GetCoreMemSize(CoreMemType::UB)`
- `GetCoreMemSize(CoreMemType::L1)`
- `GetCoreMemSize(CoreMemType::L0A/L0B/L0C)`
- `GetCoreMemSize(CoreMemType::L2)`
- `GetCoreMemSize(CoreMemType::BT)`
- `Current Freq` / `Rated Freq`
- Vector/Cube 理论 FLOPS
- 理论带宽或实测基准带宽

代码与 TilingData：

- shape、dtype、format、op 类型、输入/输出个数。
- `blockDim`、usedCoreNum、totalTasks、totalTiles、tileLength、tileNum。
- UB/L1/L0 buffer bytes、bufferNum、queue depth、stageNum、workspace bytes、workspace slot。
- DataCopy/DataCopyPad 粒度、对齐长度、有效长度、tail 分支。
- Vector/Cube/Reduce/Matmul/Cast API 调用路径。
- CacheMode、切分轴、访问顺序。

## 入口 Skill 设计任务

- [ ] 更新 `ascendc-aprof-profiling/SKILL.md`，把“现象 → 问题族 → metric 包 → 采集任务”的路由写成固定流程。
- [ ] 增加“最小采集包”：`OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`、shape/dtype、NPU 架构分母。
- [ ] 增加“扩展采集包”：按问题族补 `ArithmeticUtilization.csv`、`ResourceConflictRatio.csv`、`L2Cache.csv`、`MemoryUB.csv`、`MemoryL0.csv`、trace/timeline。
- [ ] 增加缺失数据处理规则：说明当前只能做直接证据、派生证据还是必须等待 trace/对比。
- [ ] 增加输出模板：用户应得到一份文件清单、字段清单、派生公式、采集原因和诊断入口建议。

## 具体 Metric Skill 拆分任务

- [ ] `aprof-op-basic-metrics`：负责 `OpBasicInfo.csv`、shape/dtype、`Block Dim`、`Task Duration`、头开销和核利用分母。
- [ ] `aprof-pipe-utilization-metrics`：负责 `PipeUtilization.csv`，覆盖 VEC/CUBE/MTE/SCALAR/Fixpipe/ICache/逐核时间。
- [ ] `aprof-arithmetic-utilization-metrics`：负责 `ArithmeticUtilization.csv`，覆盖 Vector/Cube fops、指令类型占比、理论算力利用率。
- [ ] `aprof-memory-metrics`：负责 `Memory.csv`，覆盖 GM↔UB、GM→L1、L0C→GM、主存读写、MTE 指令数和带宽。
- [ ] `aprof-conflict-metrics`：负责 `ResourceConflictRatio.csv`，覆盖 wait、MTE conflict、UB bank conflict。
- [ ] `aprof-cache-metrics`：负责 `L2Cache.csv`，覆盖 L2 hit、CacheMode、重复读和局部性。
- [ ] `aprof-onchip-memory-metrics`：负责 `MemoryUB.csv`、`MemoryL0.csv`、L1/L0/UB 带宽与片上复用。
- [ ] `aprof-trace-timeline-metrics`：负责 trace/timeline，覆盖重叠率、同步等待、queue/stage/workspace slot。
- [ ] `aprof-platform-denominator-metrics`：负责 `/npu-arch` 分母，覆盖核数、容量、频率、理论带宽、理论算力。
- [ ] `aprof-code-context-metrics`：负责非 CSV 上下文，覆盖 TilingData、API 调用路径、buffer 公式、workspace、CacheMode。

## 大模型采集提示模板

当用户只描述“性能差”时：

```markdown
我需要先建立最小 profiling 证据包。请提供：

1. 目标算子的 op 名、shape、dtype、format、输入输出个数。
2. `OpBasicInfo.csv` 中该 op 的 `Task Duration`、`Block Dim`。
3. `PipeUtilization.csv` 中该 op 的完整逐核数据，保留 `block_id`、`aiv_time(us)`、`aic_time(us)`、VEC/CUBE/MTE/SCALAR 占比。
4. `Memory.csv` 中 GM↔UB、GM→L1、L0C→GM、主存读写、MTE 指令数和带宽字段。
5. 当前平台的 AIV/AIC 核数、UB/L1/L0/L2 容量、频率、理论带宽和理论算力。

拿到这些后，我可以先判断是核利用、搬运、计算、Scalar、头开销还是数据量放大问题。
```

当怀疑数据搬运瓶颈时：

```markdown
请补充 `Memory.csv`、`PipeUtilization.csv`、`L2Cache.csv`。如果要判断搬运与计算是否重叠，还需要 trace/timeline。

重点字段：`ai*_mte2_ratio`、`ai*_mte3_ratio`、`GM_to_UB_datas(KB)`、`UB_to_GM_datas(KB)`、`GM_to_UB_bw_usage_rate(%)`、`UB_to_GM_bw_usage_rate(%)`、`ai*_mte2_instructions`、`ai*_mte3_instructions`、`read_main_memory_datas`、`write_main_memory_datas`、`ai*_total_hit_rate(%)`。
```

当怀疑流水并行不足时：

```markdown
CSV 只能提示可能存在流水气泡，确认 DoubleBuffer、queue、SyncAll、WaitFlag、PipeBarrier 是否造成串行，必须提供 trace/timeline。

请同时提供 `PipeUtilization.csv`、`ResourceConflictRatio.csv`、queue/buffer 配置、`InitBuffer(..., bufNum)`、EnQue/DeQue/FreeTensor 顺序和同步事件位置。
```

当怀疑 API/算法低效时：

```markdown
请提供 `PipeUtilization.csv`、`ArithmeticUtilization.csv`、`Memory.csv` 和关键代码片段。

重点确认是否存在逐元素 Scalar 循环、`GlobalTensor::GetValue/SetValue`、重复 Cast、Vector API 粒度过小、未使用 Reduce/Matmul/GMM 高阶 API、多个 kernel 之间中间结果反复落 GM。
```

## 验收标准

- [ ] 大模型能根据用户描述选择最小采集包或问题族扩展采集包。
- [ ] 每个 metric skill 都说明字段来源、派生公式、需要的上下文和不能诊断的边界。
- [ ] 每个派生 metric 都能追溯到 CSV 字段、trace/timeline、代码/TilingData 或 `/npu-arch` 分母。
- [ ] 与 `/ascendc-aprof-diagnosis` 的每个诊断矩阵建立反向链接：诊断需要什么数据，就能从 profiling skill 得到采集任务。
- [ ] 不编造字段、不写未经验证的阈值；不确定时要求用户提供原始 profiling 文件或平台文档验证。

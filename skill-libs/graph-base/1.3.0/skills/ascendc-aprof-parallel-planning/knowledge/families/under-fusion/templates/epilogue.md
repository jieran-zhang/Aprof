---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.epilogue
kind: template
version: 1.1.0
status: active
title: 融合与组合：MatMul 输出后处理
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  original_path: examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 31
  - 182
  sha256: sha256:50399b2e9cd19fe656777c2245c8e599f5b8ed159d16c6687caa9ca9b272a9fa
  excerpt_sha256: sha256:c4dfd2a27fe874f51fdc1bcb35fbb54265be1c6b37576d8436d62a7d2371623f
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 208
  sha256: sha256:f455633ee4affaed0ad5591c0acc1d47c2d7099c3bc25a8a87a3f2259783008e
  excerpt_sha256: sha256:169eb97ea7e2c0204004ae0aba222664c39fad78545988faba90d99327f34b79
learning: {}
tags:
- fusion
- composition
- epilogue
- cube-vector
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references:
- planning.matmul.mn
- planning.matmul.splitk
- planning.under-fusion.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 融合与组合：MatMul 输出后处理

## 计算边界与精度

用于 `C=phi(A*B+bias)` 及明确的 cast/scale/逐元素后处理。矩阵乘的 MN 分区和 K 累加直接复用 `planning.matmul.mn`；若采用 split-K，必须先按 `planning.matmul.splitk` 完成所有 partial 合并，最终 MN owner 才加一次 bias、执行非线性并写最终结果。对每个 partial 提前 LeakyRelu/GELU、重复加 bias 或在 K 循环内过早 cast 会改变结果。

先冻结 MatMul 累加 dtype、bias 放置、输出转换和激活公式。来源 MatmulGelu 使用明确的近似式，不能直接替换任务要求的 erf 精确式或其他 tanh/系数实现；MatmulLeakyRelu 的示例斜率是样例参数，必须使用任务定义值。即使数学函数相同，中间 fp32→fp16/bf16、FMA、Cast 舍入也需按 oracle 保留。

## kernel 组合与物理数据路径分开选择

可以将 Cube 生产与 Vector 消费放在同一 MIX kernel，也可以分成两个 kernel。每种方案还须决定中间 tile 经 GM workspace、由高阶 Matmul API 输出到本地张量，或目标平台确实支持的直连路径。`GetTensorC(...LocalTensor...)` 和 `TPosition::VECIN` 描述接口结果位置，不能单凭类型名证明底层免 GM。

固定来源 MatmulGelu 的 Scenario 1 明确支持 A2/A3 经 `L0C→GM→UB` 中转；Scenario 2 的 `L0C→UB` 在该样例仅针对 Ascend 950PR，A2/A3 不支持。因而对 910C/dav-2201，同一 MIX kernel 仍可能写读 GM 中间 tile；不能把“融合”写成“必然省去 C 的一轮 GM 写读”。本条 scope all 仅指边界/owner 的数学方法，物理通路和 API 资格必须按具体型号、SDK 与实现证明。

## 输出所有权、槽位与同步

一个逻辑 MN tile 只有一个最终 writer。AIC 负责完整 K 累加和 Fixpipe，AIV 负责该 tile 的有效后处理区；若一个 AIC 对多个 AIV，要按 kernel 模式将 AIV 物理编号映射回相同逻辑 tile，并让子 AIV 写不相交区域，不能直接把两侧 GetBlockIdx 当作相同编号。

GM 交接采用 q 个明确的槽位：AIC 等待旧消费者完成后写 slot，Fixpipe 写入完成后发 ready；对应 AIV 等 ready 后读，处理/搬出完成后发 consumed，生产者才能覆盖。ready 的发布管道、跨核事件 ID、循环次数及尾任务都需对称。高阶 Matmul API 的队列/内部同步只在其文档范围内生效；Destroy/Free 不替代真实消费者完成。若通过独立 kernel 交接，则由正确流依赖建立完成边界。

## 容量与候选比较

令 m/n 为输出基础块有效长宽，n_a 为 UB 存储行跨度，b_c/b_o 为中间/最终字节宽，a 为字节对齐，`A(z)=ceil(z/a)*a`。`U_epi=q_c*A(m*n_a*b_c)+q_o*A(m*n_a*b_o)+U_bias+U_cast+Tmp_phi+F≤U_available`；与 MatMul API 共享 UB 时须先扣除这部分预留，不能双方各按完整 UB 规划。L1/L0A/L0B/L0C 的并存矩阵块另外计，不混入 UB。

GM 槽位最低用户容量为 `W_slots=q*A(m*n*b_c)` 乘以同时存活逻辑生产者数，另加系统 API workspace 与对齐；q 由生产消费流水和合法同步决定。若真实直连且无 spill，才可能消除该中间写读流量。比较完整成本：MatMul 周期、Fixpipe/中转搬运、Vector 激活、启动与等待、UB 预留导致的 base 块变化，以及生产者快于消费者时的背压。独立 epilogue 是合法候选，不能只按 kernel 数选优。

```text
沿 MN 指定唯一 owner；沿 K 完整累加/固定合并
生产者等待 slot 可复用 -> 写完整 C tile -> 发布 ready
消费者等待 ready -> 必要 cast/bias/activation -> 写有效输出
消费者发布 consumed；完成前不覆写 slot
```

```cpp
// 引自高阶 API 的使用形态：matmulObj 的 C 类型/tiling 已相互匹配。
matmulObj.template GetTensorC<true>(mmOutLocal, false, true);
mmOutQueue.EnQue(mmOutLocal);
mmOutLocal = mmOutQueue.DeQue<float>();
AscendC::LeakyRelu(reluOutLocal, mmOutLocal, negativeSlope, validCount);
// negativeSlope、有效元素布局和写回 stride 均来自当前任务，非示例常量。
```

验证 K 尾块/split-K、MN 尾部、bias 广播、斜率/激活近似、两侧编号映射、槽位复用与每 dtype 中间舍入。当前仅来源审读，无 NPU 性能验证；来源示例支持表不能代替当前构建和硬件资格。

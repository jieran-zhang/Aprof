---
schema_version: aprof.knowledge-record/v1
id: implementation.fusion-composition.vector_chain_residency
kind: recipe
version: 1.0.0
status: active
title: Vector 算子链融合与 UB 中间值驻留
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 613
  sha256: sha256:2fb232c81805420c88755d9bc41ea3561c3f4107946306425d1a43b48c31dd1d
  excerpt_sha256: sha256:a9dc9e4064f9198bc1a959600b5ec80e454c71f38ac2681b7cbe3e0a8d5d9728
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 31
  - 157
  sha256: sha256:f455633ee4affaed0ad5591c0acc1d47c2d7099c3bc25a8a87a3f2259783008e
  excerpt_sha256: sha256:cce28e26891a94ea183739fcf3345e32edd588c63c48de46dbc427b2878e36cd
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 40
  - 249
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:28c3372885746552f8fc7c07805f7f715efc2c32ef72a3a0155dcbd49a0967a3
learning: {}
tags:
- fusion
- source-reviewed
- not-benchmarked
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.fusion-composition
references:
- implementation.buffer-lifetime.reuse
- implementation.vector-api.batch
- implementation.vector-api.cast-control
- implementation.pipeline-sync.pipeline
evidence_status: source_reviewed_not_benchmarked
---
# Vector 算子链融合与 UB 中间值驻留

## 技术定义与适用条件

把语义允许的一串Vector操作放入同一kernel，让中间张量从生产到最后消费一直留在本核UB，只从GM读原始输入、向GM写最终输出。这同时涉及**算子组合**和**中间值驻留**；不自动意味着寄存器融合或跨tile重叠。UB上的中间计算仍可能有多次UB↔寄存器访问；950的RegBase/VF是另一实现能力，不能作为910C已消除UB访问的证据。

适合相同元素域、相容布局、无外部中间消费者的逐元素链，如scale→bias→activation、残差加法→激活或约定近似的激活内部多步运算。广播需能由C2定义tile上的广播映射；带跨tile归约、转置、随机状态、原地别名或被其它kernel读取的中间值，先由C2确定融合region和所有权。短链/单tile启动成本大时可能受益，多输入长链也可能因UB压力缩tile而回退。

C2选择融合区间、任务与tile、输入输出别名、各步dtype/舍入/近似、layout和容量上限。C3只在允许范围内安排局部tensor、Vector依赖、搬运与释放；改变region、task拆分、内存通路或数值语义就返回C2。

## 收益模型、活跃区间与所有者

对k个原本独立kernel，若k-1个内部张量都长n、每元素e字节，且无必须保留的外部消费者，则理论可消除GM中间读写`2*(k-1)*n*e`字节及部分launch；不同dtype时改为`2*Σ_j(n_j*e_j)`。这是流量上界推导，不是速度预测；最终输入/输出、多输入广播数据及强制精度物化仍要计入。

对UB张量j，分配字节`B_j=align(paddedElements_j*e_j,a_j)`，活跃区间从写前acquire到最后真实读完成。分槽预算为`UB=Σ_physical_slots(B_slot*depth_slot)+scratch+API预留`。同一块被多个不重叠生命周期复用时只计物理分配一次；原输入在链末仍使用就不能提前覆盖。

| 对象 | 生产者 | 消费者 | 何时可复用 | 需要保留的数值边界 |
|---|---|---|---|---|
| 原始输入x | MTE2 | 链首及可能的后续分支 | 最后一个使用x的Vector指令完成 | 输入dtype和载入转换 |
| 中间tmp | 前一Vector操作 | 下一操作/多个分支 | 最后读者完成 | 每一步原舍入/溢出语义 |
| 最终y | 链末Vector | MTE3 | MTE3读取完成 | 输出Cast/饱和规则 |
| scratch | 高阶API或显式算法 | 该调用 | API规定完成条件后 | 不可与仍活跃x/y重叠 |

例如S1中GELU近似的分母可在y上逐步覆盖，但最后`Div(y,x,y)`仍需要原x，因此x与y必须独立；“激活可以原地”不等于该多步链可以让所有参数相同。

## 实施步骤与调度模型

1. 从原计算图标出所有中间消费者，选只有内部边的region；保留外部可见输出和原dtype边界。
2. 对每tile列出每步读写集合和最后使用点，分配可复用槽；先实现一组输入/输出的正确基线。
3. 用公开Vector API实现同等公式，在真实依赖处插入V内barrier或使用API规定的同步；以目标支持的TQue、TBuf事件或静态租约建立搬入/计算/搬出及回收完成边，不能把管理形式固定为性能前提。
4. 尾tile只计算合法有效元素或明确填充的padding，不读GM越界；广播stride由C2给定，不把尾补零当成任意算子的中性元。
5. 在容量允许和timeline显示等待后，另行引入跨tile双缓冲；分别验证“少GM往返”和“有overlap”。

```text
for each C2-owned tile:
    load inputs from GM into owned UB slots
    wait input ready
    for op in frozen region order:
        read original dtype/layout-defined inputs
        write next resident intermediate
        preserve rounding/cast boundaries; synchronize actual V dependencies
        release only slots whose last reader completed
    publish final UB output; copy only valid elements to GM
# 这段是契约伪代码，阶段不是外部repo私有helper
```

## 真实API示例：有明确语义的GELU近似

S1/S2在2201分支采用MemBase：
`f(x)=x/(1+exp(-1.595769*(x+0.044715*x^3)))`。此公式是**该源码采用的近似**，并非任意GELU oracle的等价替换；若原接口要求erf精确式、另一tanh系数或不同中间dtype，C2需明确许可，否则使用原语义路径。下面按源码改写为独立、无需repo私有头的SDK函数。

```cpp
#include "kernel_operator.h"
// x、y分别是已分配的UB float tensor，地址不重叠；n为有效元素数。
// 调用者用MTE2_V/输入队列保证x就绪；用V_MTE3/输出队列发布y。
__aicore__ inline void GeluSourceApprox(
    const AscendC::LocalTensor<float>& x,
    const AscendC::LocalTensor<float>& y, uint32_t n) {
    AscendC::Mul(y, x, x, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Mul(y, y, x, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(y, y, 0.044715f, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Add(y, x, y, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(y, y, -1.595769f, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Exp(y, y, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Adds(y, y, 1.0f, n);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Div(y, x, y, n);
}
```

`n*sizeof(float)`不是UB申请量的全部：x和y的对齐空间、每块的物理深度及其它scratch都要算。比如tile有效4096 float，若每块按32B对齐、x/y各1份，则仅显式x/y为32768B；各2份变65536B。这是演算例，不是推荐tile，也不保证芯片的可用UB。更长链中的新增输入或保留残差要按活跃区间加入。

## SDK、失败与回退

主路线为910C/A3目标SDK支持的MemBase公开API，实际头文件/API能力以安装版本编译为准。S1的3510分支改用RegBase，只是950特定扩展；不得借用其VF、寄存器长度或同名函数的特性给2201分支兜底。源码中的MatmulGelu前半段在2201仍经GM交接，本文只消除Vector链内部的可省GM物化。

常见失败是覆盖仍被使用的x、越过Cast改变溢出语义、把全张量广播当成同shape、UB缩tile导致调度变贵，以及只减少指令数却未减少实际GM流量。对照原oracle检查随机/极值/NaN/Inf/正负零及尾长；对精度不等价的近似保持原算法，不能放宽verifier。性能比较融合候选、直接父本并检查实际中间GM读写；无收益或容量不闭合就缩小融合region或回到原多kernel路径，结构变化由C2决定。

## 固定来源与证据级别

- S1：[examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc)，行 21–613；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S2：[examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md)，行 31–157；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S3：[ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md)，行 40–249；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。

# apply_adam_w 独立代码审查

## Round 0 审查报告（Step 4 初审）

- **审查日期**：2026-08-11
- **判定**：**FAIL**
- **总分**：**71 / 100**
- **阻塞原因**：存在必须修复项（3.2 API 约束、4.1 动态硬件参数），即使总分位于 70～79 分区间也不能判定 PASS WITH NOTES。
- **审查范围**：`op_kernel/apply_adam_w_kernel.asc`、Host/Tiling、CMake、测试脚本、设计/计划/README、真实 NPU 正确性及性能证据。

### 1. 独立验证结论

#### 1.1 环境与架构核对

| 项 | 独立核对结果 |
|---|---|
| CANN / bisheng | `CANN 9.0.0`；使用 `environment.md` 指定的 `/usr/local/Ascend/cann-9.0.0/bin/bisheng` |
| environment.md 运行时架构证据 | `get_npu_arch.py -> dav-2201` |
| DESIGN / CMake | 均为 `--npu-arch=dav-2201` |
| 真机兼容性 | clean build 的 DAV_2201 可执行文件已在 device 0 成功运行 20 个强制用例 |

`/npu-arch` 的静态映射表把字面芯片型号 `Ascend910`、SocVersion `ASCEND910` 映射为 DAV_1001，而 `environment.md` 同时记录实际探测为 DAV_2201。实际探测以及 DAV_2201 二进制上板成功是更强证据，因此本轮认可 CMake 的 `dav-2201`；但环境文档应把芯片/SocVersion 更正为实际 910B/910_93 对应标识，避免后续审查按静态映射得到相反结论。

#### 1.2 CMake 门禁与独立 clean build

执行：

```bash
python3 .opencode/workflows/scripts/verify_cmake_config.py operators/apply_adam_w/CMakeLists.txt
ASCEND_HOME_PATH=/usr/local/Ascend/cann-9.0.0 \
  cmake -S operators/apply_adam_w -B /tmp/apply_adam_w_review_round0 \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=OFF
ASCEND_HOME_PATH=/usr/local/Ascend/cann-9.0.0 \
  cmake --build /tmp/apply_adam_w_review_round0 -j4
```

结果：官方 CMake 配置检查通过；clean configure/build 成功；生成 `/tmp/apply_adam_w_review_round0/apply_adam_w`；未观察到代码级编译警告。该构建未复用 Developer 的可执行文件。

#### 1.3 独立真实 NPU 精度运行

使用上述 clean-build 可执行文件，在真实 NPU device 0 上重新运行 `cases.csv` 的全部 20 个强制用例。任务 `proto.yaml` 对该复杂融合算子明确给出专用 MERE/MARE 阈值（FP32=0.005、FP16=0.01、BF16=0.01；同时要求 MARE < 10×threshold），因此以该显式任务规格为验收口径。20/20 均通过：

| Case | dtype | MERE | MARE | 特殊值一致 | 状态 |
|---:|---|---:|---:|---|---|
| 1 | FP32 | 1.9263e-11 | 1.7164e-06 | 是 | PASS |
| 2 | FP16 | 3.2706e-10 | 7.6746e-04 | 是 | PASS |
| 3 | BF16 | 0 | 0 | 是 | PASS |
| 4 | FP32 | 9.2737e-10 | 1.1205e-03 | 是 | PASS |
| 5 | FP16 | 1.0535e-09 | 1.4149e-02 | 是 | PASS |
| 6 | BF16 | 0 | 0 | 是 | PASS |
| 7 | FP32 | 1.8197e-08 | 7.8302e-03 | 是 | PASS |
| 8 | FP16 | 0 | 0 | 是 | PASS |
| 9 | BF16 | 1.5246e-10 | 7.5758e-03 | 是 | PASS |
| 10 | FP32 | 0 | 0 | 是 | PASS |
| 11 | FP16 | 0 | 0 | 是 | PASS |
| 12 | BF16 | 0 | 0 | 是（Inf） | PASS |
| 13 | FP32 | 0 | 0 | 是（NaN） | PASS |
| 14 | FP16 | 0 | 0 | 是（zero） | PASS |
| 15 | FP32 | 3.0700e-11 | 4.7051e-06 | 是 | PASS |
| 16 | BF16 | 0 | 0 | 是 | PASS |
| 17 | FP16 | 0 | 0 | 是 | PASS |
| 18 | FP32 | 3.5958e-11 | 2.1871e-06 | 是 | PASS |
| 19 | BF16 | 0 | 0 | 是 | PASS |
| 20 | FP32 | 4.8135e-12 | 9.6389e-06 | 是 | PASS |

另独立构造 `numel=16, FP32, step=2` 的 Level 0 用例，上板结果 `max_abs_err=0`、`max_rel_err=0`。这证明边界规模当前可运行，但项目自身的持久化用例集中没有 Level 0 case，不能代替测试交付件修复。

#### 1.4 独立性能采集

按项目约定使用 `msprof`，对 clean-build executable 的 case 1 进行 3 次 warm-up 后独立采集 `PipeUtilization`：

| 指标 | Reviewer 独立值 | Developer 归档值 | 结论 |
|---|---:|---:|---|
| Task Duration | 31.480 us | 31.739 us（5 次中位数） | 差异 0.82%，归档可信 |
| AIV time | 25.294 us | — | 头/调度差额约 6.186 us，占 Task 19.65% |
| MTE2 ratio | 41.9% | — | 最大流水，但未达到 >70% bound 门槛 |
| VEC ratio | 23.9% | — | 无单一 VEC bound |
| Scalar ratio | 22.3% | — | 标量开销明显 |
| MTE3 ratio | 7.9% | — | 非主导 |

case 1 的 `t_hw=8.74 us`，独立实测是其约 3.60 倍，远未满足“与理论耗时差距 <20%”；同时头/调度差额约 19.65%，高于审查清单的 10% 目标。Developer 的 20-case NPU 归档完整，综合 CANN-Bench 分数为 `75.5839696285`，但这不能抵消当前无 double buffer、UB 利用受硬编码上限限制的问题。

### 2. 100 分制评分

| 维度 | 子项 | 得分 | 证据/说明 |
|---|---|---:|---|
| 1 编译验证（10） | 1.1 独立编译成功 | 7/7 | clean build 成功 |
|  | 1.2 无代码级警告 | 3/3 | 构建日志未见代码警告 |
| 2 架构合规（15） | 2.1 TPipe/TQue | 3/3 | FP32 和半精度搬运均使用 TPipe/TQue |
|  | 2.2 入口属性 | 3/3 | 纯向量算子使用 `__global__ __vector__` |
|  | 2.3 定义顺序 | 3/3 | 类在入口前定义，无前向声明 |
|  | 2.4 内存管理配对 | 3/3 | Alloc/Free=7/7，EnQue/DeQue=7/7 |
|  | 2.5 数据流完整 | 3/3 | 结果进入 VECOUT 后搬出，20 cases 验证 |
| 3 编码规范（15） | 3.1 矢量 API | 4/4 | 无逐元素 GetValue/SetValue |
|  | 3.2 API 约束满足 | **0/4** | **阻塞：Sqrt 非正输入、Div 零分母未做安全域处理** |
|  | 3.3 数据对齐 | 4/4 | tile 256B 对齐，尾块用 DataCopyPad |
|  | 3.4 命名规范 | 3/3 | 类/方法/算子符号可辨识且一致 |
| 4 性能优化（20） | 4.1 动态硬件参数 | **0/4** | **阻塞：`ubFormer` 被硬编码 8192 截断，且依据的 API 字段说明错误** |
|  | 4.2 多核并行 | 4/4 | 动态查询 Vector Core；线性切分且 tail 合理 |
|  | 4.3 流水线/双缓冲 | 0/4 | 所有 InitBuffer 数量为 1，Process 串行 CopyIn→Compute→CopyOut |
|  | 4.4 同步策略 | 4/4 | Queue 同步覆盖跨 pipe 依赖，无冗余 PipeBarrier |
|  | 4.5 计算效率/上板性能 | 0/4 | Task/t_hw≈3.60，头开销≈19.65%，未达目标 |
| 5 测试覆盖（15） | 5.1 测试数据生成 | 4/4 | 解析权威 cases.csv，支持三种 dtype |
|  | 5.2 结果验证脚本 | 4/4 | MERE/MARE 和 NaN/Inf 一致性检查存在 |
|  | 5.3 Level 0 覆盖 | 0/4 | 项目测试集中无持久化 8～16 元素 case；Reviewer 临时用例不算交付覆盖 |
|  | 5.4 精度标准明确 | 3/3 | proto 专用阈值及特殊值规则明确 |
| 6 精度验证（10） | 6.1 FP32 全用例 | 4/4 | 独立真机 8/8 PASS |
|  | 6.2 FP16 全用例 | 3/3 | 独立真机 6/6 PASS |
|  | 6.3 BF16 全用例 | 3/3 | 独立真机 6/6 PASS |
| 7 文档（15） | 7.1 README 存在 | 3/3 | 存在 |
|  | 7.2 数学公式 | 0/3 | README 未给出 AdamW 公式 |
|  | 7.3 编译运行指南 | 3/3 | 构建、正确性、profiling 命令齐全 |
|  | 7.4 API 映射/约束 | 0/3 | README 未给 API 映射；DESIGN 与实现不一致 |
|  | 7.5 已知限制 | 0/3 | README 无明确已知限制章节 |
|  | **合计** | **71/100** | 存在阻塞项，判定 FAIL |

### 3. 同步 API 逐项依赖分析

源码中 `PipeBarrier` 调用总数为 **0**，因此逐个 PipeBarrier 表为空，冗余数 0，冗余率记为 N/A（不能用 0/0 声称 0%）。跨 pipe 依赖由 TQue 建立：

| 行号 | 前操作 | 前 Pipe | 同步机制 | 后操作 | 后 Pipe | 判定 |
|---:|---|---|---|---|---|---|
| 56-60 → 65-68 | 四路 DataCopyPad GM→UB | MTE2 | 各 VECIN Queue EnQue/DeQue | Muls/Add 等 | V | 必要且存在 |
| 98 → 100/107-109 | 最终 Add | V | VECOUT Queue EnQue/DeQue | DataCopyPad UB→GM | MTE3 | 必要且存在 |
| 196-200 | DataCopyPad GM→raw UB | MTE2 | raw VECIN Queue EnQue/DeQue | Cast | V | 必要且存在 |
| 207-211 | Cast FP32→raw output | V | raw VECOUT Queue EnQue/DeQue | DataCopyPad UB→GM | MTE3 | 必要且存在 |
| 81-98、169-186 | 连续矢量算术链 | V | 无 barrier | 后续矢量算术 | V | 同 pipe 保序，正确 |

结论：未发现缺失的显式 PipeBarrier，也没有冗余 barrier；当前同步策略本身通过。性能问题来自单 buffer 串行组织，而不是 barrier 过多。

### 4. 必须修复项

#### M1（阻塞）Sqrt/Div 调用违反官方输入约束，且实现与 DESIGN 不一致

- 位置：`op_kernel/apply_adam_w_kernel.asc:90-92`、`:178-180`。
- 现状：两个 dtype 分支都直接执行 `Sqrt(..., v_hat, count)`，随后直接执行 `Div(..., denominator, count)`。
- 官方证据：`asc-devkit/docs/api/context/Sqrt.md` 的约束明确写明“如果 src 中的数值为非正数，可能会产生未知结果”；`asc-devkit/docs/api/context/Div.md` 明确写明“注意除零错误”。
- 规格风险：case 14 明确包含 `v_hat=0`；通用接口及 DESIGN 还承诺负 `v_hat`、`epsilon=0`、NaN/Inf 的确定行为。当前 20 cases 恰好在本机通过，不能把硬件当前表现当作 API 契约。
- 设计偏差：`DESIGN.md §1.3/§2.4.3` 要求 Compare/Select/Duplicate 实现 SafeSqrt/SafeDiv，`§1.5` 规划 mask 和 Select 8KB 临时区；实际 Kernel、TilingData、UB 预算均没有这些内容。
- 修复要求：按已批准设计实现 SafeSqrt/SafeDiv；对 Sqrt 的非正输入先构造安全正值，对 Div 的零分母先替换安全值，计算后按 mask 恢复 golden 需要的 zero/NaN/±Inf。涉及 API 必须再次核对本地 `CompareScalar*.md`、`Compare*.md`、`Select*.md`、`Duplicate*.md` 的所有变体、A2 对齐和临时空间要求。补齐 TilingData 特殊值 bit pattern、mask buffer、固定临时区及 UB 闭合预算，并增加负 v_hat、epsilon=0+零分母的真机回归。

#### M2（阻塞）分块大小存在硬编码上限，且 API 上限解释错误

- 位置：`op_host/apply_adam_w_common.h:25-31`，尤其第 30 行 `ubFormer = min(ubFormer, 8192)`。
- 现状：虽然先从运行时 UB 反推 tile，随后又固定截断到 8192。FP32 在当前 192KB UB 上确实命中该固定值，未使用动态预算可容纳的更大 tile。
- 注释错误：代码称“`DataCopyExtParams::blockLen` 是 uint16 bytes”；官方 `DataCopyPad(ISASI).md` 显示 `DataCopyExtParams::blockLen` 是 `uint32_t`、范围到 2097151 字节，而当前四字段初始化实际对应 `DataCopyParams`，其 `blockLen` 才是 `uint16_t`。
- 修复要求：明确选用 `DataCopyExtParams`（五字段）或 `DataCopyParams`（四字段），依据所选结构体的官方字段范围、dtype 字节数、UB 运行时容量共同推导 `ubFormer`；不得保留无依据的固定 8192 tile。若保留 API 上限 clamp，必须由 API 类型上限公式推导并在 Host 侧做溢出检查。SafeSqrt/SafeDiv 加入后要重新计算完整 UB 预算。

### 5. 其他修复要求与建议

1. **补持久化 Level 0 和设计承诺的 smoke cases**：至少加入 8～16 元素基础 case，以及 `step=2/100`、beta near 1、负 v_hat、`epsilon=0 + denominator=0`、最小 shape、8D shape、非法 attrs。必须由 `run.sh` 或正式测试入口可重复执行，而不是只写在 PLAN 中。
2. **优化流水线**：当前 Queue depth 模板参数为 1 且 `InitBuffer(..., 1, ...)`，每个 tile 严格串行。注意 TQue 文档明确说明 Queue depth 与 double buffer 不是同一概念；需要分配两份 buffer 并重排循环以形成实际 CopyIn/Compute/CopyOut 重叠，不能只把模板 depth 改成 2。A2 的 eventID 数量也必须纳入四输入 Queue 规划。
3. **性能复验**：修复后至少重新独立采集代表性 FP32、FP16/BF16 大 case；目标是缩小 Task Duration 与 `t_hw` 差距、将头开销压到 10% 以下，并检查核间负载差异 <10%。
4. **README 补全**：加入数学公式、Kernel API 映射/关键约束、已知限制；当前这些信息只在 DESIGN，且 DESIGN 已与实现漂移。
5. **API 注释**：开发指南要求每个 API 调用说明 API 功能及关键参数。当前 Kernel 的矢量 API 调用基本没有参数/约束注释，应在修复时补齐关键调用说明。
6. **环境文档一致性**：修正 `Ascend910/ASCEND910` 与运行时 `dav-2201` 的产品标识冲突，保存可追踪的真实 SKU/SocVersion。

### 6. 测试覆盖与交付件说明

| 测试级别 | 状态 | 说明 |
|---|---|---|
| Level 0（必须） | 项目内缺失 | Reviewer 临时 numel=16 真机通过，但未形成交付测试 |
| Level 1（推荐） | 通过 | 多个约 1M 元素 case |
| Level 2（推荐） | 部分通过 | zero/NaN/Inf 已覆盖；负 v_hat、显式零分母等 PLAN smoke 未落地 |
| Level 3（可选） | 通过 | 最高约 50M 元素，20 cases 均有 NPU 性能数据 |

由于存在 M1/M2 必须修复项，本轮按 `review-final-round.md` 流程跳过“预计通过”才执行的最终轮交付件/代码清洁附加门禁。修复后复审必须重新 clean build、全量真机精度运行，并重新采集性能；不得仅引用本轮或 Developer 的既有结果。

---

## Round 1 审查报告（Step 5 复审）

- **审查日期**：2026-08-11
- **判定**：**PASS**
- **总分**：**92 / 100**
- **复审结论**：Round 0 的 M1/M2 两个阻塞项均已修复；独立 clean build、11 个 smoke、20 个强制 case、独立 msprof 与最终轮交付检查均通过。当前单缓冲和上板性能差距作为非阻塞优化项保留。

### 1. Round 0 问题闭环

| Round 0 项目 | Round 1 证据 | 结论 |
|---|---|---|
| M1：Sqrt 非正输入、Div 零分母 | `apply_adam_w_kernel.asc:15-62` 新增 SafeSqrt/SafeDiv；两个 dtype 分支均调用；Compare count 对齐到 64 个 FP32 元素；TilingData 携带 quiet NaN/±Inf bit pattern；独立负 v_hat、0/0、非零/0 smoke 全部通过 | 已修复 |
| M1：DESIGN 与实现不一致 | DESIGN 的 mask、Select 8KB 预留、特殊值恢复、半精度 30B/元素预算均已与实现对齐 | 已修复 |
| M2：固定 8192 tile | 固定 clamp 已删除；Host 按运行时 UB、实际 buffer、mask、Select 8KB、2KB reserve 和 API 上限动态搜索；真机 FP32/半精度 tile 为 9216/6144 | 已修复 |
| M2：DataCopy 参数类型混淆 | 所有 GM↔UB 搬运均显式使用五字段 `DataCopyExtParams`；`blockLen` 使用 `uint32_t`，上限公式为 2097151 字节 | 已修复 |
| 缺少 Level 0/smoke | `scripts/test_smoke.py` 持久化 11 个用例，包含 8/16 元素、step、beta near 1、安全域、1D/8D 和非法参数 | 已修复 |
| README/环境文档缺项 | README 已含公式、API 映射、已知限制；environment.md 明确运行时 DAV_2201 证据及 `Ascend910` 通用驱动标签语义 | 已修复 |

### 2. 独立构建与架构验证

执行：

```bash
python3 .opencode/workflows/scripts/verify_cmake_config.py \
  operators/apply_adam_w/CMakeLists.txt
ASCEND_HOME_PATH=/usr/local/Ascend/cann-9.0.0 \
  cmake -S operators/apply_adam_w -B /tmp/apply_adam_w_review_round1 \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=OFF
ASCEND_HOME_PATH=/usr/local/Ascend/cann-9.0.0 \
  cmake --build /tmp/apply_adam_w_review_round1 -j4
```

结果：官方 CMake 门禁通过；使用 environment.md 指定的 CANN 9.0.0/bisheng 完成全新构建；无代码级警告。DESIGN 和两个 ASC target 均为 `--npu-arch=dav-2201`。environment.md 的权威运行时探测是 DAV_2201，且本轮 clean-build DAV_2201 二进制已在真实 NPU device 0 成功执行，因此架构配置一致。

### 3. API 合规复核

通过 `/ascendc-docs-search` 列出并核对所有新 API 变体：`CompareScalar.md`、`Compare.md`/寄存器变体、`Select.md`/`Select-38.md`、`Duplicate.md`、`DataCopyPad(ISASI).md`。

| API | 官方约束 | 当前实现 | 判定 |
|---|---|---|---|
| CompareScalar/Compare | FP32 count 所占空间必须 256B 对齐 | `ApplyAdamWCompareCount` 将 count 对齐到 64 个 FP32 元素；mask buffer 256B 对齐 | 通过 |
| Select 基础 API 模式 1/2 | A2 需预留 8KB UB；LocalTensor 32B 对齐 | Host UB 预算固定扣除 8192B；所有 tensor/mask 由 TPipe 分配且对齐 | 通过 |
| Sqrt | 非正输入可能产生未知结果 | 先用 `GT 0` mask 把非正/NaN 替换为 1，再 Sqrt，随后恢复 zero/NaN | 通过 |
| Div | 注意除零错误 | 零分母先替换为 1，Div 后按 numerator/denominator mask 恢复 ±Inf/NaN | 通过 |
| DataCopyPad + DataCopyExtParams | `blockLen` 为 uint32 字节，范围 1～2097151 | 五字段结构体；Host 由 API 上限和 dtype 推导元素上限 | 通过 |
| Select-38 高阶变体 | byte mask、多维 shape、显式 sharedTmpBuffer | 当前使用的是基础 bit-mask Select，不混用该高阶变体 | 不适用 |

SafeSqrt/SafeDiv 的 LocalTensor 均为完全分离或 100% 原地重叠，无部分重叠；与基础 API 的通用地址重叠约束一致。尾 tile 的 Compare 会读取对齐后的 padding 区域，但 Select/算术/写回只处理 `validCount`，padding 不影响有效输出。

### 4. 独立真实 NPU 精度验证

#### 4.1 持久化 smoke

Reviewer 将 `scripts/test_smoke.py` 指向 Round 1 clean-build executable，在真实 device 0 独立执行，结果 **11/11 PASS**：Level0 8/16、step=2、step=100+beta near 1、负 v_hat、0/0、非零/0、最小 shape、8D shape以及非法 step/beta/dtype 均符合预期。

#### 4.2 20 个强制用例全覆盖

Reviewer 使用 Round 1 clean-build executable 独立运行全部 20 个 `cases.csv` 用例。显式任务规格为 FP32/FP16/BF16 MERE threshold `0.005/0.01/0.01`，并要求 MARE < 10×threshold；特殊值位置必须完全一致。结果 20/20 PASS：

| dtype | Case | Shape | dim | Max Abs Err | Max Rel Err | Mismatch | 状态 |
|---|---:|---|---:|---:|---:|---:|---|
| FP32 | 1 | 1024×1024 | 2 | 5.9605e-08 | 1.7164e-06 | 0 | PASS |
| FP16 | 2 | 2048×2048 | 2 | 1.2207e-04 | 7.6746e-04 | 0 | PASS |
| BF16 | 3 | 4096×4096 | 2 | 0 | 0 | 0 | PASS |
| FP32 | 4 | 4096×4096 | 2 | 9.5367e-07 | 1.1205e-03 | 0 | PASS |
| FP16 | 5 | 4096×8192 | 2 | 3.9063e-03 | 1.4149e-02 | 0 | PASS |
| BF16 | 6 | 1023×1023 | 2 | 0 | 0 | 0 | PASS |
| FP32 | 7 | 1009×1021 | 2 | 1.1921e-07 | 7.8302e-03 | 0 | PASS |
| FP16 | 8 | 1537×769 | 2 | 0 | 0 | 0 | PASS |
| BF16 | 9 | 363×367×373 | 3 | 6.2500e-02 | 7.5758e-03 | 0 | PASS |
| FP32 | 10 | 2049×513 | 2 | 0 | 0 | 0 | PASS |
| FP16 | 11 | 3×7×13×4001 | 4 | 0 | 0 | 0 | PASS |
| BF16 | 12 | 1000003 | 1 | 0 | 0 | 0 | PASS |
| FP32 | 13 | 11×13×17×67×67 | 5 | 0 | 0 | 0 | PASS |
| FP16 | 14 | 3×7×11×13×1013 | 5 | 0 | 0 | 0 | PASS |
| FP32 | 15 | 512×2049 | 2 | 2.9802e-08 | 4.7051e-06 | 0 | PASS |
| BF16 | 16 | 255×8193 | 2 | 0 | 0 | 0 | PASS |
| FP16 | 17 | 4097×511 | 2 | 0 | 0 | 0 | PASS |
| FP32 | 18 | 2×511×2049 | 3 | 1.4901e-08 | 2.1871e-06 | 0 | PASS |
| BF16 | 19 | 4×255×2049 | 3 | 0 | 0 | 0 | PASS |
| FP32 | 20 | 2×3×17×1024×101 | 5 | 3.8147e-06 | 9.6389e-06 | 0 | PASS |

Mismatch 统计包括特殊值位置不一致，或有限元素相对误差达到该 dtype 的 `10×threshold`；所有 case 均为 0。case 12/13/14 的 Inf/NaN/zero pattern 独立核对一致。

### 5. 独立性能验证

对 clean-build executable 的 case 1 做 3 次 warm-up 后独立执行 `msprof` PipeUtilization 采集：

| 指标 | Reviewer Round 1 | Developer round_002 | 结论 |
|---|---:|---:|---|
| Task Duration | 37.339 us | 37.339 us（5 次中位数） | 完全一致 |
| AIV time | 32.643 us | — | Task 与 AIV 差额 4.696 us，占 12.58% |
| VEC ratio | 37.2% | — | 无 >70% VEC bound |
| MTE2 ratio | 34.3% | — | 无 >70% MTE2 bound |
| Scalar ratio | 16.8% | — | 非主导 |
| MTE3 ratio | 4.6% | — | 非主导 |

修复后的安全域增加了必要矢量计算，case 1 为 `t_hw=8.74 us` 的约 4.27 倍，仍未达到“与理论耗时差距 <20%”；因此 4.5 不得分。四输入单缓冲没有实现搬运/计算重叠，因此 4.3 也不得分。Developer 已如实将旧 round_001 标为修复前数据、将新综合分置空，并保存 round_002 的三个代表 case；后续 Step 6b 应完成修复版 20-case 全量性能重采和评分。

### 6. 同步策略逐项分析

源码 `PipeBarrier` 数量为 **0**，冗余数为 0，冗余率 N/A。新增 SafeSqrt/SafeDiv 全部是 PIPE_V 内连续操作，不应插入 barrier。跨 pipe 依赖如下：

| 行号 | 前操作 | 前 Pipe | 同步机制 | 后操作 | 后 Pipe | 判定 |
|---:|---|---|---|---|---|---|
| 118-124 → 129-132 | 四路 DataCopyPad GM→UB | MTE2 | 四个 VECIN Queue EnQue/DeQue | 矢量计算 | V | 必要且存在 |
| 167-178 | 最终 Add | V | VECOUT Queue EnQue/DeQue | DataCopyPad UB→GM | MTE3 | 必要且存在 |
| 277-295 | 四路 DataCopyPad GM→raw UB | MTE2 | 各 raw VECIN Queue EnQue/DeQue | Cast | V | 必要且存在 |
| 310-318 | Cast FP32→raw output | V | raw VECOUT Queue EnQue/DeQue | DataCopyPad UB→GM | MTE3 | 必要且存在 |
| 23-61 | Compare/Select/Sqrt/Div/Duplicate | V | 无 barrier | 后续矢量操作 | V | 同 pipe 保序，正确 |
| 149-167、248-266 | AdamW 算术链 | V | 无 barrier | 后续矢量操作 | V | 同 pipe 保序，正确 |

AllocTensor/FreeTensor 为 7/7，EnQue/DeQue 为 7/7；未发现同步遗漏、错误位置或过度同步。

### 7. 100 分制评分

| 维度 | 子项 | 得分 | Round 1 证据 |
|---|---|---:|---|
| 1 编译验证（10） | 1.1 独立编译成功 | 7/7 | clean build PASS |
|  | 1.2 无代码级警告 | 3/3 | 无代码警告 |
| 2 架构合规（15） | 2.1 TPipe/TQue | 3/3 | 两分支均合规 |
|  | 2.2 入口属性 | 3/3 | 纯向量入口 `__vector__` |
|  | 2.3 定义顺序 | 3/3 | helper/class/入口顺序正确 |
|  | 2.4 内存管理配对 | 3/3 | Alloc/Free、EnQue/DeQue 全配对 |
|  | 2.5 数据流完整 | 3/3 | 独立 20 cases + smoke 通过 |
| 3 编码规范（15） | 3.1 矢量 API | 4/4 | 无逐元素 GM API |
|  | 3.2 API 约束满足 | 4/4 | 安全域、对齐、临时 UB、API 上限均满足 |
|  | 3.3 数据对齐 | 4/4 | tile/Compare/mask/尾块对齐正确 |
|  | 3.4 命名规范 | 3/3 | 符号清晰一致 |
| 4 性能优化（20） | 4.1 动态硬件参数 | 4/4 | 核数、UB、tile 全部动态推导 |
|  | 4.2 多核并行 | 4/4 | 动态 AIV 数量，线性均衡切分 |
|  | 4.3 流水线/双缓冲 | 0/4 | 已知单缓冲限制 |
|  | 4.4 同步策略 | 4/4 | Queue 同步正确，无冗余 barrier |
|  | 4.5 计算效率/上板性能 | 0/4 | case 1 为 t_hw 约 4.27 倍 |
| 5 测试覆盖（15） | 5.1 测试数据生成 | 4/4 | 三 dtype + 权威 cases |
|  | 5.2 结果验证脚本 | 4/4 | MERE/MARE/特殊值验证 |
|  | 5.3 Level 0 覆盖 | 4/4 | 持久化 8/16 元素 smoke |
|  | 5.4 精度标准明确 | 3/3 | proto 专用阈值明确 |
| 6 精度验证（10） | 6.1 FP32 全用例 | 4/4 | 8/8 PASS |
|  | 6.2 FP16 全用例 | 3/3 | 6/6 PASS |
|  | 6.3 BF16 全用例 | 3/3 | 6/6 PASS |
| 7 文档（15） | 7.1 README 存在 | 3/3 | 完整 |
|  | 7.2 数学公式 | 3/3 | 已补齐 |
|  | 7.3 编译运行指南 | 3/3 | build/run/smoke/profile 齐全 |
|  | 7.4 API 映射/约束 | 3/3 | 已补齐且与实现一致 |
|  | 7.5 已知限制 | 3/3 | 明确单缓冲、dtype/shape 等限制 |
|  | **合计** | **92/100** | 无必须修复项 |

### 8. 最终轮附加检查

#### 8.1 交付件 D1-D8

| 项 | 状态 | 说明 |
|---|---|---|
| D1 算子源码 | PASS | 独立编译通过，无警告 |
| D2 CMakeLists | PASS | 官方门禁通过，依赖和 NPU arch 完整 |
| D3 Golden 数据生成 | PASS | FP32/FP16/BF16 全覆盖 |
| D4 run.sh | PASS | 单 case、全量和 smoke 入口齐全；独立等价路径已执行 |
| D5 README | PASS | 公式、API、构建运行、测试和限制齐全 |
| D6 DESIGN | PASS | 需求、3D/数据流、API、UB、安全域与实现一致 |
| D7 PLAN | PASS | Developer 阶段和测试结果已记录；Step 6b 的修复后全量性能按工作流明确留待审查通过后执行 |
| D8 REVIEW | PASS | Round 0 保留，Round 1 已追加 |

#### 8.2 代码清洁 C1-C4

| 项 | 状态 | 说明 |
|---|---|---|
| C1 printf/cout | PASS | Kernel 无调试输出；Host 仅保留 CLI 成功信息 |
| C2 TODO/FIXME/HACK/XXX | PASS | 无残留 |
| C3 注释代码块 | PASS | 未发现大段注释掉的实现 |
| C4 调试硬编码 | PASS | 未发现固定 blockDim/blockIdx/tile/UB；参数解析中的循环常量不属于硬件硬编码 |

精度全覆盖见 §4.2，三种 dtype 的全部强制 case 均已由 Reviewer 独立执行并记录。

### 9. 非阻塞后续项

1. Step 6b 对修复版重新采集全部 20 个 case，更新 `results.json` 的 operator score；不得复用 pre-fix round_001 分数。
2. 单缓冲是明确的性能限制。若后续优化，应先做 A2 event/Queue 资源预算，再设计能证明无死锁的双缓冲管线；不得只增加 buffer 数量。
3. 当前 case 1 的 Task/AIV 头差额约 12.58%，仍高于 10% 目标；可结合完整多指标和 sample-based 逐核数据继续定位调度/标量开销。

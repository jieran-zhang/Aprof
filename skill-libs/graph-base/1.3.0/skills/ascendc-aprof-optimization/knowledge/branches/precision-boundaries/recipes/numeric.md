---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries.numeric
kind: recipe
version: 1.2.0
status: active
title: 累加精度、特殊值与数值边界
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 643
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 349
  sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
  excerpt_sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 327
  sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
  excerpt_sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 151
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Compare.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Compare.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 357
  sha256: sha256:353264a38c342ca8b668d0400e48750461820fa743be89ba59d6824eb4764262
  excerpt_sha256: sha256:353264a38c342ca8b668d0400e48750461820fa743be89ba59d6824eb4764262
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Select.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Select.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 345
  sha256: sha256:615845595e9b6ca5d150548eb27e9e6fd9d0bb972ee1533f933ad6bea8d940b5
  excerpt_sha256: sha256:615845595e9b6ca5d150548eb27e9e6fd9d0bb972ee1533f933ad6bea8d940b5
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Max.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Max.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 177
  sha256: sha256:3ef8936b5fe5025072d33fa4b79380cd04c73ffbc33786605cadd5dee8b49329
  excerpt_sha256: sha256:3ef8936b5fe5025072d33fa4b79380cd04c73ffbc33786605cadd5dee8b49329
learning: {}
tags:
- accumulation-order
- numeric-contract
- special-values
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.precision-boundaries
references:
- implementation.cube-api.fixpipe_output
- implementation.cube-api.mmad_accumulation
- implementation.precision-boundaries.bounds
- implementation.vector-api.cast
evidence_status: source_reviewed_not_benchmarked
---
# 累加精度、特殊值与数值边界

## 守住原数值契约

适用于 reduction、方差、norm、softmax、Split-K/KV、Cast 与输出转换的实现改动。先从冻结 oracle 和 C2 写出输入/中间/累加/输出 dtype，允许误差的定义与逐元素判据、舍入/饱和模式、epsilon/correction、归约/合并次序、bias/scale/激活执行次数，以及空/全 mask/计数为零的结果。原标准不清楚就保持当前正确路径，不能先改实现再放宽 tolerance。

本条补强等价实现的验证与精度状态，不引入新的近似算法、不把“更稳定”当作任意换算法许可。已有 Welford 计划继续按其状态与合并契约实现；TwoPass、平方和差、分组合并或 FP32 partial 与当前算法不同则须 C2 明确授权。FP32 partial 只是 dtype 选择，不能自动证明归约顺序变化、溢出或特殊值正确。

## 实施步骤与状态生命周期

1. 列出每个阶段首个可能舍入的位置与状态存活期。Cast 合并、Fixpipe 随路 Cast、Mmad 分片和 Vector batch 分别核验原 dtype/模式；先检查中间结果再只看最终误差。
2. 对累加明确“首片初始化一次、后片累加、最后处理输出”的边界。每片添加 bias、每个 Split 重复 epsilon/归一化、每轮清空状态都会改变结果；局部 K 顺序与跨核合并顺序分开记录，不能把相同数学实数和当作浮点等价。
3. 计数/索引使用足够宽类型并核验转换。很大的整数 count 转 float 可能丢失低位；分母 `count−correction`、空归约、全 mask softmax 与全零 norm 必须走原 oracle 定义分支，不能在无效值上继续计算后依靠乘0消掉。
4. padding 不应计入有效计数。sum 的0、max 的负无穷是常见中性元，但 dtype/NaN/量化/分段状态需按具体算子核对。Welford 的空状态应按单位元处理，不能仅填 mean=0 而让 count 错误为非零。
5. 量化/MX 格式单独核验 quantization 轴、scale 对应关系、pack 布局、scale dtype 与目标 SDK；连续维并不意味着 scale 轴正确。不得为获得 API 支持改用另一 rounding、改 scale 关联或省略 saturation 检查。

## 已选 Welford 的参考核对片段

固定来源给出状态 `(mean,M2,count)` 与两组公式。下例是 Host 双精度参考核对，不是 NPU kernel 代码；`countA/countB` 是非负 `uint64_t` 有效元素数，`meanA/meanB/m2A/m2B` 是对应块已有状态。Host 已检查计数相加不溢出；零计数状态先按原 oracle 单独处理，以下只用于两块非空、总计数可转换的分支。

```cpp
const double a = static_cast<double>(countA);
const double b = static_cast<double>(countB);
const double total = a + b;
const double delta = meanB - meanA;
const double mean = meanA + delta * (b / total);
const double m2 = m2A + m2B + delta * delta * (a * b / total);
```

数学上的计数单位为有效元素，mean 与输入同量纲，M2 为输入平方量纲；最终 `variance=M2/(total−correction)` 仅在原计划相应分母域内使用。该 double 参考仍不能替代 oracle 对 NaN、Inf、±0、空状态与最终舍入的规定；kernel 应保持 C2 选定的累加 dtype、实际指令次序与合并树，不因参考使用 double 就添加新高精度路径。不能未经授权把负方差 clamp 到0，这可能掩盖错误或改变边界语义。

若每行有 `P` 份 FP32 `(mean,M2)` partial，状态逻辑存储至少 `8P` 字节加计数字段、对齐与 workspace；分组更细增加状态写读、合并次数与取舍误差，精度代价与流量同时核算。Cast 中间 buffer 和输出量化参数需活到最后消费者完成，不能因精度调试延长存活而忽略容量。

## 特殊值与验证矩阵

至少覆盖正负抵消、大均值小方差、大动态范围、长 K/长归约、最大/最小有限值、次正规数、±0、NaN/±Inf、全 mask、空/单元素与 correction 边界；比较不同合法分段数、顺序、tail 和 dtype。先确认 oracle 对 NaN 传播/忽略、Inf 运算和符号零的规定，再判断 API 输出，不能凭平均误差掩盖少数极端值超标。

Cast 的 CAST_NONE 不是普遍无舍入；Fixpipe F322F16/F322BF16 使用 RINT，和原 FLOOR/CEIL 等不等价。Mmad/Fixpipe 的 CTRL 饱和模式可能把 Inf 变最大有限值、NaN 变0；Mmad 固定文档还提示避免 NaN 输入。当原输入域包含这些值而目标路径不能保持契约，应保留原正确实现，不修改 CTRL/输入域来让测试通过。3510 新类型/舍入不能从其支持表搬到 A3。

失败特征包括平均误差小但极值超标、方差负值、全 mask 出 NaN、Split 后 bias 重复、只在中点舍入或量化轴错误。保留首个错误中间状态、完整 case 和日志，进入 precision debug；异常/挂起另保留 runtime/crash 证据。正确性不过不计性能，不能换近似、放宽门限或削减 case。来源事实是 Welford、Cast/Mmad/Fixpipe 固定契约；状态预算与验证矩阵为工程提炼。本条通用契约适用 all，具体 API 仍受目标 dav-2201/dav-3510 与 SDK 约束，没有目标硬件验证。

## 条件选择不是按名字替换 Max/Min

原实现若是 `a>b ? a : b`，相等时选择 b，NaN 参与比较的结果也影响选择；不能仅因 API 名叫 Max 就认定特殊值、符号零和 payload 行为一致。把“比较→predicate→选择”的 dtype、CMPMODE、Select 模式、有效元素和尾部单独核对，完整实施细节见 [Compare/Select 尾部](../../vector-api/recipes/compare-select-tail.md)。该组合不能解决 A2/A3 不支持的 dtype/比较模式；额外 Cast 会引入精度与资源代价，必须独立证明。

从固定 API 文档可确认 Compare/Select 的操作与模式；不能据缺少特殊值描述断言某个 Max 实现一定错误。保持原 oracle 边界，分别检查 `a/b` 为 NaN、±0、相等极值与无穷。性能未测不阻止选择已合法的组合；数值语义未闭合则需补具体依据。


## 局部加权和、finalCast与严格阈值

本条也覆盖只有K个邻居的小局部加权和，无需大规模归约才讨论顺序。绑定 `acc0`、每项 `term=weight_i*value_i` 的乘法dtype/舍入、acc更新次序、是否允许FMA及最后 `finalCast(acc)` 的模式。改成pairwise、分组partial、FMA或先把权重/值Cast再乘均可能改变结果；把finalCast移到每项或每组后也不自动等价。若选择数值组织变更，沿既有action.restructure_reduction及其reduction_semantics条件，不新造“近似精度”意图，也不以K小否定该Action。保存派生权重只减少生成，不能暗改乘加次序。

严格判据必须照抄oracle的定义与比较边：例如 `err < threshold` 与 `err <= threshold` 在边界不同；absolute/relative分母、NaN处理、零参考值和逐元素/聚合判据分别绑定，不能用均值误差代替严格逐元素上限。不在知识库预设通用容差。finalCast前后均保留必要观察，边界样本包括抵消、大动态范围、±0、NaN/Inf和恰在阈值附近的结果。

保护分支是语义的一部分：越界先判再读；空/零分母/特殊值按原定义处理；不能假设乘0消除无效值。Compare+Select可能计算两侧而非短路，若一侧有非法读取/除法不能把短路if直接改Select。安全后再比较保护代价：每元素predicate、mask初始化、额外Select/Cast、分支分歧、处理正常/异常域的重复工作、临时buffer和事件；不能为省分支放宽输入域或阈值。来源Compare/Select/Cast契约支持参数审查，不支持未写明的异常值行为；局部加权顺序与阈值审查为本次机制推导，无目标收益证明。

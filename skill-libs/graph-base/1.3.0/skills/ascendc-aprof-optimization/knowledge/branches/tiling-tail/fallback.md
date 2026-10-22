---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.fallback
kind: recipe
version: 1.1.0
status: active
title: Tiling / tail 回退方法
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 320
  sha256: sha256:8fd9166a39e7ab163695f1d965ad633725afa1c60cff08708b439f58f2a646ee
  excerpt_sha256: sha256:643aefa2bdb90c4fa26a228d9f36b5d487f11b9ebbcc80c4d7d3f52273abf98c
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 58
  - 148
  sha256: sha256:23e9b37e62ff5c2fed4b142ad65b346f8987aa6be527e291dae63466dc88f315
  excerpt_sha256: sha256:e4fc628736c5c7870254ce95b9ef24afb65e80df4762615190a2b173e22cb01d
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 31
  - 144
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:9b82f521bfc25b8c16cea361e35e230d057580630377745c5a4a099d56a39447
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/Kernel-Tiling/TILING_KEY_IS.md
  original_path: docs/zh/api/SIMD-API/basic_api/Kernel-Tiling/TILING_KEY_IS.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 29
  - 109
  sha256: sha256:6aa47a2f6a12a5b0954fed6e93f3c0c2c25922b37849c866187a04f21560ee74
  excerpt_sha256: sha256:e7791334b8daf11cce11428c3b16682a4728599933f1d08a77dac28ef701fb7d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 34
  - 220
  sha256: sha256:36da88132f7d5f62484bc98896bd99577bcce25d71a84e21220731a557aea34d
  excerpt_sha256: sha256:70619eed307e130c5d64b3936d3c609e096c608ba0b6bba136e773385fe5bd2d
learning: {}
tags:
- dispatch-domain
- tail-fallback
- valid-count
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.tiling-tail
references:
- implementation.tiling-tail.dispatch
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---

# 尾域或分发证据不足时使用已声明的通用路径

## 何时回退

候选对某shape/dtype/layout的有效长度、API范围、容量或entry覆盖尚不能证明时，使用C2已经声明且支持该元数据的fallback。fallback不是自行补一套C2条件/key，也不是遇到错误后重跑另一算法掩盖失败；如果计划没有覆盖该域或fallback没有实现，应报告缺项并回C2。

## 保守实现的关键等式

保留本任务起点B和有效量L。对允许的tile元素T>0，使用`Q=L/T+(L%T!=0)`、`vi=min(T,L-iT)`；L=0时不进入tile循环。对每个dtype分别算有效字节`vi*s`和UB对齐字节`AlignUp(vi*s,32)`，不要把UB容量加到GM范围，也不要把dummy当数学输入。二维普通DataCopyPad每行独立对齐；归约count用有效R，rowOffset用UB物理行跨度。

| 缺项/失败 | 回退动作 | 禁止的快捷处理 |
|---|---|---|
| full tile通过、tail失败 | 恢复已验证的短块路径和有效count | 将GM读写长度一律向上补齐 |
| 最后核无有效任务 | 保留C2空任务协议，跳过依赖生产的loop | `loops-1`下溢或等待从未发出的事件 |
| SDK字段容量/计数超限 | 在C2范围内进一步分组/缩tile | 强制cast截断长度/stride |
| candidate key无实际entry | 修复既定接线或使用已声明fallback | 裸else吞未知key、私改key含义 |
| tail需要更多转换/临时区 | 重新算最大分支UB/workspace | 复用仍被异步读取的槽 |
| 真实元数据不在C2覆盖域 | 明确返回重规划/既有错误路径 | 用case名或跑分结果发明条件 |

若原DataCopy路径要求对齐而尾块不满足，应使用目标支持的有效字节DataCopyPad或原有合法尾实现。API不支持时不能从其他架构拷一个mode模板或SIMT尾方法。归约最保守路线是用支持有效count的路径；如果只能处理对齐count，明确单位元和原数值语义后才能填充，Max的负值域、Mean分母和NaN处理都不能省略。

## 完成边与资源

队列/事件数量必须与实际执行轮数一致；短tile也有同样的producer→consumer→最后异步消费者关系。对双槽分别核算，`numSlots×AlignUp(maxTile*s,32)`按最大tile而非最后短tile计容量；输入/输出不同dtype、归约临时区、bank padding和workspace全部叠加。分发fallback的数据布局要与其kernel序列化契约完全一致，不能拿候选tiling结构凑字段。

## 验证与返回产物

先验证边界，不先追求性能：零任务既有语义、1元素、对齐边界±1、T−1/T/T+1、两个tile、不同任务起点和最后核；每个合法dispatch key至少一个可达case并覆盖其谓词边界。沿用原oracle和完整case域，检查输出唯一所有者、实际kernel entry、最后地址与静态UB分配。正确性失败保留日志和候选快照，回到原合法实现，不静默切换算法后继续计时。

提交C3时说明实际使用的fallback key/entry、有效域、参数变化、源文件身份、条目版本与未满足前提。只做来源审读应如实标明，不能把来源样例或历史validated标为当前性能资格。只有目标SDK构建、完整正确性与既定性能协议均完成后，才讨论接受该候选。

来源事实：DataCopyPad文档给出双端单位、对齐和有效字节；AR全载材料给出R与rLengthAlign区分；TILING_KEY_IS文档要求各key显式分支。回退矩阵、零任务循环式和C2接线边界为本树提炼，不搬运来源经验阈值。

# graph-base/1.0.0 独立硬件验收（2026-10-14）

## 最新授权与当前状态（2026-10-15）

用户已批准以源码和绑定 SDK 可证明的分配、临时区、对齐及可用容量作为 UB 审查准则，保留实际 SDK/构建身份检查。这不宣称获得编译器总 UB 上界，也不追认此前被拒绝的审查。

本轮 **exp / 910C A3 / CANN 9.0.0** 已补齐机制证据，最终机器门禁返回 **`production_safe_gain`，实际 exit 0**。单个 canonical optimization skill 的局部 Teacher 晋升及对应 Exp Wiki/index/evolution 更新已应用；独立发布审计与封存仍待完成，当前尚未发布 1.0.0，默认仍为 0.5.1。sigmoid 本轮不运行，其他规则保留 draft。45 次 validation 对比与封存后全量 test 均按用户指令 **not_run**，不作为本轮待执行项，也不能被记录为通过；不声称跨算子泛化收益。后文的双算子及 45 次比较要求属于保留的旧计划。

本轮复用了 `/tmp/aprof-teacher-boundary-fixed-20261015-ust71pmc/exp` 的独立 accepted 审查（45,893 个实际 token）、唯一一次候选构建、两侧各 20 个原始 case、42 个额外边界、独立六 case screen、完整 20×30 对正式 Task 样本及前后 A/A 控制。来源、构建、输入与阶段证据经过独立回放；没有重建、重新审查或追加正式样本。正式加速比为 **1.1885722798×**，95% 下界 **1.1882032839×**，20 case 均更快，无逐 case 回退。该结论仅覆盖声明的 Exp 工作负载和上述硬件/SDK。

原 baseline PMU 的 10 次预热、5 次采集及原始 oracle 被保留；仅缺失的 candidate PMU 新采 10 次预热、5 次采集并执行原 oracle，预登记的 `mte2_instructions` 方向证据进入同一机器门禁。该补采任务随后因 LocalEvidence 包装器误走 CAS 注册路径而 exit 2；样本和 oracle 均已完成。最后单独的 CPU gate-only 任务修复登记接线并完整在线验收，没有新构建、设备采集或计时样本。

| 实际任务 | 终态 | 执行器记录耗时 |
| --- | --- | ---: |
| 原始完整 trial；profile stdout/stderr 拼接解析失败 | failed / exit 2 | 2821.423869 秒 |
| 仅 candidate PMU 补采；门禁请求登记失败 | failed / exit 2 | 337.899868 秒 |
| 仅完成机器门禁 | passed / exit 0 | 286.803726 秒 |

三段实际执行合计 **3446.127464 秒**；连同续跑 launch 窗口核算为 **3446.129387 秒**，在单独登记的累计 5400 秒内。两次失败、各自原 deadline 和实际费用均不改写。归档及独立发布审计费用在任务后单列，不计回优化预算。

最终任务目录为 `/dev/shm/aprof-exp-gate-completion-20261015-rys12h6p`，dispatcher SHA 为 `sha256:bafe7eca85b05b66b2315638557c229f65041767224babc9c3ed4a2be2f30fea`。持久晋升回执为 [promotion.json](../../../validation-graph-base-1.0.0/exp-teacher-promotion-20261015/promotion.json)，SHA 为 `sha256:33be3448ee471db6899fa9278dc1524fdf7b073ee6ee44425f93c5752c95095c`。

本次仅更新状态文档，没有启动新的模型、硬件采集、回放、归档或发布。下文所有历史失败与当时的阻断状态原样保留，以本节为当前状态。

## 此前状态与执行历史（2026-10-15；由上节最新授权更新）

0.5.1 已封存并设为默认。1.0.0 已经用户明确授权升级至 runtime 0.2.3 / Task v5，以支持逐 case 的完整多 kernel 绑定；v0002、正确性与性能门槛不变。用户随后允许调整原 60 分钟预算：新一轮须按完整采集成本统一冻结有限预算与收尾预留，token 仅记成本。升级仍需独立硬件复验。具体源码差异与 CPU 检查见 [已应用记录](task-case-binding-v5/APPLIED.md)。下文保留此前 0.2.1 / Event 复验的历史结果，不代表当前候选已经通过。

Task v5 首次预登记的 exp、sigmoid 尝试均在独立源码审查阶段超出当时累计 8k token：分别为 15,836 和 15,736。两次真实任务均退出 2，构建次数和硬件阶段数均为零；没有源码接受结论，也没有新的正确性或性能结论。该轮已关闭，不在原尝试中重跑。任务结束后由独立收集流程保存[拒绝证据](../../../validation-graph-base-1.0.0/task-v5-review-budget-rejections-20261015/summary.json)，收集成本单列。

随后用户明确调整为 `time_only_v1`：每个新任务共享 60 分钟硬上限，包含生成、独立审查、构建、正确性、计时、profiling 和在线验收；token 只记录实际成本，取消生成 56k、审查 8k、合计 64k 的硬限制。单候选、一次候选构建、独立审查、正确性与性能门禁保留。旧失败回执不追认，后续尝试及所有比较组须按新规则重新冻结。审查首包去重和结构化结束协议已完成工具资格检查。

第一次 `time_only_v1` 实测中，exp 独立审查使用 84,978 个实际累计 token，8 项检查全部通过，随后一次构建成功。任务在 448.143 秒时因采集器不能将原始 case 12 的 `-Inf` 元数据写入严格 JSON 而退出 2；case 1–11 两侧均通过，case 12 尚未执行。没有边界、正式计时或性能结论。sigmoid 的原始元数据存在同一前置问题，明确记录为未启动，未伪造零成本执行。完整小型回执由独立收集流程在退出后保存于[该轮归档](../../../validation-graph-base-1.0.0/task-v5-time-only-json-rejection-20261015/summary.json)。

修复只允许原始 oracle 元数据保留其既有 Inf/NaN 表示；验收、计时和成本报告继续使用严格 JSON。在线与归档回放共享带类型检查的 NaN 比较。15 项 CPU 回归通过，覆盖原始元数据、完整小型 oracle 链和删除临时目录后的回放；原始输入、oracle 与阈值均未修改。下一轮 exp 的独立审查使用 60,742 个实际 token，通过 8 项检查；一次构建成功，原始 20 case 和额外 42 个边界的两侧 native/oracle 结果共 124 条均通过。任务在 1531.473 秒内退出 2：边界回放发现 protocol 缺少原冻结 generator 绑定，整体边界报告仍为失败。没有探索、正式计时或机制证据。sigmoid 因相同已确认的前置合同问题明确记录为未启动。原回执与 94 个执行 producer 在退出后由收集流程保存于[该轮归档](../../../validation-graph-base-1.0.0/task-v5-boundary-binding-rejection-20261015/summary.json)。

已修复 generator/verifier 绑定，并在审查、构建与设备执行前检查完整边界合同。CPU 检查覆盖 42/57 项边界和缺失绑定的零执行拒绝。对原 124 条结果的[诊断回放](../../../validation-graph-base-1.0.0/task-v5-boundary-binding-rejection-20261015/boundary-contract-diagnostic-v1/result.json)未发现额外边界合同问题；该诊断没有追认原失败。等待新冻结的独立硬件尝试，未晋升任何规则。

时间预算还覆盖本地源码准备与在线验收：准备时间扣除剩余额度，剩余时间耗尽时不启动子进程；在线验收超过总截止时间不能报告成功部署。token 的实际数量继续完整记账，不影响准入。归档仍在任务退出后单独执行。

用户随后明确允许按完整采集成本校准时间上限：60 分钟属于可调预算参数，不能仅因达到该初始值而粗暴中断正常采集。下一次比较须在运行前冻结统一的显式上限，三组及各 seed 一致；保留单候选、一次构建、独立审查、正确性和性能阈值。正在参数化旧控制器和回放中的 3600 秒常量；已启动任务的原始 deadline 与实际耗时不重写，归档成本仍单列。

## 以下为 2026-10-14 历史结果

本轮按原发布门禁执行。四条独立尝试均未取得晋升资格，**未封存 1.0.0，默认
继续使用 0.5.0**。原始数据、拒绝原因及未应用的 Teacher 提案均已保留。

## 环境与冻结边界

- 实测设备：Ascend910_9392，910C/A3，24 AIC / 48 AIV，UB 196352 字节。
- 工具链：CANN 9.0.0，目标编译器探测通过。正式计时在独占设备窗口执行。
- 仍使用 runtime 0.2.1、v0002 图及原机器验收阈值；未用 lesson JSONL 作为 reward。
- 66 条原始来源、当前 split 和排除决定继续由 `graph-base-1.0.0.json` 固定。
- 原始来源不变；本轮证据另存于工作区 `validation-graph-base-1.0.0-20261014/`。

## 已完成的独立尝试

| 提案 | 完整正确性与额外边界 | 本轮判定 |
| --- | --- | --- |
| exp：tile 4096→8192 | baseline/candidate 各通过声明 20 case 和额外 42 case | A/A 的 case 3、9 角色偏差为 2.4353%、3.6243%，超过预设 2%；在候选 A/B 前停止，性能不确定，未晋升 |
| foreach_norm：动态 partial 划分 | 两侧声明 20 case 通过；额外边界前五个 FP16 p 分组共 160 个张量检查通过 | 原始 baseline 的 FP16 p=0 语义失败；按计划停止，未计时、未晋升 |
| sigmoid：两槽流水 | 两侧各通过声明 20 case 和额外 57 case | 正式 600 对计时观察约 1.3175× 加速，但后置 A/A 的 case 8 跨会话漂移 3.563358% > 2%；未晋升 |
| masked_scale：一 tile 预取 | 两侧声明 20 case 均通过 | 第一个额外边界发现 baseline 在 FP16 中间溢出上的语义不一致；停止，未计时、未晋升 |

norm 首次两线程 CPU 参考在 FP32 p=3 上出现偏差；已保存该失败及 FP64 诊断。
随后恢复历史已独立核验的 32 线程参考环境，生成器、verifier 和容差均未修改。
其机器 `accuracy_failed` 表示额外语义范围未完成验收，不表示候选声明的 20 case
失败。没有在看到边界结果后删除 p=0 或缩窄本轮范围。

exp 的同源 A/A 两侧 CV 均低于 5%，仍未通过角色偏差控制。未通过的 A/A 样本
不能作为候选性能回退证据；本轮没有重采样、没有以探索样本冒充正式计时。

详见候选包 `wiki/evolution.jsonl` 的哈希绑定 `evidence_refs`；外部尝试目录中的
`closure.json`、`exploration-request.json` 和 `gate-replay.json` 保留机器回放结果。
所有执行费用按各阶段 `execution.json` 的真实时长、退出码和日志保留。

## sigmoid 的未获准发布性能观测

sigmoid 两槽流水已通过两侧各 20 个声明 case、57 个额外边界，以及前置 A/A。
六 case 探索筛选几何平均约 1.317×，不构成正式收益。独立的 20×30 对正式计时
已完成：几何平均 1.317478×，95% 加速下界 1.313086×，20 case 均更快，最大逐
case CV 为 1.878%。后置 A/A 的 case 8 在其中一个角色上的跨会话均值漂移为
3.563358%，超过预设 2%；另一角色为 1.433158%。本轮按此强制门禁停止，未采集
机制 profile，Teacher 的单 skill 修改草案留在包外，未应用到技能文件。

实际正式报告保持 `stable=true`，没有为制造失败结论而改写原始测量。正式数据
作为未获准发布的观测保存；机器回放返回 `artifacts_incomplete`，没有生产接受
或 policy episode。控制实验失败不等于候选性能回退，也不支持直接封存。

阶段执行时长：正确性与边界 362.94 秒，前置 A/A 143.46 秒，探索筛选 144.99 秒，
正式计时 522.71 秒，后置 A/A 148.42 秒。配置、构建和其他尝试的费用保存在各自
执行回执；这些阶段时长不能当作整个 Teacher 工作的模型 token 费用。

## masked_scale 边界与未验证提案

预先固定的第一项额外边界为 shape `[33]`、FP16 `x=65504`、int8 `mask=2`、`scale=0.5`。
原有 PyTorch 参考在中间 FP16 乘法溢出为 Inf；原始 kernel 提升为 FP32 后计算，
给出有限值，因此未通过原 verifier 的特殊值掩码检查。这是继承的 baseline
语义差异；候选在该边界尚未运行，不能归因于预取改动。没有删除这个边界、改
oracle 或重新缩窄提案范围；后续 A/A、候选计时和 profile 均未运行。

norm 的 p 分支特化尚无独立晋升回执，不能继承 partial 提案的资格。

## 仓库与发布检查

- Teacher、发布门禁、评估器和适配器相关测试：52 项通过。
- registry 有效；45 个 runtime、图和 schema 文件与 0.5.0 字节一致。
- 0.5.0 封存校验通过，200 个文件保持原样。
- Teacher 校验通过：66 条来源、9 篇 Wiki、0 个晋升 skill，当前 split 隔离有效。
- 实际调用封存入口的拒绝检查通过：因没有独立验证的晋升规则退出，未创建
  `release.json`，默认仍为 `graph-base/0.5.0`。
- 45 次 validation 和封存后的 test 均未运行。

完整回执索引及执行费用见 [硬件验收 JSON](graph-base-1.0.0-hardware-validation.json)。
记录的各尝试阶段时间（重叠区间合并）为 exp 484.216 秒、norm 879.586 秒、
sigmoid 1363.986 秒、masked_scale 695.273 秒；不含未由执行器包装的准备、协调
和 Teacher 模型 token 费用，也不把这些时间当作等预算评估结果。

评估工具还保留明确的启动阻断：模型 worker 的“零额外编译”预算没有操作系统
或工具层的强制执行，因此冻结、模型启动和发布均会直接拒绝；配置中的自报
凭据不能绕过。此外，复杂流水/算法修改的独立源码审查路径、五个 baseline 的
硬件资格及评估器硬件正向路径尚未完成。详见
[评估协议与限制](graph-base-1.0.0-evaluation.md)。CPU 测试不代表这些验收已通过。

历史档案暴露也保留披露：本轮来源盘点确认 `apply_rotary_pos_emb`、`gather`、
`rms_norm`、`scatter`、`softmax` 已属于当前 test，历史记录均从本轮 Wiki/技能
训练来源中排除。不能把未来 test 结果宣称为没有任何历史接触的评测。

只有独立规则晋升、冻结候选和完整 45 次等预算主比较均通过，才允许生成 stable
manifest 并切换默认入口。失败及不确定提案继续保留为 Wiki 观察。
# 2026-10-15：Task-v5 本轮关闭与后续修复

`509bc26e...` campaign 已关闭：exp 实际运行 2821.424 秒、exit 2；sigmoid
因相同采集器缺陷未启动。exp 的 20 个原始 case 与 42 个边界检查均通过，
正式 Task 计时报告为 1.188572×、95% 下界 1.188203×，但整项任务没有通过。
机制阶段原始 verifier exit 0，stdout 是正确 JSON，stderr 是库警告；旧 bridge
把两者拼接解析，触发 `JSONDecodeError: Extra data`。这些历史结果未被改写。

修复仅解析有哈希绑定的 stdout，并保留 stderr。8 项 CPU 回归及真实已保存
输出回放通过；关闭记录独立重放为 exp failed、sigmoid not_run，未补跑旧任务。
完整 exp 归档在实际退出之后由 trace collection 完成，耗时 461.603 秒，
没有算入优化任务。索引见
`validation-graph-base-1.0.0/task-v5-exp-mechanism-stream-rejection-20261015/collection-result.json`。

退出后执行的一次预登记 whole-app PMU 设施检查与原始正确性校验均 exit 0。
真实导出使用 `aic_*` / `aiv_*` 列；LPM 原始二进制包含 type 0 频率变化，
可以用 SDK 时钟锚点关联到完整 Task 区间。新增只读解析使用这些原始变化，
缺失锚点、任务内变频或不支持的时钟修正保持 unknown；不把静态 info.json
频率当成当前频率。92 项相关 CPU 检查通过，仍不代表五个 baseline 完整资格通过。

用户已允许调整原 60 分钟参数。下一轮先统一冻结有限预算和采集收尾预留；
预算覆盖生成、审查、构建、正确性、计时、profiling 与在线验收。三组/各 seed
预算相同，token 只记成本，归档单独计费；新预算与完整硬件资格尚待校准。
默认版本继续为已封存的 0.5.1，1.0.0 暂无规则晋升或稳定发布。

## 2026-10-15：可配置预算与有界采集收尾已接线

按最新用户指令，60 分钟改为每轮开始前冻结的有限参数 B；token 只记成本。新 controller 与回放器绑定同一父时钟 D，子阶段不能续期。采集在 D−R 后不启动新单元，已开始的完整单元在原 D 内收尾；真正挂起仍由预登记单元期限约束。screen 六个固定 case 是一个单元，正式 Task 按完整周期、PMU 按完整回调/原两角色单 kernel 流程各自收尾，未完成证据不获准入。

CPU 检查：runtime/采集/PMU 111 项；Teacher 预算与负向回放 70 项；真实短子进程 campaign 与父 launch 保持 21 项；baseline/validation controller 45 项；Context/trial 48 项；受保护机器规则负向 3 项；retained review 20 项；screen 新增 17 项。不同组可能复用检查，不将计数当硬件验收。真实旧 exp 审查可独立回放 45,893 token 的 accepted 决策；该旧任务仍是失败。

新工具资格已捕获并核验三种实际工具集合：`sha256:0cad95cf47389fbef0455ce23fdeaf7a3b663d9673edda951e9722e6ca3fcd19`。旧 0.5.0/0.5.1 manifest 和 53 项受保护机器文件校验通过；v0002 与性能阈值不变。

新 Teacher 轮次：`/dev/shm/aprof-teacher-adjustable-budget-20261015-mye7mbxn`，campaign `sha256:5a34f062cbb6a3552a5f6d3b9012e9111a04b3a96e7e72e466900acc92f731c5`。基于旧 exp 2,821.42 秒、额外 sigmoid 边界和剩余 PMU/在线验收估算，预登记 B=5,400 秒、R=600、Task 单元=300、PMU 角色单元=540、终态写入=60 秒；估算不冒充测量。exp 已启动，sigmoid 尚未启动。未完成本轮前不晋升技能。45 次比较的 B 仍待五个 baseline 的完整成本校准后统一冻结；多 kernel 调用数大，不能直接套用单 kernel 单元期限。

## 2026-10-15：上述轮次已结束；重型 baseline 的实际成本

上述 campaign 的两个尝试均在独立源码审查阶段结束，未构建、未启动硬件。
exp 实际 240.416 秒、62,726 token，UB 总资源证据为 unknown；sigmoid 实际
118.470 秒、39,956 token，UB 与临时缓冲区同步证据为 unknown。均非预算拒绝。
trace collector 在实际退出后完成归档（42.410 秒）与只读回放（12.678 秒）；
原拒绝结论不变。索引为
`validation-graph-base-1.0.0/task-v5-adjustable-budget-review-rejections-20261015/summary.json`。

随后进行预登记的原始 baseline 单次完整调用成本定位；不运行候选，不授予资格。
第一版在构建后、采集前因把 oracle Python 文件当 JSON 读取而失败；旧回执保留。
修正该指针读取后，新一版两个 probe 均实际 exit 0，完整任务序列与原始 oracle 通过：

| 算子/case | 完整 Task 数 | Task 总和 | Task 跨度 |
| --- | ---: | ---: | ---: |
| GQA/14 | 2,051 | 2.826907 秒 | 2.855342 秒 |
| GQA/17 | 2,051 | 3.284290 秒 | 3.315576 秒 |
| weight_quant_batch_matmul/20 | 3 | 18.316790 秒 | 18.317175 秒 |

原始记录位于 `/dev/shm/aprof-baseline-call-cost-observation-20261015-v2/`。
这是一次 whole-app Task+PMU 观测，包含 profiling 扰动，不能当作无 profile 延迟、
正式采样或五个 baseline 的资格。旧 v5 每 case 最低 26,054 次完整调用；按本次
WQ 跨度条件性外推约 132.6 小时。只提高总时限无法消除这种采集成本。

已提出独立的 v6 草案：共同 baseline pilot 冻结各 case 的重复与预热次数，最低
一次完整调用，仍保留六周期、正式 30 对、前后各 30 对 A/A、完整 20 case 与
原数值门槛。该改变超出仅调整总时限，等待用户答复；尚未修改生产采样协议。
即使最低计数，WQ/20 含共同 pilot 仍需 281 次完整调用，按上述一次观测外推
约 85.8 分钟，仅此一个 case。比较总预算、单元期限与收尾预留必须由后续独立
校准确定，不能把 Teacher 的 90 分钟直接套给 45 次比较。

本轮仍为 0 条晋升规则、0 次 validation 比较；默认继续使用已封存的 0.5.1。

### 2026-10-15：SDK 证据补充后的新独立复验

新增匿名 v3 合同保留原合同和八项检查表，补齐 SDK primitive、Sigmoid 临时区及同步源码、ABI 上界和真实平台容量观测。实际构建新增工具链与有效参数绑定，34 项 CPU 测试通过；这不代替候选构建或硬件准入。

新 round：`/dev/shm/aprof-teacher-sdk-evidence-20261015-dd4tlcr7`。统一 B=5400 秒，R=600 秒收尾窗口；Task/PMU 单元上限分别 300/540 秒，终结记录保留 60 秒。token 只记录成本。exp 已开始独立审查，sigmoid 已预登记待启动；每个算子仅一次尝试。原失败不变，仍用 Task-v5；重型算子的新采样提案尚待答复。所有 producer 已冻结，原始数据仅在任务本地保存，实际结束后由独立 collector 归档。

新 round 已闭合：exp 实际 exit 2，189.299 秒，UB 上界与 Vector 链同步为 unknown；sigmoid 实际 exit 2，108.050 秒，仅 UB 上界为 unknown。均在独立源码审查阶段终止，没有候选构建或硬件样本，也没有触及预算。当前合同把尚不存在的角色编译资源证明放入源码审查，而唯一构建仅在审查通过后启动，形成阶段依赖冲突；此问题需明确责任与可执行凭据，不能将失败改为通过。新 SDK 构建身份工具的真实构建验收尚未到达。

同步补充（只读定位，不改变本轮拒绝）：CANN 9.0 编译器 Automatic Synchronization 文档说明 Kernel 直调工程默认自动同步并插入 PIPE_V，前提是调用函数 inline 且遵循 Ascend C 编程模型。TBuf 计算临时内存不能入队，SDK TBuf::Get 含 sync_alias 属性。因此源码无手写 PIPE_V 或临时张量未入队本身不足以证明错误；仍需将这些条件与实际构建绑定。官方来源：https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/compiler/BishengCompiler/atlas_bisheng_10_0008.html 。当前未追加构建或审查。

独立 collector 已在两任务实际退出后完成本轮归档及失败回放：`/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/validation-graph-base-1.0.0/task-v5-sdk-evidence-review-rejections-20261015`，summary `sha256:2ea4227016dc12a4bae521a1e53e589ad678c7ac907242f858166e1d221e6f29`。归档 53.014 秒、回放 15.630 秒，成本均属 post-task；SDK/tool identity 引用经 archive reader 核验。两任务仍为 failed，0 构建、0 硬件；没有补样、追加审查、晋升或发布。

预算修改已完成。重型算子的 repeat/预热协议修订，以及 UB 验收是否采用源码/SDK 可证明分配边界，两项定义问题均已提出，等待用户选择；当前未启用这些修订。0.5.1 继续为默认稳定版。

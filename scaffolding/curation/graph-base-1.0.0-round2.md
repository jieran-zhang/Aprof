# graph-base/1.0.0 第二轮：控制实验与发布凭据

本轮只重新验收 sigmoid 两槽流水和 exp 的 tile 4096→8192。norm 与
masked_scale 的语义问题保留为后续独立提案。原始第一轮失败、来源索引、
当前 split、runtime 0.2.1、v0002 以及 0.5.0 发布包保持不变。

本轮已按停止规则结束，工具资格通过、两算子计时控制被拒绝。
详见[实际结果](graph-base-1.0.0-round2-results.md)；下文保留登记流程定义。

## 有限硬件流程

运行目录为工作区 `validation-graph-base-1.0.0-round2-20261014/`。
`round-plan.json` 和两个算子的阶段登记在设备运行前固定。每个算子只有
一次旧协议诊断、一次 v2 诊断、一次独立确认和一次候选验收的名额。
旧协议失败保留为对照；v2 诊断或确认的必需检查失败即结束该算子的本轮。
未运行阶段保持未运行，不能补写通过结果。

v2 每个 case 建立两个真正独立的进程/context/设备分配周期，启动顺序
分别为 A→B 和 B→A。两侧 READY 后按 A/B/B/A、B/A/A/B 各执行四批
100 次完整算子预热；预热不进入样本。正式 30 对分为每周期 15 对，
保存真实局部样本编号、全局顺序、进程标识和单调时间。

诊断控制使用原六 case、六对样本；独立确认和候选验收的前后 A/A
使用 30 对。完整算子计时范围、repeat=100、原 20 case 和 exp 42 /
sigmoid 57 项额外边界不变。总体与各周期均检查 sample CV≤5%、
`abs(gmean(B/A)-1)≤2%` 和逐角色算术均值漂移≤2%。baseline-only
长会话检查 A/A 质量；加速下界≥1.03 只适用于真实优化候选。

## 可重放的控制与边界证据

`timing_admission.py` 在冻结 runtime 外核验协议、独立登记、真实阶段
事件链、前后控制和正式采样。Teacher 和评估发布共用该验证器。控制
回执绑定原始 stdout、源码、二进制、输入、oracle、采集程序和硬件；
汇总 `passed` 或正式报告的 `stable=true` 不能代替整个生命周期的准入。

边界计划固定 dtype、大小、属性、特殊值和输入哈希，结果绑定两角色
逐项执行、原 verifier、metadata 与输出字节。部分执行和失败仍保留，
不可减少边界清单后重新声称通过。

## 等预算评估工具

模型使用外部文件工具 broker；模型进程中的工作树只读。候选写入只由
broker 执行，shell、代码执行、插件等执行入口关闭。模拟 provider
捕获实际模型请求与完整工具 schema；CLI、配置、模型、effort 和实现
文件均须与资格回执一致，不能以自报零编译解锁。

候选生成 56k token、独立审查 8k token，共享 64k 和 60 分钟。审查
只读匿名源码、diff、合同和检查表，不读实验分组、Wiki、候选性能或
生成对话；关键项 unknown/fail 拒绝且不增加候选修改轮。仅可信
controller 执行一次构建和一组计时/profile，前后控制属于这一计时组。

`graph_route(context_id)` 仅重放冻结 Context、规划材料与已有谓词证据。
候选必须绑定实际选中的合法边；等待比例不能单独将 overlap_low 置 true。
缺少校准或时间线仍为 unknown。任意 host launch/loop/timer 重构继续
不在本轮自动准入范围内。

## 知识与发布

新增 `exp-tile8192` 条目只绑定 exp 的两条训练来源；综合
`tile-amortization` 条目继续独立保留 mish、addcdiv 等未验证观察。
未获独立回执的条目保持 draft。接受提案每次只修改一个 canonical
skill，并绑定 before/after 与实际硬件回执。

只有独立规则晋升及冻结的 45 次等预算比较均通过，才封存 1.0.0 并
更新默认入口。主比较、bootstrap、失败回退与 correctness 要求不变；
validation 不回流调技能，test 在封存后仅评估一次。具体执行结果另记
在本轮 JSON/硬件回执中；本文件定义流程，不代替验收结果。

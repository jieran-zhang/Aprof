---
name: ascendc-aprof-profiling
description: 为 Ascend C 算子执行统一 L2 清理 Task 计时、完整调用解析和性能收尾；按诊断需要另采 msprof 或 npu-compute 机制指标，保留可回放原始证据。
---

# Ascend C 性能采集

工作流中的调用职责见 [profiling 角色](../../workflows/agents/profiling.md)，输入输出和阶段文档见 [profiling contract](../../workflows/contracts/profiling.md)。本 skill 维护专业操作；跨角色调用由协调者按 contract 分派。

优化会话由 [主工作流](../ascendc-aprof-coordinator/SKILL.md) 编排。本 skill 负责采集与解析，不自行选择图动作、改代码、制造机制结论或训练奖励。

## 性能计时

反馈与正式收尾唯一协议为 [统一计时](references/unified-timing.md)：`single_role_l2_clean_task_v1`。每 case/实现一个新进程，5 次预热、20 次逐轮清 L2 的完整调用，以逐轮全部目标 Task 之和的中位数计时。

- 先确认该源码已构建并通过完整声明正确性。复用原回执，不因增加 profiling 视图重新构建或重新生成输入。
- 先声明 case 集、输入、设备、比较父版本和复用/复验策略；检查 source-bound native adapter 的完整调用、清 L2 和输出路径。
- 使用 `scripts/single_role_task.py` 调度预构建 adapter、导出和校验。设备稳态准备在计时外完成；真实驱逐 callback 由算子工程提供。
- 采集记录独立于 A/B 比较角色；相同来源和有效条件下可复用。每轮只为缺失的实现/case 采集。
- 代表集给反馈；完整声明集合及证据齐备后交由协调者调用 `tools/aprofctl timing finalize` 一次收尾。不再切换 v5 或串行调用旧 gate/finalize。
- 单进程 CV 只反映轮内波动。新门槛是中位数比点估计，不是 paired/95% LCB。复用超时、环境变化和预声明的异常复验仍用同一方法。
- 不丢慢 Task，不挑有利前缀，不把多 kernel 调用简化成最长 kernel 或各 kernel 中位数之和；缺 Task、乱序、流不明或变化必须拒绝。
- 缺少 adapter 或兼容证据时报告缺项，不静默回退旧计时。失败采集保留日志与实际成本。

正式性能结果不等于语义、生产范围、图路由或机制归因均已通过；也不自动成为策略 episode。

## 机制采集与架构路由

机制 PMU 回答“为什么变化”，与计时分开。源码/workload 足够提出假设时先使用已有证据；图动作需要尚缺的 profile 谓词时先补足。未实现 extractor 保持未知。

根据真实设备与已安装工具选择后端，细节见 [后端路由](references/metric-to-profiler.md)：

| 环境 | 机制后端 |
| --- | --- |
| 910C/A3 | msprof op |
| 兼容的 950/dav-3510 | 优先 npu-compute，核对版本和单算子支持 |
| 未知或不兼容 | 返回计划与具体缺项，不安装或升级 CANN/驱动 |
| 用户要求模拟或无硬件 | simulator，仅作代理证据 |

机制采集按 [collector 接口](references/collector-interface.md)执行，按 [解析规则](references/report-parsing.md)归一化。选择能验证当前假设的最少指标/区域，不因完整正确性覆盖较大就对每 case 采 PMU。msprof 当前使用 `--aic-metrics=Default`，少选归一化指标并不减少采集成本，不宣称实现了逐 Section msprof 采集。

正式机制证据保留至少 10 次已记录预热、5 次独立 capture 与 CV≤0.05 的现有要求。这是机制证据要求，不能移作性能计时轮数。Core 行、Section 行、内部 replay 和 Pipeline 采样组都不算独立 capture。

兼容的基线机制 profile 可以复用，必须匹配 source、workload、设备/频率依据、后端/工具、collector、选择器含义和测量策略。不能只把 candidate 角色改名为 baseline；这与新计时中角色无关的测量记录是不同契约。

## 来源与交付

原始文件、选中 collection、kernel、源码/二进制、输入、设备、工具版本、策略及执行回执一起保留。JSONL 不能改写成 CSV 冒充原始来源；字段缺失和 NA 保持未知。

归一化与 runtime 回放后，经协调者把值、波动、替代机制及缺失视图交回诊断，保留 `linked_hypotheses`。schema 通过不等于采集成功，Agent 填写 `passed` 不能替代原始来源核验。

原始数据保存在任务私有目录，采集和在线判定共用任务预算；永久复制、CAS 和归档由明确要求的独立 collector 负责。安装结构检查不等于硬件验证。

## 工具入口

- `scripts/single_role_task.py`：当前统一采集 controller，算子提供 native callbacks。
- `assets/device_single_role_task.h`：5/20 原生采集时序。
- `scripts/fast_task_samples.py`：完整调用 Task 解析。
- `scripts/fast_task_screen.py`：早期草稿比较兼容入口，不将旧 manifest 自动升级为正式证据。
- `scripts/prepare_workload.py`：可验证的输入/oracle 准备复用。
- `scripts/run_profile_stages.py`：按 argv 记录阶段顺序、超时、退出码与日志。
- `scripts/profile_capture.py`、`scripts/normalize_profile.py`：独立机制采集与来源归一化。
- `scripts/device_task_window_timing.py`、`device_task_timing.py`、`device_shared_timing.py`、`device_paired_timing.py`、`paired_timing.py`：历史或诊断工具，不是当前性能验收入口。

仅在解释历史结果时读 [旧 v5 边界](references/shared-timing.md)。当前命令见 [统一协议](references/unified-timing.md)和 [collector 接口](references/collector-interface.md)。

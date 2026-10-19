# 编排职责、复用与任务生命周期

主流程由 [角色与 contract 工作流](../aprof-performance-workflow.md) 定义；采样与判定规则只在 [统一计时协议](../../skills/ascendc-aprof-profiling/references/unified-timing.md)维护。

## 会话内复用

协调者按 [公共契约](../contracts/common.md) 分派阶段文档，引用计划、源码/补丁、执行回执和本地证据。决策和最终摘要引用这些产物，不要求每个角色重述上游完整分析。

| 可复用内容 | 失效条件 |
| --- | --- |
| 输入、oracle 文件 | workload、依赖内容、生成命令/环境或文件完整性改变 |
| 基线构建/正确性 | 源码、二进制、工具链或正确性契约改变 |
| 统一 Task 测量 | 实现身份、case/输入、设备、工具、collector、缓存/地址策略不符，或超出预声明复用时限 |
| 架构/并行计划 | 硬件能力、语义、算法、分解、所有权、归约或 workspace 改变 |
| dispatch 分组与规则 | metadata 域、key/group/entry/fallback 改变；每次候选仍重绑实现 hash |
| 基线机制 profile | 源码、workload、设备/频率、后端、collector、策略或选择器含义改变 |

准备复用不缓存候选正确性。测量 artifact 不含固定 A/B 角色；比较时指定父版本与候选，前轮 B 在兼容条件下可直接作后轮 A。原始基线独立保留，父子链不证明因果加速。

所有原始记录只引用、不改写。执行时核验 live 身份，不能用会话预检缓存取消实际身份检查。

## 反馈与收尾

代表集反馈和完整集合收尾使用同一 5/20 方法。正式收尾补齐缺少的 case，引用已有合格采集，不另启旧配对协议。完整正确性范围可以大于 timing case 集，但必须覆盖全部计时 case。

异常、过期或近阈值结果按事先声明的规则用同一方法复验，保留全部结果；不能择优重试或用更强筛选门槛排除原本允许的 3% 收益。点估计不是置信区间。

机制 PMU 按图谓词或归因需要采集，不因正确性矩阵较大而对所有 case 重采。独立诊断请求可以直接采 profile，无需创建候选。

## 失败交接

角色边界与阶段推进以 [主流程](../aprof-performance-workflow.md) 和各 contract 为准。静态/API/容量问题由优化角色调用 code-review；精度问题用 precision-debug；非零运行用 runtime-debug；挂起/崩溃/AIC 用 crash-debug；采集缺项由 profiling 查明。需要其他角色的工作时交回协调者。

保留原失败、实际退出和部分产物，修复或补证据使用新阶段实例，不能重新命名为成功。

<a id="runtime-state"></a>
## 运行状态与交付

证据保存在任务私有 scratch，最终代码和中文报告放 final。正式收尾一次调用 `timing finalize`，不再先旧 candidate gate 再 episode finalize。新性能工程结果不自动授予旧策略 reward 或生产 best；历史 episode 仍按原契约回放。

优化 Agent 不做永久 profile 复制、CAS 导入或归档审计。用户要求归档时，独立 collector 必须保留失败、超时和原始结果，单独报告成本。归档不能补完或改变线上失败。

在线核验和交付后，只清理任务拥有的 scratch；被后续回放、继续任务或交付文档引用的证据先保持可访问，不能在引用闭包仍依赖 scratch 时删除。要求归档时先等完整交接。保留用户源码、最终交付物、安装包及所有活跃符号链接目标。禁止把 traces 写入 skills/ 或任何知识源目录。未封版结构校验不是硬件资格或默认切换。

<a id="task-workspace-and-budget-commands"></a>
## 工作区与预算命令

<a id="stage-budget-policy"></a>
### 阶段预算绑定

任务带入冻结的外层 `budget_policy_ref` 时，先核对 policy 与任务预算一致。`task_budget_seconds` 用于总 deadline；`stage_timeout_seconds.C0_capability` 用于 C0 指令、阶段检查和成本判断。C0 从任务接收 seed 的原始单调起点开始，包含技能读取、模型/工具等待与交付后的排队；有效 C0 deadline 为 `min(task_deadline, task_started_monotonic + C0_capability)`。每个依赖调用的 timeout 不超过所属阶段与总任务的剩余时间，子角色和 continuation 继承原期限。

阶段耗时、限额、是否超限及超限秒数使用同一 policy 与原始时钟计算。1.1.0 Vector 验收的具体额度由批次冻结策略提供，不能以旧 run 的 180 秒 C0 常量覆盖；其他任务不自动套用 Vector 额度。阶段或总期限耗尽后停止依赖执行，已确认的硬阻塞及时返回 needs_input/blocked。独立归档预算另计，不用于补跑已停止任务。扩大总预算不会扩大已冻结的测量复用有效期。

policy 引用及阶段控制字段写外层 manifest/C0 文本，不加入严格 Context 或 runtime budget plan；runtime 保持接收调用者的真实预算和原始期限。新策略只用于新任务，不能改写历史 launch、失败、超限或成本记录。

### runtime 命令

全程使用同一包的 `tools/aprofctl`：

```bash
tools/aprofctl task workspace-create --task-id <task-id> --parent /tmp
tools/aprofctl task budget-check --plan <budget-plan.json>
```

workspace 返回 root、scratch、final。只有要求后续归档时创建时加 `--collect`。budget-check 的 plan 模式只校验结构；回放实际原始期限使用：

```bash
tools/aprofctl task budget-check --local-index <local-index.json> --launch-ref <sha256:launch> --task-id <task-id>
tools/aprofctl task run --local-index <local-index.json> --budget-ref <sha256:budget-plan> --job-ref <sha256:job> --destination <new-task-scratch-job-directory>
```

task run 是进程监督器，不是完整优化调度器。受信 controller 冻结 job 的 argv、cwd、environment 和输出路径；调用 `local_archive.freeze_package_identity(local)` 并写入 `package_identity_ref`。执行和归档按此身份核验，不能换默认版本重新解释任务。

有子证据索引时在 job 预声明 `evidence_indices` 和明确输出目录，父进程合并引用而非复制原始数据。缺少声明索引使任务失败，但保留子进程实际退出码与部分证据。普通无索引 job 可省略此字段。

失败或超时 CLI 返回 2，执行回执保留真实退出和耗时。只有明确授权续跑时传完整有序 `--prior-terminal-ref` 链；此前失败成本累积计入预算。复用阶段仍需独立来源/二进制/输入/回执核验，不能靠自填 passed 或重置 timeout 续期。

交付并核验终态后：

```bash
tools/aprofctl task cleanup --workspace <root> --local-index <root/scratch/local-index.json> --terminal-ref <sha256:terminal>
```

创建时带 `--collect` 的工作区还需 `--collector-receipt <receipt-outside-scratch.json>`。只移除该工作区 scratch，保留 final 和外部路径。缺少终态或交接证据应拒绝清理，不用递归删除绕过。

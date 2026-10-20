# AProf 运行时契约

Python runtime 是语义校验的权威入口。JSON Schema 描述文件形状；跨字段身份、原始文件哈希、完整调用边界、输出数值、case 覆盖和执行回执还需要 runtime 回放。

1.1.0 的性能工程验收使用 `single_role_l2_clean_task_v1`。相关契约是 `unified-timing-declaration`、`unified-timing-capture`、`unified-timing-request`、`unified-correctness` 和 `unified-timing-result`。采集记录没有 A/B 角色，也不绑定比较父版本；比较请求将两个源码版本绑定为 A 与 B。

```bash
aprofctl timing finalize --request comparison.json --output timing-result.json
aprofctl timing verify --result timing-result.json
```

第一次命令完成一次完整回放并输出独立性能结果；第二次命令只在需要再次审计时运行。验收要求每 case/角色 5 次预热、20 次逐轮清 L2 的完整调用，完整正确性覆盖和原始输出重算，全部声明的计时 case 覆盖，轮内 CV 不超过 5%，中位数比的等权几何平均至少 1.03，任一 case 耗时回归不超过 3%。预声明有效期或 A/B 间隔超限会得到 `inconclusive`，不能靠删掉慢样本恢复通过。3% 是工程点估计目标；20 轮不是 20 对独立进程，也不产生 95% 置信下界。完整正确性 case 可以比计时 case 更多。

预声明中的有效期是任务选择的复用限制，并非已经完成硬件校准的结论。原始输出回放核验冻结 golden 与实际结果相符；golden 的来源、精度阈值、算法语义、静态审查和图路由仍由工作流的相应阶段负责。结果的权限固定为 `performance_engineering_only`，不自动生成生产最优标记、训练奖励或旧 candidate episode。

当前 controller 的 oracle adapter 仅支持 little-endian `float16/32/64`、`int/uint8/16/32/64`、`bool` 的冻结逐元素 `atol/rtol/equal_nan` 检查。其他原始 oracle（例如 mean/max-relative 判据）需保持原有精度标准并实现相应 adapter；不能更换判据来迁就此格式，也不能宣称已通用接入全部算子。

旧序列化版本 `1.0.0` 的契约保持历史兼容。原有配对测量、gate 和 episode 算术仍用于旧证据回放；1.1.0 不允许旧配对计时通过 `candidate gate` 或 `episode finalize` 接纳新的性能结果。未执行的构建/正确性失败和合法 NOOP 仍可记录。

`handler-attempt.schema.json` 是探索过程的独立辅助记录，描述 handler、参数、上下文和重试决策；它不证明图边身份，不写入旧 episode，也不授予奖励权限。

`architecture-profile`、`parallel-plan`、`dispatch-plan` 用于 v0002 回放，也由当前 C2/C3 按原严格格式引用，可用 `aprofctl contract validate --kind architecture_profile|parallel_plan|dispatch_plan --input FILE` 校验其中一种。规划契约另行拒绝冲突身份、无效元数据条件和重复 uint64 tiling key。`Context.evidence` 保存对象及对应 `*_ref`；其值是 `content_hash(object)`，与带缩进 JSON 文件的字节哈希不同。归档前应通过 `register_json_artifact` 注册规范化对象。

`optimization_stage` 为 `algorithm_parallel` 或 `execution`。后者要求与架构绑定的并行计划、dispatch 计划、源码、算子、能力、容量和工作负载选择。`Context.workload` 包含 `source_hash`、`metadata`、`tiling_key`、`workload_group`。可以使用 `aprofctl dispatch validate-context --context FILE` 校验整体绑定，或 `dispatch select --plan FILE --workload METADATA` 单独选择元数据入口；选择器拒绝重叠条件并要求显式通用回退，不生成 C++ 启动代码。

计划分析父版本、dispatch 实现候选时，需同时声明 `plan_basis_source_hash` 与 `implementation_source_hash`，分别绑定并行计划与 dispatch 的源码身份。路由 `source_hash` 仍指向提出候选的父版本。启动和 dispatch 辅助文件应放在源码归档之外，避免哈希自引用。

`architecture_profile.core_counts` 记录 SDK 容量。新探测还记录成功 `aclrtGetDeviceInfo` 查询的 `visible_core_counts` 和编译器 `compiler` 身份；旧记录缺字段表示未知。编译器身份本身不证明 API 或目标编译选项受支持，950 专有能力仍需独立编译证据。已冻结的历史记录不改写。

规划校验只证明结构、容量和声明适用性，不证明算法正确性。独立版本 `2.0.0` 的 memory 和 lesson 契约仍是研究记录，不自动成为 policy episode。

## 旧诊断与 P/O 兼容格式

历史诊断 v0003 和当前 P/O v0002 共用 [knowledge-record](knowledge-record.schema.json) 的身份、版本、适用域、来源和学习参数；[knowledge-index](knowledge-index.schema.json) 描述带正文快照、来源 hash 和生成器身份的构建产物。当前诊断 v0004 使用后文的独立契约。边的唯一来源是独立 Markdown，不能手改生成的 graph/index。

[knowledge-route](knowledge-route.schema.json) 保留知识版本/hash、完整输入快照、匹配路径、证据和缺项；[knowledge-override](knowledge-override.schema.json) 只允许对确切版本及 hash 的已有参数覆盖。图 v0003 与树 v0001 使用新格式，不能加载旧 fixed-graph policy 或把路由当作旧 RouteDecision。

[knowledge-handoff](knowledge-handoff.schema.json) 使用 `aprof.handoff/v2`，按 C1/C2/C3 约束图快照、规划选择和实际实现；C3 必须带真实候选 ID 与 implementation_source_hash。角色交接仍由 [公共契约](../workflows/contracts/common.md) 管理，外层 Markdown 的 contract_version=1 不改变。

```bash
tools/aprofctl contract validate --root <完整包> --kind knowledge-handoff --input C3.json
tools/aprofctl knowledge validate --root <完整包> --owner parallel-planning
```

当前关联结果是独立的 `aprof.knowledge-outcome/v1` 记录，不写入旧 episode，不产生自动训练任务或因果收益标签。字段完整不代表事实已成立；来源、硬前提、完整正确性和统一计时分别核验。

## v0004机制诊断与v3交接

新增diagnosis-record/region/graph/retrieval/reasoning/case/proposal以及action-routing和knowledge-handoff-v3契约。旧schema保持原字节，新记录不塞入旧schema。当前语义见[机制与交接](../workflows/references/diagnosis-v4.md)；模板、关系、实例、案例和提案分别校验，不以格式检查宣称机制正确。

```bash
tools/aprofctl diagnosis verify --root <完整包>
tools/aprofctl diagnosis retrieve --root <完整包> --context evidence.json
tools/aprofctl knowledge validate-chain --root <完整包> --task-root <任务目录> --c1 C1.json --c2 C2.json --c3 C3.json
```

当前诊断不走 `knowledge build/validate --owner diagnosis`。历史 v0003 需通过显式快照路径回放；新交接链校验无需 timing，不能替代实施后的正确性与性能验收。

# 共享 context 采集工具执行说明

本入口属于外部实验采集层。原 AProf workflow、skills、graph 和 runtime gate 不承担数据集目标，也不接收本协议展平后的计时样本。

实验组织原则及统计口径分别见 [实验手册](optimization_experiment_playbook.md) 和 [配对协议](shared_context_paired_protocol.md)。本文件说明已实现工具的职责和恢复边界。

## 执行顺序

1. 冻结源码 tar、输入及 oracle、环境、知识 manifest。源码 tar 必须包含 `APROF_SOURCE_SNAPSHOT.json`，其文件路径、权限、大小及 hash 与 tar 内容一致。完整 tar 与原生 host/kernel hash 的覆盖范围不同，分别保存在 `source-native-bindings.json`，不能互换。
2. 使用 `shared_context_build.py` 构建 A/B 动态库及唯一 ACL 生命周期 runner。源码 CMake 采用严格白名单；未知编译参数或源结构必须先修复适配，不能悄悄忽略。
3. 用实际编译器取得 sizeof 证据，完成对应 build 的资源计划，然后做 baseline 方法资格校准。`run_shared_context_qualification.py` 每次只执行一个明确任务，启动前写 ledger；它不会自动重试或自动开始候选搜索。norm 方法对照独立归档，不登记新源码候选。
4. 优化 agent 只接收自身任务的规格、原 workflow、当前源码和已发生的测量反馈。每次只提出一次修改。协调器登记源码父本、观察依据及最多两个诊断 case，执行构建、20-case 正确性、搜索测量和必要 profile。
5. 每任务的 6 个计时组中保留至少 1 个最终评估组。候选冻结后再采集完整 20-case 性能；冻结后不向本批追加候选。最终选择多个候选时，剩余额度必须覆盖每个候选。
6. 通过 v2 发布器同时发布实验记忆和条件经验；完成后释放本轮进程、设备锁，保留待启动 checkpoint。

## 明确的工具边界

- `shared_context_campaign.py`：CPU 账本，记录启动即计费、观察闭环、预算、冻结和 checkpoint。方法校准不冒充源码尝试。
- `shared_context_build.py`：仅生成与构建，不运行设备。`--generate-only` 可审查 harness patch。
- `cannbench_shared_context.py prepare`：冻结比较 manifest、执行计划和 supervisor 副本；不执行硬件。
- `cannbench_shared_context.py collect`：执行原生配对计时，持有主机串行锁及兼容设备锁。已启动目录拒绝再次执行。
- `cannbench_shared_context.py verify`：只读重放原始 journal、校验输入/源码/二进制/外部资格及统计结果；不调用 gate、不登记 artifact、不补跑实验。
- `run_shared_context_qualification.py`：串联单任务 prepare、账本开始、collect 和结果登记，记录 `qualification-result.json`。失败后不自动恢复。
- `run_shared_context_diagnostic.py`：显式运行一次正确性或 profile，冻结源码、输入、producer 与资源计划；输出该组的 `group-result.json`。正确性固定全部 20 个 case；搜索期候选 profile 限于已登记 sentinel/probe。
- `run_shared_context_comparison.py`：一次候选 search/final 计时组，绑定独立比较及外部资格；开始即计费，输出 `comparisons/PURPOSE/group-result.json` 和各比较报告。它不会自动登记观察、生成 lesson 或选择下一候选。
- `shared_context_archive.py`：只读解释已发生的实验，再发布按 train/validation 分离的 v2 记忆、经验和方法 checkpoint。`verify` 只读验证现有发布。

## 资源预检

`shared_context_collect_sizeof.py` 只运行已经构建好的 host-only probe；不构建或执行设备算子。probe 必须使用对应 CANN 编译器、实际架构参数和头文件，保存 `sizeof`、`alignof`、`size_t` 位宽，以及编译命令、CMake 参数、编译器版本和预先核实的编译器 hash。工具从 `compile_commands.json` 或严格解析的 CMake Makefile 取得编译命令；CMake 的 C++ 标准声明不证明 ASC 默认方言。不能填入推测的结构大小。

以下变量和目录由协调器按实际 probe 构建填写；`SIZEOF_COMPILER_SHA256` 是不带 `sha256:` 前缀的 64 位十六进制 hash，`SIZEOF_CMAKE_PARAMETERS_JSON` 是实际 configure 参数的 JSON 数组。示例命令只有在调用时才运行 probe 或写输出：

```bash
python3 scaffolding/collection/scripts/shared_context_collect_sizeof.py \
  --probe-dir "$SIZEOF_PROBE_DIR" --build-dir "$SIZEOF_BUILD_DIR" \
  --compiler "$SIZEOF_COMPILER" --compiler-sha256 "$SIZEOF_COMPILER_SHA256" \
  --cmake-parameters-json "$SIZEOF_CMAKE_PARAMETERS_JSON" \
  --output "$RUN/bootstrap/sizeof-metadata.json"

python3 scaffolding/collection/scripts/shared_context_memory_plan.py \
  --audit "$RUN/bootstrap/resource-preflight-audit.json" \
  --sizeof "$RUN/bootstrap/sizeof-metadata.json" \
  --request "$RUN/tasks/exp/case-memory-request.json"
```

资源 audit 是经过审查的 adapter 分配公式白名单。单 case request 指明 A/B adapter 绝对路径、原始 case attributes、cores 和 `buffer_configs`。把 request 与返回的 plan 收入 `tasks/OP/LABEL-memory-plan.json` 的 `cases` 数组，每项为 `{case_id, request, plan}`；顶层保存 `label`、`prospective`，并在 `provenance.audit`、`provenance.sizeof` 中绑定两个文件的 `sha256:` hash。

wrapper 会重算声明 case 的计划，核对输入属性、确切 build/role、source、adapter、header、kernel 和 sizeof 输出。后续资格与比较必须使用预先形成的 `prospective: true` 计划。资格与 A/A 控制计划必须包括 `normal`、`swapped` 两种配置；A/B 和 A/A build 分别核验，不能用候选 A/B 计划代替 A/A 控制计划。输出只覆盖显式 `aclrtMalloc` 请求及保留缓冲区峰值，不是设备剩余显存或 runtime/allocator 额外开销的保证。

## 单任务诊断与搜索

以下示例从仓库根目录调用。`RUN` 指已经准备好且账本处于 active 状态的新 run；源码候选及成功 build 已登记。正确性 wrapper 还要求已准备 `tools/diagnostic/profile-build.json`。现有输出目录都是证据，不能复用：

```bash
RUN=.aprof/runs/your-new-run

python3 scaffolding/collection/scripts/run_shared_context_qualification.py \
  --run "$RUN" --operator exp

python3 scaffolding/collection/scripts/run_shared_context_diagnostic.py \
  --run "$RUN" --operator exp --candidate exp001 \
  --stage correctness --group default

python3 scaffolding/collection/scripts/run_shared_context_diagnostic.py \
  --run "$RUN" --operator exp --candidate exp001 \
  --stage profile --group probes --cases 1,8

python3 scaffolding/collection/scripts/run_shared_context_comparison.py run \
  --run "$RUN" --operator exp --candidate exp001 --purpose search
```

诊断使用 `--candidate baseline` 时选原 baseline 的 A 角色；普通候选使用其 A/B build 的 B 角色。诊断和资格入口固定 device 0、CPU 8。比较的 `prepare`、`run` 支持 `--device`、`--cpu`、`--timeout`，但必须与已通过资格的硬件绑定一致；`collect` 只接收 `--group`，沿用冻结参数。采集前要求候选最新 build 和正确性阶段均成功。

搜索 case 严格等于 `[1,8,14,20]` 加候选登记时最多两个 probe，比较 CLI 不提供 case 覆盖参数。默认比较使用候选 `ab-build/build_manifest.json`、任务 `aa-build/build_manifest.json` 和 `qualification/report.json`，适用于直接父本就是原 baseline 的候选。

父本不同于原 baseline 时，必须通过 `--comparison-inputs FILE` 预先提供两组真实比较，顺序为 `parent`、`original`；每组分别具备 parent/candidate 或 original/candidate 的 A/B build、同一控制源码的 A/A build 及其通过的资格报告。输入文件只含 `comparisons` 数组，每项必填 `control`、`build`、`control_build`、`qualification_report`，路径相对该文件解析。可选 `memory_label`、`control_memory_label` 指向任务目录下对应的 `LABEL-memory-plan.json`；默认分别为候选 ID 和控制候选 ID（原 baseline 为 `baseline`）。不同 build 需要不同计划时显式指定 label。父本与原 baseline 相同则合并为一项 `original`，不能用倍率相乘代替独立比较。

每组 AB formal samples 为 `case 数 × 比较数 × 6 × 30 × 2`；A/A 样本单独进入 `actual_costs`，不混入 ledger 的候选 formal samples。完整的 `quality_failed` 仍保留所有结果，继续完成已声明的其他独立比较，不自动重测。执行错误保留原始部分结果和后续未执行比较。

## 不可变账本与最终冻结

`config.json`、事件链及 checkpoint seal 保持不可变；状态由事件重放得到。除初始化 `prepare --config` 外，所有写入命令通过 `--payload` 接收 JSON，并要求明确的 `event_id`。相同 ID 和相同参数只返回已记录事件，不能作为重新执行硬件的许可。协调器用 `observation` 登记真实反馈，覆盖各源码所有新完成阶段，任务内全部候选反馈闭合后才能冻结；wrapper 的采集完成不等于反馈已闭合。

最终比较分三步。先为所有拟选候选执行 `prepare --purpose final`，再把各自生成的 `ledger-plan.json` 原样写入一次 freeze 的 `final_plans`，最后显式 collect。prepare 不运行硬件；freeze 之后不能重新 prepare、修改计划或继续搜索。以下示例选一个已经闭合反馈的候选：

```bash
python3 scaffolding/collection/scripts/run_shared_context_comparison.py prepare \
  --run "$RUN" --operator exp --candidate exp001 --purpose final

python3 - "$RUN" exp exp001 <<'PY'
import json
import sys
from pathlib import Path

run, operator, candidate = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
group = run / "tasks" / operator / "candidates" / candidate / "comparisons" / "final"
payload = {
    "event_id": f"{operator}-{candidate}-freeze",
    "workload": operator,
    "candidate_ids": [candidate],
    "final_plans": {candidate: json.loads((group / "ledger-plan.json").read_text())},
    "reason": "根据已闭合的搜索反馈冻结候选及完整 20-case 最终计划",
}
with (group / "freeze-payload.json").open("x") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
PY

python3 scaffolding/collection/scripts/shared_context_campaign.py freeze --ledger "$RUN/ledger" \
  --payload "$RUN/tasks/exp/candidates/exp001/comparisons/final/freeze-payload.json"

python3 scaffolding/collection/scripts/run_shared_context_comparison.py collect \
  --group "$RUN/tasks/exp/candidates/exp001/comparisons/final"
```

## 只读验证与归档

原生验证会读源文件、二进制、输入及 journal 并重算报告；它不启动设备。应在测量窗口结束后执行，避免额外文件读取干扰正在运行的实验。归档要求所有 ledger 阶段已完成；先准备再发布也可以分开执行：

```bash
python3 scaffolding/collection/scripts/shared_context_campaign.py verify --ledger "$RUN/ledger"
python3 scaffolding/collection/scripts/shared_context_campaign.py status --ledger "$RUN/ledger" --split train
python3 scaffolding/collection/scripts/cannbench_shared_context.py verify \
  --output "$RUN/tasks/exp/qualification"
python3 scaffolding/collection/scripts/cannbench_shared_context.py verify \
  --output "$RUN/tasks/exp/candidates/exp001/comparisons/search/original"

python3 scaffolding/collection/scripts/shared_context_archive.py archive --run "$RUN" --prepare-only
python3 scaffolding/collection/scripts/shared_context_archive.py archive --run "$RUN"
python3 scaffolding/collection/scripts/shared_context_archive.py verify --output "$RUN/archive"
```

归档默认发布到 `RUN/archive/train/v2` 和 `RUN/archive/validation/v2`；可用 `archive --output DIR` 指定根目录，验证时传同一个根目录。`--prepare-only` 会写准备后的 recording manifest，但不发布 v2；`verify` 不修改现有归档。norm 的资格与 `method/foreach_norm/positive-comparison` 分别归入方法 checkpoint；正例报告按常规比较重算，不登记新 norm 源码尝试。采集及归档均不产生正式 gate 准入或 graph episode。

任务可在 `tasks/OP/closure.json` 留下明确收尾记录。最小可接受形状为 `{"status":"状态字符串","evidence":[{"path":"证据路径","sha256":"sha256:…"}]}`，相对证据路径以 RUN 为根。`reason`、`next_action`、`paired_performance_evaluated`、`formal_admission` 属于说明字段，原样保存在 `recorded_closure`；它们不能覆盖 ledger 的次数、实际方法报告或归档的准入状态。

以下例子仅适用于方法资格失败、尚未做候选配对性能评估而结束的任务。它读取真实 `qualification-result.json`，计算该小文件的 hash，调用时才以独占方式创建 closure；若已有其他实验，先按其真实证据编写相应收尾记录。

```bash
python3 - "$RUN" exp <<'PY'
import hashlib
import json
import sys
from pathlib import Path

task = Path(sys.argv[1]).resolve() / "tasks" / sys.argv[2]
source = task / "qualification-result.json"
data = source.read_bytes()
result = json.loads(data)
if result.get("status") not in {"execution_failed", "quality_failed"}:
    raise SystemExit("此例只用于资格失败后终止的任务")
closure = {
    "status": result["status"],
    "reason": result.get("error") or result.get("failures") or "方法资格未通过",
    "next_action": result["next_action"],
    "paired_performance_evaluated": False,
    "formal_admission": "not_evaluated",
    "evidence": [{"path": str(source), "sha256": "sha256:" + hashlib.sha256(data).hexdigest()}],
}
with (task / "closure.json").open("x") as stream:
    json.dump(closure, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
PY
```

## 证据与解释

资格校准采用 12 次原生启动，即 6 个 block 内各做 AB/BA 加载顺序；每次分别测正常/交换缓冲区配置。常规比较使用前置 A/A、反向 A/A、A/B、后置 A/A，每阶段 6 次启动。每进程、每 case、每配置均为 30 对、10 次预热、每样本 100 次完整算子调用。

routine 比较必须绑定完成且通过的资格报告及其 manifest、sessions、执行计划 hash；逐一核对设备、环境、harness、baseline、case、输入、oracle 和 launch 契约。baseline 资格不能自动证明候选特有的资源配置没有偏差，候选资源映射和常规控制仍须审阅。

`journal.jsonl` 保留真正的 context/stream、角色入口、缓冲区地址、配对顺序、原始 ms 与完整 launch 数。每个 case/config 的两个角色导出最终正式样本的最后一次调用输出，外部原始 oracle 校验后才允许进入下一个 case。该覆盖不等于逐个中间调用均被验证。

统计以独立进程为复现单位。绝对漂移、配对倍率、顺序/加载/缓冲区偏差、测量质量与正式准入分开表达。失败的 A/A 不是优化负例；未通过正式 3% 准入也不抹掉已可信的小幅变化或条件经验。

## 中断与恢复

已有失败执行和半成品 journal 永久保留。恢复前核对进程已退出、锁已释放、账本计费和已完成样本。仅客观的零正式样本预启动故障可依协议恢复一次；稳定性失败不能换目录一直重测到通过。源码修复必须登记新候选。

诊断或资格预检在 ledger stage 开始前失败时，wrapper 保留失败记录并注明 `ledger_stage_started: false`；不能补写成已运行阶段或正确性失败。比较准备或预检被拒绝时，保留已有文件及错误，不能冒充已启动计时组。已启动阶段按实际计费，失败不退款。wrapper 拒绝隐式重跑；满足协议的一次预启动恢复仍需协调器显式记录原失败与恢复关系。

暂停前通过 `checkpoint --ledger … --payload …` 记录 `checkpoint_id`、原因、下一动作、证据位置、资格状态和 `resources_released: true`，前提是没有运行阶段且资源确已释放。恢复使用 `resume --ledger … --payload …` 引用最新 checkpoint；首次启动的 `checkpoint_id` 为 `null`。`verify` 可加 `--expected-head` 和 `--expected-config-hash` 核对外部固定值。未完成 seal 的 checkpoint 只可用原事件 ID 和原参数补齐，不重写历史。

只读验证不能替代执行恢复。统计或导出代码修复可基于原始不可变数据重新解释，并显式增加分析版本；不能伪装成新的实机观察。共享 runner 正确性问题暂停所有硬件采集；任务特有的测量阻断则独立记录，不影响其他任务完成自己的资格检查。

尚无源码候选的任务，在资格报告和账本均为 `quality_failed` 后，可显式保存阻断记录：

```bash
python3 scaffolding/collection/scripts/close_shared_context_method_block.py --run "$RUN" --operator masked_scale
```

此命令重算报告并核对账本，只新增 `closure.json`；不登记候选、不退款、不重试，也不把测量失败写成优化失败。已经存在候选的任务必须先保存该源码实际发生的反馈和各阶段结果，再由协调器记录任务结论，不能用此快捷关闭替代候选闭环。

## 显式候选分析与两种视图

协调器可在 `tasks/OP/candidates/ID/analysis.json` 提供少量有证据支持的当前分析。归档仅接受 `shared_context_candidate_analysis_v1`，要求 `candidate_id`、ledger 中的完整源码 `source_hash`、`retrospective: true`，以及 `evidence`、`diagnosis`、`intervention`。未知顶层字段会被拒绝。该文件增加已有源码的诊断和条件经验，不登记新源码、不改写历史 proposal，也不把当前分析冒充优化器当时的预测。

`evidence` 是别名到 `{path, sha256, selector?}` 的映射；相对路径以 RUN 为根，hash 必须匹配，selector 必须能定位原文件中的内容。正文事实只引用别名，避免复制完整 hash 清单。每个 fact 的必需字段为 `statement`、`basis: "retrospective_current_evidence"` 和非空 `evidence: [别名]`，可带 `case_ids`、`metrics`、`parameters`、`conditions`、`limitations`。后三种数值/条件容器必须为对象；case ID 限于 1–20。

`diagnosis` 包含 `symptoms`、`hypotheses` 两个 fact 数组和 `missing_evidence` 字符串数组。`intervention` 是一个 fact，必须引用该候选精确 `optimization.patch` 的完整文件证据。原历史 proposal 的假设单独保留，当前 fact 均标为 retrospective。

可选 `lessons` 中，每条需要本地 `id`、`kind: "operator_optimization"`、`title`、非空 `claims` 和 `evidence`。claim 是额外带 `status: "supported" | "refuted" | "inconclusive"` 的 fact。lesson 默认继承当前 analysis 的 diagnosis/intervention，可显式覆盖；可添加 `effective_conditions`、`ineffective_conditions`、`counterexamples`、`limitations`、`next_questions`。条件和反例使用 fact 数组；后两项使用字符串数组。lesson 必须有 patch 以外的已记录证据，归档自动把它绑定到当前候选对应的原始 source attempt。局部 counter 变化、反例和未测的全套收益可以分别表达，不从 profile kernel 时长推导 qualified speedup。

可选 `read_audits` 示例：

```json
[
  {
    "record": "initial_review",
    "temporal_scope": "current_pre_execution_review",
    "used_for_current_judgment": ["diagnosis_skill", "optimization_skill"]
  },
  {
    "record": "feedback",
    "temporal_scope": "post_execution_analysis",
    "used_for_current_judgment": []
  }
]
```

`record` 和所选知识项都是 evidence 别名。原审计必须记录同算子、同候选、实际时间戳和 `actual_reads`；初始审计的 kind 必须是 `agent_initial_static_review`，时间不能晚于该候选本轮硬件开始。所选最多五个知识项，其 path/hash 必须出现在对应审计的实际 read 列表中。完整读取名单保存在外置原审计，正文只显示审计时序与少数实际用于本次判断的知识项。当前初始 review、后验反馈和旧候选 proposal 的时间语义分别保留。

以下入口仅检查 analysis、ledger 声明和每个不超过 1 MiB 的命名证据；不读取源码 tar/DSO、不建目录、不运行设备或归档。超过限额会拒绝，可在明确需要时调整 `--max-evidence-bytes`。

```bash
python3 scaffolding/collection/scripts/shared_context_archive.py validate-analysis \
  --run "$RUN" --operator exp --candidate exp001
```

方法资格报告在归档时独立重算。方法 lesson 只内嵌 case 属性、A/A 倍率范围与代表 CI、最大 CV、失败分类、关键异常条件/因子及 block 倍率极值；完整 11 项检查和逐进程序列留在外置报告。低 CV 但跨 block 比较不可靠的情况会显式保留。`measurement_method_lessons` 与 `operator_optimization_lessons` 分开计数，方法校准与 norm 正例均不增加优化 source attempt。

任务的 `aa-failure-analysis.json`、`agent-initial-review.json`、`agent-feedback-decision.json`、`execution-manifest.json` 和名称同时含 runtime/manifest 的补充 JSON 自动进入外置证据，不依赖重写 closure。方法结论仍由主报告重算得到。baseline 和候选 profile 的原始 CSV、native JSON、执行日志均冻结；build/diagnostic 清单绑定的 DSO、runner 和 source tar 进入 CAS 校验。输出 tensor 不复制，保留 oracle 结果及输出 hash。历史 wrapper 优先按原 hash 寻找快照或旧导出 CAS；retrospective 保存不会被写成预执行冻结。

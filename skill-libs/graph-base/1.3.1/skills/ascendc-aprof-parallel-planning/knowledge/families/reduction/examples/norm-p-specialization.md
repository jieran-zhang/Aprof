---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.example.norm-p-specialization
kind: example
version: 1.1.0
status: active
title: norm-p-specialization 历史案例：既定归约内的 p 分支特化
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/norm-p-specialization.md
  original_path: wiki/norm-p-specialization.md
  revision: aprof-1.1.0-pre-governance:sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
  lines:
  - 1
  - 26
  sha256: sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
  excerpt_sha256: sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
- path: workflows/migration/archive/wiki/index.json
  original_path: wiki/index.json
  revision: aprof-1.1.0-pre-governance:sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  lines:
  - 1
  - 388
  sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  excerpt_sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
- path: workflows/migration/archive/wiki/evolution.jsonl
  original_path: wiki/evolution.jsonl
  revision: aprof-1.1.0-pre-governance:sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  lines:
  - 1
  - 15
  sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  excerpt_sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
learning: {}
tags: []
seed_reason: 从已绑定的包内历史档案、索引和演化记录补足中文案例正文；保留原协议、失败与适用边界，不迁移历史性能资格。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# norm-p-specialization 历史案例：既定归约内的 p 分支特化

## 背景与方法

来源是在 910C/A3 上对 `foreach_norm` 的历史观察：仅当运行时 p 确认为 1、2、4，且数学定义、dtype、精度与特殊值合同成立时，比较用 identity、乘法、平方和平方根等替代通用 Power 链。数学上 p=1 为绝对值求和，p=2 为平方求和后开平方，p=4 可用绝对值的四次幂求和后还原；这些等式不自动允许更换中间舍入或归约顺序。原档案未逐项给出替换后的完整代码，不能把数学等式当作已验证实现。

该改动发生在已经确定的分区和归约结构内，属于 C3 执行优化；本规划例用于提示候选与边界，不授权改变 C2 的任务所有权、partial 数或合并规则。其他有限 p、±Infinity、零与 NaN 路径保持独立分支和验证；“接近”1/2/4 不能视为属性精确相等。固定的转换、epsilon、输入变换与最后还原均按当前 oracle 保留。

## 历史收益、反例与范围

历史 20-case 候选中，12 个目标分支观察倍率约 2.96–3.86×，suite 约 2.05×；正式 verdict 仍为 `benchmark_specialized_gain`。七个非目标有限 p case 全部有约 0.64–1.34% 小回退，+Infinity case 约 1×且没有执行特化。另一批 p=1 identity 消除实验也记录了目标 case 获益与非目标 case 小回退。因此 suite 收益不能写成全部分支获益，保留一般 fallback 也不能替代对非目标成本的检查。

资料仅给出 910C/A3 历史范围和原来源绑定的 CANN/编译器身份，没有在本页列出完整 shape、dtype 或具体工具链版本，不能补造这些参数；该 p 特化也没有可移植性验收。norm-partials 的 2026-10-14 独立复验不构成本 p 特化已复验的证据。

## 验收与当前证据

对新任务先独立核验所有 p 分支、dtype、尾部和特殊值，再按相同协议比较目标与非目标分支，保留语义合法的一般实现。只有全声明范围的正确性与收益资格均闭合，才能提升为接受规则；不能用目标 case 或 suite 结果代替该验收。

演化记录因没有独立生产安全硬件验收而 deferred，原 wiki 状态为 draft；未获得 `production_safe_gain`。1.3.0 仅审读来源，未按 `single_role_l2_clean_task_v1` 重测，也未新增 NPU 正确性或性能证明。scope=all 仅用于检索，历史倍率和任何 validated 字段均不迁移为当前资格。

来源：[原始历史档案](../../../../../../workflows/migration/archive/wiki/norm-p-specialization.md)、同目录 index.json，以及 evolution.jsonl 的 `1.0.0-norm-p-specialization`。本正文已保留其执行阶段归属、目标/非目标反例和未验收范围。

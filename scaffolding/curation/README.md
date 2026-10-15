# graph-base/1.0.0 teacher snapshot

0.5.1 的 Task v4 测量修复已封存并成为默认版本。1.0.0 候选已同步其
runtime 0.2.2、本地优化证据和任务后归档分工；Teacher 绑定真实稳定 manifest。
66 条来源、当前 split、10 篇 Wiki 与 v0002 校验通过，尚无规则晋升。
规则独立复验及 45 次等预算比较仍待完成；原 0.5.0 比较组保持不变。

第二轮已结束：工具整改与资格通过，sigmoid、exp 的 v2 计时控制均未
通过，稳定版仍未封存。见[第二轮实测报告](graph-base-1.0.0-round2-results.md)。

The [first-round hardware report](graph-base-1.0.0-hardware-validation.md) records
four independent 910C/A3 attempts. None qualified for skill promotion; 1.0.0
remains unsealed; the current stable default is the qualified 0.5.1 measurement release.

The [second-round protocol](graph-base-1.0.0-round2.md) retries only sigmoid and
exp after finite baseline-only controls. Its [preregistration](graph-base-1.0.0-round2-plan.json)
binds all eight attempt slots; the [screen API correction](graph-base-1.0.0-round2-amendment-screen.json)
preserves their sources, samples and thresholds. Original failures remain part
of the audit. Tool qualification and the full validation comparison are separate
requirements described in the [evaluation guide](graph-base-1.0.0-evaluation.md).

`graph-base-1.0.0.json` freezes the source index and CANNBench split bytes, then
records one decision for each of 26 Level1 lessons and 40 closed Level2 source
attempts. The current split is recalculated by operator; old `original_split`
labels are not trusted. This pass selected 29 train records for nine conditional
Wiki pages (now ten after separating the exp-only tile proposal), left 16 train attempts in raw for later review, and excluded 21
validation/test records. Source hashes refer to the exact JSONL line or feedback
file; the raw archive remains outside Git.

Run `python3 scaffolding/tools/verify_teacher_wiki.py` from the repository root.
It rejects changed inputs, leaked split records, missing pages, mismatched
evidence hashes and graph links. A skill promotion requires an independent,
source-bound `production_safe_gain` receipt replayed through the frozen runtime
and CAS, full correctness and extra boundary reports, and 910C/CANN provenance.
Both formal graph episodes and the official exploration gate are supported;
exploration evidence does not acquire graph-policy eligibility. Each accepted
proposal changes one skill, with hashed before/after snapshots forming a local
revision chain that ends at the published skill bytes.

The Wiki pages explain historical conditions and counterexamples. Historical
`benchmark_specialized_gain` and Level2 `formal_admission=not_evaluated` do not
authorize a production rule. A deferred proposal stays in `wiki/evolution.jsonl`
until a separate independent validation run supplies a replayable receipt.

`release_skill_lib.py seal` enforces this boundary for graph-base/1.0.0. It
requires at least one verified skill promotion and `--validation-run <directory>`
pointing to the frozen 45-run comparison. Publication verification replays its
receipts and requires the primary skill-plus-Wiki arm's paired speedup ratio to
have a 95% bootstrap lower bound above 1, without a paired correctness decline.
The skill-only arm is a reported ablation and cannot rescue a failing primary
comparison. Missing or incomplete qualification cannot create a stable manifest.

Independent failed controls and boundary checks also remain in the evolution
log. Their `evidence_refs` are workspace-relative files with checked SHA-256
hashes; they do not authorize a skill promotion or a policy-training reward.

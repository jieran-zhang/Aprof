# R2 workload 内容绑定短审阅

结论：缺口成立。当前 v2 反馈仅将计时 case ID 与前轮 case 清单/语义域关联，没有把各 case 的实际 workload 内容关联。CPU FakeRunner 的有效证据链可以测 `shape:[2]`，同时归入决策中同 ID 的 `shape:[64]`。`attempt_identity.workload_hash` 只绑定一份声明文件；它不能证明另一个计时文件所含 shape 与声明相同。

## 可回放反例

本目录 `probe_workload_binding.py` 载入发现问题时公共 `action_decision_v2.py` 的冻结快照 `workload-binding-runtime.py`，其余依赖使用已冻结、可回放的 v5 fixture 包；仅将测试的版本选择替换为 v2。未修改任何公共文件、旧 schema 或旧计时逻辑。

修复后的可回放检查见包内 `runtime/tests/test_action_decision_v2.py` 的 `test_valid_v2_feedback_replays_absolute_request_and_exact_case_scope` 参数化用例。临时反例工作区用于发现问题，不是包的运行依赖。

- 原决策完整 workload：shape=[64], dtype=float32, layout=ND, cases=[1,2]。
- 实际候选/基线统一计时：case=1, shape=[2], oracle_limits={atol:0,rtol:0,equal_nan:false}。
- A/B、正确性、source、请求、结果、任务内回执 hash 与父本绑定全部走现有真实验证器。
- 选择反馈标 measurement=valid，measured_case_ids=[1]，measured_domain_ids=[all]。
- 另将前轮 performance prediction 标 supported，引用拥有正确 attempt_identity 且引用真实合成 result 的回执；此结果也用于检查仅添加 scoped_evidence 能否补上缺口。
- 结果见 `workload-binding-repro.log`；坏输入保存在 `workload-binding-bad-decision.json`，其 task_root 是 `fixed-valid-task/`。

以上均为 CPU 合成契约测试，不能称为实测加速。原报告中的局部测量正例验证了 ID/域分层，没有验证 workload 内容；本反例揭示更深的一层未绑定关系。

## 已有字段确实能够提供什么

| 所在层 | 已有身份/内容 | 当前保证 |
| --- | --- | --- |
| timing result | request.path/sha256；每 case 的 baseline/candidate capture ref | 能回到原始请求与捕获 |
| timing request | baseline_captures/candidate_captures、correctness引用 | 每 role/case均回放、hash核验 |
| capture | identity.workload_ref；artifacts.workload.path/sha256 | workload_ref是快照文件的**字节hash**，不是case ID，也不是规范JSON内容hash |
| capture workload | 任意JSON对象；原收集器直接保存 config.cases[i].workload | 包含实际声明的shape、oracle_limits等字段，可直接读取做内容等价核对 |
| correctness↔timing、A↔B | 同 case 的 workload_ref 相等 | 保证各测量/正确性环节workload相同；没有与decision建立边 |
| decision v2 | path_overview.workload_ref，case_ids/domains | 指向整个任意workload JSON；当前只提取case身份，没有规范每case payload到timing workload的变换 |

定位：`unified_timing.py:_base` 约202–208行校验workload快照hash；`_evaluate_request`约386–405行绑定正确性/计时与A/B；`single_role_task.py`约294行原样保存 `case['workload']`。`action_decision_v2.py`约210–215行只处理case集合及域交集。

因此不能把整个decision workload文件hash与每case capture workload_ref直接比较，也不能把按case ID生成的字符串hash充当workload身份。

## 建议的最小严格修法：只增强 v2 measured feedback

不改 timing result/request/capture 的旧schema，也不改变v1语义。读取已经由 verify_timing 完整验证的 request.candidate_captures，沿每个capture.artifacts.workload取得原始JSON；继续检查ref/hash，不能只信任新声明hash。A/B内部已绑定相同workload，检查候选一侧足以建立该边。

前轮冻结 workload 若采用以下**明确、无推断的表示**，现有字段已经足够，无需增加decision字段：

```json
{
  "cases": [
    {"case_id": 1, "workload": {"shape": [2], "oracle_limits": {"atol": 0, "rtol": 0, "equal_nan": false}}},
    {"case_id": 2, "workload": {"shape": [64], "oracle_limits": {"atol": 0, "rtol": 0, "equal_nan": false}}}
  ]
}
```

此清单结构已经被 workload_case_ids 支持。对每个实际测到的case，唯一定位前轮case记录，比较其完整 `workload` 对象与capture workload的规范JSON内容全等。比较内容时可忽略序列化空白/对象键顺序，不能忽略dtype/layout/attributes/oracle_limits或只取键交集。所有文件引用仍使用原字节hash，不能把两种hash定义混用。未测case不需要捕获，语义域部分测量保持有效。

如要接受每case外部workload_ref，需要显式定义此字段为任务内文件引用并验证完整payload；这是新v2表示约定，应先确认。不能在已有原始矩阵中遇到任意 `path`/`hash` 就自行当作此约定。

## 异构旧清单不能靠现有字段普遍严格映射

实际自主回归输入常为 `{cases:[{case_id,shape,dtype,dim,...}]}`，甚至只有case_ids；timing workload还含oracle_limits。不存在通用、无歧义的规则可从任意原始case对象恢复收集器workload。只比较共同字段会接受遗漏参数，删除oracle_limits会丢精度契约，全部强制相等则会误拒合法的格式差异。

所以最小修法需要明确边界：对没有可验证每case payload的v2记录，不将当前计时结果认定为该decision范围内的有效性能反馈。应报告“计时链自身有效，决策workload映射缺失/不匹配”，保留结果和静态事实，禁止supported/weakened性能更新。不要声称硬件测量本身无效，不改写R1，也不要求机械重跑硬件。现有measurement=invalid若用于此情况，必须在result_limits中明确是**归属该决策无效**；若此枚举旧语义只指计时链无效，则需要另加v2关联状态，不能悄然改义。

若业务要求旧异构矩阵直接复用测量，需先设计新的v2绑定对象：前轮原始workload引用、唯一case定位、完整期望capture payload及可复算转换规则/解析器身份。仅新增 `{case_id, workload_hash}` 自我声明仍不能证明hash对应前轮shape。该扩展已先报主agent，本文不实施新接口。

## 相容性与验证范围

- v1、旧D4/D5、timing旧schema/原始结果含义全部不动。
- v2 not_measured纯源码比较继续接受原始矩阵，无前置硬件门禁。
- v2 valid测量才要求同case内容绑定；同ID异shape/dtype/属性/精度需拒绝性能归属。
- 语义域可含多个case，而只测其中一个；绑定只检查真实测到的case，不要求重测未测项。
- 完整等价且仅JSON空白/键顺序不同应接受；payload不同则拒绝。重新排case顺序不改变对应关系；重复caseID拒绝。
- 上述调查阶段未修改公共代码；随后完成的修复及验证记录如下。

## 已实施修复与定向验证

主agent已授权并采用上述严格最小格式。仅修改公共 action_decision_v2.py、test_action_decision_v2.py、workflows/references/action-decision-v2.md。保留 prediction_updates scoped_evidence 校验，未修改v1/旧schema/计时文件或快照。valid反馈读取前轮完整cases映射并沿原捕获引用核对字节hash，再规范JSON全等比较；缺映射与同ID异payload拒绝归属。

原有valid反馈测试扩为4种参数，测试函数新增0、用例净增3：合法完整payload且只测语义域内case1、同ID异shape、缺映射、不同oracle_limits。合法正例在R1之前冻结case1/case2完整workload，使用performance supported及原result引用；验证完整payload匹配而非仅计时成功。

定向执行：
```bash
PYTHONPATH=runtime/src:runtime/tests python -m pytest -q runtime/tests/test_action_decision_v2.py -k 'valid_v2_feedback or r2_unmeasured or invalid_measurement or prediction_update_cannot_borrow'
```
结果：**7 passed, 29 deselected in 79.88s**。日志见 `../checks/workload-binding-tests.log`；另完成py_compile与这3个文件的git diff --check。没有运行硬件，也没有重复全包测试。

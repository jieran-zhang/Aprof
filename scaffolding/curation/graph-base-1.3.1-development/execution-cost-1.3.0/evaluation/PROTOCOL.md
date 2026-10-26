# 无工具自主行为 A/B 协议（冻结）

六组场景，各组含两个事实变化小例；每组 A/B 各两次独立请求，共24个。模型 gpt-6.1-sol，reasoning=high，max_output_tokens=12000，tools=[]，tool_choice=none，store=false；无 previous_response_id，不附旧会话。真实请求通过之前已用的 run_no_tools.py 客户端；读取现有合法本地认证但不存储请求headers或token。保存 request、SSE events、终态response、正文answer及RUN元数据。不模拟任何输出。

先独立阅读原始 case-08/case-12 与 R15 研究候选源码，冻结 inputs、sources 和 FACTS 的SHA256；其后才允许读取B正文。题目不附FACTS、标准答案、旧报告或预选Problem/Action。源码摘录保留原文件/行定位，题目自行提供必要外部函数契约和当前入口。仅第六题提供明确标注的合成原始源码谱系、正确性记录与计时窗口，用于区分结构事实和有效性能证据；这不是旧诊断报告，也不是硬件测量。

A/B同一读取策略：五个角色skill、完整方案/历史/选择规则、代码理解参考、全部Problem/Action正文、全部O分支正文、P的elementwise/indexing/layout全部正文及router。跳过案例examples、庞大的来源/审阅元数据，仅保留实施必要的Action条件、invariant及instantiation元数据。新版本新增正文按相同目录规则包括，A缺失记版本差异，不人工把新知识塞回A。本轮不评价检索速度。PROTOCOL-{A,B}.json列所有文档hash、输入长度、逐次prompt hash，request.json是实际送出正文。

人工逐题语义复核，每题四项冻结标准，每项0/1/2：0=缺失、错误或无源码依据；1=部分正确但遗漏改变选择的关键事实/代价；2=准确具体并进入实际方案/竞争比较。不能按关键词、Action名字或文字正则自动通过。不预设唯一Action，不要求双子例不同选择，也不预设B优于A。独立记录具体事实错误、未授权收益/硬件断言、方案覆盖、共同计划和方法能力缺口。整体总分仅汇总，不替代逐题解释。

先检查infra：HTTP成功、response_status=completed、model和预算一致、请求和响应均tools=[]/tool_choice=none、output类型仅message/reasoning、零tool_call。超时/拒绝/截断单列为基础设施失败，不视为技术结论，不补造结果。使用response.usage记录实际输入/输出/推理token和cache命中；文本字符/字节成本另列，两者不混算。

不调用NPU、编译器、profile、硬件测试或数据生成。本评测衡量纸面自主行为与源码推理，不能证明真实性能收益、未来工具路由的检索行为或所有工作负载上的泛化。

## 对称基础设施重试修订

详见RETRY-AMENDMENT.json：24个初始请求全部结束后，仅对无valid completed结果的逻辑项固定至多追加两次独立同请求重试；保留原模型/输入/effort/12k预算和全部失败证据。按顺序取首个completed，不依据分数或内容择优。三次均失败则上报，禁止给截断响应评分或单边改预算。冻结修订时尚无已保存或冻结的正式评分；已阅读s1-A两份完成正文作事实核对，未阅读s2截断正文，也未据此修改提示。

## 当前正式协议 v2（取代上文12k执行预算）

依据协调者明确要求，V2-AMENDMENT.json将两版本全部24项统一改为max_output_tokens=20000，并全部重新发送。题目、源码、冻结事实标准和资料选择策略均不变；A新旧prompt和文档hash逐项相等。v1所有已完成、截断与取消项仅为preflight，其答案/临时评分一律不进入正式A/B。保留失败暴露和全部已知成本，禁止悄悄沿用v1完成结果。v2仍是同gpt-6.1-sol/high、tools=[]/tool_choice=none；24初始终态齐全后适用对称固定重试规则。

B冻结包为/dev/shm/aprof-execution-cost-130-20261022/after-evaluation。B-BUDGET-CHECK.json记录统一语料下的本地tokenization：最大246813+已观测provider开销48+20000=266861，小于272k；最终以各真实response.usage为准。正文A127文档/B131文档，新增知识按原目录规则纳入；不能因为文档多或Action名称新就提高评分。该比较仅衡量显式预展开材料中的无工具信息使用和选择，不代表按需retrieval质量改善。

# 开发与独立性检查

这些检查发生在技能开发交付中，不增加日常优化阶段的校验门槛。

| 检查 | 结果与范围 |
|---|---|
| skill格式 | skill-creator quick_validate通过；短入口与按需参考 |
| 来源完整性 | 30个原始文件的git blob/完整hash、34段原文的行号/字节/hash及2份许可核对通过；见[source-checks](checks/source-checks.json) |
| 独立技术复核 | 硬件/API映射、格式、同步、Add/Cube推导无待修复发现；见[报告](technical-review/REPORT.md) |
| workflow/安装/注册 | [8个CPU测试通过](checks/package-tests.log)，覆盖完整安装/幂等与新skill、agent、contract缺失时拒绝不完整包 |
| 执行事实金标准 | [6项CPU检查](checks/sources/evaluation/private/results/cpu_checks.json)通过；[独立复核](evaluation-review/REPORT.md)无阻断问题 |
| 主体调用 | 24份有效、24个独立成功会话；1次容量失败同配置重试；所有源码/资料hash及B的12次真实入口加载核对通过 |
| 匿名评分 | 24份有效；[96项最终文件身份](checks/GRADES_LOCK.json)在解盲前锁定；引文均为答案中的连续原文；2次容量失败保留并重试 |
| 评分抽审 | 独立全量抽审8份/78事实，追加同类事实一致性检查；3项语义等价修正均在解盲前完成，原标记保留；见[裁决](scoring-review/ADJUDICATION.md) |
| 原内容保护 | [1465个受保护文件](checks/protected-check.json)保持实施前hash，包括runtime实现、schema、知识快照、routing及1.2.0；按实际实施前工作区比对，保留此前未提交工作 |
| 独立目录 | 整包复制到独立目录；Python审计钩子拒绝网络、原工作树、上游仓库及子任务输入路径后执行release检查；最终记录见[结果](checks/offline-release.json) |

runtime仍为0.7.0，D v0006、P v0003、O v0006、routing v0005保持原身份，默认图仍为v0003，未切换默认版本。knowledge.py未改。新增角色使用原Markdown外壳，不新增JSON schema或runtime阶段。

没有运行SDK构建或NPU实验。普通C++探针只执行现有SDK无关的整数tiling逻辑，CPU模型只检查当前规则下的地址/格式/依赖；不证明硬件执行正确性、真实瓶颈、因果关系、速度或HAP。

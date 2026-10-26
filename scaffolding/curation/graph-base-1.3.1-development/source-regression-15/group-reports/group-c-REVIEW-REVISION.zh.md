# 独立复核修正交付

case11–15保留原自主Action及完整20case范围。本次未实施候选、未测性能。

- 10份reasoning/C1中的38个true constraint引用逐谓词指向condition-audit.json实际basis字段；source_refs定位host/tiling/kernel及原oracle正文，并重绑全部依赖hash。
- case13/15：完整semantic_equivalence改为unknown，保留numeric_order缺项；partner/插值映射另列source.element_mapping_equivalence=true。Vector条件方案继续，补齐完整舍入、NaN/Inf、正负零和输入/输出Cast证据前不授权实施。
- case14：output_ownership改为unknown，逻辑无交另列已知。新增20case行跨度/示例粒度静态检查，给出按真实物理粒度A同owner、行段裁切/跨行汇集、合法尾写或原fallback方案；1023列FP16的2046B行跨度反例明确标注A=64仅为示例。R2源工作预测收紧为unresolved，性能仍not_tested/not_measured。
- P/O阅读记录及中文结果同步最终采用解释；正式C2/C3仍未形成。

实际验证：直接validate_decision 10/10；最新2df校验器下CLI decision 10/10、C1 10/10；10份Action绑定P路由重放相等；38个true constraint定位可解析；182个唯一文件引用hash匹配。全矩阵5×20case保留。验证细节见review-final-validation.json及review-cli-final.json。

唯一评估包修改为明确授权的runtime/src/aprof_runtime/action_decision.py同步，来源、目标及最终hash见validator-sync.json。其余改动仅在本输出目录。最终文件已冻结。

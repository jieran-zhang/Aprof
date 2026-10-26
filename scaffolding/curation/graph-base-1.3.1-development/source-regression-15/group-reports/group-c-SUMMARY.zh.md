# 原始算子11–15：两轮无硬件自主分析

所有5项均覆盖各自原20case。10份action-decision通过runtime validate_decision；10份C1通过严格schema与reasoning校验。CLI回执各保存在任务目录。

|任务|R1选择|R2新增判断|
|---|---|---|
|case-11 foreach_addcdiv_scalar|software_pipeline_stages|逐20case重新计算chunk数与尾长，所有tensor均远大于U，但真实每核循环次数依赖C_available。d=2且U=2048时FP32数据65536B，16bit数据65536B（raw32768+scratch32768）；U=4096需131072B。这个值是候选字节需求，不是设备容量。若所查可用UB不足，先保持U=2048并降d；若timeline已充分重叠则撤回加槽，转向有合法alias依据的scratch复用。|
|case-12 maximum|restructure_broadcast|抽样对齐完整20case的原rank解码与按外轴/连续内轴公式，证明case11/12/13/20的x1偏移等于linear；case12/13/20的x2索引为floor(linear/W)%H。case18源宽8193*sizeof(half)=16386不是32B倍数，不能靠UB padding声称静态Broadcast合法。int64值域虽小也不能授权cast；优先广播分段，比较语义未核验时保持原scalar compare。|
|case-13 apply_rotary_pos_emb|vectorize_scalar_loop|遍历D=64/128所有维度证partner映射在行内、两次partner回到原维度；half mode两半闭式等价。原源码对每维4个volatile乘积和2个加法（q/k），使Scalar瓶颈假设比单纯字段缓存更具体；原特殊case13 Inf、14 NaN仍不能由CPU地址证明精度。R1不先融合cos复用，因为case13 N=1完全没有跨head复用；BNSD相邻row改变seq，不能把前row trig盲目驻留。|
|case-14 transpose|reorder_contiguous_access|20case样本验证逆映射与perm双射，连续suffix仅case1/14（128/127元素）；case13保持batch前缀可降14个256×256转置。case6可视作B=2的9×65536转置，case10可视作133221×373，case12为B=3的91×4001；能合轴不代表小C专用Gather API适用。int64/NaN原始位必须保留。逻辑无交不足以证明DMA物理独占；1023列FP16行宽2046B，必须按真实写粒度A同owner裁切/汇集，完整工作预测收紧为unresolved。|
|case-15 resize_bilinear|vectorize_scalar_loop|按20case解析scale_factor到真实outH/outW，逐输出列枚举w0/w1集合并算span与unique数；整2倍下采样源pair不重叠，跨输出reuse不成立；8倍上采样case5共享源区显著，复用策略须分组。源行边界clamp使h0==h1或w0==w1允许读复用却不允许删四项运算：0*Inf/NaN仍影响结果。若API/精度不满足，只先外提oh相关坐标且仍用原ResizeOne算术，不声称Vector方案已实现。|

未构建、未native、未profiling、未访问外网、未训练；初始分析未读取历史实验结果、包测试fixtures、维护/验收报告或其他组输出；本次修正仅按主agent授权阅读独立审阅REVIEW.md。路由平台来自任务声明目标及包内映射，不是设备probe。5项均给出具体结构/参数域和fallback；严格C2因真实architecture/实施绑定缺项保持未完成，未生成C3。

每项结果：
- [case-11中文结果](../cases/case-11/RESULT.zh.md)
- [case-12中文结果](../cases/case-12/RESULT.zh.md)
- [case-13中文结果](../cases/case-13/RESULT.zh.md)
- [case-14中文结果](../cases/case-14/RESULT.zh.md)
- [case-15中文结果](../cases/case-15/RESULT.zh.md)

独立复核修正：全部true constraint引用现定位condition-audit.json的逐谓词basis字段并重绑依赖hash。case13/15将完整semantic_equivalence设为unknown，数学映射另列已知事实；Vector条件方案保留。case14将output_ownership设为unknown，并给出真实物理字节块同owner及行段裁切/汇集方案；未知A、基址/尾写契约不冒充设备事实。

按明确授权只同步了主包最新runtime/src/aprof_runtime/action_decision.py到评估包；来源/目标/hash见validator-sync.json。最终校验详情见review-final-validation.json和各任务CLI回执。

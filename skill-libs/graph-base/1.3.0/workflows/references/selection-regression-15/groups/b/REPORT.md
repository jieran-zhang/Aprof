# case-06..10 自主无硬件回归

只读原始source/workload；目标910C/A3来自任务配置，未探测设备。未读历史回归答案，未编译SDK、改算子、生成输入或运行硬件。所有性能保持not_measured；runtime通过只证明合同与身份，不证明收益或语义最优。



- [case-06](../../cases/case-06/REPORT.md)：action.hoist_invariant_control。R2：新增逐case地址几何计算：case20虽尾轴Gather，index前轴为[4,127]而X为[4,255]，前缀必须按X stride保留255；case13 rank1且N=1000，所有source只等于index，段外提前缀收益接近零。于是R2明确rank1保持简单路径，其余保留分段地址方案，优先检验rank3/4/5的除模减少。

- [case-07](../../cases/case-07/REPORT.md)：action.vectorize_scalar_loop。R2：新增按host规则展开全部mask所得几何：shrink列case15输出2048、源step2048，不能整span加载；new-axis size1的step0可折叠，case16/17/19有长物理连续后缀。R2把case15列读明确保留标量，而size1轴之后连续段可合并；小stride域新增流量按s=2/3/4分别计算，不以统一API覆盖宣称全域已优化。

- [case-08](../../cases/case-08/REPORT.md)：派生几何复用意图缺口。R2：新增逐case C与K统计：C在7..256，nearest K=1而bilinear K=8。D若存完整K×三坐标+权重每点nearest至少24B、bilinear224B（mask另计）；所以R2从全C一owner改为有界Ct×St，并建议保存基坐标+分轴差分而非完整8邻域记录，但精度乘法次序必须不变。nearest小K与reflection代价不同，不能统一宣称复用总成本。

- [case-09](../../cases/case-09/REPORT.md)：action.batch_vector_api_calls。R2：新增静态API/容量复核：none路径CompareScalar按64元素补齐，而输入fi只定义count个有效值，未来扩大T仍要定义实际比较尾域；Select模式2正文要求A2/A3另预留8192B。显式none/tanh均保留5*T*4的erfTmp分配，不能因tanh未使用就自动扣除。R2缩紧合法T域并保持所有原特殊值修正，收益仍未测。

- [case-10](../../cases/case-10/REPORT.md)：action.software_pipeline_stages。R2：新增按符号核数C_available计算循环条件：源useful=ceil(N/4096)，当C_available≥useful，每核L≤4096、无第二tile，因此不能仅由N很大断言重叠；真实核心数未知。R2将多tile作为pipeline有效域条件，补上FP32与half双槽均16*T显式字节的分账；若目标可用核数导致单tile则batch/原路径优先。

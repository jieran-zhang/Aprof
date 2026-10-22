# 原始算子01–05自主两轮静态分析

每任务均使用全部原20case；目标910C/A3仅为任务指定，未探测硬件。没有build/native/profiling、外网或训练，没有读取历史实验、测试fixtures、维护/验收报告或其他组结果。

- case-01 Exp：保留blockNum/blockLength与精确有效长度；T∈{1024,2048,4096}，原始输入/输出各2物理槽，FP32工作区仍仅当前计算tile一套。UB=(4s+8·[s=2])T+API预留≤B可用，即三dtype数据区均16T。序言只预取tile0；每轮DeQue当前输入后，合法发射下一tile到另一空闲槽，再计算当前tile、入输出队列并发有效长度写回。输出槽仅在MTE3完成后回收；tileCount<2保留单槽。Exp乘加顺序及Cast模式不变。

- case-02 Mish：仅FP32模板：fi绑定in，fo绑定out，删除fpIn_/fpOut_两项InitBuffer，fpWork_保留；保留开头Adds(fi,in,+0)和末尾Adds(out,fo,+0)的原指令次序（即原地Adds），避免擅自改变±0行为。in活到最终Mul，out活到MTE3完成。先T2048，再在原41216字节显式预算内比较T∈{2048,2560,3072,3392}，UB=12T+ceil(ceil(T/8)/256)*256+API预留≤B。低精度路径继续2048和原Cast/负尾Exp+Select。

- case-03 MaskedScale：删除outFp_，令of=xf，以Mul(xf,xf,mf)后Muls(xf,xf,scale)保持原先先乘mask再乘scale；FromFloat(yLocal,xf)保留原RoundMode。T=64k，第一候选4096；后续T≤floor64((UB原预算-API预留)/(2sx+sm+8+2Ibyte))，Ibyte表示int8/uint8 mask。输入输出所有权、每个有效count和半精度输出路径保持原定义；不把scale0或mask0替换成常数以规避Inf/NaN。

- case-04 SwiGLU：C2重新规划短S组的整段owner：Q=N/S段，核c分配[q0,q1)，处理R个完整段，R≥2且RS≤T、(5s+12·[s=2])RS+shuffleTmp≤B。一次读x[2qS:2(q+R)S]到packed，再以a[rS+j]=raw[2rS+j], b[rS+j]=raw[2rS+S+j]作UB向量重排；保持原Cast及Muls/Exp/Adds/Div/Mul，最后写y[qS:(q+R)S]。优先S∈{1,7,50}，候选R使RS≈512/1024/2048；其他S及API无法合法高效重排时走原segment路径，所有20case都覆盖。不能用逐元素GetValue实现shuffle冒充高效向量化。

- case-05 ApplyAdamW：保留host对齐512的blockFormer与输出owner，四路输入队列各配置2物理槽，输出1槽，低精度5个FP32 compute buffer仍1套。T=64k，系数float32=36、half/bf16=38；alpha*T+ceil(ceil(T/8)/256)*256+8192+2048≤B，并保留copy字段上限2097151/s。在当前tile DeQue/读入计算前后为下一tile独立槽预取，队列最大未DeQue数受SDK深度约束，逐代完成后回收。保持SafeSqrt、SafeDiv、weightDecay条件、bias与输出RoundMode全部不变；单tile回退原槽数。

每项已保存源码文件hash、20case成本表、完整28项Problem检索、按理由展开及回放校验、R1/R2 reasoning、aprof.action-decision/v1、严格C1 schema回执、真实P/O内部router结果、Action限定P/O咨询路由、正文行号与判断变化、中文报告。10份decision均通过validate_decision与CLI diagnosis verify-decision。

R2保留原父本，以新增静态证据复核结构预测；全部性能预测not_tested，不造加速比或C3。各自C2-limit.json精确记录未能构造严格C2的架构/API/dispatch缺项。

源码/公式分析支持这些候选值得实施检验；实际目标API、容量及完整正确性/收益仍需后继执行。

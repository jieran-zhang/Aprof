# R15 最终完整方案与C1/C2

已重读R14 C5/history；R14 source原20+3extra正确、20valid/HAP17，同窗R13 A17，parent rejected.991032788/worst1+24.9158%，directR0 accepted5.478682947。五padding域2/4/10/15/16实测1.001375/1.002791/1.005133/1.000368/.988636未支持预测，放弃R14。1不加padding仍回退，不声称binary未变/noise/bank因果，addendum已保留。R15实际父本是完整R13正确性探索版、工程仍R10。R14鲜窗R13余2 42.23需<=41.14、15 54.34需<=51.042857、16 31.32需<=27.425714，分别约2.58/6.07/12.43%时间缺口。其余17个过线特别19 A34.284us须保护；单完整A或B20原oracle+20valid+HAP20早停，否则最终R15后额度用尽，不开R16。

候选比较覆盖全20：bank相位已实测未支持、目标映射仍unknown，不续padding。继续C32/16或更大tile/alias有R13近中性和R6/R11回退证据。只缓存tile字段容易等价，但bulk搬运/Max/queue控制仍在，CSE可能已消除字段，故不能停止主要机会比较。选择完整长循环的静态槽租约、合并两input完成边、热tile快照与独立长输出策略。最强替代S2是一个packed input TQue2加Y1：两Pad后共用EnQue/DeQue/Free，仅减一套input动态管理，保留更少改动/SDK自动租约，但两套queue状态与事件pool仍可能保留；S1移除全部长plain队列管理的潜在工作更多，代价是显式slot/reuse/首次/收尾证明和新增Scalar分支。不预言源级调用减少等于速度。独立Y DISABLE来源R9 same域温和正方向与公开API，输出不同于输入配方；保护广播12/20、19原策略。性能unknown允许实测，缺PMU不自动否定。

通用分派：原samePipeline下plain half/f32/int32且blockLength>3*(half?15360:7680)，当前2/4/10/15/16。Host/tiling字节全R13，C24、relative512B q/r owner、U18432/9216、groups456/7296/2712/600/336、tail/必要GM/Max有效元素不变，无caseID或新增Key。新KernelMaximumPlainStream只此域使用；旧SamePipelined/所有其它类body全R13，Dispatch调用helper与全compiled binary变化仍可能影响未修改路径，不能承诺其binary/时间不变。

算法/数值：每tile仍同一个AscendC::Max(y,a,b,n)、同A/B顺序、同PIPEV；无Cast/alias/近似/运算重排。完整int32域和float NaN/Inf/有符号零等原oracle行为不变，原阈值/20集合不改。不用生成数据范围缩合同。tileElements同uint32在Init读取一次，tiling在整个launch只读且与输出分离；不复制256B结构、不改ABI。length/owner64位，n>0才发Pad/Max；off += n不越length，next只在remaining>tile时计算，因此next<length。Count只是valid min。GM Pad每次valid n*sizeofT字节、UB32B对齐尾<=B；dummy不算数学输入、不写GM。

资源所有实际Init：A TBuf VECIN2B、B TBuf VECIN2B、Y TBuf VECOUT B，B=U*sizeofT。无R14 padding，当前各B36864，共184320，含保守8192=192512<实测196352。相对地址模型A0=0/A1=B/B0=2B/B1=3B/Y=4B，TPipe当前SDK sequential allocator支持模型，非实测bank地址。旧queue类在new分支完全不实例化/Init，不占/共管manual事件；其它互斥分支最大184320，actual19 named182432原字节。特定Select TMP[188416,188544)独立，8KiB是budget reserve而不是假定追加物理区。新uint32 tile、seq/slot和视图是Scalar资源，寄存器/CSE/spill未知，不假0也不冒充UB。

真实lastconsumer与事件：每input槽s=0/1包含独立A_s、B_s。CopyIn(s)先在复用时Wait V_MTE2(s)，再MTE2 FIFO两个valid Pad，最后一次Set MTE2_V(s)保证两input都ready；Compute Wait该ready后才读。唯一两input消费者是同一Max，随后PIPEV，再Set V_MTE2(s)，故共同free真覆盖两者最后读；CopyOut只读独立Y，不需要A/B。两input没有queue管理，不同时存在TQue事件。普通HardEvent每类型独立ID命名空间0/1在实测SDK QUE_MAX_EVENT8范围内，非CrossCore counter。程序首CopyIn0不等不存在的free；稳态先只发合法next，next槽复用仅seq>=1；最后每个used input槽各消费最后free，无任务return不发/等通知。

Y单槽：除首次外，Max写Y前Wait上一MTE3_V(0)，确保前代MTE3最后读完；Max+PIPEV后Set V_MTE3(0)/MTE3 Wait，valid Pad出，Set MTE3_V(0)。最后消耗最后Yfree再PIPEALL。每tile都恰一次out-ready set/wait和free set/wait，输入每代也一对ready/free；末两inputfree与Yfree是收齐未消费代次，不是重复等。新全路径的0/1/2/奇数/回卷/尾DAG在static-check.py核计数与无环，但不能叫实测重叠。仍单Y所以可能等输出，没假删除依赖或保证理想overlap。

独立Y策略：aG/bG保留R13 DISABLE；仅新long yG在SetGlobalBuffer后设置DISABLE，B共享的所有广播/19依然原NORMAL，19 A原DISABLE保留。输出读者集合为空（kernel内），每有效元素唯一MTE3写，原fullTask计时不测后继算子。c220 GlobalTensor.address_经runtime配置alias影响DataCopyPad GM dst GetPhyAddr；Scalar oriAddress不受影响，不套950bit60。默认RW/NORMAL与DISABLE公共API支持、source span/actual新binary feature绑定，动态offset/honor/cache命中/HBM字节未知。输入cache Action/输入叶配方不是Y输出准入；Y成员O注册采用为空、直接引用官方API/实际c220通路，保持task-local graph-out。它可能丢cache复用或改变服务而回退，与手动控制不做内部单项因果归因。

工作成本：两输入Pad+一Max+一输出Pad仍每tile4个数据/数学API；GM仍3Ns。原input A/B和Y三个queue每tile各Alloc/EnQue/DeQue/Free=12源级管理调用删除，改静态视图/slot分支与8稳态Set/Wait（含复用free等待），源SDK还含动态AllocEventID/Release/state/cursor工作但编译可能部分消除。第一代/末drain另外闭合，不把短predicate、复制字节或API个数当同等成本。uint32 tile源级重复读取改一次，实际重复GM/CSE/spill未知；新代码体积、Scalar分支、描述参数仍在。Yhint不减逻辑字节、不额外分配UB。

实际读的P/O：P continuous.md用于唯一owner、C/g/U与5B+reserve；O pipeline.md用于queue/手写二选一、MTE2→V/V→MTE2/V→MTE3/MTE3→V四类边及prolog/drain；O scalar-control/recipes/tilingdata-access.md用于uint32只读hot snapshot/ABI及CSE边界；O buffer-lifetime/recipes/reuse.md用于全部真实Init和最后消费者。O slots.md作租约代次/强替代比较，不把普通Vector变全局槽。O cache-hint.md作保留输入/共享域策略和边界阅读；输出Y直接用sources/asc-devkit/.../GlobalTensor/SetL2CacheHint.md+installed c220 GM dst GetPhyAddr，不伪配方ready。D control_metadata_overhead正文区分源码工作/编译成本/寄存器，主变换及Y均graph-out；实际独立成员/作用域与P/O router完整保存。

C3/C4：原build先独立，随后本轮新身份原20原oracle+3longplain24 >2tile、slot回卷/short tail fullbit/special extra。整数exact、float原special/error，diagnostic bitexact原样，extra不计20/GM/HAP。按新授权仅未来C3用一次原launch顺序bundle：原measurement.py check成功后才原extra脚本，原device锁/独立native+oracle收据/连续budget父operation不重置，失败即停并保留未执行清单；脚本给prep只读核。C4仍独立同窗R0/R13探索A/B完整Task，原5+20真清L2/固定一次second/原anchor，全first/raw/invalid保留。known旧wrapper full chain unadmitted，普通安全/实际source/hash/build/oracle/测量状态分别诚实记录，无fake v4 implemented。

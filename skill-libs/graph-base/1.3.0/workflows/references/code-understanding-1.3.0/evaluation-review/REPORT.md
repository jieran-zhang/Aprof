独立 gold / CPU 模型复核：通过，无技术阻断问题。

复核对象是 eval-private/public 的六题 workload、host/tiling/kernel 与固定 rawdocs，以及 private/gold、GRADING_PROTOCOL 和 CPU/scorer helper。未读取 skill-draft、PKG 新 skill、runs、评测答案或后续评分。只在 review-gold 写入文件；未改源码、gold、评测协议或 FREEZE。

| 题目 | 独立核对结论 |
| --- | --- |
| 01 | host 调用原 tiling，3 blocks、blockLength=8340、tileElements=4096；有效长度 8340/8340/8339、尾部 148/148/147 元素。数学变换 2^(0.5*x-1) 与 FP32 临时量及 BF16 CAST_RINT 均匹配源码。BF16 显式 UB 49152 bytes，FP32 32768 bytes；每个 queue 只有一个 slot，不能由此声称双缓冲或已证明重叠。覆盖终点 25019 是排他端点，最后一个元素索引为 25018。 |
| 02 | 当前 scenario2 的 GM 输入每行读 52 bytes，加 28-byte gap，起点 0/80/160/240/320。UB 的 13 float 数据加 3 float 右填充为 64 bytes，再加 dstStride=1 的 32 bytes，行距为 96 bytes；五个起点 0/96/192/288/384，数据/pad/gap 与 480-byte 分配均匹配。UB->GM 读取按 align32(52)+32=96 前进；写出按 52+20=72 前进，最后写到排他端点340，分配360 bytes。五个20-byte输出间隔保持0xA5，末尾间隔也包括在内。V_MTE2保护Duplicate零初始化先于copy-in；MTE2_MTE3保护copy-in先于copy-out。 |
| 03 | 三次原 tiling 均为 [2,3]、total=6、1 block、blockLength=6。P/Q 的x2Stride=[1,0]是数学广播映射，不能代替真实分支。P/R均选half专用路径，row_=3，off=0和3各从x2_[0]读3 half。P的实际请求[0,6)超出4-byte分配，不能承诺完整确定输出；SetGlobalBuffer长度不分配GM。Q scalar映射正确，有限输入输出[3,4,8,7,7,9]；R实际三元素分配匹配专用路径，输出[3,7,8,3,7,9]。三half queue槽共24576 bytes。其余dtype分派、BF16经float与int8经half/float也与源码一致。 |
| 04 | main只启动2 AIC，__mix__(1,2)对应4 AIV。AIC各负责256x128、完整K=128，一次Mmad且无隐藏K循环；AIV各负责128x128，C起点以half元素计为0/16384/32768/49152。每AIC L1 A/B为65536/32768 bytes，L0A/B为65536/32768，L0C float为131072；每AIV UB32768。2201物理路径是ND half GM->NZ L1->Zz A2/Zn B2->NZ float L0C->ND half GM->UB half->原C GM。Fixpipe之后才激活，GM中间结果明确存在；MTE2_MTE1、MTE1_M、M_FIX、PIPE_FIX模式2核间同步、MTE2_V、V_MTE3逐边对应生产消费关系。 |
| 05 | 2201/scenario1的24 blocks按block%4与block/4映射，M循环16，N循环6或最终slab的2，每tile K循环128。A/B输入half、L0C float、输出half；GM B的[N,K]存储对应逻辑[K,N]。A1/B1同属L1，四槽byte范围[0,131072)、[131072,262144)、[262144,393216)、[393216,524288)；A2/B2属不同物理存储，ping/pong偏移0/32768 bytes，因此同offset不混淆。前10次K中A1为0000000011、B1为0000111100、L0交替01；子chunk地址来自kOffset*baseK*baseM/baseN，LoadData3D A和不转置的B 2D搬运与存储路线一致。前向事件保护就绪，MTE1_MTE2保护L1覆盖前最后一次LoadData完成，M_MTE1保护L0覆盖前Mmad完成读取。variant仅删循环M_MTE1 Wait，失去Compute(k)->Load(k+2)保证；剩余单bit flag生命周期也不再受配对保证。不能将这个静态结论写成已观测设备损坏或hang。Mmad 2/最终3及Fixpipe3确有UnitFlag协议，不能仅因缺少显式M_FIX就断言bug。 |
| 06 | helper做token级逆向更名，三个vector文件和cube文件与01/04精确还原；数学、常量、buffer数与同步未变。A3=2201，950PR/950DT=3510，LoadData2DParamsV2在A3不支持，不能错用于本目标。2201 A NZ->Zz而3510 A NZ->NZ，B两边逻辑NZ->Zn但参数结构不同；两分支共用源码层的Mmad/Fixpipe/激活不构成跨平台编译或运行证明。CrossCoreWaitFlag在A3/A2忽略pipe选择并阻塞全部后续流水；950的pipe参数生效。 |

对 API 适用性的核查使用 A3 条目而非名字推断：DataCopyPad 无 mode 重载支持A3，带mode重载限950；GM stride单位为bytes、UB stride单位为32-byte dataBlock，padding为元素。UB->GM的非32字节尾块按对齐物理块前进而只写有效blockLen。LoadData2D的srcStride是512-byte分形的起点到起点距离，dstGap是分形尾到下个起点的间隔，二者不能混用。Mmad的A3输入布局Zz/Zn和float L0C、Fixpipe的F322F16，以及half/float LeakyRelu均符合所用路线。Exp/Muls/Adds/Max在A3所需的float/half/int32类型可用；BF16或int8的对应cast路线已核对Cast的A3类型表。

CPU helper已先读完整实现并逐一对照所依赖源码片段/参数与官方规则，再隔离执行。只将RESULT输出目录在内存中改到本review目录，原helper文件未修改；原tiling_probe.cpp直接包含原始纯C++头并调用ComputeExpTiling/ComputeMaximumTiling/MakeNacrePlan，普通g++编译与运行，不构建SDK。6组检查全部通过。其余字节模型、标签布局模型和事件偏序是契约模型，不是NPU仿真；检查通过不等价于硬件验证，布局标签也不是数值精度oracle。

六份gold均为algorithm_strategy/execution/hardware各10分、每题30分，总计180分；每个fact ID独立、权重总和正确。引用的文件hash与行区间有效。独立scorer聚合检查验证每题全对30、全partial15、全omitted/wrong/unsupported为0；各维度只应用最小显式错误cap且不额外减分。GRADING_PROTOCOL区分省略、明确错误、无证断言和有依据的不确定性；省略不触发cap，简短回答与无正式引用不自动扣分，两arm应同等适用。没有新增事后错误cap。

验证边界备注：UnitFlag.md还说明Fixpipe启用NZ2ND时要设置Mmad的N优先计算方向（SetMMRowMajor）；给定mmad.asc没有显式调用，InitSocState和SDK默认配置不在本CPU模型内。现gold要求识别2/3协议及证据边界，没有承诺整体SDK有效，因此不构成阻断。若盲评答案据此提出有限保留，不能把它等同于忽略UnitFlag，或等同于宣称已观测bug；本说明已同步根与作者，不改变冻结gold及cap。

未运行评测Agent、NPU、SDK构建、硬件仿真或远程设备，也未核查实际数值位模式、耗时、3510可编译性或任何生产执行结果。风险仅限于静态材料和CPU模型不能覆盖这些执行事实。

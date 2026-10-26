# 完整例子：从 simplified key Add 工程读出实际策略

本例使用固定版本 devkit 的 `custom_op_simplified_key`，完整的 host、kernel、tiling、模板选择、Binary JSON 和构建片段随包保存，见 [A01–A08](source-index.md#a01)。上游工程注册的是 `ascend910b`，用于演示阅读方法；它没有证明已在 910C 构建或运行。硬件解释另由 A3/2201 适用文档支持，二者的证据范围分开。

## 算法与输入输出契约

算子目标是对同形输入逐元素计算 `z[i]=x[i]+y[i]`。README 和 `Add` 调用相互印证；OpDef 声明 ND 的 float16/float32，InferShape 将 x 的 shape 复制给 z，InferDataType 将 x 的 dtype 传给 z。模板选择只列出三者全 half 或全 float 的组合，不能因为三个模板类型分别命名，就说支持任意混合 dtype。[源码 A01–A05、说明 A08]

host 的 shape 推断没有展示 x 与 y shape 相等的校验；TilingFunc 也只从 x 获取总元素数。因此“合法输入的目标语义”和“这组文件实际证明的校验”应分开描述。代码没有广播索引，不应为其补造广播支持。[源码 A01/A02；推导]

## 分支是怎样形成的

`GenSimplifiedKeyFunc` 按 x dtype 返回 `custom_fp16` 或 `custom_fp32`。Binary JSON 把它们对应到两个二进制名。与此同时，TilingFunc 根据总长度决定模板轴 `TILE_NUM` 与 `IS_SPLIT`，两者不是一个含义：simplified key 用于二进制查找，模板参数进一步决定 kernel 内的编译期路径。[源码 A01/A04/A05/A07；说明 A08]

host 侧的相关内容可压缩为下列语义等价片段，完整原文见 A01：

```cpp
totalLength = input_x_shape.GetShapeSize();
NUM_BLOCKS = 8;
if (totalLength < 2048) {
    TILE_NUM = 1; IS_SPLIT = 0;
} else {
    TILE_NUM = 8; IS_SPLIT = 1;
}
context->SetSimdNumBlocks(NUM_BLOCKS);
tiling->totalLength = totalLength;
ASCENDC_TPL_SEL_PARAM(context, D_T_X, D_T_Y, D_T_Z, TILE_NUM, IS_SPLIT);
workspace_size = 0;
```

这说明当前实现使用固定启动数量和长度阈值，并不说明 8 是设备物理核数、2048 是硬件最佳阈值。tiling 结构只有 `totalLength` 一个字段；`TILE_NUM`/`IS_SPLIT` 来自模板路由。入口 `if constexpr` 选择 Process1/Process2，运行时不会每个 tile 都再执行这个选择。[源码 A01–A04；推导]

## 选择一个可完整计算的输入贯通路径

取同 dtype float32、连续 ND 的 `N=16384`，并按 host 的 8 个 block 解释 `GetBlockNum()==8` 的路径。它选择 `TILE_NUM=8, IS_SPLIT=1`。Init 的原始公式是：[源码 A02]

```text
blockLength = totalLength / GetBlockNum()
tileLength = blockLength / tileNum / BUFFER_NUM   // tileNum != 1
GM 起点 = blockLength * GetBlockIdx()
loopCount = tileNum * BUFFER_NUM
```

代入 `BUFFER_NUM=2`：每 block 2048 元素，每 tile 128 元素，循环 16 次。block b 的第 i 次迭代处理半开区间 `[2048b+128i, 2048b+128(i+1))`；b∈[0,8)、i∈[0,16)。区间互不重叠，联集恰为 `[0,16384)`。这是所选输入下的覆盖推导；对任意 N 的余数不能凭这个例子消除。[源码 A02；推导]

该策略把独立逐元素工作均分到 block，再在每个 block 内循环复用片上存储。数学上不需要核间合并，代码也没有展示跨核累加或通信。具体事件约束在核内保护 buffer 复用。[源码 A02；推导]

## 物理 buffer 与命名给出的暗示并不相同

Process2 只有这些静态分配，每个申请 2048 个元素：[源码 A02；元素单位 H15]

```cpp
LocalMemAllocator<Hardware::UB> ubAllocator;
xLocal = ubAllocator.Alloc<dtypeX, CALCULATE_SIZE>();
yLocal = ubAllocator.Alloc<dtypeY, CALCULATE_SIZE>();
zLocal = ubAllocator.Alloc<dtypeZ, CALCULATE_SIZE>();
```

所选 float32 路径三份用户数据区合计 `3*2048*4=24576B`，每次只对各 tensor 前 128 个元素进行有效搬运/计算。没有 TQue，也没有 `i%2` 地址切换或两套 X/Y/Z；`BUFFER_NUM=2` 仅参与 tileLength 与 loopCount 的算术。准确理解是“一组静态 UB tensor 的循环复用”，不能写成“已开启双物理 buffer”。[源码 A02；推导；H15/H16]

这也展示了为什么资源占用与有效 tile 工作集不能混为一谈：当前有效输入/输出总共 `3*128*4=1536B`，但分配空间是 24576B。二者都不是运行时总 UB 使用量的完整证明，因为还要考虑框架、编译器和其他隐含用途。[源码 A02；文档 H02；推导]

## 数据流与事件的完整解释

每次迭代先将 GM 对应范围的 X/Y 搬到 UB，由 Vector Add 写 Z，再将 Z 搬回 GM。同一套地址重复使用，因此既要保护生产者→消费者的就绪关系，也要保护消费者结束→下一次覆盖的复用关系。[源码 A02；硬件 H04]

| 代码位置 / 事件方向 | 它实际保护的关系 |
| --- | --- |
| 循环前 Set `V_MTE2`、Set `MTE3_V` | 初始化首轮可使用输入/输出 buffer 的事件状态 |
| 循环开头 Wait `V_MTE2` | 下一次 MTE2 覆写 x/yLocal 前，上一轮 V 已读完输入 |
| 两次 DataCopy 后 Set/Wait `MTE2_V` | 当前 Add 读取前，X/Y 数据已经搬入 |
| Add 前 Wait `MTE3_V` | 本轮写 zLocal 前，上一轮 MTE3 已读取旧输出 |
| Add 后 Set `V_MTE2` | 发布输入区可复用状态 |
| Add 后 Set/Wait `V_MTE3` | 当前输出搬出前，Vector 已写完 zLocal |
| 搬出后 Set `MTE3_V` | 发布输出区可复用状态 |
| 循环末尾两次 Wait | 消耗最后一轮留下的复用事件状态；入口还有 `PipeBarrier<PIPE_ALL>()` |

事件名称和顺序均来自 Process2；含义由 H04 的源/目的流水语义解释。MTE2、V、MTE3 属于不同流水，输入区和输出区也不同，但这不足以断言某次真实执行已有效重叠。源码的 printf、launch 和 host 开销也不能凭这一张表消去。

从算法所需数据量算，当前 N 的有效逻辑访问量为 `N*(4+4+4)=196608B`：读 X/Y 各一次、写 Z 一次。这个推导只计算有效 payload，不是实测 HBM 流量或耗时；cache、事务和运行行为没有在本次阅读中测量。[源码 A02；推导]

## 小数据与尾块：保留工程事实的边界

Process1 在 `tileNum==1` 时把 `tileLength` 设为整个 `totalLength`，而每个 GlobalTensor 的起始偏移仍用 `blockLength*GetBlockIdx()`，声明长度为 blockLength。若沿同样的 8 block 假设取 N=1024，blockLength=128，末 block 的数据范围从 896 开始、长度 1024，超过逻辑输入 `[0,1024)`。这组可见文件没有给出把该分支改成单 block 的配套条件。因此不能把“小数据分支覆盖正确”当作已证明；应记录此分支的 launch/范围契约未闭合。[源码 A01/A02；条件推导]

同样，Process2 的连续整数除法没有显示余数补偿和显式尾长，固定 `CALCULATE_SIZE=2048` 又给实际 tile 容量设置了条件。完整理解需说明“本例选定可整除输入的路径成立”，而不是承诺任意长度都有效。这是理解边界，尚未给它绑定问题分类、修改策略或优化方案。[源码 A02；推导]

## 一份可交接的理解叙述

> 当前 Add 工程按 dtype 选择二进制，再按 N<2048 的阈值选择编译期 Process1/2；tiling 仅传总长度，host 设置 8 个 block。对 N=16384、float32 且 GetBlockNum()==8 的 Process2 路径，每 block 处理 2048 元素，分成 16 次、每次 128 元素。三个静态 UB tensor 各有 2048 元素容量，由 MTE2 搬入、V 相加、MTE3 写回；事件同时保护数据就绪和单组 buffer 复用。所有 block 的有效范围共同覆盖输出，无跨核合并。BUFFER_NUM 的值不证明双物理缓冲；小数据分支及非整除长度的范围条件仍需配套工程证据。上述是源码与 API 支持的理解，未测量执行重叠和性能。

这段叙述由前文证据支撑。实际报告应引用目标项目自身位置，不能把教学样例中的常量或疑点复制给别的工程。

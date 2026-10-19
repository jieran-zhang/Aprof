# API、内存与同步约束

准确声明与目标宏以已安装 CANN SDK 为准。签名、repeat 上限、stride 单位和支持范围随重载变化；下列规则是检查要点，不是统一 ABI。

## 搬运、对齐与尾块

区分逻辑有效元素和对齐后的本地分配。DataCopy 前计算每核、每 tile 的源/目标字节范围，按重载核实 stride/block-length 的单位是字节、元素还是数据块。DataCopyPad 可支持部分非对齐搬运，但不能授权 GM 越界。只搬运有效 GM 元素，显式使用受支持的本地 padding/mask；排除偏移与总字节乘积溢出。

stride/broadcast 保留逐轴映射并验证最后的不完整块。基地址对齐不代表每行对齐；NDDMA 的维度、stride、padding 和目标支持以所选 SDK 为准。

## 队列与流水生命周期

AllocTensor/EnQue/DeQue/FreeTensor 在零工作量、末块、提前退出等每条路径都要形成合法生命周期，最后消费者结束后才可复用队列槽。不同变量名不证明 TBuf 与存活张量无别名。容量包含全部存活队列槽和临时张量。

SetFlag/WaitFlag 和跨核 flag 要记录生产流水、消费流水、事件 ID 与迭代；前一轮仍占有事件时不能复用。每个 barrier 参与者都必须到达，跳过工作不能跳过必需同步。替换同步 API 需要目标证据，不能靠泛化架构判断。

## Vector、Cast 与归约

逐重载检查 mask、stride、repeat 限制；声明将 repeatTime 限为 255 时应合法拆分，不能溢出字段。Counter/normal mask 的生命周期和 API 要求不同，跨调用按 SDK 契约维护 mask。

Cast 舍入、中间 dtype、累加次序、次正规数或近似模式可能改变语义，按原 checker 验证特殊值与误差。带索引归约保持相等值规则和索引宽度；只有 padding 对该操作为中性值时才能按对齐长度计算。

## Cube、矩阵与启动

MatMul/GMM 前检查平台/dtype、转置/layout、base tile、累加类型和 API scratch。MX/FP8 scale 打包属于输入契约，新目标支持不授权降低用户 dtype。MrgSort proposal 和索引布局同样以 SDK 为准。

Host/Kernel 必须统一参数顺序、uint64 tiling key、tiling 结构对齐/大小、workspace 和 blockDim。验证真实编译入口，不能只测 Python selector；直调必须显式分发或传 key，注册宏不会自动注入。

设备函数只用目标支持的语言和库，不能引入 host-only std API、动态分配或不支持重载。构建错误作为明确失败证据保留，修复进入新子候选。

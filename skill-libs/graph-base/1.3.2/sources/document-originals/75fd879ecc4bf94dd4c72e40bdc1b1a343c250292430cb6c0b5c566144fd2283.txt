# CV 数据通路（cv_datapath）

## 概述

本样例以 MatMul + ReLU 融合算子计算流程，展示 Ascend 950PR/950DT 产品在 **CV（Cube-Vector）数据通路** 方面的新硬件特性，介绍：

1. Mix 核（`__mix__(1,2)`）下 **AIC / AIV 协同**编程模型；
2. **Scenario1**：L0C → GM → UB → ReLU → GM（GM 中转融合）；
3. **Scenario2**：L0C → UB → ReLU → GM（Ascend 950 新增 Fixpipe / L0C→UB 直通）。

## 支持产品与 CANN 版本


| 产品                        | CANN 软件版本 |
| --------------------------- | ------------- |
| Ascend 950PR / Ascend 950DT | >= CANN 9.1.0 |


NPU 架构：`dav-3510`（以下使用28核Ascend950PR平台进行展示说明）。

## 算子与规格

$$
C = \mathrm{ReLU}(A \times B),\quad \mathrm{ReLU}(x)=\max(x,0)
$$

输入shape：

- [M, K, N] = [8192, 8192, 8192]
- [dtypeA, dtypeB, dtypeC] = [float16, float16, float32]
- A, B, C 数据格式均为 ND（生成数据时，会将B矩阵进行转置以实现高性能计算）


## 目录结构

```text
cv_datapath/
├── CMakeLists.txt
├── README.md
├── include/
│   ├── common_utils.h
│   ├── host_runner.h
│   └── kernel_common.h          # Cube 流水与 Fixpipe 封装
├── src/
│   ├── 0_separate.asc           # Cube / Vector 分离 launch
│   ├── 1_mix_scenario1.asc      # Mix + Scenario1（L0C→GM→UB）
│   └── 2_mix_scenario2.asc      # Mix + Scenario2（L0C→UB）
└── scripts/
    ├── gen_data.py
    └── verify_result.py
```

## 样例递进

| Scenario | 可执行文件                    | 说明                                                         |
| -------- | ----------------------------- | ------------------------------------------------------------ |
| 0        | `cv_datapath_0_separate`      | 先 launch MatMul（L0C→GM），再 launch ReLU（GM→UB→GM），无融合基线 |
| 1        | `cv_datapath_1_mix_scenario1` | 单次 Mix launch；AIC Fixpipe→GM，AIV 读 GM 做 ReLU           |
| 2        | `cv_datapath_2_mix_scenario2` | 单次 Mix launch；AIC Fixpipe→UB，AIV 直接 ReLU 后写 GM       |


建议阅读顺序：Scenario0（理解 CV 分离方案）→ Scenario1（理解 Mix 融合方案 + GM 中转）→ Scenario2（理解 L0C→UB 收益）。

---



## AIC↔AIV 的 CV 融合机制

在昇腾 AI Core 上，**Cube（矩阵乘）** 与 **Vector（逐元素算子）** 由不同硬件单元执行：


| 简称 | 全称           | 本样例职责                                   |
| ---- | -------------- | -------------------------------------------- |
| AIC  | AI Cube Core   | 执行 MatMul：GM→L1→L0→L0C，再经 Fixpipe 搬出 |
| AIV  | AI Vector Core | 执行 ReLU：在 UB 上做 `max(x,0)`，再写回 GM  |

若写成两个独立 Kernel 先后 launch（Scenario0），在实际执行时，将会在 AIC 上的MatMul计算全部结束后，才开始 AIV 上的 ReLU 计算，二者无法重叠。 

为了进一步提升性能，CANN提供了融合算子的开发范式。融合算子通常由多个独立的小算子融合而成，其功能与多个小算子的功能等价，而性能方面通常优于独立的小算子。融合了Cube计算、Vector计算的算子统称为CV融合算子。

下面分三点说明本样例采用的机制（对应 Scenario1 / Scenario2）。

### 1. CV 融合架构：`__mix__(1, 2)` 核函数

使用 `__global__ __mix__(1, 2)` 声明核函数，含义是：

- 该kernel声明为mix融合算子，其中 AIC 与 AIV 的配比数目为1:2；
- 同一份 Kernel 源码会分别在 AIC 与 AIV 上执行，用宏区分路径。

以 Scenario1 为例（Scenario2 结构相同，仅搬出通路不同）：

```cpp
__global__ __mix__(1, 2) void matmul_relu_scenario1(
    __gm__ uint8_t* a, __gm__ uint8_t* b, __gm__ uint8_t* c)
{
    AscendC::InitSocState();
    KernelMatmulReluScenario1 op;
    op.Init(a, b, c);
    op.Process();
    AscendC::PipeBarrier<PIPE_ALL>();
}
```

在 `Process()` 中，通过 `ASCEND_IS_AIC` / `ASCEND_IS_AIV` 拆分职责：

```cpp
__aicore__ inline void Process()
{
    if ASCEND_IS_AIC {
        // AIC：MatMul 累加到 L0C → Fixpipe 搬出 → 通知 AIV
        AscendC::LocalTensor<float> cLocal(...);
        pipe.RunMatmul(cLocal);
        pipe.FixpipeToGm(cLocal);   // Scenario1；Scenario2 则为 FixpipeToUbDualM
        AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(AIC_SYNC_AIV_FLAG);
    }
    if ASCEND_IS_AIV {
        // AIV：等待就绪 → ReLU → 写回 GM
        ReluFromGm();               // Scenario1；Scenario2 则为 ReluFromUb
    }
}
```

代码说明：

1. `__mix__(1,2)` = 「 AIC 与 AIV 的配比数目为 1:2 」；
2. `ASCEND_IS_AIC` / `ASCEND_IS_AIV` 决定当前硬件上实际走哪段代码；
3. 两边共享同一套 GM 指针与问题规模，但**本地 Buffer（L0C / UB）彼此独立**。



### 2. 跨核同步：AIC→AIV 数据就绪通知

AIC 把 MatMul 结果经 Fixpipe 写出之后，AIV 才能安全读取。本样例用 **CrossCore Flag** 相关的同步API 实现跨核同步：

```cpp
// AIC 侧：Fixpipe 完成后置位（PIPE_FIX 表示与 Fixpipe 流水绑定）
AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(AIC_SYNC_AIV_FLAG);  // flag = 0x8

// AIV 侧：进入 ReLU 前等待
AscendC::CrossCoreWaitFlag(AIC_SYNC_AIV_FLAG);
```

时序可以理解为：

```text
AIC:  CopyIn → Mmad → Fixpipe ──► SetFlag(0x8)
                                      │
AIV:  WaitFlag(0x8) ──► (读 GM 或直接用 UB) → Relu → 写 GM
```

注意：

- Set / Wait 必须**成对**出现；若某条路径提前 return，仍需保证对侧不会永久等待（多核/无任务场景尤其重要）；
- Flag 编号在工程中集中定义为 `AIC_SYNC_AIV_FLAG`（本样例为 `0x8`）；
- Scenario0 的两次独立 launch 之间由 Host `aclrtSynchronizeStream` 保证顺序，**不需要** CrossCore；Scenario1/2 则在核内完成同步。



### 3. `__mix__(1, 2)` 模式下的多核切分与双 AIV 分工



#### 3.1 逻辑核 ID（多核时）

`__mix__(1,2)` 下，`GetBlockIdx()` 在 AIC 与 AIV 侧**各自独立编号**：

- AIC：`0 ~ numAICores-1`
- AIV：`0 ~ numAIVCores-1`（约为 AIC 数量的 2 倍）

因此，当将来扩展到多逻辑核时，AIV 侧通常要把 BlockIdx 映射回逻辑核 ID，才能与 AIC 使用同一套 M/N 切分：

```cpp
uint32_t logicCoreId;
if ASCEND_IS_AIC {
    logicCoreId = AscendC::GetBlockIdx();
} else {
    logicCoreId = AscendC::GetBlockIdx() / 2;  // 每逻辑核对应 2 个 AIV
}
// 再由 logicCoreId 计算 mIterIdx / nIterIdx ...
```

> 本样例 `numBlocks=28`，MN 共 `8×8=64` 个 `singleCore` 块 / `16×16=256` 个 base tile，按  
> `blockId = logicCoreId; blockId < 64; blockId += numBlocks` 轮询分配；AIV 侧用 `GetBlockIdx()/2` 映射回逻辑核 ID。



#### 3.2 双 AIV 按 M 维拆分（本样例已使用）

即便只有一个逻辑核，`__mix__(1,2)` 仍会启动 **2 个 AIV**。本样例把 MatMul 输出的 `M` 行均分：

- SubBlock0：处理行 `[0, M/2)`
- SubBlock1：处理行 `[M/2, M)`

AIV 侧通过 `GetSubBlockIdx() % 2` 取得自己的子块索引：

```cpp
uint32_t localSubIdx = AscendC::GetSubBlockIdx() % 2;
uint32_t gmOffset = localSubIdx * (MATMUL_RELU_M / 2) * MATMUL_RELU_N;
```

Scenario2 中，AIC 的 Fixpipe 还会设置 `dualDstCtl = 0b01`，把 L0C 结果**按 M 维直接拆进两个 AIV 各自的 UB**，与上述分工一致。

---



## Scenario1：CV 融合 — GM 中转

**对应代码**：`src/1_mix_scenario1.asc`  
**定位**：Mix 核入门通路；中间结果落 GM，便于调试与理解「先 Cube 后 Vector」。

### 数据流

```text
GM ──(MTE2)──► L1 ──(MTE1)──► L0A/L0B ──(Cube)──► L0C
                                                    │
                                               Fixpipe (CO1→GM)
                                                    ▼
                                                   GM
                                                    │
                                               MTE2 (GM→UB)
                                                    ▼
                                                   UB ──VEC(ReLU)──► UB ──(MTE3)──► GM
```

与 Scenario0 的本质区别：Scenario0 是两次 Kernel launch；Scenario1 是**一次 Mix launch**，AIC/AIV 通过 CrossCore 衔接，Vector 侧仍从 GM 取数。

### AIC 侧：Fixpipe L0C → GM

Ascend 950 上使用 `FixpipeParamsArch3510`，目的端为 GM（`CFG_ROW_MAJOR_GM`，即 `isToUB=false`）：

```cpp
AscendC::FixpipeParamsArch3510<AscendC::CO2Layout::ROW_MAJOR> fixpipeParams;
fixpipeParams.mSize = baseM;
fixpipeParams.nSize = baseN;
fixpipeParams.srcStride = baseM;           // L0C 源侧 M 维步长
fixpipeParams.dstStride = MATMUL_RELU_N;   // GM 为 [M,N]，行宽是 N 而非 baseN
fixpipeParams.unitFlag = 3;               // 与 Cube unitFlag 收尾一致
uint32_t gmOffset = mTileIdx * baseM * MATMUL_RELU_N + nTileIdx * baseN;
AscendC::Fixpipe<float, float, CFG_ROW_MAJOR_GM>(cGM[gmOffset], cLocal, fixpipeParams);
AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(AIC_SYNC_AIV_FLAG);
```



### AIV 侧：GM → UB → ReLU → GM

```cpp
AscendC::CrossCoreWaitFlag(AIC_SYNC_AIV_FLAG);

uint32_t localSubIdx = AscendC::GetSubBlockIdx() % 2;
uint32_t gmOffset = localSubIdx * halfM * MATMUL_RELU_N;

// 1) GM → xUB
AscendC::DataCopyPad<float>(xUB, pipe.cGM[gmOffset], copyInParams, padParams);
// 2) ReLU
AscendC::Relu(yUB, xUB, halfMN);
// 3) yUB → GM
AscendC::DataCopyPad<float>(pipe.cGM[gmOffset], yUB, copyOutParams);
```

关键点：AIV 必须先完成 **MTE2（GM→UB）**，才能做 Vector 计算，因此 profiling 中通常能看到明显的 `aiv_mte2_time`。



---



## Scenario2：CV 融合 — UB 直通 / L0C→UB

**对应代码**：`src/2_mix_scenario2.asc`  
**定位**：Ascend 950 新特性使能样例；省去 AIV 侧 GM→UB，是本 Story 的核心收益点。

### 为什么需要 L0C→UB？

Cube 累加结果默认在 **L0C（CO1）**。传统路径是 Fixpipe 到 **GM**，再由 AIV 用 MTE2 搬进 **UB**。  
Ascend 950 的 Fixpipe 支持把 **L0C 直通 UB**（文档称通路 CO1→UB），于是：

- 少一次「写 GM + 读 GM」；
- AIV 的 `aiv_mte2_time` 可降至接近 0；
- 仅 **dav-3510 / Ascend 950** 支持该通路（A2/A3 无此能力）。

官方接口说明见：[Fixpipe API](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/latest/API/ascendcopapi/atlasascendc_api_07_0251.html)。

### 数据流

```text
GM ──(MTE2)──► L1 ──(MTE1)──► L0A/L0B ──(Cube)──► L0C
                                                    │
                                               Fixpipe (CO1→UB, dualDstCtl=0b01)
                                                    ▼
                                                   UB ──VEC(ReLU)──► UB ──(MTE3)──► GM
```

与 Scenario1 对比，**删除了「L0C→GM」以及「GM→UB」两段**，其余 Cube 前半段与 ReLU→GM 后半段保持一致。

### AIC 侧：Fixpipe L0C → UB（双目标按 M 拆分）

关键配置：


| 配置项             | 取值                         | 含义                                           |
| ------------------ | ---------------------------- | ---------------------------------------------- |
| `CFG_ROW_MAJOR_UB` | `{ROW_MAJOR, true}`          | NZ→ND，且目的为 UB（`isToUB=true`）            |
| `dualDstCtl`       | `0b01`                       | 双目标模式，按 **M 维**拆到两个 SubBlock 的 UB |
| `mSize`            | `DivCeilU32(baseM, 2) * 2`   | 按 M 拆分时对齐到 2 的倍数                     |
| `srcStride`        | `baseM`                      | L0C 源侧 M 维步长                              |
| `dstStride`        | `baseN`                      | 每个 AIV 子块 UB 内 ND 行宽                    |
| `unitFlag`         | `3`                          | 与 Cube unitFlag 收尾一致                      |


```cpp
AscendC::FixpipeParamsArch3510<AscendC::CO2Layout::ROW_MAJOR> fixpipeParams;
fixpipeParams.mSize = DivCeilU32(baseM, 2) * 2;  // 按 M 拆分时对齐到 2 的倍数
fixpipeParams.nSize = baseN;
fixpipeParams.srcStride = baseM;
fixpipeParams.dstStride = baseN;                 // 每个 AIV 子块 UB 内 ND 行宽
fixpipeParams.dualDstCtl = 0b01;                 // 按 M 拆到 2 个 AIV 的 UB
fixpipeParams.unitFlag = 3;
AscendC::Fixpipe<float, float, CFG_ROW_MAJOR_UB>(xUB, cLocal, fixpipeParams);
AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(AIC_SYNC_AIV_FLAG);
```



### AIV 侧：UB → ReLU → GM（无 GM→UB）

```cpp
AscendC::CrossCoreWaitFlag(AIC_SYNC_AIV_FLAG);

// xUB 已由 Fixpipe 写入本 SubBlock，无需 DataCopy GM→UB
AscendC::Relu(yUB, xUB, halfMN);

AscendC::SetFlag<AscendC::HardEvent::V_MTE3>(EVENT_ID0);
AscendC::WaitFlag<AscendC::HardEvent::V_MTE3>(EVENT_ID0);

uint32_t localSubIdx = AscendC::GetSubBlockIdx() % 2;
uint32_t gmOffset = localSubIdx * halfM * MATMUL_RELU_N;
AscendC::DataCopyPad<float>(pipe.cGM[gmOffset], yUB, copyOutParams);
```

Scenario1 至 Scenario2 的实现代码差异可概括为两处：

1. AIC：`FixpipeToGm` → `FixpipeToUbDualM`（`CFG_ROW_MAJOR_UB` + `dualDstCtl`）；
2. AIV：删除 `DataCopyPad` GM→UB 段。

---



## Scenario1 vs Scenario2 对照小结


| 对比项              | Scenario1（GM 中转）     | Scenario2（UB 直通）             |
| ------------------- | ------------------------ | -------------------------------- |
| Fixpipe 目的        | GM（`CFG_ROW_MAJOR_GM`） | UB（`CFG_ROW_MAJOR_UB`）         |
| AIV 取数            | `DataCopy` GM→UB         | Fixpipe 已写入 UB                |
| `dualDstCtl`        | 不需要                   | `0b01`（按 M 拆双 AIV）          |
| 典型 profiling 信号 | `aiv_mte2_time` 可见     | `aiv_mte2_time` ≈ 0              |
| 平台                | Atlas A2 / Ascend 950PR  | **仅 Ascend 950PR**              |

---




## 编译与运行

在仓库根目录先配置环境与工程（参考根目录 [README.md](../../../../README.md)）：

```bash
source ${install_path}/cann/set_env.sh
cmake -S . -B build -DNPU_ARCH=dav-3510
```

### 方式 A：只编译本样例（推荐）

`cmake --install` 默认会安装仓库内**所有**已配置目标；若只编译了本样例，安装会因缺少 `vector_add` 等其它二进制而失败。  
单样例请构建后直接在 `build` 产物目录运行（`gen_data.py` / `verify_result.py` 已由 CMake `COPYONLY` 到该目录），或使用本样例的 install COMPONENT：

```bash
cmake --build build --target cv_datapath --parallel

# 选项 1：在 build 目录直接运行
cd build/Samples/1_Features/hardware_features/cv_datapath

# 选项 2：仅安装本样例到 build_out
# cmake --install build --prefix ./build_out --component cv_datapath
# cd build_out/1_Features/hardware_features/cv_datapath
```

### 方式 B：全量编译后再安装

与仓库根 README 一致：先编完全部 Target，再 `cmake --install`：

```bash
cmake --build build --parallel
cmake --install build --prefix ./build_out
cd build_out/1_Features/hardware_features/cv_datapath
```

### 运行与校验

在上述工作目录执行以下命令执行算子二进制文件，确认功能正常、算子精度测试通过：

```bash
python3 gen_data.py

./cv_datapath_0_separate
python3 verify_result.py output/output.bin output/golden.bin

./cv_datapath_1_mix_scenario1
python3 verify_result.py output/output.bin output/golden.bin

./cv_datapath_2_mix_scenario2
python3 verify_result.py output/output.bin output/golden.bin
```

成功时打印 `test pass!`。



## 性能对比与分析

### 采集方法

在样例运行目录（已 `gen_data.py` 且精度校验通过）执行：

```bash
# Scenario0 含两次 launch，需采集 matmul_only + relu_only
msprof op --launch-count=2 ./cv_datapath_0_separate
msprof op ./cv_datapath_1_mix_scenario1
msprof op ./cv_datapath_2_mix_scenario2

# 采集Scenario1和Scenario2的算子流水执行图（使用Mindstudio Insight打开获得的visualize_data.bin产物）
msprof op --aic-metrics=PipeTimeline ./cv_datapath_1_mix_scenario1 
msprof op --aic-metrics=PipeTimeline ./cv_datapath_2_mix_scenario2 
```

关注 `OpBasicInfo.csv` 的 **Task Duration**，以及 `PipeUtilization.csv` 中各 AIC/AIV 的中位数（`aic_cube_*` / `aiv_mte2_*` 等）。

### 实测总览（Ascend 950PR，28 核）

| Case        | Op                      | Task Duration(μs) | aic_cube_time(μs)¹ | aic_cube_ratio¹ | aiv_mte2_time(μs)¹ | 说明                     |
| ----------- | ----------------------- | ----------------- | ------------------ | --------------- | ------------------ | ------------------------ |
| 0 分离      | `matmul_only`           | **3891.2**        | 2542.0             | 0.980           | ≈0（AIV 空闲）     | 仅 Cube→GM               |
| 0 分离      | `relu_only`             | **302.0**         | 0                  | 0               | 161.9              | 独立 Vector launch       |
| 0 合计      | 两次 launch             | **4193.2**        | —                  | —               | —                  | 无 CV 重叠               |
| 1 Scenario1 | `matmul_relu_scenario1` | **3909.7**        | 2542.0             | 0.975           | **57.4**           | GM 中转，融合覆盖 ReLU   |
| 2 Scenario2 | `matmul_relu_scenario2` | **3852.0**        | 2542.0             | 0.990           | **≈0.005**         | UB 直通，AIV 几乎无 MTE2 |

¹ `PipeUtilization.csv` 各核中位数（多数核持有 2 个 singleCore；临界路径核持有 3 个，`aic_cube_max≈3813`）；  
平台：Ascend 950PR，`Aicore Count=28`，`M=K=N=8192`，`baseM/N/K=256/256/64`，`singleCoreM/N/K=1024/1024/8192`，`numBlocks=28`，Freq=1650 MHz。

排序满足：**分离合计 > Scenario1 > Scenario2**。相对 Scenario0 合计，Scenario1 / Scenario2 约节省 **6.8% / 8.1%**；Scenario2 相对 Scenario1 约再省 **58 μs（≈1.5%）**。

### Scenario0：CV分离执行

| Scenario | Task Duration(μs) | Block Dim | Mix Block Dim | aic_time(μs) | aic_cube_time(μs) | aic_cube_ratio | aic_mte1_time(μs) | aic_mte2_time(μs) | aic_fixpipe_time(μs) | aiv_time(μs) | aiv_vec_time(μs) | aiv_mte2_time(μs) | aiv_mte3_time(μs) |
| -------- | ----------------- | --------- | ------------- | ------------ | ----------------- | -------------- | ----------------- | ----------------- | -------------------- | ------------ | ---------------- | ----------------- | ----------------- |
| MatMul   | 3891.2            | 28        | 56            | 2595.9       | 2542.0            | 0.980          | 818.4             | 2021.4            | 253.4                | ≈0.46        | 0                | ≈0                | ≈0                |
| ReLU     | 302.0             | 28        | 56            | ≈0.8         | 0                 | 0              | ≈0                | ≈0                | ≈0                   | 243.6        | 10.7             | 161.9             | 71.3              |

解读：

- MatMul 侧 `aic_cube_ratio≈0.98`，说明 L1/L0 PingPong + 大包搬运已把 Cube 算力吃满。
- `Block Dim=28` 对齐物理核；
- ReLU 侧耗时主要在 **MTE2（GM→UB）+ MTE3（UB→GM）**，`aiv_vec_time` 仅约 11 μs；分离执行时这段时间全部叠在 MatMul 之后。

### Scenario1：CV融合 - GM 中转

| Scenario  | Task Type | Task Duration(μs) | Block Dim | Mix Block Dim | aic_time(μs) | aic_cube_time(μs) | aic_cube_ratio | aic_fixpipe_time(μs) | aiv_time(μs) | aiv_vec_time(μs) | aiv_mte2_time(μs) | aiv_mte3_time(μs) | 备注      |
| --------- | --------- | ----------------- | --------- | ------------- | ------------ | ----------------- | -------------- | -------------------- | ------------ | ---------------- | ----------------- | ----------------- | --------- |
| Scenario1 | MIX_AIC   | 3909.7            | 28        | 56            | 2610.8       | 2542.0            | 0.975          | 267.3                | 2614.0       | 10.7             | 57.4              | 50.0              | L0C→GM→UB |

分析：

- Scenario1总耗时3909.7us，与Scenario0的单独MatMul任务耗时（3891.2us）接近，表明此时AIV的Vector计算时间基本被AIC的Cube计算时间覆盖，体现了 CV 融合方案的性能收益。

下图展示了Scenario1场景下的算子流水执行图。CV融合算子执行的流程为，AIC侧完成MatMul计算后通过Fixpipe将结果写入GM，AIV侧从GM读取数据，完成ReLU激活函数计算。

![image.png](https://raw.gitcode.com/user-images/assets/8788227/1bb238c6-7235-46ab-8757-7d57260d4374/image.png 'image.png')

### Scenario2：CV融合 - UB 直通

| Scenario  | Task Type | Task Duration(μs) | Block Dim | Mix Block Dim | aic_time(μs) | aic_cube_time(μs) | aic_cube_ratio | aic_fixpipe_time(μs) | aiv_time(μs) | aiv_vec_time(μs) | aiv_mte2_time(μs) | aiv_mte3_time(μs) | 备注   |
| --------- | --------- | ----------------- | --------- | ------------- | ------------ | ----------------- | -------------- | -------------------- | ------------ | ---------------- | ----------------- | ----------------- | ------ |
| Scenario2 | MIX_AIC   | 3852.0            | 28        | 56            | 2568.5       | 2542.0            | 0.990          | 211.6                | 2570.8       | 10.7             | **≈0.005**        | 80.2              | L0C→UB |

分析：

- 从Scenario1改进至Scenario2，总耗时进一步减少约57us
- 由于UB直通的方案中，数据搬运不再涉及GM通路搬运，Scenario2中aiv_mte2_time显著降低

下图展示了Scenario2场景下的算子流水执行图。改进为UB直通的CV融合算子执行后，在AIC侧完成MatMul计算后通过Fixpipe将结果直接写入UB，AIV侧在UB上进行ReLU激活函数计算。

![image.png](https://raw.gitcode.com/user-images/assets/8788227/c37adf5b-f8f4-4738-badb-58216c06b725/image.png 'image.png')


# MatMul Optimization Playbook

用于 MatMul / BatchMatMul / GroupMatMul / GMM / MMAD 类 candidate。只在算子族或源码锚点明确指向
MatMul 时加载；默认不要同时加载其他 operator playbook。

## Decision Gate

- **先建 DP/SWAT 基线**：枚举 `baseM/baseN/baseK`，确认 16 对齐、L0A/L0B/L0C 容量、`mCnt*nCnt`、tail block 和
  `aicNum`。没有这个基线，不生成 FullLoad 或 StreamK candidate。
- **SWAT / tail balance**：`mCnt*nCnt` 足够但末轮 tail 或 MN 边缘负载不均时，优先调整 `baseM/baseN` 评分、
  tail split、`usedCoreNum` 与 serpentine/window 调度。
- **FullLoad**：A 或 B 小侧可全量驻留 L1，且对侧循环次数 `T >= 2`、未进入 StreamK、L1 pingpong 仍可放下时才生成。
- **StreamK / DP+SK**：MN 欠并行或末轮空核明显，且 K 足够长、可接受 workspace partial reduce 与 AIC/AIV 同步时才生成。
- **MTE2 preload / pingpong**：trace 有 PING/PONG gap 或 MTE2 等待 CUBE，且 `kL1TileNum >= 2`、L1 slot 足够时生成。

## Capacity Formula

- `baseM * baseN * sizeof(float) * l0cDB <= L0C`，`l0cDB` 只有容量允许且 CopyL0C/Fixpipe 可 overlap 时取 2。
- `max(baseM, baseN) * baseK * sizeof(dtype) * 2 <= min(L0A, L0B)`；MXFP 场景把 scale A/B 也计入。
- SWAT L1：`(baseM*kL1 + baseN*kL1) * sizeof(dtype) * DB + bias/scale <= L1`。
- FullLoad：`full_side_bytes + streaming_side_bytes * nBufferNum + bias/scale <= L1`，且 full side 复用次数 `T-1` 足够覆盖驻留成本。
- StreamK workspace：每个 SK tile 至少保存 `baseM * baseN * sizeof(float) * kCnt` 的 partial，另加 AIC/AIV 通信区。
- Scale/bias/LUT coalescing：小参数搬运要按 `scale_per_K = ceil(K/group)`、复用因子和最小有效 MTE 粒度建模。

## Structural Patch Shape

- Host tiling 同步修改 `baseM/baseN/baseK/kL1/stepKa/stepKb/nBufferNum/l0cDB/usedCoreNum/workspace`。
- Kernel scheduler 同步修改 MN/K 坐标、tail tile、workspace offset、AIC/AIV handoff 和 CopyL0C/Fixpipe 目的地。
- FullLoad candidate 必须显式增加驻留侧初始化、对侧 streaming pingpong、失效条件和 fallback SWAT 路径。
- StreamK candidate 必须增加 K 分段、FP32 partial workspace、AIV reduce+cast、cross-core flag 与 DP/DP+SK 分支。
- MTE2 preload candidate 必须形成 prolog/steady/drain 或倒数轮 preload 结构，不能只是调 `nBufferNum`。

## Metric Delta

- SWAT/tail：per-core time 方差下降，末轮活跃核数上升，CUBE 利用不因小 base block 下降。
- FullLoad：小侧 GM_to_L1/MTE2 bytes 按 `(T-1)/T` 量级下降，CUBE wait 不上升。
- StreamK：active AIC 数接近 `min(mCnt*nCnt*kCnt, aicNum)`，但 workspace read/write 和 AIV reduce time 小于并行收益。
- Preload：PING/PONG gap、MTE2 wait 或 Fixpipe wait 下降，GM bytes 不增加。

## Abort Conditions

- 未知 SoC 的 L1/L0/Fixpipe 容量、scale/bias 布局或 MatMul API 平台边界。
- StreamK 与 FullLoad 同时成立但没有互斥决策；默认二者互斥，不混在一个 candidate。
- partial workspace combine、FP32 accumulate、Cast 回写或输出顺序无法证明正确。
- candidate 只服务单一 benchmark shape，却没有标记 `benchmark_specialized`。

# 910C code-understanding 独立技术复核

结论：未发现需要修复的技术或职责边界问题；P0/P1/P2/P3 发现均为 0。本结论是固定来源、当前草稿的静态复核，不代表已完成 SDK 构建或 910C 运行验证。

## 对象与方法

精读 `SKILL.md` 及 `engineering-reading.md`、`910c-hardware.md`、`example-add.md`、`example-cube.md` 四篇正文，检查算法 → 实际策略 → 数据/存储/布局/依赖 → 硬件行为的论证链。结合源 manifest、来源索引和必要原始片段核验，不把上游注释单独当成硬件规格。

同时审阅目标包 `workflows/contracts/code-understanding.md`、`workflows/agents/code-understanding.md`、主 workflow 的阶段推进段，以及 common/preparation/diagnosis/coordinator 的理解报告交接与复用约定。只写本复核目录，未修改作者草稿或公共包。

## 已核对内容

| 范围 | 草稿位置 | 独立核对依据与结果 |
| --- | --- | --- |
| 910C/A3/2201 边界 | `910c-hardware.md:7–13`、`SKILL.md:10` | H01:14–19、H02:3–14、M02:19–31 区分了 A3、2201 与具体项目型号。草稿没有把 A2 教学源码当成已在 910C 运行的证明，也没有移植 950/3510 的 Compact、负 stride 或 CV 直连行为。 |
| AIC/AIV 与 TPosition | `910c-hardware.md:17–28` | H02:14–30 与 H03:24–48 支持 AIC/AIV 分离、经 GM 交接，以及 VEC*→UB、A1/B1/TSCM→L1、A2/B2→L0A/B、CO1→L0C、A3 CO2→GM。未发现旧产品 CO2→UB 的混用。 |
| DataCopy 路径 | `910c-hardware.md:32–43` | H10:52–189、645–704、1094–1168，H11 架构分派，H12/H13 的 UB→UB intrinsic 与 PIPE_V 旁证，以及 H04 流水表相互一致。软件 UB→L1 被限定到具体 AIV/Matmul 重载，正确包含 GM workspace 与 AIC 消息工作。 |
| ND/NZ/ZZ/ZN | `910c-hardware.md:47–60`、`example-cube.md:37–50` | H09:42–62、176–216 与 C01:47–89 支持 half 分形和布局。对 32×48、48×64 全坐标用独立块遍历复核三条物理偏移公式；再按 C01 的 2201 LoadData 参数重建每核 A 的 8192 和 B 的 16384 个坐标，均与 ZZ/ZN 排布一致。`ifTranspose=true` 未被误译成数学 B 转置。 |
| DataCopyPad 的方向和单位 | `910c-hardware.md:64–76` | H05:138–179、H06:126–167 支持 GM 字节间隔、UB 32B 间隔、按块对齐与 padding 元素单位。11 个 float、GM 行长 16、右补 5 的推导为 blockLen=44B、GM srcStride=20B、UB 共 192B、紧凑写回 132B，计算正确；右补 20B 也在 H05 的单侧 ≤32B 条件内。没有把 isPad=false 当成补零。 |
| 物理槽、queue depth、预留与有效数据 | `910c-hardware.md:78–84`、`example-add.md:50–61`、`example-cube.md:54–66` | H07:97–108、H08:27–45、H15:36–49/79–103、H16:3–5 支持分配单位与编程方式。三队列双槽对齐量 2496B 正确，未再乘 depth。Add 静态分配 24576B 与有效 tile 数据 1536B 被区分；Cube 分别计 L1/L0A/L0B/L0C，未当成 UB。H02:40–59 的标称容量、SDK 预留和用户可用容量没有混为实际占用。 |
| 事件和异步边界 | `910c-hardware.md:88–101`、`example-add.md:65–80`、`example-cube.md:70–74` | H04:62–72、H02:174–224 与 A02/C01 对齐。Set/Wait 的方向及状态消耗、输入/输出复用依赖、核内/跨核/host stream 范围说明准确；没有把不同流水、双缓冲或事件的存在当成实测重叠。 |
| Add 的完整工程解释 | `example-add.md:7–44/84–90` | 联合 A01 host、A02 kernel、A03/A04 tiling/模板、A05/A06/A07 binary/build 核验。N=16384、GetBlockNum=8 时每 block 2048、每 tile 128、16 轮；128 个半开区间连续且互不重叠地覆盖 [0,16384)。有效访问量 196608B 正确。小数据 Process1 的条件性越界推导与非整除/容量限制均保留为契约未知，没有泛化成任意长度正确。 |
| Cube 的完整工程解释 | `example-cube.md:7–30/70–80` | 联合 C01 host/device、C03 CMake、C04 输入/参考脚本核验。固定 half GEMM 沿 M 轴分 2 block、每核读完整 B；float L0C 累加及 Fixpipe F322F16、ReLU=false、GM 行跨度 N 均匹配。131072B L0C、8388608 FLOPs 和 229376B 源码有效 payload 计算正确。没有补造 K 累加循环或逐位一致承诺。 |
| 理解报告和工作流职责 | `engineering-reading.md:53–57`、`SKILL.md:19–25`，公共 contract:3–30 | C0 后、C1 前为正式 Markdown 阶段；正文要求连贯解释并附必要源码上下文。无新机器 schema/runtime、无必跑工具或性能采集门禁；没有预选 Problem/Action/新 C2 策略。已有报告可直接复用，相关变化局部更新并保留后继，纯新增 profiling 不重做，与 skill 一致。 |

上表的 H/M/A/C 编号对应草稿 `sources/manifest.json` 与 `references/source-index.md`；原文均来自固定源清单指定 revision。

## 来源完整性抽查

使用 `git show <固定 revision>:<source_path>` 与 `git rev-parse` 抽查 M02、H02、H03、H05、H09、H10、A01、A02、C01、C04 共 10 份原始源文件。逐项核对固定 revision、Git blob、full_source_sha256，以及对应 13 个 snapshot 的 SHA256 和原始行区间逐字节提取，全部通过。

未替代根 Agent 的全量包 manifest/源码完整性核验；本次没有读取所有未用原文。

## 发现和建议

没有 actionable finding，因此 `issues.json` 中 issues 为空。不建议为了复核增加新的必跑脚本、性能门槛或报告产物。

## 范围限制

未运行硬件、SDK 编译或性能测试；没有生成优化代码。未读取 `eval-private` 或任何私有评测题、gold、参考答案；C04 是作者随包明确引用的公开上游教学输入/参考脚本。包测试、安装/发布完整性和作者后继修改由根 Agent 的整体验证覆盖。

## 审阅正文身份

- `SKILL.md`：`5bd1244fc69083c0d6a4c6a221dc0f46caa0f25392a9924a4ac4be8730e2885e`
- `references/engineering-reading.md`：`78d37849f7345e38d22c1e14e97ce73edad8825d53686a23389011427216c977`
- `references/910c-hardware.md`：`0bef452f8caaeee1c2498a19de83b821a887f115557facb59d557efb63669d74`
- `references/example-add.md`：`0eae50c42e51ceb7a7cabd356f80829bc0a9df675b41775e72f9e02499ca3b76`
- `references/example-cube.md`：`908b201edf08749338f45d38522c65e525414787096a81a2e5579bfc99a7f5c3`

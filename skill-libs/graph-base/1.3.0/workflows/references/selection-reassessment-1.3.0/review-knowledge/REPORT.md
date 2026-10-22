# P/O 知识独立技术审阅

结论：发现 1 个 P2 模型表述错误，未发现 P0/P1。其余本轮新增的 API 与平台约束、采样条件骨架、成本单位和来源归档在本次源码审阅范围内成立。结论不以 hash 或文档数量替代技术判断。

## 范围与方法

- 比较活跃包 `skill-libs/graph-base/1.3.0` 与 `/dev/shm/aprof-selection-v2-hx6s1amt/baseline-package` 的实际差异；审读 5 个 P 叶、9 个 O 叶、两个新增 router 路径、六个 Action 追加边界及 action-routing 的相关 diff。
- `planning/DELIVERY.md`、`optimization/changes.json` 仅用于找到文件。
- 原始源码限定 `/tmp/aprof-knowledge-sources-1SHAlx/direct/SOURCE_REVISIONS.json` 五个 revision。仅本地读取、CPU 检查，无网络、无设备运行、未修改公共文件。
- 技术核对包括 Compare/Select 文档及 dav_c220 实现、RoPE interleaved host→entry→SplitBS/BSN、GatherElements host→transpose/workspace、950 general Gather 和 RMSNormQuant host/kernel/CMake。

## 需修正

**[P2] K-P2-001：连续模板把核内循环误写为独立 task。**

文件：`skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md:186`。

新增「更大 h/U 会减少 task」不满足本叶自己的分区模型。C 已由 g/Q 固定，U 仅决定每核循环长度。反例 N=4096、g=64、C=8：U=64→128 后核内循环总量 L=64→32，独立 owner/task 数仍为8。同行 owner 内合并 h 行也不必减少 task。错误可能使选择阶段无故将增大合法 U 评为降低核间并行度。

建议替换为「更大 h/U 可减少核内批次/循环；仅当同时扩大跨 owner 工作域或改变分核策略时，独立 task 数才可能减少」。尾部浪费、活跃状态与槽位预算的其他描述保留。已发主 Agent，未改公共文件。

## 已核实的技术边界

1. **Compare/Select**：A2/A3 count 只处理完整256B、显式高维 mask 无效，分别由 Compare.md 约束和 dav_c220 `sumRepeat=count*sizeof(T)/256` 确认。half/float 全比较模式、int32 仅EQ、Select half/float 的限制与文档一致。代码中的 Compare 和 Select 模式2 count 签名正确；逐repeat连续消费predicate与模式0复用第一组的区分准确。`c=ceil(n/E)E`、`M=AlignUp(ceil(c/8),32)`、三个独立tensor下 `3cs+M+8192` 单位正确。文档已要求 padding 定义、输入依赖、Compare→Select依赖、有效输出以及API alias证明；未把32B DMA padding当256B比较域。
2. **临时UB和950**：Select 模式1/2 A2/A3预留8KB与固定文档一致；950 count/显式mask不占此8KB、不传mask高维重载占用，分别描述。RMSNormQuant CMake限定dav-3510且README限定950，源码使用VF/Reg；正文没有把该API路径移植到910C。general Gather README也仅列950；源码CPU_DEBUG的2201分支不能改变这一产品支持结论，正文未误用它。
3. **host/entry与实际数据路径**：RoPE host根据seq/batch/head、dtype转换和UB选择SplitS/BS/BSN，entry key实际映射相应类；BS offset表在Process开始处一次生成、每seq/batch循环复用，cos/sin同存储区在V→MTE2后覆盖，与正文区分“值复用/存储复用”相符。GatherElements `CalcMaxBufferSize()` 成功才选transpose，按核配置workspace；kernel确有转置输入/索引落GM、Gather结果再落GM、重新读回反转置。新增2W中转字节提醒有真实源码依据。
4. **公式与所有权**：广播B尺寸与A/Y尺寸分开；按行和r行并存的容量分开，跨核共享没有冒充片上共享。归约GS份完整状态及2GSb逻辑GM字节成立，Welford被明确要求完整count/mean/M2，数值树与调度成本独立。流水时间式在均匀tile、独立资源、合法重叠的限定下成立，未当作实测时延。除上述task混淆外，未发现本轮公式的确定性单位错误。
5. **采样骨架自足性**：新叶明确是机制推导，G/B/H/F、dtype/舍入、边界、真实stride和地址必须绑定。c无关条件限定跨c几何复用，输入X仍依赖c；有效源读取先判界；输出矩形独占，跨kernel几何表需阶段同步。几何构造NS·ceil(C/Ct)与最坏NCSK请求分开，UB与Scalar私有状态分开。它是条件化完整任务循环，不是完整插值数值kernel；正文没有假称后者。对随机坐标源窗口可行性有明确前提。
6. **路由与Action**：实际CPU route_tree可达两个新叶；缺约束时分别为needs_evidence，未自动填true。coordinate_mapping/neighborhood_bounds/precision强化采样约束。叶级match为空会产生较宽咨询，但前级indexing family/vector-api feature、叶scope、required_evidence及正文适用范围共同限定；reference_ready不是自动adopted_full。现有Action没有被放宽来冒充任意派生几何/权重复用；确无合法注册意图时保留提案边界，属于诚实缺口。未找到本轮新增的明确误阻断。

## 归档、重复与检索限制

独立以 `git show REV:path` 比对两处selection-v2归档的44个原始文件（含10份许可，五仓各有P/O副本）；全部与固定revision字节一致。另对39个manifest来源项的整文件/摘录hash核对通过。详细结果见 `source-checks.json`。这是可追溯性检查，不是数值或API正确性证明。

新增正文有明确增量：旧batch的count泛化被修正；Compare/Select正文集中维护，其他叶仅链接；值/存储复用和流水代价分别集中。来源目录存在同revision文件的归档重复，但本轮技术正文并非仅堆篇幅。未要求为去重而改冻结历史。

搜索还找到固定asc-devkit的 `BilinearInterpolation_ISASI.md`（UB Gatherb/Brcb/Mul/Add软仿API）及固定cannbot-skills的 `stencil-resize-gm-to-ub-staging.md`（Triton/IR模式经验）。二者不构成完整GridSampler/Resize host+kernel实现链，也不能无条件给本叶提供目标数值实现。因此「未找到可用完整实现链」的保守表述仍成立；这些资料可用于以后受限API/窗口补强，不能把其经验阈值直接带入当前方案。

## 检查局限

未编译目标SDK、未运行设备、未验证目标平台NaN/符号零/舍入或性能。CPU路由夹具的true只用于验证可达性，不是任何真实任务的证据；见 `route-checks.json`。修正K-P2-001后仍不能据本审阅宣称硬件收益已验证。

## 集成处理

K-P2-001 已在 v0003 规划知识冻结前修正为核内批次/循环变化，独立 task 只有重新分核或改变 owner 工作域才可能减少。公共 contract 已同步 measured_case_ids 与 attempt_identity。以上审阅发现保持记录，不代表当前仍有该缺陷。

# case-14 transpose

R1：按真实perm合并两端均连续轴；保留末轴的域直接搬连续条带，其余规则二维/批次二维域采用片上矩形转置，复杂perm保留通用索引fallback；Raw位宽搬运不转换数值，输出矩形互斥且只写有效元素。

完整路径：host检查rank<=8及perm双射、生成inputStride和outputShape；连续output分核，每输出从末轴倒序rank次除模重建source，原始位宽Scalar读写，不作数值运算。

原工作：N*rank次除法及N*rank次模，N*rank地址乘加，N次Scalar源读和N次Scalar写；逻辑必要GM=2*N*s字节

减少：连续后缀域每E元素一次外层地址解码并整段搬运；矩形域按tile外层解码，输入连续段DMA和UB局部置换替代N次离散源请求

代价：U=qX*A(tileR*inputPitch*s)+qY*A(tileC*outputPitch*s)+Boffset+BtransposeTmp；增加局部置换、尾mask和两方向padding，禁止GM中转被当免费

最强替代：仅缓存rank/stride及外提公共前缀成本小、全dtype通用，但一般转置仍每输出离散源访问；编译器可能已缓存字段，不能由源码加载次数推收益。

残余：任意高rank复杂perm与不支持的Raw宽度API仍需通用scalar映射；必要2Ns字节不变，局部重排和offset生成成为新增工作。

R2新增静态证据及复评：新增矩阵逐perm检查：case1、14保留末轴，连续后缀E=128、127；case2/3/4/5/7/8/9/11/17/18/19为二维交换；case13可分批二维交换；其余为一般置换。R2将原广义矩形方案限定为后缀条带和二维/批二维优先，其余保留fallback，收益覆盖不再泛称所有20case。

跨形态/代价反转纸面probe：反事实非实测：同N及dtype将perm由swap改为保留长内轴，连续条带可省局部transpose与offset，优先级更高；反之tile很窄且s=1，32B逐行padding大、局部表成本可能使Scalar地址递增更优。

Problem：problem.noncontiguous_access；替代problem.control_metadata_overhead。Action：action.reorder_contiguous_access；替代action.hoist_invariant_control。

实际读取P/O正文：
- skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md sha256:9b830c4ea01484b8a7e2d89e8c44d4d8087a821a2b887f3bd28c1e2172c53d49 lines:78-128。full conditional skeleton：输出到输入perm映射、Raw位宽、非原址、互斥矩形、fallback齐备；具体transpose API范围尚待证。影响：按真实perm合并两端均连续轴；保留末轴的域直接搬连续条带，其余规则二维/批次二维域采用片上矩形转置，复杂perm保留通用索引fallback；Raw位宽搬运不转换数值，输出矩形互斥且只写有效元素。 采用正文约束：U=qX*A(tileR*inputPitch*s)+qY*A(tileC*outputPitch*s)+Boffset+BtransposeTmp；增加局部置换、尾mask和两方向padding，禁止GM中转被当免费；替代边界：仅缓存rank/stride及外提公共前缀成本小、全dtype通用，但一般转置仍每输出离散源访问；编译器可能已缓存字段，不能由源码加载次数推收益。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md sha256:dbd61eaa8bb85b89b10ae445f1cff983baaaf8aa7a707b07900c18ac60262403 lines:77-132。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：按真实perm合并两端均连续轴；保留末轴的域直接搬连续条带，其余规则二维/批次二维域采用片上矩形转置，复杂perm保留通用索引fallback；Raw位宽搬运不转换数值，输出矩形互斥且只写有效元素。 采用正文约束：U=qX*A(tileR*inputPitch*s)+qY*A(tileC*outputPitch*s)+Boffset+BtransposeTmp；增加局部置换、尾mask和两方向padding，禁止GM中转被当免费；替代边界：仅缓存rank/stride及外提公共前缀成本小、全dtype通用，但一般转置仍每输出离散源访问；编译器可能已缓存字段，不能由源码加载次数推收益。
- skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md sha256:136b0642b2359171260588136c3cf909e46b82a62ef99790607771cade27d576 lines:57-107。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：按真实perm合并两端均连续轴；保留末轴的域直接搬连续条带，其余规则二维/批次二维域采用片上矩形转置，复杂perm保留通用索引fallback；Raw位宽搬运不转换数值，输出矩形互斥且只写有效元素。 采用正文约束：U=qX*A(tileR*inputPitch*s)+qY*A(tileC*outputPitch*s)+Boffset+BtransposeTmp；增加局部置换、尾mask和两方向padding，禁止GM中转被当免费；替代边界：仅缓存rank/stride及外提公共前缀成本小、全dtype通用，但一般转置仍每输出离散源访问；编译器可能已缓存字段，不能由源码加载次数推收益。

完整轻目录已检索，按源码展开Problem；额外正文反证：foreach必要Cast不可删除，Maximum已有Vector域不重复计收益，RoPE现有Cast不是算术Vector化，Transpose不能忽略局部重排，Resize派生几何复用不等于原输入驻留。停止比较因主要源码工作与最强替代已覆盖；性能主次与具体API/容量待后续授权实验。

未改算子、未编译SDK、未运行设备/正确性/计时；R1/R2均not_measured，性能接纳not_evaluated。P/O为真实内部router咨询，没有完整已确认C2，因此不伪造P_KEEP/C3实施。容量仅公式，actual cores/SDK/UB未知。


逐文档采用核对（此项为最终记录，替代前文合并描述）：
- skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md lines:78-128 sha256:9b830c4ea01484b8a7e2d89e8c44d4d8087a821a2b887f3bd28c1e2172c53d49；采用输出坐标到源perm映射、互斥矩形owner和有效宽度/物理pitch分离；先连续后缀、再规则矩形，复杂perm保留fallback。明确额外GM中转写读2W和局部表/transpose成本，禁止直接套小C TransDataTo5HD方案到全部dtype。 full conditional skeleton：输出到输入perm映射、Raw位宽、非原址、互斥矩形、fallback齐备；具体transpose API范围尚待证。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md lines:77-132 sha256:dbd61eaa8bb85b89b10ae445f1cff983baaaf8aa7a707b07900c18ac60262403；矩形源GM srcStride=(pitch-valid)*s按字节，UB dstStride按32B块；UB每行AlignUp(valid*s,32)并不改变GM有效长度。A3字段blockCount<=4095/blockLen<2^21作为实现检查，尾行只写有效域。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md lines:57-107 sha256:136b0642b2359171260588136c3cf909e46b82a62ef99790607771cade27d576；公共地址前缀只能升到依赖不变的最小外层，rank/stride缓存扩大活跃期并可能spill；保留源索引/位宽语义，编译器已CSE会削弱收益，不能仅因小改动优先。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。

最终审核：同范围谓词已去重，并从C1真实实例scope调用routing_context和P/O route_candidates；action绑定咨询与全部正文采用见consultation-r1/r2.json。没有P_KEEP或正式C2/C3。R1/R2机器回执见validation-r1/r2.json。
单位纠正：减少项为所选suffix/matrix域N条Scalar源load被DMA通路替代，不把N-ceil(N/E)推广到矩形；必要GM字节和新增DMA/局部置换独立计。

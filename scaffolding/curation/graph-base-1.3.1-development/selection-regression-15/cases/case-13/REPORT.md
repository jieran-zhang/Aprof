# case-13 apply_rotary_pos_emb

R1：保留row owner和读取，half mode将q/k两半分别Mul后Add/Sub，禁止FMA融合或重排原数值顺序；interleaved建立合法偶奇视图/UB重排后同序计算；保留数值与同步边，只有API、容量、特殊值契约闭合后实施。

完整路径：host验证BSND/BNSD和cos rank2/3；按row分核，整D行搬入q/k及D/2 cos/sin，必要FP32 Cast后逐d GetValue/SetValue执行两输出乘加；最后批量Cast/DMA，显式PIPE_ALL贯穿各阶段。

原工作：R=B*S*H rows，每行4D主输入输出+D三角输入，即5*R*D*s GM逻辑字节；每维两输出各两个乘法链与加法，Scalar loop R*D iterations；窄dtype每行5D cast elements。

减少：R*D次Scalar元素循环及其GetValue/SetValue改为每row常数个Mul/Add/Sub向量批次；不减少数学乘加或必要GM

代价：半分模式可用两段连续视图，interleaved需要配对重排/索引；Ubase=20D+10D*[s=2]字节，加临时Q(D)、padding、mask与API暂存

最强替代：保留cos/sin输入可减少trig读和Cast，但只占基线逻辑字节1/5；BSND相邻head容易同key，BNSD需跨S窗口或重排owner，仍保留全部Scalar乘加。

残余：cos/sin跨head重复DMA、row级屏障与小D搬运仍在；Vector API出现于Cast不代表原乘加已经批量化。

R2新增静态证据及复评：新增依赖域分析：BSND row/N给seq，相邻N个head共享trig；BNSD seq=row%S，head间复用距离S行。矩阵case13的N=1，head内复用因子为1而Scalar乘加仍D次。R2继续向量化且half/interleaved分开检验；输入驻留仅BSND同key连续窗口优先，不能声称全部20case等量减少输入。

跨形态/代价反转纸面probe：反事实非实测：D=2且N很大、BSND时Mul/Add小批次发射和重排可高于Scalar算术，trig驻留可能更优；D=128且interleaved重排代价可控则批量算术更合理。BNSD长S会削弱同owner小驻留窗收益。

Problem：problem.scalar_control_hot_loop；替代problem.insufficient_input_reuse。Action：action.vectorize_scalar_loop；替代action.reuse_input_tiles。

实际读取P/O正文：
- skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4 lines:83-138。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：保留row owner和读取，half mode将q/k两半分别Mul后Add/Sub，禁止FMA融合或重排原数值顺序；interleaved建立合法偶奇视图/UB重排后同序计算；保留数值与同步边，只有API、容量、特殊值契约闭合后实施。 采用正文约束：半分模式可用两段连续视图，interleaved需要配对重排/索引；Ubase=20D+10D*[s=2]字节，加临时Q(D)、padding、mask与API暂存；替代边界：保留cos/sin输入可减少trig读和Cast，但只占基线逻辑字节1/5；BSND相邻head容易同key，BNSD需跨S窗口或重排owner，仍保留全部Scalar乘加。
- skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1 lines:90-131。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：保留row owner和读取，half mode将q/k两半分别Mul后Add/Sub，禁止FMA融合或重排原数值顺序；interleaved建立合法偶奇视图/UB重排后同序计算；保留数值与同步边，只有API、容量、特殊值契约闭合后实施。 采用正文约束：半分模式可用两段连续视图，interleaved需要配对重排/索引；Ubase=20D+10D*[s=2]字节，加临时Q(D)、padding、mask与API暂存；替代边界：保留cos/sin输入可减少trig读和Cast，但只占基线逻辑字节1/5；BSND相邻head容易同key，BNSD需跨S窗口或重排owner，仍保留全部Scalar乘加。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md sha256:b09805a543555151cb41051cb57cfb967a8b47e68ae5d320820ef661806dc6e8 lines:97-152。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：保留row owner和读取，half mode将q/k两半分别Mul后Add/Sub，禁止FMA融合或重排原数值顺序；interleaved建立合法偶奇视图/UB重排后同序计算；保留数值与同步边，只有API、容量、特殊值契约闭合后实施。 采用正文约束：半分模式可用两段连续视图，interleaved需要配对重排/索引；Ubase=20D+10D*[s=2]字节，加临时Q(D)、padding、mask与API暂存；替代边界：保留cos/sin输入可减少trig读和Cast，但只占基线逻辑字节1/5；BSND相邻head容易同key，BNSD需跨S窗口或重排owner，仍保留全部Scalar乘加。

完整轻目录已检索，按源码展开Problem；额外正文反证：foreach必要Cast不可删除，Maximum已有Vector域不重复计收益，RoPE现有Cast不是算术Vector化，Transpose不能忽略局部重排，Resize派生几何复用不等于原输入驻留。停止比较因主要源码工作与最强替代已覆盖；性能主次与具体API/容量待后续授权实验。

未改算子、未编译SDK、未运行设备/正确性/计时；R1/R2均not_measured，性能接纳not_evaluated。P/O为真实内部router咨询，没有完整已确认C2，因此不伪造P_KEEP/C3实施。容量仅公式，actual cores/SDK/UB未知。


逐文档采用核对（此项为最终记录，替代前文合并描述）：
- skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md lines:83-138 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；确认按连续输出owner分区和valid长度，tile容量必须计所有实际分配；单槽/双槽只是假设。foreach完整结构适用；Maximum只覆盖同形；RoPE伴随partner读不满足逐元素同下标前提，仅采用owner/容量原则。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md lines:90-131 sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1；采用A3 memory Vector连续count与合法repeat的地址范围公式，避免950 Reg/VF。数值操作顺序和mask尾部须逐API核验；有Cast不代表主要Scalar算术已向量化。Compare非整256B边界不能从Add的count推合法性。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md lines:97-152 sha256:b09805a543555151cb41051cb57cfb967a8b47e68ae5d320820ef661806dc6e8；只有原输入同地址同版本才能驻留；保留到最后异步消费者结束，删除copy不自动扣除独立InitBuffer分配。RoPE限同owner trig key窗口；Maximum限broadcast源；Resize限同nc窗口公共原值，几何权重表不是原输入。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。

最终审核：同范围谓词已去重，并从C1真实实例scope调用routing_context和P/O route_candidates；action绑定咨询与全部正文采用见consultation-r1/r2.json。没有P_KEEP或正式C2/C3。R1/R2机器回执见validation-r1/r2.json。

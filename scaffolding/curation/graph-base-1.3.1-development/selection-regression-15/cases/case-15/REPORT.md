# case-15 resize_bilinear

R1：固定nc的连续空间St片生成原坐标/合法邻居，再收集四路值，按原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw顺序批量Mul/Add，保持FP32路径和B16回写舍入，输出统一有效DMA；不修改align/clip/Floor。

完整路径：NCHW输出连续分核；每输出decode nc/oh/ow，两轴ResizeCoord及Floor/clip，四邻居Scalar GM取值和FP32加权；float直接Scalar写，B16先逐点SetValue再按1024 Cast/DMA。

原工作：Nout次坐标解码、2*Nout次坐标映射，4*Nout原输入Scalar读和Nout写；权重乘加逐点执行；逻辑读写上界5*Nout*s字节，缓存命中未知

减少：将每点四项加权的Scalar乘加及B16逐点SetValue改为St点批量Vector计算；地址生成与四邻域收集作为明确残余，不把derived geometry当原输入

代价：四邻域FP32数组及输出至少5*A(4*St)，另加索引/权重/转换/原始暂存；Scalar gather→UB新增存储和同步，需比较St及原float直接写

最强替代：局部输入窗口驻留可减少上采样重读，但下采样邻域稀疏时加载未消费间隙，halo重读和UB局部gather增加代价；不能把跨channel坐标相同当相同输入值。

残余：坐标生成、Floor和间接读取仍逐输出；几何跨NC相同可减少派生计算但需独立意图，不能塞进reuse_input_tiles或控制字段缓存。

R2新增静态证据及复评：新增静态依赖证明：ResizeCoord/Floor及权重只依赖oh/ow和shape/align，与nc无关；实际x base依赖nc，所以几何复用与输入复用必须分开。矩阵同时含上采样与下采样，后者完整窗口可多搬未用元素。R2保持Vector加权为注册条件后继，把跨NC几何表列为intent gap并计算存储/task代价，不伪造已注册Action。

跨形态/代价反转纸面probe：反事实非实测：NC=1且强下采样，几何复用因子1、窗口输入可能膨胀，批量加权或直接Scalar有竞争；NC很大且St相同，几何复用由NC*St降为ceil(NC/Ct)*St，但D表存活及task减少使其未必优于重算。

Problem：problem.scalar_control_hot_loop；替代problem.insufficient_input_reuse。Action：action.vectorize_scalar_loop；替代action.reuse_input_tiles。

实际读取P/O正文：
- skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/coordinate_neighborhood.md sha256:5e4f96af8fde45ec3d5ea785c96c2243f211dbeeb93cd28c1f4d7e63bdf036fb lines:110-165。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：固定nc的连续空间St片生成原坐标/合法邻居，再收集四路值，按原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw顺序批量Mul/Add，保持FP32路径和B16回写舍入，输出统一有效DMA；不修改align/clip/Floor。 采用正文约束：四邻域FP32数组及输出至少5*A(4*St)，另加索引/权重/转换/原始暂存；Scalar gather→UB新增存储和同步，需比较St及原float直接写；替代边界：局部输入窗口驻留可减少上采样重读，但下采样邻域稀疏时加载未消费间隙，halo重读和UB局部gather增加代价；不能把跨channel坐标相同当相同输入值。
- skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1 lines:90-131。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：固定nc的连续空间St片生成原坐标/合法邻居，再收集四路值，按原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw顺序批量Mul/Add，保持FP32路径和B16回写舍入，输出统一有效DMA；不修改align/clip/Floor。 采用正文约束：四邻域FP32数组及输出至少5*A(4*St)，另加索引/权重/转换/原始暂存；Scalar gather→UB新增存储和同步，需比较St及原float直接写；替代边界：局部输入窗口驻留可减少上采样重读，但下采样邻域稀疏时加载未消费间隙，halo重读和UB局部gather增加代价；不能把跨channel坐标相同当相同输入值。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md sha256:b09805a543555151cb41051cb57cfb967a8b47e68ae5d320820ef661806dc6e8 lines:97-152。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：固定nc的连续空间St片生成原坐标/合法邻居，再收集四路值，按原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw顺序批量Mul/Add，保持FP32路径和B16回写舍入，输出统一有效DMA；不修改align/clip/Floor。 采用正文约束：四邻域FP32数组及输出至少5*A(4*St)，另加索引/权重/转换/原始暂存；Scalar gather→UB新增存储和同步，需比较St及原float直接写；替代边界：局部输入窗口驻留可减少上采样重读，但下采样邻域稀疏时加载未消费间隙，halo重读和UB局部gather增加代价；不能把跨channel坐标相同当相同输入值。

完整轻目录已检索，按源码展开Problem；额外正文反证：foreach必要Cast不可删除，Maximum已有Vector域不重复计收益，RoPE现有Cast不是算术Vector化，Transpose不能忽略局部重排，Resize派生几何复用不等于原输入驻留。停止比较因主要源码工作与最强替代已覆盖；性能主次与具体API/容量待后续授权实验。

未改算子、未编译SDK、未运行设备/正确性/计时；R1/R2均not_measured，性能接纳not_evaluated。P/O为真实内部router咨询，没有完整已确认C2，因此不伪造P_KEEP/C3实施。容量仅公式，actual cores/SDK/UB未知。


逐文档采用核对（此项为最终记录，替代前文合并描述）：
- skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/coordinate_neighborhood.md lines:110-165 sha256:5e4f96af8fde45ec3d5ea785c96c2243f211dbeeb93cd28c1f4d7e63bdf036fb；将Resize G绑定ResizeCoord、B绑定clip与边界h1/w1、H绑定四点/权重、F绑定原FP32乘加序列。仅部分采用空间块与依赖轴成本；还未证明最终API/容量。确认几何与nc无关而输入值依赖nc，派生表复用必须单列未注册意图，不归reuse_input_tiles。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md lines:90-131 sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1；采用A3 memory Vector连续count与合法repeat的地址范围公式，避免950 Reg/VF。数值操作顺序和mask尾部须逐API核验；有Cast不代表主要Scalar算术已向量化。Compare非整256B边界不能从Add的count推合法性。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md lines:97-152 sha256:b09805a543555151cb41051cb57cfb967a8b47e68ae5d320820ef661806dc6e8；只有原输入同地址同版本才能驻留；保留到最后异步消费者结束，删除copy不自动扣除独立InitBuffer分配。RoPE限同owner trig key窗口；Maximum限broadcast源；Resize限同nc窗口公共原值，几何权重表不是原输入。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。

另登记H-geometry，action_id=null，已进入两轮v2机会比较；该意图未注册，未以原输入驻留或控制缓存冒充。


最终审核：同范围谓词已去重，并从C1真实实例scope调用routing_context和P/O route_candidates；action绑定咨询与全部正文采用见consultation-r1/r2.json。没有P_KEEP或正式C2/C3。R1/R2机器回执见validation-r1/r2.json。

# gather R2第二次静态复核

对20case在起点、末端、半程和每个混合进位边界比较独立解码与递增base，共15250次边界地址断言；所有测试通过。这只确认地址模型，不证明编译后指令或NPU正确性。case20的index第二维127小于X的255，必须用源xStride而非展平index前缀；case13 rank1去掉全部坐标状态。

条件后继：取得目标编译器后先检查除模数量与spill；若除模确已消除或新增spill抵消，转入case7/20尾轴UB Gather候选；否则保持本意图实现并完整20case按位oracle检查，后做同协议Task比较。 另需确认原gather未对齐分核的Scalar写安全；若实际粒度导致共享写块，先由C2对齐owner边界再应用同一地址递增意图，不能把基线assumed当作正确性实测。

修订方案：保持原每核输出区间和Raw按位拷贝；每核begin只解码一次indexShape坐标，base=Σ(d≠dim)coord[d]*xStride[d]。逐元素用base+index[linear]*xStride[dim]读取；mixed-radix odometer按indexShape进位，以xStride加/减更新base，gather轴不加入base。rank1直接x[index]。只缓存rank、dim及实际使用stride/shape，最多8轴；不引入全量索引表、workspace或UB分配。保留host拒绝/设备guard及各dtype位模式；源shape非gather轴不等长仍用原xStride。

未执行候选、构建、native、oracle或性能计时；保留原始父本。

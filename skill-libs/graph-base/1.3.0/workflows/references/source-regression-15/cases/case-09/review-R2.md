# gelu R2第二次静态复核

逐20case重算模式域，9个tanh和11个none；T1024节约20736B的等式成立。确认erfTmp在none还被saved复用，不能从none再减一块；tanh的work ReinterpretCast<int32>只是视图，未新增物理区。R2坚持保留2^-23 RINT和none负尾修正。

条件后继：核对目标Erfc/Tanh/CompareScalar count与API临时预算后才设T上限；先单独验证删除无用分配，再同意图内增加合法T，完整20case含NaN/Inf/零和负尾域。若较大T不改善，保留资源简化但不宣称性能接纳。

修订方案：保留none/tanh定义和全部Cast/尾部修正。在Init按mode分配：none保持原erfTmp/mask；tanh省去两项无用分配。基于mode,dtype合法容量选择T：tanh{1024,2048,4096}，none{1024,2048}，T均64整数倍。tanh U=2*Align32(b*T)+3*Align32(4*T)+APIreserve；none另加Align32(20*T)+Align256(ceil(T/8))。只有U≤actualUB且count API允许才选择较大T，否则原1024分支。直调用实际mode字段/template分支接线，不伪造TILING_KEY_IS。

未执行候选、构建、native、oracle或性能计时；保留原始父本。

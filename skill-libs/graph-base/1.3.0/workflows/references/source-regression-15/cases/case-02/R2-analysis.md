# Mish：R2静态更新

生命周期逐项复核：fi在最后Mul前仍活，不能把fi和work互相覆盖；fo从Maxs后持续参与Add/Select/Tanh直到Mul。正确复用是fi=in、fo=out，不是fi/work/fo三者共用一块。保留两次+0，源工作预测调整为减少静态分配与扩大tile，不能宣称已删两条Vector指令。T3392时12T+mask512=41216，恰等于原20×2048+256。

具体条件后继：仅FP32模板：fi绑定in，fo绑定out，删除fpIn_/fpOut_两项InitBuffer，fpWork_保留；保留开头Adds(fi,in,+0)和末尾Adds(out,fo,+0)的原指令次序（即原地Adds），避免擅自改变±0行为。in活到最终Mul，out活到MTE3完成。先T2048，再在原41216字节显式预算内比较T∈{2048,2560,3072,3392}，UB=12T+ceil(ceil(T/8)/256)*256+API预留≤B。低精度路径继续2048和原Cast/负尾Exp+Select。

需确认目标Adds/Abs/Mul/Tanh等在VECIN/VECOUT位置及完全原地alias的支持，实际UB及Select/Tanh临时需求；不改变负尾-8阈值或浮点运算顺序。

R1未实现/未测量；只能支持源码结构预测，性能预测全部not_tested。父本仍为原始源码，R2不声明implemented C3或加速比。

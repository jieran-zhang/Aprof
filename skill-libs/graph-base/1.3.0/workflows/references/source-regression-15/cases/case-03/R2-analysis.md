# MaskedScale：R2静态更新

原xf最后读就是Mul本身；mf需读至Mul结束，之后两者旧值均无消费者。采用源一完全原地Mul须查API重叠许可；不需要让xLocal和xf跨dtype共用地址。20case逐项公式显示整数mask系数至少减少4，float32 mask和X组合也一致；scale=NaN/Inf(case12/13)或0(case7)均保留完整两个乘法及特殊值。

具体条件后继：删除outFp_，令of=xf，以Mul(xf,xf,mf)后Muls(xf,xf,scale)保持原先先乘mask再乘scale；FromFloat(yLocal,xf)保留原RoundMode。T=64k，第一候选4096；后续T≤floor64((UB原预算-API预留)/(2sx+sm+8+2Ibyte))，Ibyte表示int8/uint8 mask。输入输出所有权、每个有效count和半精度输出路径保持原定义；不把scale0或mask0替换成常数以规避Inf/NaN。

需确认目标Mul完整dst=src0别名及依赖完成规则，实际B与CopyPad/API字段上限。整型mask两段Cast的支持不能推断为直接转换支持。

R1未实现/未测量；只能支持源码结构预测，性能预测全部not_tested。父本仍为原始源码，R2不声明implemented C3或加速比。

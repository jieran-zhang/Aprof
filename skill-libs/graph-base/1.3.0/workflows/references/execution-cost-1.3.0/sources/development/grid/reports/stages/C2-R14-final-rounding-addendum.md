# R14 最终量化与实际补充

原half oracle先Cast回half，diff<=2^-9才清零，MERE严格<2^-10。FP32树误差小于floor不能直接证明最终half通过。有限|x|<32及8个[0,1]系数给出sumabs<256、gamma24*256约0.000367<floor/4的保守局部预算；这只作有限误差分析，不单独构成最终量化证明。对绝对结果较小者，half量化步长受floor约束；较大者即使只差相邻half，也可能在reference为2的幂、candidate绝对值为其上一个half时碰严格relative阈值。源码对absHalf>=4且mantissa==1通用位类别回算软件RN-even FMA，覆盖这一严格角点，并非枚举幂2值或按caseID。它不宣称全float形式化证明，原oracle和实际必要边界仍最终判定。

prep定向CPU确有可达<32例：X=0/8交替，half grid=(2^-11,-0.2073974609375,-0.96923828125)，假设邻接树Cast=4.00390625、Torch Cast=4，257点MERE=2^-10严格失败。仅CPU假设树，不称actualdevice失败；实际保护命中候选位类别。收据在ROOT/continuation-R6/final/measurement/R14-half-cast-targeted-CPU-contract.json。

计算dtype与输入dtype分开：small bilinear half和Float输入都改FP32 Mul+BlockReduceSum；large Float/half保R13顺序和overflowguard，nearest不变。Float small新tree的普通finite-cancellation不是R13正确性覆盖结论，新增独立原oracle fixture包含非dyadic坐标、相消、subnormal/大指数差和低于overflowguard幅值，正常/高幅值分开，已有非有限边界继续核。关联改变及新的数值保护属任务内research unadmitted，不借batch Action。

实际Half保护先扫wholeplane有限|x|>=32触发wholeplane软件；normal再每tile Cast、Abs/Maxs/两Shift/Adds/Compare/两级压缩，命中类别的点用保留rawHalf+coef软件回算，再Cast全tile。位操作scratch先2T B，pred@2T、temp@2T+256，最大2T+544B，均在失效values的32T B内，raw/coeff仍live。group liveidx/coef不覆盖。所有Compare/Scalar读写入口出口有ALL，Scalar结束再Cast/MTE3。额外扫描约22T基本UB字节另加predicate/压缩、Scalar查词/修正和可能二次Cast；原196T→132T只描述Mul+归约主链，不能当完整方案工作或速度比。有限>=32可能频繁fallback，全部成本实际计入，不把“罕见”作为事实。

资源按R14实际Init重算，见artifacts/R14-attempt-01-resources.json：原20最大named186880、加8192预算reserve195072<196352；fixedSelectTMP188416..188544独立不相交。AoS G512 half153984/float157056；full8 group9 tile1280/10块，旧four1664/8块源重读增加。原workspace、完整4/3/2Task和Host条件不变；R15范围沿scope-v2-confirmed，不复制旧budget5字段。

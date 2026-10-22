# R15 完整共同计划

父本R13-attempt-03。完整Host条件沿R13 useChannels：bilinear、plane>131072、C<=256、CP=Align16(C)、CP*item%64==0、inputPlaneBytes<2^32、S*item<=2^32-1、4*geometryLength<=2^32-1、最小batch真实UB可容；nearest仍原useNearestChannels条件。没有caseID分支。原20新pair域10/16/17/20，nearest5只有pack索引生成配套（P保持原值）；G/小源/原输出dtype/地址/精度父本保持，但wholebinary性能须新测。

Xp从[n,I+1,CP]改[n,I+1,2,CP]（只bilinear channel）。Xp[n,q,0,c]=X[n,c,q]，Xp[n,q,1,c]=X[n,c,q+HW]当q<I-HW，顶Z high=+0，sentinel q=I两个slot全+0，CP padding通道全+0。原X每块仍读一次/一次Gather原值输出UB；同out写low[q]及high[q-HW]两个stridedGM流，最后top高槽显式清零，末tile填sentinel。CP*item完整64B保证low/high槽与各producer物理块不同，不只声称每元素unique；MTE3两写末ALL后才能Duplicate/下tile覆盖。

workspace live Xp增加一倍，原Ypad/64G并存；四域额外178097920/32006144/390193152/520257536B。所有offset由相同factor和dtype/mode计算：Host geometryPtr在Xp+Ypad之后、sampleY与compactY在Xp之后，nearestfactor1；无分配后隐含一次初始化。四Task仍G→pack(含全部必要初始化)→sample→compact，同stream完成关系、timing/dispatch/map全包含。原HBM观测容量约65.8GB不等于未来free，正常Host原query/alloc实际结果保留。

合法内点需原index0/7均valid、W>=2、rowStride=(W-2)*2*CP*item<=2^32-1，八映射和范围经CPU核。一次2D: blockCount2、blockLen4*CP*item、srcStride上述GM字节、dstStride0，把[0,4,1,5,2,6,3,7]读入raw连续；边界/stride不满足仍8个单邻居请求，只读各record low，sentinel正确。所有Apply和软件FMA按slot(k)=2*(k&3)+(k>>2)恢复原k0..7顺序，weights/acc相同，不改变浮点关联。raw guard、UB2UB PIPE_V、最终transpose/Ypad/compact owner和原借用最后reader保留。

pack P在bilinear pair域按UB CP*(P*(2item+4)+32)<=188160、P32倍数、Gather元素<=255*256/item共同参数化，不依赖caseID；nearest P保512逐半旧规则。原20 10CP112/F32P128、16CP16/F32P960、17CP64/F16P352、20CP64/F32P224，额外写流/所有pad/初始化和P变化的Task数需实际核算。R9大P反慢保留为反证，当前不是通用最佳阈值。

配套索引生成：CP power2时 q=p*CP+c，p=q>>log2CP、c=q-(p<<log2CP)，idx=c*pitch+p*item。用Arange/Shift/Sub/Muls/Add在合法int32范围分一块Float或两块Half生成，以失效raw/out为scratch；其最后Vector读完成ALL后再Duplicate raw定义Cpad/尾，之后原MTE2覆盖。非power2 CP保原逐p Arange；元数据不改变tensor位值。wideP没有以多P次Scalar/API init抵消的必然优点，实际新增整数Vector工作/依赖完整计入。所有实际Init/32B对齐/TMP/lease由新源独立重核，未拿R14或R13 passed当本轮证据。

全20原oracle及原所有30aux（包括R14 newtree六fixture即使本轮不再有tree），加新pair大源Half/Float正常/Float极值、跨N/S尾和padding/special完整callback。原oracle/floor/严格门槛不改，所有失败保留。整体继承数值/派生GM与wrapper缺口unadmitted；新layout可按registered reorder真实局部route，pack索引metadata子目标独立说明，不新登记Action或伪造profile。C4唯一R15-001 freshR0/R13/B，双直接结果与HAP逐case；额满即停无R16。

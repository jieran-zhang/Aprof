# grid_sampler_3d R1当前源码事实与方案

每个(N,C,S)输出都重复读取同一(n,s)三坐标、半精度转FP32、unnormalize、padding与floor/round；nearest再读1个x，trilinear最多8个x并保持8项加法。原坐标计算N*C*S次，grid逻辑读3*b*N*C*S；FP16输出1024tile占显式6144B并3次PIPE_ALL，FP32单元素写。

新P按(n,channel-group,spatial-tile)拥有互斥输出，H∈{4,8,16}, T∈{64,128,256,512}。同一个空间tile先算一次坐标几何，再按channel顺序采样，保留原GridRead边界和三线性八项相加/乘法顺序；只缓存x0/x1,y0/y1,z0/z1与6个独立FP32轴权重，禁止预乘权重改变舍入。nearest缓存3个int64坐标。U≤Align32(3*b*T)+Align32(geometry*T)+Align32((b+4)*T)+reserve，geometry=72或24B；输出每次只保留一个channel的T元素；不新增GM workspace。R1按channel-group输出所有权只是逻辑互斥；跨组和空间tile边界的物理独占需实施前核验，尤其S*b非64B倍数。原路径fallback。

所有case C=7..256，重复坐标工作是明确源码成本；相比仅驻留原grid，几何共享同时删去floor/reflection/权重，x随机读取和原算术保留。相比全向量化采样，它较少改变数值API及64位索引路径。

输入快照含完整host/tiling/kernel、原20case、定义及oracle。所有数值为源码/公式，非profiling；基线assumed。

所有原case均保留：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
优化适用case：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
其余原case走明确fallback，同样属于完整后续正确性/性能域。

语义审查：同(n,s)坐标与channel无关；相同float表达式/顺序，保留half转换、GridRoundEven、reflection、8项累加，物理owner为独立待补条件。

逐项实施条件依据：
constraint.semantic_equivalence：GridSampler3DOne的gridBase、unnormalize、padding、floor/round和独立轴权重只依赖(n,s)及只读metadata；按原float顺序重用同值，不改每channel x样本/八项累加或Cast。输出物理owner另列unknown。
constraint.control_equivalence：在同batch/同空间片/同interpolation,padding,align范围内channel不参与坐标表达式；跨该范围立即重算。R2保留原owner并限制完整channel平面。

源码复合观察分量：
GridSampler3DScalar/ Half每输出调用GridSampler3DOne，重复3个grid load及坐标/权重表达式。
gridBase=(batch*spatialOut+spatial)*3，无channel项；input xBase含channel，不能一并缓存为全局不变量。
host计算n,c,d,h,w、float尺寸与模式；tiling struct经H2D并被kernel同一结构读取。
